import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { GoalJarSvg } from "../components/GoalJarSvg";
import { useAppDialog } from "../context/DialogContext";
import { usePeriod } from "../context/PeriodContext";
import { fetchGoalPoolTotals } from "../lib/goalPool";
import { formatBRL } from "../money";
import type { Category, GoalRow, Period } from "../types";

type Tx = {
  id: string;
  tipo: string;
  valor: string;
  descricao: string | null;
  data: string;
  income_id?: string | null;
};

type GoalVariant = "short" | "medium" | "long" | "overdue";

function formatPct(value: number): string {
  return `${value.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function isoToBrDate(iso: string): string {
  if (!iso) return "";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(d.getTime())) return "";
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${d.getFullYear()}`;
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

function periodPrefix(period: Period | null): string {
  return period ? `${period.ano}-${String(period.mes).padStart(2, "0")}` : "";
}

/** Movimentações pertencem ao mês selecionado, então o padrão é hoje só quando cai nele. */
function defaultDateForPeriod(period: Period | null): string {
  const today = new Date();
  if (!period) return todayBrDate();
  if (period.ano === today.getFullYear() && period.mes === today.getMonth() + 1) {
    return todayBrDate();
  }
  return isoToBrDate(`${periodPrefix(period)}-01`);
}

function formatDateBR(value: string | null): string {
  if (!value) return "Sem prazo";
  return isoToBrDate(value) || value;
}

function goalTipoLabel(tipo: string): string {
  if (tipo === "medium") return "Médio prazo";
  if (tipo === "long") return "Longo prazo";
  return "Curto prazo";
}

function goalStatusLabel(goal: GoalRow, overdue: boolean): string {
  if (goal.status === "completed") return "● Concluída";
  if (overdue) return "● Vencida";
  return "● Ativa";
}

function goalStatusClass(goal: GoalRow, overdue: boolean): string {
  if (goal.status === "completed") return "gd-status-pill--done";
  if (overdue) return "gd-status-pill--overdue";
  return "gd-status-pill--active";
}

function getGoalVariant(goal: GoalRow, overdue: boolean): GoalVariant {
  if (overdue) return "overdue";
  if (goal.tipo === "medium" || goal.tipo === "long") return goal.tipo;
  return "short";
}

function parseDecimal(value: string): number {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function daysBetween(from: Date, to: Date): number {
  const ms = to.getTime() - from.getTime();
  return Math.max(0, Math.floor(ms / (1000 * 60 * 60 * 24)));
}

function computeRitmo(goal: GoalRow, valorAtual: number, valorMeta: number) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = new Date(`${goal.data_inicio.slice(0, 10)}T00:00:00`);
  const diasDecorridos = Math.max(1, daysBetween(start, today));
  const remaining = Math.max(0, valorMeta - valorAtual);
  let diasRestantes: number | null = null;
  let ritmoNecessario: number | null = null;

  if (goal.data_fim) {
    const end = new Date(`${goal.data_fim.slice(0, 10)}T00:00:00`);
    diasRestantes = daysBetween(today, end);
    if (diasRestantes > 0 && remaining > 0 && goal.status !== "completed") {
      ritmoNecessario = remaining / diasRestantes;
    }
  }

  return {
    diasRestantes,
    ritmoNecessario,
    ritmoAtual: valorAtual / diasDecorridos,
    remaining,
  };
}

function isGoalOverdue(goalValue: GoalRow | null): boolean {
  if (!goalValue) return false;
  if (goalValue.status === "completed") return false;
  if (goalValue.status === "expired") return true;
  if (!goalValue.data_fim) return false;
  const today = new Date().toISOString().slice(0, 10);
  return goalValue.data_fim < today;
}

function txTipoLabel(tipo: string, incomeId?: string | null): string {
  if (tipo === "deposit") return "⬆️ Depósito";
  if (incomeId) return "⬇️ Retirada · 💰 Receita";
  return "⬇️ Retirada";
}

function periodLabelFromBrDate(
  brDate: string,
  monthLabel: (mes: number, ano: number) => string,
): string {
  const iso = parseBrDateToIso(brDate);
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00`);
  return monthLabel(d.getMonth() + 1, d.getFullYear());
}

export function GoalDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { confirm } = useAppDialog();
  const { periodId, currentPeriod, monthLabel } = usePeriod();
  const [goal, setGoal] = useState<GoalRow | null>(null);
  const [progress, setProgress] = useState<{
    progress_percent: number;
    tipo: "short" | "medium" | "long";
    valor_atual: string;
    valor_meta: string;
  } | null>(null);
  const [txs, setTxs] = useState<Tx[]>([]);
  const [error, setError] = useState("");
  const [valor, setValor] = useState("");
  const [observacao, setObservacao] = useState("");
  const [tipo, setTipo] = useState<"deposit" | "withdraw">("deposit");
  const [data, setData] = useState(() => todayBrDate());
  const periodoLabel = currentPeriod ? monthLabel(currentPeriod.mes, currentPeriod.ano) : "";
  const [launchAsIncome, setLaunchAsIncome] = useState(false);
  const [categoriaId, setCategoriaId] = useState("");
  const [incomeCategories, setIncomeCategories] = useState<Category[]>([]);
  const [metasPoolTotal, setMetasPoolTotal] = useState(0);
  const [metasDepositedTotal, setMetasDepositedTotal] = useState(0);
  const [availableForGoals, setAvailableForGoals] = useState(0);
  const [saving, setSaving] = useState(false);
  const [deletingTxId, setDeletingTxId] = useState<string | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editNome, setEditNome] = useState("");
  const [editTipo, setEditTipo] = useState<"short" | "medium" | "long">("short");
  const [editMeta, setEditMeta] = useState("");
  const [editDataFim, setEditDataFim] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [poolError, setPoolError] = useState("");

  async function loadPoolSummary() {
    if (!periodId) return;
    try {
      const totals = await fetchGoalPoolTotals(periodId);
      setMetasPoolTotal(totals.poolTotal);
      setMetasDepositedTotal(totals.depositedTotal);
      setAvailableForGoals(totals.available);
      setPoolError("");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erro ao carregar painel de metas";
      setPoolError(msg);
      if (import.meta.env.DEV) {
        console.warn("[GoalDetail] pool-summary failed:", msg);
      }
    }
  }

  async function loadCore() {
    if (!id) return;
    const [g, p, t] = await Promise.all([
      api.getGoal(id),
      api.goalProgress(id),
      api.listGoalTransactions(id) as Promise<Tx[]>,
    ]);
    setGoal(g);
    setProgress({
      progress_percent: p.progress_percent,
      tipo: p.tipo,
      valor_atual: p.valor_atual,
      valor_meta: p.valor_meta,
    });
    setTxs(t);
  }

  async function load() {
    await loadCore();
    await loadPoolSummary();
  }

  useEffect(() => {
    if (!id) return;
    let c = false;
    (async () => {
      try {
        await loadCore();
      } catch (e) {
        if (!c) setError(e instanceof Error ? e.message : "Erro");
      }
      if (!c) void loadPoolSummary();
    })();
    return () => {
      c = true;
    };
  }, [id, periodId]);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const cats = await api.categories("income");
        if (!c) {
          setIncomeCategories(cats);
          setCategoriaId((prev) => prev || cats[0]?.id || "");
        }
      } catch {
        /* categories optional until withdraw-as-income */
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  useEffect(() => {
    setData(defaultDateForPeriod(currentPeriod));
  }, [currentPeriod]);

  function handleSetTipo(next: "deposit" | "withdraw") {
    setTipo(next);
    if (next === "deposit") {
      setLaunchAsIncome(false);
    }
  }

  const withdrawPeriodLabel = useMemo(
    () => periodLabelFromBrDate(data, monthLabel),
    [data, monthLabel],
  );

  const overdue = isGoalOverdue(goal);
  const variant = goal ? getGoalVariant(goal, overdue) : "short";
  const pct = progress?.progress_percent ?? 0;

  const ritmo = useMemo(() => {
    if (!goal || !progress) {
      return { diasRestantes: null, ritmoNecessario: null, ritmoAtual: 0, remaining: 0 };
    }
    return computeRitmo(goal, parseDecimal(progress.valor_atual), parseDecimal(progress.valor_meta));
  }, [goal, progress]);

  function openEditModal() {
    if (!goal) return;
    setEditNome(goal.nome);
    setEditTipo(goal.tipo as "short" | "medium" | "long");
    setEditMeta(goal.valor_meta);
    setEditDataFim(isoToBrDate(goal.data_fim ?? ""));
    setShowEditModal(true);
  }

  async function onEditSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!id) return;
    const isoFim = editDataFim.trim() ? parseBrDateToIso(editDataFim) : null;
    if (editDataFim.trim() && !isoFim) {
      setError("Data de fim inválida. Use dd/mm/aaaa.");
      return;
    }
    setEditSaving(true);
    setError("");
    try {
      await api.updateGoal(id, {
        nome: editNome,
        tipo: editTipo,
        valor_meta: editMeta.replace(",", "."),
        data_fim: isoFim,
      });
      setShowEditModal(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar meta");
    } finally {
      setEditSaving(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!id) return;
    const isoData = parseBrDateToIso(data);
    if (!isoData) {
      setError("Data inválida. Use dd/mm/aaaa.");
      return;
    }
    const prefix = periodPrefix(currentPeriod);
    if (prefix && !isoData.startsWith(prefix)) {
      setError(`A data precisa estar em ${periodoLabel}, o mês selecionado no topo da tela.`);
      return;
    }
    const movementValue = parseDecimal(valor.replace(",", "."));
    if (movementValue <= 0) {
      setError("Informe um valor válido maior que zero.");
      return;
    }
    if (tipo === "deposit" && movementValue - availableForGoals > 0.001) {
      setError(
        `Saldo insuficiente para depósito. Disponível em ${periodoLabel}: ${formatBRL(availableForGoals)}.`,
      );
      return;
    }
    if (tipo === "withdraw" && launchAsIncome && !categoriaId) {
      setError("Selecione a categoria da receita.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const body: Record<string, string | boolean | undefined> = {
        tipo,
        valor: valor.replace(",", "."),
        data: isoData,
        descricao: observacao.trim() || undefined,
      };
      if (tipo === "withdraw" && launchAsIncome) {
        body.launch_as_income = true;
        body.categoria_id = categoriaId;
      }
      await api.addGoalTransaction(id, body);
      setValor("");
      setObservacao("");
      setLaunchAsIncome(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setSaving(false);
    }
  }

  async function removeTx(tx: Tx) {
    if (!id) return;
    const ok = await confirm({
      title: "Excluir movimentação",
      message: "Excluir esta movimentação? O saldo da meta será revertido.",
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    setDeletingTxId(tx.id);
    setError("");
    try {
      await api.deleteGoalTransaction(id, tx.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir movimentação");
    } finally {
      setDeletingTxId(null);
    }
  }

  if (!id) return null;

  return (
    <div className="padded goal-detail-page">
      <header className="gd-topbar">
        <div className="gd-topbar-left">
          <button type="button" className="gd-btn-back" onClick={() => navigate("/metas")}>
            ← Metas
          </button>
          <h1 className="gd-topbar-title">{goal?.nome ?? "Meta"}</h1>
        </div>
        {goal && (
          <div className="gd-topbar-right">
            <span className={`gd-status-pill ${goalStatusClass(goal, overdue)}`}>
              {goalStatusLabel(goal, overdue)}
            </span>
            <button type="button" className="gd-btn-edit" onClick={openEditModal}>
              ✏️ Editar
            </button>
          </div>
        )}
      </header>

      <div className="gd-content">
        {error && <p className="error gd-error">{error}</p>}

        {goal && progress && (
          <>
            <article className={`gd-hero-card gd-hero-card--${variant}`}>
              <div className="gd-hero-stripe" />
              <div className="gd-hero-body">
                <div className="gd-jar-col">
                  <div className="gd-jar-scale">
                    <GoalJarSvg progress={pct} id={id} variant={variant} />
                  </div>
                  <div className="gd-jar-pct">{formatPct(pct)}</div>
                </div>

                <div className="gd-hero-info">
                  <div className="gd-hero-name">{goal.nome}</div>
                  <div className="gd-hero-dates">
                    <span>
                      📅 Início: <strong>{formatDateBR(goal.data_inicio)}</strong>
                    </span>
                    <span>
                      🏁 Fim: <strong>{formatDateBR(goal.data_fim)}</strong>
                    </span>
                    <span>📋 {goalTipoLabel(goal.tipo)}</span>
                  </div>
                  <div className="gd-progress-section">
                    <div className="gd-progress-header">
                      <span className="gd-progress-lbl">Progresso</span>
                      <span className="gd-progress-pct">{formatPct(pct)}</span>
                    </div>
                    <div className="gd-progress-track">
                      <div className="gd-progress-fill" style={{ width: `${Math.min(100, pct)}%` }} />
                    </div>
                    <div className="gd-progress-labels">
                      <span className="gd-progress-atual">
                        {formatBRL(progress.valor_atual)} guardados
                      </span>
                      <span className="gd-progress-meta">meta: {formatBRL(progress.valor_meta)}</span>
                    </div>
                    {goal.status !== "completed" &&
                      ritmo.remaining > 0 &&
                      ritmo.diasRestantes !== null &&
                      ritmo.diasRestantes >= 0 && (
                        <div className="gd-falta-badge">
                          ⏳ Faltam {formatBRL(ritmo.remaining)}
                          {ritmo.diasRestantes > 0 ? ` · ${ritmo.diasRestantes} dias restantes` : " · prazo encerrado"}
                        </div>
                      )}
                  </div>
                </div>

                <div className="gd-hero-stats">
                  <div className="gd-hero-stat">
                    <div className="gd-hero-stat-lbl">Ritmo necessário</div>
                    <div className="gd-hero-stat-val" style={{ color: "var(--warning)" }}>
                      {ritmo.ritmoNecessario != null ? `${formatBRL(ritmo.ritmoNecessario)}/dia` : "—"}
                    </div>
                  </div>
                  <div className="gd-hero-stat">
                    <div className="gd-hero-stat-lbl">Ritmo atual</div>
                    <div className="gd-hero-stat-val" style={{ color: "var(--success)" }}>
                      {formatBRL(ritmo.ritmoAtual)}/dia
                    </div>
                  </div>
                  <div className="gd-hero-stat">
                    <div className="gd-hero-stat-lbl">Movimentações</div>
                    <div className="gd-hero-stat-val" style={{ color: "var(--accent)" }}>
                      {txs.length}
                    </div>
                  </div>
                </div>
              </div>
            </article>

            <section className="gd-dashboard-panel" aria-label="Dashboard de metas">
              <div className="gd-panel-title">Dashboard de metas</div>
              <p className="gd-panel-sub">
                {periodoLabel ? `Competência de ${periodoLabel}` : "Competência do mês selecionado"}
              </p>
              {poolError && <p className="error gd-error">{poolError}</p>}
              <div className="gd-panel-grid">
                <div className="gd-panel-item">
                  <div className="gd-panel-item-lbl">Disponível para dividir no mês</div>
                  <div
                    className={`gd-panel-item-val${availableForGoals < 0 ? " gd-panel-item-val--muted" : " gd-panel-item-val--green"}`}
                  >
                    {formatBRL(availableForGoals)}
                  </div>
                </div>
                <div className="gd-panel-item">
                  <div className="gd-panel-item-lbl">Lançado em despesas fixas no mês</div>
                  <div className="gd-panel-item-val gd-panel-item-val--blue">{formatBRL(metasPoolTotal)}</div>
                </div>
                <div className="gd-panel-item">
                  <div className="gd-panel-item-lbl">Guardado nos cofres neste mês</div>
                  <div className="gd-panel-item-val gd-panel-item-val--muted">
                    {formatBRL(metasDepositedTotal)}
                  </div>
                </div>
              </div>
            </section>

            <section className="gd-movimentar-card" aria-label="Registrar movimentação">
              <div className="gd-sec-label">Registrar movimentação</div>
              <div className="gd-tipo-indicator">
                <button
                  type="button"
                  className={`gd-tipo-chip${tipo === "deposit" ? " gd-tipo-chip--dep" : ""}`}
                  onClick={() => handleSetTipo("deposit")}
                >
                  ⬆️ Depósito
                </button>
                <button
                  type="button"
                  className={`gd-tipo-chip${tipo === "withdraw" ? " gd-tipo-chip--ret" : ""}`}
                  onClick={() => handleSetTipo("withdraw")}
                >
                  ⬇️ Retirada
                </button>
              </div>
              <div className="gd-mov-body">
                <form onSubmit={onSubmit}>
                  <div className="gd-form-grid">
                    <div>
                      <label className="gd-form-label" htmlFor="gd-mov-valor">
                        Valor
                      </label>
                      <div className="gd-prefix-wrap">
                        <span className="gd-prefix">R$</span>
                        <input
                          id="gd-mov-valor"
                          className="gd-form-input gd-form-input--pfx"
                          type="text"
                          placeholder="0,00"
                          value={valor}
                          onChange={(e) => setValor(e.target.value)}
                          required
                        />
                      </div>
                    </div>
                    <div>
                      <label className="gd-form-label" htmlFor="gd-mov-data">
                        Data
                      </label>
                      <input
                        id="gd-mov-data"
                        className="gd-form-input"
                        type="text"
                        value={data}
                        onChange={(e) => setData(formatDateInput(e.target.value))}
                        placeholder="dd/mm/aaaa"
                        inputMode="numeric"
                        maxLength={10}
                        required
                      />
                    </div>
                    <div>
                      <label className="gd-form-label" htmlFor="gd-mov-obs">
                        Observação
                      </label>
                      <input
                        id="gd-mov-obs"
                        className="gd-form-input"
                        type="text"
                        placeholder="Opcional…"
                        value={observacao}
                        onChange={(e) => setObservacao(e.target.value)}
                      />
                    </div>
                    <button
                      type="submit"
                      className={`gd-btn-registrar${tipo === "deposit" ? " gd-btn-registrar--dep" : " gd-btn-registrar--ret"}`}
                      disabled={saving}
                    >
                      {saving ? "Salvando…" : tipo === "deposit" ? "⬆️ Registrar" : "⬇️ Registrar"}
                    </button>
                  </div>

                  {tipo === "withdraw" && (
                    <div className="gd-withdraw-options">
                      <button
                        type="button"
                        className={`gd-receita-check-wrap${launchAsIncome ? " checked" : ""}`}
                        onClick={() => setLaunchAsIncome((prev) => !prev)}
                      >
                        <span className="gd-chk-box" aria-hidden />
                        <span className="gd-chk-content">
                          <span className="gd-chk-label">💰 Lançar como receita do mês</span>
                          <span className="gd-chk-sub">
                            {launchAsIncome
                              ? "O valor será registrado automaticamente nas receitas do período da data informada."
                              : 'Se desmarcado, o valor fica em "Disponível para dividir nas metas".'}
                          </span>
                        </span>
                      </button>

                      {launchAsIncome && (
                        <div className="gd-cat-receita-wrap show">
                          <label className="gd-form-label" htmlFor="gd-mov-categoria">
                            Categoria da receita
                          </label>
                          <select
                            id="gd-mov-categoria"
                            className="gd-form-select"
                            value={categoriaId}
                            onChange={(e) => setCategoriaId(e.target.value)}
                            required
                          >
                            {incomeCategories.map((cat) => (
                              <option key={cat.id} value={cat.id}>
                                {cat.nome}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      <div
                        className={`gd-preview-banner${launchAsIncome ? " gd-preview-banner--receita" : " gd-preview-banner--saldo"}`}
                      >
                        {launchAsIncome ? (
                          <>
                            ✅ <strong>R$ {valor || "0,00"}</strong> serão adicionados às receitas de{" "}
                            {withdrawPeriodLabel} automaticamente.
                          </>
                        ) : (
                          <>
                            🏦 O valor volta para o <strong>disponível de {withdrawPeriodLabel}</strong> — você
                            pode dividir em outras metas dentro desse mês.
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </form>
              </div>
            </section>

            <div className="gd-sec-label">Movimentações</div>
            {txs.length === 0 ? (
              <p className="gd-empty-msg">Nenhuma movimentação.</p>
            ) : (
              <div className="gd-mov-table">
                <div className="gd-mov-head">
                  <div className="gd-mov-th">Data</div>
                  <div className="gd-mov-th">Tipo</div>
                  <div className="gd-mov-th">Observação</div>
                  <div className="gd-mov-th">Valor</div>
                  <div className="gd-mov-th" aria-hidden />
                </div>
                {txs.map((t) => {
                  const isDeposit = t.tipo === "deposit";
                  return (
                    <div key={t.id} className="gd-mov-row">
                      <div className="gd-mov-date">{formatDateBR(t.data)}</div>
                      <div>
                        <span
                          className={`gd-mov-tipo ${isDeposit ? "gd-mov-tipo--deposito" : "gd-mov-tipo--retirada"}`}
                        >
                          {txTipoLabel(t.tipo, t.income_id)}
                        </span>
                      </div>
                      <div className="gd-mov-origem">{t.descricao ?? "Manual"}</div>
                      <div
                        className="gd-mov-val"
                        style={{ color: isDeposit ? "var(--success)" : "var(--danger)" }}
                      >
                        {isDeposit ? "+" : "−"}
                        {formatBRL(t.valor)}
                      </div>
                      <div className="gd-mov-actions">
                        <button
                          type="button"
                          className="gd-btn-del-sm"
                          disabled={deletingTxId === t.id}
                          aria-label="Excluir movimentação"
                          onClick={() => void removeTx(t)}
                        >
                          🗑
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      {showEditModal && (
        <div
          className="gd-modal-overlay"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowEditModal(false);
          }}
        >
          <div
            className="gd-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="gd-edit-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="gd-modal-header">
              <h2 id="gd-edit-title" className="gd-modal-title">
                Editar meta
              </h2>
              <button
                type="button"
                className="gd-modal-close"
                aria-label="Fechar"
                onClick={() => setShowEditModal(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={onEditSubmit}>
              <div className="gd-modal-body">
                <div>
                  <label className="gd-form-label" htmlFor="gd-edit-nome">
                    Nome da meta
                  </label>
                  <input
                    id="gd-edit-nome"
                    className="gd-form-input"
                    type="text"
                    value={editNome}
                    onChange={(e) => setEditNome(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="gd-form-label" htmlFor="gd-edit-tipo">
                    Tipo
                  </label>
                  <select
                    id="gd-edit-tipo"
                    className="gd-form-select"
                    value={editTipo}
                    onChange={(e) => setEditTipo(e.target.value as typeof editTipo)}
                  >
                    <option value="short">Curto prazo</option>
                    <option value="medium">Médio prazo</option>
                    <option value="long">Longo prazo</option>
                  </select>
                </div>
                <div>
                  <label className="gd-form-label" htmlFor="gd-edit-meta">
                    Valor objetivo
                  </label>
                  <input
                    id="gd-edit-meta"
                    className="gd-form-input"
                    type="text"
                    value={editMeta}
                    onChange={(e) => setEditMeta(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="gd-form-label" htmlFor="gd-edit-fim">
                    Fim
                  </label>
                  <input
                    id="gd-edit-fim"
                    className="gd-form-input"
                    type="text"
                    value={editDataFim}
                    onChange={(e) => setEditDataFim(formatDateInput(e.target.value))}
                    placeholder="dd/mm/aaaa"
                    inputMode="numeric"
                    maxLength={10}
                  />
                </div>
              </div>
              <div className="gd-modal-actions">
                <button type="button" className="gd-btn-cancel" onClick={() => setShowEditModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="gd-btn-registrar" disabled={editSaving}>
                  {editSaving ? "Salvando…" : "Salvar alterações"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
