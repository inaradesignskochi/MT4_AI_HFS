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

# Database configuration - use PostgreSQL for Render
import os
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///trading_system.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Use SQLAlchemy for database abstraction
from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Legacy SQLite path for backward compatibility
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

# SQLAlchemy Models
class Tick(Base):
    __tablename__ = "ticks_raw"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(Float)
    symbol = Column(String)
    bid = Column(Float)
    ask = Column(Float)
    spread = Column(Float)
    volume = Column(Integer)
    created_at = Column(Float, default=time.time)

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, index=True)
    ticket = Column(Integer)
    symbol = Column(String)
    type = Column(String)
    lots = Column(Float)
    open_price = Column(Float)
    close_price = Column(Float, nullable=True)
    profit = Column(Float, default=0)
    swap = Column(Float, default=0)
    commission = Column(Float, default=0)
    open_time = Column(Float)
    close_time = Column(Float, nullable=True)
    sl = Column(Float, nullable=True)
    tp = Column(Float, nullable=True)
    comment = Column(Text, default="")
    created_at = Column(Float, default=time.time)

class Signal(Base):
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String)
    direction = Column(String)
    confidence = Column(Float)
    entry_price = Column(Float)
    sl = Column(Float)
    tp = Column(Float)
    timestamp = Column(Float)
    executed = Column(Integer, default=0)
    created_at = Column(Float, default=time.time)

def init_database():
    """Initialize database with required tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

def get_db_session():
    """Get database session."""
    return SessionLocal()

def calculate_metrics():
    """Calculate trading performance metrics."""
    try:
        session = get_db_session()

        # Get today's trades
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_timestamp = today_start.timestamp()

        trades = session.query(Trade).filter(
            Trade.close_time >= today_timestamp,
            Trade.close_time.isnot(None)
        ).all()

        if not trades:
            session.close()
            return {
                'today_pnl': 0.0,
                'win_rate': 0.0,
                'wins': 0,
                'total_trades': 0,
                'signals_today': 0
            }

        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.profit > 0])
        today_pnl = sum(t.profit for t in trades)

        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0

        # Get signals count for today
        signals_today = session.query(Signal).filter(
            Signal.timestamp >= today_timestamp
        ).count()

        session.close()

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
        session = get_db_session()

        positions = session.query(Trade).filter(
            Trade.close_time.is_(None)
        ).order_by(Trade.open_time.desc()).limit(10).all()

        result = [{
            'ticket': p.ticket,
            'symbol': p.symbol,
            'type': p.type,
            'lots': p.lots,
            'open_price': p.open_price,
            'open_time': p.open_time,
            'sl': p.sl,
            'tp': p.tp
        } for p in positions]

        session.close()
        return result

    except Exception as e:
        logger.error(f"Error getting live positions: {e}")
        return []

def get_recent_trades(limit: int = 10):
    """Get recent closed trades."""
    try:
        session = get_db_session()

        trades = session.query(Trade).filter(
            Trade.close_time.isnot(None)
        ).order_by(Trade.close_time.desc()).limit(limit).all()

        result = [{
            'ticket': t.ticket,
            'symbol': t.symbol,
            'type': t.type,
            'lots': t.lots,
            'open_price': t.open_price,
            'close_price': t.close_price,
            'profit': t.profit,
            'open_time': t.open_time,
            'close_time': t.close_time,
            'sl': t.sl,
            'tp': t.tp
        } for t in trades]

        session.close()
        return result

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
        session = get_db_session()

        for tick in ticks:
            new_tick = Tick(
                timestamp=tick.get('timestamp', time.time()),
                symbol=symbol,
                bid=tick.get('bid', 0),
                ask=tick.get('ask', 0),
                spread=tick.get('spread', 0),
                volume=tick.get('volume', 0)
            )
            session.add(new_tick)

        session.commit()
        session.close()

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
        session = get_db_session()
        new_signal = Signal(
            symbol=signal.get('symbol', 'EURUSD'),
            direction=signal.get('direction'),
            confidence=signal.get('confidence', 0),
            entry_price=signal.get('entry_price', 0),
            sl=signal.get('sl', 0),
            tp=signal.get('tp', 0),
            timestamp=signal.get('timestamp', time.time())
        )
        session.add(new_signal)
        session.commit()
        session.close()

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
        session = get_db_session()
        new_trade = Trade(
            ticket=trade.get('ticket'),
            symbol=trade.get('symbol'),
            type=trade.get('type'),
            lots=trade.get('lots', 0),
            open_price=trade.get('open_price', 0),
            close_price=trade.get('close_price'),
            profit=trade.get('profit', 0),
            swap=trade.get('swap', 0),
            commission=trade.get('commission', 0),
            open_time=trade.get('open_time'),
            close_time=trade.get('close_time'),
            sl=trade.get('sl'),
            tp=trade.get('tp'),
            comment=trade.get('comment', '')
        )
        session.add(new_trade)
        session.commit()
        session.close()

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