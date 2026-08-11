import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { GoalJarSvg } from "../components/GoalJarSvg";
import { useAppDialog } from "../context/DialogContext";
import { usePeriod } from "../context/PeriodContext";
import { fetchGoalPoolTotals } from "../lib/goalPool";
import type { GoalRow } from "../types";
import { formatBRL } from "../money";

type GoalVariant = "short" | "medium" | "long" | "overdue";

function getGoalProgress(goal: GoalRow) {
  const atual = Number(goal.valor_atual);
  const meta = Number(goal.valor_meta);
  if (!Number.isFinite(atual) || !Number.isFinite(meta) || meta <= 0) return 0;
  return Math.max(0, Math.min(100, (atual / meta) * 100));
}

function getGoalVariant(goal: GoalRow, overdue: boolean): GoalVariant {
  if (overdue) return "overdue";
  if (goal.tipo === "medium" || goal.tipo === "long") return goal.tipo;
  return "short";
}

function formatPct(value: number): string {
  return `${value.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function activeCountLabel(count: number): string {
  return count === 1 ? "1 ativa" : `${count} ativas`;
}

function goalStatusLabel(goal: GoalRow, overdue: boolean): string {
  if (goal.status === "completed") return "● CONCLUÍDA";
  if (overdue) return "● VENCIDA";
  return "● ATIVA";
}

function goalStatusClass(goal: GoalRow, overdue: boolean): string {
  if (goal.status === "completed") return "gp-goal-badge--done";
  if (overdue) return "gp-goal-badge--overdue";
  return "gp-goal-badge--active";
}

function isoToBrDate(iso: string): string {
  if (!iso) return "";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(d.getTime())) return "";
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${d.getFullYear()}`;
}

function formatDateBR(value: string | null): string {
  if (!value) return "Sem prazo";
  return isoToBrDate(value) || value;
}

function formatDateInput(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
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

function todayBrDate(): string {
  return isoToBrDate(new Date().toISOString().slice(0, 10));
}

export function Goals() {
  const { confirm, alert } = useAppDialog();
  const { periodId, currentPeriod, monthLabel } = usePeriod();
  const [goals, setGoals] = useState<GoalRow[]>([]);
  const [error, setError] = useState("");
  const [editingGoalId, setEditingGoalId] = useState<string | null>(null);
  const [nome, setNome] = useState("");
  const [tipo, setTipo] = useState<"short" | "medium" | "long">("short");
  const [meta, setMeta] = useState("");
  const [dataIni, setDataIni] = useState(() => todayBrDate());
  const [dataFim, setDataFim] = useState("");
  const [metasPoolTotal, setMetasPoolTotal] = useState(0);
  const [metasDepositedTotal, setMetasDepositedTotal] = useState(0);
  const [availableForGoals, setAvailableForGoals] = useState(0);

  function parseDecimal(value: string): number {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function isGoalOverdue(goal: GoalRow): boolean {
    if (goal.status === "completed") return false;
    if (goal.status === "expired") return true;
    if (!goal.data_fim) return false;
    const today = new Date().toISOString().slice(0, 10);
    return goal.data_fim < today;
  }

  async function loadPoolSummary() {
    if (!periodId) return;
    try {
      const totals = await fetchGoalPoolTotals(periodId);
      setMetasPoolTotal(totals.poolTotal);
      setMetasDepositedTotal(totals.depositedTotal);
      setAvailableForGoals(totals.available);
    } catch (e) {
      if (import.meta.env.DEV) {
        console.warn("[Goals] falha ao carregar totais do painel:", e);
      }
    }
  }

  async function load() {
    setError("");
    const g = await api.listGoals();
    setGoals(g);
    await loadPoolSummary();
  }

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        await load();
      } catch (e) {
        if (!c) setError(e instanceof Error ? e.message : "Erro");
      }
    })();
    return () => {
      c = true;
    };
  }, [periodId]);

  const periodoLabel = useMemo(
    () => (currentPeriod ? monthLabel(currentPeriod.mes, currentPeriod.ano) : ""),
    [currentPeriod, monthLabel],
  );

  const goalsExecutiveSummary = useMemo(() => {
    const mapped = goals.map((g) => {
      const progress = getGoalProgress(g);
      const overdue = isGoalOverdue(g);
      const variant = getGoalVariant(g, overdue);
      return { goal: g, progress, overdue, variant };
    });
    const active = mapped.filter((item) => !item.overdue && item.goal.status !== "completed").length;
    const completed = mapped.filter((item) => item.goal.status === "completed").length;
    const avgProgress =
      mapped.length === 0 ? 0 : mapped.reduce((acc, item) => acc + item.progress, 0) / mapped.length;
    const ordered = [...mapped].sort((a, b) => {
      if (a.overdue !== b.overdue) return a.overdue ? -1 : 1;
      return b.progress - a.progress;
    });
    return { active, completed, avgProgress, ordered };
  }, [goals]);

  function resetForm() {
    setEditingGoalId(null);
    setNome("");
    setTipo("short");
    setMeta("");
    setDataIni(todayBrDate());
    setDataFim("");
  }

  function edit(goal: GoalRow) {
    setEditingGoalId(goal.id);
    setNome(goal.nome);
    setTipo(goal.tipo as "short" | "medium" | "long");
    setMeta(goal.valor_meta);
    setDataIni(isoToBrDate(goal.data_inicio));
    setDataFim(isoToBrDate(goal.data_fim));
    if (typeof window !== "undefined") {
      window.location.hash = "nova-meta";
    }
  }

  async function submitGoal(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const isoIni = parseBrDateToIso(dataIni);
    const isoFim = dataFim.trim() ? parseBrDateToIso(dataFim) : null;
    if (!isoIni) {
      setError("Data de início inválida. Use dd/mm/aaaa.");
      return;
    }
    if (dataFim.trim() && !isoFim) {
      setError("Data de fim inválida. Use dd/mm/aaaa.");
      return;
    }
    try {
      if (editingGoalId) {
        await api.updateGoal(editingGoalId, {
          nome,
          tipo,
          valor_meta: meta.replace(",", "."),
          data_fim: isoFim,
        });
      } else {
        await api.createGoal({
          nome,
          tipo,
          valor_meta: meta.replace(",", "."),
          data_inicio: isoIni,
          data_fim: isoFim || undefined,
          status: "active",
        });
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    }
  }

  async function remove(id: string) {
    const ok = await confirm({
      title: "Excluir meta",
      message: "Excluir meta?",
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.deleteGoal(id);
      await load();
    } catch (e) {
      await alert(e instanceof Error ? e.message : "Erro");
    }
  }

  return (
    <div className="padded goals-page">
      <header className="gp-header">
        <h1 className="gp-page-title">Metas financeiras</h1>
      </header>

      {error && <p className="error gp-error">{error}</p>}

      <section className="gp-section" aria-label="Painel executivo de metas">
        <div className="gp-section-label">Painel executivo de metas</div>
        <p className="gp-section-sub">
          {periodoLabel
            ? `Dinheiro separado em ${periodoLabel} — cada mês é fechado em si mesmo`
            : "Consolidado do mês selecionado"}
        </p>

        <div className="gp-panel-grid">
          <div className="gp-stat-card">
            <div className={`gp-stat-val ${availableForGoals < 0 ? "gp-stat-val--muted" : "gp-stat-val--green"}`}>
              {formatBRL(availableForGoals)}
            </div>
            <div className="gp-stat-desc">
              Disponível para dividir {periodoLabel ? `em ${periodoLabel}` : "no mês"}
            </div>
          </div>
          <div className="gp-stat-card">
            <div className="gp-stat-val gp-stat-val--blue">{formatBRL(metasPoolTotal)}</div>
            <div className="gp-stat-desc">Lançado em despesas fixas (Metas) no mês</div>
          </div>
          <div className="gp-stat-card gp-stat-card--wide">
            <div className="gp-stat-val">{formatBRL(metasDepositedTotal)}</div>
            <div className="gp-stat-desc">Guardado nos cofres neste mês</div>
          </div>
        </div>

        <div className="gp-mini-row">
          <div className="gp-mini-card">
            <div className="gp-mini-label">Ativas</div>
            <div className="gp-mini-val gp-mini-val--accent">{goalsExecutiveSummary.active}</div>
          </div>
          <div className="gp-mini-card">
            <div className="gp-mini-label">Concluídas</div>
            <div className="gp-mini-val gp-mini-val--muted">{goalsExecutiveSummary.completed}</div>
          </div>
          <div className="gp-mini-card">
            <div className="gp-mini-label">Progresso</div>
            <div className="gp-mini-val gp-mini-val--green gp-mini-val--pct">
              {formatPct(goalsExecutiveSummary.avgProgress)}
            </div>
          </div>
        </div>
      </section>

      <div className="gp-divider gp-divider--before-main" />

      <div className="gp-main">
        <section id="nova-meta" className="gp-form-section">
        <div className="gp-form-card">
          <div className="gp-form-title">
            <div className="gp-form-title-icon" aria-hidden="true">
              🎯
            </div>
            {editingGoalId ? "Editar meta" : "Criar nova meta"}
          </div>

          <form onSubmit={submitGoal}>
            <div className="gp-form-group gp-form-group--wide">
              <label className="gp-form-label" htmlFor="goal-nome">
                Nome da meta
              </label>
              <input
                id="goal-nome"
                className="gp-form-input"
                type="text"
                placeholder="Ex: Viagem, Carro, Reserva…"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                required
              />
            </div>

            <div className="gp-form-row">
              <div className="gp-form-group">
                <label className="gp-form-label" htmlFor="goal-tipo">
                  Tipo
                </label>
                <select
                  id="goal-tipo"
                  className="gp-form-select"
                  value={tipo}
                  onChange={(e) => setTipo(e.target.value as typeof tipo)}
                >
                  <option value="short">Curto prazo</option>
                  <option value="medium">Médio prazo</option>
                  <option value="long">Longo prazo</option>
                </select>
              </div>
              <div className="gp-form-group">
                <label className="gp-form-label" htmlFor="goal-meta">
                  Valor objetivo
                </label>
                <input
                  id="goal-meta"
                  className="gp-form-input"
                  type="text"
                  placeholder="R$ 0,00"
                  value={meta}
                  onChange={(e) => setMeta(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="gp-form-row">
              <div className="gp-form-group">
                <label className="gp-form-label" htmlFor="goal-ini">
                  Início
                </label>
                <input
                  id="goal-ini"
                  className="gp-form-input"
                  type="text"
                  value={dataIni}
                  onChange={(e) => setDataIni(formatDateInput(e.target.value))}
                  placeholder="dd/mm/aaaa"
                  inputMode="numeric"
                  maxLength={10}
                  required
                />
              </div>
              <div className="gp-form-group">
                <label className="gp-form-label" htmlFor="goal-fim">
                  Fim
                </label>
                <input
                  id="goal-fim"
                  className="gp-form-input"
                  type="text"
                  value={dataFim}
                  onChange={(e) => setDataFim(formatDateInput(e.target.value))}
                  placeholder="dd/mm/aaaa"
                  inputMode="numeric"
                  maxLength={10}
                />
              </div>
            </div>

            <button type="submit" className="gp-btn-criar">
              {editingGoalId ? "Salvar alterações" : "Criar meta"}
            </button>
            {editingGoalId && (
              <button type="button" className="gp-btn-cancel" onClick={resetForm}>
                Cancelar edição
              </button>
            )}
          </form>
        </div>
        </section>

        <div className="gp-divider gp-divider--in-main" />

        <section className="gp-goals-section">
        <div className="gp-goals-header">
          <span className="gp-goals-title">Suas metas</span>
          <span className="gp-goals-count">{activeCountLabel(goalsExecutiveSummary.active)}</span>
        </div>

        {goals.length === 0 ? (
          <p className="gp-empty">Nenhuma meta ainda.</p>
        ) : (
          <div className="gp-goals-list">
            {goalsExecutiveSummary.ordered.map(({ goal: g, progress, overdue, variant }) => {
            const remaining = Math.max(0, parseDecimal(g.valor_meta) - parseDecimal(g.valor_atual));
            const pctLabel = formatPct(progress);

            return (
              <article key={g.id} className={`gp-goal-card gp-goal-card--${variant}`}>
                <div className="gp-goal-stripe" />
                <div className="gp-goal-body">
                  <div className="gp-goal-top">
                    <Link to={`/metas/${g.id}`} className="gp-goal-name">
                      {g.nome}
                    </Link>
                    <span className={`gp-goal-badge ${goalStatusClass(g, overdue)}`}>
                      {goalStatusLabel(g, overdue)}
                    </span>
                  </div>

                  <Link to={`/metas/${g.id}`} className="gp-goal-progress-row">
                    <div className="gp-jar-wrap">
                      <GoalJarSvg progress={progress} id={g.id} variant={variant} />
                      <div className="gp-jar-pct">{pctLabel}</div>
                    </div>
                    <div className="gp-goal-meta">
                      <div className="gp-goal-amount">
                        {formatBRL(g.valor_atual)} <span>/ {formatBRL(g.valor_meta)}</span>
                      </div>
                      <div className="gp-goal-dates">
                        {formatDateBR(g.data_inicio)} → {formatDateBR(g.data_fim)}
                      </div>
                      {remaining > 0 && g.status !== "completed" && (
                        <div className="gp-goal-remaining">Faltam {formatBRL(remaining)}</div>
                      )}
                    </div>
                  </Link>

                  <div className="gp-goal-bar-row">
                    <div className="gp-bar-track">
                      <div className="gp-bar-fill" style={{ width: `${progress}%` }} />
                    </div>
                    <span className="gp-bar-remaining">{pctLabel}</span>
                  </div>

                  <div className="gp-goal-actions">
                    <button type="button" className="gp-btn-goal gp-btn-edit" onClick={() => edit(g)}>
                      ✏️ Editar
                    </button>
                    <button type="button" className="gp-btn-goal gp-btn-del" onClick={() => remove(g.id)}>
                      🗑 Excluir
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
          </div>
        )}
      </section>
      </div>
    </div>
  );
}
