import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { usePeriod } from "../context/PeriodContext";
import { formatBRL } from "../money";
import {
  IMPORT_PREVIEW_STORAGE_KEY,
  type ImportPreviewEditableRow,
  type ImportPreviewSession,
} from "../statementImportTypes";
import {
  PREVIEW_ROW_LIMIT,
  categoryEmoji,
  categoryNameById,
  formatDateBR,
  skipReasonLabel,
  updateKindLabel,
  valorToApi,
} from "../statementImportUtils";
import type { ImportPreviewStatus } from "../statementImportTypes";
import type { CardRow, Category } from "../types";

const VALID_STATUSES = new Set<ImportPreviewStatus>(["new", "kept", "updated", "skip", "orphan"]);

function statusLabel(row: ImportPreviewEditableRow): string {
  if (row.status === "new") return "➕ Novo";
  if (row.status === "kept") return "✓ Mantido";
  if (row.status === "updated") return "🔄 Atualizado";
  if (row.status === "orphan") return "🗑 Órfão";
  return "⊘ Ignorado";
}

function SummaryCard({
  tone,
  label,
  count,
  desc,
}: {
  tone: "new" | "kept" | "updated" | "skip" | "orphan";
  label: string;
  count: number;
  desc: string;
}) {
  return (
    <div className={`ip-sum-card ip-sum-card--${tone}`}>
      <div className="ip-sum-lbl">{label}</div>
      <div className="ip-sum-num">{count}</div>
      <div className="ip-sum-desc">{desc}</div>
    </div>
  );
}

export function CardImportPreview() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { periods, monthLabel, periodClosed, setPeriodId } = usePeriod();

  const [card, setCard] = useState<CardRow | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [session, setSession] = useState<ImportPreviewSession | null>(null);
  const [rows, setRows] = useState<ImportPreviewEditableRow[]>([]);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [showNew, setShowNew] = useState(true);
  const [showUpdated, setShowUpdated] = useState(true);
  const [showKept, setShowKept] = useState(false);
  const [showSkip, setShowSkip] = useState(false);
  const [showOrphan, setShowOrphan] = useState(true);
  const [expandNew, setExpandNew] = useState(false);
  const [expandUpdated, setExpandUpdated] = useState(false);
  const [expandKept, setExpandKept] = useState(false);
  const [expandOrphan, setExpandOrphan] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const periodId = searchParams.get("periodId") ?? session?.periodId ?? "";

  useEffect(() => {
    if (!id) return;
    void api.getCard(id).then(setCard).catch(() => setCard(null));
    void api.categories("expense").then(setCategories).catch(() => setCategories([]));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    const raw = sessionStorage.getItem(IMPORT_PREVIEW_STORAGE_KEY);
    if (!raw) {
      navigate(`/cartoes/${id}`, { replace: true });
      return;
    }
    try {
      const parsed = JSON.parse(raw) as ImportPreviewSession;
      if (parsed.cardId !== id) {
        navigate(`/cartoes/${id}`, { replace: true });
        return;
      }
      if (!Array.isArray(parsed.rows) || !parsed.summary) {
        sessionStorage.removeItem(IMPORT_PREVIEW_STORAGE_KEY);
        setSessionError("Dados da preview inválidos. Importe o arquivo novamente.");
        return;
      }
      setSession(parsed);
      setRows(parsed.rows);
      setSessionError(null);
    } catch {
      sessionStorage.removeItem(IMPORT_PREVIEW_STORAGE_KEY);
      setSessionError("Não foi possível ler a preview salva. Importe o arquivo novamente.");
    }
  }, [id, navigate]);

  const periodLabel = useMemo(() => {
    const pid = periodId || session?.periodId || "";
    const p = periods.find((x) => x.id === pid);
    if (p) return monthLabel(p.mes, p.ano);
    return "Período da importação";
  }, [periodId, session?.periodId, periods, monthLabel]);

  const grouped = useMemo(() => {
    const g = {
      new: [] as ImportPreviewEditableRow[],
      kept: [] as ImportPreviewEditableRow[],
      updated: [] as ImportPreviewEditableRow[],
      skip: [] as ImportPreviewEditableRow[],
      orphan: [] as ImportPreviewEditableRow[],
    };
    for (const r of rows) {
      if (!VALID_STATUSES.has(r.status)) continue;
      g[r.status].push(r);
    }
    return g;
  }, [rows]);

  const toImportCount = useMemo(
    () => grouped.new.filter((r) => !r.skipped).length,
    [grouped.new],
  );
  const toUpdateCount = useMemo(
    () => grouped.updated.filter((r) => r.applyUpdate && !r.skipped).length,
    [grouped.updated],
  );
  const toDeleteCount = useMemo(
    () => grouped.orphan.filter((r) => r.removeOrphan && r.existingTransactionId).length,
    [grouped.orphan],
  );

  function patchRow(index: number, patch: Partial<ImportPreviewEditableRow>) {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  function globalIndex(row: ImportPreviewEditableRow): number {
    return rows.indexOf(row);
  }

  async function confirmImport() {
    if (!id || !periodId || periodClosed) return;
    const creates = grouped.new
      .filter((r) => !r.skipped)
      .map((r) => ({
        data: r.data,
        descricao: r.descricao.trim(),
        valor: valorToApi(r.valor),
        parcela_atual: r.parcelaAtual,
        parcela_total: r.parcelaTotal,
        categoria_id: r.categoriaId || null,
      }));
    const updates = grouped.updated
      .filter((r) => r.existingTransactionId)
      .map((r) => ({
        transaction_id: r.existingTransactionId!,
        apply: r.applyUpdate && !r.skipped,
        descricao: r.applyUpdate && !r.skipped ? r.descricao.trim() : undefined,
        valor: r.applyUpdate && !r.skipped ? valorToApi(r.valor) : undefined,
        data: r.applyUpdate && !r.skipped ? r.data : undefined,
        categoria_id: r.categoriaId || null,
      }));
    const deletes = grouped.orphan
      .filter((r) => r.removeOrphan && r.existingTransactionId)
      .map((r) => r.existingTransactionId!);

    if (creates.length === 0 && updates.every((u) => !u.apply) && deletes.length === 0) {
      setError("Nenhuma alteração para aplicar.");
      return;
    }

    const badCreate = creates.some((r) => !r.descricao || parseFloat(r.valor) === 0);
    if (badCreate) {
      setError("Revise descrição e valor dos lançamentos novos.");
      return;
    }

    setImporting(true);
    setError("");
    try {
      const res = await api.confirmStatementImport({
        card_id: id,
        period_id: periodId,
        creates,
        updates,
        deletes,
      });
      sessionStorage.removeItem(IMPORT_PREVIEW_STORAGE_KEY);
      setPeriodId(periodId);
      navigate(`/cartoes/${id}?periodId=${periodId}&importMsg=${encodeURIComponent(res.message)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro na importação");
    } finally {
      setImporting(false);
    }
  }

  function cancelImport() {
    sessionStorage.removeItem(IMPORT_PREVIEW_STORAGE_KEY);
    navigate(`/cartoes/${id}?periodId=${periodId}`);
  }

  function goBackToCard() {
    navigate(`/cartoes/${id}?periodId=${periodId || session?.periodId || ""}`);
  }

  if (!id) return null;

  if (sessionError) {
    return (
      <div className="ip-page-wrap padded">
        <p className="ip-error" role="alert">
          {sessionError}
        </p>
        <button type="button" className="btn" onClick={() => goBackToCard()}>
          Voltar ao cartão
        </button>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="ip-page-wrap padded">
        <p className="ip-loading">Carregando preview…</p>
      </div>
    );
  }

  const summary = session.summary;
  const nothingToApply = toImportCount === 0 && toUpdateCount === 0 && toDeleteCount === 0;

  function renderRow(row: ImportPreviewEditableRow, editable: boolean) {
    const idx = globalIndex(row);
    const catName = row.categoriaId
      ? categoryNameById(categories, row.categoriaId)
      : row.categoriaNome ?? "Sem categoria";

    return (
      <div
        key={`${row.status}-${row.data}-${row.descricao}-${idx}`}
        className={`ip-txn-row ip-txn-row--${row.status}${row.skipped ? " ip-txn-row--skipped" : ""}`}
      >
        <div className="ip-td-date">{formatDateBR(row.data)}</div>
        <div className="ip-td-desc">
          <div className="ip-td-desc-name">{row.descricao}</div>
          {row.status === "skip" && row.skipReason && (
            <div className="ip-skip-reason">{skipReasonLabel(row.skipReason)}</div>
          )}
          {row.status === "updated" && row.previousDescricao && (
            <div className="ip-update-diff">
              <span className="ip-diff-old">{row.previousDescricao}</span>
              <span className="ip-diff-arrow">→</span>
              <span className="ip-diff-new">{updateKindLabel(row.updateKind)}</span>
            </div>
          )}
          {row.status === "updated" &&
            row.updateKind === "valor" &&
            row.previousValor &&
            row.previousValor !== row.valor && (
              <div className="ip-update-diff">
                <span className="ip-diff-old">{formatBRL(row.previousValor)}</span>
                <span className="ip-diff-arrow">→</span>
                <span className="ip-diff-new">{formatBRL(row.valor)}</span>
              </div>
            )}
          {row.status === "updated" &&
            row.previousData &&
            row.previousData !== row.data && (
              <div className="ip-update-diff">
                <span className="ip-diff-old">{formatDateBR(row.previousData)}</span>
                <span className="ip-diff-arrow">→</span>
                <span className="ip-diff-new">{formatDateBR(row.data)}</span>
              </div>
            )}
        </div>
        <div className="ip-td-cat">
          {editable ? (
            <select
              className="ip-cat-select"
              value={row.categoriaId}
              onChange={(e) => patchRow(idx, { categoriaId: e.target.value })}
              disabled={importing}
            >
              <option value="">Selecionar…</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {categoryEmoji(c.nome)} {c.nome}
                </option>
              ))}
            </select>
          ) : (
            <span className="ip-cat-readonly">
              {catName !== "Sem categoria" ? `${categoryEmoji(catName)} ${catName}` : catName}
            </span>
          )}
        </div>
        <div className={`ip-td-val${row.status === "updated" && row.updateKind === "valor" ? " ip-td-val--updated" : ""}`}>
          {formatBRL(row.valor)}
        </div>
        <div className="ip-td-status">
          <span className={`ip-pill ip-pill--${row.status}`}>{statusLabel(row)}</span>
        </div>
        <div className="ip-td-action">
          {(row.status === "new" || row.status === "updated") && (
            <button
              type="button"
              className="ip-btn-skip"
              title={row.status === "updated" ? "Manter original" : "Ignorar"}
              disabled={importing}
              onClick={() => {
                const nextSkipped = !row.skipped;
                patchRow(idx, {
                  skipped: nextSkipped,
                  applyUpdate: row.status === "updated" ? !nextSkipped : row.applyUpdate,
                });
              }}
            >
              {row.skipped ? "↩" : "⊘"}
            </button>
          )}
          {row.status === "orphan" && (
            <label className="ip-orphan-check" title="Remover na confirmação">
              <input
                type="checkbox"
                checked={row.removeOrphan}
                disabled={importing}
                onChange={(e) => patchRow(idx, { removeOrphan: e.target.checked })}
              />
              <span>Remover</span>
            </label>
          )}
        </div>
      </div>
    );
  }

  function renderSection(
    status: "new" | "kept" | "updated" | "skip" | "orphan",
    title: string,
    subtitle: string,
    visible: boolean,
    onToggleVisible: () => void,
    expanded: boolean,
    onToggleExpand: () => void,
    list: ImportPreviewEditableRow[],
    editable: boolean,
    collapsedCard?: React.ReactNode,
  ) {
    if (list.length === 0) return null;
    const slice = expanded ? list : list.slice(0, PREVIEW_ROW_LIMIT);
    return (
      <section className="ip-section">
        <div className="ip-section-head">
          <div className={`ip-section-title ip-section-title--${status}`}>{title}</div>
          <div className="ip-section-meta">
            <span className="ip-section-count">{subtitle}</span>
            <button type="button" className="ip-section-toggle" onClick={onToggleVisible}>
              {visible ? "Ocultar" : "Ver"}
            </button>
          </div>
        </div>
        {!visible && collapsedCard}
        {visible && (
          <div className="ip-txn-table">
              <div className="ip-txn-head">
                <div>Data</div>
                <div>Descrição</div>
                <div>Categoria</div>
                <div className="ip-th-right">Valor</div>
                <div>Status</div>
                <div />
              </div>
              {slice.map((r) => renderRow(r, editable))}
              {list.length > PREVIEW_ROW_LIMIT && !expanded && (
                <div className="ip-table-more">
                  + {list.length - PREVIEW_ROW_LIMIT} lançamento(s) ·{" "}
                  <button type="button" className="ip-link-btn" onClick={onToggleExpand}>
                    Ver todos
                  </button>
                </div>
              )}
            </div>
        )}
      </section>
    );
  }

  return (
    <div className="ip-page-wrap">
      <header className="ip-topbar">
        <Link to={`/cartoes/${id}?periodId=${periodId}`} className="cd-back-btn">
          ← {card?.nome ?? "Cartão"}
        </Link>
        <div>
          <h1 className="ip-title">Preview da importação</h1>
          <p className="ip-subtitle">Revise antes de confirmar — categorias e divisões serão preservadas nos mantidos</p>
        </div>
      </header>

      <div className="ip-page">
        <div className="ip-header">
          <div className="ip-header-icon" aria-hidden>
            📥
          </div>
          <div className="ip-header-info">
            <div className="ip-header-title">
              {session.fileName} · {card?.nome ?? "Cartão"}
              {card?.banco ? ` (${card.banco})` : ""}
            </div>
            <div className="ip-header-meta">
              <span>📅 Período: {periodLabel}</span>
              <span>📄 {summary.total_in_file} lançamentos no arquivo</span>
              <span className={`ip-badge ip-badge--${session.formatTab}`}>
                {session.formatTab.toUpperCase()}
                {session.formatId ? ` · ${session.formatId}` : ""}
              </span>
              {periodClosed ? (
                <span className="ip-badge ip-badge--closed">Fatura fechada</span>
              ) : (
                <span className="ip-badge ip-badge--open">Fatura aberta</span>
              )}
            </div>
          </div>
        </div>

        <div className="ip-summary">
          <SummaryCard tone="new" label="➕ Novos" count={summary.new} desc="Não existiam antes" />
          <SummaryCard
            tone="kept"
            label="✓ Mantidos"
            count={summary.kept}
            desc="Já existem · categorias preservadas"
          />
          <SummaryCard
            tone="updated"
            label="🔄 Atualizados"
            count={summary.updated}
            desc="Nome ou valor diferente"
          />
          <SummaryCard tone="skip" label="⊘ Ignorados" count={summary.skip} desc="Pagamentos e linhas irrelevantes" />
          {(summary.orphan ?? 0) > 0 && (
            <SummaryCard
              tone="orphan"
              label="🗑 Órfãos"
              count={summary.orphan}
              desc="Não estão na fatura · remoção sugerida"
            />
          )}
        </div>

        {session.warnings.length > 0 && (
          <div className="ip-warnings" role="status">
            <div className="ip-warnings-title">Avisos do parser</div>
            <ul>
              {session.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        {error && (
          <p className="ip-error" role="alert">
            {error}
          </p>
        )}

        {renderSection(
          "new",
          "Novos lançamentos",
          `${grouped.new.length} lançamento(s) · ${grouped.new.filter((r) => !r.categoriaId).length} sem categoria`,
          showNew,
          () => setShowNew((v) => !v),
          expandNew,
          () => setExpandNew(true),
          grouped.new,
          true,
        )}

        {renderSection(
          "updated",
          "Atualizados — nome ou valor diferente",
          `${grouped.updated.length} lançamento(s) · revise se quiser`,
          showUpdated,
          () => setShowUpdated((v) => !v),
          expandUpdated,
          () => setExpandUpdated(true),
          grouped.updated,
          true,
        )}

        {renderSection(
          "kept",
          "Mantidos — nenhuma ação necessária",
          `${grouped.kept.length} lançamento(s) · categorias preservadas`,
          showKept,
          () => setShowKept((v) => !v),
          expandKept,
          () => setExpandKept(true),
          grouped.kept,
          false,
          !showKept ? (
            <div className="ip-kept-collapsed">
              <span aria-hidden>✓</span>
              <div>
                <div className="ip-kept-collapsed-title">
                  {grouped.kept.length} lançamento(s) já existem e estão preservados
                </div>
                <div className="ip-kept-collapsed-sub">
                  Categorias, divisões e observações mantidas como você configurou
                </div>
              </div>
              <button type="button" className="ip-link-btn" onClick={() => setShowKept(true)}>
                Ver detalhes →
              </button>
            </div>
          ) : undefined,
        )}

        {grouped.skip.length > 0 &&
          renderSection(
            "skip",
            "Ignorados automaticamente",
            `${grouped.skip.length} linha(s)`,
            showSkip,
            () => setShowSkip((v) => !v),
            false,
            () => undefined,
            grouped.skip,
            false,
          )}

        {grouped.orphan.length > 0 &&
          renderSection(
            "orphan",
            "Não estão na fatura",
            `${grouped.orphan.length} lançamento(s) · ${toDeleteCount} marcado(s) para remover`,
            showOrphan,
            () => setShowOrphan((v) => !v),
            expandOrphan,
            () => setExpandOrphan(true),
            grouped.orphan,
            false,
          )}

        <div className="ip-spacer" />
      </div>

      <footer className="ip-footer">
        <div className="ip-footer-left">
          {toImportCount > 0 && (
            <>
              <strong>{toImportCount} novos</strong> serão adicionados
            </>
          )}
          {summary.kept > 0 && (
            <>
              {toImportCount > 0 ? " · " : ""}
              <strong>{summary.kept} mantidos</strong> preservados
            </>
          )}
          {toUpdateCount > 0 && (
            <>
              {" · "}
              <strong>{toUpdateCount} atualizados</strong>
            </>
          )}
          {toDeleteCount > 0 && (
            <>
              {toImportCount > 0 || summary.kept > 0 || toUpdateCount > 0 ? " · " : ""}
              <strong>{toDeleteCount} removidos</strong>
            </>
          )}
          {nothingToApply && summary.kept > 0 && (
            <>Nenhuma alteração necessária — todos os lançamentos já estão no sistema.</>
          )}
        </div>
        <div className="ip-footer-btns">
          {nothingToApply && (
            <button type="button" className="btn" disabled={importing} onClick={() => goBackToCard()}>
              Voltar ao cartão
            </button>
          )}
          <button type="button" className="btn btn-ghost" disabled={importing} onClick={cancelImport}>
            Cancelar
          </button>
          <button
            type="button"
            className="btn"
            disabled={importing || periodClosed || nothingToApply}
            onClick={() => void confirmImport()}
          >
            {importing
              ? "Importando…"
              : toDeleteCount > 0
                ? `✅ Confirmar · remover ${toDeleteCount}`
                : "✅ Confirmar importação"}
          </button>
        </div>
      </footer>
    </div>
  );
}
