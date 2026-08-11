import { parseBrazilianMoney } from "./parseCardCsv";
import type { Category } from "./types";
import type {
  ImportPreviewEditableRow,
  ImportPreviewResponse,
  ImportPreviewRowApi,
  ImportPreviewSession,
} from "./statementImportTypes";

export function normalizeDescForMatch(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

export function shouldSuggestCarCategory(desc: string): boolean {
  const d = normalizeDescForMatch(desc);
  const carHints = [
    "nutag*",
    "transacao de nutag",
    "uber",
    "99app",
    "99 *",
    "auto posto",
    "abastec",
    "posto de serv",
    "pedagio",
    "pedágio",
    "rodoanel",
    "sem parar",
    "conectcar",
    "veloe",
    "parking",
    "estacionamento",
    "shellbox",
    "ipiranga",
  ];
  return carHints.some((hint) => d.includes(normalizeDescForMatch(hint)));
}

export function suggestCategoryId(desc: string, categories: Category[]): string {
  const carroId = findCarCategoryId(categories);
  if (carroId && shouldSuggestCarCategory(desc)) return carroId;

  const d = normalizeDescForMatch(desc);
  const rules: { hints: string[]; names: string[] }[] = [
    {
      hints: ["ifood", "rappi", "restaurante", "padaria", "supermercado", "mercado*", "assai", "atacadao"],
      names: ["alimentacao", "alimentação", "comida", "mercado"],
    },
    {
      hints: ["farmacia", "drogaria", "raia", "drogasil", "panvel"],
      names: ["saude", "saúde", "farmacia", "farmácia"],
    },
    {
      hints: ["spotify", "netflix", "disney", "amazon prime", "youtube", "apple.com/bill", "claro", "vivo", "tim"],
      names: ["assinatura", "streaming", "contas", "servicos", "serviços"],
    },
    {
      hints: ["hotel", "booking", "airbnb", "gol linhas", "latam", "azul", "buser", "passagem"],
      names: ["viagem", "turismo"],
    },
    {
      hints: ["magazine", "americanas", "casasbahia", "mercado livre", "shopee", "amazon"],
      names: ["compras", "shopping"],
    },
  ];

  for (const rule of rules) {
    if (!rule.hints.some((h) => d.includes(normalizeDescForMatch(h)))) continue;
    const found = categories.find((c) => {
      const n = normalizeDescForMatch(c.nome);
      return rule.names.some((name) => n.includes(normalizeDescForMatch(name)));
    });
    if (found) return found.id;
  }
  return "";
}

export function findCarCategoryId(categories: Category[]): string {
  const c = categories.find((x) => x.nome.toLowerCase().trim() === "carro");
  if (c) return c.id;
  const c2 = categories.find((x) => x.nome.toLowerCase().includes("carro"));
  return c2?.id ?? "";
}

export function decimalPointToComma(val: string): string {
  const n = parseFloat(val);
  if (!Number.isFinite(n)) return val.replace(".", ",");
  return n.toFixed(2).replace(".", ",");
}

export function valorToApi(s: string): string {
  const n = parseBrazilianMoney(s);
  if (n === null || n === 0) return "0";
  return n.toFixed(2);
}

export function formatDateBR(isoDate: string): string {
  if (!isoDate) return "—";
  const [y, m, d] = isoDate.split("-");
  if (!y || !m || !d) return isoDate;
  return `${d}/${m}/${y}`;
}

export function categoryEmoji(name: string): string {
  const n = name.toLowerCase();
  if (n.includes("viagem")) return "✈️";
  if (n.includes("casa")) return "🏡";
  if (n.includes("compra")) return "🛍️";
  if (n.includes("carro")) return "🚗";
  if (n.includes("conta")) return "📋";
  if (n.includes("transport")) return "🚕";
  if (n.includes("lazer")) return "🎭";
  if (n.includes("aliment")) return "🍽️";
  return "🏪";
}

export function categoryNameById(categories: Category[], id: string | null | undefined): string {
  if (!id) return "Sem categoria";
  return categories.find((c) => c.id === id)?.nome ?? "Outros";
}

function mapApiRow(row: ImportPreviewRowApi, categories: Category[]): ImportPreviewEditableRow {
  const suggestedId = row.status === "new" ? suggestCategoryId(row.descricao, categories) : "";
  const categoriaId = row.categoria_id ?? suggestedId ?? "";
  return {
    status: row.status,
    data: row.data,
    descricao: row.descricao,
    valor: decimalPointToComma(row.valor),
    parcelaAtual: row.parcela_atual,
    parcelaTotal: row.parcela_total,
    existingTransactionId: row.existing_transaction_id,
    previousDescricao: row.previous_descricao,
    previousValor: row.previous_valor ? decimalPointToComma(row.previous_valor) : null,
    previousData: row.previous_data,
    categoriaId,
    categoriaNome: row.categoria_nome,
    skipReason: row.skip_reason,
    updateKind: row.update_kind,
    skipped: false,
    applyUpdate: row.status === "updated",
    removeOrphan: row.status === "orphan" ? row.remove_by_default !== false : false,
  };
}

export function buildPreviewSession(args: {
  preview: ImportPreviewResponse;
  categories: Category[];
  cardId: string;
  periodId: string;
  fileName: string;
  formatId: string;
  formatTab: "csv" | "pdf";
}): ImportPreviewSession {
  return {
    cardId: args.cardId,
    periodId: args.periodId,
    fileName: args.fileName,
    formatId: args.formatId,
    formatTab: args.formatTab,
    warnings: args.preview.warnings,
    summary: args.preview.summary,
    rows: args.preview.rows.map((r) => mapApiRow(r, args.categories)),
  };
}

export function updateKindLabel(kind: ImportPreviewEditableRow["updateKind"]): string {
  if (kind === "valor") return "Valor ou data da parcela";
  if (kind === "both") return "Nome e valor diferentes";
  return "Nome ou data atualizado";
}

export function skipReasonLabel(reason: string | null): string {
  if (reason === "payment_line") return "Pagamento da fatura";
  if (reason === "summary_line") return "Resumo / saldo / valor pendente";
  if (reason === "already_exists") return "Já existe no período";
  if (reason === "duplicate_in_file") return "Duplicado no arquivo";
  return reason ?? "Ignorado";
}

export const PREVIEW_ROW_LIMIT = 8;
