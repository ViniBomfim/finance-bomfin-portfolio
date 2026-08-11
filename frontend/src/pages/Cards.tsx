import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAppDialog } from "../context/DialogContext";
import {
  buildStripeByCardId,
  cardCountLabel,
  cardRiskLevel,
  closingChipParts,
  daysUntilNextDay,
  dueChipParts,
  invoiceClosingInfo,
  usageTier,
  type CardComputed,
} from "../lib/cardMetrics";
import { usePeriod } from "../context/PeriodContext";
import { availableCardLimit, formatBRL } from "../money";
import type { CardRow } from "../types";

type CardSort = "usage_desc" | "usage_asc" | "limit_desc" | "name_asc";
type ActiveChip = "all" | "alert" | string;

const CARD_BANKS = [
  { id: "nubank", label: "Nubank", preview: "Banco Nubank", color: "linear-gradient(90deg,#820ad1,#a855f7)" },
  { id: "itau", label: "Itaú", preview: "Banco Itaú", color: "linear-gradient(90deg,#003d7c,#0057b8)" },
  { id: "bradesco", label: "Bradesco", preview: "Banco Bradesco", color: "linear-gradient(90deg,#cc0000,#ef4444)" },
  { id: "santander", label: "Santander", preview: "Banco Santander", color: "linear-gradient(90deg,#cc0000,#f43f5e)" },
  { id: "bb", label: "Banco do Brasil", preview: "Banco do Brasil", color: "linear-gradient(90deg,#f59e0b,#fbbf24)" },
  { id: "caixa", label: "Caixa", preview: "Caixa Econômica", color: "linear-gradient(90deg,#1d4ed8,#3b82f6)" },
  { id: "inter", label: "Inter", preview: "Banco Inter", color: "linear-gradient(90deg,#ea580c,#f97316)" },
  { id: "c6", label: "C6 Bank", preview: "C6 Bank", color: "linear-gradient(90deg,#1c1c1c,#404040)" },
  { id: "xp", label: "XP", preview: "XP Investimentos", color: "linear-gradient(90deg,#0f172a,#1e293b)" },
  { id: "outro", label: "Outro", preview: "Outro banco", color: "linear-gradient(90deg,#475569,#64748b)" },
] as const;

type CardBankId = (typeof CARD_BANKS)[number]["id"];

function normalizeBankKey(banco: string): string {
  return banco
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "");
}

function resolveBankKey(banco: string): CardBankId {
  const key = normalizeBankKey(banco);
  if (key.includes("nubank")) return "nubank";
  if (key.includes("itau")) return "itau";
  if (key.includes("bradesco")) return "bradesco";
  if (key.includes("santander")) return "santander";
  if (key.includes("banco do brasil") || key === "bb") return "bb";
  if (key.includes("caixa")) return "caixa";
  if (key.includes("inter")) return "inter";
  if (key.includes("c6")) return "c6";
  if (key.includes("xp")) return "xp";
  return "outro";
}

function bankById(id: CardBankId) {
  return CARD_BANKS.find((b) => b.id === id) ?? CARD_BANKS[CARD_BANKS.length - 1];
}

function formatPaidAtBR(iso: string): string {
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return iso;
  return `${d}/${m}/${y}`;
}

export function Cards() {
  const { periodId, ready } = usePeriod();
  const { confirm: askConfirm } = useAppDialog();
  const [cards, setCards] = useState<CardRow[]>([]);
  const [usedByCard, setUsedByCard] = useState<Record<string, string>>({});
  const [spentLifetimeByCard, setSpentLifetimeByCard] = useState<Record<string, string>>({});
  const [unpaidByCard, setUnpaidByCard] = useState<
    Record<string, { unpaidTotal: string; unpaidCount: number; paidAt: string | null }>
  >({});
  const [cardsLoading, setCardsLoading] = useState(true);
  const [usedLoading, setUsedLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [activeChip, setActiveChip] = useState<ActiveChip>("all");
  const [sortBy, setSortBy] = useState<CardSort>("usage_desc");
  const [nome, setNome] = useState("");
  const [banco, setBanco] = useState("");
  const [bancoKey, setBancoKey] = useState<CardBankId | "">("");
  const [limite, setLimite] = useState("");
  const [fechamento, setFechamento] = useState("10");
  const [vencimento, setVencimento] = useState("15");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingCardId, setEditingCardId] = useState<string | null>(null);
  const [savingCard, setSavingCard] = useState(false);

  async function load() {
    setCardsLoading(true);
    try {
      const c = await api.listCards();
      setCards(c);
    } finally {
      setCardsLoading(false);
    }
  }

  useEffect(() => {
    let x = false;
    (async () => {
      try {
        await load();
      } catch (e) {
        if (!x) setError(e instanceof Error ? e.message : "Erro");
      }
    })();
    return () => {
      x = true;
    };
  }, []);

  useEffect(() => {
    if (!ready || !periodId || cards.length === 0) {
      setUsedByCard({});
      setSpentLifetimeByCard({});
      setUnpaidByCard({});
      setUsedLoading(false);
      return;
    }
    let cancelled = false;
    setUsedLoading(true);
    (async () => {
      try {
        const rows = await Promise.all(
          cards.map(async (c) => {
            const [inv, spent] = await Promise.all([
              api.invoiceTotal(c.id, periodId),
              api.cardSpentTotal(c.id),
            ]);
            return {
              id: c.id,
              periodTotal: inv.total,
              lifetimeSpent: spent.total,
              unpaidTotal: inv.unpaid_total ?? "0",
              unpaidCount: inv.unpaid_count ?? 0,
              paidAt: inv.paid_at ?? null,
            };
          }),
        );
        if (!cancelled) {
          setUsedByCard(Object.fromEntries(rows.map((r) => [r.id, r.periodTotal])));
          setSpentLifetimeByCard(Object.fromEntries(rows.map((r) => [r.id, r.lifetimeSpent])));
          setUnpaidByCard(
            Object.fromEntries(
              rows.map((r) => [
                r.id,
                { unpaidTotal: r.unpaidTotal, unpaidCount: r.unpaidCount, paidAt: r.paidAt },
              ]),
            ),
          );
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Erro");
      } finally {
        if (!cancelled) setUsedLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [cards, periodId, ready]);

  const cardMetrics = useMemo<CardComputed[]>(() => {
    return cards.map((card) => {
      const limit = parseFloat(card.limite) || 0;
      const monthUsed = parseFloat(usedByCard[card.id] ?? "0") || 0;
      const spentTotal = parseFloat(spentLifetimeByCard[card.id] ?? "0") || 0;
      const unpaidMeta = unpaidByCard[card.id];
      const unpaidTotal = parseFloat(unpaidMeta?.unpaidTotal ?? "0") || 0;
      const unpaidCount = unpaidMeta?.unpaidCount ?? 0;
      const paidAt = unpaidMeta?.paidAt ?? null;
      const available = availableCardLimit(card.limite, spentLifetimeByCard[card.id] ?? "0");
      const utilization = limit > 0 ? (monthUsed / limit) * 100 : 0;
      const hasActivity = monthUsed > 0.009 || unpaidCount > 0 || paidAt != null;
      return {
        card,
        monthUsed,
        spentTotal,
        limit,
        available,
        utilization,
        hasActivity,
        unpaidTotal,
        unpaidCount,
        paidAt,
        isPaid: unpaidCount === 0 && hasActivity,
        risk: cardRiskLevel(utilization),
        daysUntilDue: daysUntilNextDay(card.vencimento),
        closingInfo: invoiceClosingInfo(card.fechamento),
      };
    });
  }, [cards, spentLifetimeByCard, unpaidByCard, usedByCard]);

  const stripeByCardId = useMemo(() => buildStripeByCardId(cardMetrics), [cardMetrics]);

  const bankChips = useMemo(() => {
    const seen = new Set<string>();
    const list: string[] = [];
    for (const x of cardMetrics) {
      const b = x.card.banco.trim();
      if (!b) continue;
      const key = b.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      list.push(b);
    }
    return list.sort((a, b) => a.localeCompare(b, "pt-BR"));
  }, [cardMetrics]);

  const filteredCards = useMemo(() => {
    const query = search.trim().toLowerCase();
    const filtered = cardMetrics.filter((x) => {
      const matchesSearch =
        query.length === 0 ||
        x.card.nome.toLowerCase().includes(query) ||
        x.card.banco.toLowerCase().includes(query);
      if (!matchesSearch) return false;
      if (activeChip === "alert") return x.risk !== "normal";
      if (activeChip !== "all") {
        return x.card.banco.trim().toLowerCase() === activeChip.toLowerCase();
      }
      return true;
    });
    return [...filtered].sort((a, b) => {
      if (sortBy === "name_asc") return a.card.nome.localeCompare(b.card.nome, "pt-BR");
      if (sortBy === "usage_asc") return a.utilization - b.utilization;
      if (sortBy === "limit_desc") return b.limit - a.limit;
      return b.utilization - a.utilization;
    });
  }, [cardMetrics, activeChip, search, sortBy]);

  const totalLimit = useMemo(
    () => cardMetrics.reduce((acc, item) => acc + item.limit, 0),
    [cardMetrics],
  );
  const totalUsedMonth = useMemo(
    () => cardMetrics.reduce((acc, item) => acc + item.monthUsed, 0),
    [cardMetrics],
  );
  const totalAvailable = useMemo(
    () => cardMetrics.reduce((acc, item) => acc + item.available, 0),
    [cardMetrics],
  );
  const cardsInAlert = useMemo(
    () => cardMetrics.reduce((acc, item) => acc + (item.risk === "normal" ? 0 : 1), 0),
    [cardMetrics],
  );

  function clearFilters() {
    setSearch("");
    setActiveChip("all");
  }

  function resetCardForm() {
    setNome("");
    setBanco("");
    setBancoKey("");
    setLimite("");
    setFechamento("10");
    setVencimento("15");
  }

  function closeCardModal() {
    setShowCreateModal(false);
    setEditingCardId(null);
    resetCardForm();
  }

  function openCreateModal() {
    setEditingCardId(null);
    resetCardForm();
    setShowCreateModal(true);
  }

  function openEditModal(card: CardRow) {
    setShowCreateModal(false);
    setEditingCardId(card.id);
    setNome(card.nome);
    const key = resolveBankKey(card.banco);
    setBancoKey(key);
    setBanco(bankById(key).label);
    setLimite(String(card.limite).replace(".", ","));
    setFechamento(String(card.fechamento));
    setVencimento(String(card.vencimento));
  }

  function onBankKeyChange(nextKey: string) {
    if (!nextKey) {
      setBancoKey("");
      setBanco("");
      return;
    }
    const bank = bankById(nextKey as CardBankId);
    setBancoKey(bank.id);
    setBanco(bank.label);
  }

  async function onDeleteCard(card: CardRow) {
    const ok = await askConfirm({
      title: "Excluir cartão",
      message: `Excluir o cartão "${card.nome}"? Esta ação não pode ser desfeita.`,
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    setError("");
    try {
      await api.deleteCard(card.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir cartão");
    }
  }

  async function criar(e: React.FormEvent) {
    e.preventDefault();
    setSavingCard(true);
    setError("");
    try {
      await api.createCard({
        nome,
        banco,
        limite: limite.replace(",", ".") || "0",
        fechamento: parseInt(fechamento, 10),
        vencimento: parseInt(vencimento, 10),
      });
      closeCardModal();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setSavingCard(false);
    }
  }

  async function onSaveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editingCardId) return;
    setSavingCard(true);
    setError("");
    try {
      await api.updateCard(editingCardId, {
        nome: nome.trim(),
        banco: banco.trim(),
        limite: limite.replace(/\./g, "").replace(",", ".") || "0",
        fechamento: parseInt(fechamento, 10),
        vencimento: parseInt(vencimento, 10),
      });
      closeCardModal();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSavingCard(false);
    }
  }

  const cardModalOpen = showCreateModal || editingCardId !== null;
  const selectedBank = bancoKey ? bankById(bancoKey) : null;

  useEffect(() => {
    if (!cardModalOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !savingCard) closeCardModal();
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [cardModalOpen, savingCard]);

  return (
    <div className="padded cards-page">
      <header className="cp-header">
        <div className="cp-header-top">
          <h1 className="cp-page-title">Cartões</h1>
          <div className="cp-header-actions">
            <Link to="/cartoes/pessoas" className="cp-btn-secondary">
              👥 Pessoas
            </Link>
            <button type="button" className="cp-btn-primary" onClick={() => openCreateModal()}>
              ＋ Cartão
            </button>
          </div>
        </div>
      </header>

      {error && <p className="error cp-error">{error}</p>}

      <section className="cp-stats-section" aria-label="Resumo dos cartões">
        <div className="cp-stats-grid">
          <div className="cp-stat-card cp-stat-card--highlight">
            <span className="cp-stat-label">Limite total</span>
            <span className="cp-stat-value cp-stat-value--blue">
              {cardsLoading ? "…" : formatBRL(totalLimit.toFixed(2))}
            </span>
          </div>
          <div className="cp-stat-card">
            <span className="cp-stat-label">Usado no mês</span>
            <span className="cp-stat-value cp-stat-value--amber">
              {cardsLoading || usedLoading ? "…" : periodId ? formatBRL(totalUsedMonth.toFixed(2)) : "—"}
            </span>
          </div>
          <div className="cp-stat-card">
            <span className="cp-stat-label">Saldo disponível</span>
            <span className="cp-stat-value cp-stat-value--green">
              {cardsLoading || usedLoading ? "…" : formatBRL(totalAvailable.toFixed(2))}
            </span>
          </div>
          <div className="cp-stat-card">
            <span className="cp-stat-label">Em alerta</span>
            <span className={`cp-stat-value cp-stat-value--muted${cardsInAlert > 0 ? " cp-stat-value--alert-count" : ""}`}>
              {cardsLoading || usedLoading ? "…" : String(cardsInAlert)}
            </span>
          </div>
        </div>
      </section>

      <section className="cp-filters-section" aria-label="Filtros">
        <div className="cp-search-box">
          <span className="cp-search-icon" aria-hidden>
            🔍
          </span>
          <input
            className="cp-search-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nome ou banco…"
            aria-label="Buscar cartão"
          />
        </div>
        <div className="cp-filter-row" role="group" aria-label="Filtrar por banco">
          <button
            type="button"
            className={`cp-filter-chip${activeChip === "all" ? " cp-filter-chip--active" : ""}`}
            onClick={() => setActiveChip("all")}
          >
            Todos
          </button>
          {bankChips.map((bank) => (
            <button
              key={bank}
              type="button"
              className={`cp-filter-chip${activeChip === bank ? " cp-filter-chip--active" : ""}`}
              onClick={() => setActiveChip(bank)}
            >
              {bank}
            </button>
          ))}
          <button
            type="button"
            className={`cp-filter-chip${activeChip === "alert" ? " cp-filter-chip--active" : ""}`}
            onClick={() => setActiveChip("alert")}
          >
            Em alerta
          </button>
        </div>
      </section>

      <div className="cp-sort-row">
        <span className="cp-sort-label">{cardCountLabel(filteredCards.length)}</span>
        <select
          className="cp-sort-select"
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as CardSort)}
          aria-label="Ordenar cartões"
        >
          <option value="usage_desc">Maior uso (%)</option>
          <option value="usage_asc">Menor uso (%)</option>
          <option value="limit_desc">Maior limite</option>
          <option value="name_asc">Nome</option>
        </select>
      </div>

      {cardsLoading || !ready ? (
        <div className="cp-cards-list" aria-label="Carregando cartões">
          {Array.from({ length: 4 }).map((_, idx) => (
            <div key={idx} className="cp-card-item cp-card-item--skeleton">
              <div className="cp-card-stripe" />
              <div className="cp-card-body">
                <span className="cp-card-name">Carregando…</span>
                <div className="cp-progress-track">
                  <div className="cp-progress-fill" style={{ width: "45%" }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : cards.length === 0 ? (
        <div className="cp-empty">
          <p className="muted">Nenhum cartão cadastrado ainda.</p>
        </div>
      ) : filteredCards.length === 0 ? (
        <div className="cp-empty">
          <p className="muted">Nenhum cartão encontrado com os filtros atuais.</p>
          <button type="button" className="cp-btn-secondary" onClick={clearFilters}>
            Limpar filtros
          </button>
        </div>
      ) : (
        <div className="cp-cards-list">
          {filteredCards.map((item) => {
            const tier = usageTier(item.utilization);
            const stripe = stripeByCardId.get(item.card.id) ?? "default";
            const pctWidth = Math.min(100, Math.max(0, item.utilization));
            const paid = item.isPaid;
            return (
              <article
                key={item.card.id}
                className={`cp-card-item cp-card-item--${stripe}${paid ? " cp-card-item--pago" : ""}`}
              >
                <div className="cp-card-stripe" aria-hidden />
                <div className="cp-card-body">
                  <div className="cp-card-top">
                    <div>
                      <div className="cp-card-name">{item.card.nome}</div>
                      <div className="cp-card-bank">
                        {item.card.banco ? `Banco ${item.card.banco}` : "Banco não informado"}
                      </div>
                    </div>
                    {paid ? (
                      <span className="cp-status-badge cp-status-badge--pago">✓ PAGO</span>
                    ) : (
                      <span
                        className={`cp-status-badge${item.risk === "normal" ? " cp-status-badge--normal" : " cp-status-badge--alerta"}`}
                      >
                        {item.risk === "normal" ? "NORMAL" : "ALERTA"}
                      </span>
                    )}
                  </div>
                  {paid && item.paidAt ? (
                    <div className="cp-paid-banner">Paga em {formatPaidAtBR(item.paidAt)}</div>
                  ) : null}
                  <div className="cp-meta-grid">
                    <div className="cp-meta-item">
                      <div className="cp-meta-key">Disponível</div>
                      <div className="cp-meta-val cp-meta-val--green">
                        {usedLoading ? "…" : formatBRL(item.available.toFixed(2))}
                      </div>
                    </div>
                    <div className="cp-meta-item">
                      <div className={`cp-meta-key${paid ? " cp-meta-key--pago" : ""}`}>
                        {paid ? "Valor pago" : "Usado no mês"}
                      </div>
                      <div className={`cp-meta-val${paid ? " cp-meta-val--green" : " cp-meta-val--blue"}`}>
                        {usedLoading ? "…" : periodId ? formatBRL(item.monthUsed.toFixed(2)) : "—"}
                      </div>
                    </div>
                  </div>
                  <div className="cp-usage-row">
                    <span className="cp-usage-label">Uso do limite</span>
                    <span className={`cp-usage-pct cp-usage-pct--${tier}`}>
                      {usedLoading ? "…" : `${item.utilization.toFixed(1).replace(".", ",")}%`}
                    </span>
                  </div>
                  <div className="cp-progress-track">
                    <div
                      className={`cp-progress-fill cp-progress-fill--${tier}`}
                      style={{ width: `${pctWidth}%` }}
                    />
                  </div>
                  <div className="cp-dates-row">
                    {(() => {
                      const close = closingChipParts(item.closingInfo);
                      return (
                        <div className="cp-date-chip">
                          📅 {close.lead ? `${close.lead} ` : ""}
                          <span>{close.highlight}</span>
                          <span className="cp-date-chip-day">· {close.day}</span>
                        </div>
                      );
                    })()}
                    {paid ? (
                      <div className="cp-date-chip cp-date-chip--pago">
                        ✓ <span>Pago</span>
                      </div>
                    ) : (
                      (() => {
                        const due = dueChipParts(item.daysUntilDue);
                        return (
                          <div className="cp-date-chip">
                            ⚠️ {due.lead ? `${due.lead} ` : ""}
                            <span>{due.highlight}</span>
                          </div>
                        );
                      })()
                    )}
                  </div>
                </div>
                <div className="cp-card-actions">
                  <Link className="cp-card-btn" to={`/cartoes/${item.card.id}`}>
                    📋 Ver lançamentos
                  </Link>
                  <button
                    type="button"
                    className="cp-card-btn"
                    onClick={() => openEditModal(item.card)}
                  >
                    ✏️ Editar
                  </button>
                  <button
                    type="button"
                    className="cp-card-btn cp-card-btn--danger"
                    onClick={() => void onDeleteCard(item.card)}
                  >
                    🗑 Excluir
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {cardModalOpen && (
        <div
          className="cp-card-modal-overlay cp-card-modal-overlay--open"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget && !savingCard) closeCardModal();
          }}
        >
          <div
            className="cp-card-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="card-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="cp-card-modal-header">
              <div className="cp-card-modal-title-row">
                <div className="cp-card-modal-icon" aria-hidden>
                  💳
                </div>
                <div id="card-modal-title" className="cp-card-modal-title">
                  {editingCardId ? "Editar cartão" : "Novo cartão"}
                </div>
              </div>
              <button
                type="button"
                className="cp-card-modal-close"
                aria-label="Fechar"
                disabled={savingCard}
                onClick={() => closeCardModal()}
              >
                ✕
              </button>
            </div>
            <form onSubmit={editingCardId ? onSaveEdit : criar} className="cp-card-modal-form">
              <div className="cp-card-modal-body">
                <div className="cp-card-modal-field">
                  <label className="cp-card-modal-label" htmlFor="card-nome">
                    Nome do cartão <span className="cp-card-modal-required">*</span>
                  </label>
                  <input
                    id="card-nome"
                    className="cp-card-modal-input"
                    type="text"
                    value={nome}
                    onChange={(e) => setNome(e.target.value)}
                    placeholder="Ex: Ultravioleta, PDA, Black…"
                    required
                    disabled={savingCard}
                  />
                </div>
                <div className="cp-card-modal-field">
                  <label className="cp-card-modal-label" htmlFor="card-banco">
                    Banco <span className="cp-card-modal-required">*</span>
                  </label>
                  <select
                    id="card-banco"
                    className="cp-card-modal-select"
                    value={bancoKey}
                    onChange={(e) => onBankKeyChange(e.target.value)}
                    required
                    disabled={savingCard}
                  >
                    <option value="" disabled>
                      Selecione o banco…
                    </option>
                    {CARD_BANKS.map((bank) => (
                      <option key={bank.id} value={bank.id}>
                        {bank.label}
                      </option>
                    ))}
                  </select>
                  {selectedBank && (
                    <div className="cp-card-modal-bank-preview">
                      <div
                        className="cp-card-modal-bank-strip"
                        style={{ background: selectedBank.color }}
                        aria-hidden
                      />
                      <div className="cp-card-modal-bank-preview-info">{selectedBank.preview}</div>
                    </div>
                  )}
                </div>
                <div className="cp-card-modal-field">
                  <label className="cp-card-modal-label" htmlFor="card-limite">
                    Limite <span className="cp-card-modal-required">*</span>
                  </label>
                  <div className="cp-card-modal-prefix-wrap">
                    <span className="cp-card-modal-prefix" aria-hidden>
                      R$
                    </span>
                    <input
                      id="card-limite"
                      className="cp-card-modal-input cp-card-modal-input--prefix cp-card-modal-input--mono"
                      type="text"
                      value={limite}
                      onChange={(e) => setLimite(e.target.value)}
                      placeholder="0,00"
                      required
                      disabled={savingCard}
                      inputMode="decimal"
                    />
                  </div>
                </div>
                <div className="cp-card-modal-field-row">
                  <div className="cp-card-modal-field">
                    <label className="cp-card-modal-label" htmlFor="card-fechamento">
                      Fechamento
                    </label>
                    <input
                      id="card-fechamento"
                      className="cp-card-modal-input cp-card-modal-input--mono"
                      type="number"
                      min={1}
                      max={31}
                      placeholder="Dia"
                      value={fechamento}
                      onChange={(e) => setFechamento(e.target.value)}
                      disabled={savingCard}
                      required
                    />
                  </div>
                  <div className="cp-card-modal-field">
                    <label className="cp-card-modal-label" htmlFor="card-vencimento">
                      Vencimento
                    </label>
                    <input
                      id="card-vencimento"
                      className="cp-card-modal-input cp-card-modal-input--mono"
                      type="number"
                      min={1}
                      max={31}
                      placeholder="Dia"
                      value={vencimento}
                      onChange={(e) => setVencimento(e.target.value)}
                      disabled={savingCard}
                      required
                    />
                  </div>
                </div>
                <div className="cp-card-modal-days-preview">
                  <div className="cp-card-modal-day-badge">
                    <div className="cp-card-modal-day-badge-lbl">Fecha em</div>
                    <div className="cp-card-modal-day-badge-val">
                      {fechamento ? `dia ${fechamento}` : "–"}
                    </div>
                  </div>
                  <div className="cp-card-modal-day-badge">
                    <div className="cp-card-modal-day-badge-lbl">Vence em</div>
                    <div className="cp-card-modal-day-badge-val">
                      {vencimento ? `dia ${vencimento}` : "–"}
                    </div>
                  </div>
                </div>
              </div>
              <div className="cp-card-modal-divider" />
              <div className="cp-card-modal-footer">
                <button
                  type="button"
                  className="cp-card-modal-btn-cancel"
                  onClick={() => closeCardModal()}
                  disabled={savingCard}
                >
                  Cancelar
                </button>
                <button type="submit" className="cp-card-modal-btn-save" disabled={savingCard || !bancoKey}>
                  {savingCard ? "Salvando…" : "💾 Salvar cartão"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
