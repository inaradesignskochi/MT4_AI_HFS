
import { useState, useEffect } from 'react';
import { Metrics, LivePosition, RecentTrade, AiSignal, SystemStatus } from '../types.ts';
import { useSettings } from './useSettings.ts';

export const useTradingData = () => {
    const [metrics, setMetrics] = useState<Metrics>({ todayPnl: 0, winRate: 0, wins: 0, totalTrades: 0, signalsToday: 0 });
    const [livePositions, setLivePositions] = useState<LivePosition[]>([]);
    const [recentTrades, setRecentTrades] = useState<RecentTrade[]>([]);
    const [aiSignals, setAiSignals] = useState<AiSignal[]>([]);
    const [systemStatus, setSystemStatus] = useState<SystemStatus>('OFFLINE');
    const [settings] = useSettings();

    useEffect(() => {
        // Only connect if backend URL is configured
        if (!settings.gcpVmIp || settings.gcpVmIp.trim() === '') {
            setSystemStatus('OFFLINE');
            return;
        }

        const eventSource = new EventSource(`${settings.gcpVmIp}/api/dashboard/stream`);

        eventSource.onopen = () => {
            setSystemStatus('OPERATIONAL');
        };

        eventSource.onerror = (error) => {
            console.error('EventSource error:', error);
            setSystemStatus('DEGRADED');
        };

        eventSource.addEventListener('metrics', (event) => {
            const newMetrics = JSON.parse(event.data);
            setMetrics(newMetrics);
        });

        eventSource.addEventListener('positions', (event) => {
            const newPositions = JSON.parse(event.data);
            setLivePositions(newPositions);
        });

        eventSource.addEventListener('trades', (event) => {
            const newTrades = JSON.parse(event.data);
            setRecentTrades(newTrades);
        });

        eventSource.addEventListener('signals', (event) => {
            const newSignals = JSON.parse(event.data);
            setAiSignals(newSignals);
        });

        return () => {
            eventSource.close();
        };
    }, [settings.gcpVmIp]);

    return { metrics, livePositions, recentTrades, aiSignals, systemStatus };
};
