import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAppDialog } from "../context/DialogContext";
import { usePeriod } from "../context/PeriodContext";
import { formatBRL } from "../money";

type IncomeRow = {
  id: string;
  descricao: string;
  valor: string;
  data: string;
  recorrente: boolean;
};

function formatDateBR(value: string): string {
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("pt-BR");
}

export function Incomes() {
  const { periodId, ready } = usePeriod();
  const { confirm, alert } = useAppDialog();
  const [rows, setRows] = useState<IncomeRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!ready || !periodId) return;
    let c = false;
    (async () => {
      try {
        const data = (await api.listIncomes(periodId)) as IncomeRow[];
        if (!c) setRows(data);
      } catch (e) {
        if (!c) setError(e instanceof Error ? e.message : "Erro");
      }
    })();
    return () => {
      c = true;
    };
  }, [periodId, ready]);

  async function remove(id: string) {
    const ok = await confirm({
      title: "Excluir receita",
      message: "Excluir esta receita?",
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.deleteIncome(id);
      setRows((r) => r.filter((x) => x.id !== id));
    } catch (e) {
      await alert(e instanceof Error ? e.message : "Erro");
    }
  }

  if (!ready) return null;

  return (
    <div className="padded">
      <div className="page-head">
        <h1>Receitas do período</h1>
        <Link to="/receitas/nova" className="btn">
          Nova receita
        </Link>
      </div>
      {error && <p className="error">{error}</p>}
      {rows.length === 0 ? (
        <p className="muted">Nenhuma receita lançada.</p>
      ) : (
        <div className="card">
          <ul className="card-tx-list card-lancamentos-mobile-only" aria-label="Receitas">
            {rows.map((r) => (
              <li key={r.id} className="card-tx-item">
                <div className="card-tx-item-main">
                  <span className="card-tx-desc">{r.descricao}</span>
                  <span className="card-tx-val">{formatBRL(r.valor)}</span>
                </div>
                <div className="card-tx-item-meta">
                  <span className="muted small">{formatDateBR(r.data)}</span>
                  <span className="muted small">{r.recorrente ? "Recorrente" : "Única"}</span>
                </div>
                <div className="card-tx-item-actions">
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => void remove(r.id)}>
                    Excluir
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <div className="card-lancamentos-desktop-only table-scroll-wrap">
            <table>
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Descrição</th>
                  <th>Valor</th>
                  <th>Recorrente</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{r.data}</td>
                    <td>{r.descricao}</td>
                    <td>{formatBRL(r.valor)}</td>
                    <td>{r.recorrente ? "Sim" : "Não"}</td>
                    <td>
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => void remove(r.id)}>
                        Excluir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
