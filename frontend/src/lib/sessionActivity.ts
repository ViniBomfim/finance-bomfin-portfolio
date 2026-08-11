const LAST_ACTIVITY_KEY = "fm_last_activity_at";

export function touchSessionActivity(): void {
  localStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()));
}

export function clearSessionActivity(): void {
  localStorage.removeItem(LAST_ACTIVITY_KEY);
}

export function getLastSessionActivityAt(): number | null {
  const raw = localStorage.getItem(LAST_ACTIVITY_KEY);
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function msSinceLastActivity(): number | null {
  const last = getLastSessionActivityAt();
  if (last === null) return null;
  return Date.now() - last;
}
