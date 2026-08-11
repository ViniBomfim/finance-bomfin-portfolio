import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAppDialog } from "../context/DialogContext";
import { formatCompactBRL } from "../money";
import type { TripRow, TripStatus } from "../types";

const STATUS_LABEL: Record<TripStatus, string> = {
  planning: "Planejada",
  ongoing: "Em andamento",
  closed: "Encerrada",
};

type FilterChip = "all" | TripStatus;

const FILTERS: { id: FilterChip; label: string }[] = [
  { id: "all", label: "Todas" },
  { id: "planning", label: "Planejadas" },
  { id: "ongoing", label: "Em andamento" },
  { id: "closed", label: "Encerradas" },
];

const CURRENCIES = [
  { value: "BRL", label: "🇧🇷 BRL – Real" },
  { value: "USD", label: "🇺🇸 USD – Dólar" },
  { value: "EUR", label: "🇪🇺 EUR – Euro" },
  { value: "ARS", label: "🇦🇷 ARS – Peso" },
];

const AVATAR_GRADIENTS = [
  "linear-gradient(135deg, #3b82f6, #22d3ee)",
  "linear-gradient(135deg, #f43f5e, #a855f7)",
  "linear-gradient(135deg, #f59e0b, #ef4444)",
  "linear-gradient(135deg, #22c55e, #16a34a)",
  "linear-gradient(135deg, #8b5cf6, #6366f1)",
];

function formatDateBR(value: string | null): string {
  if (!value) return "—";
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("pt-BR");
}

function formatDateShort(value: string | null): string {
  if (!value) return "—";
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}`;
}

function formatDateRange(start: string | null, end: string | null): string {
  if (!start && !end) return "Datas não definidas";
  if (start && end) {
    const endFull = formatDateBR(end);
    return `${formatDateShort(start)} → ${endFull}`;
  }
  if (start) return `A partir de ${formatDateBR(start)}`;
  return `Até ${formatDateBR(end)}`;
}

function normalizeDecimal(value: string): string {
  return value.trim().replace(",", ".");
}

function parseBrDateToIso(value: string): string | null {
  const clean = value.trim();
  if (!clean) return null;
  const match = clean.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!match) return null;
  const [, dd, mm, yyyy] = match;
  const iso = `${yyyy}-${mm}-${dd}`;
  const date = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(date.getTime())) return null;
  if (
    date.getFullYear() !== Number(yyyy) ||
    date.getMonth() + 1 !== Number(mm) ||
    date.getDate() !== Number(dd)
  ) {
    return null;
  }
  return iso;
}

function formatDateInput(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

function daysBetween(start: string | null, end: string | null): number | null {
  if (!start || !end) return null;
  const a = new Date(`${start}T00:00:00`);
  const b = new Date(`${end}T00:00:00`);
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return null;
  const ms = b.getTime() - a.getTime();
  return Math.max(1, Math.round(ms / 86400000) + 1);
}

function daysUntil(start: string | null): number | null {
  if (!start) return null;
  const a = new Date(`${start}T00:00:00`);
  if (Number.isNaN(a.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const ms = a.getTime() - today.getTime();
  return Math.ceil(ms / 86400000);
}

function participantInitials(nome: string): string {
  const parts = nome.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase();
}

function budgetTone(pct: number): "ok" | "warn" | "over" {
  if (pct > 100) return "over";
  if (pct >= 80) return "warn";
  return "ok";
}

export function Trips() {
  const { confirm, alert } = useAppDialog();
  const [trips, setTrips] = useState<TripRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<FilterChip>("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const [nome, setNome] = useState("");
  const [destino, setDestino] = useState("");
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");
  const [orcamento, setOrcamento] = useState("");
  const [moeda, setMoeda] = useState("BRL");

  async function load() {
    try {
      setLoading(true);
      const t = await api.listTrips();
      setTrips(t);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar viagens");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!modalOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !saving) {
        setModalOpen(false);
        resetForm();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modalOpen, saving]);

  const stats = useMemo(() => {
    const total = trips.length;
    const ongoing = trips.filter((t) => t.status === "ongoing").length;
    const planning = trips.filter((t) => t.status === "planning").length;
    const closed = trips.filter((t) => t.status === "closed").length;
    return { total, ongoing, planning, closed };
  }, [trips]);

  const filtered = useMemo(() => {
    if (filter === "all") return trips;
    return trips.filter((t) => t.status === filter);
  }, [trips, filter]);

  function resetForm() {
    setNome("");
    setDestino("");
    setDataInicio("");
    setDataFim("");
    setOrcamento("");
    setMoeda("BRL");
  }

  function openModal() {
    setError("");
    resetForm();
    setModalOpen(true);
  }

  function closeModal() {
    if (saving) return;
    setModalOpen(false);
    resetForm();
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!nome.trim()) {
      setError("Informe um nome para a viagem.");
      return;
    }
    if (!destino.trim()) {
      setError("Informe o destino da viagem.");
      return;
    }
    if (!dataInicio || !dataFim) {
      setError("Informe as datas de início e fim da viagem.");
      return;
    }
    const dataInicioIso = parseBrDateToIso(dataInicio);
    const dataFimIso = parseBrDateToIso(dataFim);
    if (!dataInicioIso || !dataFimIso) {
      setError("Use o formato de data dia/mês/ano (dd/mm/aaaa).");
      return;
    }
    if (new Date(`${dataFimIso}T00:00:00`) < new Date(`${dataInicioIso}T00:00:00`)) {
      setError("A data de fim não pode ser anterior à data de início.");
      return;
    }
    if (!orcamento.trim()) {
      setError("Informe o orçamento da viagem.");
      return;
    }
    const normalizedBudget = normalizeDecimal(orcamento);
    const budgetNumber = parseFloat(normalizedBudget);
    if (!Number.isFinite(budgetNumber) || budgetNumber <= 0) {
      setError("Informe um orçamento válido maior que zero.");
      return;
    }
    setSaving(true);
    try {
      await api.createTrip({
        nome: nome.trim(),
        destino: destino.trim(),
        data_inicio: dataInicioIso,
        data_fim: dataFimIso,
        orcamento_total: normalizedBudget,
        moeda_base: moeda,
        participant_spender_ids: [],
      });
      resetForm();
      setModalOpen(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar viagem");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    const ok = await confirm({
      title: "Excluir viagem",
      message: "Excluir esta viagem? Todos os gastos vão junto.",
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.deleteTrip(id);
      await load();
    } catch (err) {
      await alert(err instanceof Error ? err.message : "Erro ao excluir");
    }
  }

  return (
    <div className="padded trips-page">
      <header className="tp-header">
        <h1 className="tp-page-title">✈️ Viagens</h1>
        <button type="button" className="tp-btn-nova" onClick={openModal}>
          ＋ Nova viagem
        </button>
      </header>

      {error && !modalOpen && (
        <p className="error tp-error" role="alert">
          {error}
        </p>
      )}

      <section className="tp-stats" aria-label="Resumo das viagens">
        <div className="tp-stat-card tp-stat-card--muted">
          <span className="tp-stat-lbl">Total de viagens</span>
          <span className="tp-stat-val tp-stat-val--muted">{loading ? "…" : stats.total}</span>
        </div>
        <div className="tp-stat-card tp-stat-card--green">
          <span className="tp-stat-lbl">Em andamento</span>
          <span className="tp-stat-val tp-stat-val--green">{loading ? "…" : stats.ongoing}</span>
        </div>
        <div className="tp-stat-card tp-stat-card--blue">
          <span className="tp-stat-lbl">Planejadas</span>
          <span className="tp-stat-val tp-stat-val--blue">{loading ? "…" : stats.planning}</span>
        </div>
        <div className="tp-stat-card tp-stat-card--gray">
          <span className="tp-stat-lbl">Encerradas</span>
          <span className="tp-stat-val tp-stat-val--gray">{loading ? "…" : stats.closed}</span>
        </div>
      </section>

      <section className="tp-filters" aria-label="Filtros">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            className={`tp-chip${filter === f.id ? " tp-chip--active" : ""}`}
            onClick={() => setFilter(f.id)}
          >
            {f.label}
          </button>
        ))}
      </section>

      {loading ? (
        <p className="muted">Carregando…</p>
      ) : trips.length === 0 ? (
        <button type="button" className="tp-empty-card" onClick={openModal}>
          <span className="tp-empty-icon" aria-hidden>
            ✈️
          </span>
          <div className="tp-empty-title">Nova viagem</div>
          <div className="tp-empty-sub">Clique para planejar sua próxima aventura</div>
          <span className="tp-btn-add-empty">＋ Criar viagem</span>
        </button>
      ) : filtered.length === 0 ? (
        <div className="tp-empty-filtered">
          <p className="muted">Nenhuma viagem neste filtro.</p>
          <button type="button" className="tp-chip tp-chip--active" onClick={() => setFilter("all")}>
            Ver todas
          </button>
        </div>
      ) : (
        <div className="tp-grid">
          {filtered.map((trip) => {
            const orcado = trip.orcamento_total ? parseFloat(trip.orcamento_total) : 0;
            const gasto = parseFloat(trip.total_gasto || "0");
            const pctRaw = orcado > 0 ? (gasto / orcado) * 100 : 0;
            const pctBar = orcado > 0 ? Math.min(100, pctRaw) : 0;
            const tone = budgetTone(pctRaw);
            const duration = daysBetween(trip.data_inicio, trip.data_fim);
            const until = daysUntil(trip.data_inicio);
            const showDaysLeft =
              trip.status === "planning" && until != null && until > 0;
            const people = trip.participants ?? [];
            const shown = people.slice(0, 4);

            return (
              <article key={trip.id} className={`tp-card tp-card--${trip.status}`}>
                <div className="tp-stripe" aria-hidden />
                <div className="tp-body">
                  <div className="tp-top">
                    <h2 className="tp-name">{trip.nome}</h2>
                    <span className={`tp-status tp-status--${trip.status}`}>
                      {STATUS_LABEL[trip.status]}
                    </span>
                  </div>
                  <div className="tp-dest">
                    <span>🗺️ {trip.destino || "Sem destino"}</span>
                    <span className="tp-dest-sep">·</span>
                    <span className="tp-dest-dates">
                      {formatDateRange(trip.data_inicio, trip.data_fim)}
                    </span>
                  </div>

                  {orcado > 0 && (
                    <div className="tp-orc">
                      <div className="tp-orc-header">
                        <span>Orçamento usado</span>
                        <span className={`tp-orc-pct tp-orc-pct--${tone}`}>
                          {pctRaw.toLocaleString("pt-BR", {
                            maximumFractionDigits: pctRaw < 10 ? 1 : 0,
                          })}
                          %{tone === "over" ? " ⚠" : ""}
                        </span>
                      </div>
                      <div className="tp-orc-bar">
                        <div
                          className={`tp-orc-fill tp-orc-fill--${tone}`}
                          style={{ width: `${pctBar}%` }}
                        />
                      </div>
                    </div>
                  )}

                  <div className="tp-mini-stats">
                    <div className="tp-ms">
                      <div className="tp-ms-lbl">Total gasto</div>
                      <div
                        className={`tp-ms-val${tone === "over" ? " tp-ms-val--over" : " tp-ms-val--accent"}`}
                      >
                        {formatCompactBRL(gasto)}
                      </div>
                    </div>
                    <div className="tp-ms">
                      <div className="tp-ms-lbl">Orçamento</div>
                      <div className="tp-ms-val">
                        {orcado > 0 ? formatCompactBRL(orcado) : "—"}
                      </div>
                    </div>
                    <div className="tp-ms">
                      <div className="tp-ms-lbl">{showDaysLeft ? "Dias rest." : "Duração"}</div>
                      <div className={`tp-ms-val${showDaysLeft ? " tp-ms-val--amber" : ""}`}>
                        {showDaysLeft
                          ? `${until}d`
                          : duration != null
                            ? `${duration} dia${duration === 1 ? "" : "s"}`
                            : "—"}
                      </div>
                    </div>
                  </div>

                  <div className="tp-people">
                    {shown.map((p, i) => (
                      <div
                        key={p.spender_id}
                        className="tp-av"
                        style={{ background: AVATAR_GRADIENTS[i % AVATAR_GRADIENTS.length] }}
                        title={p.spender_nome}
                      >
                        {participantInitials(p.spender_nome)}
                      </div>
                    ))}
                    <span className="tp-people-lbl">
                      {people.length === 0
                        ? "Sem participantes"
                        : `${people.length} participante${people.length === 1 ? "" : "s"}`}
                    </span>
                  </div>

                  <div className="tp-actions">
                    <Link to={`/viagens/${trip.id}`} className="tp-btn-abrir">
                      {trip.status === "closed" ? "Ver detalhes →" : "Abrir viagem →"}
                    </Link>
                    <button
                      type="button"
                      className="tp-btn-del"
                      aria-label="Excluir viagem"
                      onClick={() => void handleDelete(trip.id)}
                    >
                      🗑
                    </button>
                  </div>
                </div>
              </article>
            );
          })}

          <button type="button" className="tp-empty-card" onClick={openModal}>
            <span className="tp-empty-icon" aria-hidden>
              ✈️
            </span>
            <div className="tp-empty-title">Nova viagem</div>
            <div className="tp-empty-sub">Clique para planejar sua próxima aventura</div>
            <span className="tp-btn-add-empty">＋ Criar viagem</span>
          </button>
        </div>
      )}

      {modalOpen && (
        <div
          className="tp-modal-overlay tp-modal-overlay--open"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget && !saving) closeModal();
          }}
        >
          <div
            className="tp-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="trip-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="tp-modal-header">
              <div className="tp-modal-title-row">
                <div className="tp-modal-icon" aria-hidden>
                  ✈️
                </div>
                <div id="trip-modal-title" className="tp-modal-title">
                  Nova viagem
                </div>
              </div>
              <button
                type="button"
                className="tp-modal-close"
                aria-label="Fechar"
                disabled={saving}
                onClick={closeModal}
              >
                ✕
              </button>
            </div>
            <form onSubmit={(e) => void handleCreate(e)} className="tp-modal-form">
              <div className="tp-modal-body">
                {error && (
                  <p className="error tp-error" role="alert">
                    {error}
                  </p>
                )}
                <div className="tp-field">
                  <label className="tp-label" htmlFor="trip-nome">
                    Nome da viagem
                  </label>
                  <input
                    id="trip-nome"
                    className="tp-input"
                    type="text"
                    value={nome}
                    onChange={(e) => setNome(e.target.value)}
                    placeholder="Ex: Férias Bahia 2026…"
                    required
                    disabled={saving}
                  />
                </div>
                <div className="tp-field">
                  <label className="tp-label" htmlFor="trip-destino">
                    Destino
                  </label>
                  <input
                    id="trip-destino"
                    className="tp-input"
                    type="text"
                    value={destino}
                    onChange={(e) => setDestino(e.target.value)}
                    placeholder="Ex: Salvador, Itacaré…"
                    required
                    disabled={saving}
                  />
                </div>
                <div className="tp-form-row">
                  <div className="tp-field">
                    <label className="tp-label" htmlFor="trip-ini">
                      Início
                    </label>
                    <input
                      id="trip-ini"
                      className="tp-input"
                      type="text"
                      value={dataInicio}
                      onChange={(e) => setDataInicio(formatDateInput(e.target.value))}
                      placeholder="dd/mm/aaaa"
                      inputMode="numeric"
                      maxLength={10}
                      required
                      disabled={saving}
                    />
                  </div>
                  <div className="tp-field">
                    <label className="tp-label" htmlFor="trip-fim">
                      Fim
                    </label>
                    <input
                      id="trip-fim"
                      className="tp-input"
                      type="text"
                      value={dataFim}
                      onChange={(e) => setDataFim(formatDateInput(e.target.value))}
                      placeholder="dd/mm/aaaa"
                      inputMode="numeric"
                      maxLength={10}
                      required
                      disabled={saving}
                    />
                  </div>
                </div>
                <div className="tp-form-row">
                  <div className="tp-field">
                    <label className="tp-label" htmlFor="trip-budget">
                      Orçamento total
                    </label>
                    <div className="tp-prefix-wrap">
                      <span className="tp-prefix">R$</span>
                      <input
                        id="trip-budget"
                        className="tp-input tp-input--pfx"
                        type="text"
                        inputMode="decimal"
                        value={orcamento}
                        onChange={(e) => setOrcamento(e.target.value)}
                        placeholder="0,00"
                        required
                        disabled={saving}
                      />
                    </div>
                  </div>
                  <div className="tp-field">
                    <label className="tp-label" htmlFor="trip-moeda">
                      Moeda base
                    </label>
                    <select
                      id="trip-moeda"
                      className="tp-select"
                      value={moeda}
                      onChange={(e) => setMoeda(e.target.value)}
                      disabled={saving}
                    >
                      {CURRENCIES.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <p className="tp-hint">
                  👤 Você poderá adicionar participantes depois na aba Participantes.
                </p>
              </div>
              <div className="tp-modal-footer">
                <button type="submit" className="tp-btn-save" disabled={saving}>
                  {saving ? "Salvando…" : "✈️ Criar viagem"}
                </button>
                <button
                  type="button"
                  className="tp-btn-cancel"
                  disabled={saving}
                  onClick={closeModal}
                >
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
