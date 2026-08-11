export function formatBRL(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(n);
}

/** Compact BRL for tight UI (no narrow space; drop trailing ",00"). */
export function formatCompactBRL(value: string | number): string {
  return formatBRL(value).replace(/\s/g, "").replace(",00", "");
}

/** Limite do cartão menos soma de todos os lançamentos (à vista e parcelados). */
export function availableCardLimit(limiteStr: string, spentTotalStr: string): number {
  const lim = parseFloat(limiteStr) || 0;
  const sp = parseFloat(spentTotalStr) || 0;
  return Math.max(0, lim - sp);
}
