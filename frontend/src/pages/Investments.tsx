import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useAppDialog } from "../context/DialogContext";
import { formatBRL } from "../money";
import type { InvestmentRow, InvestmentTipo, ListedAssetRow } from "../types";
import {
  InvestmentCarousel,
  InvestmentsDividends,
  InvestmentsOverview,
  InvestmentsRebalance,
  InvestmentTabs,
  type InvestmentTab,
} from "./investments/InvestmentDashboard";

/** Ordem fixa de exibição: RF, Ação, FIIs, Cripto */
const ASSET_ORDER: InvestmentTipo[] = ["renda_fixa", "stock", "fii", "crypto"];

const TIPO_LABEL: Record<InvestmentTipo, string> = {
  renda_fixa: "Renda Fixa",
  stock: "Ação",
  fii: "FIIs",
  crypto: "Cripto",
};

function normalizeTipo(raw: string): InvestmentTipo {
  if (raw === "other") return "renda_fixa";
  return raw as InvestmentTipo;
}

function parseMoney(value: string | number): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : NaN;
  const n = parseFloat(String(value).replace(",", "."));
  return Number.isFinite(n) ? n : NaN;
}

function variationParts(aplicadoStr: string, atualStr: string): { pct: number | null; delta: number | null } {
  const aplicado = parseMoney(aplicadoStr);
  const atual = parseMoney(atualStr);
  if (!Number.isFinite(aplicado) || aplicado <= 0 || !Number.isFinite(atual)) return { pct: null, delta: null };
  const delta = atual - aplicado;
  const pct = (delta / aplicado) * 100;
  return { pct, delta };
}

function formatBRLInputDisplay(raw: string): string {
  return raw.replace(".", ",");
}

function formatCotasDisplay(raw: string | null | undefined): string {
  if (raw == null || raw === "") return "—";
  const n = parseFloat(String(raw));
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("pt-BR", { maximumFractionDigits: 8 });
}

function formatUnitBRL(raw: string | null | undefined): string {
  if (raw == null || raw === "") return "—";
  return formatBRL(raw);
}

type SortKey = "valor_atual_desc" | "valor_atual_asc" | "descricao";

export function Investments() {
  const { confirm } = useAppDialog();
  const [catalog, setCatalog] = useState<ListedAssetRow[]>([]);
  const [rows, setRows] = useState<InvestmentRow[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [initialLoading, setInitialLoading] = useState(true);
  const [submittingAdd, setSubmittingAdd] = useState(false);
  const [submittingEdit, setSubmittingEdit] = useState(false);
  const [activeTab, setActiveTab] = useState<InvestmentTab>("overview");

  const [selectedCatalogId, setSelectedCatalogId] = useState("");
  const [descricao, setDescricao] = useState("");
  const [tipo, setTipo] = useState<InvestmentTipo>("renda_fixa");
  const [valorAplicado, setValorAplicado] = useState("");
  const [valorAtual, setValorAtual] = useState("");
  const [quantidade, setQuantidade] = useState("");
  const [precoMedio, setPrecoMedio] = useState("");
  const [precoUnitarioAtual, setPrecoUnitarioAtual] = useState("");

  const [tipoFilter, setTipoFilter] = useState<"all" | InvestmentTipo>("all");
  const [sortBy, setSortBy] = useState<SortKey>("valor_atual_desc");

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editListedAssetId, setEditListedAssetId] = useState("");
  const [editDescricao, setEditDescricao] = useState("");
  const [editTipo, setEditTipo] = useState<InvestmentTipo>("renda_fixa");
  const [editValorAplicado, setEditValorAplicado] = useState("");
  const [editValorAtual, setEditValorAtual] = useState("");
  const [editQuantidade, setEditQuantidade] = useState("");
  const [editPrecoMedio, setEditPrecoMedio] = useState("");
  const [editPrecoUnitarioAtual, setEditPrecoUnitarioAtual] = useState("");

  const fiiPreview = useMemo(() => {
    const q = parseMoney(quantidade.replace(",", "."));
    const pm = parseMoney(precoMedio.replace(",", "."));
    const pu = parseMoney(precoUnitarioAtual.replace(",", "."));
    if (!Number.isFinite(q) || !Number.isFinite(pm) || !Number.isFinite(pu) || q <= 0) return null;
    return { aplicado: q * pm, posicao: q * pu };
  }, [quantidade, precoMedio, precoUnitarioAtual]);

  const editFiiPreview = useMemo(() => {
    if (!editingId || editTipo !== "fii") return null;
    const q = parseMoney(editQuantidade.replace(",", "."));
    const pm = parseMoney(editPrecoMedio.replace(",", "."));
    const pu = parseMoney(editPrecoUnitarioAtual.replace(",", "."));
    if (!Number.isFinite(q) || !Number.isFinite(pm) || !Number.isFinite(pu) || q <= 0) return null;
    return { aplicado: q * pm, posicao: q * pu };
  }, [editingId, editTipo, editQuantidade, editPrecoMedio, editPrecoUnitarioAtual]);

  const catalogForTipo = useMemo(
    () => catalog.filter((a) => normalizeTipo(String(a.tipo)) === tipo),
    [catalog, tipo],
  );

  const editCatalogForTipo = useMemo(
    () => catalog.filter((a) => normalizeTipo(String(a.tipo)) === editTipo),
    [catalog, editTipo],
  );

  async function refresh() {
    const [cat, list, t] = await Promise.all([
      api.listInvestmentCatalog(),
      api.listInvestments(),
      api.investmentsTotal(),
    ]);
    setCatalog(cat.map((a) => ({ ...a, tipo: normalizeTipo(String(a.tipo)) })));
    setRows(
      list.map((r) => ({
        ...r,
        tipo: normalizeTipo(String(r.tipo)),
        listed_asset_id: r.listed_asset_id ?? null,
        quantidade: r.quantidade ?? null,
        preco_medio: r.preco_medio ?? null,
        preco_unitario_atual: r.preco_unitario_atual ?? null,
      })),
    );
    setTotal(t.total_valor_atual);
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setInitialLoading(true);
      setError("");
      try {
        await refresh();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Erro");
      } finally {
        if (!cancelled) setInitialLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredSorted = useMemo(() => {
    let list = tipoFilter === "all" ? [...rows] : rows.filter((r) => r.tipo === tipoFilter);
    list.sort((a, b) => {
      if (sortBy === "descricao") {
        return a.descricao.localeCompare(b.descricao, "pt-BR");
      }
      const va = parseMoney(a.valor_atual);
      const vb = parseMoney(b.valor_atual);
      const na = Number.isFinite(va) ? va : 0;
      const nb = Number.isFinite(vb) ? vb : 0;
      return sortBy === "valor_atual_desc" ? nb - na : na - nb;
    });
    return list;
  }, [rows, tipoFilter, sortBy]);

  const portfolioSum = useMemo(() => {
    return rows.reduce((acc, r) => {
      const v = parseMoney(r.valor_atual);
      return acc + (Number.isFinite(v) ? v : 0);
    }, 0);
  }, [rows]);

  const totalsByTipo = useMemo(() => {
    const init: Record<InvestmentTipo, number> = {
      renda_fixa: 0,
      stock: 0,
      fii: 0,
      crypto: 0,
    };
    for (const r of rows) {
      const tt = normalizeTipo(String(r.tipo));
      const v = parseMoney(r.valor_atual);
      if (Number.isFinite(v)) init[tt] += v;
    }
    return init;
  }, [rows]);

  const rowsByTipo = useMemo(() => {
    const m: Record<InvestmentTipo, InvestmentRow[]> = {
      renda_fixa: [],
      stock: [],
      fii: [],
      crypto: [],
    };
    for (const r of filteredSorted) {
      const tt = normalizeTipo(String(r.tipo));
      m[tt].push({ ...r, tipo: tt });
    }
    return m;
  }, [filteredSorted]);

  function onSelectCatalogForNew(id: string) {
    setSelectedCatalogId(id);
    if (!id) return;
    const a = catalog.find((x) => x.id === id);
    if (a) {
      const nt = normalizeTipo(String(a.tipo));
      setTipo(nt);
      setDescricao(`${a.codigo} — ${a.nome}`);
    }
  }

  function onTipoChangeNew(next: InvestmentTipo) {
    setTipo(next);
    setSelectedCatalogId("");
    if (next !== "fii") {
      setQuantidade("");
      setPrecoMedio("");
      setPrecoUnitarioAtual("");
    }
  }

  function startEdit(r: InvestmentRow) {
    setEditingId(r.id);
    setEditListedAssetId(r.listed_asset_id ?? "");
    setEditDescricao(r.descricao);
    setEditTipo(normalizeTipo(String(r.tipo)));
    setEditValorAplicado(formatBRLInputDisplay(String(r.valor_aplicado)));
    setEditValorAtual(formatBRLInputDisplay(String(r.valor_atual)));
    setEditQuantidade(r.quantidade != null ? formatBRLInputDisplay(String(r.quantidade)) : "");
    setEditPrecoMedio(r.preco_medio != null ? formatBRLInputDisplay(String(r.preco_medio)) : "");
    setEditPrecoUnitarioAtual(r.preco_unitario_atual != null ? formatBRLInputDisplay(String(r.preco_unitario_atual)) : "");
  }

  function cancelEdit() {
    setEditingId(null);
  }

  function onSelectCatalogForEdit(id: string) {
    setEditListedAssetId(id);
    if (!id) return;
    const a = catalog.find((x) => x.id === id);
    if (a) {
      const nt = normalizeTipo(String(a.tipo));
      setEditTipo(nt);
      setEditDescricao(`${a.codigo} — ${a.nome}`);
    }
  }

  async function onAdd(e: React.FormEvent) {
    e.preventDefault();
    setSubmittingAdd(true);
    setError("");
    try {
      if (tipo === "fii") {
        const q = quantidade.replace(",", ".").trim();
        const pm = precoMedio.replace(",", ".").trim();
        const pu = precoUnitarioAtual.replace(",", ".").trim();
        if (!q || !pm || !pu) {
          setError("Para FII, informe cotas compradas, preço médio e preço atual (por cota).");
          setSubmittingAdd(false);
          return;
        }
        const base = {
          quantidade: q,
          preco_medio: pm,
          preco_unitario_atual: pu,
          valor_aplicado: "0",
          valor_atual: "0",
        };
        if (selectedCatalogId) {
          await api.createInvestment({ ...base, listed_asset_id: selectedCatalogId });
        } else {
          await api.createInvestment({ ...base, descricao, tipo: "fii" });
        }
      } else if (selectedCatalogId) {
        await api.createInvestment({
          listed_asset_id: selectedCatalogId,
          valor_aplicado: valorAplicado.replace(",", "."),
          valor_atual: valorAtual.replace(",", "."),
        });
      } else {
        await api.createInvestment({
          descricao,
          tipo,
          valor_aplicado: valorAplicado.replace(",", "."),
          valor_atual: valorAtual.replace(",", "."),
        });
      }
      setDescricao("");
      setSelectedCatalogId("");
      setValorAplicado("");
      setValorAtual("");
      setQuantidade("");
      setPrecoMedio("");
      setPrecoUnitarioAtual("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setSubmittingAdd(false);
    }
  }

  async function onSaveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editingId) return;
    setSubmittingEdit(true);
    setError("");
    try {
      const va = editValorAplicado.replace(",", ".").trim();
      const vu = editValorAtual.replace(",", ".").trim();
      const q = editQuantidade.replace(",", ".").trim();
      const pm = editPrecoMedio.replace(",", ".").trim();
      const pu = editPrecoUnitarioAtual.replace(",", ".").trim();
      const useFiiDetail = editTipo === "fii" && q && pm && pu;

      const patch: Parameters<typeof api.updateInvestment>[1] = {};
      if (editListedAssetId) {
        patch.listed_asset_id = editListedAssetId;
      } else {
        patch.listed_asset_id = null;
        patch.descricao = editDescricao;
        patch.tipo = editTipo;
      }

      if (useFiiDetail) {
        patch.quantidade = q;
        patch.preco_medio = pm;
        patch.preco_unitario_atual = pu;
      } else {
        patch.valor_aplicado = va;
        patch.valor_atual = vu;
      }

      await api.updateInvestment(editingId, patch);
      setEditingId(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setSubmittingEdit(false);
    }
  }

  async function onDelete(id: string) {
    const ok = await confirm({
      title: "Remover posição",
      message: "Remover esta posição?",
      confirmLabel: "Remover",
      danger: true,
    });
    if (!ok) return;
    setError("");
    try {
      await api.deleteInvestment(id);
      if (editingId === id) setEditingId(null);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
    }
  }

  const tipoOptions = ASSET_ORDER.map((value) => (
    <option key={value} value={value}>
      {TIPO_LABEL[value]}
    </option>
  ));

  const catalogSelectNew = (
    <select
      value={selectedCatalogId}
      onChange={(e) => onSelectCatalogForNew(e.target.value)}
      disabled={editingId !== null}
      style={{ minWidth: 220 }}
      aria-label="Ativo do cadastro"
    >
      <option value="">Descrição livre (sem cadastro)</option>
      {catalogForTipo.map((a) => (
        <option key={a.id} value={a.id}>
          {a.codigo} — {a.nome}
        </option>
      ))}
    </select>
  );

  return (
    <div className="padded investments-page">
      <div className="inv-page-heading">
        <div>
          <span className="inv-eyebrow">Patrimônio e estratégia</span>
          <h1>Carteira de investimentos</h1>
          <p>Acompanhe sua alocação, posições e próximos movimentos em um só lugar.</p>
        </div>
        <span className="inv-demo-badge">Prévia com dados demonstrativos</span>
      </div>
      {error && <p className="error">{error}</p>}

      <InvestmentTabs active={activeTab} onChange={setActiveTab} />
      <InvestmentCarousel />

      {activeTab === "overview" && !initialLoading && (
        <InvestmentsOverview
          rows={rows}
          onOpenAssets={() => setActiveTab("assets")}
          onOpenRebalance={() => setActiveTab("rebalance")}
        />
      )}
      {activeTab === "rebalance" && !initialLoading && <InvestmentsRebalance rows={rows} />}
      {activeTab === "dividends" && !initialLoading && <InvestmentsDividends />}

      {initialLoading ? (
        <p className="muted">Carregando…</p>
      ) : activeTab === "assets" ? (
        <>
          {total !== null && (
            <div className="card">
              <p className="muted" style={{ margin: 0 }}>
                Patrimônio investido (valor atual)
              </p>
              <p style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.25rem 0 0" }}>{formatBRL(total)}</p>
            </div>
          )}

          {rows.length > 0 && (
            <div className="card">
              <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Por classe de ativo</h2>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
                  gap: "0.75rem",
                }}
              >
                {ASSET_ORDER.map((t) => {
                  const sub = totalsByTipo[t];
                  const pct = portfolioSum > 0 ? (sub / portfolioSum) * 100 : 0;
                  return (
                    <div
                      key={t}
                      style={{
                        padding: "0.55rem 0.7rem",
                        border: "1px solid color-mix(in srgb, var(--accent) 14%, var(--surface2))",
                        borderRadius: 10,
                        background: "color-mix(in srgb, var(--accent) 6%, var(--surface))",
                      }}
                    >
                      <div className="muted" style={{ fontSize: "0.72rem", letterSpacing: "0.04em" }}>
                        {TIPO_LABEL[t]}
                      </div>
                      <div style={{ fontWeight: 700, fontSize: "1.05rem", marginTop: 2 }}>{formatBRL(sub)}</div>
                      <div className="muted" style={{ fontSize: "0.8rem" }}>
                        {portfolioSum > 0 ? `${pct.toFixed(1)}% do total` : "—"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="card">
            <h2>Nova posição</h2>
            <form onSubmit={onAdd} className="inline-form" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
              <label className="muted" style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.85rem" }}>
                Classe
                <select
                  value={tipo}
                  onChange={(e) => onTipoChangeNew(e.target.value as InvestmentTipo)}
                  disabled={editingId !== null}
                >
                  {tipoOptions}
                </select>
              </label>
              <label className="muted" style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.85rem" }}>
                Ativo (cadastro)
                {catalogSelectNew}
              </label>
              <input
                placeholder="Descrição (obrigatória se não usar cadastro)"
                value={descricao}
                onChange={(e) => setDescricao(e.target.value)}
                required={!selectedCatalogId}
                disabled={editingId !== null || !!selectedCatalogId}
                style={{ minWidth: 180 }}
              />
              {tipo === "fii" ? (
                <>
                  <label className="muted" style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.85rem" }}>
                    Cotas (quantidade)
                    <input
                      inputMode="decimal"
                      placeholder="Ex.: 100"
                      value={quantidade}
                      onChange={(e) => setQuantidade(e.target.value)}
                      disabled={editingId !== null}
                      required
                    />
                  </label>
                  <label className="muted" style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.85rem" }}>
                    Preço médio (R$/cota)
                    <input
                      inputMode="decimal"
                      placeholder="Custo médio por cota"
                      value={precoMedio}
                      onChange={(e) => setPrecoMedio(e.target.value)}
                      disabled={editingId !== null}
                      required
                    />
                  </label>
                  <label className="muted" style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.85rem" }}>
                    Preço atual (R$/cota)
                    <input
                      inputMode="decimal"
                      placeholder="Cotação atual"
                      value={precoUnitarioAtual}
                      onChange={(e) => setPrecoUnitarioAtual(e.target.value)}
                      disabled={editingId !== null}
                      required
                    />
                  </label>
                  {fiiPreview && (
                    <p className="muted" style={{ flexBasis: "100%", margin: "0.15rem 0 0", fontSize: "0.88rem" }}>
                      Total aplicado: <strong>{formatBRL(fiiPreview.aplicado)}</strong> · Posição (valor atual):{" "}
                      <strong>{formatBRL(fiiPreview.posicao)}</strong>
                    </p>
                  )}
                </>
              ) : (
                <>
                  <input
                    placeholder="Valor aplicado"
                    inputMode="decimal"
                    value={valorAplicado}
                    onChange={(e) => setValorAplicado(e.target.value)}
                    disabled={editingId !== null}
                  />
                  <input
                    placeholder="Valor atual"
                    inputMode="decimal"
                    value={valorAtual}
                    onChange={(e) => setValorAtual(e.target.value)}
                    required
                    disabled={editingId !== null}
                  />
                </>
              )}
              <button type="submit" className="btn" disabled={submittingAdd || editingId !== null}>
                {submittingAdd ? "Salvando…" : "Adicionar"}
              </button>
            </form>
          </div>

          <div className="card">
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "0.75rem",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "0.75rem",
              }}
            >
              <h2 style={{ margin: 0 }}>Posições</h2>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
                <label className="muted" style={{ fontSize: "0.85rem" }}>
                  Tipo{" "}
                  <select
                    value={tipoFilter}
                    onChange={(e) => setTipoFilter(e.target.value as typeof tipoFilter)}
                    style={{ marginLeft: 4 }}
                    disabled={editingId !== null}
                  >
                    <option value="all">Todos</option>
                    {tipoOptions}
                  </select>
                </label>
                <label className="muted" style={{ fontSize: "0.85rem" }}>
                  Ordenar{" "}
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as SortKey)}
                    style={{ marginLeft: 4 }}
                    disabled={editingId !== null}
                  >
                    <option value="valor_atual_desc">Valor atual (maior)</option>
                    <option value="valor_atual_asc">Valor atual (menor)</option>
                    <option value="descricao">Descrição (A–Z)</option>
                  </select>
                </label>
              </div>
            </div>

            {rows.length === 0 ? (
              <p className="muted">Nenhuma posição cadastrada.</p>
            ) : filteredSorted.length === 0 ? (
              <p className="muted">Nenhuma posição neste filtro.</p>
            ) : (
              <form onSubmit={onSaveEdit}>
                {ASSET_ORDER.map((tipoKey) => {
                  const sectionRows = rowsByTipo[tipoKey];
                  if (sectionRows.length === 0) return null;
                  const sectionSubtotal = sectionRows.reduce((acc, r) => {
                    const v = parseMoney(r.valor_atual);
                    return acc + (Number.isFinite(v) ? v : 0);
                  }, 0);
                  const isFiiSection = tipoKey === "fii";

                  return (
                    <details className="inv-asset-group" key={tipoKey} open>
                      <summary>
                        <span>{TIPO_LABEL[tipoKey]}</span>
                        <span>{sectionRows.length} {sectionRows.length === 1 ? "ativo" : "ativos"} · {formatBRL(sectionSubtotal)}</span>
                      </summary>
                      <div className="inv-table-wrap">
                      <table className="inv-assets-table">
                        <thead>
                          <tr>
                            {isFiiSection ? (
                              <>
                                <th>Descrição</th>
                                <th>Cotas</th>
                                <th>P. médio</th>
                                <th>P. atual</th>
                                <th>Total aplicado</th>
                                <th>Posição</th>
                                <th>Variação</th>
                                <th />
                              </>
                            ) : (
                              <>
                                <th>Descrição</th>
                                <th>Aplicado</th>
                                <th>Atual</th>
                                <th>Variação</th>
                                <th />
                              </>
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {sectionRows.map((r) => {
                            const descCell = (
                              <>
                                <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4 }}>
                                  Cadastro
                                </label>
                                <select
                                  value={editListedAssetId}
                                  onChange={(e) => onSelectCatalogForEdit(e.target.value)}
                                  style={{ width: "100%", maxWidth: 280, marginBottom: 8 }}
                                >
                                  <option value="">Descrição livre</option>
                                  {editCatalogForTipo.map((a) => (
                                    <option key={a.id} value={a.id}>
                                      {a.codigo} — {a.nome}
                                    </option>
                                  ))}
                                </select>
                                <input
                                  value={editDescricao}
                                  onChange={(e) => setEditDescricao(e.target.value)}
                                  required={!editListedAssetId}
                                  disabled={!!editListedAssetId}
                                  style={{ width: "100%", minWidth: 120 }}
                                />
                                <select
                                  value={editTipo}
                                  onChange={(e) => {
                                    const nt = e.target.value as InvestmentTipo;
                                    setEditTipo(nt);
                                    setEditListedAssetId("");
                                    if (nt !== "fii") {
                                      setEditQuantidade("");
                                      setEditPrecoMedio("");
                                      setEditPrecoUnitarioAtual("");
                                    }
                                  }}
                                  style={{ marginTop: 6, width: "100%", maxWidth: 200 }}
                                >
                                  {tipoOptions}
                                </select>
                              </>
                            );

                            const actionCell = (
                              <>
                                <button type="submit" className="btn btn-sm" disabled={submittingEdit}>
                                  {submittingEdit ? "…" : "Salvar"}
                                </button>{" "}
                                <button
                                  type="button"
                                  className="btn btn-ghost btn-sm"
                                  onClick={cancelEdit}
                                  disabled={submittingEdit}
                                >
                                  Cancelar
                                </button>
                              </>
                            );

                            if (editingId === r.id) {
                              if (isFiiSection) {
                                return (
                                  <tr key={r.id}>
                                    <td>{descCell}</td>
                                    <td>
                                      <input
                                        inputMode="decimal"
                                        value={editQuantidade}
                                        onChange={(e) => setEditQuantidade(e.target.value)}
                                        style={{ maxWidth: 96 }}
                                      />
                                    </td>
                                    <td>
                                      <input
                                        inputMode="decimal"
                                        value={editPrecoMedio}
                                        onChange={(e) => setEditPrecoMedio(e.target.value)}
                                        style={{ maxWidth: 96 }}
                                      />
                                    </td>
                                    <td>
                                      <input
                                        inputMode="decimal"
                                        value={editPrecoUnitarioAtual}
                                        onChange={(e) => setEditPrecoUnitarioAtual(e.target.value)}
                                        style={{ maxWidth: 96 }}
                                      />
                                    </td>
                                    <td>{editFiiPreview ? formatBRL(editFiiPreview.aplicado) : formatBRL(editValorAplicado)}</td>
                                    <td>{editFiiPreview ? formatBRL(editFiiPreview.posicao) : formatBRL(editValorAtual)}</td>
                                    <td className="muted">—</td>
                                    <td>{actionCell}</td>
                                  </tr>
                                );
                              }
                              return (
                                <tr key={r.id}>
                                  <td>{descCell}</td>
                                  <td>
                                    <input
                                      inputMode="decimal"
                                      value={editValorAplicado}
                                      onChange={(e) => setEditValorAplicado(e.target.value)}
                                      style={{ maxWidth: 110 }}
                                    />
                                  </td>
                                  <td>
                                    <input
                                      inputMode="decimal"
                                      value={editValorAtual}
                                      onChange={(e) => setEditValorAtual(e.target.value)}
                                      required
                                      style={{ maxWidth: 110 }}
                                    />
                                  </td>
                                  <td className="muted">—</td>
                                  <td>{actionCell}</td>
                                </tr>
                              );
                            }

                            const { pct, delta } = variationParts(r.valor_aplicado, r.valor_atual);
                            const deltaCls =
                              delta == null ? "" : delta > 0 ? "positive" : delta < 0 ? "negative" : "";

                            if (isFiiSection) {
                              return (
                                <tr key={r.id}>
                                  <td>{r.descricao}</td>
                                  <td>{formatCotasDisplay(r.quantidade)}</td>
                                  <td>{formatUnitBRL(r.preco_medio)}</td>
                                  <td>{formatUnitBRL(r.preco_unitario_atual)}</td>
                                  <td>{formatBRL(r.valor_aplicado)}</td>
                                  <td>{formatBRL(r.valor_atual)}</td>
                                  <td>
                                    {pct != null && delta != null ? (
                                      <>
                                        <span className={deltaCls} style={{ fontWeight: 600 }}>
                                          {delta >= 0 ? "+" : ""}
                                          {formatBRL(delta)}
                                        </span>
                                        <span className="muted" style={{ marginLeft: 6, fontSize: "0.85rem" }}>
                                          ({pct >= 0 ? "+" : ""}
                                          {pct.toFixed(1)}%)
                                        </span>
                                      </>
                                    ) : (
                                      <span className="muted">—</span>
                                    )}
                                  </td>
                                  <td>
                                    <button
                                      type="button"
                                      className="btn btn-ghost btn-sm"
                                      onClick={() => startEdit(r)}
                                      disabled={editingId !== null}
                                    >
                                      Editar
                                    </button>{" "}
                                    <button
                                      type="button"
                                      className="btn btn-ghost btn-sm"
                                      onClick={() => onDelete(r.id)}
                                      disabled={editingId !== null}
                                    >
                                      Excluir
                                    </button>
                                  </td>
                                </tr>
                              );
                            }

                            return (
                              <tr key={r.id}>
                                <td>{r.descricao}</td>
                                <td>{formatBRL(r.valor_aplicado)}</td>
                                <td>{formatBRL(r.valor_atual)}</td>
                                <td>
                                  {pct != null && delta != null ? (
                                    <>
                                      <span className={deltaCls} style={{ fontWeight: 600 }}>
                                        {delta >= 0 ? "+" : ""}
                                        {formatBRL(delta)}
                                      </span>
                                      <span className="muted" style={{ marginLeft: 6, fontSize: "0.85rem" }}>
                                        ({pct >= 0 ? "+" : ""}
                                        {pct.toFixed(1)}%)
                                      </span>
                                    </>
                                  ) : (
                                    <span className="muted">—</span>
                                  )}
                                </td>
                                <td>
                                  <button
                                    type="button"
                                    className="btn btn-ghost btn-sm"
                                    onClick={() => startEdit(r)}
                                    disabled={editingId !== null}
                                  >
                                    Editar
                                  </button>{" "}
                                  <button
                                    type="button"
                                    className="btn btn-ghost btn-sm"
                                    onClick={() => onDelete(r.id)}
                                    disabled={editingId !== null}
                                  >
                                    Excluir
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                          <tr className="muted">
                            {isFiiSection ? (
                              <>
                                <td colSpan={5} style={{ textAlign: "right", fontWeight: 600, paddingTop: "0.5rem" }}>
                                  Subtotal ({TIPO_LABEL[tipoKey]}) — posição (valor atual)
                                </td>
                                <td style={{ fontWeight: 700, paddingTop: "0.5rem" }}>{formatBRL(sectionSubtotal)}</td>
                                <td colSpan={2} style={{ paddingTop: "0.5rem" }} />
                              </>
                            ) : (
                              <>
                                <td colSpan={2} style={{ textAlign: "right", fontWeight: 600, paddingTop: "0.5rem" }}>
                                  Subtotal ({TIPO_LABEL[tipoKey]}) — valor atual
                                </td>
                                <td style={{ fontWeight: 700, paddingTop: "0.5rem" }}>{formatBRL(sectionSubtotal)}</td>
                                <td colSpan={2} style={{ paddingTop: "0.5rem" }} />
                              </>
                            )}
                          </tr>
                        </tbody>
                      </table>
                      </div>
                    </details>
                  );
                })}
              </form>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
