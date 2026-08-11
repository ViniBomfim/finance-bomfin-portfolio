import type { CardRow } from "../types";

export type CardRiskLevel = "normal" | "warning" | "high";
export type UsageTier = "low" | "mid" | "high";

export type InvoiceClosingPhase = "before" | "today" | "after";

export type InvoiceClosingInfo = {
  phase: InvoiceClosingPhase;
  daysUntilClose: number;
  closingDay: number;
};

export type CardComputed = {
  card: CardRow;
  monthUsed: number;
  spentTotal: number;
  limit: number;
  available: number;
  utilization: number;
  hasActivity: boolean;
  unpaidTotal: number;
  unpaidCount: number;
  paidAt: string | null;
  /** Período com lançamentos e nada pendente. */
  isPaid: boolean;
  risk: CardRiskLevel;
  daysUntilDue: number;
  closingInfo: InvoiceClosingInfo;
};

export function effectiveDayInMonth(day: number, year: number, month: number): number {
  const safeDay = Math.min(Math.max(day, 1), 31);
  const lastDay = new Date(year, month + 1, 0).getDate();
  return Math.min(safeDay, lastDay);
}

export function invoiceClosingInfo(closingDay: number, now = new Date()): InvoiceClosingInfo {
  const safeDay = Math.min(Math.max(closingDay, 1), 31);
  const today = now.getDate();
  const effectiveDay = effectiveDayInMonth(safeDay, now.getFullYear(), now.getMonth());

  if (today < effectiveDay) {
    return { phase: "before", daysUntilClose: effectiveDay - today, closingDay: safeDay };
  }
  if (today === effectiveDay) {
    return { phase: "today", daysUntilClose: 0, closingDay: safeDay };
  }
  return { phase: "after", daysUntilClose: 0, closingDay: safeDay };
}

export function closingChipParts(info: InvoiceClosingInfo) {
  const day = `dia ${info.closingDay}`;
  if (info.phase === "today") {
    return { lead: "", highlight: "Fechado", day };
  }
  if (info.phase === "after") {
    return { lead: "", highlight: "Aberto", day };
  }
  return { lead: "Fecha em", highlight: `${info.daysUntilClose}d`, day };
}

export function closingDashboardLabel(info: InvoiceClosingInfo): string {
  if (info.phase === "today") return "Fechado";
  if (info.phase === "after") return `Aberto · d${info.closingDay}`;
  return `${info.daysUntilClose}d`;
}

export function daysUntilNextDay(day: number, now = new Date()): number {
  const safeDay = Math.min(Math.max(day, 1), 31);
  const today = now.getDate();
  const year = now.getFullYear();
  const month = now.getMonth();
  const effectiveDay = effectiveDayInMonth(safeDay, year, month);

  if (today < effectiveDay) {
    return effectiveDay - today;
  }
  if (today === effectiveDay) {
    return 0;
  }
  const daysLeftThisMonth = new Date(year, month + 1, 0).getDate() - today;
  const nextMonth = month === 11 ? 0 : month + 1;
  const nextYear = month === 11 ? year + 1 : year;
  const nextEffectiveDay = effectiveDayInMonth(safeDay, nextYear, nextMonth);
  return daysLeftThisMonth + nextEffectiveDay;
}

export function dueChipParts(daysUntilDue: number) {
  if (daysUntilDue === 0) return { lead: "", highlight: "Vence hoje" };
  return { lead: "Vence em", highlight: `${daysUntilDue}d` };
}

export function dueDashboardLabel(daysUntilDue: number): string {
  if (daysUntilDue === 0) return "Vence hoje";
  return `${daysUntilDue}d`;
}

export function cardRiskLevel(utilization: number): CardRiskLevel {
  if (utilization >= 90) return "high";
  if (utilization >= 70) return "warning";
  return "normal";
}

export function usageTier(utilization: number): UsageTier {
  if (utilization >= 70) return "high";
  if (utilization >= 35) return "mid";
  return "low";
}

export function cardRiskLabel(risk: CardRiskLevel): string {
  if (risk === "high") return "CRÍTICO";
  if (risk === "warning") return "ALERTA";
  return "NORMAL";
}

function normalizeBankKey(banco: string): string {
  return banco
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "");
}

export function buildStripeByCardId(metrics: CardComputed[]): Map<string, string> {
  let itauIdx = 0;
  const result = new Map<string, string>();
  for (const item of metrics) {
    const key = normalizeBankKey(item.card.banco);
    let stripe = "default";
    if (key.includes("nubank")) stripe = "nubank";
    else if (key.includes("santander")) stripe = "santander";
    else if (key.includes("itau")) {
      stripe = itauIdx === 0 ? "itau" : "itau2";
      itauIdx += 1;
    }
    result.set(item.card.id, stripe);
  }
  return result;
}

export function cardCountLabel(count: number): string {
  return count === 1 ? `${count} cartão` : `${count} cartões`;
}
