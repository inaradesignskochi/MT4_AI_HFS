#!/usr/bin/env python3
"""
AI Scalping System - Flask REST API Backend
===========================================

This Flask application serves as the backend API for the AI-powered high-frequency
scalping trading system. It handles:

1. Tick data ingestion from MT4 Expert Advisor
2. Signal serving to MT4 EA
3. Real-time dashboard streaming (SSE)
4. Trade logging and performance metrics
5. System status monitoring

Author: AI Assistant
Date: 2025
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import sqlite3
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/api.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database configuration
DATABASE_PATH = 'trading_system.db'

# In-memory cache for fast access
cache = {
    'latest_ticks': [],
    'feature_vectors': [],
    'latest_signals': None,
    'system_status': 'INITIALIZING',
    'metrics': {
        'today_pnl': 0.0,
        'win_rate': 0.0,
        'wins': 0,
        'total_trades': 0,
        'signals_today': 0
    },
    'live_positions': [],
    'recent_trades': []
}

# Thread lock for cache operations
cache_lock = threading.Lock()

def init_database():
    """Initialize SQLite database with required tables."""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()

            # Create ticks table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ticks_raw (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    symbol TEXT,
                    bid REAL,
                    ask REAL,
                    spread REAL,
                    volume INTEGER,
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            ''')

            # Create trades table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket INTEGER,
                    symbol TEXT,
                    type TEXT,
                    lots REAL,
                    open_price REAL,
                    close_price REAL,
                    profit REAL,
                    swap REAL,
                    commission REAL,
                    open_time REAL,
                    close_time REAL,
                    sl REAL,
                    tp REAL,
                    comment TEXT,
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            ''')

            # Create signals table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    direction TEXT,
                    confidence REAL,
                    entry_price REAL,
                    sl REAL,
                    tp REAL,
                    timestamp REAL,
                    executed INTEGER DEFAULT 0,
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            ''')

            conn.commit()
            logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

def get_db_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def calculate_metrics():
    """Calculate trading performance metrics."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Get today's trades
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_timestamp = today_start.timestamp()

            cursor.execute('''
                SELECT profit, close_time
                FROM trades
                WHERE close_time >= ?
                ORDER BY close_time DESC
            ''', (today_timestamp,))

            trades = cursor.fetchall()

            if not trades:
                return {
                    'today_pnl': 0.0,
                    'win_rate': 0.0,
                    'wins': 0,
                    'total_trades': 0,
                    'signals_today': 0
                }

            total_trades = len(trades)
            winning_trades = len([t for t in trades if t['profit'] > 0])
            today_pnl = sum(t['profit'] for t in trades)

            win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0

            # Get signals count for today
            cursor.execute('''
                SELECT COUNT(*) as signals_count
                FROM signals
                WHERE timestamp >= ?
            ''', (today_timestamp,))

            signals_result = cursor.fetchone()
            signals_today = signals_result['signals_count'] if signals_result else 0

            return {
                'today_pnl': round(today_pnl, 2),
                'win_rate': round(win_rate, 2),
                'wins': winning_trades,
                'total_trades': total_trades,
                'signals_today': signals_today
            }

    except Exception as e:
        logger.error(f"Error calculating metrics: {e}")
        return cache['metrics']

def get_live_positions():
    """Get current open positions."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT ticket, symbol, type, lots, open_price, open_time, sl, tp
                FROM trades
                WHERE close_time IS NULL
                ORDER BY open_time DESC
                LIMIT 10
            ''')

            positions = cursor.fetchall()
            return [{
                'ticket': p['ticket'],
                'symbol': p['symbol'],
                'type': p['type'],
                'lots': p['lots'],
                'open_price': p['open_price'],
                'open_time': p['open_time'],
                'sl': p['sl'],
                'tp': p['tp']
            } for p in positions]

    except Exception as e:
        logger.error(f"Error getting live positions: {e}")
        return []

def get_recent_trades(limit: int = 10):
    """Get recent closed trades."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT ticket, symbol, type, lots, open_price, close_price,
                       profit, open_time, close_time, sl, tp
                FROM trades
                WHERE close_time IS NOT NULL
                ORDER BY close_time DESC
                LIMIT ?
            ''', (limit,))

            trades = cursor.fetchall()
            return [{
                'ticket': t['ticket'],
                'symbol': t['symbol'],
                'type': t['type'],
                'lots': t['lots'],
                'open_price': t['open_price'],
                'close_price': t['close_price'],
                'profit': t['profit'],
                'open_time': t['open_time'],
                'close_time': t['close_time'],
                'sl': t['sl'],
                'tp': t['tp']
            } for t in trades]

    except Exception as e:
        logger.error(f"Error getting recent trades: {e}")
        return []

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'system_status': cache['system_status']
    })

@app.route('/api/ticks', methods=['POST'])
def receive_ticks():
    """Receive tick data from MT4 Expert Advisor."""
    try:
        data = request.get_json()

        if not data or 'ticks' not in data:
            return jsonify({'error': 'Invalid tick data format'}), 400

        ticks = data['ticks']
        symbol = data.get('symbol', 'EURUSD')

        logger.info(f"Received {len(ticks)} ticks for {symbol}")

        # Store ticks in database
        with get_db_connection() as conn:
            cursor = conn.cursor()

            for tick in ticks:
                cursor.execute('''
                    INSERT INTO ticks_raw (timestamp, symbol, bid, ask, spread, volume)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    tick.get('timestamp', time.time()),
                    symbol,
                    tick.get('bid', 0),
                    tick.get('ask', 0),
                    tick.get('spread', 0),
                    tick.get('volume', 0)
                ))

            conn.commit()

        # Update cache
        with cache_lock:
            cache['latest_ticks'] = ticks[-100:]  # Keep last 100 ticks

        return jsonify({'status': 'success', 'ticks_received': len(ticks)})

    except Exception as e:
        logger.error(f"Error processing ticks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/signals', methods=['GET'])
def get_signals():
    """Serve latest trading signals to MT4 EA."""
    try:
        with cache_lock:
            signal = cache.get('latest_signals')

        if signal:
            return jsonify(signal)
        else:
            return jsonify({'status': 'no_signal'})

    except Exception as e:
        logger.error(f"Error serving signals: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/signals', methods=['POST'])
def post_signal():
    """Receive signals from signal generator service."""
    try:
        signal = request.get_json()

        if not signal:
            return jsonify({'error': 'Invalid signal data'}), 400

        logger.info(f"Received signal: {signal}")

        # Store signal in database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO signals (symbol, direction, confidence, entry_price, sl, tp, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal.get('symbol', 'EURUSD'),
                signal.get('direction'),
                signal.get('confidence', 0),
                signal.get('entry_price', 0),
                signal.get('sl', 0),
                signal.get('tp', 0),
                signal.get('timestamp', time.time())
            ))
            conn.commit()

        # Update cache
        with cache_lock:
            cache['latest_signals'] = signal

        return jsonify({'status': 'success'})

    except Exception as e:
        logger.error(f"Error storing signal: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades', methods=['POST'])
def log_trade():
    """Log executed trades."""
    try:
        trade = request.get_json()

        if not trade:
            return jsonify({'error': 'Invalid trade data'}), 400

        logger.info(f"Logging trade: {trade}")

        # Store trade in database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades (
                    ticket, symbol, type, lots, open_price, close_price,
                    profit, swap, commission, open_time, close_time, sl, tp, comment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade.get('ticket'),
                trade.get('symbol'),
                trade.get('type'),
                trade.get('lots', 0),
                trade.get('open_price', 0),
                trade.get('close_price'),
                trade.get('profit', 0),
                trade.get('swap', 0),
                trade.get('commission', 0),
                trade.get('open_time'),
                trade.get('close_time'),
                trade.get('sl'),
                trade.get('tp'),
                trade.get('comment', '')
            ))
            conn.commit()

        return jsonify({'status': 'success'})

    except Exception as e:
        logger.error(f"Error logging trade: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/stream')
def dashboard_stream():
    """Server-Sent Events stream for real-time dashboard updates."""
    def generate():
        while True:
            try:
                # Update metrics
                metrics = calculate_metrics()
                positions = get_live_positions()
                trades = get_recent_trades()

                with cache_lock:
                    cache['metrics'] = metrics
                    cache['live_positions'] = positions
                    cache['recent_trades'] = trades

                data = {
                    'metrics': metrics,
                    'positions': positions,
                    'trades': trades,
                    'timestamp': time.time()
                }

                yield f"data: {json.dumps(data)}\n\n"

            except Exception as e:
                logger.error(f"Error in dashboard stream: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

            time.sleep(1)  # Update every second

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/dashboard/data', methods=['GET'])
def get_dashboard_data():
    """Get current dashboard data (non-streaming endpoint)."""
    try:
        metrics = calculate_metrics()
        positions = get_live_positions()
        trades = get_recent_trades()

        return jsonify({
            'metrics': metrics,
            'live_positions': positions,
            'recent_trades': trades,
            'system_status': cache['system_status'],
            'timestamp': time.time()
        })

    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create logs directory
    os.makedirs('logs', exist_ok=True)

    # Initialize database
    init_database()

    # Update system status
    cache['system_status'] = 'RUNNING'

    logger.info("Starting Flask API server...")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)