import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api";
import { DatePicker } from "../components/DatePicker";
import { useAppDialog } from "../context/DialogContext";
import { formatBRL } from "../money";
import type { DebtorLoanRow, SpenderRow } from "../types";

type PaymentDraft = { data_pagamento: string; valor_pago: string; observacao: string };
type LoanFilter = "pending" | "settled" | "stale";
type LoanSort = "pending_desc" | "newest_desc" | "name_asc";
type LoanRisk = "normal" | "warning" | "high";

const FILTER_CHIPS: { value: LoanFilter; label: string; activeClass: string }[] = [
  { value: "pending", label: "Pendentes", activeClass: "db-chip--accent" },
  { value: "stale", label: "Em atenção", activeClass: "db-chip--amber" },
  { value: "settled", label: "Histórico", activeClass: "db-chip--muted" },
];

const todayIso = () => new Date().toISOString().slice(0, 10);

function normalizeDecimalInput(value: string): string {
  return value.trim().replace(",", ".");
}

function parseDecimal(value: string): number {
  return parseFloat(value) || 0;
}

function formatDateBR(isoDate: string | null | undefined): string {
  if (!isoDate) return "—";
  const d = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(d.getTime())) return isoDate;
  return d.toLocaleDateString("pt-BR");
}

function paidPercent(row: DebtorLoanRow): number {
  const total = parseDecimal(row.valor_emprestado);
  if (total <= 0) return 0;
  return Math.min(100, Math.round((parseDecimal(row.valor_pago) / total) * 100));
}

function loanRisk(row: DebtorLoanRow): LoanRisk {
  const pending = parseDecimal(row.valor_restante);
  const days = row.dias_sem_pagamento ?? 0;
  if (pending > 0 && (days >= 60 || pending >= 1000)) return "high";
  if (pending > 0 && (days >= 30 || pending >= 500)) return "warning";
  return "normal";
}

function loanRiskLabel(row: DebtorLoanRow, risk: LoanRisk): string {
  if (row.status === "quitado") return "✓ QUITADO";
  if (risk === "high") return "🚨 ALTO RISCO";
  if (risk === "warning") return "⚠ ATENÇÃO";
  return "● NORMAL";
}

function badgeClass(row: DebtorLoanRow, risk: LoanRisk): string {
  if (row.status === "quitado") return "db-badge--quitado";
  if (risk === "high") return "db-badge--high";
  if (risk === "warning") return "db-badge--warning";
  return "db-badge--normal";
}

function pendingColorClass(row: DebtorLoanRow, risk: LoanRisk): string {
  const pending = parseDecimal(row.valor_restante);
  if (row.status === "quitado") return "db-cs-val--muted";
  if (risk === "high" || pending >= 500) return "db-cs-val--red";
  if (risk === "warning") return "db-cs-val--amber";
  return "db-cs-val--amber";
}

function progressFillClass(row: DebtorLoanRow, risk: LoanRisk): string {
  if (row.status === "quitado") return "db-progress-fill--green";
  if (risk === "high") return "db-progress-fill--red";
  if (risk === "warning") return "db-progress-fill--amber";
  return "db-progress-fill--green";
}

function stripeClass(row: DebtorLoanRow, risk: LoanRisk): string {
  if (row.status === "quitado") return "db-stripe--settled";
  if (risk === "high") return "db-stripe--high";
  if (risk === "warning") return "db-stripe--warning";
  return "db-stripe--normal";
}

const DEBTORS_LOAN_DETAILS_HIDDEN_KEY = "fm_debtors_loan_details_hidden";

function maskDebtorTitle(nome: string): string {
  const len = nome.trim().length;
  const dots = Math.min(14, Math.max(6, len || 6));
  return "•".repeat(dots);
}

function maskBRLPlaceholder(): string {
  return "R$ ••••";
}

function maskSnippet(): string {
  return "••••••••";
}

function loadDebtorsLoanDetailsHidden(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(DEBTORS_LOAN_DETAILS_HIDDEN_KEY);
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

function persistDebtorsLoanDetailsHidden(next: Record<string, boolean>) {
  try {
    localStorage.setItem(DEBTORS_LOAN_DETAILS_HIDDEN_KEY, JSON.stringify(next));
  } catch {
    // ignore
  }
}

function IconEyeOpen() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" aria-hidden={true}>
      <path
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
      />
      <path
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
      />
    </svg>
  );
}

function IconEyeSlash() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" aria-hidden={true}>
      <path
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88"
      />
    </svg>
  );
}

export function Debtors() {
  const { confirm } = useAppDialog();
  const [rows, setRows] = useState<DebtorLoanRow[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [devedorNome, setDevedorNome] = useState("");
  const [valorEmprestado, setValorEmprestado] = useState("");
  const [dataEmprestimo, setDataEmprestimo] = useState(todayIso());
  const [destinoDinheiro, setDestinoDinheiro] = useState("");
  const [observacoes, setObservacoes] = useState("");
  const [spenderRows, setSpenderRows] = useState<SpenderRow[]>([]);
  const [selectedSpenderId, setSelectedSpenderId] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<LoanFilter>("pending");
  const [sortBy, setSortBy] = useState<LoanSort>("pending_desc");
  const [paymentDrafts, setPaymentDrafts] = useState<Record<string, PaymentDraft>>({});
  const [historyOpenByLoan, setHistoryOpenByLoan] = useState<Record<string, boolean>>({});
  const [editingLoanId, setEditingLoanId] = useState<string | null>(null);
  const [editDevedorNome, setEditDevedorNome] = useState("");
  const [editValorEmprestado, setEditValorEmprestado] = useState("");
  const [editDataEmprestimo, setEditDataEmprestimo] = useState(todayIso());
  const [editDestinoDinheiro, setEditDestinoDinheiro] = useState("");
  const [editObservacoes, setEditObservacoes] = useState("");
  const [editSpenderId, setEditSpenderId] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [loanDetailsHiddenById, setLoanDetailsHiddenById] = useState<Record<string, boolean>>(
    loadDebtorsLoanDetailsHidden,
  );

  const resumo = useMemo(() => {
    return rows.reduce(
      (acc, row) => {
        const restante = parseDecimal(row.valor_restante);
        acc.emprestado += parseDecimal(row.valor_emprestado);
        acc.pago += parseDecimal(row.valor_pago);
        acc.restante += restante;
        if (row.status === "pendente") acc.pendentes += 1;
        if (row.status === "quitado") acc.quitados += 1;
        if (restante > acc.maiorPendente) {
          acc.maiorPendente = restante;
          acc.maiorPendenteNome = row.devedor_nome;
        }
        return acc;
      },
      {
        emprestado: 0,
        pago: 0,
        restante: 0,
        pendentes: 0,
        quitados: 0,
        maiorPendente: 0,
        maiorPendenteNome: "",
      },
    );
  }, [rows]);

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    const base = rows.filter((row) => {
      const matchSearch =
        !query ||
        row.devedor_nome.toLowerCase().includes(query) ||
        (row.spender_nome ?? "").toLowerCase().includes(query) ||
        row.destino_dinheiro.toLowerCase().includes(query) ||
        (row.observacoes ?? "").toLowerCase().includes(query);
      if (!matchSearch) return false;
      if (filter === "settled") return row.status === "quitado";
      if (filter === "stale") return row.status === "pendente" && (row.dias_sem_pagamento ?? 0) >= 30;
      return row.status === "pendente";
    });
    return [...base].sort((a, b) => {
      if (sortBy === "name_asc") return a.devedor_nome.localeCompare(b.devedor_nome, "pt-BR");
      if (sortBy === "newest_desc") return b.data_emprestimo.localeCompare(a.data_emprestimo);
      return parseDecimal(b.valor_restante) - parseDecimal(a.valor_restante);
    });
  }, [filter, rows, search, sortBy]);

  async function refresh() {
    setLoading(true);
    try {
      const [debtors, spenders] = await Promise.all([api.listDebtors(), api.listSpenders()]);
      setRows(debtors);
      setSpenderRows(spenders);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await refresh();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Erro ao carregar devedores");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function draftFor(loanId: string): PaymentDraft {
    return paymentDrafts[loanId] ?? { data_pagamento: todayIso(), valor_pago: "", observacao: "" };
  }

  function updateDraft(loanId: string, patch: Partial<PaymentDraft>) {
    setPaymentDrafts((prev) => ({ ...prev, [loanId]: { ...draftFor(loanId), ...patch } }));
  }

  function onCreateSpenderChange(nextSpenderId: string) {
    setSelectedSpenderId(nextSpenderId);
    if (!nextSpenderId) return;
    const selected = spenderRows.find((s) => s.id === nextSpenderId);
    if (!selected) return;
    setDevedorNome((prev) => (prev.trim() ? prev : selected.nome));
  }

  function onEditSpenderChange(nextSpenderId: string) {
    setEditSpenderId(nextSpenderId);
    if (!nextSpenderId) return;
    const selected = spenderRows.find((s) => s.id === nextSpenderId);
    if (!selected) return;
    setEditDevedorNome((prev) => (prev.trim() ? prev : selected.nome));
  }

  async function onCreateLoan(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await api.createDebtor({
        devedor_nome: devedorNome.trim(),
        valor_emprestado: normalizeDecimalInput(valorEmprestado),
        data_emprestimo: dataEmprestimo,
        destino_dinheiro: destinoDinheiro.trim(),
        observacoes: observacoes.trim() || undefined,
        spender_id: selectedSpenderId || undefined,
      });
      setDevedorNome("");
      setValorEmprestado("");
      setDataEmprestimo(todayIso());
      setDestinoDinheiro("");
      setObservacoes("");
      setSelectedSpenderId("");
      setMessage("Empréstimo criado com sucesso.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar empréstimo");
    } finally {
      setSaving(false);
    }
  }

  async function onDeleteLoan(id: string) {
    const ok = await confirm({
      title: "Excluir empréstimo",
      message: "Excluir este empréstimo?",
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    setError("");
    setMessage("");
    try {
      await api.deleteDebtor(id);
      setMessage("Empréstimo excluído.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir empréstimo");
    }
  }

  async function onAddPayment(loanId: string) {
    const draft = draftFor(loanId);
    setError("");
    setMessage("");
    try {
      const updated = await api.addDebtorPayment(loanId, {
        data_pagamento: draft.data_pagamento,
        valor_pago: normalizeDecimalInput(draft.valor_pago),
        observacao: draft.observacao.trim() || undefined,
      });
      setRows((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
      setPaymentDrafts((prev) => ({
        ...prev,
        [loanId]: { data_pagamento: todayIso(), valor_pago: "", observacao: "" },
      }));
      if (updated.status === "quitado") {
        if (filter !== "stale") setFilter("pending");
        setMessage("Empréstimo quitado e movido para o Histórico.");
      } else {
        setMessage("Pagamento registrado.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao registrar pagamento");
    }
  }

  function startEditLoan(row: DebtorLoanRow) {
    setEditingLoanId(row.id);
    setEditDevedorNome(row.devedor_nome);
    setEditValorEmprestado(String(row.valor_emprestado).replace(".", ","));
    setEditDataEmprestimo(row.data_emprestimo);
    setEditDestinoDinheiro(row.destino_dinheiro);
    setEditObservacoes(row.observacoes ?? "");
    setEditSpenderId(row.spender_id ?? "");
  }

  function cancelEditLoan() {
    setEditingLoanId(null);
    setEditDevedorNome("");
    setEditValorEmprestado("");
    setEditDataEmprestimo(todayIso());
    setEditDestinoDinheiro("");
    setEditObservacoes("");
    setEditSpenderId("");
  }

  async function onSaveLoanEdit(loanId: string, e: React.FormEvent) {
    e.preventDefault();
    setSavingEdit(true);
    setError("");
    setMessage("");
    try {
      const updated = await api.updateDebtor(loanId, {
        devedor_nome: editDevedorNome.trim(),
        valor_emprestado: normalizeDecimalInput(editValorEmprestado),
        data_emprestimo: editDataEmprestimo,
        destino_dinheiro: editDestinoDinheiro.trim(),
        observacoes: editObservacoes.trim() || "",
        spender_id: editSpenderId || null,
      });
      setRows((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
      setMessage("Empréstimo atualizado.");
      cancelEditLoan();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao atualizar empréstimo");
    } finally {
      setSavingEdit(false);
    }
  }

  async function onSettleLoan(row: DebtorLoanRow) {
    const pending = parseDecimal(row.valor_restante);
    if (pending <= 0) return;
    const ok = await confirm({
      title: "Quitar empréstimo",
      message: `Quitar "${row.devedor_nome}" com pagamento de ${formatBRL(pending.toFixed(2))}?`,
      confirmLabel: "Quitar",
    });
    if (!ok) return;
    setError("");
    setMessage("");
    try {
      const updated = await api.addDebtorPayment(row.id, {
        data_pagamento: todayIso(),
        valor_pago: pending.toFixed(2),
        observacao: "Quitação",
      });
      setRows((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      setPaymentDrafts((prev) => ({
        ...prev,
        [row.id]: { data_pagamento: todayIso(), valor_pago: "", observacao: "" },
      }));
      if (filter !== "stale") setFilter("pending");
      setMessage("Empréstimo quitado e movido para o Histórico.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao quitar empréstimo");
    }
  }

  async function onDeletePayment(paymentId: string) {
    const ok = await confirm({
      title: "Excluir pagamento",
      message: "Excluir este pagamento do histórico?",
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    setError("");
    setMessage("");
    try {
      const updated = await api.deleteDebtorPayment(paymentId);
      setRows((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
      setMessage("Pagamento removido.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir pagamento");
    }
  }

  function buildMetaLine(row: DebtorLoanRow, detailsHidden: boolean): ReactNode {
    if (detailsHidden) {
      return (
        <>
          Emprestado em <strong>{maskSnippet()}</strong> · Sem pagamento há <strong>••d</strong>
        </>
      );
    }
    const loanDate = formatDateBR(row.data_emprestimo);
    const days = row.dias_sem_pagamento ?? 0;
    if (row.status === "quitado" && row.ultimo_pagamento_em) {
      return (
        <>
          Emprestado em <strong>{loanDate}</strong> · Último pagamento{" "}
          <strong>{formatDateBR(row.ultimo_pagamento_em)}</strong>
        </>
      );
    }
    if (row.ultimo_pagamento_em) {
      return (
        <>
          Emprestado em <strong>{loanDate}</strong> · Último pagamento{" "}
          <strong>{formatDateBR(row.ultimo_pagamento_em)}</strong> · Sem pagamento há{" "}
          <strong>{days}d</strong>
        </>
      );
    }
    return (
      <>
        Emprestado em <strong>{loanDate}</strong> · Sem pagamento há <strong>{days}d</strong>
      </>
    );
  }

  const loanCountLabel =
    filter === "settled"
      ? filteredRows.length === 1
        ? "1 empréstimo no histórico"
        : `${filteredRows.length} empréstimos no histórico`
      : filteredRows.length === 1
        ? "1 empréstimo"
        : `${filteredRows.length} empréstimos`;

  function emptyFilterMessage(): string {
    if (search.trim()) return "Nenhum empréstimo encontrado com os filtros atuais.";
    if (filter === "settled") return "Nenhum empréstimo no histórico.";
    if (filter === "stale") return "Nenhum empréstimo em atenção.";
    return "Nenhum empréstimo pendente.";
  }

  function scrollToForm() {
    document.getElementById("novo-emprestimo")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="padded debtors-page">
      <header className="db-page-header">
        <h1 className="db-page-title">💸 Devedores</h1>
        <button type="button" className="db-btn-nova" onClick={scrollToForm}>
          ＋ Novo empréstimo
        </button>
      </header>

      {(error || message) && (
        <div className="db-feedback" role="status">
          {error && <p className="error">{error}</p>}
          {message && <p className="muted small">{message}</p>}
        </div>
      )}

      <div className="db-stats-grid" role="group" aria-label="Resumo de empréstimos">
        <div className="db-stat-card db-stat-card--green">
          <div className="db-stat-lbl">Total recebido</div>
          <div className="db-stat-val db-stat-val--green">{formatBRL(resumo.pago)}</div>
          <div className="db-stat-sub">acumulado</div>
        </div>
        <div className="db-stat-card db-stat-card--blue">
          <div className="db-stat-lbl">Total emprestado</div>
          <div className="db-stat-val db-stat-val--blue">{formatBRL(resumo.emprestado)}</div>
          <div className="db-stat-sub">histórico total</div>
        </div>
        <div className="db-stat-card db-stat-card--amber">
          <div className="db-stat-lbl">Total pendente</div>
          <div className="db-stat-val db-stat-val--amber">{formatBRL(resumo.restante)}</div>
          <div className="db-stat-sub">a receber</div>
        </div>
        <div className="db-stat-card db-stat-card--blue">
          <div className="db-stat-lbl">Empréstimos pendentes</div>
          <div className="db-stat-val db-stat-val--blue">{resumo.pendentes}</div>
          <div className="db-stat-sub">em aberto</div>
        </div>
        <div className="db-stat-card db-stat-card--muted">
          <div className="db-stat-lbl">Empréstimos quitados</div>
          <div className="db-stat-val db-stat-val--muted">{resumo.quitados}</div>
          <div className="db-stat-sub">finalizados</div>
        </div>
        <div className="db-stat-card db-stat-card--red">
          <div className="db-stat-lbl">Maior saldo pendente</div>
          <div className="db-stat-val db-stat-val--red">{formatBRL(resumo.maiorPendente.toFixed(2))}</div>
          <div className="db-stat-sub">{resumo.maiorPendenteNome || "—"}</div>
        </div>
      </div>

      <div className="db-two-col">
        <aside className="db-form-card" id="novo-emprestimo" aria-label="Novo empréstimo">
          <div className="db-form-card-title">
            <div className="db-form-icon" aria-hidden="true">
              ＋
            </div>
            Novo empréstimo
          </div>
          <form onSubmit={onCreateLoan}>
            <div className="db-form-group">
              <label className="db-form-label" htmlFor="db-devedor-nome">
                Quem te deve
              </label>
              <input
                id="db-devedor-nome"
                className="db-form-input"
                value={devedorNome}
                onChange={(e) => setDevedorNome(e.target.value)}
                placeholder="Nome do devedor"
                required
              />
            </div>
            <div className="db-form-group">
              <label className="db-form-label" htmlFor="db-spender">
                Pessoa do cartão (opcional)
              </label>
              <select
                id="db-spender"
                className="db-form-select"
                value={selectedSpenderId}
                onChange={(e) => onCreateSpenderChange(e.target.value)}
              >
                <option value="">Não vincular ao uso por pessoa</option>
                {spenderRows.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.nome}
                  </option>
                ))}
              </select>
            </div>
            <div className="db-form-row">
              <div className="db-form-group">
                <label className="db-form-label" htmlFor="db-valor">
                  Quanto pegou
                </label>
                <div className="db-pfx-wrap">
                  <span className="db-pfx" aria-hidden="true">
                    R$
                  </span>
                  <input
                    id="db-valor"
                    className="db-form-input db-form-input--pfx"
                    value={valorEmprestado}
                    onChange={(e) => setValorEmprestado(e.target.value)}
                    inputMode="decimal"
                    placeholder="0,00"
                    required
                  />
                </div>
              </div>
              <div className="db-form-group">
                <label className="db-form-label" htmlFor="db-data">
                  Data
                </label>
                <DatePicker
                  id="db-data"
                  inputClassName="db-form-input"
                  value={dataEmprestimo}
                  onChange={setDataEmprestimo}
                  required
                  aria-label="Data do empréstimo"
                />
              </div>
            </div>
            <div className="db-form-group">
              <label className="db-form-label" htmlFor="db-destino">
                Destino do dinheiro
              </label>
              <input
                id="db-destino"
                className="db-form-input"
                value={destinoDinheiro}
                onChange={(e) => setDestinoDinheiro(e.target.value)}
                placeholder="Ex: Guardar meta 2k"
                required
              />
            </div>
            <div className="db-form-group">
              <label className="db-form-label" htmlFor="db-obs">
                Observações
              </label>
              <textarea
                id="db-obs"
                className="db-form-textarea"
                value={observacoes}
                onChange={(e) => setObservacoes(e.target.value)}
                placeholder="Observações opcionais…"
                rows={3}
              />
            </div>
            <button type="submit" className="db-btn-save" disabled={saving}>
              {saving ? "Salvando…" : "💾 Salvar empréstimo"}
            </button>
          </form>
        </aside>

        <section className="db-list-side" aria-label="Lista de empréstimos">
          <div className="db-list-controls">
            <div className="db-search-row">
              <span className="db-search-icon" aria-hidden="true">
                🔍
              </span>
              <input
                className="db-search-input"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar por devedor, destino ou observação…"
                aria-label="Buscar empréstimo"
              />
            </div>
            <div className="db-filter-row">
              <div className="db-chips" role="group" aria-label="Filtrar empréstimos">
                {FILTER_CHIPS.map((chip) => (
                  <button
                    key={chip.value}
                    type="button"
                    className={`db-chip${filter === chip.value ? ` active ${chip.activeClass}` : ""}`}
                    onClick={() => setFilter(chip.value)}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
              <select
                className="db-sort-select"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as LoanSort)}
                aria-label="Ordenar empréstimos"
              >
                <option value="pending_desc">Maior pendente</option>
                <option value="newest_desc">Mais recente</option>
                <option value="name_asc">Nome A–Z</option>
              </select>
            </div>
          </div>

          <div className="db-list-meta">
            <span className="db-list-count">{loanCountLabel}</span>
          </div>

          {loading ? (
            <div className="db-loan-cards">
              {Array.from({ length: 3 }).map((_, idx) => (
                <div key={idx} className="db-loan-card db-loan-card--skeleton">
                  <p className="muted small">Carregando empréstimo…</p>
                </div>
              ))}
            </div>
          ) : rows.length === 0 ? (
            <div className="db-empty">
              <p className="db-empty-msg">Nenhum devedor cadastrado.</p>
              <button type="button" className="db-btn-historico" style={{ width: "auto" }} onClick={scrollToForm}>
                Criar primeiro empréstimo
              </button>
            </div>
          ) : filteredRows.length === 0 ? (
            <div className="db-empty">
              <p className="db-empty-msg">{emptyFilterMessage()}</p>
              {(search.trim() || filter !== "pending") && (
                <button
                  type="button"
                  className="db-btn-historico"
                  style={{ width: "auto" }}
                  onClick={() => {
                    setSearch("");
                    setFilter("pending");
                  }}
                >
                  {filter === "settled" && !search.trim() ? "Ver pendentes" : "Limpar filtros"}
                </button>
              )}
            </div>
          ) : (
            <div className="db-loan-cards">
              {filteredRows.map((row) => {
                const draft = draftFor(row.id);
                const risk = loanRisk(row);
                const historyOpen = historyOpenByLoan[row.id] ?? false;
                const suggestedPending = parseDecimal(row.valor_restante).toFixed(2).replace(".", ",");
                const detailsHidden = !!loanDetailsHiddenById[row.id];
                const pct = paidPercent(row);
                const isSettled = row.status === "quitado";

                return (
                  <article
                    key={row.id}
                    className={`db-loan-card${isSettled ? " db-loan-card--settled" : ""}`}
                  >
                    <div className={`db-stripe ${stripeClass(row, risk)}`} aria-hidden="true" />

                    <div className="db-card-header">
                      <h3 className="db-card-name">
                        {detailsHidden ? maskDebtorTitle(row.devedor_nome) : row.devedor_nome}
                      </h3>
                      <div className="db-card-top-right">
                        <button
                          type="button"
                          className="db-privacy-toggle"
                          aria-label={
                            detailsHidden
                              ? "Mostrar nome, valores e histórico deste empréstimo"
                              : "Ocultar nome, valores e histórico deste empréstimo"
                          }
                          aria-pressed={detailsHidden}
                          onClick={() =>
                            setLoanDetailsHiddenById((prev) => {
                              const next = { ...prev };
                              if (next[row.id]) delete next[row.id];
                              else next[row.id] = true;
                              persistDebtorsLoanDetailsHidden(next);
                              return next;
                            })
                          }
                        >
                          {detailsHidden ? <IconEyeSlash /> : <IconEyeOpen />}
                        </button>
                        <span className={`db-badge ${badgeClass(row, risk)}`}>
                          {loanRiskLabel(row, risk)}
                        </span>
                      </div>
                    </div>

                    <p className="db-card-meta">{buildMetaLine(row, detailsHidden)}</p>

                    <div className="db-progress-wrap">
                      <div className="db-progress-label">
                        <span>Pago</span>
                        <span>{detailsHidden ? "••%" : `${pct}%`}</span>
                      </div>
                      <div className="db-progress-track">
                        <div
                          className={`db-progress-fill ${progressFillClass(row, risk)}`}
                          style={{ width: detailsHidden ? "0%" : `${pct}%` }}
                        />
                      </div>
                    </div>

                    <div className="db-card-stats">
                      <div className="db-card-stat">
                        <div className="db-cs-lbl">Emprestado</div>
                        <div className="db-cs-val">
                          {detailsHidden ? maskBRLPlaceholder() : formatBRL(row.valor_emprestado)}
                        </div>
                      </div>
                      <div className="db-card-stat">
                        <div className="db-cs-lbl">Pago</div>
                        <div className="db-cs-val db-cs-val--green">
                          {detailsHidden ? maskBRLPlaceholder() : formatBRL(row.valor_pago)}
                        </div>
                      </div>
                      <div className="db-card-stat">
                        <div className="db-cs-lbl">Pendente</div>
                        <div className={`db-cs-val ${pendingColorClass(row, risk)}`}>
                          {detailsHidden ? maskBRLPlaceholder() : formatBRL(row.valor_restante)}
                        </div>
                      </div>
                    </div>

                    {isSettled && row.ultimo_pagamento_em && (
                      <div className="db-quitado-banner">
                        ✅ Empréstimo quitado em{" "}
                        {detailsHidden ? maskSnippet() : formatDateBR(row.ultimo_pagamento_em)}
                      </div>
                    )}

                    {(row.destino_dinheiro || row.observacoes || row.spender_nome) && (
                      <div className="db-card-info">
                        {row.destino_dinheiro && (
                          <div>
                            <span className="db-info-lbl">Destino: </span>
                            {detailsHidden ? maskSnippet() : row.destino_dinheiro}
                          </div>
                        )}
                        {row.observacoes && (
                          <div>
                            <span className="db-info-lbl">Obs: </span>
                            {detailsHidden ? maskSnippet() : row.observacoes}
                          </div>
                        )}
                        {row.spender_nome && (
                          <div>
                            <span className="db-info-lbl">Vínculo: </span>
                            {detailsHidden ? maskSnippet() : row.spender_nome}
                          </div>
                        )}
                      </div>
                    )}

                    {editingLoanId === row.id && (
                      <form className="db-edit-form" onSubmit={(e) => void onSaveLoanEdit(row.id, e)}>
                        <div className="db-form-group">
                          <label className="db-form-label">Quem te deve</label>
                          <input
                            className="db-form-input"
                            value={editDevedorNome}
                            onChange={(e) => setEditDevedorNome(e.target.value)}
                            required
                          />
                        </div>
                        <div className="db-form-group">
                          <label className="db-form-label">Pessoa do cartão (opcional)</label>
                          <select
                            className="db-form-select"
                            value={editSpenderId}
                            onChange={(e) => onEditSpenderChange(e.target.value)}
                          >
                            <option value="">Não vincular ao uso por pessoa</option>
                            {spenderRows.map((s) => (
                              <option key={s.id} value={s.id}>
                                {s.nome}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="db-form-row">
                          <div className="db-form-group">
                            <label className="db-form-label">Valor emprestado</label>
                            <div className="db-pfx-wrap">
                              <span className="db-pfx" aria-hidden="true">
                                R$
                              </span>
                              <input
                                className="db-form-input db-form-input--pfx"
                                value={editValorEmprestado}
                                onChange={(e) => setEditValorEmprestado(e.target.value)}
                                inputMode="decimal"
                                required
                              />
                            </div>
                          </div>
                          <div className="db-form-group">
                            <label className="db-form-label">Data do empréstimo</label>
                            <DatePicker
                              inputClassName="db-form-input"
                              value={editDataEmprestimo}
                              onChange={setEditDataEmprestimo}
                              required
                              aria-label="Data do empréstimo"
                            />
                          </div>
                        </div>
                        <div className="db-form-group">
                          <label className="db-form-label">Destino do dinheiro</label>
                          <input
                            className="db-form-input"
                            value={editDestinoDinheiro}
                            onChange={(e) => setEditDestinoDinheiro(e.target.value)}
                            required
                          />
                        </div>
                        <div className="db-form-group">
                          <label className="db-form-label">Observações</label>
                          <textarea
                            className="db-form-textarea"
                            rows={3}
                            value={editObservacoes}
                            onChange={(e) => setEditObservacoes(e.target.value)}
                          />
                        </div>
                        <div className="db-edit-actions">
                          <button type="submit" className="db-btn-save" disabled={savingEdit} style={{ flex: 1 }}>
                            {savingEdit ? "Salvando…" : "Salvar alterações"}
                          </button>
                          <button type="button" className="db-btn-historico" onClick={() => cancelEditLoan()}>
                            Cancelar
                          </button>
                        </div>
                      </form>
                    )}

                    <div className={`db-card-actions${isSettled ? " db-card-actions--settled" : ""}`}>
                      <button
                        type="button"
                        className="db-btn-act db-btn-act--edit"
                        onClick={() => startEditLoan(row)}
                      >
                        ✏️ Editar
                      </button>
                      <button
                        type="button"
                        className={`db-btn-act db-btn-act--del${isSettled ? " db-btn-act--span" : ""}`}
                        onClick={() => void onDeleteLoan(row.id)}
                      >
                        {isSettled ? "🗑 Excluir do histórico" : "🗑 Excluir"}
                      </button>
                      {!isSettled && (
                        <button
                          type="button"
                          className="db-btn-act db-btn-act--quitar"
                          onClick={() => void onSettleLoan(row)}
                        >
                          ✓ Quitar
                        </button>
                      )}
                    </div>

                    <div className="db-payment-section">
                      {!isSettled && (
                        <>
                          <div className="db-pay-sec-title">Registrar pagamento</div>
                          <form
                            onSubmit={(e) => {
                              e.preventDefault();
                              void onAddPayment(row.id);
                            }}
                          >
                            <div className="db-pay-row">
                              <input
                                className="db-pay-input"
                                placeholder="Valor pago…"
                                inputMode="decimal"
                                value={draft.valor_pago}
                                onChange={(e) => updateDraft(row.id, { valor_pago: e.target.value })}
                                onFocus={() => {
                                  if (!draft.valor_pago.trim()) {
                                    updateDraft(row.id, { valor_pago: suggestedPending });
                                  }
                                }}
                                required
                              />
                              <DatePicker
                                className="db-pay-date-wrap"
                                inputClassName="db-pay-date"
                                value={draft.data_pagamento}
                                onChange={(iso) => updateDraft(row.id, { data_pagamento: iso })}
                                required
                                aria-label="Data do pagamento"
                              />
                            </div>
                            <textarea
                              className="db-pay-obs"
                              rows={2}
                              placeholder="Observação (opcional)"
                              value={draft.observacao}
                              onChange={(e) => updateDraft(row.id, { observacao: e.target.value })}
                            />
                            <button type="submit" className="db-btn-pay">
                              ＋ Adicionar pagamento
                            </button>
                          </form>
                        </>
                      )}

                      <button
                        type="button"
                        className="db-btn-historico"
                        onClick={() =>
                          setHistoryOpenByLoan((prev) => ({
                            ...prev,
                            [row.id]: !(prev[row.id] ?? false),
                          }))
                        }
                      >
                        {historyOpen
                          ? "📋 Ocultar histórico"
                          : isSettled
                            ? "📋 Ver histórico de pagamentos"
                            : "📋 Mostrar histórico"}
                      </button>

                      {historyOpen && (
                        <div className="db-hist-wrap" aria-label="Histórico de pagamentos">
                          {row.pagamentos.length === 0 ? (
                            <p className="db-no-payments">Sem pagamentos ainda.</p>
                          ) : (
                            row.pagamentos.map((payment) => (
                              <div key={payment.id} className="db-hist-item">
                                <div>
                                  <div className="db-hist-date">
                                    {detailsHidden ? "••/••/••••" : formatDateBR(payment.data_pagamento)}
                                  </div>
                                  {payment.observacao && (
                                    <p className="db-hist-obs">
                                      {detailsHidden ? maskSnippet() : payment.observacao}
                                    </p>
                                  )}
                                </div>
                                <div className="db-hist-right">
                                  <span className="db-hist-val">
                                    {detailsHidden ? maskBRLPlaceholder() : formatBRL(payment.valor_pago)}
                                  </span>
                                  <button
                                    type="button"
                                    className="db-hist-del"
                                    onClick={() => void onDeletePayment(payment.id)}
                                    aria-label="Excluir pagamento"
                                  >
                                    ✕
                                  </button>
                                </div>
                              </div>
                            ))
                          )}
                        </div>
                      )}
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
