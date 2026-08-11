import { Fragment } from "react";
import { Cell, Pie, PieChart, Tooltip } from "recharts";
import { ChartBox } from "./ChartBox";
import { formatCompactBRL } from "../money";

export const CATEGORY_CHART_COLORS = [
  "#eb6834",
  "#2a78d6",
  "#1baf7a",
  "#eda100",
  "#e87ba4",
  "#4a3aa7",
  "#e34948",
  "#008300",
];

export type CategoryExpenseRow = {
  name: string;
  value: number;
  color: string;
};

type CategoryExpensesChartProps = {
  rows: CategoryExpenseRow[];
  totalLabel: string;
};

export function CategoryExpensesChart({ rows, totalLabel }: CategoryExpensesChartProps) {
  if (rows.length === 0) return null;

  const total = rows.reduce((sum, row) => sum + row.value, 0);

  return (
    <div className="cat-wrap">
      <div className="cat-donut-wrap">
        <ChartBox height={110}>
          {({ width, height }) => (
            <PieChart width={width} height={height}>
              <Pie
                data={rows}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={38}
                outerRadius={52}
                stroke="none"
                paddingAngle={1}
              >
                {rows.map((row) => (
                  <Cell key={row.name} fill={row.color} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value: number) => formatCompactBRL(value)}
                contentStyle={{ fontSize: 12 }}
              />
            </PieChart>
          )}
        </ChartBox>
        <div className="cat-donut-center">
          <span className="cat-total-val">{totalLabel}</span>
          <span className="cat-total-lbl">total</span>
        </div>
      </div>

      <div className="cat-grid" role="table" aria-label="Gastos por categoria">
        <span className="cat-th" role="columnheader">
          Categoria
        </span>
        <span className="cat-th cat-th-r" role="columnheader">
          Valor
        </span>
        <span className="cat-th cat-th-bar" role="columnheader">
          Distribuição
        </span>
        <span className="cat-th cat-th-r" role="columnheader">
          %
        </span>

        {rows.map((row) => {
          const pct = total > 0 ? Math.round((row.value / total) * 100) : 0;
          return (
            <Fragment key={row.name}>
              <span className="cat-name">
                <span className="cat-dot" style={{ background: row.color }} />
                {row.name}
              </span>
              <span className="cat-val">{formatCompactBRL(row.value)}</span>
              <div className="cat-bar-wrap" title={`${pct}%`}>
                <div
                  className="cat-bar-fill"
                  style={{ width: `${pct}%`, background: row.color }}
                />
              </div>
              <span className="cat-pct">{pct}%</span>
            </Fragment>
          );
        })}

        <div className="cat-divider" />

        <span className="cat-total-row">Total</span>
        <span className="cat-val cat-total-row">{totalLabel}</span>
        <div aria-hidden="true" />
        <span className="cat-pct cat-total-row">100%</span>
      </div>
    </div>
  );
}
