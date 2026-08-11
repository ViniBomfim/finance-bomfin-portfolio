from __future__ import annotations

import re
import unicodedata


def normalize_statement_desc(desc: str) -> str:
    """Normaliza descrição para matching de filtros (lowercase, sem acento, espaços colapsados)."""
    s = " ".join((desc or "").strip().lower().split())
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Pagamentos da fatura — não entram como gasto nem no total oficial.
_STATEMENT_PAYMENT_RE = re.compile(
    r"pagamento\s+recebido|"
    r"pagamento\s+efetuado|"
    r"pagamento\s+(de\s+)?fatura|"
    r"pagamento\s+com\s+saldo|"
    r"pagamento\s+em\s+\d{1,2}\s+[a-z]{3,9}|"
    r"fatura\s+paga|"
    r"credito\s+antecipado|"
    r"antecipacao",
    re.I,
)

# Resumos / saldos / pendências — não são compras da fatura.
_STATEMENT_SUMMARY_RE = re.compile(
    r"saldo\s+anterior|"
    r"saldo\s+restante\s+da\s+fatura\s+anterior|"
    r"valor\s+pendente(\s+do\s+mes\s+anterior)?|"
    r"total\s+a\s+pagar|"
    r"total\s+na\s+fatura|"
    r"falta\s+pagar|"
    r"proxima\s+fatura|"
    r"limite\s+(dispon|total)|"
    r"resumo\s+da\s+fatura|"
    r"demonstrativo|"
    r"emissao\s+e\s+envio",
    re.I,
)


def is_statement_payment_description(desc: str) -> bool:
    """Linhas de pagamento da fatura não compõem o total oficial de gastos."""
    return bool(_STATEMENT_PAYMENT_RE.search(normalize_statement_desc(desc)))


def is_statement_summary_description(desc: str) -> bool:
    """Linhas de resumo/saldo/pendência não são lançamentos de compra."""
    return bool(_STATEMENT_SUMMARY_RE.search(normalize_statement_desc(desc)))


def is_statement_non_purchase_description(desc: str) -> bool:
    """Pagamento ou resumo — deve ser filtrado no parse e marcado skip no preview."""
    d = normalize_statement_desc(desc)
    return bool(_STATEMENT_PAYMENT_RE.search(d) or _STATEMENT_SUMMARY_RE.search(d))


def statement_skip_reason(desc: str) -> str | None:
    """Motivo de skip para o preview, ou None se a linha deve ser importada."""
    d = normalize_statement_desc(desc)
    if _STATEMENT_PAYMENT_RE.search(d):
        return "payment_line"
    if _STATEMENT_SUMMARY_RE.search(d):
        return "summary_line"
    return None
