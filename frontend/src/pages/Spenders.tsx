import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAppDialog } from "../context/DialogContext";
import type { SpenderRow, UserMe } from "../types";

const PERSON_GRADIENTS = [
  "linear-gradient(135deg,#334155,#475569)",
  "linear-gradient(135deg,#3b82f6,#22d3ee)",
  "linear-gradient(135deg,#f43f5e,#a855f7)",
  "linear-gradient(135deg,#f59e0b,#ef4444)",
  "linear-gradient(135deg,#a78bfa,#ec4899)",
  "linear-gradient(135deg,#22c55e,#16a34a)",
];

function personInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0]!.slice(0, 2);
  return `${parts[0]!.charAt(0)}${parts[parts.length - 1]!.charAt(0)}`;
}

function personGradient(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash + name.charCodeAt(i) * (i + 1)) % PERSON_GRADIENTS.length;
  }
  return PERSON_GRADIENTS[hash] ?? PERSON_GRADIENTS[0]!;
}

export function Spenders() {
  const { confirm } = useAppDialog();
  const navigate = useNavigate();
  const addCardRef = useRef<HTMLDivElement>(null);
  const addInputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<SpenderRow[]>([]);
  const [me, setMe] = useState<UserMe | null>(null);
  const [nome, setNome] = useState("");
  const [error, setError] = useState("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameNome, setRenameNome] = useState("");
  const [savingMe, setSavingMe] = useState(false);
  const [savingRename, setSavingRename] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [creating, setCreating] = useState(false);

  async function load() {
    const [r, u] = await Promise.all([api.listSpenders(), api.getMe()]);
    setRows(r);
    setMe(u);
  }

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        await load();
      } catch (e) {
        if (!c) setError(e instanceof Error ? e.message : "Erro");
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  useEffect(() => {
    if (!showAddForm) return;
    const t = window.setTimeout(() => {
      addInputRef.current?.focus();
      addCardRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 80);
    return () => window.clearTimeout(t);
  }, [showAddForm]);

  useEffect(() => {
    if (!renamingId) return;
    const t = window.setTimeout(() => renameInputRef.current?.focus(), 120);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeRenameModal();
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [renamingId]);

  function openAddForm() {
    setShowAddForm(true);
  }

  function cancelAddForm() {
    setShowAddForm(false);
    setNome("");
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!nome.trim()) {
      setError("Informe um nome.");
      return;
    }
    setCreating(true);
    try {
      await api.createSpender({ nome: nome.trim() });
      setNome("");
      setShowAddForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setCreating(false);
    }
  }

  function openRenameModal(row: SpenderRow) {
    setRenamingId(row.id);
    setRenameNome(row.nome);
  }

  function closeRenameModal() {
    setRenamingId(null);
    setRenameNome("");
  }

  async function onSaveRename(e?: React.FormEvent) {
    e?.preventDefault();
    if (!renamingId || !renameNome.trim()) return;
    setSavingRename(true);
    setError("");
    try {
      await api.updateSpender(renamingId, { nome: renameNome.trim() });
      closeRenameModal();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setSavingRename(false);
    }
  }

  async function onDelete(id: string) {
    const ok = await confirm({
      title: "Excluir pessoa",
      message: "Excluir esta pessoa? Só é permitido se não houver divisões de cartão vinculadas.",
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    setError("");
    try {
      await api.deleteSpender(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    }
  }

  async function setAsMe(spenderId: string) {
    setSavingMe(true);
    setError("");
    try {
      const u = await api.patchMe({ me_spender_id: spenderId });
      setMe(u);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setSavingMe(false);
    }
  }

  async function clearMe() {
    setSavingMe(true);
    setError("");
    try {
      const u = await api.patchMe({ me_spender_id: null });
      setMe(u);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setSavingMe(false);
    }
  }

  function onGoBack() {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate("/cartoes");
  }

  return (
    <div className="padded spenders-page">
      <header className="sp-topbar">
        <button type="button" className="sp-topbar-back" onClick={() => onGoBack()}>
          ← Cartões
        </button>
        <div className="sp-topbar-title">Pessoas no cartão</div>
        <div className="sp-topbar-right">
          <button type="button" className="sp-btn-primary" onClick={() => openAddForm()}>
            ＋ Criar participante
          </button>
        </div>
      </header>

      <div className="sp-page">
        <div className="sp-info-banner">
          <span className="sp-info-icon" aria-hidden>
            ℹ️
          </span>
          <div className="sp-info-text">
            Cadastre quem usa o cartão compartilhado. Em cada lançamento você pode dividir o valor entre essas pessoas
            e gerar o resumo do mês para enviar. Marque <strong>Titular</strong> na pessoa que representa você — no
            cartão, &quot;minha parte&quot; soma só os valores dessa pessoa nas divisões (o mesmo critério do card em
            &quot;Uso por pessoa&quot;).
          </div>
        </div>

        {error && <p className="sp-error">{error}</p>}

        <div className="sp-section-label">Cadastradas</div>

        <div className="sp-person-list">
          {rows.length === 0 ? (
            <p className="sp-empty">Nenhuma pessoa ainda.</p>
          ) : (
            rows.map((r, idx) => {
              const isEu = me?.me_spender_id === r.id;
              return (
                <div
                  key={r.id}
                  className={`sp-person-row${isEu ? " sp-person-row--eu" : ""}`}
                  style={{ animationDelay: `${0.03 * (idx + 1)}s` }}
                >
                  <div
                    className="sp-person-av"
                    style={{ background: personGradient(r.nome) }}
                    aria-hidden
                  >
                    {personInitials(r.nome)}
                  </div>
                  <div className="sp-person-info">
                    <div className="sp-person-name">
                      {r.nome}
                      {isEu && <span className="sp-eu-badge">✓ Titular</span>}
                    </div>
                    <div className="sp-person-sub">
                      {isEu
                        ? 'Você — valores "minha parte" usam esta pessoa'
                        : "Participante do cartão"}
                    </div>
                  </div>
                  <div className="sp-person-actions">
                    {isEu ? (
                      <button
                        type="button"
                        className="sp-btn-action sp-btn-remover-eu"
                        disabled={savingMe}
                        onClick={() => void clearMe()}
                      >
                        Remover titular
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="sp-btn-action sp-btn-sou-eu"
                        disabled={savingMe}
                        onClick={() => void setAsMe(r.id)}
                      >
                        Titular
                      </button>
                    )}
                    <button
                      type="button"
                      className="sp-btn-action sp-btn-renomear"
                      onClick={() => openRenameModal(r)}
                    >
                      Renomear
                    </button>
                    <button
                      type="button"
                      className="sp-btn-action sp-btn-excluir"
                      onClick={() => void onDelete(r.id)}
                    >
                      Excluir
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {showAddForm && (
          <div ref={addCardRef} className="sp-add-card">
            <div className="sp-add-card-title">Novo participante</div>
            <form onSubmit={onCreate} className="sp-add-row">
              <input
                ref={addInputRef}
                className="sp-add-input"
                type="text"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                placeholder="Nome do participante…"
                disabled={creating}
                required
              />
              <button type="submit" className="sp-btn-primary" disabled={creating}>
                {creating ? "Adicionando…" : "Adicionar"}
              </button>
              <button
                type="button"
                className="sp-btn-action sp-btn-renomear sp-add-cancel"
                onClick={() => cancelAddForm()}
                disabled={creating}
              >
                Cancelar
              </button>
            </form>
          </div>
        )}
      </div>

      {renamingId && (
        <div
          className="sp-modal-overlay sp-modal-overlay--open"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget && !savingRename) closeRenameModal();
          }}
        >
          <div
            className="sp-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="rename-spender-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sp-modal-header">
              <div id="rename-spender-title" className="sp-modal-title">
                Renomear participante
              </div>
              <button
                type="button"
                className="sp-modal-close"
                aria-label="Fechar"
                disabled={savingRename}
                onClick={() => closeRenameModal()}
              >
                ✕
              </button>
            </div>
            <form onSubmit={onSaveRename}>
              <div className="sp-modal-body">
                <label className="sp-modal-label" htmlFor="rename-spender-input">
                  Novo nome
                </label>
                <input
                  ref={renameInputRef}
                  id="rename-spender-input"
                  className="sp-modal-input"
                  type="text"
                  value={renameNome}
                  onChange={(e) => setRenameNome(e.target.value)}
                  placeholder="Nome…"
                  disabled={savingRename}
                  required
                />
              </div>
              <div className="sp-modal-footer">
                <button
                  type="button"
                  className="sp-modal-btn-cancel"
                  onClick={() => closeRenameModal()}
                  disabled={savingRename}
                >
                  Cancelar
                </button>
                <button type="submit" className="sp-modal-btn-save" disabled={savingRename || !renameNome.trim()}>
                  {savingRename ? "Salvando…" : "Salvar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
