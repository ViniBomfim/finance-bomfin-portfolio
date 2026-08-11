import { useEffect, useState } from "react";
import { api } from "../api";
import { usePeriod } from "../context/PeriodContext";
import type { BudgetCompareRow } from "../types";
import { formatBRL } from "../money";
import type { Category } from "../types";

export function Budgets() {
  const { periodId, ready, periodClosed, monthLabel, periods } = usePeriod();
  const [compare, setCompare] = useState<BudgetCompareRow[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [catId, setCatId] = useState("");
  const [valor, setValor] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [copyLoading, setCopyLoading] = useState(false);
  const [copyMessage, setCopyMessage] = useState("");
  const [replicateFrom, setReplicateFrom] = useState(String(new Date().getFullYear() - 1));
  const [replicateTo, setReplicateTo] = useState(String(new Date().getFullYear()));
  const [replicateLoading, setReplicateLoading] = useState(false);
  const [replicateMessage, setReplicateMessage] = useState("");

  async function refresh() {
    if (!periodId) return;
    const [cmp, cats] = await Promise.all([
      api.budgetCompare(periodId),
      api.categories("expense"),
    ]);
    setCompare(cmp);
    setCategories(cats);
    setCatId((c) => c || cats[0]?.id || "");
  }

  useEffect(() => {
    setCopyMessage("");
    setReplicateMessage("");
  }, [periodId]);

  const current = periods.find((p) => p.id === periodId);
  useEffect(() => {
    if (current) {
      setReplicateTo(String(current.ano));
      setReplicateFrom(String(current.ano - 1));
    }
  }, [current?.ano, periodId]);

  useEffect(() => {
    if (!ready || !periodId) return;
    let c = false;
    (async () => {
      try {
        await refresh();
      } catch (e) {
        if (!c) setError(e instanceof Error ? e.message : "Erro");
      }
    })();
    return () => {
      c = true;
    };
  }, [periodId, ready]);

  const prevPeriod =
    current &&
    periods.find((p) =>
      current!.mes > 1
        ? p.mes === current!.mes - 1 && p.ano === current!.ano
        : p.mes === 12 && p.ano === current!.ano - 1,
    );

  async function replicateYear() {
    const from = parseInt(replicateFrom, 10);
    const to = parseInt(replicateTo, 10);
    if (Number.isNaN(from) || Number.isNaN(to) || from === to) {
      setError("Informe dois anos distintos.");
      return;
    }
    setReplicateLoading(true);
    setError("");
    setReplicateMessage("");
    try {
      const created = await api.replicateYearBudgets(from, to);
      setReplicateMessage(
        created.length === 0
          ? "Nenhum orçamento novo (já existentes ou ano origem sem dados)."
          : `${created.length} linha(s) de orçamento replicada(s) para ${to}.`,
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao replicar");
    } finally {
      setReplicateLoading(false);
    }
  }

  async function copyFromPrevious() {
    if (!periodId || periodClosed) return;
    setCopyLoading(true);
    setError("");
    setCopyMessage("");
    try {
      const created = await api.copyBudgetsFromPrevious(periodId);
      setCopyMessage(
        created.length === 0
          ? "Nada a copiar (mês anterior sem orçamentos ou categorias já preenchidas)."
          : `${created.length} orçamento(s) copiado(s) do mês anterior.`,
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao copiar");
    } finally {
      setCopyLoading(false);
    }
  }

  async function addBudget(e: React.FormEvent) {
    e.preventDefault();
    if (!periodId || !catId) return;
    setLoading(true);
    setError("");
    try {
      await api.createBudget({
        categoria_id: catId,
        period_id: periodId,
        valor: valor.replace(",", "."),
      });
      setValor("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setLoading(false);
    }
  }

  if (!ready) return null;

  return (
    <div className="padded">
      <div className="page-head">
        <div>
          <h1>Orçamento</h1>
          <p className="muted">Planejado × realizado por categoria no período selecionado (barra superior).</p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={!periodId || periodClosed || !prevPeriod || copyLoading}
          onClick={copyFromPrevious}
          title={
            !prevPeriod
              ? "Cadastre o ano anterior ou o mês anterior na lista de períodos."
              : `Copiar valores planejados de ${monthLabel(prevPeriod.mes, prevPeriod.ano)}`
          }
        >
          {copyLoading ? "Copiando…" : "Copiar do mês anterior"}
        </button>
      </div>
      {copyMessage && <p className="muted">{copyMessage}</p>}
      {replicateMessage && <p className="muted">{replicateMessage}</p>}
      {error && <p className="error">{error}</p>}

      <div className="card">
        <h2>Novo ano: replicar orçamentos</h2>
        <p className="muted">
          Copia os valores planejados mês a mês do ano de origem para o ano de destino (cria os 12 meses do
          destino se ainda não existirem). Não altera despesas nem receitas.
        </p>
        <div className="inline-form" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="field" style={{ margin: 0 }}>
            <label htmlFor="rep-from">Ano origem</label>
            <input
              id="rep-from"
              type="number"
              min={2000}
              max={2100}
              value={replicateFrom}
              onChange={(e) => setReplicateFrom(e.target.value)}
            />
          </div>
          <div className="field" style={{ margin: 0 }}>
            <label htmlFor="rep-to">Ano destino</label>
            <input
              id="rep-to"
              type="number"
              min={2000}
              max={2100}
              value={replicateTo}
              onChange={(e) => setReplicateTo(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="btn"
            disabled={periodClosed || replicateLoading}
            onClick={replicateYear}
          >
            {replicateLoading ? "Replicando…" : "Replicar orçamentos"}
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Comparativo</h2>
        {compare.length === 0 ? (
          <p className="muted">Nenhum orçamento definido para este período.</p>
        ) : (
          <>
            <ul className="card-tx-list card-lancamentos-mobile-only" aria-label="Orçamentos">
              {compare.map((r) => (
                <li key={r.categoria_id} className="card-tx-item">
                  <div className="card-tx-item-main">
                    <span className="card-tx-desc">{r.categoria_nome}</span>
                    <span
                      className={`card-tx-val ${Number(r.diferenca) >= 0 ? "positive" : "negative"}`}
                    >
                      {formatBRL(r.diferenca)}
                    </span>
                  </div>
                  <div className="card-tx-item-meta muted small">
                    <span>Planejado {formatBRL(r.planejado)}</span>
                    <span>Realizado {formatBRL(r.realizado)}</span>
                  </div>
                </li>
              ))}
            </ul>
            <div className="card-lancamentos-desktop-only table-scroll-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Categoria</th>
                    <th>Planejado</th>
                    <th>Realizado</th>
                    <th>Diferença</th>
                  </tr>
                </thead>
                <tbody>
                  {compare.map((r) => (
                    <tr key={r.categoria_id}>
                      <td>{r.categoria_nome}</td>
                      <td>{formatBRL(r.planejado)}</td>
                      <td>{formatBRL(r.realizado)}</td>
                      <td className={Number(r.diferenca) >= 0 ? "positive" : "negative"}>
                        {formatBRL(r.diferenca)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <div className="card">
        <h2>Definir orçamento</h2>
        <form onSubmit={addBudget} className="inline-form">
          <select value={catId} onChange={(e) => setCatId(e.target.value)} required>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
              </option>
            ))}
          </select>
          <input
            placeholder="Valor planejado"
            inputMode="decimal"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
            required
          />
          <button type="submit" className="btn" disabled={loading || periodClosed}>
            Adicionar
          </button>
        </form>
      </div>
    </div>
  );
}
