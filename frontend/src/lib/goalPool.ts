import { api } from "../api";

export type GoalPoolTotals = {
  poolTotal: number;
  depositedTotal: number;
  available: number;
};

function parseDecimal(value: string): number {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

/** Totais do pool de metas na competência informada. Cada mês é fechado em si mesmo. */
export async function fetchGoalPoolTotals(periodId: string): Promise<GoalPoolTotals> {
  const summary = await api.goalPoolSummary(periodId);
  return {
    poolTotal: parseDecimal(summary.pool_total),
    depositedTotal: parseDecimal(summary.deposited_total),
    available: parseDecimal(summary.available),
  };
}
