import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import { usePeriod } from "../context/PeriodContext";
import type { BudgetCompareRow, CategoryExpenseReportRow, MonthlyFlowRow } from "../types";
import { formatBRL } from "../money";

const MONTH_SHORT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

function fmtTooltip(value: number | string | undefined) {
  if (value === undefined) return "";
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (Number.isNaN(n)) return String(value);
  return formatBRL(n);
}

export function Reports() {
  const { periodId, ready, currentPeriod } = usePeriod();
  const ano = currentPeriod?.ano ?? new Date().getFullYear();
  const [anoState, setAnoState] = useState(ano);
  const [flow, setFlow] = useState<MonthlyFlowRow[]>([]);
  const [byCat, setByCat] = useState<CategoryExpenseReportRow[]>([]);
  const [budgetVs, setBudgetVs] = useState<BudgetCompareRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    setAnoState(ano);
  }, [ano]);

  useEffect(() => {
    if (!ready) return;
    let c = false;
    (async () => {
      try {
        setError("");
        const f = await api.reportsMonthlyFlow(anoState);
        if (!c) setFlow(f);
      } catch (e) {
        if (!c) setError(e instanceof Error ? e.message : "Erro");
      }
    })();
    return () => {
      c = true;
    };
  }, [ready, anoState]);

  useEffect(() => {
    if (!ready || !periodId) return;
    let c = false;
    (async () => {
      try {
        const [cats, bv] = await Promise.all([
          api.reportsExpensesByCategory(periodId),
          api.reportsBudgetVsActual(periodId),
        ]);
        if (!c) {
          setByCat(cats);
          setBudgetVs(bv);
        }
      } catch (e) {
        if (!c) setError(e instanceof Error ? e.message : "Erro");
      }
    })();
    return () => {
      c = true;
    };
  }, [ready, periodId]);

  const flowChart = useMemo(
    () =>
      flow.map((r) => ({
        mesLabel: MONTH_SHORT[r.mes - 1] ?? String(r.mes),
        receitas: parseFloat(r.receitas),
        despesas: parseFloat(r.despesas),
        saldo: parseFloat(r.saldo),
      })),
    [flow],
  );

  const pieData = useMemo(
    () =>
      byCat.map((r) => ({
        name: r.categoria_nome,
        value: parseFloat(r.total),
        fill: r.cor,
      })),
    [byCat],
  );

  const budgetBars = useMemo(
    () =>
      budgetVs.map((r) => ({
        name: r.categoria_nome,
        planejado: parseFloat(r.planejado),
        realizado: parseFloat(r.realizado),
      })),
    [budgetVs],
  );

  if (!ready) return null;

  return (
    <div className="padded">
      <h1>Relatórios</h1>
      <p className="muted">
        Gráficos usam o período da barra superior (pizza e orçamento) e o ano abaixo (fluxo mensal).
      </p>
      {error && <p className="error">{error}</p>}

      <div className="card">
        <h2>Fluxo mensal ({anoState})</h2>
        <div className="field" style={{ maxWidth: "12rem" }}>
          <label htmlFor="ano-rep">Ano</label>
          <input
            id="ano-rep"
            type="number"
            min={2000}
            max={2100}
            value={anoState}
            onChange={(e) => setAnoState(Number(e.target.value))}
          />
        </div>
        {flowChart.length === 0 ? (
          <p className="muted">Nenhum período neste ano.</p>
        ) : (
          <>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={flowChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="mesLabel" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip formatter={(v) => fmtTooltip(v as number | string | undefined)} />
                  <Legend />
                  <Bar dataKey="receitas" name="Receitas" fill="var(--success)" />
                  <Bar dataKey="despesas" name="Despesas" fill="var(--danger)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="chart-wrap" style={{ marginTop: "1rem" }}>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={flowChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="mesLabel" />
                  <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip formatter={(v) => fmtTooltip(v as number | string | undefined)} />
                  <Legend />
                  <Line type="monotone" dataKey="saldo" name="Saldo" stroke="var(--accent)" strokeWidth={2} dot />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>

      <div className="card">
        <h2>Gastos por categoria (mês atual)</h2>
        {pieData.length === 0 ? (
          <p className="muted">Sem despesas categorizadas neste período.</p>
        ) : (
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={320}>
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={110}
                  label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => fmtTooltip(v as number | string | undefined)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="card">
        <h2>Orçamento × realizado</h2>
        {budgetBars.length === 0 ? (
          <p className="muted">Nenhum orçamento definido para este período.</p>
        ) : (
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={Math.max(280, budgetBars.length * 36)}>
              <BarChart
                data={budgetBars}
                layout="vertical"
                margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis type="number" tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => fmtTooltip(v as number | string | undefined)} />
                <Legend />
                <Bar dataKey="planejado" name="Planejado" fill="var(--accent)" />
                <Bar dataKey="realizado" name="Realizado" fill="var(--muted)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
