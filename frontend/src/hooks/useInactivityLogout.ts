import { useCallback, useEffect, useRef, useState } from "react";
import { getToken, setToken } from "../api";
import {
  clearSessionActivity,
  getLastSessionActivityAt,
  touchSessionActivity,
} from "../lib/sessionActivity";

const ACTIVITY_THROTTLE_MS = 15_000;
const SETTINGS_REFRESH_MS = 5 * 60_000;
const WARN_BEFORE_MS = 60_000;
const SHORT_TIMEOUT_WARN_MS = 30_000;

const ACTIVITY_EVENTS: (keyof WindowEventMap)[] = [
  "mousedown",
  "keydown",
  "touchstart",
  "scroll",
  "click",
];

export type InactivityLogoutState = {
  warningVisible: boolean;
  secondsRemaining: number;
  continueSession: () => void;
};

function performInactivityLogout(): void {
  setToken(null);
  clearSessionActivity();
  window.location.href = "/login?inativo=1";
}

function getWarnBeforeMs(timeoutMs: number): number {
  if (timeoutMs <= WARN_BEFORE_MS) {
    return Math.min(SHORT_TIMEOUT_WARN_MS, Math.max(timeoutMs / 2, 1_000));
  }
  return WARN_BEFORE_MS;
}

export function useInactivityLogout(
  enabled: boolean,
  timeoutMinutes: number | null,
  onRefreshSettings?: () => void,
): InactivityLogoutState {
  const [warningVisible, setWarningVisible] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(0);

  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;
  const timeoutRef = useRef(timeoutMinutes);
  timeoutRef.current = timeoutMinutes;
  const warningVisibleRef = useRef(false);
  warningVisibleRef.current = warningVisible;

  const warnTimeoutRef = useRef<number | undefined>(undefined);
  const countdownIntervalRef = useRef<number | undefined>(undefined);
  const logoutAtRef = useRef<number | null>(null);
  const scheduleTimersRef = useRef<() => void>(() => {});

  const clearTimers = useCallback(() => {
    if (warnTimeoutRef.current !== undefined) {
      window.clearTimeout(warnTimeoutRef.current);
      warnTimeoutRef.current = undefined;
    }
    if (countdownIntervalRef.current !== undefined) {
      window.clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = undefined;
    }
  }, []);

  const hideWarning = useCallback(() => {
    warningVisibleRef.current = false;
    setWarningVisible(false);
    setSecondsRemaining(0);
    logoutAtRef.current = null;
    if (countdownIntervalRef.current !== undefined) {
      window.clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = undefined;
    }
  }, []);

  const startCountdown = useCallback((logoutAt: number) => {
    logoutAtRef.current = logoutAt;
    warningVisibleRef.current = true;
    setWarningVisible(true);

    const tick = () => {
      const remainingMs = Math.max(0, (logoutAtRef.current ?? 0) - Date.now());
      const secs = Math.ceil(remainingMs / 1000);
      setSecondsRemaining(secs);
      if (secs <= 0) {
        performInactivityLogout();
      }
    };

    tick();
    if (countdownIntervalRef.current !== undefined) {
      window.clearInterval(countdownIntervalRef.current);
    }
    countdownIntervalRef.current = window.setInterval(tick, 1_000);
  }, []);

  const scheduleTimers = useCallback(() => {
    clearTimers();
    hideWarning();

    if (!enabledRef.current || !getToken()) return;

    const minutes = timeoutRef.current;
    if (!minutes || minutes <= 0) return;

    const timeoutMs = minutes * 60_000;
    const warnBeforeMs = getWarnBeforeMs(timeoutMs);
    const warnAfterMs = timeoutMs - warnBeforeMs;

    let last = getLastSessionActivityAt();
    if (last === null) {
      touchSessionActivity();
      last = getLastSessionActivityAt() ?? Date.now();
    }

    const now = Date.now();
    const idleMs = now - last;

    if (idleMs >= timeoutMs) {
      performInactivityLogout();
      return;
    }

    const logoutAt = last + timeoutMs;
    const warnAt = last + warnAfterMs;

    if (idleMs >= warnAfterMs) {
      startCountdown(logoutAt);
      return;
    }

    warnTimeoutRef.current = window.setTimeout(() => {
      startCountdown(logoutAt);
    }, warnAt - now);
  }, [clearTimers, hideWarning, startCountdown]);

  scheduleTimersRef.current = scheduleTimers;

  const continueSession = useCallback(() => {
    touchSessionActivity();
    scheduleTimersRef.current();
  }, []);

  useEffect(() => {
    if (!getToken()) {
      hideWarning();
      return;
    }

    if (!enabled) {
      clearSessionActivity();
      clearTimers();
      hideWarning();
      return;
    }

    const minutes = timeoutMinutes;
    if (minutes && minutes > 0) {
      const last = getLastSessionActivityAt();
      if (last !== null && Date.now() - last >= minutes * 60_000) {
        performInactivityLogout();
        return;
      }
      if (last === null) {
        touchSessionActivity();
      }
    }

    let throttleUntil = 0;
    const onActivity = () => {
      if (warningVisibleRef.current) return;
      const now = Date.now();
      if (now < throttleUntil) return;
      throttleUntil = now + ACTIVITY_THROTTLE_MS;
      touchSessionActivity();
      scheduleTimersRef.current();
    };

    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, onActivity, { passive: true });
    }

    scheduleTimers();

    let settingsIntervalId: number | undefined;
    if (onRefreshSettings) {
      settingsIntervalId = window.setInterval(onRefreshSettings, SETTINGS_REFRESH_MS);
    }

    return () => {
      for (const event of ACTIVITY_EVENTS) {
        window.removeEventListener(event, onActivity);
      }
      clearTimers();
      if (settingsIntervalId !== undefined) {
        window.clearInterval(settingsIntervalId);
      }
    };
  }, [onRefreshSettings, enabled, timeoutMinutes, scheduleTimers, clearTimers, hideWarning]);

  return { warningVisible, secondsRemaining, continueSession };
}
