import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { CategoryExpensesChart, CATEGORY_CHART_COLORS } from "../components/CategoryExpensesChart";
import { api } from "../api";
import { useAppDialog } from "../context/DialogContext";
import { usePeriod } from "../context/PeriodContext";
import { parseBrazilianMoney } from "../parseCardCsv";
import type { ImportFormatTab } from "../statementFormats";
import {
  defaultImportFormatTab,
  isItauAzulCard,
  isItauPdaCard,
  isNubankCard,
  isSantanderCard,
  statementFormatForTab,
  statementFormatOptionsForCard,
} from "../statementFormats";
import type {
  CardRow,
  CardSpenderSummary,
  CardSpenderSummaryGroup,
  CardTransactionRow,
  Category,
  SpenderRow,
} from "../types";
import { availableCardLimit, formatBRL } from "../money";
import {
  buildPreviewSession,
  findCarCategoryId,
  shouldSuggestCarCategory,
} from "../statementImportUtils";
import { IMPORT_PREVIEW_STORAGE_KEY } from "../statementImportTypes";
import {
  autoSplitRowsOnPersonSelect,
  decimalPointToComma,
  prepareShareRowsForSubmit,
  rebalanceShareRows,
  resolveSharesPayload,
  shareBalanceGap,
  shareBalanceStatus,
  sumShareRows,
} from "../shareSplit";

function displayCardDescription(desc: string): string {
  const s0 = desc.trim();
  const patterns = [
    /\s*[-–—]\s*Parcela\s+(\d{1,3})\s*\/\s*(\d{1,3})\s*$/i,
    /\s*\(\s*Parcela\s+(\d{1,3})\s*\/\s*(\d{1,3})\s*\)\s*$/i,
    /\s*\(\s*(\d{1,3})\s*\/\s*(\d{1,3})\s*\)\s*$/,
  ];
  for (const pattern of patterns) {
    const m = s0.match(pattern);
    if (!m) continue;
    const atual = parseInt(m[1]!, 10);
    const total = parseInt(m[2]!, 10);
    if (atual < 1 || total < 1 || atual > total) continue;
    const clean = s0.replace(pattern, "").trim();
    return clean || s0;
  }
  let s2 = s0.replace(/\s*\(\s*Parcela\s+(\d{1,3})\s*\/\s*(\d{1,3})\s*\)/gi, "");
  s2 = s2.replace(/\s*[-–—]\s*Parcela\s+(\d{1,3})\s*\/\s*(\d{1,3})\s*$/i, "");
  s2 = s2.replace(/\s*\(\s*(\d{1,3})\s*\/\s*(\d{1,3})\s*\)\s*$/, "");
  const out = s2.trim();
  return out || s0;
}

function isSharePaid(share: { pago?: boolean }): boolean {
  return share.pago === true;
}

function txPaymentStatus(tx: CardTransactionRow): "paid" | "partial" | "pending" {
  const shares = tx.shares ?? [];
  if (shares.length === 0) return tx.pago ? "paid" : "pending";
  const paidCount = shares.filter((s) => isSharePaid(s)).length;
  if (paidCount === shares.length) return "paid";
  if (paidCount === 0) return "pending";
  return "partial";
}

function defaultPurchaseDate(mes: number, ano: number): string {
  const now = new Date();
  if (now.getFullYear() === ano && now.getMonth() + 1 === mes) {
    return now.toISOString().slice(0, 10);
  }
  return `${ano}-${String(mes).padStart(2, "0")}-01`;
}

function parseInstallmentInput(raw: string): { total: number; current: number | null; fromFraction: boolean } {
  const t = raw.trim();
  const m = t.match(/^(\d{1,3})\s*\/\s*(\d{1,3})$/);
  if (m) {
    const current = Math.max(1, parseInt(m[1], 10) || 1);
    const total = Math.max(1, parseInt(m[2], 10) || 1);
    if (current <= total) {
      return { total, current, fromFraction: true };
    }
  }
  const total = Math.max(1, parseInt(t, 10) || 1);
  return { total, current: null, fromFraction: false };
}

function formatDateBR(isoDate: string): string {
  if (!isoDate) return "—";
  const [y, m, d] = isoDate.split("-");
  if (!y || !m || !d) return isoDate;
  return `${d}/${m}/${y}`;
}

function formatShortDateBR(isoDate: string): string {
  if (!isoDate) return "—";
  const [, m, d] = isoDate.split("-");
  if (!m || !d) return isoDate;
  return `${d}/${m}`;
}

const IMPORT_PROGRESS_STEPS = [
  { w: 20, t: "Lendo arquivo…" },
  { w: 45, t: "Identificando lançamentos…" },
  { w: 70, t: "Categorizando automaticamente…" },
  { w: 90, t: "Preparando revisão…" },
] as const;

function importFileExtensionOk(file: File, tab: ImportFormatTab): boolean {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (tab === "pdf") return ext === "pdf";
  return ext === "csv" || ext === "txt";
}

function formatImportFileSize(bytes: number): string {
  const kb = Math.round(bytes / 1024);
  return `${kb} KB`;
}

function importFormatInfo(
  card: CardRow | null,
  tab: ImportFormatTab,
): { title: string; items: string[] } {
  if (tab === "pdf") {
    return {
      title: "Sobre importação via PDF:",
      items: [
        "PDFs podem ter leitura inconsistente dependendo do banco",
        "Prefira CSV sempre que possível — mais preciso",
        "PDFs protegidos por senha não são suportados",
        "Em caso de erro, tente exportar novamente pelo app do banco",
      ],
    };
  }
  if (isNubankCard(card)) {
    return {
      title: "Como exportar o CSV do Nubank:",
      items: [
        "Abra o app Nubank → Cartão de crédito",
        "Toque na fatura fechada desejada",
        'Toque em "Exportar" ou "Baixar PDF/CSV"',
        "Escolha o formato CSV e envie para o computador",
      ],
    };
  }
  if (isSantanderCard(card)) {
    return {
      title: "Como exportar o CSV do Santander:",
      items: [
        "Acesse o app Santander → Cartões",
        "Abra a fatura do período desejado",
        "Exporte ou baixe o arquivo CSV da fatura",
        "Envie o arquivo para o computador",
      ],
    };
  }
  if (isItauAzulCard(card)) {
    return {
      title: "Como exportar o CSV do Itaú Azul:",
      items: [
        "Acesse o app Itaú → Cartão Azul",
        "Abra a fatura fechada desejada",
        "Exporte o CSV da fatura",
        "Envie o arquivo para o computador",
      ],
    };
  }
  if (isItauPdaCard(card)) {
    return {
      title: "Como exportar o CSV do Itaú PDA:",
      items: [
        "Acesse o app Itaú → Cartão PDA",
        "Abra a fatura fechada desejada",
        "Exporte o CSV da fatura",
        "Envie o arquivo para o computador",
      ],
    };
  }
  return {
    title: "Como exportar o CSV:",
    items: [
      "Exporte a fatura pelo app ou internet banking do banco",
      "Escolha o formato CSV quando disponível",
      "Envie o arquivo para o computador",
      "Prefira CSV em vez de PDF para maior precisão",
    ],
  };
}
const PERSON_GRADIENTS = [
  "linear-gradient(135deg,#334155,#475569)",
  "linear-gradient(135deg,#3b82f6,#22d3ee)",
  "linear-gradient(135deg,#f43f5e,#a855f7)",
  "linear-gradient(135deg,#f59e0b,#ef4444)",
  "linear-gradient(135deg,#a78bfa,#ec4899)",
  "linear-gradient(135deg,#22c55e,#16a34a)",
];

type TxSort = "recent" | "oldest" | "value_desc" | "value_asc" | "name_asc";

function formatCompactBRL(value: number): string {
  return formatBRL(value).replace(/\s/g, "").replace(",00", "");
}

function formatGroupDateLabel(isoDate: string): string {
  const d = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(d.getTime())) return isoDate;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
}

function cardStripeFromBanco(banco: string): string {
  const key = banco
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "");
  if (key.includes("nubank")) return "nubank";
  if (key.includes("santander")) return "santander";
  if (key.includes("itau")) return "itau";
  return "default";
}

function cardIconEmoji(stripe: string): string {
  if (stripe === "nubank") return "💜";
  if (stripe === "santander") return "🔴";
  if (stripe === "itau") return "🏦";
  return "💳";
}

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

function categoryEmoji(name: string): string {
  const n = name.toLowerCase();
  if (n.includes("viagem")) return "✈️";
  if (n.includes("casa")) return "🏡";
  if (n.includes("compra")) return "🛍️";
  if (n.includes("carro")) return "🚗";
  if (n.includes("conta")) return "📋";
  if (n.includes("transport")) return "🚕";
  if (n.includes("lazer")) return "🎭";
  return "🏪";
}

function categoryNameById(categories: Category[], id: string | null | undefined): string {
  if (!id) return "Sem categoria";
  return categories.find((c) => c.id === id)?.nome ?? "Outros";
}

/** Só soma valores em que há divisão e existe linha para `meId` (igual ao card da pessoa em “Uso por pessoa”). */
function valorMinhaParte(tx: CardTransactionRow, meId: string): number {
  if (!tx.shares?.length) return 0;
  const mine = tx.shares.find((s) => s.spender_id === meId);
  return mine ? parseFloat(mine.valor) || 0 : 0;
}

function valorMinhaPartePendente(tx: CardTransactionRow, meId: string): number {
  if (!tx.shares?.length) return 0;
  const mine = tx.shares.find((s) => s.spender_id === meId);
  if (!mine || isSharePaid(mine)) return 0;
  return parseFloat(mine.valor) || 0;
}

export function CardDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { periodId, setPeriodId, ready, periods, monthLabel, periodClosed, currentPeriod } = usePeriod();
  const { confirm: askConfirm } = useAppDialog();
  const [card, setCard] = useState<CardRow | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [txs, setTxs] = useState<CardTransactionRow[]>([]);
  const [invoice, setInvoice] = useState<string>("");
  const [lifetimeSpentTotal, setLifetimeSpentTotal] = useState<string>("0");
  const [categoriaId, setCategoriaId] = useState("");
  const [showPurchaseForm, setShowPurchaseForm] = useState(false);
  const [showShareForm, setShowShareForm] = useState(false);
  const [shareEditingTxId, setShareEditingTxId] = useState<string | null>(null);
  const [showInstallmentForm, setShowInstallmentForm] = useState(false);
  const [installmentEditingTxId, setInstallmentEditingTxId] = useState<string | null>(null);
  const [installmentCurrentInput, setInstallmentCurrentInput] = useState("1");
  const [installmentTotalInput, setInstallmentTotalInput] = useState("2");
  const [savingInstallment, setSavingInstallment] = useState(false);
  const [showSpenderBoardModal, setShowSpenderBoardModal] = useState(false);
  const [selectedSpenderGroup, setSelectedSpenderGroup] = useState<CardSpenderSummaryGroup | null>(null);
  const [statementParsing, setStatementParsing] = useState(false);
  const [deletingAllTxs, setDeletingAllTxs] = useState(false);
  const [deletingAllMonthsTxs, setDeletingAllMonthsTxs] = useState(false);
  const [markingAllPaid, setMarkingAllPaid] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importFormatTab, setImportFormatTab] = useState<ImportFormatTab>("csv");
  const [importError, setImportError] = useState<{ title: string; sub: string } | null>(null);
  const [importProgressStep, setImportProgressStep] = useState(0);
  const [csvMessage, setCsvMessage] = useState("");
  const importFileInputRef = useRef<HTMLInputElement>(null);
  const [descricao, setDescricao] = useState("");
  const [valor, setValor] = useState("");
  const [data, setData] = useState("");
  const [parcelas, setParcelas] = useState("1");
  const [recorrenteEdicao, setRecorrenteEdicao] = useState(false);
  const [mesesRecorrenciaEdicao, setMesesRecorrenciaEdicao] = useState("1");
  const [pago, setPago] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [updatingPagoId, setUpdatingPagoId] = useState<string | null>(null);
  const [descFilter, setDescFilter] = useState("");
  const [paidFilter, setPaidFilter] = useState<"all" | "paid" | "unpaid">("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [personFilter, setPersonFilter] = useState("all");
  const [showLancamentosMoreActions, setShowLancamentosMoreActions] = useState(false);
  const [txMenuTxId, setTxMenuTxId] = useState<string | null>(null);
  const [txSort, setTxSort] = useState<TxSort>("recent");
  const [spenders, setSpenders] = useState<SpenderRow[]>([]);
  const [shareRows, setShareRows] = useState<{ spenderId: string; valor: string }[]>([
    { spenderId: "", valor: "" },
  ]);
  const [spenderSummary, setSpenderSummary] = useState<CardSpenderSummary | null>(null);
  const [meSpenderId, setMeSpenderId] = useState<string | null>(null);
  const shareEditingTx = useMemo(
    () => (shareEditingTxId ? txs.find((x) => x.id === shareEditingTxId) ?? null : null),
    [shareEditingTxId, txs],
  );
  const installmentEditingTx = useMemo(
    () => (installmentEditingTxId ? txs.find((x) => x.id === installmentEditingTxId) ?? null : null),
    [installmentEditingTxId, txs],
  );
  const editingTx = useMemo(
    () => (editingId ? txs.find((x) => x.id === editingId) ?? null : null),
    [editingId, txs],
  );
  const txMenuTx = useMemo(
    () => (txMenuTxId ? txs.find((x) => x.id === txMenuTxId) ?? null : null),
    [txMenuTxId, txs],
  );
  const allocatedShareTotal = useMemo(() => sumShareRows(shareRows), [shareRows]);
  const purchaseShareTarget = useMemo(() => parseBrazilianMoney(valor) ?? 0, [valor]);
  const editShareTarget = useMemo(
    () => (shareEditingTx ? parseFloat(String(shareEditingTx.valor)) || 0 : 0),
    [shareEditingTx],
  );
  const purchaseShareBalanceStatus = useMemo(
    () => shareBalanceStatus(purchaseShareTarget, allocatedShareTotal),
    [purchaseShareTarget, allocatedShareTotal],
  );
  const editShareBalanceStatus = useMemo(
    () => shareBalanceStatus(editShareTarget, allocatedShareTotal),
    [editShareTarget, allocatedShareTotal],
  );

  const faltaPagar = useMemo(
    () =>
      txs.reduce((acc, t) => acc + (t.pago ? 0 : parseFloat(t.valor) || 0), 0),
    [txs],
  );

  const faltaPagarMinhaParte = useMemo(() => {
    if (!meSpenderId) return 0;
    return txs.reduce((acc, t) => acc + valorMinhaPartePendente(t, meSpenderId), 0);
  }, [txs, meSpenderId]);

  const periodoLabel = useMemo(() => {
    if (!periodId) return "";
    const p = periods.find((x) => x.id === periodId);
    if (!p) return "";
    return monthLabel(p.mes, p.ano);
  }, [periodId, periods, monthLabel]);

  const limiteDisponivel = useMemo(
    () => (card ? availableCardLimit(card.limite, lifetimeSpentTotal) : 0),
    [card, lifetimeSpentTotal],
  );

  const cardStripe = useMemo(() => cardStripeFromBanco(card?.banco ?? ""), [card?.banco]);

  const limitNum = useMemo(() => (card ? parseFloat(card.limite) || 0 : 0), [card]);

  const invoiceNum = useMemo(() => parseFloat(invoice) || 0, [invoice]);

  const utilizationPct = useMemo(
    () => (limitNum > 0 ? (invoiceNum / limitNum) * 100 : 0),
    [invoiceNum, limitNum],
  );

  const categoryChartRows = useMemo(() => {
    const totals = new Map<string, { name: string; value: number }>();
    let uncat = 0;
    for (const t of txs) {
      const val = parseFloat(t.valor) || 0;
      if (!t.categoria_id) {
        uncat += val;
        continue;
      }
      const name = categoryNameById(categories, t.categoria_id);
      const existing = totals.get(t.categoria_id) ?? { name, value: 0 };
      existing.value += val;
      totals.set(t.categoria_id, existing);
    }
    const rows = [...totals.values()].sort((a, b) => b.value - a.value);
    if (uncat > 0.009) rows.push({ name: "Outros", value: uncat });
    return rows
      .filter((r) => r.value > 0.009)
      .map((r, idx) => ({
        name: r.name,
        value: r.value,
        color: CATEGORY_CHART_COLORS[idx % CATEGORY_CHART_COLORS.length]!,
      }));
  }, [categories, txs]);

  const categoriesWithTxs = useMemo(() => {
    const ids = new Set(txs.map((t) => t.categoria_id).filter(Boolean) as string[]);
    return categories
      .filter((category) => ids.has(category.id))
      .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
  }, [categories, txs]);

  const txsOrdered = useMemo(() => {
    // Ordem da fatura: primeiro datas menores; mesmo dia mantém sequência original.
    return [...txs].sort((a, b) => a.data.localeCompare(b.data));
  }, [txs]);
  const txsFiltered = useMemo(() => {
    const query = descFilter.trim().toLowerCase();
    return txsOrdered.filter((t) => {
      const matchDesc =
        query.length === 0 || displayCardDescription(t.descricao).toLowerCase().includes(query);
      if (!matchDesc) return false;
      if (paidFilter === "paid" && !t.pago) return false;
      if (paidFilter === "unpaid" && t.pago) return false;
      if (categoryFilter !== "all" && (t.categoria_id ?? "uncategorized") !== categoryFilter) {
        return false;
      }
      if (personFilter === "none") return (t.shares?.length ?? 0) === 0;
      if (personFilter !== "all") {
        return !!t.shares?.some((s) => s.spender_id === personFilter);
      }
      return true;
    });
  }, [categoryFilter, descFilter, paidFilter, personFilter, txsOrdered]);

  const txsDisplay = useMemo(() => {
    const list = [...txsFiltered];
    switch (txSort) {
      case "oldest":
        return list.sort((a, b) => a.data.localeCompare(b.data));
      case "value_desc":
        return list.sort((a, b) => (parseFloat(b.valor) || 0) - (parseFloat(a.valor) || 0));
      case "value_asc":
        return list.sort((a, b) => (parseFloat(a.valor) || 0) - (parseFloat(b.valor) || 0));
      case "name_asc":
        return list.sort((a, b) =>
          displayCardDescription(a.descricao).localeCompare(
            displayCardDescription(b.descricao),
            "pt-BR",
          ),
        );
      case "recent":
      default:
        return list.sort((a, b) => b.data.localeCompare(a.data));
    }
  }, [txSort, txsFiltered]);

  const txnGroups = useMemo(() => {
    const groups: { label: string; items: CardTransactionRow[] }[] = [];
    let currentDate = "";
    let currentItems: CardTransactionRow[] = [];
    for (const t of txsDisplay) {
      if (t.data !== currentDate) {
        if (currentItems.length > 0) {
          groups.push({ label: formatGroupDateLabel(currentDate), items: currentItems });
        }
        currentDate = t.data;
        currentItems = [t];
      } else {
        currentItems.push(t);
      }
    }
    if (currentItems.length > 0) {
      groups.push({ label: formatGroupDateLabel(currentDate), items: currentItems });
    }
    return groups;
  }, [txsDisplay]);

  const unpaidTxCount = useMemo(() => txs.reduce((n, t) => n + (t.pago ? 0 : 1), 0), [txs]);

  const importActionsDisabled =
    periodClosed ||
    !periodId ||
    statementParsing ||
    deletingAllTxs ||
    deletingAllMonthsTxs ||
    markingAllPaid;

  const currentImportFormatInfo = useMemo(
    () => importFormatInfo(card, importFormatTab),
    [card, importFormatTab],
  );

  const importProgress = IMPORT_PROGRESS_STEPS[importProgressStep] ?? IMPORT_PROGRESS_STEPS[0];

  const statementFormatChoices = useMemo(() => statementFormatOptionsForCard(card), [card]);
  const spenderBoardRows = useMemo(() => {
    if (!periodId) return [];

    const byId = new Map<string, CardSpenderSummaryGroup>();
    let unassigned: CardSpenderSummaryGroup | null = null;
    for (const g of spenderSummary?.groups ?? []) {
      if (g.spender_id == null) {
        unassigned = g;
        continue;
      }
      byId.set(g.spender_id, g);
    }

    const rows: { group: CardSpenderSummaryGroup; nome: string; total: number }[] = [];

    for (const s of spenders) {
      const g = byId.get(s.id);
      if (!g) continue;
      const total = parseFloat(g.total) || 0;
      if (total <= 0.009) continue;
      rows.push({
        group: g,
        nome: g.spender_nome ?? s.nome,
        total,
      });
    }

    rows.sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));

    if (unassigned) {
      const unassignedTotal = parseFloat(unassigned.total) || 0;
      if (unassignedTotal > 0.009) {
        rows.push({
          group: unassigned,
          nome: "Não atribuído",
          total: unassignedTotal,
        });
      }
    }

    return rows;
  }, [periodId, spenderSummary, spenders]);

  const totalPersonUsage = useMemo(
    () => spenderBoardRows.reduce((sum, r) => sum + r.total, 0),
    [spenderBoardRows],
  );

  async function loadCard() {
    if (!id) return;
    try {
      const c = await api.getCard(id);
      setCard(c);
    } catch {
      setCard(null);
    }
  }

  async function loadCategories() {
    const cats = await api.categories("expense");
    setCategories(cats as Category[]);
    setCategoriaId((prev) => prev || cats[0]?.id || "");
  }

  async function loadTxs() {
    if (!id) return;
    const spent = await api.cardSpentTotal(id);
    setLifetimeSpentTotal(spent.total);
    if (!periodId) {
      setTxs([]);
      setInvoice("0");
      setSpenderSummary(null);
      return;
    }
    const [t, inv, sum] = await Promise.all([
      api.listCardTransactions(id, periodId),
      api.invoiceTotal(id, periodId),
      api.cardSpenderSummary(id, periodId).catch(() => null),
    ]);
    setTxs(t);
    setInvoice(inv.total);
    setSpenderSummary(sum);
  }

  function resetForm() {
    setEditingId(null);
    setDescricao("");
    setValor("");
    setParcelas("1");
    setRecorrenteEdicao(false);
    setMesesRecorrenciaEdicao("1");
    setPago(false);
    if (currentPeriod) {
      setData(defaultPurchaseDate(currentPeriod.mes, currentPeriod.ano));
    } else {
      setData(new Date().toISOString().slice(0, 10));
    }
    setCategoriaId(categories[0]?.id ?? "");
    setShareRows([{ spenderId: "", valor: "" }]);
  }

  useEffect(() => {
    if (!id) return;
    let c = false;
    (async () => {
      try {
        await loadCard();
      } catch (e) {
        if (!c) setError(e instanceof Error ? e.message : "Erro");
      }
    })();
    return () => {
      c = true;
    };
  }, [id]);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        await loadCategories();
      } catch (e) {
        if (!c) setError(e instanceof Error ? e.message : "Erro");
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  useEffect(() => {
    if (currentPeriod) {
      setData((d) => d || defaultPurchaseDate(currentPeriod.mes, currentPeriod.ano));
    }
  }, [currentPeriod?.mes, currentPeriod?.ano]);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const s = await api.listSpenders();
        if (!c) setSpenders(s);
      } catch {
        if (!c) setSpenders([]);
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const u = await api.getMe();
        if (!c) setMeSpenderId(u.me_spender_id ?? null);
      } catch {
        if (!c) setMeSpenderId(null);
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  useEffect(() => {
    if (!ready || !id) return;
    let cancelled = false;
    (async () => {
      try {
        await loadTxs();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Erro");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, periodId, ready]);

  useEffect(() => {
    setCsvMessage("");
  }, [periodId]);

  function closePurchaseModal() {
    resetForm();
    setShowPurchaseForm(false);
  }

  function closeShareModal() {
    setShowShareForm(false);
    setShareEditingTxId(null);
    setShareRows([{ spenderId: "", valor: "" }]);
  }

  function closeInstallmentModal() {
    setShowInstallmentForm(false);
    setInstallmentEditingTxId(null);
    setInstallmentCurrentInput("1");
    setInstallmentTotalInput("2");
  }

  function closeSpenderBoardModal() {
    setShowSpenderBoardModal(false);
    setSelectedSpenderGroup(null);
  }

  function openNewPurchaseModal() {
    resetForm();
    setShowPurchaseForm(true);
  }

  useEffect(() => {
    const shouldOpenPurchase = searchParams.get("openPurchase") === "1";
    if (!shouldOpenPurchase || periodClosed) return;
    openNewPurchaseModal();
    const next = new URLSearchParams(searchParams);
    next.delete("openPurchase");
    setSearchParams(next, { replace: true });
  }, [openNewPurchaseModal, periodClosed, searchParams, setSearchParams]);

  useEffect(() => {
    const importMsg = searchParams.get("importMsg");
    if (!importMsg) return;
    setCsvMessage(importMsg);
    void loadTxs();
    const next = new URLSearchParams(searchParams);
    next.delete("importMsg");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (
      !showPurchaseForm &&
      !showShareForm &&
      !showInstallmentForm &&
      !showSpenderBoardModal &&
      !showImportModal &&
      !showLancamentosMoreActions &&
      !txMenuTxId
    )
      return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (showImportModal) {
        closeImportModal();
      } else if (showLancamentosMoreActions) {
        setShowLancamentosMoreActions(false);
      } else if (showSpenderBoardModal) {
        closeSpenderBoardModal();
      } else if (showInstallmentForm) {
        closeInstallmentModal();
      } else if (showShareForm) {
        closeShareModal();
      } else if (txMenuTxId) {
        setTxMenuTxId(null);
      } else {
        resetForm();
        setShowPurchaseForm(false);
      }
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [
    showPurchaseForm,
    showShareForm,
    showInstallmentForm,
    showSpenderBoardModal,
    showImportModal,
    showLancamentosMoreActions,
    txMenuTxId,
  ]);

  useEffect(() => {
    if (!statementParsing) {
      setImportProgressStep(0);
      return;
    }
    let step = 0;
    const interval = window.setInterval(() => {
      if (step < IMPORT_PROGRESS_STEPS.length - 1) {
        step += 1;
        setImportProgressStep(step);
      }
    }, 700);
    return () => window.clearInterval(interval);
  }, [statementParsing]);

  function startEdit(t: CardTransactionRow) {
    setEditingId(t.id);
    setCategoriaId(t.categoria_id ?? categories[0]?.id ?? "");
    setDescricao(t.descricao);
    setValor(String(t.valor).replace(".", ","));
    setData(t.data.slice(0, 10));
    setParcelas(String(t.installment_total));
    setRecorrenteEdicao(false);
    setMesesRecorrenciaEdicao("1");
    setPago(t.pago);
    if (t.shares && t.shares.length > 0) {
      setShareRows(
        t.shares.map((s) => ({
          spenderId: s.spender_id,
          valor: String(s.valor).replace(".", ","),
        })),
      );
    } else {
      setShareRows([{ spenderId: "", valor: "" }]);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!id || !periodId || !categoriaId) return;
    setSaving(true);
    setError("");
    try {
      const valorApi = valor.replace(/\./g, "").replace(",", ".");
      let sharesPayload: { spender_id: string; valor: string }[] | undefined;
      try {
        const preparedRows = prepareShareRowsForSubmit(shareRows, valor);
        sharesPayload = resolveSharesPayload(Boolean(editingId), valor, preparedRows);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Divisão inválida");
        setSaving(false);
        return;
      }
      if (editingId) {
        const patch: Record<string, unknown> = {
          descricao: descricao.trim(),
          valor: valorApi,
          categoria_id: categoriaId,
          data,
          pago,
        };
        if (recorrenteEdicao) {
          const n = Math.max(1, parseInt(mesesRecorrenciaEdicao, 10) || 1);
          patch.recorrente = true;
          patch.recurrence_months = n;
        }
        if (sharesPayload !== undefined) patch.shares = sharesPayload;
        await api.updateCardTransaction(editingId, patch);
      } else {
        const installmentInfo = parseInstallmentInput(parcelas);
        const body: Record<string, unknown> = {
          descricao: descricao.trim(),
          valor: valorApi,
          card_id: id,
          categoria_id: categoriaId,
          period_id: periodId,
          data,
          pago,
          installment_total: installmentInfo.total,
        };
        if (installmentInfo.fromFraction && installmentInfo.current) {
          body.installment_number = installmentInfo.current;
          body.auto_generate_future_installments = true;
        }
        if (sharesPayload !== undefined && sharesPayload.length > 0) body.shares = sharesPayload;
        await api.createCardTransaction(body);
      }
      resetForm();
      setShowPurchaseForm(false);
      await loadTxs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setSaving(false);
    }
  }

  async function onDelete(tx: CardTransactionRow) {
    const confirmMsg =
      tx.installment_total > 1
        ? "Este lançamento é parcelado. Excluir em todos os meses/parcela(s)?"
        : "Excluir este lançamento?";
    const ok = await askConfirm({
      title: "Excluir lançamento",
      message: confirmMsg,
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    setError("");
    try {
      await api.deleteCardTransaction(tx.id);
      if (editingId === tx.id) {
        resetForm();
        setShowPurchaseForm(false);
      }
      await loadTxs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao excluir");
    }
  }

  async function onPagoChange(t: CardTransactionRow, nextPago: boolean) {
    if (periodClosed) return;
    setUpdatingPagoId(t.id);
    setError("");
    try {
      const updated = await api.setCardTransactionPaid(t.id, nextPago);
      setTxs((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao atualizar");
    } finally {
      setUpdatingPagoId(null);
    }
  }

  async function onSharePagoChange(t: CardTransactionRow, spenderId: string, nextPago: boolean) {
    if (periodClosed) return;
    setUpdatingPagoId(t.id);
    setError("");
    try {
      const updated = await api.setCardTransactionSharePaid(t.id, spenderId, nextPago);
      setTxs((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao atualizar status da pessoa");
    } finally {
      setUpdatingPagoId(null);
    }
  }

  async function onDeleteAllTransactions() {
    if (!id || !periodId || txs.length === 0 || periodClosed) return;
    const ok = await askConfirm({
      title: "Apagar lançamentos",
      message:
        `Apagar todos os ${txs.length} lançamento(s) do período ${periodoLabel || "atual"}? ` +
        "Só este mês é limpo: parcelas da mesma compra em outros meses ficam no sistema. " +
        "Ao importar a fatura de novo, parcelas podem herdar categoria e divisão das parcelas anteriores. " +
        "Esta ação não pode ser desfeita.",
      confirmLabel: "Apagar tudo",
      danger: true,
    });
    if (!ok) return;
    setDeletingAllTxs(true);
    setError("");
    setCsvMessage("");
    try {
      const res = await api.deleteAllCardTransactions(id, periodId);
      setCsvMessage(`${res.deleted} lançamento(s) apagados neste período. Parcelas em outros meses foram mantidas.`);
      await loadTxs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao apagar lançamentos");
    } finally {
      setDeletingAllTxs(false);
    }
  }

  async function onDeleteAllTransactionsAllMonths() {
    if (!id || periodClosed) return;
    const ok = await askConfirm({
      title: "Apagar lançamentos de todos os meses",
      message:
        "Apagar todos os lançamentos deste cartão em todos os meses? " +
        "Essa ação remove também parcelas futuras e não pode ser desfeita.",
      confirmLabel: "Apagar tudo",
      danger: true,
    });
    if (!ok) return;
    setDeletingAllMonthsTxs(true);
    setError("");
    setCsvMessage("");
    try {
      const res = await api.deleteAllCardTransactionsAllMonths(id);
      setCsvMessage(
        `${res.deleted} lançamento(s) apagados em meses abertos deste cartão. Meses fechados foram preservados.`,
      );
      await loadTxs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao apagar lançamentos");
    } finally {
      setDeletingAllMonthsTxs(false);
    }
  }

  async function onMarkAllPaid() {
    if (!id || !periodId || periodClosed || unpaidTxCount === 0) return;
    const ok = await askConfirm({
      title: "Marcar como pago",
      message: `Marcar ${unpaidTxCount} lançamento(s) como pagos no período ${periodoLabel || "atual"}?`,
      confirmLabel: "Marcar pagos",
    });
    if (!ok) return;
    setMarkingAllPaid(true);
    setError("");
    setCsvMessage("");
    try {
      const res = await api.markAllCardTransactionsPaid(id, periodId);
      setCsvMessage(
        res.updated > 0
          ? `${res.updated} lançamento(s) marcados como pagos.`
          : "Nenhum lançamento pendente.",
      );
      await loadTxs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao marcar como pagos");
    } finally {
      setMarkingAllPaid(false);
    }
  }

  function splitShareEqually() {
    setShareRows((rows) => rebalanceShareRows(rows, valor));
  }

  function openShareModal(t: CardTransactionRow) {
    setShareEditingTxId(t.id);
    if (t.shares && t.shares.length > 0) {
      setShareRows(
        t.shares.map((s) => ({
          spenderId: s.spender_id,
          valor: String(s.valor).replace(".", ","),
        })),
      );
    } else {
      setShareRows([{ spenderId: "", valor: "" }]);
    }
    setShowShareForm(true);
  }

  function openInstallmentModal(t: CardTransactionRow) {
    setInstallmentEditingTxId(t.id);
    setInstallmentCurrentInput(String(Math.max(1, t.installment_number || 1)));
    setInstallmentTotalInput(String(Math.max(2, t.installment_total || 2)));
    setShowInstallmentForm(true);
  }

  function splitShareEquallyByTotal(total: string) {
    setShareRows((rows) => rebalanceShareRows(rows, total));
  }

  async function onSubmitShare(e: React.FormEvent) {
    e.preventDefault();
    if (!shareEditingTx || periodClosed) return;
    setSaving(true);
    setError("");
    try {
      const total = String(shareEditingTx.valor).replace(".", ",");
      const preparedRows = prepareShareRowsForSubmit(shareRows, total);
      const existingPago = new Map(
        (shareEditingTx.shares ?? []).map((s) => [s.spender_id, s.pago === true]),
      );
      const sharesPayload = (resolveSharesPayload(true, total, preparedRows) ?? []).map((s) => ({
        ...s,
        pago: existingPago.get(s.spender_id) ?? false,
      }));
      await api.updateCardTransaction(shareEditingTx.id, { shares: sharesPayload });
      await loadTxs();
      closeShareModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar divisão");
    } finally {
      setSaving(false);
    }
  }

  async function onSubmitInstallment(e: React.FormEvent) {
    e.preventDefault();
    if (!installmentEditingTx || periodClosed) return;
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
    setSavingInstallment(true);
    setError("");
    try {
      const sharesPayload =
        installmentEditingTx.shares?.map((s) => ({ spender_id: s.spender_id, valor: s.valor })) ?? [];
      const body: Record<string, unknown> = {
        descricao: installmentEditingTx.descricao.trim(),
        valor: String(installmentEditingTx.valor),
        card_id: installmentEditingTx.card_id,
        categoria_id: installmentEditingTx.categoria_id ?? undefined,
        period_id: installmentEditingTx.period_id,
        data: installmentEditingTx.data,
        pago: installmentEditingTx.pago,
        installment_total: total,
        installment_number: current,
        auto_generate_future_installments: true,
        shares: sharesPayload,
      };
      await api.createCardTransaction(body);
      await api.deleteCardTransaction(installmentEditingTx.id);
      await loadTxs();
      closeInstallmentModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao definir parcelas");
    } finally {
      setSavingInstallment(false);
    }
  }

  function openSpenderBoard(group: CardSpenderSummaryGroup) {
    setSelectedSpenderGroup(group);
    setShowSpenderBoardModal(true);
  }

  function valorToApi(s: string): string {
    const n = parseBrazilianMoney(s);
    if (n === null || n === 0) return "0";
    return n.toFixed(2);
  }

  function openImportModal() {
    const tab = defaultImportFormatTab(card);
    setImportFormatTab(tab);
    setImportFile(null);
    setImportError(null);
    setImportProgressStep(0);
    setShowImportModal(true);
  }

  function closeImportModal() {
    if (statementParsing) return;
    setShowImportModal(false);
    setImportFile(null);
    setImportError(null);
    setImportProgressStep(0);
    if (importFileInputRef.current) importFileInputRef.current.value = "";
  }

  function changeImportFormatTab(tab: ImportFormatTab) {
    setImportFormatTab(tab);
    setImportFile(null);
    setImportError(null);
    if (importFileInputRef.current) importFileInputRef.current.value = "";
  }

  function selectImportFile(file: File) {
    if (!importFileExtensionOk(file, importFormatTab)) {
      setImportError({
        title: "Formato não suportado",
        sub:
          importFormatTab === "csv"
            ? "Use um arquivo .csv ou .txt exportado pelo banco."
            : "Use um arquivo .pdf exportado pelo banco.",
      });
      return;
    }
    setImportError(null);
    setImportFile(file);
  }

  function removeImportFile() {
    setImportFile(null);
    setImportError(null);
    setImportProgressStep(0);
    if (importFileInputRef.current) importFileInputRef.current.value = "";
  }

  function onImportFileInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) selectImportFile(file);
  }

  function onImportDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.currentTarget.classList.remove("cd-dropzone--drag");
    const file = e.dataTransfer.files[0];
    if (file) selectImportFile(file);
  }

  async function parseStatementFile(file: File): Promise<boolean> {
    if (!id || !periodId || periodClosed) return false;
    setCsvMessage("");
    const defaultDate = currentPeriod
      ? defaultPurchaseDate(currentPeriod.mes, currentPeriod.ano)
      : new Date().toISOString().slice(0, 10);
    setStatementParsing(true);
    setImportError(null);
    setImportProgressStep(0);
    try {
      let effectiveCategories = categories;
      // A aba ativa é a fonte de verdade do formato: evita enviar um perfil PDF
      // para um arquivo CSV (ou vice-versa) quando o estado dessincroniza.
      const effectiveFormat = statementFormatForTab(card, importFormatTab);
      const previewProbe = await api.previewStatement(file, effectiveFormat, defaultDate, id, periodId);
      const hasCarRows = previewProbe.rows.some(
        (r) => r.status === "new" && shouldSuggestCarCategory(r.descricao),
      );
      const extraWarnings: string[] = [...previewProbe.warnings];
      if (!findCarCategoryId(effectiveCategories) && hasCarRows) {
        try {
          const created = await api.createCategory({
            nome: "Carro",
            tipo: "expense",
            cor: "#2563eb",
          });
          effectiveCategories = [...effectiveCategories, created];
          setCategories(effectiveCategories);
          extraWarnings.push(
            "Categoria 'Carro' criada automaticamente para classificar lançamentos de mobilidade.",
          );
        } catch {
          // segue sem bloquear
        }
      }
      const actionable = previewProbe.rows.filter((r) => r.status !== "skip");
      if (actionable.length === 0) {
        setImportError({
          title: "Não foi possível ler o arquivo",
          sub:
            card && statementFormatChoices[0]?.id.startsWith("nubank")
              ? "Nenhuma linha reconhecida. Tente o outro formato ou exporte o CSV pelo app do Nubank."
              : "Nenhuma linha reconhecida. Escolha outro formato ou importe um CSV exportado pelo banco.",
        });
        return false;
      }
      const session = buildPreviewSession({
        preview: { ...previewProbe, warnings: extraWarnings },
        categories: effectiveCategories,
        cardId: id,
        periodId,
        fileName: file.name,
        formatId: effectiveFormat,
        formatTab: importFormatTab,
      });
      sessionStorage.setItem(IMPORT_PREVIEW_STORAGE_KEY, JSON.stringify(session));
      setShowImportModal(false);
      setImportFile(null);
      setImportError(null);
      setImportProgressStep(0);
      if (importFileInputRef.current) importFileInputRef.current.value = "";
      navigate(`/cartoes/${id}/importar/preview?periodId=${periodId}`);
      return true;
    } catch (err) {
      setImportError({
        title: "Não foi possível ler o arquivo",
        sub: err instanceof Error ? err.message : "Verifique se o arquivo é válido e exportado pelo banco.",
      });
      return false;
    } finally {
      setStatementParsing(false);
      setImportProgressStep(0);
    }
  }

  async function startImportFromModal() {
    if (!importFile || statementParsing) return;
    await parseStatementFile(importFile);
  }

  if (!id) return null;
  if (!card) {
    return (
      <div className="padded">
        <p className="muted">Cartão não encontrado.</p>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => onGoBack()}>
          Voltar
        </button>
      </div>
    );
  }

  function onGoBack() {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate("/cartoes");
  }

  return (
    <div className="padded card-detail-page">
      <header className="cd-header">
        <div className="cd-header-top">
          <button type="button" className="cd-back-btn" onClick={() => onGoBack()}>
            ← Voltar
          </button>
        </div>
        <div className="cd-card-hero">
          <div className={`cd-card-icon cd-card-icon--${cardStripe}`} aria-hidden>
            {cardIconEmoji(cardStripe)}
          </div>
          <div className="cd-card-hero-info">
            <div className="cd-card-hero-name">{card.nome}</div>
            <div className="cd-card-hero-bank">{card.banco ? `Banco ${card.banco}` : "Banco não informado"}</div>
            {periodoLabel && <div className="cd-card-hero-period">Período: {periodoLabel}</div>}
          </div>
        </div>
      </header>

      <div className="cd-stats-wrap">
        <div className="cd-stats-card">
          <div className="cd-stats-card-title">💳 Cartão e limites</div>
          <div className="cd-stats-grid">
            <div className="cd-stat-item">
              <div className="cd-stat-lbl">Limite cadastrado</div>
              <div className="cd-stat-val cd-stat-val--purple">{formatBRL(card.limite)}</div>
            </div>
            <div className="cd-stat-item">
              <div className="cd-stat-lbl">Limite disponível</div>
              <div className="cd-stat-val cd-stat-val--green">{formatBRL(limiteDisponivel)}</div>
            </div>
          </div>
          <div className="cd-usage-row">
            <span className="cd-usage-lbl">Uso do limite</span>
            <span className="cd-usage-pct">{utilizationPct.toFixed(1).replace(".", ",")}%</span>
          </div>
          <div className="cd-bar-track">
            <div
              className={`cd-bar-fill cd-bar-fill--${cardStripe}`}
              style={{ width: `${Math.min(100, Math.max(0, utilizationPct))}%` }}
            />
          </div>
        </div>

        <div className="cd-stats-card">
          <div className="cd-stats-card-title">🧾 Fatura</div>
          <div className="cd-fatura-highlight">
            <div className="cd-fat-item">
              <div className="cd-fat-lbl">Total fatura</div>
              <div className="cd-fat-val cd-fat-val--blue">{formatCompactBRL(invoiceNum)}</div>
            </div>
            <div className="cd-fat-item">
              <div className="cd-fat-lbl">Falta pagar</div>
              <div className="cd-fat-val cd-fat-val--amber">{formatCompactBRL(faltaPagar)}</div>
            </div>
            {meSpenderId && (
              <div className="cd-fat-item">
                <div className="cd-fat-lbl">Minha parte</div>
                <div className="cd-fat-val cd-fat-val--red">{formatCompactBRL(faltaPagarMinhaParte)}</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {periodId && spenderBoardRows.length > 0 && (
        <>
          <div className="cd-section">
            <div className="cd-sec-title">Uso por pessoa — {periodoLabel || "período"}</div>
          </div>
          <div className="cd-pessoas-scroll" role="list">
            <button
              type="button"
              role="listitem"
              className={`cd-pessoa-chip${personFilter === "all" ? " cd-pessoa-chip--active" : ""}`}
              onClick={() => setPersonFilter("all")}
            >
              <div className="cd-pessoa-av" style={{ background: PERSON_GRADIENTS[0] }}>
                All
              </div>
              <div className="cd-pessoa-chip-name">Todos</div>
              <div className="cd-pessoa-chip-val cd-pessoa-chip-val--accent">
                {formatCompactBRL(totalPersonUsage)}
              </div>
            </button>
            {spenderBoardRows.map((r) => {
              const isFilterActive =
                r.group.spender_id == null
                  ? personFilter === "none"
                  : personFilter === r.group.spender_id;
              const isModalActive =
                showSpenderBoardModal &&
                selectedSpenderGroup != null &&
                (r.group.spender_id === selectedSpenderGroup.spender_id ||
                  (r.group.spender_id == null && selectedSpenderGroup.spender_id == null));
              const isActive = isFilterActive || isModalActive;
              return (
                <button
                  key={r.group.spender_id ?? "nao-atribuido"}
                  type="button"
                  role="listitem"
                  className={`cd-pessoa-chip${isActive ? " cd-pessoa-chip--active" : ""}`}
                  onClick={() => {
                    if (r.group.spender_id == null) {
                      setPersonFilter("none");
                    } else {
                      setPersonFilter(r.group.spender_id);
                    }
                    openSpenderBoard(r.group);
                  }}
                >
                  <div className="cd-pessoa-av" style={{ background: personGradient(r.nome) }}>
                    {personInitials(r.nome)}
                  </div>
                  <div className="cd-pessoa-chip-name">{r.nome}</div>
                  <div className="cd-pessoa-chip-val cd-pessoa-chip-val--green">
                    {formatCompactBRL(r.total)}
                  </div>
                </button>
              );
            })}
          </div>
        </>
      )}

      {categoryChartRows.length > 0 && (
        <>
          <div className="cd-section cd-section--chart">
            <div className="cd-sec-title">Gastos por categoria</div>
          </div>
          <div className="cd-chart-card">
            <CategoryExpensesChart
              rows={categoryChartRows}
              totalLabel={formatCompactBRL(
                categoryChartRows.reduce((sum, row) => sum + row.value, 0),
              )}
            />
          </div>
        </>
      )}

      {error && <p className="error cd-error">{error}</p>}
      {csvMessage && <p className="muted small cd-message">{csvMessage}</p>}

      <div className="cd-section cd-section--lancamentos">
        <div className="cd-sec-title">Lançamentos no período</div>
      </div>

      <div className="cd-filters-wrap">
        <div className="cd-filter-main">
          <div className="cd-search-box">
            <span className="cd-search-icon" aria-hidden>
              🔍
            </span>
            <input
              className="cd-search-input"
              value={descFilter}
              onChange={(e) => setDescFilter(e.target.value)}
              placeholder="Buscar lançamento…"
              aria-label="Buscar lançamento"
            />
          </div>
          <select
            className="cd-filter-select"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            aria-label="Filtrar por categoria"
          >
            <option value="all">Todas categorias</option>
            {txs.some((t) => !t.categoria_id) && (
              <option value="uncategorized">Sem categoria</option>
            )}
            {categoriesWithTxs.map((category) => (
              <option key={category.id} value={category.id}>
                {category.nome}
              </option>
            ))}
          </select>
          <select
            className="cd-filter-select"
            value={txSort}
            onChange={(e) => setTxSort(e.target.value as TxSort)}
            aria-label="Ordenar lançamentos"
          >
            <option value="recent">Mais recentes</option>
            <option value="oldest">Mais antigos</option>
            <option value="value_desc">Maior valor</option>
            <option value="value_asc">Menor valor</option>
            <option value="name_asc">A–Z</option>
          </select>
        </div>
        <div className="cd-filter-row" role="group" aria-label="Filtrar lançamentos">
          <button
            type="button"
            className={`cd-filter-chip${paidFilter === "all" ? " cd-filter-chip--active" : ""}`}
            onClick={() => setPaidFilter("all")}
          >
            Todos
          </button>
          <button
            type="button"
            className={`cd-filter-chip${paidFilter === "paid" ? " cd-filter-chip--active" : ""}`}
            onClick={() => setPaidFilter("paid")}
          >
            Pagos
          </button>
          <button
            type="button"
            className={`cd-filter-chip cd-filter-chip--unpaid${
              paidFilter === "unpaid" ? " cd-filter-chip--active" : ""
            }`}
            onClick={() => setPaidFilter("unpaid")}
          >
            Não pagos
          </button>
        </div>
      </div>

      <div className="cd-action-bar">
        <button
          type="button"
          className="cd-bar-btn cd-bar-btn--primary"
          disabled={importActionsDisabled}
          onClick={() => openNewPurchaseModal()}
        >
          ＋ Lançar compra
        </button>
        <button
          type="button"
          className="cd-bar-btn cd-bar-btn--import"
          disabled={importActionsDisabled}
          onClick={() => openImportModal()}
        >
          📥 Importar fatura
        </button>
        <button
          type="button"
          className="cd-bar-btn"
          disabled={importActionsDisabled}
          onClick={() => setShowLancamentosMoreActions(true)}
        >
          ··· Mais ações
        </button>
        <span className="cd-count-badge">
          {txsFiltered.length} lançamento{txsFiltered.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="cd-txn-list" aria-label="Lançamentos">
        {txs.length === 0 ? (
          <p className="muted cd-empty-msg">Nenhum lançamento neste período.</p>
        ) : txsFiltered.length === 0 ? (
          <p className="muted cd-empty-msg">Nenhum lançamento corresponde aos filtros selecionados.</p>
        ) : (
          txnGroups.map((group) => (
            <div key={group.label}>
              <div className="cd-txn-group-label">{group.label}</div>
              {group.items.map((t) => {
                const catName = categoryNameById(categories, t.categoria_id);
                return (
                  <article key={t.id} className="cd-txn-card">
                    <button
                      type="button"
                      className="cd-txn-main"
                      onClick={() => setTxMenuTxId(t.id)}
                      aria-label={`Abrir ações: ${displayCardDescription(t.descricao)}`}
                    >
                      <div className="cd-txn-cat-icon" aria-hidden>
                        {categoryEmoji(catName)}
                      </div>
                      <div className="cd-txn-info">
                        <div className="cd-txn-name">{displayCardDescription(t.descricao)}</div>
                        <div className="cd-txn-meta">
                          <span className="cd-txn-date">{formatDateBR(t.data)}</span>
                          <span className="cd-txn-cat-tag">{catName}</span>
                          {t.installment_total > 1 && (
                            <span className="cd-txn-parcela">
                              {t.installment_number}/{t.installment_total}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="cd-txn-right">
                        <div className="cd-txn-val">{formatBRL(t.valor)}</div>
                        {(() => {
                          const payStatus = txPaymentStatus(t);
                          return (
                            <span
                              className={`cd-txn-status-dot${
                                payStatus === "paid"
                                  ? " cd-txn-status-dot--pago"
                                  : payStatus === "partial"
                                    ? " cd-txn-status-dot--parcial"
                                    : " cd-txn-status-dot--pend"
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
                          );
                        })()}
                      </div>
                    </button>
                    {t.shares && t.shares.length > 0 ? (
                      t.shares.map((s) => {
                        const sharePaid = isSharePaid(s);
                        return (
                          <div
                            key={s.spender_id}
                            className={`cd-txn-person-row${sharePaid ? " cd-txn-person-row--pago" : ""}`}
                          >
                            <div className="cd-txn-person-left">
                              <div
                                className="cd-txn-person-av"
                                style={{ background: personGradient(s.spender_nome) }}
                                aria-hidden
                              >
                                {personInitials(s.spender_nome)}
                              </div>
                              <span className="cd-txn-person-name">{s.spender_nome}</span>
                            </div>
                            <span className="cd-txn-person-val">{formatBRL(s.valor)}</span>
                            {!periodClosed ? (
                              <button
                                type="button"
                                className={`cd-share-status-toggle${sharePaid ? " cd-share-status-toggle--pago" : " cd-share-status-toggle--pendente"}`}
                                disabled={updatingPagoId === t.id}
                                onClick={() => void onSharePagoChange(t, s.spender_id, !sharePaid)}
                              >
                                {sharePaid ? "✓ Pago" : "○ Pendente"}
                              </button>
                            ) : (
                              <span
                                className={`cd-share-status-toggle${sharePaid ? " cd-share-status-toggle--pago" : " cd-share-status-toggle--pendente"}`}
                              >
                                {sharePaid ? "✓ Pago" : "○ Pendente"}
                              </span>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      <div className="cd-txn-person-row cd-sem-divisao">
                        Sem divisão entre pessoas
                      </div>
                    )}
                    {t.shares && t.shares.length > 0 && !periodClosed && (
                      <div className="cd-txn-toggle-hint">
                        Clique no status de cada pessoa para marcar como pago ou pendente
                      </div>
                    )}
                    <div className="cd-txn-person-actions cd-txn-person-actions--cols-4">
                      {t.shares && t.shares.length > 0 ? (
                        !periodClosed ? (
                          <button
                            type="button"
                            className={`cd-txn-pact-btn${
                              txPaymentStatus(t) === "paid"
                                ? " cd-txn-pact-btn--desmarcar"
                                : " cd-txn-pact-btn--pagar"
                            }`}
                            disabled={updatingPagoId === t.id}
                            onClick={() =>
                              void onPagoChange(t, txPaymentStatus(t) !== "paid")
                            }
                          >
                            {txPaymentStatus(t) === "paid" ? "↺ Desmarcar todos" : "✓ Marcar todos"}
                          </button>
                        ) : (
                          <span className="cd-txn-pact-btn cd-txn-pact-btn--placeholder" aria-hidden />
                        )
                      ) : !periodClosed && !t.pago ? (
                        <button
                          type="button"
                          className="cd-txn-pact-btn cd-txn-pact-btn--pagar"
                          disabled={updatingPagoId === t.id}
                          onClick={() => void onPagoChange(t, true)}
                        >
                          ✓ Marcar pago
                        </button>
                      ) : !periodClosed && t.pago ? (
                        <button
                          type="button"
                          className="cd-txn-pact-btn"
                          disabled={updatingPagoId === t.id}
                          onClick={() => void onPagoChange(t, false)}
                        >
                          Desmarcar pago
                        </button>
                      ) : (
                        <span className="cd-txn-pact-btn cd-txn-pact-btn--placeholder" aria-hidden />
                      )}
                      <button
                        type="button"
                        className="cd-txn-pact-btn cd-txn-pact-btn--divisao"
                        disabled={periodClosed}
                        onClick={() => openShareModal(t)}
                      >
                        {t.shares && t.shares.length > 0 ? (
                          <>
                            <span className="cd-div-badge">{t.shares.length}</span> Divisão
                          </>
                        ) : (
                          <>＋ Divisão</>
                        )}
                      </button>
                      <button
                        type="button"
                        className="cd-txn-pact-btn"
                        disabled={periodClosed}
                        onClick={() => {
                          startEdit(t);
                          setShowPurchaseForm(true);
                        }}
                      >
                        ✏️ Editar
                      </button>
                      <button
                        type="button"
                        className="cd-txn-pact-btn cd-txn-pact-btn--danger"
                        disabled={periodClosed}
                        onClick={() => void onDelete(t)}
                      >
                        🗑 Excluir
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          ))
        )}
      </div>


      {showImportModal && (
        <div
          className="cd-import-overlay cd-import-overlay--open"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeImportModal();
          }}
        >
          <div
            className="cd-import-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="import-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="cd-import-header">
              <div className="cd-import-header-left">
                <div className="cd-import-hicon" aria-hidden>
                  📥
                </div>
                <div id="import-modal-title" className="cd-import-htitle">
                  Importar fatura
                </div>
              </div>
              <button
                type="button"
                className="cd-import-close"
                aria-label="Fechar"
                disabled={statementParsing}
                onClick={() => closeImportModal()}
              >
                ✕
              </button>
            </div>

            <div className="cd-import-body">
              <div className="cd-import-sec-lbl">Formato do arquivo</div>
              <div className="cd-fmt-tabs" role="tablist" aria-label="Formato do arquivo">
                <button
                  type="button"
                  role="tab"
                  aria-selected={importFormatTab === "csv"}
                  className={`cd-fmt-tab${importFormatTab === "csv" ? " cd-fmt-tab--active" : ""}`}
                  disabled={statementParsing}
                  onClick={() => changeImportFormatTab("csv")}
                >
                  📊 CSV (recomendado)
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={importFormatTab === "pdf"}
                  className={`cd-fmt-tab${importFormatTab === "pdf" ? " cd-fmt-tab--active" : ""}`}
                  disabled={statementParsing}
                  onClick={() => changeImportFormatTab("pdf")}
                >
                  📄 PDF
                </button>
              </div>

              <div className="cd-fmt-info">
                <div className="cd-fmt-info-title">{currentImportFormatInfo.title}</div>
                <div className="cd-fmt-info-list">
                  {currentImportFormatInfo.items.map((item) => (
                    <div key={item} className="cd-fmt-info-item">
                      {item}
                    </div>
                  ))}
                </div>
              </div>

              <div className="cd-import-sec-lbl cd-import-sec-lbl--spaced">Arquivo da fatura</div>
              {!importFile ? (
                <div
                  className="cd-dropzone"
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.currentTarget.classList.add("cd-dropzone--drag");
                  }}
                  onDragLeave={(e) => e.currentTarget.classList.remove("cd-dropzone--drag")}
                  onDrop={onImportDrop}
                >
                  <input
                    ref={importFileInputRef}
                    type="file"
                    className="cd-dropzone-input"
                    accept={importFormatTab === "csv" ? ".csv,.txt" : ".pdf"}
                    aria-label="Selecionar arquivo da fatura"
                    disabled={statementParsing}
                    onChange={onImportFileInputChange}
                  />
                  <span className="cd-dropzone-icon" aria-hidden>
                    ☁️
                  </span>
                  <div className="cd-dropzone-title">Arraste o arquivo ou clique para selecionar</div>
                  <div className="cd-dropzone-sub">Arquivo da fatura exportado pelo app do banco</div>
                  <div className="cd-dropzone-formats">
                    <span className="cd-fmt-badge cd-fmt-badge--csv">CSV</span>
                    <span className="cd-fmt-badge cd-fmt-badge--pdf">PDF</span>
                  </div>
                </div>
              ) : (
                <div className="cd-file-selected">
                  <div className="cd-file-icon" aria-hidden>
                    {importFormatTab === "csv" ? "📊" : "📄"}
                  </div>
                  <div className="cd-file-info">
                    <div className="cd-file-name">{importFile.name}</div>
                    <div className="cd-file-size">{formatImportFileSize(importFile.size)}</div>
                  </div>
                  <button
                    type="button"
                    className="cd-file-remove"
                    aria-label="Remover arquivo"
                    disabled={statementParsing}
                    onClick={() => removeImportFile()}
                  >
                    ✕
                  </button>
                </div>
              )}

              {importError && (
                <div className="cd-import-error" role="alert">
                  <span className="cd-import-error-icon" aria-hidden>
                    ⚠️
                  </span>
                  <div>
                    <div className="cd-import-error-title">{importError.title}</div>
                    <div className="cd-import-error-sub">{importError.sub}</div>
                  </div>
                </div>
              )}

              {statementParsing && (
                <div className="cd-import-progress">
                  <div className="cd-import-prog-bar">
                    <div
                      className="cd-import-prog-fill"
                      style={{ width: `${importProgress.w}%` }}
                    />
                  </div>
                  <div className="cd-import-prog-label">{importProgress.t}</div>
                </div>
              )}

              <button
                type="button"
                className="cd-import-submit"
                disabled={!importFile || statementParsing}
                onClick={() => void startImportFromModal()}
              >
                {statementParsing ? (
                  <>
                    <span className="cd-import-spin" aria-hidden>
                      ⏳
                    </span>{" "}
                    Importando…
                  </>
                ) : (
                  <>📥 Importar e categorizar automaticamente</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {showLancamentosMoreActions && (
        <div
          className="cd-mais-overlay cd-mais-overlay--open"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowLancamentosMoreActions(false);
          }}
        >
          <div
            className="cd-mais-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="mais-acoes-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="cd-import-header">
              <div className="cd-import-header-left">
                <div className="cd-import-hicon cd-import-hicon--muted" aria-hidden>
                  ⚙️
                </div>
                <div id="mais-acoes-title" className="cd-import-htitle">
                  Mais ações
                </div>
              </div>
              <button
                type="button"
                className="cd-import-close"
                aria-label="Fechar"
                onClick={() => setShowLancamentosMoreActions(false)}
              >
                ✕
              </button>
            </div>

            <div className="cd-mais-body">
              <div className="cd-import-sec-lbl">Fatura</div>

              <button
                type="button"
                className="cd-mais-item cd-mais-item--success"
                disabled={
                  importActionsDisabled ||
                  !id ||
                  unpaidTxCount === 0
                }
                onClick={() => {
                  setShowLancamentosMoreActions(false);
                  void onMarkAllPaid();
                }}
              >
                <div className="cd-mais-icon" aria-hidden>
                  ✅
                </div>
                <div className="cd-mais-text">
                  <div className="cd-mais-label">
                    {markingAllPaid ? "Marcando…" : "Marcar tudo como pago"}
                  </div>
                  <div className="cd-mais-sub">Marca todos os lançamentos deste mês</div>
                </div>
              </button>

              <div className="cd-mais-divider" />
              <div className="cd-import-sec-lbl">Ações irreversíveis</div>

              <button
                type="button"
                className="cd-mais-item cd-mais-item--warn"
                disabled={importActionsDisabled || !id || txs.length === 0}
                onClick={() => {
                  setShowLancamentosMoreActions(false);
                  void onDeleteAllTransactions();
                }}
              >
                <div className="cd-mais-icon" aria-hidden>
                  🗑️
                </div>
                <div className="cd-mais-text">
                  <div className="cd-mais-label">
                    {deletingAllTxs ? "Apagando…" : "Apagar mês"}
                  </div>
                  <div className="cd-mais-sub">
                    Remove todos os lançamentos de {periodoLabel || "este mês"}
                  </div>
                </div>
              </button>

              <button
                type="button"
                className="cd-mais-item cd-mais-item--danger"
                disabled={importActionsDisabled || !id}
                onClick={() => {
                  setShowLancamentosMoreActions(false);
                  void onDeleteAllTransactionsAllMonths();
                }}
              >
                <div className="cd-mais-icon" aria-hidden>
                  💥
                </div>
                <div className="cd-mais-text">
                  <div className="cd-mais-label">
                    {deletingAllMonthsTxs ? "Apagando…" : "Apagar todos os meses"}
                  </div>
                  <div className="cd-mais-sub">Remove todo o histórico deste cartão</div>
                </div>
              </button>
            </div>
          </div>
        </div>
      )}

      {txMenuTxId && txMenuTx && (() => {
        const txMenuCat = categoryNameById(categories, txMenuTx.categoria_id);
        return (
          <div
            className="cd-lanc-overlay cd-lanc-overlay--open"
            role="presentation"
            onClick={(e) => {
              if (e.target === e.currentTarget) setTxMenuTxId(null);
            }}
          >
            <div
              className="cd-lanc-modal cd-lanc-modal--mais"
              role="dialog"
              aria-modal="true"
              aria-labelledby="tx-menu-title"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="cd-lanc-modal-header">
                <div id="tx-menu-title" className="cd-lanc-modal-title">
                  Lançamento
                </div>
                <button
                  type="button"
                  className="cd-lanc-modal-close"
                  aria-label="Fechar"
                  onClick={() => setTxMenuTxId(null)}
                >
                  ✕
                </button>
              </div>
              <div className="cd-lanc-modal-body cd-lanc-modal-body--mais">
                <div className="cd-lanc-mais-txn-info">
                  <span className="cd-lanc-mais-txn-icon" aria-hidden>
                    {categoryEmoji(txMenuCat)}
                  </span>
                  <div>
                    <div className="cd-lanc-mais-txn-name">
                      {displayCardDescription(txMenuTx.descricao)}
                    </div>
                    <div className="cd-lanc-mais-txn-meta">
                      {txMenuCat} · {formatDateBR(txMenuTx.data)}
                      {txMenuTx.installment_total > 1
                        ? ` · Parcela ${txMenuTx.installment_number}/${txMenuTx.installment_total}`
                        : ""}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  className="cd-lanc-mais-item cd-lanc-mais-item--primary"
                  disabled={periodClosed}
                  onClick={() => {
                    setTxMenuTxId(null);
                    startEdit(txMenuTx);
                    setShowPurchaseForm(true);
                  }}
                >
                  <div className="cd-lanc-mais-icon" aria-hidden>
                    ✏️
                  </div>
                  <div>
                    <div className="cd-lanc-mais-label">Editar</div>
                    <div className="cd-lanc-mais-sub">Alterar categoria, valor ou descrição</div>
                  </div>
                </button>
                <button
                  type="button"
                  className="cd-lanc-mais-item cd-lanc-mais-item--neutral"
                  disabled={periodClosed}
                  onClick={() => {
                    setTxMenuTxId(null);
                    openShareModal(txMenuTx);
                  }}
                >
                  <div className="cd-lanc-mais-icon" aria-hidden>
                    👥
                  </div>
                  <div>
                    <div className="cd-lanc-mais-label">Divisão entre pessoas</div>
                    <div className="cd-lanc-mais-sub">Definir quem paga quanto</div>
                  </div>
                </button>
                <button
                  type="button"
                  className="cd-lanc-mais-item cd-lanc-mais-item--warning"
                  disabled={periodClosed}
                  onClick={() => {
                    setTxMenuTxId(null);
                    openInstallmentModal(txMenuTx);
                  }}
                >
                  <div className="cd-lanc-mais-icon" aria-hidden>
                    📦
                  </div>
                  <div>
                    <div className="cd-lanc-mais-label">
                      {txMenuTx.installment_total > 1
                        ? `Parcela ${txMenuTx.installment_number}/${txMenuTx.installment_total}`
                        : "Parcelas"}
                    </div>
                    <div className="cd-lanc-mais-sub">Gerenciar parcelas deste lançamento</div>
                  </div>
                </button>
                <div className="cd-lanc-mais-divider" />
                <button
                  type="button"
                  className="cd-lanc-mais-item cd-lanc-mais-item--danger"
                  disabled={periodClosed}
                  onClick={() => {
                    setTxMenuTxId(null);
                    void onDelete(txMenuTx);
                  }}
                >
                  <div className="cd-lanc-mais-icon" aria-hidden>
                    🗑️
                  </div>
                  <div>
                    <div className="cd-lanc-mais-label">Excluir</div>
                    <div className="cd-lanc-mais-sub">Remove este lançamento permanentemente</div>
                  </div>
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {showPurchaseForm && (
        <div
          className="cd-lanc-overlay cd-lanc-overlay--open"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) closePurchaseModal();
          }}
        >
          <div
            className="cd-lanc-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="purchase-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="cd-lanc-modal-header">
              <div className="cd-lanc-modal-title-row">
                <div className="cd-lanc-modal-icon" aria-hidden>
                  💳
                </div>
                <h2 id="purchase-modal-title" className="cd-lanc-modal-title">
                  {editingId ? "Editar lançamento" : "Nova compra"}
                </h2>
              </div>
              <button
                type="button"
                className="cd-lanc-modal-close"
                aria-label="Fechar"
                onClick={() => closePurchaseModal()}
              >
                ✕
              </button>
            </div>
            <form onSubmit={onSubmit} className="cd-lanc-modal-form">
              <div className="cd-lanc-modal-body">
                <div className="cd-lanc-form-group">
                  <label className="cd-lanc-form-label" htmlFor="cd-lanc-categoria">
                    Categoria
                  </label>
                  <select
                    id="cd-lanc-categoria"
                    className="cd-lanc-form-select"
                    value={categoriaId}
                    onChange={(e) => setCategoriaId(e.target.value)}
                    required
                    disabled={periodClosed}
                  >
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nome}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="cd-lanc-form-group">
                  <label className="cd-lanc-form-label" htmlFor="cd-lanc-descricao">
                    Descrição
                  </label>
                  <input
                    id="cd-lanc-descricao"
                    className="cd-lanc-form-input"
                    value={descricao}
                    onChange={(e) => setDescricao(e.target.value)}
                    required
                    disabled={periodClosed}
                  />
                </div>
                <div className="cd-lanc-form-row">
                  <div className="cd-lanc-form-group">
                    <label className="cd-lanc-form-label" htmlFor="cd-lanc-valor">
                      Valor total
                    </label>
                    <div className="cd-lanc-input-prefix-wrap">
                      <span className="cd-lanc-input-prefix">R$</span>
                      <input
                        id="cd-lanc-valor"
                        className="cd-lanc-form-input cd-lanc-form-input--mono cd-lanc-form-input--with-prefix"
                        inputMode="decimal"
                        value={valor}
                        onChange={(e) => setValor(e.target.value)}
                        placeholder="0,00"
                        required
                        disabled={periodClosed}
                      />
                    </div>
                  </div>
                  <div className="cd-lanc-form-group">
                    <label className="cd-lanc-form-label" htmlFor="cd-lanc-data">
                      Data da compra
                    </label>
                    <input
                      id="cd-lanc-data"
                      className="cd-lanc-form-input"
                      type="date"
                      value={data}
                      onChange={(e) => setData(e.target.value)}
                      required
                      disabled={periodClosed}
                    />
                  </div>
                </div>
                {!editingId && (
                  <div className="cd-lanc-form-group">
                    <label className="cd-lanc-form-label" htmlFor="cd-lanc-parcelas">
                      Parcelas
                    </label>
                    <input
                      id="cd-lanc-parcelas"
                      className="cd-lanc-form-input"
                      type="text"
                      value={parcelas}
                      onChange={(e) => setParcelas(e.target.value)}
                      placeholder="Ex.: 1 ou 2/5"
                      disabled={periodClosed}
                    />
                    <p className="cd-lanc-form-hint">
                      Use <span className="cd-lanc-form-highlight">número</span> (ex.: 5) quando o valor for o{" "}
                      <span className="cd-lanc-form-highlight">total da compra</span>; o sistema divide em n meses.
                    </p>
                    <p className="cd-lanc-form-hint">
                      Use <span className="cd-lanc-form-highlight">x/y</span> (ex.: 2/5) quando o valor for o{" "}
                      <span className="cd-lanc-form-highlight">valor da parcela</span>; o período atual vira a parcela x
                      e o sistema gera as próximas até y.
                    </p>
                  </div>
                )}
                {editingId && (
                  <div className="cd-lanc-form-group">
                    <span className="cd-lanc-form-label">Parcela atual</span>
                    <div className="cd-lanc-parcela-badge" aria-label={`Parcela ${editingTx?.installment_number ?? 1} de ${editingTx?.installment_total ?? 1}`}>
                      {editingTx?.installment_number ?? 1}/{editingTx?.installment_total ?? 1}
                    </div>
                  </div>
                )}
                {editingId && (editingTx?.installment_total ?? 1) > 1 && (
                  <p className="cd-lanc-form-hint">
                    Para alterar parcelas, use o botão de parcelas no menu do lançamento.
                  </p>
                )}
                {editingId && (
                  <>
                    <div className="cd-lanc-checks-group">
                      <button
                        type="button"
                        className={`cd-lanc-check-row${recorrenteEdicao ? " cd-lanc-check-row--on" : ""}`}
                        disabled={periodClosed || (editingTx?.installment_total ?? 1) > 1}
                        onClick={() => setRecorrenteEdicao((v) => !v)}
                      >
                        <div className="cd-lanc-chk" aria-hidden />
                        <div>
                          <div className="cd-lanc-check-label">Recorrente</div>
                          <div className="cd-lanc-check-sub">Replicar nos meses seguintes automaticamente</div>
                        </div>
                      </button>
                    </div>
                    {(editingTx?.installment_total ?? 1) > 1 ? null : (
                      recorrenteEdicao && (
                        <div className="cd-lanc-form-group">
                          <label className="cd-lanc-form-label" htmlFor="cd-lanc-meses-recorrencia">
                            Adicionar em quantos meses seguintes
                          </label>
                          <input
                            id="cd-lanc-meses-recorrencia"
                            className="cd-lanc-form-input"
                            type="number"
                            min={1}
                            max={120}
                            value={mesesRecorrenciaEdicao}
                            onChange={(e) => setMesesRecorrenciaEdicao(e.target.value)}
                            disabled={periodClosed}
                          />
                        </div>
                      )
                    )}
                  </>
                )}
                <div className="cd-lanc-divisao-header">
                  <span className="cd-lanc-divisao-title">Divisão entre pessoas</span>
                  <Link to="/cartoes/pessoas" className="cd-lanc-divisao-link">
                    + Cadastrar pessoas
                  </Link>
                </div>
                <p className="cd-lanc-form-hint">
                  A soma das partes deve fechar com o valor
                  {editingId ? " desta parcela" : " total da compra"}.
                </p>
                {shareRows.map((row, idx) => (
                  <div key={idx} className="cd-lanc-div-person-row">
                    <select
                      className="cd-lanc-div-select"
                      value={row.spenderId}
                      onChange={(e) => {
                        const v = e.target.value;
                        setShareRows((rs) => autoSplitRowsOnPersonSelect(rs, idx, v, valor));
                      }}
                      disabled={periodClosed}
                      aria-label={`Pessoa ${idx + 1}`}
                    >
                      <option value="">—</option>
                      {spenders.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.nome}
                        </option>
                      ))}
                    </select>
                    <input
                      className="cd-lanc-div-input"
                      value={row.valor}
                      onChange={(e) => {
                        const v = decimalPointToComma(e.target.value);
                        setShareRows((rs) => rs.map((x, i) => (i === idx ? { ...x, valor: v } : x)));
                      }}
                      placeholder="0,00"
                      disabled={periodClosed}
                      inputMode="decimal"
                      aria-label={`Valor parte ${idx + 1}`}
                    />
                    <button
                      type="button"
                      className="cd-lanc-div-del"
                      onClick={() =>
                        setShareRows((rs) => {
                          const next = rs.filter((_, i) => i !== idx);
                          return next.length === 0 ? [{ spenderId: "", valor: "" }] : next;
                        })
                      }
                      disabled={periodClosed}
                      aria-label={`Excluir linha ${idx + 1}`}
                    >
                      ✕
                    </button>
                  </div>
                ))}
                <div className="cd-lanc-divisao-actions">
                  <button
                    type="button"
                    className="cd-lanc-btn-linha"
                    onClick={() => setShareRows((r) => [...r, { spenderId: "", valor: "" }])}
                    disabled={periodClosed}
                  >
                    ＋ Linha
                  </button>
                  <button
                    type="button"
                    className="cd-lanc-btn-recalc"
                    onClick={() => splitShareEqually()}
                    disabled={periodClosed}
                  >
                    ⟳ Recalcular partes iguais
                  </button>
                </div>
                <div className="cd-lanc-soma-row">
                  Soma das partes: <span>{formatBRL(allocatedShareTotal.toFixed(2))}</span> · Total:{" "}
                  <span>{formatBRL(purchaseShareTarget.toFixed(2))}</span> · Saldo:{" "}
                  {purchaseShareBalanceStatus === "closed" ? (
                    <span className="cd-lanc-saldo-ok">fechado</span>
                  ) : purchaseShareBalanceStatus === "short" ? (
                    <span className="cd-lanc-saldo-err">
                      falta{" "}
                      {formatBRL(shareBalanceGap(purchaseShareTarget, allocatedShareTotal).toFixed(2))}
                    </span>
                  ) : (
                    <span className="cd-lanc-saldo-err">
                      sobra{" "}
                      {formatBRL(shareBalanceGap(purchaseShareTarget, allocatedShareTotal).toFixed(2))}
                    </span>
                  )}
                </div>
                <div className="cd-lanc-checks-group">
                  <button
                    type="button"
                    className={`cd-lanc-check-row${pago ? " cd-lanc-check-row--on" : ""}`}
                    disabled={periodClosed}
                    onClick={() => setPago((v) => !v)}
                  >
                    <div className="cd-lanc-chk" aria-hidden />
                    <div>
                      <div className="cd-lanc-check-label">Já pago</div>
                      <div className="cd-lanc-check-sub">Marcar este lançamento como pago</div>
                    </div>
                  </button>
                </div>
              </div>
              <div className="cd-lanc-modal-footer">
                <div className="cd-lanc-footer-grid">
                  <button
                    type="submit"
                    className="cd-lanc-btn-save"
                    disabled={periodClosed || saving || !categoriaId}
                  >
                    {saving
                      ? "Salvando…"
                      : editingId
                        ? "💾 Salvar alterações"
                        : "💾 Lançar"}
                  </button>
                  <button
                    type="button"
                    className="cd-lanc-btn-cancel"
                    onClick={() => closePurchaseModal()}
                    disabled={saving}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {showShareForm && shareEditingTx && (
        <div
          className="cd-lanc-overlay cd-lanc-overlay--open"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeShareModal();
          }}
        >
          <div
            className="cd-lanc-modal cd-div-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="share-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="cd-lanc-modal-header">
              <div className="cd-lanc-modal-title-row">
                <div className="cd-div-modal-icon" aria-hidden>
                  👥
                </div>
                <h2 id="share-modal-title" className="cd-lanc-modal-title">
                  Divisão entre pessoas
                </h2>
              </div>
              <button
                type="button"
                className="cd-lanc-modal-close"
                aria-label="Fechar"
                onClick={() => closeShareModal()}
              >
                ✕
              </button>
            </div>
            <div className="cd-div-txn-info">
              <span className="cd-div-txn-icon" aria-hidden>
                {categoryEmoji(categoryNameById(categories, shareEditingTx.categoria_id))}
              </span>
              <span className="cd-div-txn-name">
                {displayCardDescription(shareEditingTx.descricao)}
              </span>
              <span className="cd-div-txn-date">{formatDateBR(shareEditingTx.data)}</span>
              <span className="cd-div-txn-val">{formatBRL(shareEditingTx.valor)}</span>
            </div>
            <form onSubmit={onSubmitShare} className="cd-lanc-modal-form">
              <div className="cd-lanc-modal-body">
                <p className="cd-div-hint">
                  <Link to="/cartoes/pessoas">Cadastrar pessoas</Link> · A soma das partes precisa bater com o
                  total. Ao salvar, a proporção fica guardada para esta descrição neste cartão.
                </p>
                <div
                  className={`cd-saldo-row${editShareBalanceStatus === "closed" ? " cd-saldo-ok" : " cd-saldo-err"}`}
                >
                  <span className="cd-saldo-lbl">
                    {editShareBalanceStatus === "closed" ? "✓ Saldo fechado" : "⚠ Saldo aberto"}
                  </span>
                  <span className="cd-saldo-vals">
                    Soma: {formatBRL(allocatedShareTotal.toFixed(2))} · Total:{" "}
                    {formatBRL(editShareTarget.toFixed(2))}
                  </span>
                </div>
                <div className="cd-div-rows">
                  {shareRows.map((row, idx) => {
                    const spender = spenders.find((s) => s.id === row.spenderId);
                    const spenderName = spender?.nome ?? "";
                    const rowVal = parseFloat(row.valor.replace(",", ".")) || 0;
                    const pct =
                      editShareTarget > 0 ? Math.round((rowVal / editShareTarget) * 100) : 0;
                    return (
                      <div key={idx} className="cd-div-row">
                        <div
                          className="cd-div-av"
                          style={{ background: personGradient(spenderName || "?") }}
                          aria-hidden
                        >
                          {spenderName ? personInitials(spenderName) : "?"}
                        </div>
                        <div className="cd-div-select-wrap">
                          <select
                            className="cd-div-select"
                            value={row.spenderId}
                            onChange={(e) => {
                              const v = e.target.value;
                              setShareRows((rs) =>
                                autoSplitRowsOnPersonSelect(
                                  rs,
                                  idx,
                                  v,
                                  String(shareEditingTx.valor).replace(".", ","),
                                ),
                              );
                            }}
                            disabled={periodClosed || saving}
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
                        <span className="cd-div-pct-badge">{pct}%</span>
                        <input
                          className="cd-div-input"
                          value={row.valor}
                          onChange={(e) => {
                            const v = decimalPointToComma(e.target.value);
                            setShareRows((rs) => rs.map((x, i) => (i === idx ? { ...x, valor: v } : x)));
                          }}
                          placeholder="0,00"
                          disabled={periodClosed || saving}
                          inputMode="decimal"
                          aria-label={`Valor parte ${idx + 1}`}
                        />
                        <button
                          type="button"
                          className="cd-div-del"
                          onClick={() =>
                            setShareRows((rs) => {
                              const next = rs.filter((_, i) => i !== idx);
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
                <div className="cd-div-actions">
                  <button
                    type="button"
                    className="cd-div-btn-add"
                    onClick={() => setShareRows((r) => [...r, { spenderId: "", valor: "" }])}
                    disabled={periodClosed || saving}
                  >
                    ＋ Linha
                  </button>
                  <button
                    type="button"
                    className="cd-div-btn-recalc"
                    onClick={() =>
                      splitShareEquallyByTotal(String(shareEditingTx.valor).replace(".", ","))
                    }
                    disabled={periodClosed || saving}
                  >
                    ⟳ Recalcular partes iguais
                  </button>
                </div>
                <p className="cd-div-remove-hint">
                  Excluir todas as linhas (ou deixar em branco) e salvar remove a divisão deste lançamento.
                </p>
              </div>
              <div className="cd-lanc-modal-footer">
                <div className="cd-lanc-footer-grid">
                  <button type="submit" className="cd-lanc-btn-save" disabled={periodClosed || saving}>
                    {saving ? "Salvando…" : "💾 Salvar divisão"}
                  </button>
                  <button
                    type="button"
                    className="cd-lanc-btn-cancel"
                    onClick={() => closeShareModal()}
                    disabled={saving}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {showInstallmentForm && installmentEditingTx && (
        <div
          className="cd-lanc-overlay cd-lanc-overlay--open"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget && !savingInstallment) closeInstallmentModal();
          }}
        >
          <div
            className="cd-lanc-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="installment-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="cd-lanc-modal-header">
              <div id="installment-modal-title" className="cd-lanc-modal-title">
                Definir parcelas
              </div>
              <button
                type="button"
                className="cd-lanc-modal-close"
                aria-label="Fechar"
                disabled={savingInstallment}
                onClick={() => closeInstallmentModal()}
              >
                ✕
              </button>
            </div>
            <form onSubmit={onSubmitInstallment} className="cd-lanc-modal-form">
              <div className="cd-lanc-modal-body">
                <div className="cd-lanc-mais-txn-info">
                  <span className="cd-lanc-mais-txn-icon" aria-hidden>
                    📦
                  </span>
                  <div>
                    <div className="cd-lanc-mais-txn-name">
                      {displayCardDescription(installmentEditingTx.descricao)}
                    </div>
                    <div className="cd-lanc-mais-txn-meta">
                      Parcela atual: {installmentEditingTx.installment_number}/
                      {installmentEditingTx.installment_total}
                    </div>
                  </div>
                </div>
                <div className="cd-lanc-form-row">
                  <div className="cd-lanc-form-group">
                    <label className="cd-lanc-form-label">Parcela atual</label>
                    <input
                      className="cd-lanc-form-input"
                      type="number"
                      min={1}
                      max={120}
                      value={installmentCurrentInput}
                      onChange={(e) => setInstallmentCurrentInput(e.target.value)}
                      disabled={savingInstallment}
                      required
                    />
                  </div>
                  <div className="cd-lanc-form-group">
                    <label className="cd-lanc-form-label">Total de parcelas</label>
                    <input
                      className="cd-lanc-form-input"
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
              </div>
              <div className="cd-lanc-modal-footer">
                <div className="cd-lanc-footer-grid">
                  <button
                    type="button"
                    className="cd-lanc-btn-cancel"
                    onClick={() => closeInstallmentModal()}
                    disabled={savingInstallment}
                  >
                    Cancelar
                  </button>
                  <button type="submit" className="cd-lanc-btn-save" disabled={savingInstallment}>
                    {savingInstallment ? "Salvando…" : "Salvar parcelas"}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {showSpenderBoardModal && selectedSpenderGroup && (
        <div
          className="cd-person-overlay cd-person-overlay--open"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeSpenderBoardModal();
          }}
        >
          <div
            className="cd-person-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="spender-board-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="cd-person-modal-header">
              <div className="cd-person-modal-top-row">
                <div className="cd-person-modal-person-row">
                  <div
                    className="cd-person-modal-av"
                    style={{
                      background: personGradient(
                        selectedSpenderGroup.spender_nome ?? "Não atribuído",
                      ),
                    }}
                    aria-hidden
                  >
                    {personInitials(selectedSpenderGroup.spender_nome ?? "Não atribuído")}
                  </div>
                  <div className="cd-person-modal-info">
                    <div id="spender-board-title" className="cd-person-modal-name">
                      {selectedSpenderGroup.spender_nome ?? "Não atribuído"}
                    </div>
                    <div className="cd-person-modal-sub">
                      {card.nome}
                      {periodoLabel ? ` · ${periodoLabel}` : ""}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  className="cd-person-modal-close"
                  aria-label="Fechar"
                  onClick={() => closeSpenderBoardModal()}
                >
                  ✕
                </button>
              </div>
              <div className="cd-person-modal-total">
                <span className="cd-person-modal-total-lbl">Total usado no período</span>
                <span className="cd-person-modal-total-val">
                  {formatBRL(selectedSpenderGroup.total)}
                </span>
              </div>
            </div>

            <div className="cd-person-modal-divider" />

            <div className="cd-person-modal-list">
              {selectedSpenderGroup.lines.length === 0 ? (
                <p className="muted small cd-person-modal-empty">
                  Nenhum lançamento atribuído a esta pessoa neste período.
                </p>
              ) : (
                selectedSpenderGroup.lines.map((l, idx) => {
                  const tx = txs.find((t) => t.id === l.transaction_id);
                  const catName = categoryNameById(categories, tx?.categoria_id);
                  const valNum = parseFloat(l.valor_parte) || 0;
                  const isNegative = valNum < -0.009;
                  const displayVal = isNegative
                    ? `-${formatBRL(Math.abs(valNum))}`
                    : formatBRL(l.valor_parte);
                  const parcela =
                    tx && tx.installment_total > 1
                      ? `${tx.installment_number}/${tx.installment_total}`
                      : null;
                  return (
                    <div key={`${l.transaction_id}-${idx}`} className="cd-person-txn-item">
                      <div className="cd-person-txn-icon" aria-hidden>
                        {categoryEmoji(catName)}
                      </div>
                      <div className="cd-person-txn-info">
                        <div className="cd-person-txn-name">
                          {displayCardDescription(l.descricao)}
                        </div>
                        <div className="cd-person-txn-meta">
                          <span className="cd-person-txn-date">{formatShortDateBR(l.data)}</span>
                          <span className="cd-person-txn-cat">{catName}</span>
                          {parcela && <span className="cd-person-txn-parc">{parcela}</span>}
                        </div>
                      </div>
                      <div className="cd-person-txn-right">
                        <div
                          className={`cd-person-txn-val${isNegative ? " cd-person-txn-val--neg" : ""}`}
                        >
                          {displayVal}
                        </div>
                        <span
                          className={`cd-person-txn-dot${tx?.pago ? " cd-person-txn-dot--pago" : " cd-person-txn-dot--pend"}`}
                          aria-hidden
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
