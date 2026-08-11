/** Linha pronta para POST em createCardTransaction (valor com ponto decimal). */
export type ParsedCardCsvRow = {
  data: string;
  descricao: string;
  valor: string;
};

function splitCsvLine(line: string, delim: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') {
      inQuotes = !inQuotes;
    } else if (c === delim && !inQuotes) {
      out.push(cur.trim());
      cur = "";
    } else {
      cur += c;
    }
  }
  out.push(cur.trim());
  return out;
}

function normHeader(h: string): string {
  return h
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
}

export function parseBrazilianMoney(s: string): number | null {
  const t = s.trim().replace(/\s/g, "").replace(/R\$\s?/gi, "");
  if (!t) return null;
  const neg = t.startsWith("-") || t.startsWith("(");
  let u = t.replace(/[()]/g, "").replace(/^-/, "");
  if (u.includes(",") && /\.\d{3}/.test(u)) {
    u = u.replace(/\./g, "").replace(",", ".");
  } else if (u.includes(",")) {
    u = u.replace(",", ".");
  }
  const n = parseFloat(u);
  if (Number.isNaN(n)) return null;
  const v = Math.abs(n);
  return neg ? -v : v;
}

function parseDateToIso(s: string): string | null {
  const t = s.trim().slice(0, 10);
  const m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (m) {
    const d = parseInt(m[1], 10);
    const mo = parseInt(m[2], 10);
    const y = parseInt(m[3], 10);
    if (mo >= 1 && mo <= 12 && d >= 1 && d <= 31)
      return `${y}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  }
  const iso = t.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  return null;
}

/**
 * Interpreta CSV de fatura (bancos costumam usar `;` e cabeçalhos em português).
 * Colunas reconhecidas: data, descrição, valor — nomes flexíveis.
 */
export function parseCardStatementCsv(
  raw: string,
  options?: { defaultDate?: string },
): ParsedCardCsvRow[] {
  const defaultDate = options?.defaultDate;
  const lines = raw.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length === 0) return [];

  const first = lines[0];
  const delim = first.split(";").length >= first.split(",").length ? ";" : ",";
  const matrix = lines.map((l) => splitCsvLine(l, delim));
  if (matrix[0].length < 2) return [];

  let colData = -1;
  let colDesc = -1;
  let colValor = -1;
  const h0 = matrix[0].map(normHeader);

  for (let i = 0; i < h0.length; i++) {
    const h = h0[i];
    if (/^(data|date|dt|vencimento|compra|data da compra)$/.test(h)) colData = i;
    else if (/^(valor|amount|value|total)$/.test(h)) colValor = i;
    else if (/^(desc|historico|estabelecimento|title|memo|lancamento|identificador)$/.test(h)) colDesc = i;
  }

  let startRow = 0;
  const hasHeader = colData >= 0 || colValor >= 0 || colDesc >= 0;
  if (hasHeader) {
    if (colData < 0) colData = h0.findIndex((x) => /data|date/.test(x));
    if (colValor < 0) colValor = h0.findIndex((x) => /valor|amount|total/.test(x));
    if (colDesc < 0) colDesc = h0.findIndex((x) => /desc|histor|title|estab|memo|ident/.test(x));
    startRow = 1;
  }

  if (colDesc < 0 && colData >= 0 && colValor >= 0) {
    for (let i = 0; i < h0.length; i++) {
      if (i !== colData && i !== colValor) {
        colDesc = i;
        break;
      }
    }
  }

  if (colValor < 0 && matrix[0].length >= 3) {
    colData = 0;
    colDesc = 1;
    colValor = 2;
    startRow = 0;
    const testVal = parseBrazilianMoney(matrix[0][colValor] ?? "");
    if (testVal === null || testVal === 0) startRow = 1;
  } else if (colValor < 0 && matrix[0].length === 2) {
    colDesc = 0;
    colValor = 1;
    startRow = 0;
    const testVal = parseBrazilianMoney(matrix[0][colValor] ?? "");
    if (testVal === null) startRow = 1;
  }

  if (colValor < 0) return [];

  const out: ParsedCardCsvRow[] = [];

  for (let r = startRow; r < matrix.length; r++) {
    const row = matrix[r];
    if (row.length <= Math.max(colData, colDesc, colValor)) continue;

    const ds = colData >= 0 ? (row[colData] ?? "").trim() : "";
    const desc = (colDesc >= 0 ? row[colDesc] : row[0] ?? "").trim() || "Importação CSV";
    const vs = (row[colValor] ?? "").trim();

    let dataIso = ds ? parseDateToIso(ds) : null;
    if (!dataIso && defaultDate) dataIso = defaultDate;
    if (!dataIso) continue;

    const valNum = parseBrazilianMoney(vs);
    if (valNum === null || valNum <= 0) continue;

    out.push({
      data: dataIso,
      descricao: desc.slice(0, 500),
      valor: valNum.toFixed(2),
    });
  }

  return out;
}
