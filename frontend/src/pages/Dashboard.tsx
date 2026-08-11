import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CategoryExpensesChart, CATEGORY_CHART_COLORS } from "../components/CategoryExpensesChart";
import { GoalJarSvg } from "../components/GoalJarSvg";
import { api } from "../api";
import { useAppDialog } from "../context/DialogContext";
import { usePeriod } from "../context/PeriodContext";
import {
  buildStripeByCardId,
  cardCountLabel,
  cardRiskLabel,
  cardRiskLevel,
  daysUntilNextDay,
  invoiceClosingInfo,
  usageTier,
  type CardComputed,
} from "../lib/cardMetrics";
import { formatBRL, formatCompactBRL } from "../money";
import type { CardRow, DashboardSummary, InvestmentRow, TripRow } from "../types";

type IncomeRow = {
  id: string;
  descricao: string;
  valor: string;
  data: string;
  recorrente: boolean;
  categoria_id: string;
};

const PERSON_GRADIENTS = [
  "linear-gradient(135deg,#f43f5e,#a855f7)",
  "linear-gradient(135deg,#3b82f6,#22d3ee)",
  "linear-gradient(135deg,#22c55e,#16a34a)",
  "linear-gradient(135deg,#f59e0b,#ef4444)",
  "linear-gradient(135deg,#a78bfa,#6366f1)",
  "linear-gradient(135deg,#14b8a6,#0ea5e9)",
];
const DASHBOARD_GOAL_DETAILS_HIDDEN_KEY = "fm_dashboard_goal_details_hidden";

const QUICK_LINKS = [
  { to: "/cartoes", label: "Cartões", icon: "💳" },
  { to: "/gastos-fixos", label: "Gastos fixos", icon: "📌" },
  { to: "/metas", label: "Metas", icon: "🎯" },
  { to: "/devedores", label: "Devedores", icon: "💸" },
  { to: "/viagens", label: "Viagens", icon: "✈️" },
  { to: "/investimentos", label: "Investimentos", icon: "📈" },
] as const;

function formatDateBR(value: string): string {
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("pt-BR");
}

function incomeCategoryEmoji(nome: string): string {
  const n = nome.toLowerCase();
  if (n.includes("salár") || n.includes("salario")) return "💼 ";
  if (n.includes("freelance")) return "💻 ";
  if (n.includes("invest")) return "📈 ";
  if (n.includes("aluguel")) return "🏠 ";
  return "💰 ";
}

function formatShortDateBR(value: string): string {
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function normalizePersonName(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function isUnassignedPerson(value?: string | null) {
  if (!value) return true;
  const normalized = normalizePersonName(value);
  return normalized.length === 0 || normalized.includes("sem pessoa") || normalized.includes("nao informado");
}

function isMePerson(value: string) {
  const normalized = normalizePersonName(value);
  return normalized === "eu" || normalized.startsWith("eu ") || normalized.includes("(eu)");
}

function getGoalTypeLabel(goalType: string) {
  if (goalType === "short") return "Curto prazo";
  if (goalType === "medium") return "Médio prazo";
  if (goalType === "long") return "Longo prazo";
  return "Meta";
}

function getInvestmentTypeLabel(tipo: string) {
  if (tipo === "renda_fixa") return "Renda fixa";
  if (tipo === "stock") return "Ações";
  if (tipo === "fii") return "FII";
  if (tipo === "crypto") return "Cripto";
  return tipo;
}

function maskGoalTitle(nome: string): string {
  const len = nome.trim().length;
  const dots = Math.min(14, Math.max(6, len || 6));
  return "•".repeat(dots);
}

function loadGoalDetailsHiddenFromStorage(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(DASHBOARD_GOAL_DETAILS_HIDDEN_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const out: Record<string, boolean> = {};
    for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
      if (v === true) out[k] = true;
    }
    return out;
  } catch {
    return {};
  }
}

function personInitial(name: string): string {
  const trimmed = name.trim();
  return trimmed ? trimmed.charAt(0).toUpperCase() : "?";
}

function personGradient(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash + name.charCodeAt(i) * (i + 1)) % PERSON_GRADIENTS.length;
  }
  return PERSON_GRADIENTS[hash] ?? PERSON_GRADIENTS[0];
}

export function Dashboard() {
  const navigate = useNavigate();
  const { periodId, ready } = usePeriod();
  const { confirm } = useAppDialog();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [cards, setCards] = useState<CardRow[]>([]);
  const [meSpenderId, setMeSpenderId] = useState<string | null>(null);
  const [incomeCategories, setIncomeCategories] = useState<Array<{ id: string; nome: string }>>([]);
  const [error, setError] = useState("");
  const [showIncomeForm, setShowIncomeForm] = useState(false);
  const [incomeCategoryId, setIncomeCategoryId] = useState("");
  const [incomeDescription, setIncomeDescription] = useState("");
  const [incomeValue, setIncomeValue] = useState("");
  const [incomeDate, setIncomeDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [incomeRecurring, setIncomeRecurring] = useState(false);
  const [incomeSaving, setIncomeSaving] = useState(false);
  const [incomeFormError, setIncomeFormError] = useState("");
  const [incomeRows, setIncomeRows] = useState<IncomeRow[]>([]);
  const [incomeLoading, setIncomeLoading] = useState(false);
  const [editingIncomeId, setEditingIncomeId] = useState<string | null>(null);
  const [showHeavySections, setShowHeavySections] = useState(false);
  const [goalDetailsHiddenById] = useState<Record<string, boolean>>(loadGoalDetailsHiddenFromStorage);
  const [investmentPatrimonio, setInvestmentPatrimonio] = useState<number | null>(null);
  const [trips, setTrips] = useState<TripRow[]>([]);
  const [investments, setInvestments] = useState<InvestmentRow[]>([]);
  const [summaryLoading, setSummaryLoading] = useState(true);

  useEffect(() => {
    if (!periodId) return;
    let cancelled = false;
    setShowHeavySections(false);
    setSummaryLoading(true);
    (async () => {
      try {
        if (!cancelled) setError("");
        const [s, cardsList, incomeCats, invTotal, me, tripsList, invList] = await Promise.all([
          api.dashboardSummary(periodId),
          api.listCards(),
          api.categories("income"),
          api.investmentsTotal(),
          api.getMe(),
          api.listTrips().catch(() => [] as TripRow[]),
          api.listInvestments().catch(() => [] as InvestmentRow[]),
        ]);
        if (!cancelled) {
          setSummary(s);
          setCards(cardsList);
          setMeSpenderId(me.me_spender_id ?? null);
          setIncomeCategories(incomeCats.map((c) => ({ id: c.id, nome: c.nome })));
          setIncomeCategoryId((prev) => prev || incomeCats[0]?.id || "");
          setInvestmentPatrimonio(invTotal.total_valor_atual);
          setTrips(tripsList);
          setInvestments(invList);
          window.setTimeout(() => {
            if (!cancelled) setShowHeavySections(true);
          }, 0);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Erro no dashboard");
      } finally {
        if (!cancelled) setSummaryLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [periodId]);

  const cardSlides = useMemo(() => {
    if (!summary || cards.length === 0) return [];
    const usedMap = new Map(summary.card_totals.map((row) => [row.card_id, parseFloat(row.total) || 0]));
    const metrics: CardComputed[] = cards
      .map((card) => {
        const limit = parseFloat(card.limite) || 0;
        const usado = usedMap.get(card.id) ?? 0;
        const disponivel = limit - usado;
        const utilization = limit > 0 ? (usado / limit) * 100 : 0;
        return {
          card,
          monthUsed: usado,
          spentTotal: 0,
          limit,
          available: disponivel,
          utilization,
          hasActivity: usado > 0,
          unpaidTotal: 0,
          unpaidCount: 0,
          paidAt: null,
          isPaid: false,
          risk: cardRiskLevel(utilization),
          daysUntilDue: daysUntilNextDay(card.vencimento),
          closingInfo: invoiceClosingInfo(card.fechamento),
        };
      })
      .sort((a, b) => b.monthUsed - a.monthUsed);
    const stripes = buildStripeByCardId(metrics);
    return metrics.map((item) => ({
      ...item,
      stripe: stripes.get(item.card.id) ?? "default",
      pctUsado: item.limit > 0 ? Math.min(100, Math.round(item.utilization)) : 0,
      tier: usageTier(item.utilization),
    }));
  }, [cards, summary]);

  const sortedGoalProgress = useMemo(
    () => (summary ? [...summary.goal_progress].sort((a, b) => b.progress_percent - a.progress_percent) : []),
    [summary],
  );

  const sortedUsageByPerson = useMemo(
    () =>
      summary
        ? [...summary.usage_by_person_cards]
            .filter((row) => row.pessoa_id && !isUnassignedPerson(row.pessoa_nome))
            .sort((a, b) => {
              const aIsMe = isMePerson(a.pessoa_nome);
              const bIsMe = isMePerson(b.pessoa_nome);
              if (aIsMe && !bIsMe) return -1;
              if (!aIsMe && bIsMe) return 1;
              return parseFloat(b.total_geral) - parseFloat(a.total_geral);
            })
        : [],
    [summary],
  );

  const fixedStats = useMemo(() => {
    if (!summary || !meSpenderId) {
      return { total: 0, paid: 0, pending: 0, count: 0, lines: [] as Array<{ id: string; nome: string; sub: string; valor: number; pending: boolean }> };
    }
    const meUsage = summary.usage_by_person_cards.find((row) => row.pessoa_id === meSpenderId);
    if (!meUsage) {
      return { total: 0, paid: 0, pending: 0, count: 0, lines: [] };
    }
    const total = parseFloat(meUsage.total_gastos_fixos) || 0;
    const pending = parseFloat(meUsage.total_gastos_fixos_falta_pagar) || 0;
    const paid = total - pending;
    const lines = meUsage.gastos_fixos.slice(0, 4).map((g) => ({
      id: g.expense_id,
      nome: g.descricao,
      sub: "Gasto fixo",
      valor: parseFloat(g.total) || 0,
      pending: !g.pago,
    }));
    return { total, paid, pending, count: meUsage.gastos_fixos.length, lines };
  }, [summary, meSpenderId]);

  const tripPreview = useMemo(() => {
    const active = trips.find((t) => t.status === "planning" || t.status === "ongoing") ?? trips[0];
    return active ?? null;
  }, [trips]);

  const tripDaysLeft = useMemo(() => {
    if (!tripPreview?.data_inicio) return null;
    const start = new Date(`${tripPreview.data_inicio}T00:00:00`);
    if (Number.isNaN(start.getTime())) return null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return Math.ceil((start.getTime() - today.getTime()) / 86400000);
  }, [tripPreview]);

  const categoryChartRows = useMemo(() => {
    if (!summary) return [];
    return [...summary.expenses_by_category]
      .map((row) => ({
        name: row.categoria_nome,
        value: parseFloat(row.total) || 0,
      }))
      .filter((row) => row.value > 0)
      .sort((a, b) => b.value - a.value)
      .slice(0, 5)
      .map((row, idx) => ({
        ...row,
        color: CATEGORY_CHART_COLORS[idx % CATEGORY_CHART_COLORS.length],
      }));
  }, [summary]);

  const orderedIncomeCategories = useMemo(() => {
    const priority: Record<string, number> = { salario: 0, vale: 1, extra: 2 };
    return [...incomeCategories].sort((a, b) => {
      const aKey = normalizePersonName(a.nome);
      const bKey = normalizePersonName(b.nome);
      const aRank = priority[aKey] ?? 99;
      const bRank = priority[bKey] ?? 99;
      if (aRank !== bRank) return aRank - bRank;
      return a.nome.localeCompare(b.nome);
    });
  }, [incomeCategories]);

  const incomeCategoryLabelById = useMemo(
    () => new Map(incomeCategories.map((c) => [c.id, c.nome])),
    [incomeCategories],
  );

  const incomeSummary = useMemo(() => {
    const total = incomeRows.reduce((acc, row) => acc + (parseFloat(row.valor) || 0), 0);
    const recurringCount = incomeRows.filter((row) => row.recorrente).length;
    return { count: incomeRows.length, total, recurringCount };
  }, [incomeRows]);

  const bal = summary ? parseFloat(summary.monthly_balance) : 0;
  const totalIncome = summary ? parseFloat(summary.total_income) || 0 : 0;
  const totalExpenses = summary ? parseFloat(summary.total_expenses) || 0 : 0;
  const flowDenominator = totalIncome + totalExpenses;
  const incomeFlowPercent =
    flowDenominator > 0 ? Math.round((totalIncome / flowDenominator) * 100) : 50;
  const expenseFlowPercent = flowDenominator > 0 ? 100 - incomeFlowPercent : 50;

  useEffect(() => {
    if (!showIncomeForm || !periodId) return;
    let cancelled = false;
    setIncomeLoading(true);
    (async () => {
      try {
        const rows = (await api.listIncomes(periodId)) as IncomeRow[];
        if (!cancelled) {
          setIncomeRows(rows.sort((a, b) => b.data.localeCompare(a.data)));
        }
      } catch (err) {
        if (!cancelled) {
          setIncomeFormError(err instanceof Error ? err.message : "Erro ao carregar receitas");
        }
      } finally {
        if (!cancelled) setIncomeLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [showIncomeForm, periodId]);

  function resetIncomeForm() {
    setEditingIncomeId(null);
    setIncomeDescription("");
    setIncomeValue("");
    setIncomeDate(new Date().toISOString().slice(0, 10));
    setIncomeRecurring(false);
    setIncomeFormError("");
  }

  function startEditIncome(row: IncomeRow) {
    setEditingIncomeId(row.id);
    setIncomeDescription(row.descricao);
    setIncomeValue(String(row.valor).replace(".", ","));
    setIncomeDate(row.data);
    setIncomeRecurring(!!row.recorrente);
    setIncomeCategoryId(row.categoria_id);
    setIncomeFormError("");
  }

  async function removeIncome(id: string) {
    const ok = await confirm({
      title: "Excluir receita",
      message: "Excluir esta receita?",
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.deleteIncome(id);
      setIncomeRows((rows) => rows.filter((r) => r.id !== id));
      if (periodId) {
        const refreshed = await api.dashboardSummary(periodId);
        setSummary(refreshed);
      }
      if (editingIncomeId === id) resetIncomeForm();
    } catch (err) {
      setIncomeFormError(err instanceof Error ? err.message : "Erro ao excluir receita");
    }
  }

  async function handleQuickIncomeSubmit(e: { preventDefault: () => void }) {
    e.preventDefault();
    if (!periodId || !incomeCategoryId) {
      setIncomeFormError("Selecione categoria e período.");
      return;
    }
    setIncomeSaving(true);
    setIncomeFormError("");
    try {
      const payload = {
        descricao: incomeDescription,
        valor: incomeValue.replace(",", "."),
        data: incomeDate,
        period_id: periodId,
        categoria_id: incomeCategoryId,
        recorrente: incomeRecurring,
      };
      if (editingIncomeId) {
        await api.updateIncome(editingIncomeId, payload);
      } else {
        await api.createIncome(payload);
      }
      const [refreshedSummary, refreshedIncomes] = await Promise.all([
        api.dashboardSummary(periodId),
        api.listIncomes(periodId),
      ]);
      setSummary(refreshedSummary);
      setIncomeRows((refreshedIncomes as IncomeRow[]).sort((a, b) => b.data.localeCompare(a.data)));
      resetIncomeForm();
    } catch (err) {
      setIncomeFormError(err instanceof Error ? err.message : "Erro ao salvar receita");
    } finally {
      setIncomeSaving(false);
    }
  }

  if (!ready) return null;

  if (error && !summary) {
    return (
      <div className="padded dashboard-page">
        <p className="error">{error}</p>
      </div>
    );
  }

  let incomeModal: ReactNode = null;
  if (showIncomeForm) {
    incomeModal = (
      <div
        className="db-income-modal-overlay db-income-modal-overlay--open"
        role="presentation"
        onClick={() => setShowIncomeForm(false)}
      >
        <div
          className="db-income-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="income-modal-title"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="db-income-modal-header">
            <div className="db-income-modal-title-row">
              <div className="db-income-modal-icon" aria-hidden>
                💰
              </div>
              <h3 id="income-modal-title" className="db-income-modal-title">
                Receitas do período
              </h3>
            </div>
            <button
              type="button"
              className="db-income-modal-close"
              onClick={() => setShowIncomeForm(false)}
              aria-label="Fechar"
            >
              ✕
            </button>
          </div>

          <div className="db-income-modal-stats">
            <div className="db-income-stat-block">
              <div className="db-income-stat-lbl">Lançamentos</div>
              <div className="db-income-stat-val db-income-stat-val--blue">
                {incomeLoading ? "—" : incomeSummary.count}
              </div>
            </div>
            <div className="db-income-stat-block">
              <div className="db-income-stat-lbl">Total lançado</div>
              <div className="db-income-stat-val db-income-stat-val--green">
                {incomeLoading ? "—" : formatBRL(incomeSummary.total)}
              </div>
            </div>
            <div className="db-income-stat-block">
              <div className="db-income-stat-lbl">Recorrentes</div>
              <div className="db-income-stat-val db-income-stat-val--muted">
                {incomeLoading ? "—" : incomeSummary.recurringCount}
              </div>
            </div>
          </div>

          <div className="db-income-modal-table-wrap">
            {incomeLoading ? (
              <p className="db-income-modal-empty">Carregando receitas...</p>
            ) : incomeRows.length === 0 ? (
              <p className="db-income-modal-empty">Nenhuma receita cadastrada neste período.</p>
            ) : (
              <>
                <ul className="db-income-mobile-list card-lancamentos-mobile-only" aria-label="Receitas">
                  {incomeRows.map((row) => {
                    const catName = incomeCategoryLabelById.get(row.categoria_id) ?? "Categoria";
                    return (
                      <li key={row.id} className="db-income-mobile-item">
                        <div className="db-income-mobile-item-main">
                          <span className="db-income-mobile-item-desc">{row.descricao}</span>
                          <span className="db-income-modal-val">{formatBRL(row.valor)}</span>
                        </div>
                        <div className="db-income-mobile-item-meta">
                          <span className="db-income-cat-badge">
                            {incomeCategoryEmoji(catName)}
                            {catName}
                          </span>
                          <span className="db-income-modal-date">{formatDateBR(row.data)}</span>
                          <span
                            className={`db-income-rec-badge ${row.recorrente ? "db-income-rec-badge--sim" : "db-income-rec-badge--nao"}`}
                          >
                            {row.recorrente ? "Sim" : "Não"}
                          </span>
                        </div>
                        <div className="db-income-mobile-item-actions">
                          <button type="button" className="db-income-btn-edit" onClick={() => startEditIncome(row)}>
                            ✏️ Editar
                          </button>
                          <button type="button" className="db-income-btn-del" onClick={() => void removeIncome(row.id)}>
                            🗑 Excluir
                          </button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
                <div className="card-lancamentos-desktop-only">
                  <table className="db-income-modal-table">
                    <thead>
                      <tr>
                        <th>Data</th>
                        <th>Categoria</th>
                        <th>Descrição</th>
                        <th>Valor</th>
                        <th>Recorrente</th>
                        <th>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {incomeRows.map((row) => {
                        const catName = incomeCategoryLabelById.get(row.categoria_id) ?? "Categoria";
                        return (
                          <tr key={row.id}>
                            <td className="db-income-modal-date">{formatDateBR(row.data)}</td>
                            <td>
                              <span className="db-income-cat-badge">
                                {incomeCategoryEmoji(catName)}
                                {catName}
                              </span>
                            </td>
                            <td>{row.descricao}</td>
                            <td className="db-income-modal-val">{formatBRL(row.valor)}</td>
                            <td>
                              <span
                                className={`db-income-rec-badge ${row.recorrente ? "db-income-rec-badge--sim" : "db-income-rec-badge--nao"}`}
                              >
                                {row.recorrente ? "Sim" : "Não"}
                              </span>
                            </td>
                            <td className="db-income-modal-actions">
                              <button type="button" className="db-income-btn-edit" onClick={() => startEditIncome(row)}>
                                ✏️ Editar
                              </button>
                              <button type="button" className="db-income-btn-del" onClick={() => void removeIncome(row.id)}>
                                🗑 Excluir
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>

          <div className="db-income-modal-form-section">
            <div className="db-income-modal-form-title">
              {editingIncomeId ? "Editar receita" : "Nova receita"}
            </div>
            <form className="db-income-modal-form" onSubmit={handleQuickIncomeSubmit}>
              <div className="db-income-modal-form-grid">
                <div className="db-income-modal-field">
                  <label className="db-income-modal-label" htmlFor="quick-income-cat">
                    Categoria
                  </label>
                  <select
                    id="quick-income-cat"
                    className="db-income-modal-select"
                    value={incomeCategoryId}
                    onChange={(e) => setIncomeCategoryId(e.target.value)}
                    required
                  >
                    {orderedIncomeCategories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nome}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="db-income-modal-field">
                  <label className="db-income-modal-label" htmlFor="quick-income-date">
                    Data
                  </label>
                  <input
                    id="quick-income-date"
                    className="db-income-modal-input"
                    type="date"
                    value={incomeDate}
                    onChange={(e) => setIncomeDate(e.target.value)}
                    required
                  />
                </div>
                <div className="db-income-modal-field">
                  <label className="db-income-modal-label" htmlFor="quick-income-desc">
                    Descrição
                  </label>
                  <input
                    id="quick-income-desc"
                    className="db-income-modal-input"
                    type="text"
                    value={incomeDescription}
                    onChange={(e) => setIncomeDescription(e.target.value)}
                    placeholder="Ex: Salário, Freelance…"
                    required
                  />
                </div>
                <div className="db-income-modal-field">
                  <label className="db-income-modal-label" htmlFor="quick-income-value">
                    Valor (R$)
                  </label>
                  <input
                    id="quick-income-value"
                    className="db-income-modal-input db-income-modal-input--mono"
                    inputMode="decimal"
                    value={incomeValue}
                    onChange={(e) => setIncomeValue(e.target.value)}
                    placeholder="0,00"
                    required
                  />
                </div>
              </div>

              <label className="db-income-chk-row">
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={incomeRecurring}
                  onChange={(e) => setIncomeRecurring(e.target.checked)}
                />
                <span className={`db-income-chk${incomeRecurring ? " db-income-chk--on" : ""}`} aria-hidden />
                <span className="db-income-chk-label">Recorrente</span>
              </label>

              {incomeFormError && <p className="error">{incomeFormError}</p>}

              <div className="db-income-modal-form-footer">
                <button type="submit" className="db-income-btn-save" disabled={incomeSaving}>
                  {incomeSaving
                    ? "Salvando..."
                    : editingIncomeId
                      ? "💾 Salvar alterações"
                      : "💾 Salvar receita"}
                </button>
                {editingIncomeId && (
                  <button type="button" className="db-income-btn-limpar" onClick={resetIncomeForm}>
                    ↺ Nova receita
                  </button>
                )}
                <button type="button" className="db-income-btn-limpar" onClick={resetIncomeForm}>
                  ↺ Limpar
                </button>
                <button type="button" className="db-income-btn-cancelar" onClick={() => setShowIncomeForm(false)}>
                  ✕ Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="padded dashboard-page">
      {error && <p className="error" style={{ padding: "0 1rem" }}>{error}</p>}

      {summaryLoading && !summary && (
        <div className="db-skeleton" aria-hidden>
          <div className="skeleton db-skeleton-hero" />
        </div>
      )}

      {summary && (
        <>
          <div className="db-top-block">
            <div className="db-saldo-card">
            <div className="db-saldo-main">
              <div className="db-saldo-label">Saldo do mês</div>
              <div className={`db-saldo-value db-mono ${bal >= 0 ? "db-green" : "db-red"}`}>
                {formatBRL(summary.monthly_balance)}
              </div>
              <p className="db-saldo-updated">Atualizado hoje</p>
            </div>
            <div className="db-saldo-bar-wrap">
              <div
                className="db-bar-split"
                role="img"
                aria-label={`Receita ${formatBRL(totalIncome)} · Despesa ${formatBRL(totalExpenses)}`}
              >
                <div className="db-bar-r" style={{ flex: Math.max(incomeFlowPercent, 1) }} />
                <div className="db-bar-d" style={{ flex: Math.max(expenseFlowPercent, 1) }} />
              </div>
              <div className="db-bar-legend">
                <div className="db-legend-item">
                  <span className="db-dot" style={{ background: "var(--success)" }} />
                  <span>Receita {formatBRL(totalIncome)}</span>
                </div>
                <div className="db-legend-item">
                  <span className="db-dot" style={{ background: "var(--danger)" }} />
                  <span>Despesa {formatBRL(totalExpenses)}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="db-mini-stats">
            <button type="button" className="db-mini-card db-mini-card--action db-mini-card--green" onClick={() => setShowIncomeForm(true)}>
              <div className="db-mini-lbl">Receita</div>
              <div className="db-mini-val db-green">{formatCompactBRL(summary.total_income)}</div>
              <div className="db-mini-trend db-trend-neutral">Toque para lançar</div>
            </button>
            <button type="button" className="db-mini-card db-mini-card--action db-mini-card--red" onClick={() => navigate("/gastos-fixos")}>
              <div className="db-mini-lbl">Despesa</div>
              <div className="db-mini-val db-red">{formatCompactBRL(summary.total_expenses)}</div>
              <div className="db-mini-trend db-trend-neutral">Ver gastos</div>
            </button>
            <div className="db-mini-card db-mini-card--warn">
              <div className="db-mini-lbl">Falta pagar</div>
              <div className="db-mini-val db-amber">{formatCompactBRL(summary.pending_expenses)}</div>
              <div className="db-mini-trend db-trend-neutral">
                {parseFloat(summary.pending_expenses) > 0 ? "Pendências no mês" : "Tudo em dia"}
              </div>
            </div>
            <Link to="/investimentos" className="db-mini-card db-mini-card--action db-mini-card--blue">
              <div className="db-mini-lbl">Investimento</div>
              <div className="db-mini-val db-muted">
                {investmentPatrimonio != null ? formatCompactBRL(investmentPatrimonio) : "—"}
              </div>
              <div className="db-mini-trend db-trend-neutral">
                {investmentPatrimonio && investmentPatrimonio > 0 ? "Patrimônio" : "Nenhum lançado"}
              </div>
            </Link>
          </div>
          </div>

          <div className="db-actions-block">
          <div className="db-sec">
            <div className="db-sec-row">
              <h2 className="db-sec-title">Ações rápidas</h2>
            </div>
          </div>
          <nav className="db-quick-grid db-quick-grid--6" aria-label="Atalhos">
            {QUICK_LINKS.map(({ to, label, icon }) => (
              <Link key={to} to={to} className="db-quick-btn">
                <span className="db-quick-icon">{icon}</span>
                <span className="db-quick-label">{label}</span>
              </Link>
            ))}
          </nav>
          </div>

          {showHeavySections && (
            <div className="db-widgets">
              <div className="db-widgets-2">
              <section className="db-widget">
              <div className="db-widget-header">
                <div className="db-widget-title">
                  💳 Cartões{" "}
                  <span className="db-widget-badge db-widget-badge--b">{cardCountLabel(cardSlides.length)}</span>
                </div>
                <Link to="/cartoes" className="db-widget-link">
                  Ver todos →
                </Link>
              </div>
              <div className="db-widget-body">
              {cardSlides.length === 0 ? (
                <p className="muted">
                  Nenhum cartão cadastrado.{" "}
                  <Link to="/cartoes" className="db-empty-link">
                    Cadastrar cartões
                  </Link>
                </p>
              ) : (
                <>
                  {cardSlides.slice(0, 1).map((item) => (
                    <Link key={item.card.id} to={`/cartoes/${item.card.id}`} className="db-item-row">
                      <div className={`db-item-icon db-item-icon--stripe-${item.stripe}`}>💜</div>
                      <div className="db-item-info">
                        <div className="db-item-name">{item.card.nome}</div>
                        <div className="db-item-sub">
                          fecha dia {item.card.fechamento} · vence dia {item.card.vencimento}
                        </div>
                        <div className="db-mini-bar">
                          <div
                            className={`db-mini-bar-fill db-mini-bar-fill--${item.tier}`}
                            style={{ width: `${item.pctUsado}%` }}
                          />
                        </div>
                      </div>
                      <div className="db-item-right">
                        <div className="db-item-val">{formatCompactBRL(item.monthUsed)}</div>
                        <span
                          className={`db-status-badge ${
                            item.risk === "high"
                              ? "db-badge-high"
                              : item.risk === "warning"
                                ? "db-badge-warning"
                                : "db-badge-normal"
                          }`}
                        >
                          {cardRiskLabel(item.risk)}
                        </span>
                      </div>
                    </Link>
                  ))}
                  {cardSlides[0] && (
                    <div className="db-mini-stats-row">
                      <div className="db-mini-stat">
                        <div className="db-mini-stat-lbl">Usado</div>
                        <div className="db-mini-stat-val db-red">{formatCompactBRL(cardSlides[0].monthUsed)}</div>
                      </div>
                      <div className="db-mini-stat">
                        <div className="db-mini-stat-lbl">Disponível</div>
                        <div className={`db-mini-stat-val ${cardSlides[0].available < 0 ? "db-red" : "db-green"}`}>
                          {formatCompactBRL(cardSlides[0].available)}
                        </div>
                      </div>
                      <div className="db-mini-stat">
                        <div className="db-mini-stat-lbl">Limite</div>
                        <div className="db-mini-stat-val db-muted">{formatCompactBRL(cardSlides[0].limit)}</div>
                      </div>
                    </div>
                  )}
                </>
              )}
              </div>
              </section>

              <section className="db-widget">
              <div className="db-widget-header">
                <div className="db-widget-title">
                  🎯 Metas{" "}
                  <span className="db-widget-badge db-widget-badge--g">
                    {sortedGoalProgress.length} ativa{sortedGoalProgress.length === 1 ? "" : "s"}
                  </span>
                </div>
                <Link to="/metas" className="db-widget-link">
                  Ver todas →
                </Link>
              </div>
              <div className="db-widget-body">
              {sortedGoalProgress.length === 0 ? (
                <p className="muted">
                  Nenhuma meta.{" "}
                  <Link to="/metas" className="db-empty-link">
                    Criar meta
                  </Link>
                </p>
              ) : (
                <>
                  {sortedGoalProgress.slice(0, 1).map((g) => {
                    const detailsHidden = !!goalDetailsHiddenById[g.goal_id];
                    const progress = detailsHidden ? 0 : g.progress_percent;
                    return (
                      <div key={g.goal_id} className="db-item-row">
                        <GoalJarSvg progress={progress} id={`dash-${g.goal_id}`} variant={g.tipo} />
                        <div className="db-item-info">
                          <div className="db-item-name">{detailsHidden ? maskGoalTitle(g.nome) : g.nome}</div>
                          <div className="db-item-sub">{getGoalTypeLabel(g.tipo)}</div>
                          <div className="db-mini-bar">
                            <div
                              className="db-mini-bar-fill db-mini-bar-fill--green"
                              style={{ width: `${detailsHidden ? 0 : g.progress_percent}%` }}
                            />
                          </div>
                        </div>
                        <div className="db-item-right">
                          <div className="db-item-val db-green">
                            {detailsHidden ? "•••%" : `${g.progress_percent.toFixed(0)}%`}
                          </div>
                          <div className="db-item-sub">
                            {detailsHidden
                              ? "••••"
                              : `${formatCompactBRL(g.valor_atual)} / ${formatCompactBRL(g.valor_meta)}`}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  <div className="db-mini-stats-row">
                    <div className="db-mini-stat">
                      <div className="db-mini-stat-lbl">Ativas</div>
                      <div className="db-mini-stat-val db-blue">{sortedGoalProgress.length}</div>
                    </div>
                    <div className="db-mini-stat">
                      <div className="db-mini-stat-lbl">Concluídas</div>
                      <div className="db-mini-stat-val db-muted">
                        {sortedGoalProgress.filter((g) => g.progress_percent >= 100).length}
                      </div>
                    </div>
                    <div className="db-mini-stat">
                      <div className="db-mini-stat-lbl">Progresso</div>
                      <div className="db-mini-stat-val db-green">
                        {sortedGoalProgress.length
                          ? `${Math.round(
                              sortedGoalProgress.reduce((a, g) => a + g.progress_percent, 0) /
                                sortedGoalProgress.length,
                            )}%`
                          : "—"}
                      </div>
                    </div>
                  </div>
                </>
              )}
              </div>
              </section>
              </div>

              <div className="db-widgets-3">
              <section className="db-widget">
              <div className="db-widget-header">
                <div className="db-widget-title">
                  📌 Gastos fixos{" "}
                  <span className="db-widget-badge db-widget-badge--a">
                    {fixedStats.pending > 0 ? `${fixedStats.count} item(ns)` : "Em dia"}
                  </span>
                </div>
                <Link to="/gastos-fixos" className="db-widget-link">
                  Ver →
                </Link>
              </div>
              <div className="db-widget-body">
                {fixedStats.lines.length === 0 ? (
                  <p className="muted">Nenhum gasto fixo neste período.</p>
                ) : (
                  fixedStats.lines.map((line) => (
                    <div key={line.id} className="db-item-row">
                      <div className="db-item-icon db-item-icon--amber">🏠</div>
                      <div className="db-item-info">
                        <div className="db-item-name">{line.nome}</div>
                        <div className="db-item-sub">{line.sub}</div>
                      </div>
                      <div className="db-item-right db-item-right--row">
                        <div className="db-item-val">{formatCompactBRL(line.valor)}</div>
                        <div className={`db-sdot ${line.pending ? "db-sdot--a" : "db-sdot--g"}`} />
                      </div>
                    </div>
                  ))
                )}
                <div className="db-mini-stats-row db-mini-stats-row--2">
                  <div className="db-mini-stat">
                    <div className="db-mini-stat-lbl">Total mês</div>
                    <div className="db-mini-stat-val">{formatCompactBRL(fixedStats.total)}</div>
                  </div>
                  <div className="db-mini-stat">
                    <div className="db-mini-stat-lbl">Pendente</div>
                    <div className="db-mini-stat-val db-amber">{formatCompactBRL(fixedStats.pending)}</div>
                  </div>
                </div>
              </div>
              </section>

              <section className="db-widget">
              <div className="db-widget-header">
                <div className="db-widget-title">
                  ✈️ Viagens{" "}
                  <span className="db-widget-badge db-widget-badge--b">
                    {trips.length} {trips.length === 1 ? "viagem" : "viagens"}
                  </span>
                </div>
                <Link to="/viagens" className="db-widget-link">
                  Ver →
                </Link>
              </div>
              <div className="db-widget-body">
                {!tripPreview ? (
                  <p className="muted">Nenhuma viagem cadastrada.</p>
                ) : (
                  <>
                    <Link to={`/viagens/${tripPreview.id}`} className="db-item-row">
                      <div className="db-item-icon db-item-icon--blue">🏖️</div>
                      <div className="db-item-info">
                        <div className="db-item-name">{tripPreview.nome}</div>
                        <div className="db-item-sub">
                          {[
                            tripPreview.destino,
                            tripPreview.data_inicio && tripPreview.data_fim
                              ? `${formatShortDateBR(tripPreview.data_inicio)} → ${formatShortDateBR(tripPreview.data_fim)}`
                              : null,
                            tripDaysLeft != null && tripDaysLeft > 0 ? `${tripDaysLeft} dias restantes` : null,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </div>
                        {tripPreview.orcamento_total && (
                          <div className="db-mini-bar">
                            <div
                              className="db-mini-bar-fill db-mini-bar-fill--blue"
                              style={{
                                width: `${Math.min(
                                  100,
                                  Math.round(
                                    ((parseFloat(tripPreview.total_gasto) || 0) /
                                      (parseFloat(tripPreview.orcamento_total) || 1)) *
                                      100,
                                  ),
                                )}%`,
                              }}
                            />
                          </div>
                        )}
                      </div>
                      <div className="db-item-right">
                        <div className="db-item-val db-blue">{formatCompactBRL(tripPreview.total_gasto)}</div>
                        <div className="db-item-sub db-green">
                          {tripPreview.status === "ongoing"
                            ? "● Em andamento"
                            : tripPreview.status === "closed"
                              ? "● Encerrada"
                              : "● Planejada"}
                        </div>
                      </div>
                    </Link>
                    <div className="db-mini-stats-row">
                      <div className="db-mini-stat">
                        <div className="db-mini-stat-lbl">Orçamento</div>
                        <div className="db-mini-stat-val db-muted">
                          {tripPreview.orcamento_total ? formatCompactBRL(tripPreview.orcamento_total) : "—"}
                        </div>
                      </div>
                      <div className="db-mini-stat">
                        <div className="db-mini-stat-lbl">Usado</div>
                        <div className="db-mini-stat-val db-green">
                          {tripPreview.orcamento_total
                            ? `${Math.min(
                                100,
                                Math.round(
                                  ((parseFloat(tripPreview.total_gasto) || 0) /
                                    (parseFloat(tripPreview.orcamento_total) || 1)) *
                                    100,
                                ),
                              )}%`
                            : "—"}
                        </div>
                      </div>
                      <div className="db-mini-stat">
                        <div className="db-mini-stat-lbl">Dias</div>
                        <div className="db-mini-stat-val db-amber">
                          {tripDaysLeft != null ? `${tripDaysLeft}d` : "—"}
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>
              </section>

              <section className="db-widget">
              <div className="db-widget-header">
                <div className="db-widget-title">
                  📈 Investimentos{" "}
                  <span className="db-widget-badge db-widget-badge--muted">
                    {investments.length > 0 ? `${investments.length}` : "Em breve"}
                  </span>
                </div>
                <Link to="/investimentos" className="db-widget-link">
                  Ver →
                </Link>
              </div>
              <div className="db-widget-body">
                {investments.length === 0 ? (
                  <div className="db-empty-block">
                    <div className="db-empty-icon">📈</div>
                    <div className="db-empty-title">Nenhum investimento lançado</div>
                    <div className="db-empty-sub">Adicione seus investimentos para acompanhar aqui</div>
                  </div>
                ) : (
                  <>
                    {investments.slice(0, 2).map((inv) => (
                      <div key={inv.id} className="db-item-row">
                        <div className="db-item-icon db-item-icon--green">📈</div>
                        <div className="db-item-info">
                          <div className="db-item-name">{inv.descricao}</div>
                          <div className="db-item-sub">{getInvestmentTypeLabel(inv.tipo)}</div>
                        </div>
                        <div className="db-item-right">
                          <div className="db-item-val">{formatCompactBRL(inv.valor_atual)}</div>
                        </div>
                      </div>
                    ))}
                    <div className="db-mini-stats-row db-mini-stats-row--2">
                      <div className="db-mini-stat">
                        <div className="db-mini-stat-lbl">Patrimônio</div>
                        <div className="db-mini-stat-val db-green">
                          {investmentPatrimonio != null ? formatCompactBRL(investmentPatrimonio) : "—"}
                        </div>
                      </div>
                      <div className="db-mini-stat">
                        <div className="db-mini-stat-lbl">Ativos</div>
                        <div className="db-mini-stat-val">{investments.length}</div>
                      </div>
                    </div>
                  </>
                )}
              </div>
              </section>
              </div>

              <section className="db-widget">
              <div className="db-widget-header">
                <div className="db-widget-title">
                  👥 Pessoas no cartão{" "}
                  <span className="db-widget-badge db-widget-badge--b">
                    {sortedUsageByPerson.length} pessoas
                  </span>
                </div>
                <Link to="/dashboard/pessoas" className="db-widget-link">
                  Gerenciar →
                </Link>
              </div>
              <div className="db-widget-body db-widget-body--flush">
              {sortedUsageByPerson.length === 0 ? (
                <p className="muted" style={{ padding: "16px 18px" }}>
                  Sem uso por pessoa neste período.
                </p>
              ) : (
                <div className="db-people-grid">
                  {sortedUsageByPerson.map((row) => {
                    const me = isMePerson(row.pessoa_nome);
                    const falta = parseFloat(row.total_falta_pagar) || 0;
                    return (
                      <Link
                        key={row.pessoa_id ?? row.pessoa_nome}
                        className="db-people-card"
                        to={`/dashboard/uso-pessoa/${encodeURIComponent(row.pessoa_id ?? row.pessoa_nome)}`}
                      >
                        {me && <span className="db-people-eu">EU</span>}
                        <div className="db-people-head">
                          <div
                            className="db-pessoa-av"
                            style={{ background: personGradient(row.pessoa_nome) }}
                          >
                            {personInitial(row.pessoa_nome)}
                          </div>
                          <div>
                            <div className="db-people-name">{row.pessoa_nome}</div>
                            <div className="db-people-role">{me ? "Titular" : "Adicional"}</div>
                          </div>
                        </div>
                        <div className="db-people-stats">
                          <div className="db-mini-stat">
                            <div className="db-mini-stat-lbl">Gasto</div>
                            <div className="db-mini-stat-val db-red">{formatCompactBRL(row.total_geral)}</div>
                          </div>
                          <div className="db-mini-stat">
                            <div className="db-mini-stat-lbl">Status</div>
                            <div className={`db-mini-stat-val ${falta > 0 ? "db-amber" : "db-green"}`}>
                              {falta > 0 ? "● Pendente" : "● Pago"}
                            </div>
                          </div>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
              </div>
              </section>

              <section className="db-widget">
              <div className="db-widget-header">
                <div className="db-widget-title">🏷️ Gastos por categoria</div>
              </div>
              <div className="db-widget-body">
              <div className="db-cat-chart-wrap">
                  {categoryChartRows.length === 0 ? (
                    <p className="muted">Sem despesas por categoria neste período.</p>
                  ) : (
                    <CategoryExpensesChart
                      rows={categoryChartRows}
                      totalLabel={formatCompactBRL(
                        categoryChartRows.reduce((sum, row) => sum + row.value, 0),
                      )}
                    />
                  )}
              </div>
              </div>
              </section>
            </div>
          )}

          {!showHeavySections && summary && (
            <p className="muted" style={{ padding: "1rem", textAlign: "center" }}>
              Carregando painéis detalhados...
            </p>
          )}
        </>
      )}

      {incomeModal}
    </div>
  );
}
