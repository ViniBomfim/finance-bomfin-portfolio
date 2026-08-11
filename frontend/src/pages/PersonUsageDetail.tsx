import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CategoryExpensesChart, CATEGORY_CHART_COLORS } from "../components/CategoryExpensesChart";
import { api } from "../api";
import { usePeriod } from "../context/PeriodContext";
import { downloadPersonUsagePdf } from "../exportCsv";
import { buildStripeByCardId, invoiceClosingInfo, type CardComputed } from "../lib/cardMetrics";
import { formatBRL, formatCompactBRL } from "../money";
import type { CardRow, DashboardSummary } from "../types";
const PERSON_GRADIENTS = [
  "linear-gradient(135deg,#f43f5e,#a855f7)",
  "linear-gradient(135deg,#3b82f6,#22d3ee)",
  "linear-gradient(135deg,#22c55e,#16a34a)",
  "linear-gradient(135deg,#f59e0b,#ef4444)",
];

const STRIPE_COLORS: Record<string, string> = {
  nubank: "#a855f7",
  itau: "#0057b8",
  itau2: "#3b82f6",
  santander: "#ef4444",
  default: "var(--accent)",
};

function normalizeKey(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

function formatShortDateBR(value: string): string {
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
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

function capitalizePeriodLabel(label: string) {
  if (!label) return label;
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function formatMonthYear(value: string): string {
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("pt-BR", { month: "short", year: "numeric" }).replace(".", "");
}

export function PersonUsageDetail() {
  const { personRef } = useParams<{ personRef: string }>();
  const navigate = useNavigate();
  const { periodId, ready, monthLabel, currentPeriod } = usePeriod();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [cards, setCards] = useState<CardRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!periodId) return;
    let cancelled = false;
    (async () => {
      try {
        if (!cancelled) setError("");
        const [s, cardsList] = await Promise.all([api.dashboardSummary(periodId), api.listCards()]);
        if (!cancelled) {
          setSummary(s);
          setCards(cardsList);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Erro ao carregar uso por pessoa");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [periodId]);

  const person = useMemo(() => {
    if (!summary || !personRef) return null;
    return (
      summary.usage_by_person_cards.find((row) => row.pessoa_id === personRef) ??
      summary.usage_by_person_cards.find((row) => normalizeKey(row.pessoa_nome) === normalizeKey(personRef))
    );
  }, [summary, personRef]);

  const personInstallments = useMemo(() => {
    if (!summary || !person) return null;
    return (
      summary.person_installments.find((row) => row.pessoa_id === person.pessoa_id) ??
      summary.person_installments.find(
        (row) => normalizeKey(row.pessoa_nome) === normalizeKey(person.pessoa_nome),
      ) ??
      null
    );
  }, [summary, person]);

  const categoryChartRows = useMemo(() => {
    if (!summary || !person) return [];
    const match =
      summary.expenses_by_person_category.find((row) => row.pessoa_id === person.pessoa_id) ??
      summary.expenses_by_person_category.find(
        (row) => normalizeKey(row.pessoa_nome) === normalizeKey(person.pessoa_nome),
      );
    if (!match) return [];
    return [...match.categorias]
      .map((cat) => ({
        name: cat.categoria_nome,
        value: parseFloat(cat.total) || 0,
      }))
      .filter((row) => row.value > 0)
      .sort((a, b) => b.value - a.value)
      .slice(0, 5)
      .map((row, idx) => ({
        ...row,
        color: CATEGORY_CHART_COLORS[idx % CATEGORY_CHART_COLORS.length],
      }));
  }, [summary, person]);

  const cardStripes = useMemo(() => {
    if (!person || cards.length === 0) return new Map<string, string>();
    const cardById = new Map(cards.map((c) => [c.id, c]));
    const metrics: CardComputed[] = person.cartoes
      .filter((c) => c.card_id)
      .map((c) => {
        const card = cardById.get(c.card_id!);
        const row =
          card ?? {
            id: c.card_id!,
            nome: c.card_nome,
            banco: "",
            limite: "0",
            fechamento: 1,
            vencimento: 1,
          };
        return {
          card: row,
          monthUsed: parseFloat(c.total) || 0,
          spentTotal: 0,
          limit: 0,
          available: 0,
          utilization: 0,
          hasActivity: true,
          unpaidTotal: 0,
          unpaidCount: 0,
          paidAt: null,
          isPaid: false,
          risk: "normal",
          daysUntilDue: 0,
          closingInfo: invoiceClosingInfo(row.fechamento),
        };
      });
    return buildStripeByCardId(metrics);
  }, [person, cards]);

  function onGoBack() {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate("/");
  }

  const periodTitle =
    currentPeriod != null
      ? capitalizePeriodLabel(monthLabel(currentPeriod.mes, currentPeriod.ano))
      : "";

  if (!ready) return null;
  if (error && !summary) {
    return (
      <div className="padded person-detail-page">
        <p className="error">{error}</p>
      </div>
    );
  }

  return (
    <div className="padded person-detail-page">
      <header className="pd-detail-header">
        <button type="button" className="pd-detail-back" onClick={() => onGoBack()}>
          ← Voltar
        </button>
        {person && (
          <div className="pd-detail-person-row">
            <div className="pd-detail-av" style={{ background: personGradient(person.pessoa_nome) }}>
              {personInitial(person.pessoa_nome)}
            </div>
            <div>
              <h1 className="pd-detail-name">{person.pessoa_nome}</h1>
              <div className="pd-detail-sub">Resumo financeiro · {periodTitle.toLowerCase()}</div>
            </div>
          </div>
        )}
      </header>

      {error && <p className="error" style={{ padding: "0 1rem" }}>{error}</p>}

      {!person ? (
        <p className="muted" style={{ padding: "1rem" }}>
          Pessoa não encontrada neste período.
        </p>
      ) : (
        <>
          <div className="pd-top-section">
          <div className="pd-detail-summary">
            <div className="pd-summary-grid">
              <div className="pd-summary-item">
                <div className="pd-summary-lbl">Total Cartões</div>
                <div className="pd-summary-val" style={{ color: "var(--accent)" }}>
                  {formatBRL(person.total_cartoes)}
                </div>
              </div>
              <div className="pd-summary-item">
                <div className="pd-summary-lbl">Gastos Fixos</div>
                <div className="pd-summary-val" style={{ color: "var(--warning)" }}>
                  {formatBRL(person.total_gastos_fixos)}
                </div>
              </div>
              <div className="pd-summary-item">
                <div className="pd-summary-lbl">Devedores</div>
                <div className="pd-summary-val" style={{ color: "var(--danger)" }}>
                  {formatBRL(person.total_divida_devedores)}
                </div>
              </div>
              <div className="pd-summary-item">
                <div className="pd-summary-lbl">Falta Pagar</div>
                <div className="pd-summary-val" style={{ color: "var(--danger)" }}>
                  {formatBRL(person.total_falta_pagar)}
                </div>
              </div>
            </div>
            <div className="pd-summary-total">
              <span className="pd-summary-total-lbl">Total geral</span>
              <span className="pd-summary-total-val">{formatBRL(person.total_geral)}</span>
            </div>
          </div>

          <button
            type="button"
            className="pd-btn-pdf"
            onClick={() =>
              downloadPersonUsagePdf(person, personInstallments, `uso-${person.pessoa_nome}.pdf`, {
                periodLabel: periodTitle,
                categories: categoryChartRows.map((row) => ({
                  name: row.name,
                  total: row.value,
                })),
              })
            }
          >
            📄 Baixar PDF com todas as informações
          </button>
          </div>

          <div className="pd-content-grid">
            <div className="pd-col pd-col--main">
          <div className="pd-det-sec">
            <h2 className="pd-det-sec-title">💳 Despesas em cartões</h2>
          </div>
          {person.cartoes.length === 0 ? (
            <p className="muted" style={{ padding: "0 1rem" }}>
              Sem despesas de cartão neste período.
            </p>
          ) : (
            person.cartoes.map((card) => {
              const stripeKey = cardStripes.get(card.card_id ?? "") ?? "default";
              const stripeColor = STRIPE_COLORS[stripeKey] ?? STRIPE_COLORS.default;
              return (
                <div key={`${card.card_id ?? card.card_nome}`}>
                  <div className="pd-card-group-label">
                    <div className="pd-card-group-stripe" style={{ background: stripeColor }} />
                    {card.card_nome}
                  </div>
                  <div className="pd-expense-table">
                    <div className="pd-exp-head">
                      <div className="pd-exp-th">Data</div>
                      <div className="pd-exp-th">Descrição</div>
                      <div className="pd-exp-th">Parcela</div>
                      <div className="pd-exp-th pd-exp-th--right">Valor</div>
                    </div>
                    {card.lancamentos.length === 0 ? (
                      <div className="pd-exp-row">
                        <div className="pd-exp-td-date">—</div>
                        <div className="pd-exp-td-name muted">Sem lançamentos</div>
                        <div className="pd-exp-td-parcela">—</div>
                        <div className="pd-exp-td-val">—</div>
                      </div>
                    ) : (
                      card.lancamentos.map((tx) => (
                        <div key={tx.transaction_id} className="pd-exp-row">
                          <div className="pd-exp-td-date">{formatShortDateBR(tx.data)}</div>
                          <div>
                            <div className="pd-exp-td-name">{tx.descricao}</div>
                            <span className={`pd-exp-status ${tx.pago ? "pd-exp-pago" : "pd-exp-pend"}`}>
                              {tx.pago ? "Pago" : "Pendente"}
                            </span>
                          </div>
                          <div className="pd-exp-td-parcela">
                            {tx.parcela_total > 1 ? `${tx.parcela_atual}/${tx.parcela_total}` : "1x"}
                          </div>
                          <div className="pd-exp-td-val">{formatBRL(tx.valor)}</div>
                        </div>
                      ))
                    )}
                    <div className="pd-card-total-row">
                      <span className="pd-card-total-lbl">Total {card.card_nome}</span>
                      <span className="pd-card-total-val" style={{ color: "var(--accent)" }}>
                        {formatBRL(card.total)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })
          )}

          <div className="pd-det-sec">
            <h2 className="pd-det-sec-title">🛒 Parcelas em aberto</h2>
          </div>
          {!personInstallments || personInstallments.compras.length === 0 ? (
            <p className="muted pd-panel-empty">Sem compras parceladas para esta pessoa.</p>
          ) : (
            personInstallments.compras.map((purchase) => {
              const pct =
                purchase.total_parcelas > 0
                  ? Math.round((purchase.parcela_atual / purchase.total_parcelas) * 100)
                  : 0;
              return (
                <div key={purchase.compra_id} className="pd-parcela-det-item">
                  <div className="pd-parc-top">
                    <div className="pd-parc-name">{purchase.descricao}</div>
                    <div className="pd-parc-val" style={{ color: "var(--warning)" }}>
                      {formatBRL(purchase.valor_parcela)}/mês
                    </div>
                  </div>
                  <div className="pd-parc-sub">
                    {purchase.card_nome} · {purchase.parcela_atual} de {purchase.total_parcelas} · até{" "}
                    {formatMonthYear(purchase.ate_data)}
                  </div>
                  <div className="pd-parc-bar">
                    <div
                      className="pd-parc-fill"
                      style={{ width: `${pct}%`, background: "var(--accent)" }}
                    />
                  </div>
                </div>
              );
            })
          )}
            </div>

            <div className="pd-col pd-col--aside">
          {categoryChartRows.length > 0 && (
            <>
              <div className="pd-det-sec">
                <h2 className="pd-det-sec-title">🏷️ Gastos por categoria</h2>
              </div>
              <div className="pd-cat-chart-wrap">
                <CategoryExpensesChart
                  rows={categoryChartRows}
                  totalLabel={formatCompactBRL(
                    categoryChartRows.reduce((sum, row) => sum + row.value, 0),
                  )}
                />
              </div>
            </>
          )}

          <div className="pd-det-sec">
            <h2 className="pd-det-sec-title">📌 Gastos fixos</h2>
          </div>
          {person.gastos_fixos.length === 0 ? (
            <p className="muted" style={{ padding: "0 1rem" }}>
              Sem gastos fixos para esta pessoa.
            </p>
          ) : (
            person.gastos_fixos.map((fixed) => (
              <div key={fixed.expense_id} className="pd-gasto-fixo-item">
                <div className="pd-gf-top">
                  <div className="pd-gf-name">{fixed.descricao}</div>
                  <div className="pd-gf-val">{formatBRL(fixed.total)}</div>
                </div>
                <div className="pd-gf-meta">
                  <span className={`pd-exp-status ${fixed.pago ? "pd-exp-pago" : "pd-exp-pend"}`}>
                    {fixed.pago ? "Pago" : "Não pago"}
                  </span>
                </div>
              </div>
            ))
          )}

          <div className="pd-det-sec">
            <h2 className="pd-det-sec-title">💸 Devedores</h2>
          </div>
          <div className="pd-card-generic">
            {person.devedores.length === 0 ? (
              <div className="pd-empty-note">Nenhuma dívida pendente ✓</div>
            ) : (
              person.devedores.map((debtor) => (
                <div key={debtor.loan_id} className="pd-devedor-row">
                  <div className="pd-dev-av" style={{ background: personGradient(debtor.devedor_nome) }}>
                    {personInitial(debtor.devedor_nome)}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="pd-dev-name">{debtor.devedor_nome}</div>
                    <div className="pd-dev-desc">
                      Empréstimo · {formatBRL(debtor.valor_emprestado)}
                    </div>
                  </div>
                  <div
                    className="pd-dev-val"
                    style={{ color: parseFloat(debtor.falta_pagar) > 0 ? "var(--warning)" : "var(--success)" }}
                  >
                    {formatBRL(debtor.falta_pagar)}
                  </div>
                </div>
              ))
            )}
            <Link to="/devedores" className="pd-gastos-link">
              Ir para Devedores
            </Link>
          </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
