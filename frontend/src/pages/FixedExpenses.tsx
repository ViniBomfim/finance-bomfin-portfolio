import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAppDialog } from "../context/DialogContext";
import { usePeriod } from "../context/PeriodContext";
import { formatBRL } from "../money";
import {
  autoSplitRowsOnPersonSelect,
  decimalPointToComma,
  prepareShareRowsForSubmit,
  rebalanceShareRows,
  resolveSharesPayload,
  sumShareRows,
} from "../shareSplit";
import type { Category, ExpenseRow, SpenderRow } from "../types";

function formatDateBR(value: string): string {
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("pt-BR");
}

function formatGroupDateLabel(isoDate: string): string {
  const d = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(d.getTime())) return isoDate;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
}

const PERSON_GRADIENTS = [
  "linear-gradient(135deg,#334155,#475569)",
  "linear-gradient(135deg,#3b82f6,#22d3ee)",
  "linear-gradient(135deg,#f43f5e,#a855f7)",
  "linear-gradient(135deg,#f59e0b,#ef4444)",
  "linear-gradient(135deg,#a78bfa,#ec4899)",
  "linear-gradient(135deg,#22c55e,#16a34a)",
];

function personInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0]!.slice(0, 2);
  return `${parts[0]!.charAt(0)}${parts[parts.length - 1]!.charAt(0)}`;
}

function personGradient(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash + name.charCodeAt(i) * (i + 1)) % PERSON_GRADIENTS.length;
  }
  return PERSON_GRADIENTS[hash] ?? PERSON_GRADIENTS[0]!;
}

function personToneIndex(name: string): number | "sem" {
  const n = name.trim().toLowerCase();
  if (n === "sem pessoa") return "sem";
  let hash = 0;
  for (let i = 0; i < n.length; i++) hash = (hash * 31 + n.charCodeAt(i)) >>> 0;
  return hash % 4;
}

function personCardClass(name: string): string {
  const tone = personToneIndex(name);
  if (tone === "sem") return "fe-person-card--sem";
  return `fe-person-card--tone-${tone}`;
}

function categoryEmoji(nome: string): string {
  const n = nome.toLowerCase();
  if (n.includes("apart") || n.includes("apê") || n.includes("ape")) return "🏠 ";
  if (n.includes("casa")) return "🏡 ";
  if (n.includes("meta")) return "🎯 ";
  if (n.includes("carro") || n.includes("auto")) return "🚗 ";
  return "";
}

const INSTALLMENT_SUFFIX_RE = /\((\d+)\s*\/\s*(\d+)\)\s*$/;

function stripInstallmentSuffix(descricao: string): string {
  return descricao.replace(INSTALLMENT_SUFFIX_RE, "").trimEnd();
}

function parseInstallmentSuffix(descricao: string): { current: number; total: number } | null {
  const m = descricao.trim().match(INSTALLMENT_SUFFIX_RE);
  if (!m) return null;
  const current = Number(m[1]);
  const total = Number(m[2]);
  if (!Number.isFinite(current) || !Number.isFinite(total) || total < 1) return null;
  return { current: Math.max(1, current), total: Math.max(1, total) };
}

function withInstallmentSuffix(base: string, current: number, total: number): string {
  const clean = stripInstallmentSuffix(base).trim();
  return `${clean} (${current}/${total})`;
}

function addCalendarMonths(ano: number, mes: number, delta: number): { ano: number; mes: number } {
  const idx = ano * 12 + (mes - 1) + delta;
  return { ano: Math.floor(idx / 12), mes: (idx % 12) + 1 };
}

function dateInMonthIso(ano: number, mes: number, preferredDay: number): string {
  const lastDay = new Date(ano, mes, 0).getDate();
  const day = Math.min(Math.max(1, preferredDay), lastDay);
  return `${ano}-${String(mes).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

const NO_PERSON_KEY = "no-person";

type FixedExpensePersonStat = {
  id: string;
  name: string;
  usage: number;
  pending: number;
};

function getPersonShareInExpense(row: ExpenseRow, spenderId: string): number {
  const shares = row.shares ?? [];
  if (shares.length === 0) return 0;
  const share = shares.find((s) => s.spender_id === spenderId);
  return share ? parseFloat(share.valor) || 0 : 0;
}

function isSharePaid(share: { pago?: boolean }): boolean {
  return share.pago === true;
}

function expensePaymentStatus(row: ExpenseRow): "paid" | "partial" | "pending" {
  const shares = row.shares ?? [];
  if (shares.length === 0) return row.pago ? "paid" : "pending";
  const paidCount = shares.filter((s) => isSharePaid(s)).length;
  if (paidCount === shares.length) return "paid";
  if (paidCount === 0) return "pending";
  return "partial";
}

function isMySharePending(row: ExpenseRow, meSpenderId: string): boolean {
  const shares = row.shares ?? [];
  if (shares.length === 0) return false;
  const mine = shares.find((s) => s.spender_id === meSpenderId);
  if (!mine) return false;
  return !isSharePaid(mine);
}

function buildFixedExpensePersonStats(
  rows: ExpenseRow[],
  categoryFilter: string,
): Map<string, FixedExpensePersonStat> {
  const bucket = new Map<string, FixedExpensePersonStat>();
  const targetRows = rows.filter(
    (r) => categoryFilter === "all" || r.categoria_id === categoryFilter,
  );

  for (const row of targetRows) {
    const val = parseFloat(row.valor) || 0;
    const shares = row.shares ?? [];

    if (shares.length === 0) {
      const current = bucket.get(NO_PERSON_KEY) ?? {
        id: NO_PERSON_KEY,
        name: "Sem pessoa",
        usage: 0,
        pending: 0,
      };
      current.usage += val;
      if (!row.pago) current.pending += val;
      bucket.set(NO_PERSON_KEY, current);
      continue;
    }

    for (const sh of shares) {
      const shareVal = parseFloat(sh.valor) || 0;
      const key = sh.spender_id;
      const current = bucket.get(key) ?? {
        id: key,
        name: sh.spender_nome || "Pessoa removida",
        usage: 0,
        pending: 0,
      };
      current.usage += shareVal;
      if (!isSharePaid(sh)) current.pending += shareVal;
      bucket.set(key, current);
    }
  }

  return bucket;
}

function rowsWithMyShare(rows: ExpenseRow[], meSpenderId: string | null): ExpenseRow[] {
  if (!meSpenderId) return [];
  return rows.filter((row) => getPersonShareInExpense(row, meSpenderId) > 0);
}

function rowsWithMyPendingShare(rows: ExpenseRow[], meSpenderId: string | null): ExpenseRow[] {
  if (!meSpenderId) return [];
  return rowsWithMyShare(rows, meSpenderId).filter((row) => isMySharePending(row, meSpenderId));
}

async function removeMyShareFromExpense(
  row: ExpenseRow,
  meSpenderId: string,
): Promise<"deleted" | "updated" | "skipped"> {
  const myShare = getPersonShareInExpense(row, meSpenderId);
  if (myShare <= 0) return "skipped";

  const others = (row.shares ?? []).filter((share) => share.spender_id !== meSpenderId);
  if (others.length === 0) {
    await api.deleteExpense(row.id);
    return "deleted";
  }

  const newValor = (parseFloat(row.valor) - myShare).toFixed(2);
  await api.updateExpense(row.id, {
    valor: newValor,
    shares: others.map((share) => ({
      spender_id: share.spender_id,
      valor: share.valor,
      pago: isSharePaid(share),
    })),
    tipo: "fixed",
  });
  return "updated";
}

type FixedExpenseRowProps = {
  row: ExpenseRow;
  categoryName: string;
  periodClosed: boolean;
  rowBusy: boolean;
  updatingPagoId: string | null;
  onOpenMenu: (row: ExpenseRow) => void;
  onEdit: (row: ExpenseRow) => void;
  onDelete: (row: ExpenseRow) => void;
  onShare: (row: ExpenseRow) => void;
  onExpensePagoChange: (row: ExpenseRow, nextPago: boolean) => void;
  onSharePagoChange: (row: ExpenseRow, spenderId: string, nextPago: boolean) => void;
  onMarkAllShares: (row: ExpenseRow, nextPago: boolean) => void;
};

function FixedExpenseRow({
  row,
  categoryName,
  periodClosed,
  rowBusy,
  updatingPagoId,
  onOpenMenu,
  onEdit,
  onDelete,
  onShare,
  onExpensePagoChange,
  onSharePagoChange,
  onMarkAllShares,
}: FixedExpenseRowProps) {
  const shares = row.shares ?? [];
  const disabled = periodClosed || rowBusy;
  const pagoBusy = updatingPagoId === row.id;
  const payStatus = expensePaymentStatus(row);
  const allSharesPaid = shares.length > 0 && payStatus === "paid";

  return (
    <article className="fe-txn-card">
      <button
        type="button"
        className="fe-txn-main"
        onClick={() => onOpenMenu(row)}
        aria-label={`Abrir ações: ${row.descricao}`}
      >
        <div className="fe-txn-cat-icon" aria-hidden>
          {categoryEmoji(categoryName)}
        </div>
        <div className="fe-txn-info">
          <div className="fe-txn-name">{stripInstallmentSuffix(row.descricao)}</div>
          <div className="fe-txn-meta">
            <span className="fe-txn-date">{formatDateBR(row.data)}</span>
            <span className="fe-txn-cat-tag">{categoryName}</span>
            {(() => {
              const installment = parseInstallmentSuffix(row.descricao);
              if (installment && installment.total > 1) {
                return (
                  <span className="fe-txn-parcela">
                    {installment.current}/{installment.total}
                  </span>
                );
              }
              return null;
            })()}
            {row.recorrente && <span className="fe-recurring-badge">Recorrente</span>}
          </div>
        </div>
        <div className="fe-txn-right">
          <div className="fe-txn-val">{formatBRL(row.valor)}</div>
          <span
            className={`fe-txn-status-dot${
              payStatus === "paid"
                ? " fe-txn-status-dot--pago"
                : payStatus === "partial"
                  ? " fe-txn-status-dot--parcial"
                  : " fe-txn-status-dot--pend"
            }`}
            title={
              payStatus === "paid"
                ? "Todos pagos"
                : payStatus === "partial"
                  ? "Pagamento parcial"
                  : "Pendente"
            }
            aria-hidden
          />
        </div>
      </button>
      <div className="fe-txn-persons">
        {shares.length > 0 ? (
          shares.map((s) => {
            const sharePaid = isSharePaid(s);
            return (
              <div
                key={s.spender_id}
                className={`fe-txn-person-row${sharePaid ? " fe-txn-person-row--pago" : ""}`}
              >
                <div className="fe-txn-person-left">
                  <div
                    className="fe-txn-person-av"
                    style={{ background: personGradient(s.spender_nome) }}
                    aria-hidden
                  >
                    {personInitials(s.spender_nome)}
                  </div>
                  <span className="fe-txn-person-name">{s.spender_nome}</span>
                </div>
                <span className="fe-txn-person-val">{formatBRL(s.valor)}</span>
                {!periodClosed ? (
                  <button
                    type="button"
                    className={`fe-share-status-toggle${sharePaid ? " fe-share-status-toggle--pago" : " fe-share-status-toggle--pendente"}`}
                    disabled={pagoBusy || disabled}
                    onClick={() => onSharePagoChange(row, s.spender_id, !sharePaid)}
                  >
                    {sharePaid ? "✓ Pago" : "○ Pendente"}
                  </button>
                ) : (
                  <span
                    className={`fe-share-status-toggle${sharePaid ? " fe-share-status-toggle--pago" : " fe-share-status-toggle--pendente"}`}
                  >
                    {sharePaid ? "✓ Pago" : "○ Pendente"}
                  </span>
                )}
              </div>
            );
          })
        ) : (
          <div className="fe-sem-divisao">Sem divisão entre pessoas</div>
        )}
      </div>
      {shares.length > 0 && !periodClosed && (
        <div className="fe-txn-toggle-hint">
          Clique no status de cada pessoa para marcar como pago ou pendente
        </div>
      )}
      <div className="fe-txn-person-actions fe-txn-person-actions--cols-4">
        {shares.length > 0 ? (
          !periodClosed ? (
            <button
              type="button"
              className={`fe-txn-pact-btn${allSharesPaid ? " fe-txn-pact-btn--desmarcar" : " fe-txn-pact-btn--pagar"}`}
              disabled={pagoBusy}
              onClick={() => onMarkAllShares(row, !allSharesPaid)}
            >
              {allSharesPaid ? "↺ Desmarcar todos" : "✓ Marcar todos"}
            </button>
          ) : (
            <span className="fe-txn-pact-btn fe-txn-pact-btn--placeholder" aria-hidden />
          )
        ) : !periodClosed && !row.pago ? (
          <button
            type="button"
            className="fe-txn-pact-btn fe-txn-pact-btn--pagar"
            disabled={pagoBusy}
            onClick={() => void onExpensePagoChange(row, true)}
          >
            ✓ Marcar pago
          </button>
        ) : !periodClosed && row.pago ? (
          <button
            type="button"
            className="fe-txn-pact-btn"
            disabled={pagoBusy}
            onClick={() => void onExpensePagoChange(row, false)}
          >
            ✓ Desmarcar pago
          </button>
        ) : (
          <span className="fe-txn-pact-btn fe-txn-pact-btn--placeholder" aria-hidden />
        )}
        <button
          type="button"
          className="fe-txn-pact-btn fe-txn-pact-btn--divisao"
          disabled={periodClosed}
          onClick={() => onShare(row)}
        >
          {shares.length > 0 ? (
            <>
              <span className="fe-div-badge">{shares.length}</span> Divisão
            </>
          ) : (
            <>＋ Divisão</>
          )}
        </button>
        <button
          type="button"
          className="fe-txn-pact-btn fe-txn-pact-btn--editar"
          disabled={disabled}
          onClick={() => onEdit(row)}
        >
          ✏️ Editar
        </button>
        <button
          type="button"
          className="fe-txn-pact-btn fe-txn-pact-btn--danger"
          disabled={disabled}
          onClick={() => void onDelete(row)}
        >
          🗑 Excluir
        </button>
      </div>
    </article>
  );
}

export function FixedExpenses() {
  const { periodId, ready, periodClosed, periods, monthLabel } = usePeriod();
  const { confirm, alert } = useAppDialog();
  const [rows, setRows] = useState<ExpenseRow[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [spenders, setSpenders] = useState<SpenderRow[]>([]);
  const [error, setError] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showShareForm, setShowShareForm] = useState(false);
  const [showInstallmentForm, setShowInstallmentForm] = useState(false);
  const [feMenuExpenseId, setFeMenuExpenseId] = useState<string | null>(null);
  const [shareEditingExpenseId, setShareEditingExpenseId] = useState<string | null>(null);
  const [installmentEditingExpenseId, setInstallmentEditingExpenseId] = useState<string | null>(null);
  const [installmentCurrentInput, setInstallmentCurrentInput] = useState("1");
  const [installmentTotalInput, setInstallmentTotalInput] = useState("2");
  const [savingInstallment, setSavingInstallment] = useState(false);
  const [saving, setSaving] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [updatingPagoId, setUpdatingPagoId] = useState<string | null>(null);
  const [editingExpense, setEditingExpense] = useState<ExpenseRow | null>(null);
  const [bulkAction, setBulkAction] = useState<"mark_paid" | "delete_all" | null>(null);

  const [categoriaId, setCategoriaId] = useState("");
  const [descricao, setDescricao] = useState("");
  const [valor, setValor] = useState("");
  const [data, setData] = useState(() => new Date().toISOString().slice(0, 10));
  const [pago, setPago] = useState(false);
  const [recorrente, setRecorrente] = useState(false);
  const [recurrenceValueMode, setRecurrenceValueMode] = useState<"same_value" | "blank">("same_value");
  const [shareRows, setShareRows] = useState<{ spenderId: string; valor: string }[]>([
    { spenderId: "", valor: "" },
  ]);
  const [tableCategoryFilter, setTableCategoryFilter] = useState("all");
  const [usageCategoryFilter, setUsageCategoryFilter] = useState("all");
  const [descFilter, setDescFilter] = useState("");
  const [paidFilter, setPaidFilter] = useState<"all" | "paid" | "unpaid">("all");
  const [meSpenderId, setMeSpenderId] = useState<string | null>(null);
  const [isDesktopViewport, setIsDesktopViewport] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia("(min-width: 769px)").matches : true,
  );
  const hasSpenders = spenders.length > 0;
  const categoryById = useMemo(
    () => Object.fromEntries(categories.map((c) => [c.id, c.nome])),
    [categories],
  );
  const feMenuExpense = useMemo(
    () => (feMenuExpenseId ? rows.find((x) => x.id === feMenuExpenseId) ?? null : null),
    [feMenuExpenseId, rows],
  );
  const installmentEditingExpense = useMemo(
    () =>
      installmentEditingExpenseId
        ? rows.find((x) => x.id === installmentEditingExpenseId) ?? null
        : null,
    [installmentEditingExpenseId, rows],
  );

  async function load() {
    if (!periodId) {
      setRows([]);
      return;
    }
    const [allExpenses, expenseCategories, people] = await Promise.all([
      api.listExpenses(periodId),
      api.categories("expense"),
      api.listSpenders().catch(() => []),
    ]);
    const fixedRows = allExpenses
      .filter((e) => e.tipo === "fixed")
      .sort((a, b) =>
        a.data === b.data ? b.created_at.localeCompare(a.created_at) : b.data.localeCompare(a.data),
      );
    setRows(fixedRows);
    setCategories(expenseCategories);
    setSpenders(people);
    setCategoriaId((prev) => prev || expenseCategories[0]?.id || "");
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setError("");
        await load();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Erro ao carregar gastos fixos");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [periodId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await api.getMe();
        if (!cancelled) setMeSpenderId(me.me_spender_id ?? null);
      } catch {
        if (!cancelled) setMeSpenderId(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 769px)");
    const sync = () => setIsDesktopViewport(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (!showCreateModal && !showShareForm && !showInstallmentForm && !feMenuExpenseId) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (showInstallmentForm) {
        if (!savingInstallment) closeInstallmentModal();
      } else if (showShareForm) {
        closeShareModal();
      } else if (feMenuExpenseId) {
        setFeMenuExpenseId(null);
      } else {
        closeModal();
      }
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [showCreateModal, showShareForm, showInstallmentForm, feMenuExpenseId, savingInstallment]);

  const effectiveUsageCategoryFilter = isDesktopViewport ? usageCategoryFilter : "all";

  const total = useMemo(() => rows.reduce((acc, row) => acc + parseFloat(row.valor), 0), [rows]);
  const totalPaid = useMemo(() => {
    if (!meSpenderId) return 0;
    return rows.reduce((acc, row) => {
      const shares = row.shares ?? [];
      if (shares.length === 0) return acc;
      const mine = shares.find((s) => s.spender_id === meSpenderId);
      if (!mine || !isSharePaid(mine)) return acc;
      return acc + (parseFloat(mine.valor) || 0);
    }, 0);
  }, [rows, meSpenderId]);
  const totalPending = useMemo(() => {
    if (!meSpenderId) return 0;
    return rows.reduce((acc, row) => {
      const shares = row.shares ?? [];
      if (shares.length === 0) return acc;
      const mine = shares.find((s) => s.spender_id === meSpenderId);
      if (!mine || isSharePaid(mine)) return acc;
      return acc + (parseFloat(mine.valor) || 0);
    }, 0);
  }, [rows, meSpenderId]);
  const recurringCount = useMemo(() => rows.filter((row) => row.recorrente).length, [rows]);
  const periodLabel = useMemo(() => {
    const p = periods.find((x) => x.id === periodId);
    return p ? monthLabel(p.mes, p.ano) : "—";
  }, [periodId, periods, monthLabel]);

  const visibleRows = useMemo(() => {
    const desc = descFilter.trim().toLowerCase();
    return rows.filter((r) => {
      if (tableCategoryFilter !== "all" && r.categoria_id !== tableCategoryFilter) return false;
      if (paidFilter === "paid" && !r.pago) return false;
      if (paidFilter === "unpaid" && r.pago) return false;
      if (desc && !r.descricao.toLowerCase().includes(desc)) return false;
      return true;
    });
  }, [rows, tableCategoryFilter, paidFilter, descFilter]);
  const expenseGroups = useMemo(() => {
    const groups: { label: string; items: ExpenseRow[] }[] = [];
    let currentDate = "";
    let currentItems: ExpenseRow[] = [];
    for (const row of visibleRows) {
      if (row.data !== currentDate) {
        if (currentItems.length > 0) {
          groups.push({ label: formatGroupDateLabel(currentDate), items: currentItems });
        }
        currentDate = row.data;
        currentItems = [row];
      } else {
        currentItems.push(row);
      }
    }
    if (currentItems.length > 0) {
      groups.push({ label: formatGroupDateLabel(currentDate), items: currentItems });
    }
    return groups;
  }, [visibleRows]);
  const myPendingRows = useMemo(
    () => rowsWithMyPendingShare(rows, meSpenderId),
    [rows, meSpenderId],
  );
  const myShareRows = useMemo(() => rowsWithMyShare(rows, meSpenderId), [rows, meSpenderId]);
  const rowBusy = updatingId !== null || updatingPagoId !== null || bulkAction !== null;
  const hasExtraFilters = descFilter.trim().length > 0;
  const shareEditingExpense = useMemo(
    () => (shareEditingExpenseId ? rows.find((x) => x.id === shareEditingExpenseId) ?? null : null),
    [shareEditingExpenseId, rows],
  );
  const allocatedShareTotal = useMemo(() => sumShareRows(shareRows), [shareRows]);
  const editShareTarget = useMemo(
    () => (shareEditingExpense ? parseFloat(String(shareEditingExpense.valor)) || 0 : 0),
    [shareEditingExpense],
  );
  const shareBalanceDelta = editShareTarget - allocatedShareTotal;
  const shareBalanceOk = Math.abs(shareBalanceDelta) <= 0.021;

  const usageByPerson = useMemo(() => {
    const stats = buildFixedExpensePersonStats(rows, effectiveUsageCategoryFilter);
    return [...stats.values()]
      .filter((person) => person.pending > 0)
      .sort((a, b) => {
        if (b.pending !== a.pending) return b.pending - a.pending;
        if (meSpenderId && a.id === meSpenderId) return -1;
        if (meSpenderId && b.id === meSpenderId) return 1;
        return b.usage - a.usage;
      });
  }, [rows, effectiveUsageCategoryFilter, meSpenderId]);

  function resetForm() {
    setDescricao("");
    setValor("");
    setPago(false);
    setRecorrente(false);
    setRecurrenceValueMode("same_value");
    setEditingExpense(null);
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!periodId || !categoriaId) {
      setError("Selecione período e categoria.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (editingExpense) {
        const updatePayload: Record<string, unknown> = {
          descricao,
          valor: valor.replace(",", "."),
          data,
          categoria_id: categoriaId,
          tipo: "fixed",
          pago,
          recorrente,
        };
        if (recorrente) updatePayload.recurrence_value_mode = recurrenceValueMode;
        await api.updateExpense(editingExpense.id, updatePayload);
      } else {
        const payload: Record<string, unknown> = {
          descricao,
          valor: valor.replace(",", "."),
          data,
          period_id: periodId,
          categoria_id: categoriaId,
          tipo: "fixed",
          pago,
          recorrente,
        };
        if (recorrente) payload.recurrence_value_mode = recurrenceValueMode;
        await api.createExpense(payload);
      }
      resetForm();
      setShowCreateModal(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar despesa fixa");
    } finally {
      setSaving(false);
    }
  }

  function openCreateModal() {
    resetForm();
    setData(new Date().toISOString().slice(0, 10));
    setCategoriaId((prev) => prev || categories[0]?.id || "");
    setShowCreateModal(true);
  }

  function closeModal() {
    setShowCreateModal(false);
    setEditingExpense(null);
    setError("");
  }

  function openShareModal(row: ExpenseRow) {
    setShareEditingExpenseId(row.id);
    if (row.shares && row.shares.length > 0) {
      setShareRows(row.shares.map((s) => ({ spenderId: s.spender_id, valor: s.valor.replace(".", ",") })));
    } else {
      setShareRows([{ spenderId: "", valor: "" }]);
    }
    setShowShareForm(true);
  }

  function closeShareModal() {
    setShowShareForm(false);
    setShareEditingExpenseId(null);
    setShareRows([{ spenderId: "", valor: "" }]);
  }

  function openEditModal(row: ExpenseRow) {
    setEditingExpense(row);
    setDescricao(row.descricao);
    setValor(row.valor.replace(".", ","));
    setData(row.data);
    setPago(row.pago);
    setRecorrente(row.recorrente);
    setRecurrenceValueMode("same_value");
    setCategoriaId(row.categoria_id);
    setShowCreateModal(true);
  }

  function openInstallmentModal(row: ExpenseRow) {
    const parsed = parseInstallmentSuffix(row.descricao);
    setInstallmentEditingExpenseId(row.id);
    setInstallmentCurrentInput(String(parsed?.current ?? 1));
    setInstallmentTotalInput(String(Math.max(2, parsed?.total ?? 2)));
    setShowInstallmentForm(true);
  }

  function closeInstallmentModal() {
    setShowInstallmentForm(false);
    setInstallmentEditingExpenseId(null);
    setInstallmentCurrentInput("1");
    setInstallmentTotalInput("2");
    setSavingInstallment(false);
  }

  async function onSubmitInstallment(e: React.FormEvent) {
    e.preventDefault();
    if (!installmentEditingExpense || periodClosed || savingInstallment) return;
    const current = Math.max(1, parseInt(installmentCurrentInput, 10) || 1);
    const total = Math.max(1, parseInt(installmentTotalInput, 10) || 1);
    if (total <= 1) {
      setError("Total de parcelas precisa ser maior que 1.");
      return;
    }
    if (current > total) {
      setError("Parcela atual não pode ser maior que o total.");
      return;
    }
    const currentPeriod = periods.find((p) => p.id === installmentEditingExpense.period_id);
    if (!currentPeriod) {
      setError("Período do lançamento não encontrado.");
      return;
    }

    setSavingInstallment(true);
    setError("");
    try {
      const base = stripInstallmentSuffix(installmentEditingExpense.descricao);
      const preferredDay = Number(installmentEditingExpense.data.slice(8, 10)) || 1;
      const yearsNeeded = new Set<number>();
      for (let i = 1; i <= total - current; i += 1) {
        yearsNeeded.add(addCalendarMonths(currentPeriod.ano, currentPeriod.mes, i).ano);
      }
      for (const ano of yearsNeeded) {
        await api.createYear(ano);
      }
      const allPeriods = await api.periods();
      const periodByKey = new Map(allPeriods.map((p) => [`${p.ano}-${p.mes}`, p]));

      await api.updateExpense(installmentEditingExpense.id, {
        descricao: withInstallmentSuffix(base, current, total),
        tipo: "fixed",
        recorrente: false,
      });

      const sharesPayload =
        installmentEditingExpense.shares?.map((s) => ({
          spender_id: s.spender_id,
          valor: s.valor,
          pago: false,
        })) ?? undefined;

      for (let i = 1; i <= total - current; i += 1) {
        const { ano, mes } = addCalendarMonths(currentPeriod.ano, currentPeriod.mes, i);
        const period = periodByKey.get(`${ano}-${mes}`);
        if (!period) {
          throw new Error(`Não foi possível criar o período ${String(mes).padStart(2, "0")}/${ano}.`);
        }
        if (period.status === "closed") {
          throw new Error(
            `O período ${String(mes).padStart(2, "0")}/${ano} está fechado. Reabra-o para gerar parcelas.`,
          );
        }
        const numero = current + i;
        const desc = withInstallmentSuffix(base, numero, total);
        const existingInPeriod = await api.listExpenses(period.id);
        const alreadyExists = existingInPeriod.some(
          (ex) =>
            ex.tipo === "fixed" &&
            ex.categoria_id === installmentEditingExpense.categoria_id &&
            stripInstallmentSuffix(ex.descricao) === base,
        );
        if (alreadyExists) continue;
        await api.createExpense({
          descricao: desc,
          valor: installmentEditingExpense.valor,
          data: dateInMonthIso(ano, mes, preferredDay),
          period_id: period.id,
          categoria_id: installmentEditingExpense.categoria_id,
          tipo: "fixed",
          pago: false,
          recorrente: false,
          ...(sharesPayload && sharesPayload.length > 0 ? { shares: sharesPayload } : {}),
        });
      }

      await load();
      closeInstallmentModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao definir parcelas");
    } finally {
      setSavingInstallment(false);
    }
  }

  async function removeExpense(row: ExpenseRow) {
    const ok = await confirm({
      title: "Excluir despesa",
      message: `Excluir a despesa fixa "${row.descricao}"?`,
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    setUpdatingId(row.id);
    setError("");
    try {
      await api.deleteExpense(row.id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao excluir despesa");
    } finally {
      setUpdatingId(null);
    }
  }

  async function onExpensePagoChange(row: ExpenseRow, nextPago: boolean) {
    if (periodClosed || row.pago === nextPago) return;
    setUpdatingPagoId(row.id);
    setError("");
    try {
      await api.setExpensePaid(row.id, nextPago);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao atualizar status de pagamento");
    } finally {
      setUpdatingPagoId(null);
    }
  }

  async function onSharePagoChange(row: ExpenseRow, spenderId: string, nextPago: boolean) {
    if (periodClosed) return;
    setUpdatingPagoId(row.id);
    setError("");
    try {
      const updated = await api.setExpenseSharePaid(row.id, spenderId, nextPago);
      setRows((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao atualizar status da pessoa");
    } finally {
      setUpdatingPagoId(null);
    }
  }

  async function onMarkAllShares(row: ExpenseRow, nextPago: boolean) {
    if (periodClosed) return;
    setUpdatingPagoId(row.id);
    setError("");
    try {
      const updated = await api.setExpensePaid(row.id, nextPago);
      setRows((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao atualizar status de pagamento");
    } finally {
      setUpdatingPagoId(null);
    }
  }

  async function markAllPaid() {
    if (!meSpenderId) {
      await alert("Marque uma pessoa como Titular em Pessoas para usar esta ação.");
      return;
    }
    if (myPendingRows.length === 0) {
      await alert("Não há pendências da sua parte neste período.");
      return;
    }
    const ok = await confirm({
      title: "Marcar como pago",
      message: `Marcar sua parte como paga em ${myPendingRows.length} lançamento(s)?`,
      confirmLabel: "Marcar como pago",
    });
    if (!ok) return;
    setBulkAction("mark_paid");
    setError("");
    try {
      await Promise.all(
        myPendingRows.map((row) => api.setExpenseSharePaid(row.id, meSpenderId, true)),
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao marcar sua parte como paga");
    } finally {
      setBulkAction(null);
    }
  }

  async function deleteAllExpenses() {
    if (!meSpenderId) {
      await alert('Marque uma pessoa como "eu" em Pessoas para usar esta ação.');
      return;
    }
    if (myShareRows.length === 0) {
      await alert("Não há lançamentos com a sua parte neste período.");
      return;
    }
    const ok = await confirm({
      title: "Apagar tudo",
      message: `Remover sua parte de ${myShareRows.length} lançamento(s)? Despesas divididas permanecem só com as outras pessoas. Esta ação não pode ser desfeita.`,
      confirmLabel: "Apagar tudo",
      danger: true,
    });
    if (!ok) return;
    setBulkAction("delete_all");
    setError("");
    try {
      await Promise.all(myShareRows.map((row) => removeMyShareFromExpense(row, meSpenderId)));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao remover sua parte dos lançamentos");
    } finally {
      setBulkAction(null);
    }
  }

  async function onSubmitShare(e: React.FormEvent) {
    e.preventDefault();
    if (!shareEditingExpense || periodClosed) return;
    setSaving(true);
    setError("");
    try {
      const totalValue = String(shareEditingExpense.valor).replace(".", ",");
      const preparedRows = prepareShareRowsForSubmit(shareRows, totalValue);
      const existingPago = new Map(
        (shareEditingExpense.shares ?? []).map((s) => [s.spender_id, s.pago === true]),
      );
      const sharesPayload = (resolveSharesPayload(true, totalValue, preparedRows) ?? []).map((s) => ({
        ...s,
        pago: existingPago.get(s.spender_id) ?? false,
      }));
      await api.updateExpense(shareEditingExpense.id, { shares: sharesPayload, tipo: "fixed" });
      await load();
      closeShareModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar divisão");
    } finally {
      setSaving(false);
    }
  }

  const bulkDisabled =
    !ready || !periodId || periodClosed || bulkAction !== null || updatingId !== null || updatingPagoId !== null;

  return (
    <div className="padded fixed-expenses-page">
      <div className="fe-page-header">
        <div>
          <h1>Gastos fixos</h1>
          <span className="fe-page-period">Período: {periodLabel}</span>
        </div>
        <button
          type="button"
          className="fe-btn-primary"
          onClick={openCreateModal}
          disabled={!ready || !periodId || periodClosed}
        >
          <span className="fe-cta-label fe-cta-label--short">+ Lançar</span>
          <span className="fe-cta-label fe-cta-label--full">＋ Lançar despesa fixa</span>
        </button>
      </div>
      {periodClosed && (
        <p className="error">Este mês está fechado. Reabra o período para lançar despesas fixas.</p>
      )}
      {error && <p className="error">{error}</p>}

      <div className="fe-stats-grid" role="group" aria-label="Resumo do período">
        <div className="fe-stat-card fe-stat-card--total">
          <span className="fe-stat-label">Total no período</span>
          <span className="fe-stat-value">{formatBRL(total)}</span>
        </div>
        <div className="fe-stat-card fe-stat-card--launches">
          <span className="fe-stat-label">Lançamentos</span>
          <span className="fe-stat-value fe-stat-value--accent">{rows.length}</span>
        </div>
        <div className="fe-stat-card fe-stat-card--paid">
          <span className="fe-stat-label">Pago</span>
          <span className="fe-stat-value fe-stat-value--green">{formatBRL(totalPaid)}</span>
        </div>
        <div className="fe-stat-card fe-stat-card--pending">
          <span className="fe-stat-label">Pendente</span>
          <span className="fe-stat-value fe-stat-value--amber">{formatBRL(totalPending)}</span>
        </div>
        <div className="fe-stat-card fe-stat-card--recurring">
          <span className="fe-stat-label">Recorrentes</span>
          <span className="fe-stat-value fe-stat-value--muted">{recurringCount}</span>
        </div>
      </div>

      <section aria-label="Uso por pessoa">
        <div className="fe-usage-head">
          <h2 className="fe-section-title" style={{ margin: 0 }}>
            Uso por pessoa
          </h2>
          <select
            className="fe-select fe-desktop-only"
            value={usageCategoryFilter}
            onChange={(e) => setUsageCategoryFilter(e.target.value)}
            aria-label="Filtrar uso por categoria"
          >
            <option value="all">Todas as categorias</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
              </option>
            ))}
          </select>
        </div>
        {usageByPerson.length === 0 ? (
          <p className="fe-usage-empty">
            Nenhuma pessoa com valor pendente neste período/categoria.
          </p>
        ) : (
          <div
            className={`fe-people-row${usageByPerson.length === 1 ? " fe-people-row--single" : ""}`}
          >
            {usageByPerson.map((person) => (
              <div
                key={person.id}
                className={`fe-person-card ${personCardClass(person.name)}`}
              >
                <div className="fe-person-name">{person.name}</div>
                <div className="fe-person-meta">
                  Uso {formatBRL(person.usage.toFixed(2))} / Pendente{" "}
                  {formatBRL(person.pending.toFixed(2))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="fe-lancamentos-section" aria-label="Lançamentos no período">
        <div className="fe-table-header">
          <h2 className="fe-section-title" style={{ margin: 0 }}>
            Lançamentos no período
          </h2>
          <div className="fe-table-header__actions">
            <select
              className="fe-select"
              value={tableCategoryFilter}
              onChange={(e) => setTableCategoryFilter(e.target.value)}
              aria-label="Filtrar por categoria"
            >
              <option value="all">Todas</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
            <div className="fe-bulk-actions">
              <button
                type="button"
                className="fe-btn-outline"
                onClick={() => void markAllPaid()}
                disabled={bulkDisabled || !meSpenderId || myPendingRows.length === 0}
              >
                {bulkAction === "mark_paid" ? "Marcando…" : "✓ Marcar como pago"}
              </button>
              <button
                type="button"
                className="fe-btn-outline fe-btn-outline--danger"
                onClick={() => void deleteAllExpenses()}
                disabled={bulkDisabled || !meSpenderId || myShareRows.length === 0}
              >
                {bulkAction === "delete_all" ? "Apagando…" : "🗑 Apagar tudo"}
              </button>
            </div>
          </div>
        </div>

        <details className="fe-more-filters">
          <summary>Mais filtros{hasExtraFilters ? " (ativos)" : ""}</summary>
          <div className="fe-more-filters__body">
            <div className="fe-filter-chips" role="group" aria-label="Filtrar por pagamento">
              <button
                type="button"
                className={`fe-filter-chip${paidFilter === "all" ? " fe-filter-chip--active" : ""}`}
                onClick={() => setPaidFilter("all")}
              >
                Todos
              </button>
              <button
                type="button"
                className={`fe-filter-chip fe-filter-chip--unpaid${paidFilter === "unpaid" ? " fe-filter-chip--active" : ""}`}
                onClick={() => setPaidFilter("unpaid")}
              >
                Não pagos
              </button>
              <button
                type="button"
                className={`fe-filter-chip fe-filter-chip--paid${paidFilter === "paid" ? " fe-filter-chip--active" : ""}`}
                onClick={() => setPaidFilter("paid")}
              >
                Pagos
              </button>
            </div>
            <input
              value={descFilter}
              onChange={(e) => setDescFilter(e.target.value)}
              placeholder="Filtrar descrição"
              className="fe-filter-search"
              aria-label="Filtrar por descrição"
            />
            <button
              type="button"
              className="fe-btn-outline"
              onClick={() => {
                setDescFilter("");
                setPaidFilter("all");
                setTableCategoryFilter("all");
              }}
            >
              Limpar filtros
            </button>
          </div>
        </details>

        <p className="fe-filter-count" aria-live="polite">
          Exibindo {visibleRows.length} de {rows.length} lançamento(s).
        </p>

        {!ready ? (
          <p className="fe-empty-msg">Carregando…</p>
        ) : rows.length === 0 ? (
          <p className="fe-empty-msg">Nenhum gasto fixo neste período.</p>
        ) : visibleRows.length === 0 ? (
          <p className="fe-empty-msg">Nenhum lançamento corresponde aos filtros selecionados.</p>
        ) : (
          <div className="fe-txn-list" aria-label="Lançamentos">
            {expenseGroups.map((group) => (
              <div key={group.label}>
                <div className="fe-txn-group-label">{group.label}</div>
                {group.items.map((r) => (
                  <FixedExpenseRow
                    key={r.id}
                    row={r}
                    categoryName={categoryById[r.categoria_id] ?? "Sem categoria"}
                    periodClosed={periodClosed}
                    rowBusy={rowBusy}
                    updatingPagoId={updatingPagoId}
                    onOpenMenu={(row) => setFeMenuExpenseId(row.id)}
                    onEdit={openEditModal}
                    onDelete={(row) => void removeExpense(row)}
                    onShare={openShareModal}
                    onExpensePagoChange={(row, nextPago) => void onExpensePagoChange(row, nextPago)}
                    onSharePagoChange={(row, spenderId, nextPago) =>
                      void onSharePagoChange(row, spenderId, nextPago)
                    }
                    onMarkAllShares={(row, nextPago) => void onMarkAllShares(row, nextPago)}
                  />
                ))}
              </div>
            ))}
          </div>
        )}
      </section>

      {feMenuExpenseId && feMenuExpense && (() => {
        const txMenuCat = categoryById[feMenuExpense.categoria_id] ?? "Sem categoria";
        const installment = parseInstallmentSuffix(feMenuExpense.descricao);
        return (
          <div
            className="fe-lanc-modal-overlay"
            role="presentation"
            onClick={(e) => {
              if (e.target === e.currentTarget) setFeMenuExpenseId(null);
            }}
          >
            <div
              className="fe-lanc-modal fe-lanc-modal--mais"
              role="dialog"
              aria-modal="true"
              aria-labelledby="fe-tx-menu-title"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="fe-lanc-modal-header">
                <div id="fe-tx-menu-title" className="fe-lanc-modal-title">
                  Lançamento
                </div>
                <button
                  type="button"
                  className="fe-lanc-modal-close"
                  aria-label="Fechar"
                  onClick={() => setFeMenuExpenseId(null)}
                >
                  ✕
                </button>
              </div>
              <div className="fe-lanc-modal-body fe-lanc-modal-body--mais">
                <div className="fe-lanc-mais-txn-info">
                  <span className="fe-lanc-mais-txn-icon" aria-hidden>
                    {categoryEmoji(txMenuCat) || "📌"}
                  </span>
                  <div>
                    <div className="fe-lanc-mais-txn-name">
                      {stripInstallmentSuffix(feMenuExpense.descricao)}
                    </div>
                    <div className="fe-lanc-mais-txn-meta">
                      {txMenuCat} · {formatDateBR(feMenuExpense.data)}
                      {installment && installment.total > 1
                        ? ` · Parcela ${installment.current}/${installment.total}`
                        : feMenuExpense.recorrente
                          ? " · Recorrente"
                          : ""}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  className="fe-lanc-mais-item fe-lanc-mais-item--primary"
                  disabled={periodClosed}
                  onClick={() => {
                    setFeMenuExpenseId(null);
                    openEditModal(feMenuExpense);
                  }}
                >
                  <div className="fe-lanc-mais-icon" aria-hidden>
                    ✏️
                  </div>
                  <div>
                    <div className="fe-lanc-mais-label">Editar</div>
                    <div className="fe-lanc-mais-sub">Alterar categoria, valor ou descrição</div>
                  </div>
                </button>
                <button
                  type="button"
                  className="fe-lanc-mais-item fe-lanc-mais-item--neutral"
                  disabled={periodClosed}
                  onClick={() => {
                    setFeMenuExpenseId(null);
                    openShareModal(feMenuExpense);
                  }}
                >
                  <div className="fe-lanc-mais-icon" aria-hidden>
                    👥
                  </div>
                  <div>
                    <div className="fe-lanc-mais-label">Divisão entre pessoas</div>
                    <div className="fe-lanc-mais-sub">Definir quem paga quanto</div>
                  </div>
                </button>
                <button
                  type="button"
                  className="fe-lanc-mais-item fe-lanc-mais-item--warning"
                  disabled={periodClosed}
                  onClick={() => {
                    setFeMenuExpenseId(null);
                    openInstallmentModal(feMenuExpense);
                  }}
                >
                  <div className="fe-lanc-mais-icon" aria-hidden>
                    📦
                  </div>
                  <div>
                    <div className="fe-lanc-mais-label">
                      {installment && installment.total > 1
                        ? `Parcela ${installment.current}/${installment.total}`
                        : "Parcelas"}
                    </div>
                    <div className="fe-lanc-mais-sub">Gerenciar parcelas deste lançamento</div>
                  </div>
                </button>
                <div className="fe-lanc-mais-divider" />
                <button
                  type="button"
                  className="fe-lanc-mais-item fe-lanc-mais-item--danger"
                  disabled={periodClosed}
                  onClick={() => {
                    setFeMenuExpenseId(null);
                    void removeExpense(feMenuExpense);
                  }}
                >
                  <div className="fe-lanc-mais-icon" aria-hidden>
                    🗑️
                  </div>
                  <div>
                    <div className="fe-lanc-mais-label">Excluir</div>
                    <div className="fe-lanc-mais-sub">Remove este lançamento permanentemente</div>
                  </div>
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {showCreateModal && (
        <div
          className="fe-lanc-modal-overlay"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowCreateModal(false);
          }}
        >
          <div
            className="fe-lanc-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-fixed-expense-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="fe-lanc-modal-header">
              <div className="fe-lanc-modal-title-row">
                <div className="fe-lanc-modal-icon" aria-hidden>
                  📌
                </div>
                <h2 id="create-fixed-expense-modal-title" className="fe-lanc-modal-title">
                  {editingExpense ? "Editar despesa fixa" : "Nova despesa fixa"}
                </h2>
              </div>
              <button
                type="button"
                className="fe-lanc-modal-close"
                aria-label="Fechar"
                onClick={closeModal}
              >
                ✕
              </button>
            </div>
            <form onSubmit={onCreate} className="fe-lanc-modal-form">
              <div className="fe-lanc-modal-body">
                <div className="fe-lanc-form-group">
                  <label className="fe-lanc-form-label" htmlFor="fe-lanc-categoria">
                    Categoria
                  </label>
                  <select
                    id="fe-lanc-categoria"
                    className="fe-lanc-form-select"
                    value={categoriaId}
                    onChange={(e) => setCategoriaId(e.target.value)}
                    required
                    disabled={categories.length === 0 || periodClosed}
                  >
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nome}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="fe-lanc-form-group">
                  <label className="fe-lanc-form-label" htmlFor="fe-lanc-descricao">
                    Descrição
                  </label>
                  <input
                    id="fe-lanc-descricao"
                    className="fe-lanc-form-input"
                    type="text"
                    value={descricao}
                    onChange={(e) => setDescricao(e.target.value)}
                    placeholder="Ex: Aluguel, Internet, Água…"
                    required
                    disabled={periodClosed}
                  />
                </div>
                <div className="fe-lanc-form-row">
                  <div className="fe-lanc-form-group">
                    <label className="fe-lanc-form-label" htmlFor="fe-lanc-valor">
                      Valor (R$)
                    </label>
                    <div className="fe-lanc-input-prefix-wrap">
                      <span className="fe-lanc-input-prefix">R$</span>
                      <input
                        id="fe-lanc-valor"
                        className="fe-lanc-form-input fe-lanc-form-input--mono fe-lanc-form-input--with-prefix"
                        inputMode="decimal"
                        value={valor}
                        onChange={(e) => setValor(e.target.value)}
                        placeholder="0,00"
                        required
                        disabled={periodClosed}
                      />
                    </div>
                  </div>
                  <div className="fe-lanc-form-group">
                    <label className="fe-lanc-form-label" htmlFor="fe-lanc-data">
                      Data
                    </label>
                    <input
                      id="fe-lanc-data"
                      className="fe-lanc-form-input"
                      type="date"
                      value={data}
                      onChange={(e) => setData(e.target.value)}
                      required
                      disabled={periodClosed}
                    />
                  </div>
                </div>
                <div className="fe-lanc-checks-group">
                  <button
                    type="button"
                    className={`fe-lanc-check-row${pago ? " fe-lanc-check-row--on" : ""}`}
                    disabled={periodClosed}
                    onClick={() => setPago((v) => !v)}
                  >
                    <div className="fe-lanc-chk" aria-hidden />
                    <div>
                      <div className="fe-lanc-check-label">Já pago</div>
                      <div className="fe-lanc-check-sub">Marcar este lançamento como pago</div>
                    </div>
                  </button>
                  <button
                    type="button"
                    className={`fe-lanc-check-row${recorrente ? " fe-lanc-check-row--on" : ""}`}
                    disabled={periodClosed}
                    onClick={() => setRecorrente((v) => !v)}
                  >
                    <div className="fe-lanc-chk" aria-hidden />
                    <div>
                      <div className="fe-lanc-check-label">Recorrente</div>
                      <div className="fe-lanc-check-sub">Replicar nos meses seguintes automaticamente</div>
                    </div>
                  </button>
                </div>
              </div>
              <div className="fe-lanc-modal-footer">
                <button type="submit" className="fe-lanc-btn-save" disabled={saving || periodClosed}>
                  {saving
                    ? "Salvando…"
                    : editingExpense
                      ? "💾 Salvar alterações"
                      : "💾 Salvar despesa fixa"}
                </button>
                <button type="button" className="fe-lanc-btn-cancel" onClick={closeModal}>
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showShareForm && shareEditingExpense && (
        <div
          className="fe-lanc-modal-overlay"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeShareModal();
          }}
        >
          <div
            className="fe-lanc-modal fe-div-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="fixed-expense-share-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="fe-lanc-modal-header">
              <div className="fe-lanc-modal-title-row">
                <div className="fe-div-modal-icon" aria-hidden>
                  👥
                </div>
                <h2 id="fixed-expense-share-modal-title" className="fe-lanc-modal-title">
                  Divisão entre pessoas
                </h2>
              </div>
              <button
                type="button"
                className="fe-lanc-modal-close"
                aria-label="Fechar"
                onClick={closeShareModal}
              >
                ✕
              </button>
            </div>
            <div className="fe-div-txn-info">
              <span className="fe-div-txn-icon" aria-hidden>
                {categoryEmoji(categoryById[shareEditingExpense.categoria_id] ?? "")}
              </span>
              <span className="fe-div-txn-name">{shareEditingExpense.descricao}</span>
              <span className="fe-div-txn-date">{formatDateBR(shareEditingExpense.data)}</span>
              <span className="fe-div-txn-val">{formatBRL(shareEditingExpense.valor)}</span>
            </div>
            <form onSubmit={onSubmitShare} className="fe-lanc-modal-form">
              <div className="fe-lanc-modal-body">
                <p className="fe-div-hint">
                  <Link to="/cartoes/pessoas">Cadastrar pessoas</Link> · A soma das partes precisa bater com o
                  total do lançamento.
                </p>
                <div className={`fe-saldo-row${shareBalanceOk ? " fe-saldo-ok" : " fe-saldo-err"}`}>
                  <span className="fe-saldo-lbl">
                    {shareBalanceOk ? "✓ Saldo fechado" : "⚠ Saldo aberto"}
                  </span>
                  <span className="fe-saldo-vals">
                    Soma: {formatBRL(allocatedShareTotal.toFixed(2))} · Total:{" "}
                    {formatBRL(editShareTarget.toFixed(2))}
                  </span>
                </div>
                <div className="fe-div-rows">
                  {shareRows.map((row, idx) => {
                    const spender = spenders.find((s) => s.id === row.spenderId);
                    const spenderName = spender?.nome ?? "";
                    const rowVal = parseFloat(row.valor.replace(",", ".")) || 0;
                    const pct =
                      editShareTarget > 0 ? Math.round((rowVal / editShareTarget) * 100) : 0;
                    return (
                      <div key={idx} className="fe-div-row">
                        <div
                          className="fe-div-av"
                          style={{ background: personGradient(spenderName || "?") }}
                          aria-hidden
                        >
                          {spenderName ? personInitials(spenderName) : "?"}
                        </div>
                        <div className="fe-div-select-wrap">
                          <select
                            className="fe-div-select"
                            value={row.spenderId}
                            onChange={(e) => {
                              const v = e.target.value;
                              setShareRows((rowsDraft) =>
                                autoSplitRowsOnPersonSelect(
                                  rowsDraft,
                                  idx,
                                  v,
                                  String(shareEditingExpense.valor).replace(".", ","),
                                ),
                              );
                            }}
                            disabled={!hasSpenders || periodClosed || saving}
                            aria-label={`Pessoa ${idx + 1}`}
                          >
                            <option value="">Selecione a pessoa</option>
                            {spenders.map((s) => (
                              <option key={s.id} value={s.id}>
                                {s.nome}
                              </option>
                            ))}
                          </select>
                        </div>
                        <span className="fe-div-pct-badge">{pct}%</span>
                        <input
                          className="fe-div-input"
                          value={row.valor}
                          onChange={(e) => {
                            const v = decimalPointToComma(e.target.value);
                            setShareRows((rowsDraft) =>
                              rowsDraft.map((x, i) => (i === idx ? { ...x, valor: v } : x)),
                            );
                          }}
                          placeholder="0,00"
                          disabled={periodClosed || saving}
                          inputMode="decimal"
                          aria-label={`Valor parte ${idx + 1}`}
                        />
                        <button
                          type="button"
                          className="fe-div-del"
                          onClick={() =>
                            setShareRows((rowsDraft) => {
                              const next = rowsDraft.filter((_, i) => i !== idx);
                              return next.length === 0 ? [{ spenderId: "", valor: "" }] : next;
                            })
                          }
                          disabled={periodClosed || saving}
                          aria-label={`Excluir linha ${idx + 1}`}
                        >
                          ✕
                        </button>
                      </div>
                    );
                  })}
                </div>
                <div className="fe-div-actions">
                  <button
                    type="button"
                    className="fe-div-btn-add"
                    onClick={() => setShareRows((r) => [...r, { spenderId: "", valor: "" }])}
                    disabled={!hasSpenders || periodClosed || saving}
                  >
                    ＋ Linha
                  </button>
                  <button
                    type="button"
                    className="fe-div-btn-recalc"
                    onClick={() =>
                      setShareRows((rowsDraft) =>
                        rebalanceShareRows(
                          rowsDraft,
                          String(shareEditingExpense.valor).replace(".", ","),
                        ),
                      )
                    }
                    disabled={!hasSpenders || periodClosed || saving}
                  >
                    ⟳ Recalcular partes iguais
                  </button>
                </div>
                <p className="fe-div-remove-hint">
                  Excluir todas as linhas e salvar remove a divisão deste lançamento.
                </p>
              </div>
              <div className="fe-lanc-modal-footer">
                <button type="submit" className="fe-lanc-btn-save" disabled={periodClosed || saving}>
                  {saving ? "Salvando…" : "💾 Salvar divisão"}
                </button>
                <button
                  type="button"
                  className="fe-lanc-btn-cancel"
                  onClick={closeShareModal}
                  disabled={saving}
                >
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showInstallmentForm && installmentEditingExpense && (
        <div
          className="fe-lanc-modal-overlay"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget && !savingInstallment) closeInstallmentModal();
          }}
        >
          <div
            className="fe-lanc-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="fe-installment-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="fe-lanc-modal-header">
              <div id="fe-installment-modal-title" className="fe-lanc-modal-title">
                Definir parcelas
              </div>
              <button
                type="button"
                className="fe-lanc-modal-close"
                aria-label="Fechar"
                disabled={savingInstallment}
                onClick={() => closeInstallmentModal()}
              >
                ✕
              </button>
            </div>
            <form onSubmit={onSubmitInstallment} className="fe-lanc-modal-form">
              <div className="fe-lanc-modal-body">
                <div className="fe-lanc-mais-txn-info">
                  <span className="fe-lanc-mais-txn-icon" aria-hidden>
                    📦
                  </span>
                  <div>
                    <div className="fe-lanc-mais-txn-name">
                      {stripInstallmentSuffix(installmentEditingExpense.descricao)}
                    </div>
                    <div className="fe-lanc-mais-txn-meta">
                      {(() => {
                        const parsed = parseInstallmentSuffix(installmentEditingExpense.descricao);
                        return parsed
                          ? `Parcela atual: ${parsed.current}/${parsed.total}`
                          : `Valor da parcela: ${formatBRL(installmentEditingExpense.valor)}`;
                      })()}
                    </div>
                  </div>
                </div>
                <div className="fe-lanc-form-row">
                  <div className="fe-lanc-form-group">
                    <label className="fe-lanc-form-label" htmlFor="fe-installment-current">
                      Parcela atual
                    </label>
                    <input
                      id="fe-installment-current"
                      className="fe-lanc-form-input"
                      type="number"
                      min={1}
                      max={120}
                      value={installmentCurrentInput}
                      onChange={(e) => setInstallmentCurrentInput(e.target.value)}
                      disabled={savingInstallment}
                      required
                    />
                  </div>
                  <div className="fe-lanc-form-group">
                    <label className="fe-lanc-form-label" htmlFor="fe-installment-total">
                      Total de parcelas
                    </label>
                    <input
                      id="fe-installment-total"
                      className="fe-lanc-form-input"
                      type="number"
                      min={2}
                      max={120}
                      value={installmentTotalInput}
                      onChange={(e) => setInstallmentTotalInput(e.target.value)}
                      disabled={savingInstallment}
                      required
                    />
                  </div>
                </div>
                <p className="fe-lanc-mais-txn-meta">
                  O valor atual é tratado como valor da parcela. As próximas parcelas serão criadas
                  nos meses seguintes com o mesmo valor e divisão.
                </p>
              </div>
              <div className="fe-lanc-modal-footer">
                <button
                  type="submit"
                  className="fe-lanc-btn-save"
                  disabled={periodClosed || savingInstallment}
                >
                  {savingInstallment ? "Salvando…" : "Salvar parcelas"}
                </button>
                <button
                  type="button"
                  className="fe-lanc-btn-cancel"
                  onClick={() => closeInstallmentModal()}
                  disabled={savingInstallment}
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
