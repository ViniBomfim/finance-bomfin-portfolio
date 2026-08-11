import type { Category, DashboardSummary } from "./types";

export type ExpenseCategoryRow = {
  categoria_id: string;
  categoria_nome: string;
  gastos: number;
};

/** Lista todas as categorias de despesa com totais do resumo (despesas + cartão no período). */
export function mergeExpenseCategoryRows(
  expenseCategories: Pick<Category, "id" | "nome">[],
  expenses: DashboardSummary["expenses_by_category"],
): ExpenseCategoryRow[] {
  const gastosByCat = new Map(expenses.map((e) => [e.categoria_id, parseFloat(e.total)]));

  return expenseCategories
    .map((cat) => ({
      categoria_id: cat.id,
      categoria_nome: cat.nome,
      gastos: gastosByCat.get(cat.id) ?? 0,
    }))
    .sort((a, b) => a.categoria_nome.localeCompare(b.categoria_nome, "pt-BR"));
}
