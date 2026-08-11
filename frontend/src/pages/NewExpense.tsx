import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { usePeriod } from "../context/PeriodContext";
import type { Category } from "../types";

export function NewExpense() {
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  const { periodId, setPeriodId, periods, ready, monthLabel, periodClosed } = usePeriod();

  const [categories, setCategories] = useState<Category[]>([]);
  const [categoriaId, setCategoriaId] = useState("");
  const [descricao, setDescricao] = useState("");
  const [valor, setValor] = useState("");
  const [data, setData] = useState(() => new Date().toISOString().slice(0, 10));
  const [tipo, setTipo] = useState<"fixed" | "variable" | "card">("variable");
  const [pago, setPago] = useState(false);
  const [recorrente, setRecorrente] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const q = searchParams.get("period");
    if (q && periods.some((p) => p.id === q)) setPeriodId(q);
  }, [searchParams, periods, setPeriodId]);

  useEffect(() => {
    const queryType = searchParams.get("tipo");
    if (queryType === "fixed" || queryType === "variable" || queryType === "card") {
      setTipo(queryType);
      if (queryType !== "fixed") setRecorrente(false);
    }
    const queryDescription = searchParams.get("descricao");
    if (queryDescription) setDescricao(queryDescription);
    const queryValue = searchParams.get("valor");
    if (queryValue) setValor(queryValue.replace(".", ","));
    const queryDate = searchParams.get("data");
    if (queryDate && /^\d{4}-\d{2}-\d{2}$/.test(queryDate)) setData(queryDate);
    const queryCategoryId = searchParams.get("categoria_id");
    if (queryCategoryId && categories.some((c) => c.id === queryCategoryId)) {
      setCategoriaId(queryCategoryId);
    }
  }, [searchParams, categories]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cats = await api.categories("expense");
        if (cancelled) return;
        setCategories(cats);
        setCategoriaId((prev) => prev || cats[0]?.id || "");
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Erro ao carregar");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!periodId || !categoriaId) {
      setError("Selecione período e categoria.");
      return;
    }
    setSaving(true);
    try {
      await api.createExpense({
        descricao,
        valor: valor.replace(",", "."),
        data,
        period_id: periodId,
        categoria_id: categoriaId,
        tipo,
        pago,
        recorrente: tipo === "fixed" && recorrente,
      });
      nav("/");
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
    nav("/");
  }

  if (!ready) {
    return (
      <div className="padded">
        <p className="muted">Carregando…</p>
      </div>
    );
  }

  return (
    <div className="narrow">
      <header className="page-head">
        <button type="button" className="btn btn-ghost" onClick={() => onGoBack()}>
          ← Voltar
        </button>
      </header>
      <div className="card">
        <h1>Nova despesa</h1>
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="period">Período</label>
            <select
              id="period"
              value={periodId}
              onChange={(e) => setPeriodId(e.target.value)}
              required
            >
              {periods.map((p) => (
                <option key={p.id} value={p.id}>
                  {monthLabel(p.mes, p.ano)}
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
              disabled={categories.length === 0}
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="desc">Descrição</label>
            <input
              id="desc"
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="valor">Valor (R$)</label>
            <input
              id="valor"
              inputMode="decimal"
              placeholder="0,00"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="data">Data</label>
            <input
              id="data"
              type="date"
              value={data}
              onChange={(e) => setData(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="tipo">Tipo</label>
            <select
              id="tipo"
              value={tipo}
              onChange={(e) => {
                const v = e.target.value as typeof tipo;
                setTipo(v);
                if (v !== "fixed") setRecorrente(false);
              }}
            >
              <option value="fixed">Fixa</option>
              <option value="variable">Variável</option>
              <option value="card">Cartão</option>
            </select>
          </div>
          <div className="field">
            <label>
              <input
                type="checkbox"
                checked={pago}
                onChange={(e) => setPago(e.target.checked)}
              />{" "}
              Já pago
            </label>
          </div>
          {tipo === "fixed" && (
            <div className="field">
              <label>
                <input
                  type="checkbox"
                  checked={recorrente}
                  onChange={(e) => setRecorrente(e.target.checked)}
                />{" "}
                Recorrente (replicar nos meses seguintes)
              </label>
            </div>
          )}
          {periodClosed && (
            <p className="error">Este mês está fechado. Reabra o período para lançar despesas.</p>
          )}
          {error && <p className="error">{error}</p>}
          <button
            type="submit"
            className="btn"
            disabled={saving || periodClosed}
            style={{ width: "100%" }}
          >
            {saving ? "Salvando…" : "Salvar despesa"}
          </button>
        </form>
      </div>
    </div>
  );
}
