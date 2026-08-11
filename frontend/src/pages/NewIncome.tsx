import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Category } from "../types";
import { usePeriod } from "../context/PeriodContext";

export function NewIncome() {
  const nav = useNavigate();
  const { periodId, setPeriodId, periods, ready } = usePeriod();
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoriaId, setCategoriaId] = useState("");
  const [descricao, setDescricao] = useState("");
  const [valor, setValor] = useState("");
  const [data, setData] = useState(() => new Date().toISOString().slice(0, 10));
  const [recorrente, setRecorrente] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const cats = await api.categories("income");
        if (!c) {
          setCategories(cats);
          setCategoriaId((prev) => prev || cats[0]?.id || "");
        }
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
    if (!periodId || !categoriaId) {
      setError("Período e categoria obrigatórios.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.createIncome({
        descricao,
        valor: valor.replace(",", "."),
        data,
        period_id: periodId,
        categoria_id: categoriaId,
        recorrente,
      });
      nav("/receitas");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  }

  function onGoBack() {
    if (window.history.length > 1) {
      nav(-1);
      return;
    }
    nav("/receitas");
  }

  if (!ready) return null;

  return (
    <div className="padded narrow">
      <div className="page-head">
        <h1>Nova receita</h1>
        <button type="button" className="btn btn-ghost" onClick={() => onGoBack()}>
          Voltar
        </button>
      </div>
      <div className="card">
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="p">Período</label>
            <select
              id="p"
              value={periodId}
              onChange={(e) => setPeriodId(e.target.value)}
              required
            >
              {periods.map((p) => (
                <option key={p.id} value={p.id}>
                  {String(p.mes).padStart(2, "0")}/{p.ano}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="cat">Categoria</label>
            <select
              id="cat"
              value={categoriaId}
              onChange={(e) => setCategoriaId(e.target.value)}
              required
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="d">Descrição</label>
            <input id="d" value={descricao} onChange={(e) => setDescricao(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="v">Valor (R$)</label>
            <input
              id="v"
              inputMode="decimal"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="dt">Data</label>
            <input id="dt" type="date" value={data} onChange={(e) => setData(e.target.value)} required />
          </div>
          <div className="field">
            <label>
              <input
                type="checkbox"
                checked={recorrente}
                onChange={(e) => setRecorrente(e.target.checked)}
              />{" "}
              Recorrente (replica nos meses futuros já cadastrados)
            </label>
          </div>
          {error && <p className="error">{error}</p>}
          <button type="submit" className="btn" disabled={saving}>
            {saving ? "Salvando…" : "Salvar"}
          </button>
        </form>
      </div>
    </div>
  );
}
