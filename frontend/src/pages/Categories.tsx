import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useAppDialog } from "../context/DialogContext";
import type { Category } from "../types";

type CategoryType = "expense" | "income";

export function Categories() {
  const { confirm } = useAppDialog();
  const [rows, setRows] = useState<Category[]>([]);
  const [nome, setNome] = useState("");
  const [tipo, setTipo] = useState<CategoryType>("expense");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    void loadCategories();
  }, []);

  const expenses = useMemo(() => rows.filter((r) => r.tipo === "expense"), [rows]);
  const incomes = useMemo(() => rows.filter((r) => r.tipo === "income"), [rows]);

  async function loadCategories() {
    setLoading(true);
    setError("");
    try {
      const [expenseRows, incomeRows] = await Promise.all([
        api.categories("expense"),
        api.categories("income"),
      ]);
      setRows([...expenseRows, ...incomeRows]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar categorias");
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!nome.trim()) {
      setError("Informe o nome da categoria.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.createCategory({ nome: nome.trim(), tipo });
      setNome("");
      await loadCategories();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao criar categoria");
    } finally {
      setSaving(false);
    }
  }

  async function onDelete(categoryId: string) {
    const ok = await confirm({
      title: "Excluir categoria",
      message: "Excluir esta categoria?",
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    setError("");
    try {
      await api.deleteCategory(categoryId);
      setRows((prev) => prev.filter((r) => r.id !== categoryId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao excluir categoria");
    }
  }

  return (
    <div className="padded">
      <div className="page-head">
        <h1>Categorias</h1>
      </div>

      <div className="card narrow" style={{ maxWidth: 640 }}>
        <h2>Nova categoria</h2>
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="tipo">Tipo</label>
            <select
              id="tipo"
              value={tipo}
              onChange={(e) => setTipo(e.target.value as CategoryType)}
              required
            >
              <option value="expense">Despesa</option>
              <option value="income">Receita</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="nome">Nome</label>
            <input
              id="nome"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              placeholder="Ex.: Moradia"
              required
            />
          </div>
          {error && <p className="error">{error}</p>}
          <button className="btn" type="submit" disabled={saving}>
            {saving ? "Salvando..." : "Criar categoria"}
          </button>
        </form>
      </div>

      <div className="card">
        <h2>Despesas</h2>
        <CategoryTable rows={expenses} loading={loading} onDelete={onDelete} />
      </div>

      <div className="card">
        <h2>Receitas</h2>
        <CategoryTable rows={incomes} loading={loading} onDelete={onDelete} />
      </div>
    </div>
  );
}

function CategoryTable({
  rows,
  loading,
  onDelete,
}: {
  rows: Category[];
  loading: boolean;
  onDelete: (categoryId: string) => Promise<void>;
}) {
  if (loading) return <p className="muted">Carregando...</p>;
  if (rows.length === 0) return <p className="muted">Nenhuma categoria cadastrada.</p>;

  return (
    <>
      <ul className="card-tx-list card-lancamentos-mobile-only" aria-label="Categorias">
        {rows.map((row) => (
          <li key={row.id} className="card-tx-item">
            <div className="card-tx-item-main">
              <span className="card-tx-desc">
                <span
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: "50%",
                    background: row.cor,
                    border: "1px solid var(--surface2)",
                    display: "inline-block",
                    marginRight: 8,
                    verticalAlign: "middle",
                  }}
                />
                {row.nome}
              </span>
            </div>
            <div className="card-tx-item-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => void onDelete(row.id)} type="button">
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
              <th>Categoria</th>
              <th>Cor</th>
              <th style={{ textAlign: "right" }}>Ações</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.nome}</td>
                <td>
                  <span
                    style={{
                      width: 14,
                      height: 14,
                      borderRadius: "50%",
                      background: row.cor,
                      border: "1px solid var(--surface2)",
                      display: "inline-block",
                      marginRight: 8,
                      verticalAlign: "middle",
                    }}
                  />
                  {row.cor}
                </td>
                <td style={{ textAlign: "right" }}>
                  <button className="btn btn-ghost btn-sm" onClick={() => void onDelete(row.id)} type="button">
                    Excluir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
