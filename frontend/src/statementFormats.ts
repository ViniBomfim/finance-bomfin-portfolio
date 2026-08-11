import type { CardRow } from "./types";

/** Cartões Nubank: só estes formatos na importação. */
export const STATEMENT_FORMAT_OPTIONS_NUBANK = [
  { id: "nubank_pdf", label: "PDF Nubank" },
  { id: "nubank_csv", label: "CSV Nubank" },
] as const;

/** Demais cartões: sem opção Nubank na lista. */
export const STATEMENT_FORMAT_OPTIONS_OTHER = [
  { id: "generic_csv", label: "CSV genérico (fallback)" },
  { id: "pdf_br", label: "PDF — fatura digital (texto extraído)" },
] as const;

/** Santander: parser dedicado para layout da fatura. */
export const STATEMENT_FORMAT_OPTIONS_SANTANDER = [
  { id: "santander_pdf", label: "PDF Santander" },
  { id: "santander_csv", label: "CSV Santander" },
] as const;

/** Itaú Azul: parser dedicado para PDF e CSV. */
export const STATEMENT_FORMAT_OPTIONS_ITAU_AZUL = [
  { id: "itau_azul_pdf", label: "PDF Itaú Azul" },
  { id: "itau_azul_csv", label: "CSV Itaú Azul" },
] as const;

/** Itaú PDA: parser dedicado para PDF e CSV. */
export const STATEMENT_FORMAT_OPTIONS_ITAU_PDA = [
  { id: "itau_pda_pdf", label: "PDF Itaú PDA" },
  { id: "itau_pda_csv", label: "CSV Itaú PDA" },
] as const;

export type StatementFormatId =
  | (typeof STATEMENT_FORMAT_OPTIONS_NUBANK)[number]["id"]
  | (typeof STATEMENT_FORMAT_OPTIONS_OTHER)[number]["id"]
  | (typeof STATEMENT_FORMAT_OPTIONS_SANTANDER)[number]["id"]
  | (typeof STATEMENT_FORMAT_OPTIONS_ITAU_AZUL)[number]["id"]
  | (typeof STATEMENT_FORMAT_OPTIONS_ITAU_PDA)[number]["id"];

export function isNubankCard(card: CardRow | null): boolean {
  if (!card) return false;
  const b = card.banco.toLowerCase();
  const n = card.nome.toLowerCase();
  return (
    b.includes("nubank") ||
    n.includes("nubank") ||
    /^nu$/i.test(card.banco.trim()) ||
    n.includes("roxinho")
  );
}

export function isSantanderCard(card: CardRow | null): boolean {
  if (!card) return false;
  const b = card.banco.toLowerCase();
  const n = card.nome.toLowerCase();
  return b.includes("santander") || n.includes("santander");
}

export function isItauAzulCard(card: CardRow | null): boolean {
  if (!card) return false;
  const b = card.banco.toLowerCase();
  const n = card.nome.toLowerCase();
  return (b.includes("itau") || b.includes("itaú")) && n.includes("azul");
}

export function isItauPdaCard(card: CardRow | null): boolean {
  if (!card) return false;
  const b = card.banco.toLowerCase();
  const n = card.nome.toLowerCase();
  return (b.includes("itau") || b.includes("itaú")) && n.includes("pda");
}

export function statementFormatOptionsForCard(card: CardRow | null) {
  if (isNubankCard(card)) return STATEMENT_FORMAT_OPTIONS_NUBANK;
  if (isSantanderCard(card)) return STATEMENT_FORMAT_OPTIONS_SANTANDER;
  if (isItauAzulCard(card)) return STATEMENT_FORMAT_OPTIONS_ITAU_AZUL;
  if (isItauPdaCard(card)) return STATEMENT_FORMAT_OPTIONS_ITAU_PDA;
  return STATEMENT_FORMAT_OPTIONS_OTHER;
}

export function defaultStatementFormatForCard(card: CardRow | null): StatementFormatId {
  if (isNubankCard(card)) return "nubank_pdf";
  if (isSantanderCard(card)) return "santander_pdf";
  if (isItauAzulCard(card)) return "itau_azul_pdf";
  if (isItauPdaCard(card)) return "itau_pda_pdf";
  return "generic_csv";
}

export type ImportFormatTab = "csv" | "pdf";

export function statementFormatForTab(card: CardRow | null, tab: ImportFormatTab): StatementFormatId {
  const opts = statementFormatOptionsForCard(card);
  const match = opts.find((o) => (tab === "csv" ? o.id.includes("csv") : o.id.includes("pdf")));
  return match?.id ?? opts[0]!.id;
}

export function defaultImportFormatTab(card: CardRow | null): ImportFormatTab {
  // Bancos com parser PDF dedicado abrem na aba PDF; demais preferem CSV.
  if (isNubankCard(card) || isSantanderCard(card) || isItauAzulCard(card) || isItauPdaCard(card)) {
    return "pdf";
  }
  const opts = statementFormatOptionsForCard(card);
  return opts.some((o) => o.id.includes("csv")) ? "csv" : "pdf";
}
