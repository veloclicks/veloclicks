'use client';

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useAuth } from './AuthContext';
import { isProgressiveActivityEnabled } from '../utils/activityRollout.mjs';

const ActivitySyncContext = createContext(null);

export function useActivitySync() {
  return useContext(ActivitySyncContext);
}

export function ActivitySyncProvider({ children }) {
  const { authToken, loginSerial, isDemoMode } = useAuth();
  const [state, setState] = useState(null);
  const [starting, setStarting] = useState(false);
  const lastAutoLogin = useRef(0);
  const generation = useRef(0);
  const pending = useRef(null);
  const channel = useRef(null);
  const enabled = Boolean(authToken) && !isDemoMode && typeof window !== 'undefined' &&
    isProgressiveActivityEnabled(window.location.hostname, process.env.NEXT_PUBLIC_PROGRESSIVE_ACTIVITY_SYNC);

  const request = useCallback(async (path, options = {}) => {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/strava/sync${path}`, {
      ...options,
      headers: { Authorization: `Bearer ${authToken}`, ...options.headers },
    });
    if (!response.ok) throw new Error('Unable to reach activity synchronisation.');
    return response.json();
  }, [authToken]);

  const startSync = useCallback(async (kind = 'manual') => {
    if (!enabled || pending.current) return;
    const operation = {};
    pending.current = operation;
    generation.current++;
    const isCurrent = () => pending.current === operation &&
      localStorage.getItem('authToken') === authToken;
    setStarting(true);
    try {
      const result = await request('', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind }),
      });
      if (isCurrent()) {
        setState({ token: authToken, result });
        channel.current?.postMessage(result);
      }
      return result;
    } catch {
      if (isCurrent()) {
        setState(previous => ({ token: authToken,
          result: { ...(previous?.token === authToken ? previous.result : {}), error: 'request_failed' } }));
      }
    } finally {
      if (isCurrent()) setStarting(false);
      if (pending.current === operation) pending.current = null;
    }
  }, [authToken, enabled, request]);

  useEffect(() => {
    setStarting(false);
    pending.current = null;
    if (!enabled) return;
    const controller = new AbortController();
    let timer;
    if (typeof BroadcastChannel === 'function') {
      channel.current = new BroadcastChannel('veloclicks-activity-sync');
      channel.current.onmessage = ({ data }) => {
        if (localStorage.getItem('authToken') !== authToken) return;
        generation.current++;
        setState({ token: authToken, result: data });
      };
    }
    async function poll() {
      const version = generation.current;
      let result;
      if (!pending.current) {
        try {
          result = await request('/status', { signal: controller.signal });
          if (!controller.signal.aborted && version === generation.current &&
              localStorage.getItem('authToken') === authToken) {
            setState({ token: authToken, result });
          }
        } catch {
          // Keep the last confirmed state until a later poll succeeds.
        }
      }
      if (!controller.signal.aborted) timer = setTimeout(poll, result?.syncing ? 2000 : 5000);
    }
    poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
      channel.current?.close();
      channel.current = null;
      pending.current = null;
    };
  }, [authToken, enabled, request]);

  useEffect(() => {
    if (enabled && loginSerial > lastAutoLogin.current) {
      lastAutoLogin.current = loginSerial;
      startSync('automatic');
    }
  }, [enabled, loginSerial, startSync]);

  const status = enabled && state?.token === authToken ? state.result : null;
  return (
    <ActivitySyncContext.Provider value={{
      enabled, status, starting: enabled && starting, startSync,
    }}>
      {children}
    </ActivitySyncContext.Provider>
  );
}
