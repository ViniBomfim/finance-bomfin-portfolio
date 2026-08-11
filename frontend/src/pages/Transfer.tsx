import { useEffect, useState } from "react";
import { api } from "../api";
import { usePeriod } from "../context/PeriodContext";
import { fetchGoalPoolTotals } from "../lib/goalPool";
import type { GoalRow, TransferRow } from "../types";
import { formatBRL } from "../money";

function parseDecimal(value: string): number {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function Transfer() {
  const { periodId } = usePeriod();
  const [goals, setGoals] = useState<GoalRow[]>([]);
  const [goalId, setGoalId] = useState("");
  const [valor, setValor] = useState("");
  const [data, setData] = useState(() => new Date().toISOString().slice(0, 10));
  const [history, setHistory] = useState<TransferRow[]>([]);
  const [error, setError] = useState("");
  const [metasPoolTotal, setMetasPoolTotal] = useState(0);
  const [metasDepositedTotal, setMetasDepositedTotal] = useState(0);
  const [availableForGoals, setAvailableForGoals] = useState(0);

  async function loadData() {
    const [g, h, totals] = await Promise.all([
      api.listGoals(),
      api.listTransfers(),
      fetchGoalPoolTotals(periodId),
    ]);
    setGoals(g);
    setGoalId((prev) => prev || g[0]?.id || "");
    setHistory(h);
    setMetasPoolTotal(totals.poolTotal);
    setMetasDepositedTotal(totals.depositedTotal);
    setAvailableForGoals(totals.available);
  }

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        await loadData();
      } catch (e) {
        if (!c) setError(e instanceof Error ? e.message : "Erro");
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!goalId) {
      setError("Crie uma meta primeiro.");
      return;
    }
    const transferValue = parseDecimal(valor.replace(",", "."));
    if (transferValue <= 0) {
      setError("Informe um valor válido para transferir.");
      return;
    }
    if (transferValue - availableForGoals > 0.001) {
      setError(
        `Saldo insuficiente para dividir nas metas. Disponível acumulado: ${formatBRL(availableForGoals)}.`,
      );
      return;
    }
    setError("");
    try {
      await api.createTransfer({
        source_type: "balance",
        source_id: undefined,
        destination_type: "goal",
        destination_id: goalId,
        valor: valor.replace(",", "."),
        data,
      });
      setValor("");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    }
  }

  return (
    <div className="padded narrow">
      <h1>Transferir para meta</h1>
      <p className="muted">
        Registra uma transferência do saldo das despesas fixas de metas para um cofre/meta.
      </p>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <h2>Dashboard de distribuição</h2>
        <p className="muted small" style={{ marginTop: 0 }}>
          Competência do mês selecionado
        </p>
        <div className="grid-kpis" style={{ marginBottom: 0 }}>
          <div className="kpi">
            <div className={`val ${availableForGoals < 0 ? "negative" : "positive"}`}>
              {formatBRL(availableForGoals)}
            </div>
            <div className="lbl">Disponível para dividir</div>
          </div>
          <div className="kpi">
            <div className="val">{formatBRL(metasPoolTotal)}</div>
            <div className="lbl">Lançado em despesas fixas (Metas)</div>
          </div>
          <div className="kpi">
            <div className="val">{formatBRL(metasDepositedTotal)}</div>
            <div className="lbl">Depositado nos cofres das metas</div>
          </div>
        </div>
      </div>
      {goals.length === 0 && (
        <p className="muted">Crie uma meta em Metas antes de transferir.</p>
      )}
      <div className="card">
        <form onSubmit={onSubmit} className="stack-form">
          <div className="field">
            <label>Meta destino</label>
            <select value={goalId} onChange={(e) => setGoalId(e.target.value)}>
              {goals.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.nome}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Valor</label>
            <input value={valor} onChange={(e) => setValor(e.target.value)} required />
          </div>
          <div className="field">
            <label>Data</label>
            <input type="date" value={data} onChange={(e) => setData(e.target.value)} />
          </div>
          <button type="submit" className="btn" disabled={goals.length === 0}>
            Transferir
          </button>
        </form>
      </div>
      <div className="card">
        <h2>Últimas transferências</h2>
        {history.length === 0 ? (
          <p className="muted">Nenhuma transferência registrada.</p>
        ) : (
          <>
            <ul className="card-tx-list card-lancamentos-mobile-only" aria-label="Transferências">
              {history.slice(0, 20).map((t) => (
                <li key={t.id} className="card-tx-item">
                  <div className="card-tx-item-main">
                    <span className="card-tx-desc">
                      {t.destination_type} {t.destination_id?.slice(0, 8)}…
                    </span>
                    <span className="card-tx-val">{formatBRL(t.valor)}</span>
                  </div>
                  <p className="muted small" style={{ margin: "0.25rem 0 0" }}>
                    {t.data}
                  </p>
                </li>
              ))}
            </ul>
            <div className="card-lancamentos-desktop-only table-scroll-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Data</th>
                    <th>Valor</th>
                    <th>Destino</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 20).map((t) => (
                    <tr key={t.id}>
                      <td>{t.data}</td>
                      <td>{formatBRL(t.valor)}</td>
                      <td>
                        {t.destination_type} {t.destination_id?.slice(0, 8)}…
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
