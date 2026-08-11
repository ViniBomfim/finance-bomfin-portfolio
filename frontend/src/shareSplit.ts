import { parseBrazilianMoney } from "./parseCardCsv";

export type ShareRow = { spenderId: string; valor: string };

export function decimalPointToComma(v: string): string {
  const t = v.trim();
  return /^-?\d+(?:\.\d+)?$/.test(t) ? t.replace(".", ",") : v;
}

function parseTotalToCents(totalStr: string): number {
  const total = parseBrazilianMoney(totalStr);
  if (total === null) return 0;
  return Math.round(total * 100);
}

function formatCentsToComma(cents: number): string {
  return (cents / 100).toFixed(2).replace(".", ",");
}

function splitCentsEqually(totalCents: number, parts: number): number[] {
  if (parts <= 0) return [];
  if (totalCents === 0) return Array.from({ length: parts }, () => 0);
  const sign = totalCents < 0 ? -1 : 1;
  const absTotal = Math.abs(totalCents);
  const base = Math.floor(absTotal / parts);
  let remainder = absTotal - base * parts;
  return Array.from({ length: parts }, () => {
    const extra = remainder > 0 ? 1 : 0;
    if (remainder > 0) remainder -= 1;
    return (base + extra) * sign;
  });
}

/** Ao escolher pessoa: 1 pessoa recebe o total; 2+ dividem em partes iguais (centavos). */
export function autoSplitRowsOnPersonSelect(
  rows: ShareRow[],
  rowIndex: number,
  spenderId: string,
  totalStr: string,
): ShareRow[] {
  const nextRows = rows.map((row, i) => {
    if (i !== rowIndex) return row;
    return { ...row, spenderId, valor: spenderId.trim() ? row.valor : "" };
  });
  return rebalanceShareRows(nextRows, totalStr);
}

export function rebalanceShareRows(rows: ShareRow[], totalStr: string): ShareRow[] {
  const selectedIndices = rows
    .map((row, i) => (row.spenderId.trim() ? i : -1))
    .filter((i) => i >= 0);
  if (selectedIndices.length === 0) return rows;
  const totalCents = parseTotalToCents(totalStr);
  if (totalCents === 0) return rows;
  const splits = splitCentsEqually(totalCents, selectedIndices.length);
  const splitByIndex = new Map<number, string>();
  selectedIndices.forEach((idx, i) => {
    splitByIndex.set(idx, formatCentsToComma(splits[i] ?? 0));
  });
  return rows.map((row, i) =>
    splitByIndex.has(i) ? { ...row, valor: splitByIndex.get(i)! } : row,
  );
}

export function sumShareRows(rows: ShareRow[]): number {
  return rows.reduce((acc, row) => {
    if (!row.spenderId.trim()) return acc;
    const v = parseBrazilianMoney(row.valor);
    return acc + (v ?? 0);
  }, 0);
}

const SHARE_BALANCE_TOLERANCE = 0.021;

export type ShareBalanceStatus = "closed" | "short" | "over";

/** Saldo da divisão: funciona para total positivo (despesa) ou negativo (crédito/estorno). */
export function shareBalanceStatus(target: number, allocated: number): ShareBalanceStatus {
  if (Math.abs(target - allocated) <= SHARE_BALANCE_TOLERANCE) return "closed";
  if (target >= 0) {
    if (allocated < target - SHARE_BALANCE_TOLERANCE) return "short";
    return "over";
  }
  // Crédito/estorno: falta quando a soma ainda não atingiu o total negativo.
  if (allocated > target + SHARE_BALANCE_TOLERANCE) return "short";
  return "over";
}

export function shareBalanceGap(target: number, allocated: number): number {
  return Math.abs(target - allocated);
}

function shouldAutoFillOnSubmit(rows: ShareRow[]): boolean {
  const selected = rows.filter((r) => r.spenderId.trim());
  if (selected.length === 0) return false;
  return selected.every((r) => {
    const n = parseBrazilianMoney(r.valor);
    return n === null || Math.abs(n) < 1e-9;
  });
}

export function prepareShareRowsForSubmit(rows: ShareRow[], totalStr: string): ShareRow[] {
  if (!shouldAutoFillOnSubmit(rows)) return rows;
  return rebalanceShareRows(rows, totalStr);
}

/** Edição: [] limpa divisão. Criação: undefined omite (sem divisão). */
export function resolveSharesPayload(
  isEdit: boolean,
  valorStr: string,
  rows: ShareRow[],
): { spender_id: string; valor: string }[] | undefined {
  const filled = rows.filter((r) => r.spenderId.trim() && r.valor.trim());
  if (filled.length === 0) {
    return isEdit ? [] : undefined;
  }
  const total = parseFloat(valorStr.replace(/\./g, "").replace(",", ".")) || 0;
  const out: { spender_id: string; valor: string }[] = [];
  let sum = 0;
  for (const r of filled) {
    const v = parseBrazilianMoney(r.valor);
    if (v === null || Math.abs(v) < 1e-9) {
      throw new Error("Cada parte precisa de valor diferente de zero.");
    }
    sum += v;
    out.push({ spender_id: r.spenderId, valor: v.toFixed(2) });
  }
  if (Math.abs(sum - total) > 0.021) {
    throw new Error(
      `Soma das partes (R$ ${sum.toFixed(2)}) deve igualar o valor (R$ ${total.toFixed(2)}).`,
    );
  }
  return out;
}
