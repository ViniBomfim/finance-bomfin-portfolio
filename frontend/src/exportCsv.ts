import { mergeExpenseCategoryRows } from "./mergeExpenseCategories";
import type { Category, DashboardSummary } from "./types";
import { jsPDF } from "jspdf";
import { formatBRL } from "./money";

export type PersonUsagePdfOptions = {
  periodLabel?: string;
  categories?: { name: string; total: number }[];
};

type PdfColumn = {
  label: string;
  width: number;
  align?: "left" | "right";
  wrap?: boolean;
};

type PdfTableRow = string[];

export function downloadDashboardCsv(
  summary: DashboardSummary,
  filename: string,
  expenseCategories: Pick<Category, "id" | "nome">[],
) {
  const lines: string[] = [];
  lines.push("Indicador;Valor");
  lines.push(`Receita;${summary.total_income}`);
  lines.push(`Despesas;${summary.total_expenses}`);
  lines.push(`Sobrando;${summary.monthly_balance}`);
  lines.push(`Falta pagar;${summary.pending_expenses}`);
  lines.push("");
  lines.push("Categoria;Gastos");
  const merged = mergeExpenseCategoryRows(expenseCategories, summary.expenses_by_category);
  for (const r of merged) {
    lines.push(`${r.categoria_nome};${r.gastos}`);
  }
  lines.push("");
  lines.push("Meta;Progresso %;Atual;Meta");
  for (const g of summary.goal_progress) {
    lines.push(`${g.nome};${g.progress_percent};${g.valor_atual};${g.valor_meta}`);
  }
  const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function downloadPersonUsageCsv(
  person: DashboardSummary["usage_by_person_cards"][number],
  filename: string,
) {
  const lines: string[] = [];
  lines.push("Pessoa;Total cartões;Total gastos fixos;Total devedores;Total geral");
  lines.push(
    `${person.pessoa_nome};${person.total_cartoes};${person.total_gastos_fixos};${person.total_divida_devedores};${person.total_geral}`,
  );
  lines.push("");

  lines.push("Cartão;Total");
  if (person.cartoes.length === 0) {
    lines.push("Sem cartão;0");
  } else {
    for (const card of person.cartoes) {
      lines.push(`${card.card_nome};${card.total}`);
    }
  }
  lines.push("");

  lines.push("Gasto fixo;Total");
  if (person.gastos_fixos.length === 0) {
    lines.push("Sem gasto fixo;0");
  } else {
    for (const fixed of person.gastos_fixos) {
      lines.push(`${fixed.descricao};${fixed.total}`);
    }
  }
  lines.push("");

  lines.push("Devedor;Emprestimo;Ultimo pagamento;Dias sem pagamento;Valor pendente");
  if (person.devedores.length === 0) {
    lines.push("Sem dívida pendente;;;;0");
  } else {
    for (const debtor of person.devedores) {
      lines.push(
        `${debtor.devedor_nome};${debtor.data_emprestimo ?? ""};${debtor.ultimo_pagamento_em ?? ""};${debtor.dias_sem_pagamento ?? ""};${debtor.valor_restante}`,
      );
    }
  }

  const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

function formatDateBR(value: string) {
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("pt-BR");
}

function txStatus(pago: boolean) {
  return pago ? "Pago" : "Pendente";
}

function txFalta(pago: boolean, faltaPagar: string) {
  if (pago) return "—";
  const falta = parseFloat(faltaPagar);
  if (falta > 0) return formatBRL(faltaPagar);
  return "—";
}

function columnPositions(columns: PdfColumn[], startX: number) {
  const positions: number[] = [];
  let x = startX;
  for (const col of columns) {
    positions.push(x);
    x += col.width;
  }
  return positions;
}

export function downloadPersonUsagePdf(
  person: DashboardSummary["usage_by_person_cards"][number],
  installments: DashboardSummary["person_installments"][number] | null,
  filename: string,
  options: PersonUsagePdfOptions = {},
) {
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 40;
  const contentWidth = pageWidth - margin * 2;
  const footerY = pageHeight - 24;
  let y = 40;
  let pageNum = 1;

  const ensurePage = (extra = 16) => {
    if (y + extra > footerY - 8) {
      drawPageFooter();
      doc.addPage();
      pageNum += 1;
      y = 40;
      return true;
    }
    return false;
  };

  const drawPageFooter = () => {
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(148, 163, 184);
    doc.text(`Pagina ${pageNum}`, pageWidth / 2, footerY, { align: "center" });
    doc.setTextColor(0, 0, 0);
  };

  const addSectionTitle = (text: string) => {
    ensurePage(28);
    y += 4;
    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.text(text, margin, y);
    y += 14;
    doc.setDrawColor(226, 232, 240);
    doc.line(margin, y, pageWidth - margin, y);
    y += 10;
  };

  const addTextLine = (text: string, indent = 0) => {
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    const lines = doc.splitTextToSize(text, contentWidth - indent);
    for (const line of lines) {
      ensurePage(14);
      doc.text(line, margin + indent, y);
      y += 13;
    }
  };

  const drawTableHeader = (columns: PdfColumn[], positions: number[]) => {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(9);
    doc.setFillColor(241, 245, 249);
    doc.setDrawColor(226, 232, 240);
    doc.rect(margin, y - 10, contentWidth, 18, "FD");
    for (let i = 0; i < columns.length; i += 1) {
      const col = columns[i];
      const x = positions[i];
      if (col.align === "right") {
        doc.text(col.label, x + col.width - 4, y, { align: "right" });
      } else {
        doc.text(col.label, x + 4, y);
      }
    }
    y += 10;
  };

  const drawTable = (columns: PdfColumn[], rows: PdfTableRow[]) => {
    if (rows.length === 0) return;
    const positions = columnPositions(columns, margin);
    const wrapColIndex = columns.findIndex((col) => col.wrap);
    const minRowHeight = 16;
    const cellPad = 4;

    const drawHeaderIfNeeded = () => {
      ensurePage(28);
      drawTableHeader(columns, positions);
    };

    drawHeaderIfNeeded();

    for (let rowIdx = 0; rowIdx < rows.length; rowIdx += 1) {
      const row = rows[rowIdx];
      let lineCount = 1;
      const wrappedCells: string[][] = row.map((cell, colIdx) => {
        if (columns[colIdx]?.wrap) {
          const lines = doc.splitTextToSize(cell, columns[colIdx].width - cellPad * 2);
          lineCount = Math.max(lineCount, lines.length);
          return lines;
        }
        return [cell];
      });

      const rowHeight = Math.max(minRowHeight, lineCount * 11 + 6);
      if (ensurePage(rowHeight + 4)) {
        drawTableHeader(columns, positions);
      }

      if (rowIdx % 2 === 0) {
        doc.setFillColor(248, 250, 252);
        doc.rect(margin, y - 8, contentWidth, rowHeight, "F");
      }

      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      for (let colIdx = 0; colIdx < columns.length; colIdx += 1) {
        const col = columns[colIdx];
        const x = positions[colIdx];
        const lines = wrappedCells[colIdx];
        for (let lineIdx = 0; lineIdx < lines.length; lineIdx += 1) {
          const textY = y + lineIdx * 11;
          if (col.align === "right") {
            doc.text(lines[lineIdx], x + col.width - cellPad, textY, { align: "right" });
          } else {
            doc.text(lines[lineIdx], x + cellPad, textY);
          }
        }
      }
      y += rowHeight;
    }
    y += 6;
  };

  const drawSummaryGrid = () => {
    const colWidth = (contentWidth - 12) / 2;
    const cardHeight = 34;
    const cards: [string, string][] = [
      ["Cartoes", formatBRL(person.total_cartoes)],
      ["Gastos fixos", formatBRL(person.total_gastos_fixos)],
      ["Devedores", formatBRL(person.total_divida_devedores)],
      ["Falta pagar", formatBRL(person.total_falta_pagar)],
    ];
    if (installments) {
      cards.push(
        ["Parcelas no mes", formatBRL(installments.total_parcelas_mes)],
        ["Compras parceladas", String(installments.compras_parceladas)],
      );
    }

    ensurePage(cards.length * (cardHeight + 8));
    for (let i = 0; i < cards.length; i += 2) {
      const rowCards = cards.slice(i, i + 2);
      for (let j = 0; j < rowCards.length; j += 1) {
        const [label, value] = rowCards[j];
        const x = margin + j * (colWidth + 12);
        doc.setDrawColor(226, 232, 240);
        doc.setFillColor(255, 255, 255);
        doc.roundedRect(x, y, colWidth, cardHeight, 6, 6, "FD");
        doc.setFont("helvetica", "normal");
        doc.setFontSize(9);
        doc.text(label, x + 8, y + 13);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(10);
        doc.text(value, x + 8, y + 26);
      }
      y += cardHeight + 8;
    }
    y += 8;
  };

  const addHeader = () => {
    const hasPeriod = Boolean(options.periodLabel);
    const headerHeight = hasPeriod ? 96 : 82;
    doc.setDrawColor(226, 232, 240);
    doc.setFillColor(248, 250, 252);
    doc.roundedRect(margin, y, contentWidth, headerHeight, 8, 8, "FD");
    doc.setFont("helvetica", "bold");
    doc.setFontSize(16);
    doc.text(`Resumo de gastos - ${person.pessoa_nome}`, margin + 12, y + 24);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    let subY = y + 42;
    if (hasPeriod) {
      doc.text(`Periodo: ${options.periodLabel}`, margin + 12, subY);
      subY += 14;
    }
    doc.text(`Gerado em ${new Date().toLocaleString("pt-BR")}`, margin + 12, subY);
    y += headerHeight + 10;

    doc.setDrawColor(167, 139, 250);
    doc.setFillColor(237, 233, 254);
    doc.roundedRect(margin, y, contentWidth, 36, 6, 6, "FD");
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.setTextColor(109, 40, 217);
    doc.text("Total geral", margin + 12, y + 14);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(16);
    doc.text(formatBRL(person.total_geral), margin + 12, y + 28);
    doc.setTextColor(0, 0, 0);
    y += 48;
  };

  const txColumns: PdfColumn[] = [
    { label: "Data", width: 52 },
    { label: "Descricao", width: 230, wrap: true },
    { label: "Parc.", width: 32 },
    { label: "Valor", width: 68, align: "right" },
    { label: "Status", width: 48 },
    { label: "Falta", width: 58, align: "right" },
  ];

  addHeader();
  drawSummaryGrid();

  if (options.categories && options.categories.length > 0) {
    addSectionTitle("Gastos por categoria");
    const totalGeral = parseFloat(person.total_geral) || 0;
    const catColumns: PdfColumn[] = [
      { label: "Categoria", width: 280, wrap: true },
      { label: "Total", width: 100, align: "right" },
      { label: "%", width: 60, align: "right" },
    ];
    drawTable(
      catColumns,
      options.categories.map((cat) => {
        const pct = totalGeral > 0 ? `${Math.round((cat.total / totalGeral) * 100)}%` : "—";
        return [cat.name, formatBRL(cat.total), pct];
      }),
    );
  }

  addSectionTitle("Cartoes e lancamentos");
  if (person.cartoes.length === 0) {
    addTextLine("Sem despesas de cartao no periodo.");
  } else {
    for (const card of person.cartoes) {
      ensurePage(36);
      doc.setDrawColor(226, 232, 240);
      doc.setFillColor(248, 250, 252);
      doc.roundedRect(margin, y, contentWidth, 22, 6, 6, "FD");
      doc.setFont("helvetica", "bold");
      doc.setFontSize(10);
      doc.text(card.card_nome, margin + 10, y + 14);
      doc.text(formatBRL(card.total), pageWidth - margin - 10, y + 14, { align: "right" });
      y += 30;

      if (card.lancamentos.length === 0) {
        addTextLine("Sem lancamentos neste cartao.", 10);
      } else {
        drawTable(
          txColumns,
          card.lancamentos.map((tx) => [
            formatDateBR(tx.data),
            tx.descricao,
            tx.parcela_total > 1 ? `${tx.parcela_atual}/${tx.parcela_total}` : "—",
            formatBRL(tx.valor),
            txStatus(tx.pago),
            txFalta(tx.pago, tx.falta_pagar),
          ]),
        );
      }
      y += 4;
    }
  }

  addSectionTitle("Gastos fixos");
  if (person.gastos_fixos.length === 0) {
    addTextLine("Sem gastos fixos para esta pessoa.");
  } else {
    const fixedColumns: PdfColumn[] = [
      { label: "Descricao", width: 260, wrap: true },
      { label: "Total", width: 80, align: "right" },
      { label: "Status", width: 48 },
      { label: "Falta", width: 58, align: "right" },
    ];
    drawTable(
      fixedColumns,
      person.gastos_fixos.map((fixed) => [
        fixed.descricao,
        formatBRL(fixed.total),
        txStatus(fixed.pago),
        txFalta(fixed.pago, fixed.falta_pagar),
      ]),
    );
  }

  addSectionTitle("Devedores");
  if (person.devedores.length === 0) {
    addTextLine("Sem divida pendente em devedores.");
  } else {
    const debtorColumns: PdfColumn[] = [
      { label: "Nome", width: 160, wrap: true },
      { label: "Emprestado", width: 80, align: "right" },
      { label: "Pago", width: 80, align: "right" },
      { label: "Status", width: 48 },
      { label: "Falta", width: 60, align: "right" },
    ];
    drawTable(
      debtorColumns,
      person.devedores.map((debtor) => [
        debtor.devedor_nome,
        formatBRL(debtor.valor_emprestado),
        formatBRL(debtor.valor_pago),
        debtor.pago ? "Pago" : "Pendente",
        formatBRL(debtor.falta_pagar),
      ]),
    );
  }

  addSectionTitle("Parcelas");
  if (!installments || installments.compras.length === 0) {
    addTextLine("Sem compras parceladas para esta pessoa.");
  } else {
    addTextLine(
      `Total de parcelas no mes: ${formatBRL(installments.total_parcelas_mes)} · ${installments.compras_parceladas} compra(s)`,
    );
    y += 4;
    const parcelColumns: PdfColumn[] = [
      { label: "Compra", width: 160, wrap: true },
      { label: "Cartao", width: 80 },
      { label: "Parcela/mes", width: 80, align: "right" },
      { label: "Progresso", width: 55, align: "right" },
      { label: "Ate", width: 55, align: "right" },
    ];
    drawTable(
      parcelColumns,
      installments.compras.map((purchase) => [
        purchase.descricao,
        purchase.card_nome,
        formatBRL(purchase.valor_parcela),
        `${purchase.parcela_atual}/${purchase.total_parcelas}`,
        formatDateBR(purchase.ate_data),
      ]),
    );
  }

  drawPageFooter();
  doc.save(filename);
}
