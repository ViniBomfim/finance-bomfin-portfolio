import { useCallback, useEffect, useMemo, useState, type MouseEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type {
  NotificationGrupos,
  NotificationListResponse,
  NotificationModulo,
  NotificationRow,
  NotificationSeveridade,
} from "../types";

const MODULE_META: {
  key: NotificationModulo;
  label: string;
  icon: string;
}[] = [
  { key: "cartoes", label: "Cartões", icon: "💳" },
  { key: "devedores", label: "Devedores", icon: "💸" },
  { key: "metas", label: "Metas", icon: "🎯" },
  { key: "viagens", label: "Viagens", icon: "✈️" },
  { key: "gastos_fixos", label: "Gastos fixos", icon: "📌" },
];

const SEV_CLASS: Record<NotificationSeveridade, string> = {
  urgente: "severity-red",
  atencao: "severity-amber",
  info: "severity-info",
};

const SEV_ICON_BG: Record<NotificationSeveridade, string> = {
  urgente: "rgba(244, 63, 94, 0.15)",
  atencao: "rgba(245, 158, 11, 0.15)",
  info: "rgba(59, 130, 246, 0.15)",
};

function emptyGrupos(): NotificationGrupos {
  return { cartoes: [], devedores: [], metas: [], viagens: [], gastos_fixos: [] };
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffSec = Math.round((Date.now() - then) / 1000);
  if (diffSec < 60) return "agora";
  const min = Math.floor(diffSec / 60);
  if (min < 60) return `há ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `há ${h}h`;
  const d = Math.floor(h / 24);
  if (d === 1) return "ontem";
  if (d < 30) return `há ${d} dias`;
  return new Date(iso).toLocaleDateString("pt-BR");
}

function countInGrupos(grupos: NotificationGrupos): number {
  return MODULE_META.reduce((acc, m) => acc + (grupos[m.key]?.length ?? 0), 0);
}

type Props = {
  open: boolean;
  onClose: () => void;
  unreadTotal: number;
  onUnreadChange: (total: number) => void;
};

export function NotificationsPanel({ open, onClose, unreadTotal, onUnreadChange }: Props) {
  const navigate = useNavigate();
  const [tab, setTab] = useState<"novas" | "historico">("novas");
  const [loading, setLoading] = useState(false);
  const [marking, setMarking] = useState(false);
  const [unread, setUnread] = useState<NotificationListResponse>({
    total: 0,
    grupos: emptyGrupos(),
  });
  const [history, setHistory] = useState<NotificationListResponse>({
    total: 0,
    grupos: emptyGrupos(),
  });

  const loadUnread = useCallback(async () => {
    const data = await api.listNotifications();
    setUnread(data);
    onUnreadChange(data.total);
  }, [onUnreadChange]);

  const loadHistory = useCallback(async () => {
    const data = await api.listNotificationHistory();
    setHistory(data);
  }, []);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        await loadUnread();
        if (tab === "historico" && !cancelled) await loadHistory();
      } catch {
        /* ignore */
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, loadUnread, loadHistory, tab]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const activeGrupos = tab === "novas" ? unread.grupos : history.grupos;
  const activeCount = useMemo(() => countInGrupos(activeGrupos), [activeGrupos]);
  const hasAny = activeCount > 0;

  async function markOne(item: NotificationRow, e: MouseEvent) {
    e.stopPropagation();
    if (item.lida) return;
    try {
      await api.markNotificationRead(item.id);
      await loadUnread();
      if (tab === "historico") await loadHistory();
    } catch {
      /* ignore */
    }
  }

  async function markAll() {
    if (marking || unreadTotal === 0) return;
    setMarking(true);
    try {
      await api.markAllNotificationsRead();
      await loadUnread();
      if (tab === "historico") await loadHistory();
    } catch {
      /* ignore */
    } finally {
      setMarking(false);
    }
  }

  function openItem(item: NotificationRow) {
    if (item.link) {
      navigate(item.link);
      onClose();
    }
  }

  if (!open) return null;

  return (
    <div className="nd-root" role="presentation">
      <button type="button" className="nd-backdrop" aria-label="Fechar notificações" onClick={onClose} />
      <aside className="nd-panel" role="dialog" aria-modal="true" aria-label="Notificações">
        <header className="nd-header">
          <div className="nd-header-title">
            <h2>Notificações</h2>
            {unreadTotal > 0 && <span className="nd-count-badge">{unreadTotal}</span>}
          </div>
          <div className="nd-header-actions">
            <button
              type="button"
              className="nd-mark-all"
              onClick={() => void markAll()}
              disabled={marking || unreadTotal === 0}
            >
              ✓ Marcar todas lidas
            </button>
            <button type="button" className="nd-close" aria-label="Fechar" onClick={onClose}>
              ✕
            </button>
          </div>
        </header>

        <div className="nd-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "novas"}
            className={`nd-tab${tab === "novas" ? " active" : ""}`}
            onClick={() => setTab("novas")}
          >
            Novas
            {unreadTotal > 0 && <span className="nd-tab-badge">{unreadTotal}</span>}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "historico"}
            className={`nd-tab${tab === "historico" ? " active" : ""}`}
            onClick={() => setTab("historico")}
          >
            Histórico
          </button>
        </div>

        <div className="nd-body">
          {loading && <p className="nd-empty">Carregando…</p>}
          {!loading && !hasAny && tab === "novas" && (
            <div className="nd-empty nd-empty-state">
              <span aria-hidden="true">🎉</span>
              <p>Tudo em dia!</p>
            </div>
          )}
          {!loading && !hasAny && tab === "historico" && (
            <div className="nd-empty nd-empty-state">
              <p>Nenhuma notificação no histórico</p>
            </div>
          )}
          {!loading &&
            hasAny &&
            MODULE_META.map((mod) => {
              const items = activeGrupos[mod.key] ?? [];
              if (items.length === 0) return null;
              return (
                <section key={mod.key} className="nd-group">
                  <h3 className="nd-group-title">
                    <span aria-hidden="true">{mod.icon}</span> {mod.label}
                  </h3>
                  <ul className="nd-list">
                    {items.map((item) => (
                      <li key={item.id}>
                        <button
                          type="button"
                          className={`nd-item ${item.lida ? "read" : `unread ${SEV_CLASS[item.severidade]}`}`}
                          onClick={() => openItem(item)}
                        >
                          {!item.lida && <span className="nd-unread-dot" aria-hidden="true" />}
                          <span
                            className="nd-item-icon"
                            style={{ background: SEV_ICON_BG[item.severidade] }}
                            aria-hidden="true"
                          >
                            {mod.icon}
                          </span>
                          <span className="nd-item-main">
                            <span className="nd-item-title">{item.titulo}</span>
                            <span className="nd-item-sub">{item.subtitulo}</span>
                            <span className="nd-item-foot">
                              <span className="nd-item-time">
                                {relativeTime(item.lida ? item.lida_em || item.criado_em : item.criado_em)}
                              </span>
                              {!item.lida && (
                                <span
                                  role="button"
                                  tabIndex={0}
                                  className="nd-item-check"
                                  title="Marcar como lida"
                                  onClick={(e) => void markOne(item, e)}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter" || e.key === " ") {
                                      e.preventDefault();
                                      e.stopPropagation();
                                      void api.markNotificationRead(item.id).then(() => {
                                        void loadUnread();
                                        if (tab === "historico") void loadHistory();
                                      });
                                    }
                                  }}
                                >
                                  ✓
                                </span>
                              )}
                            </span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
        </div>
      </aside>
    </div>
  );
}
