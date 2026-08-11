"""Extrai apenas linhas que parecem compras de faturas CSV/PDF (vários bancos)."""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from typing import Final

from fastapi import HTTPException, status

from app.services.statement_total_rules import is_statement_non_purchase_description

_MAX_BYTES: Final[int] = 5 * 1024 * 1024

# Pagamentos, taxas e linhas de resumo — não são compras no cartão
# Sufixo típico na fatura Nubank: " - Parcela 8/10"
_PARCELA_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"\s*[-–—]\s*Parcela\s+(\d{1,3})\s*/\s*(\d{1,3})\s*$",
    re.I,
)
# Ex.: "Casasbahiacom (Parcela 2/9)"
_PARCELA_PARENS_RE: Final[re.Pattern[str]] = re.compile(
    r"\s*\(\s*Parcela\s+(\d{1,3})\s*/\s*(\d{1,3})\s*\)\s*$",
    re.I,
)
# Ex.: "Casasbahiacom (2/9)" — só números (fatura ou texto já normalizado)
_BARE_PARCELAS_PARENS_RE: Final[re.Pattern[str]] = re.compile(
    r"\s*\(\s*(\d{1,3})\s*/\s*(\d{1,3})\s*\)\s*$",
)
# Ex.: "Casasbahiacom 2/9" ou "Casasbahiacom parcela 2/9"
_BARE_PARCELA_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"\s+(?:parcela\s+)?(\d{1,3})\s*/\s*(\d{1,3})\s*$",
    re.I,
)


def extract_parcela_from_description(desc: str) -> tuple[str, int | None, int | None]:
    """Remove indicação de parcela do fim da descrição; devolve (nome limpo, atual, total).

    Reconhece no fim: `` - Parcela X/Y``, ``(Parcela X/Y)``, ``(X/Y)`` ou `` X/Y``.
    A descrição retornada fica só com o nome do estabelecimento; X/Y vai em metadados.
    """
    s = desc.strip()
    for pattern in (_PARCELA_SUFFIX_RE, _PARCELA_PARENS_RE, _BARE_PARCELAS_PARENS_RE, _BARE_PARCELA_SUFFIX_RE):
        m = pattern.search(s)
        if not m:
            continue
        atual, total = int(m.group(1)), int(m.group(2))
        clean = pattern.sub("", s).strip()
        base = clean if clean else s
        if atual < 1 or total < 1 or atual > total:
            return base, None, None
        return base, atual, total
    s2 = re.sub(r"\s*\(\s*Parcela\s+(\d{1,3})\s*/\s*(\d{1,3})\s*\)", "", s, flags=re.I)
    s2 = re.sub(
        r"\s*[-–—]\s*Parcela\s+(\d{1,3})\s*/\s*(\d{1,3})\s*$",
        "",
        s2,
        flags=re.I,
    )
    s2 = re.sub(r"\s*\(\s*(\d{1,3})\s*/\s*(\d{1,3})\s*\)\s*$", "", s2)
    s2 = re.sub(r"\s+(?:parcela\s+)?(\d{1,3})\s*/\s*(\d{1,3})\s*$", "", s2, flags=re.I)
    return s2.strip(), None, None


def canonical_card_description(desc: str) -> str:
    """Nome do estabelecimento sem sufixo de parcela no fim; evita duplicar a mesma compra com textos diferentes."""
    base, _, _ = extract_parcela_from_description(desc)
    return base.strip()[:500]


def _clean_description(desc: str) -> str:
    """
    Limpa prefixos comuns de fatura:
    - símbolos antes do texto (••••, **, hífens)
    - número de cartão mascarado no início (ex.: 8879)
    """
    s = " ".join(desc.strip().split())
    s = re.sub(r"^[^\wÀ-ÿ]+", "", s)
    s = re.sub(r"^\d{3,6}\s+", "", s)
    s = re.sub(r"^[^\wÀ-ÿ]+", "", s)
    # Em alguns PDFs o parser deixa um sufixo residual de moeda na descrição ("-R$").
    s = re.sub(r"\s*[-–—]?\s*R\$\s*$", "", s, flags=re.I)
    s = re.sub(r"\s*[-–—]\s*$", "", s)
    return s.strip()


_SKIP_DESC_RE: Final[tuple[re.Pattern[str], ...]] = (
    # Mantido para heurísticas locais de PDF; o filtro canônico é statement_total_rules.
    re.compile(
        r"pagamento\s+(de\s+)?fatura|fatura\s+paga|pagamento\s+recebido|pagamento\s+efetuado|pagamento\s+com\s+saldo|"
        r"pagamento\s+em\s+\d{1,2}\s+[a-z]{3,9}|"
        r"cr[eé]dito\s+antecipado|antecipa[cç][aã]o",
        re.I,
    ),
    re.compile(
        r"saldo\s+anterior|valor\s+pendente|total\s+a\s+pagar|pr[oó]xima\s+fatura|"
        r"limite\s+dispon|resumo\s+da\s+fatura|demonstrativo",
        re.I,
    ),
    re.compile(
        r"\bol[aá],?\b|esta\s+[ée]\s+a\s+sua\s+fatura|limite\s+total\s+do\s+cart[aã]o|"
        r"emiss[aã]o\s+e\s+envio|vencimento|fatura\s+[a-z]{3}\s+\d{4}",
        re.I,
    ),
    re.compile(r"transfer[eê]ncia\s+(recebida|enviada)|pix\s+recebido", re.I),
)


@dataclass(frozen=True)
class _Row:
    data: str
    descricao: str
    valor: str  # decimal string com ponto


def _norm_header(h: str) -> str:
    h = h.lower().strip().replace("\ufeff", "")
    return "".join(c for c in unicodedata.normalize("NFD", h) if unicodedata.category(c) != "Mn")


def _parse_brl_money(s: str) -> Decimal | None:
    t = (
        s.strip()
        .replace("\u2212", "-")  # unicode minus
        .replace("\u2013", "-")  # en dash sometimes from PDF
        .replace("\u2014", "-")  # em dash sometimes from PDF
        .replace(" ", "")
        .replace("R$", "")
        .replace("r$", "")
    )
    if not t:
        return None
    neg = t.startswith("-") or t.startswith("(")
    u = t.replace("(", "").replace(")", "").lstrip("-")
    try:
        if "," in u and re.search(r"\.\d{3}", u):
            u = u.replace(".", "").replace(",", ".")
        elif "," in u:
            u = u.replace(",", ".")
        v = Decimal(u)
        if neg:
            v = -v
        return v
    except InvalidOperation:
        return None


def _parse_date_iso(s: str) -> str | None:
    t = s.strip()[:10]
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y}-{mo:02d}-{d:02d}"
    m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})", t)
    if m2:
        return f"{m2[1]}-{m2[2]}-{m2[3]}"
    return None


def _looks_like_cardholder_name(desc: str) -> bool:
    """Heurística conservadora para nome do titular no cabeçalho da fatura.

    Evita falso positivo em estabelecimentos com iniciais (ex.: "A e e Estacionamento").
    """
    d = desc.strip()
    if not d:
        return False
    if re.search(r"[^A-Za-zÀ-ÿ\s]", d):
        return False
    words = d.split()
    if len(words) < 4 or len(words) > 5:
        return False
    if len(words[0]) < 3 or len(words[-1]) < 3:
        return False
    middle = words[1:-1]
    # Padrão alvo: "Nome X Y Sobrenome" (miolo só com iniciais/partículas curtas).
    return len(middle) >= 2 and all(len(w) <= 2 for w in middle)


def _is_purchase_description(desc: str) -> bool:
    d = _clean_description(desc)
    if len(d) < 2:
        return False
    # Nome do titular no topo da fatura (ex.: "Joao A B Silva").
    if _looks_like_cardholder_name(d):
        return False
    if is_statement_non_purchase_description(d):
        return False
    for pat in _SKIP_DESC_RE:
        if pat.search(d):
            return False
    return True


def _is_nubank_statement_item(desc: str) -> bool:
    """
    Filtro mais permissivo para Nubank PDF:
    mantém praticamente tudo que tenha data+valor, descartando só cabeçalhos/resumos.
    """
    d = _clean_description(desc)
    if len(d) < 2:
        return False
    if is_statement_non_purchase_description(d):
        return False
    low = d.lower()
    if re.match(r"^(transa[cç][oõ]es|fatura|compras de)\b", low):
        return False
    if re.search(
        r"total na fatura|falta pagar|limite total|emiss[aã]o e envio|resumo da fatura|demonstrativo",
        low,
    ):
        return False
    low_norm = re.sub(r"\s*[-–—]?\s*r\$\s*$", "", low)
    if re.search(r"^pagamento\s+em\s+\d{1,2}\s+[a-z]{3,9}\b", low_norm):
        return False
    if re.search(
        r"^pagamento\s+(de\s+)?fatura\b|"
        r"^fatura\s+paga\b|"
        r"saldo\s+restante\s+da\s+fatura\s+anterior|"
        r"saldo\s+anterior|"
        r"valor\s+pendente",
        low_norm,
    ):
        return False
    # Evita nome puro do titular.
    if _looks_like_cardholder_name(d):
        return False
    return True


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _split_csv_line(line: str, delim: str) -> list[str]:
    out: list[str] = []
    cur = ""
    in_q = False
    for c in line:
        if c == '"':
            in_q = not in_q
        elif c == delim and not in_q:
            out.append(cur.strip())
            cur = ""
        else:
            cur += c
    out.append(cur.strip())
    return out


def parse_generic_csv(text: str, default_date: str | None) -> list[_Row]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    first = lines[0]
    delim = ";" if first.count(";") >= first.count(",") else ","
    matrix = [_split_csv_line(ln, delim) for ln in lines]
    if not matrix[0]:
        return []

    h0 = [_norm_header(x) for x in matrix[0]]
    col_data = col_desc = col_valor = -1
    for i, h in enumerate(h0):
        if re.search(r"^(data|date|dt|vencimento)$|^data da compra$|^compra$", h):
            col_data = i
        elif re.search(r"^(valor|amount|value|total)$", h):
            col_valor = i
        elif re.search(
            r"desc|historico|estabelecimento|title|memo|lancamento|identificador|estabelec",
            h,
        ):
            col_desc = i

    start_row = 0
    has_header = col_data >= 0 or col_valor >= 0 or col_desc >= 0
    if has_header:
        if col_data < 0:
            col_data = next((i for i, x in enumerate(h0) if re.search(r"data|date|vencimento|compra", x)), -1)
        if col_valor < 0:
            col_valor = next((i for i, x in enumerate(h0) if re.search(r"valor|amount|total", x)), -1)
        if col_desc < 0:
            col_desc = next(
                (i for i, x in enumerate(h0) if re.search(r"desc|histor|title|estab|memo|ident|lancamento", x)),
                -1,
            )
        start_row = 1

    if col_desc < 0 and col_data >= 0 and col_valor >= 0:
        for i in range(len(h0)):
            if i != col_data and i != col_valor:
                col_desc = i
                break

    if col_valor < 0 and len(matrix[0]) >= 3:
        col_data, col_desc, col_valor = 0, 1, 2
        start_row = 0
        if _parse_brl_money(matrix[0][col_valor] or "") is None:
            start_row = 1
    elif col_valor < 0 and len(matrix[0]) == 2:
        col_desc, col_valor = 0, 1
        start_row = 0
        if _parse_brl_money(matrix[0][col_valor] or "") is None:
            start_row = 1

    if col_valor < 0:
        return []

    out: list[_Row] = []
    for r in range(start_row, len(matrix)):
        row = matrix[r]
        mx = max(col_data, col_desc, col_valor)
        if len(row) <= mx:
            continue
        ds = (row[col_data] if col_data >= 0 else "").strip()
        desc = (row[col_desc] if col_desc >= 0 else row[0] or "").strip() or "Importação"
        desc = _clean_description(desc)
        vs = (row[col_valor] or "").strip()
        data_iso = _parse_date_iso(ds) if ds else None
        if not data_iso and default_date:
            data_iso = default_date
        if not data_iso:
            continue
        val = _parse_brl_money(vs)
        if val is None or val == 0:
            continue
        if not _is_purchase_description(desc):
            continue
        out.append(_Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01")))))
    return out


def parse_nubank_csv(text: str, default_date: str | None) -> list[_Row]:
    """CSV estilo Nubank / fintech: cabeçalhos em inglês ou português, valor pode ser negativo."""
    f = StringIO(text)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    f.seek(0)
    reader = csv.DictReader(f, dialect=dialect)
    if not reader.fieldnames:
        return parse_generic_csv(text, default_date)

    fn = {(_norm_header(k) if k else ""): k for k in reader.fieldnames if k}

    def pick(*candidates: str) -> str | None:
        for c in candidates:
            for key, orig in fn.items():
                if c in key or key in c:
                    return orig
        return None

    k_date = pick("data", "date")
    k_title = pick("title", "descri", "estabelecimento", "memo")
    k_amount = pick("amount", "valor", "value")
    if not k_amount or not k_title:
        return parse_generic_csv(text, default_date)

    out: list[_Row] = []
    for rec in reader:
        raw_d = (rec.get(k_date) or "").strip()
        desc = (rec.get(k_title) or "").strip() or "Compra"
        desc = _clean_description(desc)
        raw_v = (rec.get(k_amount) or "").strip()
        data_iso = _parse_date_iso(raw_d) if raw_d else None
        if not data_iso and default_date:
            data_iso = default_date
        if not data_iso:
            continue
        val = _parse_brl_money(raw_v)
        if val is None or val == 0:
            continue
        if not _is_purchase_description(desc):
            continue
        out.append(_Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01")))))
    return out


def _csv_dict_reader(text: str) -> csv.DictReader[str]:
    f = StringIO(text)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    f.seek(0)
    return csv.DictReader(f, dialect=dialect)


def _pick_csv_column(norm_headers: dict[str, str], *candidates: str) -> str | None:
    for c in candidates:
        for key, orig in norm_headers.items():
            if c in key or key in c:
                return orig
    return None


def _extract_installment_pair(
    *,
    parcela_text: str,
    parcela_atual_text: str,
    parcela_total_text: str,
) -> tuple[int | None, int | None]:
    txt = " ".join(
        x.strip() for x in (parcela_text, parcela_atual_text, parcela_total_text) if x and x.strip()
    )
    if txt:
        for m in re.finditer(
            r"(?:parcela\s*)?(\d{1,3})\s*(?:ª|o|a)?\s*(?:parcela\s*)?(?:/|de)\s*(\d{1,3})",
            txt,
            re.I,
        ):
            pa, pt = int(m.group(1)), int(m.group(2))
            if pa >= 1 and pt >= 1 and pa <= pt:
                return pa, pt
    pa_s = re.search(r"\d{1,3}", parcela_atual_text or "")
    pt_s = re.search(r"\d{1,3}", parcela_total_text or "")
    if pa_s and pt_s:
        pa, pt = int(pa_s.group(0)), int(pt_s.group(0))
        if pa >= 1 and pt >= 1 and pa <= pt:
            return pa, pt
    return None, None


def _extract_money_from_cell(raw: str) -> Decimal | None:
    val = _parse_brl_money(raw)
    if val is not None:
        return val
    m = re.search(r"-?\s*(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|-?\s*(?:R\$\s*)?\d+,\d{2}", raw, re.I)
    if not m:
        return None
    return _parse_brl_money(m.group(0))


def _append_installment_suffix(desc: str, pa: int | None, pt: int | None) -> str:
    if pa is None or pt is None:
        return desc
    base, pa0, pt0 = extract_parcela_from_description(desc)
    if pa0 is not None and pt0 is not None:
        return desc
    return f"{base} ({pa}/{pt})".strip()


def _parse_bank_csv_with_installments(text: str, default_date: str | None) -> list[_Row]:
    reader = _csv_dict_reader(text)
    if not reader.fieldnames:
        return parse_generic_csv(text, default_date)
    norm_headers = {(_norm_header(k) if k else ""): k for k in reader.fieldnames if k}

    k_date = _pick_csv_column(
        norm_headers,
        "data",
        "date",
        "dt",
        "vencimento",
        "compra",
    )
    k_desc = _pick_csv_column(
        norm_headers,
        "descricao",
        "descri",
        "estabelecimento",
        "historico",
        "lancamento",
        "title",
        "memo",
        "identificador",
    )
    k_valor = _pick_csv_column(
        norm_headers,
        "valor",
        "amount",
        "value",
        "total",
    )
    k_parcela = _pick_csv_column(
        norm_headers,
        "parcela",
        "parc",
        "n da parcela",
        "numero da parcela",
        "numero parcela",
        "n parcela",
        "nr parcela",
        "nro parcela",
    )
    k_parcela_atual = _pick_csv_column(
        norm_headers,
        "parcela atual",
        "num parcela",
        "n parcela",
        "current installment",
    )
    k_parcela_total = _pick_csv_column(
        norm_headers,
        "total de parcelas",
        "qtde parcelas",
        "qtd parcelas",
        "parcelas totais",
        "total parcelas",
        "qtd parc",
        "qtde parc",
    )
    if not k_valor or not k_desc:
        return parse_generic_csv(text, default_date)

    out: list[_Row] = []
    for rec in reader:
        raw_d = (rec.get(k_date) or "").strip() if k_date else ""
        raw_desc = (rec.get(k_desc) or "").strip() or "Compra"
        raw_v = (rec.get(k_valor) or "").strip()
        desc = _clean_description(raw_desc)

        data_iso = _parse_date_iso(raw_d) if raw_d else None
        if not data_iso and default_date:
            data_iso = default_date
        if not data_iso:
            continue

        val = _extract_money_from_cell(raw_v)
        if val is None or val == 0:
            continue

        pa, pt = _extract_installment_pair(
            parcela_text=(rec.get(k_parcela) or "").strip() if k_parcela else "",
            parcela_atual_text=(rec.get(k_parcela_atual) or "").strip() if k_parcela_atual else "",
            parcela_total_text=(rec.get(k_parcela_total) or "").strip() if k_parcela_total else "",
        )
        if pa is None or pt is None:
            flat_chunks: list[str] = []
            for v in rec.values():
                if not v:
                    continue
                if isinstance(v, list):
                    flat_chunks.extend(str(x).strip() for x in v if str(x).strip())
                else:
                    s = str(v).strip()
                    if s:
                        flat_chunks.append(s)
            extra_fields = " ".join(flat_chunks)
            pa, pt = _extract_installment_pair(
                parcela_text=extra_fields,
                parcela_atual_text="",
                parcela_total_text="",
            )
        desc = _append_installment_suffix(desc, pa, pt)

        if not _is_purchase_description(desc):
            continue
        out.append(_Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01")))))
    return out


def parse_itau_azul_csv(text: str, default_date: str | None) -> list[_Row]:
    return _parse_bank_csv_with_installments(text, default_date)


def parse_itau_pda_csv(text: str, default_date: str | None) -> list[_Row]:
    return _parse_bank_csv_with_installments(text, default_date)


def parse_santander_csv(text: str, default_date: str | None) -> list[_Row]:
    return _parse_bank_csv_with_installments(text, default_date)


def _extract_pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Leitura de PDF indisponível no servidor.",
        ) from e
    try:
        reader = PdfReader(BytesIO(content))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não foi possível ler o PDF: {ex!s}",
        ) from ex


def _join_pdf_line_fragments(parts: list[tuple[float, str]]) -> str:
    """
    Junta os trechos de uma mesma linha respeitando as quebras do pypdf.

    Trechos com a mesma origem horizontal e trechos iniciados por letra acentuada são
    continuação da palavra anterior ("Lan" + "ç" + "amentos"); os demais são colunas
    distintas e precisam de espaço.
    """
    out = ""
    prev_x: float | None = None
    for x, txt in parts:
        if not out:
            out = txt
        elif prev_x is not None and abs(x - prev_x) < 0.01:
            out += txt
        elif txt[:1].isalpha() and not txt[0].isascii():
            out += txt
        elif out.endswith(" ") or txt.startswith(" "):
            out += txt
        else:
            out += " " + txt
        prev_x = x
    return out


def _extract_pdf_text_columns(content: bytes) -> str:
    """
    Extração posicional para faturas diagramadas em duas colunas (layout Itaú).

    A extração linear do pypdf entrega as linhas de lançamento antes dos títulos de
    seção e intercala as duas colunas, o que quebra qualquer parser que dependa do
    bloco em que a linha está. Aqui reconstruímos a ordem visual: coluna esquerda
    inteira de cima para baixo e depois a coluna direita.
    """
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Leitura de PDF indisponível no servidor.",
        ) from e

    try:
        reader = PdfReader(BytesIO(content))
        pages_out: list[str] = []
        for page in reader.pages:
            chunks: list[tuple[float, float, str]] = []

            def visitor(text, cm, tm, font_dict, font_size, _sink=chunks):  # noqa: ANN001
                if text and text.strip():
                    _sink.append((float(tm[5]), float(tm[4]), text.replace("\n", " ")))

            page.extract_text(visitor_text=visitor)
            if not chunks:
                continue

            try:
                mid_x = float(page.mediabox.width) / 2
            except Exception:
                mid_x = 0.0

            # Trechos com o mesmo topo (tolerância de 2pt) e mesma coluna formam uma linha.
            lines: list[tuple[int, float, list[tuple[float, str]]]] = []
            for y, x, txt in chunks:
                col = 0 if x < mid_x else 1
                slot = next(
                    (ln for ln in lines if ln[0] == col and abs(ln[1] - y) <= 2.0),
                    None,
                )
                if slot is None:
                    lines.append((col, y, [(x, txt)]))
                else:
                    slot[2].append((x, txt))

            lines.sort(key=lambda ln: (ln[0], -ln[1]))
            pages_out.extend(
                _join_pdf_line_fragments(sorted(parts, key=lambda p: p[0])) for _, _, parts in lines
            )
        return "\n".join(pages_out)
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não foi possível ler o PDF: {ex!s}",
        ) from ex


def _extract_itau_pdf_text(content: bytes) -> str:
    """Texto de fatura Itaú em ordem visual, com fallback para a extração linear."""
    text = _extract_pdf_text_columns(content)
    if len(text.strip()) < 20:
        return _extract_pdf_text(content)
    return text


def parse_pdf_br_lines(text: str, default_date: str | None) -> list[_Row]:
    """Heurística para PDFs com texto: data DD/MM/AAAA + descrição + valor no fim da linha."""
    out: list[_Row] = []
    money_tail = re.compile(
        r"(-?\s*(?:R\$\s*)?[\d]{1,3}(?:\.\d{3})*,\d{2}|-?\s*[\d]+,\d{2})\s*$",
        re.I,
    )
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if len(line) < 12:
            continue
        dm = re.search(r"(\d{2}/\d{2}/\d{4})", line)
        if not dm:
            continue
        data_iso = _parse_date_iso(dm.group(1))
        if not data_iso and default_date:
            data_iso = default_date
        if not data_iso:
            continue
        vm = money_tail.search(line)
        if not vm:
            continue
        val = _parse_brl_money(vm.group(1))
        if val is None or val == 0:
            continue
        desc_part = line[dm.end() : vm.start()].strip()
        desc = _clean_description(desc_part if len(desc_part) >= 2 else "Compra (PDF)")
        if not _is_purchase_description(desc):
            continue
        out.append(_Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01")))))
    return out


def _parse_date_ddmm_iso(s: str, year: int, reference_date: str | None = None) -> str | None:
    """
    Converte ``DD/MM`` usando ``year`` como base.

    Faturas trazem parcelas de compras antigas (ex.: ``09/10`` numa fatura de julho).
    Com ``reference_date``, datas muito à frente do fechamento recuam um ano.
    """
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})\s*$", s)
    if not m:
        return None
    d, mo = int(m.group(1)), int(m.group(2))
    if not (1 <= d <= 31 and 1 <= mo <= 12):
        return None
    if reference_date:
        from datetime import date, timedelta

        try:
            ref = date.fromisoformat(reference_date[:10])
            parsed = date(year, mo, d)
        except ValueError:
            return f"{year:04d}-{mo:02d}-{d:02d}"
        if parsed - ref > timedelta(days=45):
            return f"{year - 1:04d}-{mo:02d}-{d:02d}"
    return f"{year:04d}-{mo:02d}-{d:02d}"


_SANTANDER_SECTION_START_RE: Final[re.Pattern[str]] = re.compile(r"^(parcelamentos|despesas)\b", re.I)
_SANTANDER_SECTION_STOP_RE: Final[re.Pattern[str]] = re.compile(
    r"^(pagamento(?:s)?\s+e\s+demais\s+cr[eé]ditos|valor\s+total|encargos|saques|resumo)\b",
    re.I,
)


def parse_santander_pdf_text(text: str, default_date: str | None) -> list[_Row]:
    """
    Layout Santander: importa somente linhas das seções "Parcelamentos" e "Despesas".
    Ignora "Pagamento e Demais Créditos" e demais blocos da fatura.
    """
    year = _year_from_default(default_date)
    out: list[_Row] = []
    in_target_section = False
    row_re = re.compile(
        r"""
        ^(?:\d+\s+)?                                      # coluna "Compra" (índice), quando existir
        [^\dA-Za-zÀ-ÿ]*                                  # ícones/prefixos residuais
        (?P<data>\d{1,2}/\d{1,2})\s+
        (?P<desc>.+?)\s+
        (?:(?P<pa>\d{1,3})/(?P<pt>\d{1,3})\s+)?          # parcela opcional
        (?P<brl>(?:-?\s*R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:-?\s*R\$\s*)?\d+,\d{2})
        (?:\s+(?:-?\s*R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|\s+(?:-?\s*R\$\s*)?\d+,\d{2})?  # US$ opcional
        \s*$
        """,
        re.I | re.X,
    )
    # Variante: há texto após a parcela e antes do valor final.
    row_with_tail_after_parcela_re = re.compile(
        r"""
        ^(?P<data>\d{1,2}/\d{1,2})\s+
        (?P<desc_before>.+?)\s+
        (?P<pa>\d{1,3})/(?P<pt>\d{1,3})\s+
        (?P<desc_after>.+?)\s+
        (?P<brl>-?(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|-?(?:R\$\s*)?\d+,\d{2})
        \s*$
        """,
        re.I | re.X,
    )

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue

        low = line.lower()
        if _SANTANDER_SECTION_START_RE.match(low):
            in_target_section = True
            continue
        if _SANTANDER_SECTION_STOP_RE.match(low):
            in_target_section = False
            continue
        if not in_target_section:
            continue

        if re.match(r"^(compra|data|descri[cç][aã]o|parcela|r\$|us\$)\b", low):
            continue

        m = row_re.match(line)
        if not m:
            continue

        data_iso = _parse_date_ddmm_iso(m.group("data"), year, default_date)
        if not data_iso:
            continue
        desc = _clean_description(m.group("desc").strip())
        if not desc:
            continue

        pa_s = m.group("pa")
        pt_s = m.group("pt")
        if pa_s and pt_s:
            pa, pt = int(pa_s), int(pt_s)
            if pa >= 1 and pt >= 1 and pa <= pt:
                desc = f"{desc} ({pa}/{pt})"

        val = _parse_brl_money(m.group("brl"))
        if val is None or val == 0:
            continue
        if not _is_purchase_description(desc):
            continue
        out.append(_Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01")))))
    return out


# "(lan)?(ç)?amentos": um título que atravessa as duas colunas é fatiado pelo pypdf e a
# segunda coluna começa no meio da palavra.
_ITAU_AZUL_SECTION_START_RE: Final[re.Pattern[str]] = re.compile(
    r"^((lan)?[cç]?amentos:\s*(compras\s+e\s+saques|produtos\s+e\s+servi[cç]os)|"
    r"(lan)?[cç]?amentos\s+internacionais)\b",
    re.I,
)
_ITAU_AZUL_SECTION_STOP_RE: Final[re.Pattern[str]] = re.compile(
    r"^(total\s+dos\s+lan[cç]amentos\s+atuais|compras\s+parceladas\s*-\s*pr[oó]ximas\s+faturas|"
    r"limites?\s+(total\s+)?de\s+cr[eé]dito|encargos\s+cobrados)\b",
    re.I,
)

# Subtotais por cartão/bloco: não encerram a seção, o próximo titular vem logo abaixo.
_ITAU_SUBTOTAL_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(lan[cç]amentos\s+no\s+cart[aã]o|lan[cç]amentos\s+produtos\s+e\s+servi[cç]os|"
    r"total\s+(de\s+)?(transa[cç][oõ]es|lan[cç]amentos)\s+inter)\b",
    re.I,
)

# Coluna de categoria/cidade impressa sob cada lançamento ("ALIMENTAÇÃO .SAO PAULO").
# Sem re.I de propósito: o padrão só vale para o texto todo em caixa alta.
_ITAU_CATEGORY_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ0-9 &/'\-]*\s*\.",
)

# Cabeçalho de cada cartão dentro do bloco: "FULANO DE TAL(final 2222)".
_ITAU_CARD_OWNER_LINE_RE: Final[re.Pattern[str]] = re.compile(r"\(\s*final\s+\d{3,6}\s*\)\s*$", re.I)

# Cabeçalhos de tabela e rodapé de página.
_ITAU_NOISE_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^("
    r"data\s+(estabelecimento|produtos)|"
    r"titular\s+\d{3,6}\b|"
    r"d[oó]lar\s+de\s+convers[aã]o|"
    r"continua\.\.\.|"
    r"pc\s*-\s*\d|"
    r"\d{4}\s+\d{4}\s*$|"
    r"0800\s|"
    r"valor\s+em\s+r\$"
    r")",
    re.I,
)


# O repasse de IOF do bloco internacional é cobrado na fatura, mas não vem como lançamento datado.
_ITAU_IOF_REPASSE_RE: Final[re.Pattern[str]] = re.compile(
    r"^repasse\s+de\s+iof(\s+em)?\s+r\$\s*"
    r"(?P<brl>-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2})\s*$",
    re.I,
)


# Parcela colada no fim da descrição, sem espaço: "AGENCIA*100000000101/04".
_ITAU_ATTACHED_PARCELA_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<base>.*?\S)(?P<digits>\d+)/(?P<pt>\d{2,3})$",
)


def _split_itau_attached_parcela(desc: str) -> tuple[str, int | None, int | None]:
    """
    Separa a parcela colada no fim da descrição.

    O Itaú imprime a parcela com o mesmo número de dígitos do total ("01/04", "06/10"),
    o que desfaz a ambiguidade quando a descrição já termina em números.
    """
    m = _ITAU_ATTACHED_PARCELA_RE.match(desc.strip())
    if not m:
        return desc, None, None
    digits, pt_s = m.group("digits"), m.group("pt")
    width = len(pt_s)
    if len(digits) < width:
        return desc, None, None
    base = f"{m.group('base')}{digits[:-width]}".strip()
    pa, pt = int(digits[-width:]), int(pt_s)
    if not base or pt < 2 or pa < 1 or pa > pt:
        return desc, None, None
    return base, pa, pt


def _itau_desc_with_parcela(desc: str, pa_s: str | None, pt_s: str | None) -> str:
    """Anexa o sufixo "(atual/total)" à descrição, venha a parcela separada ou colada."""
    if pa_s and pt_s:
        pa, pt = int(pa_s), int(pt_s)
        return f"{desc} ({pa}/{pt})" if 1 <= pa <= pt else desc
    base, pa_att, pt_att = _split_itau_attached_parcela(desc)
    return f"{base} ({pa_att}/{pt_att})" if pa_att and pt_att else desc


def _itau_strip_orphan_prefix(line: str) -> str:
    """Remove glifo solto da diagramação no início da linha ("L Total dos lançamentos atuais")."""
    return re.sub(r"^\S\s+", "", line, count=1)


def _itau_section_match(pattern: re.Pattern[str], line: str) -> bool:
    return bool(pattern.match(line) or pattern.match(_itau_strip_orphan_prefix(line)))


def _is_itau_ignorable_line(line: str) -> bool:
    """Linhas que devem ser puladas sem fechar a seção nem colar na descrição anterior."""
    return bool(
        _ITAU_SUBTOTAL_LINE_RE.match(line)
        or _ITAU_CATEGORY_LINE_RE.match(line)
        or _ITAU_NOISE_LINE_RE.match(line)
        or _ITAU_CARD_OWNER_LINE_RE.search(line)
    )


def _itau_is_description_continuation(line: str) -> bool:
    """Continuação de descrição quebrada: só linhas curtas, sem cara de frase."""
    if len(line) > 30 or len(line.split()) > 4:
        return False
    return not re.search(r"[.,;:!?]", line)


_ITAU_INVOICE_TOTAL_RE: Final[re.Pattern[str]] = re.compile(
    r"^total\s+d(os|e)\s+lan[cç]amentos\s+atuais\s+"
    r"(?P<brl>-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2})\s*$",
    re.I,
)


def _fmt_brl(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def itau_total_mismatch_warning(text: str, rows: list[_Row]) -> str | None:
    """
    Compara a soma das linhas lidas com o "Total dos lançamentos atuais" impresso na fatura.

    Rede de proteção contra regressões silenciosas de layout, em que o parser deixa de
    enxergar um bloco inteiro e ninguém percebe até conferir a fatura na mão.
    """
    declared: Decimal | None = None
    for raw in text.splitlines():
        line = " ".join(raw.split())
        m = _ITAU_INVOICE_TOTAL_RE.match(line) or _ITAU_INVOICE_TOTAL_RE.match(
            _itau_strip_orphan_prefix(line)
        )
        if m:
            declared = _parse_brl_money(m.group("brl"))
            break
    if declared is None:
        return None
    parsed_total = sum((Decimal(r.valor) for r in rows), Decimal("0")).quantize(Decimal("0.01"))
    diff = parsed_total - declared
    if diff == 0:
        return None
    return (
        f"A soma das linhas lidas (R$ {_fmt_brl(parsed_total)}) não bate com o total da fatura "
        f"(R$ {_fmt_brl(declared)}); diferença de R$ {_fmt_brl(diff)}. Confira as linhas antes de importar."
    )


def parse_itau_azul_pdf_text(text: str, default_date: str | None) -> list[_Row]:
    """
    Layout Itaú Azul: importa apenas os blocos
    - "Lançamentos: compras e saques"
    - "Lançamentos: produtos e serviços"
    """
    year = _year_from_default(default_date)
    out: list[_Row] = []
    in_target_section = False
    current_desc: str | None = None
    pending_date_iso: str | None = None
    pending_desc: str | None = None

    # Data + descrição + (parcela opcional) + valor final
    row_re = re.compile(
        r"""
        ^(?P<data>\d{1,2}/\d{1,2})\s+
        (?P<desc>.+?)\s+
        (?:(?P<pa>\d{1,3})/(?P<pt>\d{1,3})\s+)?
        (?P<brl>(?:-\s*)?(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:-\s*)?(?:R\$\s*)?\d+,\d{2})
        \s*$
        """,
        re.I | re.X,
    )
    # Variante: há texto após a parcela e antes do valor final.
    row_with_tail_after_parcela_re = re.compile(
        r"""
        ^(?P<data>\d{1,2}/\d{1,2})\s+
        (?P<desc_before>.+?)\s+
        (?P<pa>\d{1,3})/(?P<pt>\d{1,3})\s+
        (?P<desc_after>.+?)\s+
        (?P<brl>(?:-\s*)?(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:-\s*)?(?:R\$\s*)?\d+,\d{2})
        \s*$
        """,
        re.I | re.X,
    )
    # Continuação de linha: pode conter parcela+valor, ou apenas valor.
    cont_re = re.compile(
        r"""
        ^(?:(?P<pa>\d{1,3})/(?P<pt>\d{1,3})\s+)?
        (?P<brl>(?:-\s*)?(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:-\s*)?(?:R\$\s*)?\d+,\d{2})
        \s*$
        """,
        re.I | re.X,
    )
    # Continuação com texto após parcela: ex. "05/06 RETAIL SAO PAULO 185,06".
    cont_with_tail_after_parcela_re = re.compile(
        r"""
        ^(?P<pa>\d{1,3})/(?P<pt>\d{1,3})\s+
        (?P<desc_after>.+?)\s+
        (?P<brl>(?:-\s*)?(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:-\s*)?(?:R\$\s*)?\d+,\d{2})
        \s*$
        """,
        re.I | re.X,
    )
    # Linha com data+descrição sem valor (valor/parcela vêm na próxima linha).
    date_desc_only_re = re.compile(r"^(?P<data>\d{1,2}/\d{1,2})\s+(?P<desc>.+?)\s*$", re.I)
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        low = line.lower()

        if _itau_section_match(_ITAU_AZUL_SECTION_START_RE, low):
            in_target_section = True
            current_desc = None
            pending_date_iso = None
            pending_desc = None
            continue
        if _itau_section_match(_ITAU_AZUL_SECTION_STOP_RE, low):
            in_target_section = False
            current_desc = None
            pending_date_iso = None
            pending_desc = None
            continue
        if not in_target_section:
            continue

        # Cabeçalhos dentro dos blocos.
        if re.match(r"^(data|estabelecimento|produtos\/servi[cç]os|valor\s+em\s+r\$)\b", low):
            continue

        # Repasse de IOF do bloco internacional é cobrado na fatura e entra como lançamento.
        m_iof = _ITAU_IOF_REPASSE_RE.match(line)
        if m_iof:
            val_iof = _parse_brl_money(m_iof.group("brl"))
            if val_iof is not None and val_iof != 0:
                out.append(
                    _Row(
                        data=default_date or f"{year:04d}-01-01",
                        descricao="Repasse de IOF",
                        valor=str(val_iof.quantize(Decimal("0.01"))),
                    )
                )
            current_desc = None
            pending_date_iso = None
            pending_desc = None
            continue

        # Subtotais por cartão, coluna de categoria e rodapé de página não são lançamentos.
        if _is_itau_ignorable_line(line):
            continue

        m_tail = row_with_tail_after_parcela_re.match(line)
        if m_tail:
            data_iso = _parse_date_ddmm_iso(m_tail.group("data"), year, default_date)
            if not data_iso:
                current_desc = None
                pending_date_iso = None
                pending_desc = None
                continue
            desc_before = _clean_description(m_tail.group("desc_before").strip())
            desc_after = _clean_description(m_tail.group("desc_after").strip())
            if not desc_before:
                current_desc = None
                pending_date_iso = None
                pending_desc = None
                continue
            pa, pt = int(m_tail.group("pa")), int(m_tail.group("pt"))
            desc = _clean_description(f"{desc_before} {desc_after}".strip()) if desc_after else desc_before
            parcela_suffix = ""
            if pa >= 1 and pt >= 1 and pa <= pt:
                parcela_suffix = f" ({pa}/{pt})"
            desc = f"{desc}{parcela_suffix}".strip()
            val = _parse_brl_money(m_tail.group("brl"))
            if val is None or val == 0 or not _is_purchase_description(desc):
                current_desc = None
                pending_date_iso = None
                pending_desc = None
                continue
            out.append(_Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01")))))
            current_desc = desc
            pending_date_iso = None
            pending_desc = None
            continue

        m = row_re.match(line)
        if m:
            data_iso = _parse_date_ddmm_iso(m.group("data"), year, default_date)
            if not data_iso:
                current_desc = None
                continue
            desc = _clean_description(m.group("desc").strip())
            if not desc:
                current_desc = None
                continue
            desc = _itau_desc_with_parcela(desc, m.group("pa"), m.group("pt"))
            val = _parse_brl_money(m.group("brl"))
            if val is None or val == 0:
                current_desc = None
                pending_date_iso = None
                pending_desc = None
                continue
            if not _is_purchase_description(desc):
                current_desc = None
                pending_date_iso = None
                pending_desc = None
                continue
            out.append(_Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01")))))
            current_desc = desc
            pending_date_iso = None
            pending_desc = None
            continue

        # Caso de quebra: "DD/MM descricao" em uma linha e "PP/TT valor" (ou só valor) na próxima.
        m_date_desc = date_desc_only_re.match(line)
        if m_date_desc:
            data_iso = _parse_date_ddmm_iso(m_date_desc.group("data"), year, default_date)
            desc = _clean_description(m_date_desc.group("desc").strip())
            if data_iso and desc:
                pending_date_iso = data_iso
                pending_desc = desc
            else:
                pending_date_iso = None
                pending_desc = None
            continue

        if pending_date_iso and pending_desc:
            m_cont_tail = cont_with_tail_after_parcela_re.match(line)
            if m_cont_tail:
                pa, pt = int(m_cont_tail.group("pa")), int(m_cont_tail.group("pt"))
                desc = pending_desc
                desc_after = _clean_description(m_cont_tail.group("desc_after").strip())
                if desc_after:
                    desc = _clean_description(f"{desc} {desc_after}")
                if pa >= 1 and pt >= 1 and pa <= pt:
                    desc = f"{desc} ({pa}/{pt})"
                val = _parse_brl_money(m_cont_tail.group("brl"))
                if val is not None and val != 0 and _is_purchase_description(desc):
                    out.append(
                        _Row(
                            data=pending_date_iso,
                            descricao=desc[:500],
                            valor=str(val.quantize(Decimal("0.01"))),
                        )
                    )
                    current_desc = desc
                pending_date_iso = None
                pending_desc = None
                continue

            m_cont = cont_re.match(line)
            if m_cont:
                desc = pending_desc
                pa_s = m_cont.group("pa")
                pt_s = m_cont.group("pt")
                if pa_s and pt_s:
                    pa, pt = int(pa_s), int(pt_s)
                    if pa >= 1 and pt >= 1 and pa <= pt:
                        desc = f"{desc} ({pa}/{pt})"
                val = _parse_brl_money(m_cont.group("brl"))
                if val is not None and val != 0 and _is_purchase_description(desc):
                    out.append(
                        _Row(
                            data=pending_date_iso,
                            descricao=desc[:500],
                            valor=str(val.quantize(Decimal("0.01"))),
                        )
                    )
                    current_desc = desc
                pending_date_iso = None
                pending_desc = None
                continue

        # Algumas descrições quebram na linha seguinte (sem valor/data).
        if current_desc and _itau_is_description_continuation(line) and not re.search(r"\d+,\d{2}", line):
            idx = len(out) - 1
            prev_desc = out[idx].descricao
            parcela_suffix_match = _BARE_PARCELAS_PARENS_RE.search(prev_desc)
            if parcela_suffix_match:
                pa, pt = parcela_suffix_match.group(1), parcela_suffix_match.group(2)
                base_desc = _BARE_PARCELAS_PARENS_RE.sub("", prev_desc).strip()
                merged_base = _clean_description(f"{base_desc} {line}".strip())
                merged = f"{merged_base} ({pa}/{pt})".strip()[:500]
            else:
                merged = _clean_description(f"{prev_desc} {line}".strip())[:500]
            out[idx] = _Row(data=out[idx].data, descricao=merged, valor=out[idx].valor)
            continue

        current_desc = None
        pending_date_iso = None
        pending_desc = None

    return out


_ITAU_PDA_SECTION_START_RE: Final[re.Pattern[str]] = re.compile(
    r"^((lan)?[cç]?amentos:\s*(compras\s+e\s+saques|produtos\s+e\s+servi[cç]os)|"
    r"(lan)?[cç]?amentos\s+internacionais|outros\s+lan[cç]amentos)\b",
    re.I,
)
_ITAU_PDA_SECTION_STOP_RE: Final[re.Pattern[str]] = re.compile(
    r"^(total\s+de\s+outros\s+lan[cç]amentos|total\s+dos\s+lan[cç]amentos\s+atuais|"
    r"compras\s+parceladas\s*-\s*pr[oó]ximas\s+faturas|limites?\s+(total\s+)?de\s+cr[eé]dito|"
    r"encargos\s+cobrados)\b",
    re.I,
)


def parse_itau_pda_pdf_text(text: str, default_date: str | None) -> list[_Row]:
    """
    Layout Itaú PDA: mesmo critério do Itaú Azul, incluindo também o bloco
    "Outros lançamentos" quando presente na fatura.
    """
    year = _year_from_default(default_date)
    out: list[_Row] = []
    in_target_section = False
    current_desc: str | None = None
    pending_date_iso: str | None = None
    pending_desc: str | None = None

    def normalize_desc_and_sign(desc_in: str, val_in: Decimal) -> tuple[str, Decimal]:
        d = desc_in.strip()
        v = val_in
        if d.endswith("-"):
            d = d[:-1].strip()
            v = -abs(v)
        # Estornos/descontos são créditos da fatura (devem reduzir o total).
        if re.search(r"\b(estorno|desconto)\b", d, re.I):
            v = -abs(v)
        return d, v

    row_re = re.compile(
        r"""
        ^(?P<data>\d{1,2}/\d{1,2})\s+
        (?P<desc>.+?)\s+
        (?:(?P<pa>\d{1,3})/(?P<pt>\d{1,3})\s+)?
        (?P<brl>-?(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|-?(?:R\$\s*)?\d+,\d{2})
        \s*$
        """,
        re.I | re.X,
    )
    row_with_tail_after_parcela_re = re.compile(
        r"""
        ^(?P<data>\d{1,2}/\d{1,2})\s+
        (?P<desc_before>.+?)\s+
        (?P<pa>\d{1,3})/(?P<pt>\d{1,3})\s+
        (?P<desc_after>.+?)\s+
        (?P<brl>-?(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|-?(?:R\$\s*)?\d+,\d{2})
        \s*$
        """,
        re.I | re.X,
    )
    cont_re = re.compile(
        r"""
        ^(?:(?P<pa>\d{1,3})/(?P<pt>\d{1,3})\s+)?
        (?P<brl>-?(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|-?(?:R\$\s*)?\d+,\d{2})
        \s*$
        """,
        re.I | re.X,
    )
    cont_with_tail_after_parcela_re = re.compile(
        r"""
        ^(?P<pa>\d{1,3})/(?P<pt>\d{1,3})\s+
        (?P<desc_after>.+?)\s+
        (?P<brl>-?(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|-?(?:R\$\s*)?\d+,\d{2})
        \s*$
        """,
        re.I | re.X,
    )
    date_desc_only_re = re.compile(r"^(?P<data>\d{1,2}/\d{1,2})\s+(?P<desc>.+?)\s*$", re.I)
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        low = line.lower()

        if _itau_section_match(_ITAU_PDA_SECTION_START_RE, low):
            in_target_section = True
            current_desc = None
            pending_date_iso = None
            pending_desc = None
            continue
        if _itau_section_match(_ITAU_PDA_SECTION_STOP_RE, low):
            in_target_section = False
            current_desc = None
            pending_date_iso = None
            pending_desc = None
            continue
        if not in_target_section:
            continue

        if re.match(
            r"^(data|estabelecimento|produtos\/servi[cç]os|descri[cç][aã]o|valor\s+em\s+r\$|protocolo\/\s*motivo|situa[cç][aã]o)\b",
            low,
        ):
            continue

        # Repasse de IOF do bloco internacional é cobrado na fatura e entra como lançamento.
        m_iof = _ITAU_IOF_REPASSE_RE.match(line)
        if m_iof:
            val_iof = _parse_brl_money(m_iof.group("brl"))
            if val_iof is not None and val_iof != 0:
                out.append(
                    _Row(
                        data=default_date or f"{year:04d}-01-01",
                        descricao="Repasse de IOF",
                        valor=str(val_iof.quantize(Decimal("0.01"))),
                    )
                )
            current_desc = None
            pending_date_iso = None
            pending_desc = None
            continue

        # Subtotais por cartão, coluna de categoria e rodapé de página não são lançamentos.
        if _is_itau_ignorable_line(line):
            continue

        m_tail = row_with_tail_after_parcela_re.match(line)
        if m_tail:
            data_iso = _parse_date_ddmm_iso(m_tail.group("data"), year, default_date)
            if not data_iso:
                current_desc = None
                pending_date_iso = None
                pending_desc = None
                continue
            raw_desc_before = m_tail.group("desc_before").strip()
            raw_desc_after = m_tail.group("desc_after").strip()
            had_dash_sign = raw_desc_before.endswith("-") or raw_desc_after.endswith("-")
            desc_before = _clean_description(raw_desc_before)
            desc_after = _clean_description(raw_desc_after)
            if not desc_before:
                current_desc = None
                pending_date_iso = None
                pending_desc = None
                continue
            pa, pt = int(m_tail.group("pa")), int(m_tail.group("pt"))
            desc = _clean_description(f"{desc_before} {desc_after}".strip()) if desc_after else desc_before
            if pa >= 1 and pt >= 1 and pa <= pt:
                desc = f"{desc} ({pa}/{pt})"
            val = _parse_brl_money(m_tail.group("brl"))
            if val is None or val == 0 or not _is_purchase_description(desc):
                current_desc = None
                pending_date_iso = None
                pending_desc = None
                continue
            if had_dash_sign:
                val = -abs(val)
            desc, val = normalize_desc_and_sign(desc, val)
            out.append(_Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01")))))
            current_desc = desc
            pending_date_iso = None
            pending_desc = None
            continue

        m = row_re.match(line)
        if m:
            data_iso = _parse_date_ddmm_iso(m.group("data"), year, default_date)
            if not data_iso:
                current_desc = None
                continue
            raw_desc = m.group("desc").strip()
            had_dash_sign = raw_desc.endswith("-")
            desc = _clean_description(raw_desc)
            if not desc:
                current_desc = None
                continue
            desc = _itau_desc_with_parcela(desc, m.group("pa"), m.group("pt"))
            val = _parse_brl_money(m.group("brl"))
            if val is None or val == 0:
                current_desc = None
                pending_date_iso = None
                pending_desc = None
                continue
            if not _is_purchase_description(desc):
                current_desc = None
                pending_date_iso = None
                pending_desc = None
                continue
            if had_dash_sign:
                val = -abs(val)
            desc, val = normalize_desc_and_sign(desc, val)
            out.append(_Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01")))))
            current_desc = desc
            pending_date_iso = None
            pending_desc = None
            continue

        m_date_desc = date_desc_only_re.match(line)
        if m_date_desc:
            data_iso = _parse_date_ddmm_iso(m_date_desc.group("data"), year, default_date)
            desc = _clean_description(m_date_desc.group("desc").strip())
            if data_iso and desc:
                pending_date_iso = data_iso
                pending_desc = desc
            else:
                pending_date_iso = None
                pending_desc = None
            continue

        if pending_date_iso and pending_desc:
            m_cont_tail = cont_with_tail_after_parcela_re.match(line)
            if m_cont_tail:
                pa, pt = int(m_cont_tail.group("pa")), int(m_cont_tail.group("pt"))
                desc = pending_desc
                raw_desc_after = m_cont_tail.group("desc_after").strip()
                had_dash_sign = raw_desc_after.endswith("-")
                desc_after = _clean_description(raw_desc_after)
                if desc_after:
                    desc = _clean_description(f"{desc} {desc_after}")
                if pa >= 1 and pt >= 1 and pa <= pt:
                    desc = f"{desc} ({pa}/{pt})"
                val = _parse_brl_money(m_cont_tail.group("brl"))
                if val is not None and val != 0 and _is_purchase_description(desc):
                    if had_dash_sign:
                        val = -abs(val)
                    desc, val = normalize_desc_and_sign(desc, val)
                    out.append(
                        _Row(
                            data=pending_date_iso,
                            descricao=desc[:500],
                            valor=str(val.quantize(Decimal("0.01"))),
                        )
                    )
                    current_desc = desc
                pending_date_iso = None
                pending_desc = None
                continue

            m_cont = cont_re.match(line)
            if m_cont:
                desc = pending_desc
                pa_s = m_cont.group("pa")
                pt_s = m_cont.group("pt")
                if pa_s and pt_s:
                    pa, pt = int(pa_s), int(pt_s)
                    if pa >= 1 and pt >= 1 and pa <= pt:
                        desc = f"{desc} ({pa}/{pt})"
                val = _parse_brl_money(m_cont.group("brl"))
                if val is not None and val != 0 and _is_purchase_description(desc):
                    desc, val = normalize_desc_and_sign(desc, val)
                    out.append(
                        _Row(
                            data=pending_date_iso,
                            descricao=desc[:500],
                            valor=str(val.quantize(Decimal("0.01"))),
                        )
                    )
                    current_desc = desc
                pending_date_iso = None
                pending_desc = None
                continue

        if current_desc and _itau_is_description_continuation(line) and not re.search(r"\d+,\d{2}", line):
            idx = len(out) - 1
            prev_desc = out[idx].descricao
            parcela_suffix_match = _BARE_PARCELAS_PARENS_RE.search(prev_desc)
            if parcela_suffix_match:
                pa, pt = parcela_suffix_match.group(1), parcela_suffix_match.group(2)
                base_desc = _BARE_PARCELAS_PARENS_RE.sub("", prev_desc).strip()
                merged_base = _clean_description(f"{base_desc} {line}".strip())
                merged = f"{merged_base} ({pa}/{pt})".strip()[:500]
            else:
                merged = _clean_description(f"{prev_desc} {line}".strip())[:500]
            out[idx] = _Row(data=out[idx].data, descricao=merged, valor=out[idx].valor)
            continue

        current_desc = None
        pending_date_iso = None
        pending_desc = None

    def drop_next_invoice_duplicates(rows_in: list[_Row]) -> list[_Row]:
        """Remove linhas de próximas faturas quando a mesma compra aparece com parcela atual e próxima."""
        best_pa: dict[tuple[str, str, str, int], int] = {}
        for r in rows_in:
            base, pa, pt = extract_parcela_from_description(r.descricao)
            if not (pa and pt and pt > 1):
                continue
            key = (r.data, base.strip().lower(), str(Decimal(r.valor).copy_abs().quantize(Decimal("0.01"))), pt)
            prev = best_pa.get(key)
            if prev is None or pa < prev:
                best_pa[key] = pa

        out_rows: list[_Row] = []
        for r in rows_in:
            base, pa, pt = extract_parcela_from_description(r.descricao)
            if not (pa and pt and pt > 1):
                out_rows.append(r)
                continue
            key = (r.data, base.strip().lower(), str(Decimal(r.valor).copy_abs().quantize(Decimal("0.01"))), pt)
            if best_pa.get(key) == pa:
                out_rows.append(r)
        return out_rows

    def parse_encargos_section(rows_in: list[_Row]) -> list[_Row]:
        """Inclui lançamentos do bloco 'Encargos cobrados nesta fatura' (ex.: IOF de financiamento)."""
        dflt = default_date or f"{year:04d}-01-01"
        in_encargos = False
        out_rows = list(rows_in)
        seen_keys = {(r.data, r.descricao.strip().lower(), str(Decimal(r.valor).quantize(Decimal("0.01")))) for r in out_rows}

        # Ex.: "IOF de financiamento (0,38 % + 0,00820 % a.d.) 8,87"
        enc_row_re = re.compile(
            r"^(?P<desc>.+?)\s+(?P<val>(?:-\s*)?(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:-\s*)?(?:R\$\s*)?\d+,\d{2})\s*$",
            re.I,
        )
        for raw in text.splitlines():
            line = " ".join(raw.split())
            if not line:
                continue
            low = line.lower()
            # Em alguns PDFs PDA a extração embaralha a ordem; garantimos captura global do IOF.
            if "iof de financiamento" in low:
                m_i = enc_row_re.match(line)
                if m_i:
                    desc_i = _clean_description(m_i.group("desc"))
                    val_i = _parse_brl_money(m_i.group("val"))
                    if desc_i and val_i is not None and val_i != 0:
                        key_i = (dflt, desc_i.strip().lower(), str(val_i.quantize(Decimal("0.01"))))
                        if key_i not in seen_keys:
                            seen_keys.add(key_i)
                            out_rows.append(
                                _Row(data=dflt, descricao=desc_i[:500], valor=str(val_i.quantize(Decimal("0.01"))))
                            )
                continue
            if re.match(r"^encargos\s+cobrados\s+nesta\s+fatura\b", low):
                in_encargos = True
                continue
            if in_encargos and re.match(
                r"^(fique\s+atento|novo\s+teto|simula[cç][aã]o|demais\s+taxas|consulte|total\s+de\s+encargos|juros\s+m[aá]ximos)\b",
                low,
            ):
                in_encargos = False
            if not in_encargos:
                continue
            if re.match(r"^(total\s+de\s+encargos|valor\s+em\s+r\$)\b", low):
                continue
            m = enc_row_re.match(line)
            if not m:
                continue
            desc = _clean_description(m.group("desc"))
            if not desc:
                continue
            val = _parse_brl_money(m.group("val"))
            if val is None or val == 0:
                continue
            key = (dflt, desc.strip().lower(), str(val.quantize(Decimal("0.01"))))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            out_rows.append(_Row(data=dflt, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01")))))
        return out_rows

    if out:
        return parse_encargos_section(drop_next_invoice_duplicates(out))

    # Fallback para PDFs em que a extração do texto perde a ordem dos blocos.
    # Nesse caso, tentamos capturar linhas de lançamento no documento inteiro.
    current_desc = None
    pending_date_iso = None
    pending_desc = None
    fallback_out: list[_Row] = []
    in_forbidden_future_installments = False

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        low = line.lower()
        if re.match(r"^compras\s+parceladas\s*-\s*pr[oó]ximas\s+faturas\b", low):
            in_forbidden_future_installments = True
            current_desc = None
            pending_date_iso = None
            pending_desc = None
            continue
        if in_forbidden_future_installments and re.match(
            r"^(limites?\s+de\s+cr[eé]dito|encargos|fique\s+atento|novo\s+teto|simula[cç][aã]o|"
            r"demais\s+taxas|total\s+para\s+pr[oó]ximas\s+faturas|lancamentos?:|outros\s+lan[cç]amentos)\b",
            low,
        ):
            in_forbidden_future_installments = False
        if in_forbidden_future_installments:
            continue
        if re.match(
            r"^(data|estabelecimento|produtos\/servi[cç]os|descri[cç][aã]o|valor\s+em\s+r\$|"
            r"lan[cç]amentos|resumo|limites?|encargos|protocolo|situa[cç][aã]o)\b",
            low,
        ):
            continue

        m_tail = row_with_tail_after_parcela_re.match(line)
        if m_tail:
            data_iso = _parse_date_ddmm_iso(m_tail.group("data"), year, default_date)
            raw_desc_before = m_tail.group("desc_before").strip()
            raw_desc_after = m_tail.group("desc_after").strip()
            had_dash_sign = raw_desc_before.endswith("-") or raw_desc_after.endswith("-")
            desc_before = _clean_description(raw_desc_before)
            desc_after = _clean_description(raw_desc_after)
            if not data_iso or not desc_before:
                continue
            pa, pt = int(m_tail.group("pa")), int(m_tail.group("pt"))
            desc = _clean_description(f"{desc_before} {desc_after}".strip()) if desc_after else desc_before
            if pa >= 1 and pt >= 1 and pa <= pt:
                desc = f"{desc} ({pa}/{pt})"
            val = _parse_brl_money(m_tail.group("brl"))
            if val is None or val == 0 or not _is_purchase_description(desc):
                continue
            if had_dash_sign:
                val = -abs(val)
            desc, val = normalize_desc_and_sign(desc, val)
            fallback_out.append(_Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01")))))
            current_desc = desc
            pending_date_iso = None
            pending_desc = None
            continue

        m = row_re.match(line)
        if m:
            data_iso = _parse_date_ddmm_iso(m.group("data"), year, default_date)
            raw_desc = m.group("desc").strip()
            had_dash_sign = raw_desc.endswith("-")
            desc = _clean_description(raw_desc)
            if not data_iso or not desc:
                continue
            desc = _itau_desc_with_parcela(desc, m.group("pa"), m.group("pt"))
            val = _parse_brl_money(m.group("brl"))
            if val is None or val == 0 or not _is_purchase_description(desc):
                continue
            if had_dash_sign:
                val = -abs(val)
            desc, val = normalize_desc_and_sign(desc, val)
            fallback_out.append(_Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01")))))
            current_desc = desc
            pending_date_iso = None
            pending_desc = None
            continue

        m_date_desc = date_desc_only_re.match(line)
        if m_date_desc:
            data_iso = _parse_date_ddmm_iso(m_date_desc.group("data"), year, default_date)
            desc = _clean_description(m_date_desc.group("desc").strip())
            if data_iso and desc:
                pending_date_iso = data_iso
                pending_desc = desc
            else:
                pending_date_iso = None
                pending_desc = None
            continue

        if pending_date_iso and pending_desc:
            m_cont_tail = cont_with_tail_after_parcela_re.match(line)
            if m_cont_tail:
                pa, pt = int(m_cont_tail.group("pa")), int(m_cont_tail.group("pt"))
                desc = pending_desc
                raw_desc_after = m_cont_tail.group("desc_after").strip()
                had_dash_sign = raw_desc_after.endswith("-")
                desc_after = _clean_description(raw_desc_after)
                if desc_after:
                    desc = _clean_description(f"{desc} {desc_after}")
                if pa >= 1 and pt >= 1 and pa <= pt:
                    desc = f"{desc} ({pa}/{pt})"
                val = _parse_brl_money(m_cont_tail.group("brl"))
                if val is not None and val != 0 and _is_purchase_description(desc):
                    if had_dash_sign:
                        val = -abs(val)
                    desc, val = normalize_desc_and_sign(desc, val)
                    fallback_out.append(
                        _Row(data=pending_date_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01"))))
                    )
                    current_desc = desc
                pending_date_iso = None
                pending_desc = None
                continue

            m_cont = cont_re.match(line)
            if m_cont:
                desc = pending_desc
                pa_s = m_cont.group("pa")
                pt_s = m_cont.group("pt")
                if pa_s and pt_s:
                    pa, pt = int(pa_s), int(pt_s)
                    if pa >= 1 and pt >= 1 and pa <= pt:
                        desc = f"{desc} ({pa}/{pt})"
                val = _parse_brl_money(m_cont.group("brl"))
                if val is not None and val != 0 and _is_purchase_description(desc):
                    desc, val = normalize_desc_and_sign(desc, val)
                    fallback_out.append(
                        _Row(data=pending_date_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01"))))
                    )
                    current_desc = desc
                pending_date_iso = None
                pending_desc = None
                continue

        # No fallback evitamos concatenar linhas sem valor para não "colar" blocos inteiros
        # quando a extração do PDF vem fora de ordem.

    return parse_encargos_section(drop_next_invoice_duplicates(fallback_out))


_MONTH_PT: Final[dict[str, int]] = {
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}

# Valor em real: vírgula decimal ou R$ + até 5 dígitos (evita ano 2025 como valor)
_MONEY_IN_TEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:[-−–—]?\s*R\$\s*)(?:\d{1,3}(?:\.\d{3})*,\d{2}|\d{1,5}(?:,\d{2})?)\b"
    r"|(?:[-−–—]?\s*\d{1,3}(?:\.\d{3})*,\d{2}|[-−–—]?\s*\d{1,6},\d{2})\b",
    re.I,
)


def _year_from_default(default_date: str | None) -> int:
    from datetime import date

    if default_date and len(default_date) >= 4 and default_date[:4].isdigit():
        return int(default_date[:4])
    return date.today().year


_MON_ALT: Final[str] = "|".join(_MONTH_PT)

_NUBANK_MONTH_WORDS: Final[tuple[tuple[str, str], ...]] = (
    ("janeiro", "jan"),
    ("fevereiro", "fev"),
    ("março", "mar"),
    ("marco", "mar"),
    ("abril", "abr"),
    ("maio", "mai"),
    ("junho", "jun"),
    ("julho", "jul"),
    ("agosto", "ago"),
    ("setembro", "set"),
    ("outubro", "out"),
    ("novembro", "nov"),
    ("dezembro", "dez"),
)


def _normalize_nubank_month_words(text: str) -> str:
    t = text
    for full, abbr in _NUBANK_MONTH_WORDS:
        t = re.sub(re.escape(full), abbr, t, flags=re.I)
    return t


def _parse_nubank_pdf_one_line(line: str, default_year: int) -> _Row | None:
    """Uma linha: '8 abr Estabelecimento R$ 10,00' ou valor antes da data no fim."""
    line = " ".join(line.split())
    mon = _MON_ALT
    pref = re.compile(
        rf"^(\d{{1,2}})\s*({mon})\b\s*(.+?)\s+((?:[-−–—]?\s*R\$\s*)?(?:\d{{1,3}}(?:\.\d{{3}})*,\d{{2}}|\d+,\d{{2}}))\s*$",
        re.I,
    )
    m = pref.match(line)
    if m:
        day_s, mon_s, desc, vs = m.group(1), m.group(2).lower()[:3], _clean_description(m.group(3).strip()), m.group(4)
        mo = _MONTH_PT.get(mon_s)
        if mo is None:
            return None
        val = _parse_brl_money(vs)
        if val is None or val == 0 or len(desc) < 2:
            return None
        if not _is_nubank_statement_item(desc):
            return None
        try:
            from datetime import date as dt_date

            dt_date(default_year, mo, int(day_s))
        except ValueError:
            return None
        data_iso = f"{default_year}-{mo:02d}-{int(day_s):02d}"
        return _Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01"))))

    # Descrição + valor + data no fim (layout comum em extratos)
    suff = re.compile(
        rf"^(.+?)\s+((?:[-−–—]?\s*R\$\s*)?(?:\d{{1,3}}(?:\.\d{{3}})*,\d{{2}}|\d+,\d{{2}}))\s+(\d{{1,2}})\s*({mon})\b\s*$",
        re.I,
    )
    m2 = suff.match(line)
    if m2:
        desc, vs, day_s, mon_s = (
            _clean_description(m2.group(1).strip()),
            m2.group(2),
            m2.group(3),
            m2.group(4).lower()[:3],
        )
        mo = _MONTH_PT.get(mon_s)
        if mo is None:
            return None
        val = _parse_brl_money(vs)
        if val is None or val == 0 or len(desc) < 2:
            return None
        if not _is_nubank_statement_item(desc):
            return None
        try:
            from datetime import date as dt_date

            dt_date(default_year, mo, int(day_s))
        except ValueError:
            return None
        data_iso = f"{default_year}-{mo:02d}-{int(day_s):02d}"
        return _Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01"))))
    return None


def _row_semantic_key(r: _Row) -> tuple[str, str, str, int, int]:
    """Chave entre heurísticas de PDF sem perder compras à vista distintas no mesmo lugar/valor.

    - Com parcelamento (total > 1): data, valor, nome sem sufixo de parcela, pa, pt.
    - À vista / 1x: data, valor e descrição completa normalizada (duas compras iguais no valor não colapsam).
    """
    base, pa, pt = extract_parcela_from_description(r.descricao)
    v = str(Decimal(r.valor).quantize(Decimal("0.01")))
    pa_n = pa or 0
    pt_n = pt or 0
    if pt_n > 1 and pa_n >= 1:
        base_norm = " ".join(base.strip().lower().split())
        return (r.data, v, base_norm, pa_n, pt_n)
    full_norm = " ".join(_clean_description(r.descricao).lower().split())
    return (r.data, v, full_norm, 0, 0)


def _concat_rows_merge_parsers(*lists: list[_Row]) -> list[_Row]:
    """Une heurísticas do mesmo PDF: elimina a mesma compra extraída 2+ vezes com texto ligeiramente diferente.

    Preserva repetições reais no mesmo dia/valor/descrição (ex.: NuTag), removendo apenas os excedentes
    que aparecem quando múltiplas heurísticas capturam a mesma linha do PDF.
    Não aplica filtro de datas da fatura nem colapsa linha sem parcela (isso removia lançamentos válidos).
    """
    if not lists:
        return []

    max_occurrences: Counter[tuple[str, str, str, int, int]] = Counter()
    for lst in lists:
        if not lst:
            continue
        current = Counter(_row_semantic_key(r) for r in lst)
        for key, count in current.items():
            if count > max_occurrences[key]:
                max_occurrences[key] = count

    used: Counter[tuple[str, str, str, int, int]] = Counter()
    out: list[_Row] = []
    for lst in lists:
        for r in lst:
            k = _row_semantic_key(r)
            if used[k] >= max_occurrences[k]:
                continue
            used[k] += 1
            out.append(r)
    return out


def _nubank_row_from_chunk(
    chunk: str,
    day_s: str,
    mon_abbr: str,
    year: int,
    *,
    allow_empty_desc: bool,
) -> _Row | None:
    mo = _MONTH_PT.get(mon_abbr)
    if mo is None:
        return None
    money_hits = list(_MONEY_IN_TEXT_RE.finditer(chunk))
    if not money_hits:
        return None
    # Em PDF Nubank, um bloco pode conter valor estrangeiro/conversão + valor em BRL.
    # Priorizamos o último valor com cara de BRL (vírgula decimal ou prefixo R$).
    brl_hits = [h for h in money_hits if "," in h.group(0) or "R$" in h.group(0).upper()]
    mm = brl_hits[-1] if brl_hits else money_hits[-1]
    val = _parse_brl_money(mm.group(0))
    if val is None or val == 0:
        return None
    desc = chunk[: mm.start()].strip()
    desc = re.sub(r"\s*R\$\s*$", "", desc, flags=re.I).strip()
    desc = re.sub(r"\s+R\$\s*\d[\d\.,]*\s*$", "", desc, flags=re.I).strip()
    desc = _clean_description(" ".join(desc.split()))
    if "R$" in desc.upper():
        return None
    if not desc:
        if not allow_empty_desc:
            return None
        desc = "Compra (PDF Nubank)"
    if len(desc) > 320:
        return None
    if not _is_nubank_statement_item(desc):
        return None
    try:
        from datetime import date as dt_date

        dnum = int(day_s)
        dt_date(year, mo, dnum)
    except ValueError:
        return None
    data_iso = f"{year}-{mo:02d}-{dnum:02d}"
    return _Row(data=data_iso, descricao=desc[:500], valor=str(val.quantize(Decimal("0.01"))))


def _nubank_pdf_rows_date_then_desc(text_1: str, year: int) -> list[_Row]:
    """Layout: '8 abr DESC R$ 10' — data abre o lançamento."""
    date_pat = re.compile(rf"(\d{{1,2}})\s*({_MON_ALT})\b", re.I)
    matches = list(date_pat.finditer(text_1))
    out: list[_Row] = []
    for i, m in enumerate(matches):
        day_s, mon_s = m.group(1), m.group(2).lower()[:3]
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text_1)
        chunk = text_1[start:end].strip()
        if not chunk:
            continue
        row = _nubank_row_from_chunk(chunk, day_s, mon_s, year, allow_empty_desc=False)
        if row:
            out.append(row)
    return out


def _nubank_pdf_rows_desc_then_date(text_1: str, year: int) -> list[_Row]:
    """Layout: 'DESC R$ 10 8 abr' — data fecha o lançamento (comum em PDF da Nubank)."""
    date_pat = re.compile(rf"(\d{{1,2}})\s*({_MON_ALT})\b", re.I)
    matches = list(date_pat.finditer(text_1))
    out: list[_Row] = []
    prev = 0
    for m in matches:
        chunk = text_1[prev : m.start()].strip()
        prev = m.end()
        day_s, mon_s = m.group(1), m.group(2).lower()[:3]
        if not chunk:
            continue
        row = _nubank_row_from_chunk(chunk, day_s, mon_s, year, allow_empty_desc=False)
        if row:
            out.append(row)
    return out


def _nubank_pdf_rows_multiline_lines(raw_text: str, year: int) -> list[_Row]:
    """
    Captura lançamentos Nubank que quebram em múltiplas linhas:
    ex.: linha com data+descrição e valor somente nas linhas seguintes.
    """
    lines = [" ".join(ln.split()) for ln in raw_text.splitlines()]
    date_pat = re.compile(rf"^(\d{{1,2}})\s*({_MON_ALT})\b\s*(.*)$", re.I)
    out: list[_Row] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = date_pat.match(line)
        if not m:
            i += 1
            continue
        day_s, mon_s, rest = m.group(1), m.group(2).lower()[:3], (m.group(3) or "").strip()
        # Se o valor já está na mesma linha, o parser one-line já cobre.
        if _MONEY_IN_TEXT_RE.search(rest):
            i += 1
            continue

        j = i + 1
        parts = [rest] if rest else []
        while j < len(lines):
            nxt = lines[j].strip()
            if not nxt:
                j += 1
                continue
            if date_pat.match(nxt):
                break
            if re.match(r"^\d+\s+de\s+\d+$", nxt, re.I) or re.match(r"^--\s*\d+\s+of\s+\d+\s*--$", nxt, re.I):
                break
            parts.append(nxt)
            # Em geral 1-3 linhas bastam para achar o valor do bloco.
            if len(parts) >= 4 and _MONEY_IN_TEXT_RE.search(" ".join(parts)):
                break
            j += 1

        if parts:
            chunk = " ".join(parts).strip()
            row = _nubank_row_from_chunk(chunk, day_s, mon_s, year, allow_empty_desc=False)
            if row:
                out.append(row)
        i = max(i + 1, j)
    return out


def _nubank_pdf_rows_split_date_lines(raw_text: str, year: int) -> list[_Row]:
    """
    Captura layout em duas linhas: uma só com a data e a seguinte com descrição+valor.
    Ex.:
      28 MAR
      •••• 9587 Mercadodxltda R$ 82,44
    """
    lines = [" ".join(ln.split()) for ln in raw_text.splitlines()]
    date_only = re.compile(rf"^(\d{{1,2}})\s*({_MON_ALT})$", re.I)
    out: list[_Row] = []
    i = 0
    while i < len(lines):
        cur = lines[i].strip()
        m = date_only.match(cur)
        if not m:
            i += 1
            continue
        day_s, mon_s = m.group(1), m.group(2).lower()[:3]
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            break
        nxt = lines[j].strip()
        if date_only.match(nxt):
            i = j
            continue
        if not _MONEY_IN_TEXT_RE.search(nxt):
            i = j
            continue
        row = _nubank_row_from_chunk(nxt, day_s, mon_s, year, allow_empty_desc=False)
        if row:
            out.append(row)
        i = j + 1
    return out


def parse_nubank_pdf_text(text: str, default_date: str | None) -> list[_Row]:
    """
    Fatura Nubank (PDF digital): datas como '8 abr', '10 MAR', sem ano; valor tipo R$ 1.234,56.
    O texto do pypdf costuma vir em uma linha longa ou várias linhas curtas.
    """
    year = _year_from_default(default_date)
    raw = _normalize_nubank_month_words(text.replace("\xa0", " ").replace("\u00a0", " "))
    text_1 = " ".join(raw.split())

    # O texto do PDF pode alternar os dois layouts no mesmo arquivo — unimos tudo e só tiramos
    # repetição exata da mesma linha (duas heurísticas pegando o mesmo texto).
    rows_after = _nubank_pdf_rows_date_then_desc(text_1, year)
    rows_before = _nubank_pdf_rows_desc_then_date(text_1, year)
    out = _concat_rows_merge_parsers(rows_after, rows_before)

    line_rows: list[_Row] = []
    for raw_line in raw.splitlines():
        line = " ".join(raw_line.split())
        if len(line) < 8:
            continue
        row = _parse_nubank_pdf_one_line(line, year)
        if row:
            line_rows.append(row)

    # Preferimos parsing por linhas (mais fiel à fatura) e completamos apenas com
    # multiline por linhas reais (evita duplicidades/datas deslocadas do texto contínuo).
    multiline_rows = _nubank_pdf_rows_multiline_lines(raw, year)
    split_date_rows = _nubank_pdf_rows_split_date_lines(raw, year)
    if line_rows or multiline_rows or split_date_rows:
        # Não filtramos por "DE … A …" do cabeçalho: ano/mês interpretado errado excluía lançamentos válidos.
        # Quando há parsing por linhas reais, evitamos mesclar com o parser de texto contínuo (`out`),
        # que pode repetir alguns lançamentos por ambiguidade de quebra.
        return _concat_rows_merge_parsers(line_rows, multiline_rows, split_date_rows)

    if out:
        return out

    return []


def parse_statement_file(
    content: bytes,
    filename: str,
    format_id: str,
    default_date: str | None,
) -> tuple[list[_Row], list[str]]:
    warnings: list[str] = []
    if len(content) > _MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo muito grande (máx. 5 MB).")

    lower = filename.lower()
    is_pdf = lower.endswith(".pdf")
    is_csv = lower.endswith(".csv") or lower.endswith(".txt")

    # Defensivo: perfil PDF selecionado para um arquivo CSV/TXT. Em vez de jogar bytes
    # de texto no leitor de PDF (que falha com "Stream has ended unexpectedly"),
    # redirecionamos para o parser CSV equivalente.
    _PDF_TO_CSV_FALLBACK: Final[dict[str, str]] = {
        "nubank_pdf": "nubank_csv",
        "santander_pdf": "santander_csv",
        "itau_azul_pdf": "itau_azul_csv",
        "itau_pda_pdf": "itau_pda_csv",
        "pdf_br": "generic_csv",
    }
    if is_csv and not is_pdf and format_id in _PDF_TO_CSV_FALLBACK:
        warnings.append(
            "Arquivo é CSV, mas um perfil PDF foi selecionado; lendo como CSV automaticamente."
        )
        format_id = _PDF_TO_CSV_FALLBACK[format_id]

    if format_id == "nubank_pdf":
        if not is_pdf:
            warnings.append("Extensão não é .pdf; tentando ler como PDF mesmo assim.")
        text = _extract_pdf_text(content)
        if len(text.strip()) < 20:
            warnings.append(
                "Pouco texto na extração automática; se nada aparecer, experimente o outro perfil de PDF ou CSV do banco."
            )
        rows = parse_nubank_pdf_text(text, default_date)
        if not rows:
            rows = parse_pdf_br_lines(text, default_date)
        return rows, warnings

    if format_id == "pdf_br":
        if not is_pdf:
            warnings.append("Extensão não é .pdf; tentando ler como PDF mesmo assim.")
        text = _extract_pdf_text(content)
        if len(text.strip()) < 20:
            warnings.append(
                "Pouco texto na extração automática; se nada aparecer, experimente o outro perfil de PDF ou CSV do banco."
            )
        rows = parse_pdf_br_lines(text, default_date)
        if not rows:
            rows = parse_nubank_pdf_text(text, default_date)
            if rows:
                warnings.append(
                    "Datas sem ano na fatura usam o ano do período selecionado no app; confira as linhas antes de importar."
                )
        return rows, warnings

    if format_id == "santander_pdf":
        if not is_pdf:
            warnings.append("Extensão não é .pdf; tentando ler como PDF mesmo assim.")
        text = _extract_pdf_text(content)
        if len(text.strip()) < 20:
            warnings.append(
                "Pouco texto na extração automática; se nada aparecer, use um PDF digital (não escaneado)."
            )
        rows = parse_santander_pdf_text(text, default_date)
        if not rows:
            warnings.append(
                "Nenhuma linha encontrada nas seções Parcelamentos/Despesas; confira o formato da fatura ou use o perfil PDF genérico."
            )
        return rows, warnings

    if format_id == "itau_azul_pdf":
        if not is_pdf:
            warnings.append("Extensão não é .pdf; tentando ler como PDF mesmo assim.")
        text = _extract_itau_pdf_text(content)
        if len(text.strip()) < 20:
            warnings.append(
                "Pouco texto na extração automática; se nada aparecer, use um PDF digital (não escaneado)."
            )
        rows = parse_itau_azul_pdf_text(text, default_date)
        if not rows:
            warnings.append(
                "Nenhuma linha encontrada nos blocos de lançamentos do Itaú Azul; confira o layout da fatura ou use o perfil PDF genérico."
            )
        mismatch = itau_total_mismatch_warning(text, rows)
        if mismatch:
            warnings.append(mismatch)
        return rows, warnings

    if format_id == "itau_pda_pdf":
        if not is_pdf:
            warnings.append("Extensão não é .pdf; tentando ler como PDF mesmo assim.")
        text = _extract_itau_pdf_text(content)
        if len(text.strip()) < 20:
            warnings.append(
                "Pouco texto na extração automática; se nada aparecer, use um PDF digital (não escaneado)."
            )
        rows = parse_itau_pda_pdf_text(text, default_date)
        if not rows:
            warnings.append(
                "Nenhuma linha encontrada nos blocos do Itaú PDA (compras/saques, produtos/serviços, outros lançamentos); confira o layout da fatura ou use o perfil PDF genérico."
            )
        mismatch = itau_total_mismatch_warning(text, rows)
        if mismatch:
            warnings.append(mismatch)
        return rows, warnings

    if is_pdf and format_id not in ("pdf_br", "nubank_pdf", "santander_pdf", "itau_azul_pdf", "itau_pda_pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Para arquivo PDF, selecione um formato PDF (genérico, Nubank, Santander, Itaú Azul ou Itaú PDA).",
        )

    if not is_csv and not is_pdf:
        warnings.append("Formato de arquivo não reconhecido; interpretando como texto CSV.")

    text = _decode_text(content)
    if format_id == "nubank_csv":
        rows = parse_nubank_csv(text, default_date)
    elif format_id == "santander_csv":
        rows = parse_santander_csv(text, default_date)
    elif format_id == "itau_azul_csv":
        rows = parse_itau_azul_csv(text, default_date)
    elif format_id == "itau_pda_csv":
        rows = parse_itau_pda_csv(text, default_date)
    else:
        rows = parse_generic_csv(text, default_date)

    if not rows and format_id in {"nubank_csv", "santander_csv", "itau_azul_csv", "itau_pda_csv"}:
        if format_id == "nubank_csv":
            warnings.append("Nenhuma linha no layout Nubank; tentando leitura genérica do CSV.")
        elif format_id == "santander_csv":
            warnings.append("Nenhuma linha no layout Santander CSV; tentando leitura genérica do CSV.")
        elif format_id == "itau_azul_csv":
            warnings.append("Nenhuma linha no layout Itaú Azul CSV; tentando leitura genérica do CSV.")
        else:
            warnings.append("Nenhuma linha no layout Itaú PDA CSV; tentando leitura genérica do CSV.")
        rows = parse_generic_csv(text, default_date)

    return rows, warnings
