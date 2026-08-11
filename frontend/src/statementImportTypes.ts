export type ImportPreviewStatus = "new" | "kept" | "updated" | "skip" | "orphan";

export type ImportPreviewRowApi = {
  status: ImportPreviewStatus;
  data: string;
  descricao: string;
  valor: string;
  parcela_atual: number | null;
  parcela_total: number | null;
  existing_transaction_id: string | null;
  previous_descricao: string | null;
  previous_valor: string | null;
  previous_data: string | null;
  categoria_id: string | null;
  categoria_nome: string | null;
  skip_reason: string | null;
  update_kind: "descricao" | "valor" | "both" | null;
  remove_by_default?: boolean;
};

export type ImportPreviewSummary = {
  new: number;
  kept: number;
  updated: number;
  skip: number;
  orphan: number;
  total_in_file: number;
};

export type ImportPreviewResponse = {
  rows: ImportPreviewRowApi[];
  summary: ImportPreviewSummary;
  warnings: string[];
  format_used: string;
};

export type ImportPreviewEditableRow = {
  status: ImportPreviewStatus;
  data: string;
  descricao: string;
  valor: string;
  parcelaAtual: number | null;
  parcelaTotal: number | null;
  existingTransactionId: string | null;
  previousDescricao: string | null;
  previousValor: string | null;
  previousData: string | null;
  categoriaId: string;
  categoriaNome: string | null;
  skipReason: string | null;
  updateKind: "descricao" | "valor" | "both" | null;
  skipped: boolean;
  applyUpdate: boolean;
  /** Órfão: marcado para remoção no confirm. */
  removeOrphan: boolean;
};

export type ImportPreviewSession = {
  cardId: string;
  periodId: string;
  fileName: string;
  formatId: string;
  formatTab: "csv" | "pdf";
  warnings: string[];
  summary: ImportPreviewSummary;
  rows: ImportPreviewEditableRow[];
};

export const IMPORT_PREVIEW_STORAGE_KEY = "fms:import-preview:v1";
