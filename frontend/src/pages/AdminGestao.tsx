import { Fragment, useEffect, useState } from "react";
import { AdminSessionSettingsPanel } from "../components/AdminSessionSettingsPanel";
import { AdminUsersPanel } from "../components/AdminUsersPanel";
import { api } from "../api";
import type { AdminManagementStats, SystemErrorLogRow, UserMe } from "../types";

type GestaoPanel = "indicadores" | "logs" | "usuarios" | "sessao";

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pt-BR");
}

function statusTier(code: number): "error" | "warning" | "ok" {
  if (code >= 500) return "error";
  if (code >= 400) return "warning";
  return "ok";
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="admin-stat-card">
      <span className="admin-stat-card__label">{label}</span>
      <strong className="admin-stat-card__value">{value}</strong>
    </div>
  );
}

function LogEntryBody({
  row,
  expanded,
  onToggle,
}: {
  row: SystemErrorLogRow;
  expanded: boolean;
  onToggle: () => void;
}) {
  const tier = statusTier(row.status_code);
  const hasDetail = !!(row.detail || row.traceback);

  return (
    <>
      <header className="admin-log-entry__head">
        <span className={`admin-log-status admin-log-status--${tier}`}>{row.status_code}</span>
        <span className="admin-log-method">{row.method}</span>
        <time className="admin-log-time muted small">{formatWhen(row.created_at)}</time>
      </header>
      <p className="admin-log-path">{row.path}</p>
      <p className="admin-log-user muted small">{row.user_email ?? "Sem usuário"}</p>
      {expanded && hasDetail && (
        <div className="admin-log-entry__detail">
          {row.detail && (
            <p className="admin-log-detail-text">
              <strong>Detalhe:</strong> {row.detail}
            </p>
          )}
          {row.traceback && <pre className="admin-log-trace">{row.traceback}</pre>}
        </div>
      )}
      {hasDetail && (
        <div className="admin-log-entry__actions">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onToggle}>
            {expanded ? "Ocultar detalhe" : "Ver detalhe"}
          </button>
        </div>
      )}
    </>
  );
}

export function AdminGestao() {
  const [me, setMe] = useState<UserMe | null>(null);
  const [stats, setStats] = useState<AdminManagementStats | null>(null);
  const [logs, setLogs] = useState<SystemErrorLogRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [panel, setPanel] = useState<GestaoPanel | null>(null);
  const [logDetailId, setLogDetailId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const current = await api.getMe();
        if (!current.is_admin) {
          if (!cancelled) setMe(current);
          return;
        }
        const [s, rows] = await Promise.all([
          api.adminManagementStats(),
          api.adminErrorLogs(200),
        ]);
        if (!cancelled) {
          setMe(current);
          setStats(s);
          setLogs(rows);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Erro ao carregar gestão");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function togglePanel(next: GestaoPanel) {
    setPanel((current) => {
      if (current === next) return null;
      setLogDetailId(null);
      return next;
    });
  }

  function closePanel() {
    setPanel(null);
    setLogDetailId(null);
  }

  if (loading) {
    return <p className="muted">Carregando gestão…</p>;
  }

  if (!me?.is_admin) {
    return <p className="error">Acesso permitido somente para administradores.</p>;
  }

  const errorsLast7d = stats?.errors_last_7d ?? 0;

  return (
    <div className="admin-gestao">
      {error && <p className="error">{error}</p>}

      <div className="admin-gestao-hub" role="tablist" aria-label="Seções da gestão">
        <button
          type="button"
          role="tab"
          aria-selected={panel === "indicadores"}
          aria-controls="admin-gestao-panel-indicadores"
          className={`admin-gestao-hub-card card${panel === "indicadores" ? " admin-gestao-hub-card--active" : ""}`}
          onClick={() => togglePanel("indicadores")}
        >
          <span className="admin-gestao-hub-card__icon" aria-hidden>
            ◎
          </span>
          <span className="admin-gestao-hub-card__title">Indicadores</span>
          <span className="admin-gestao-hub-card__desc muted small">
            Cadastros, logins e erros da plataforma
          </span>
          {stats && (
            <span className="admin-gestao-hub-card__meta">
              {stats.total_registered} cadastrados · {stats.active_users_last_7d} ativos (7d)
            </span>
          )}
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={panel === "logs"}
          aria-controls="admin-gestao-panel-logs"
          className={`admin-gestao-hub-card card${panel === "logs" ? " admin-gestao-hub-card--active" : ""}`}
          onClick={() => togglePanel("logs")}
        >
          <span className="admin-gestao-hub-card__icon" aria-hidden>
            ⚠
          </span>
          <span className="admin-gestao-hub-card__title">Logs</span>
          <span className="admin-gestao-hub-card__desc muted small">
            Erros 4xx, 5xx e exceções recentes
          </span>
          <span className="admin-gestao-hub-card__meta">
            {logs.length} registro{logs.length === 1 ? "" : "s"}
            {stats ? ` · ${errorsLast7d} erro${errorsLast7d === 1 ? "" : "s"} (7d)` : ""}
          </span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={panel === "sessao"}
          aria-controls="admin-gestao-panel-sessao"
          className={`admin-gestao-hub-card card${panel === "sessao" ? " admin-gestao-hub-card--active" : ""}`}
          onClick={() => togglePanel("sessao")}
        >
          <span className="admin-gestao-hub-card__icon" aria-hidden>
            ⏱
          </span>
          <span className="admin-gestao-hub-card__title">Sessão</span>
          <span className="admin-gestao-hub-card__desc muted small">
            Logout automático por inatividade
          </span>
          <span className="admin-gestao-hub-card__meta">
            Ativo por padrão · 1 hora
          </span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={panel === "usuarios"}
          aria-controls="admin-gestao-panel-usuarios"
          className={`admin-gestao-hub-card card admin-gestao-hub-card--wide${panel === "usuarios" ? " admin-gestao-hub-card--active" : ""}`}
          onClick={() => togglePanel("usuarios")}
        >
          <span className="admin-gestao-hub-card__icon" aria-hidden>
            ◉
          </span>
          <span className="admin-gestao-hub-card__title">Usuários</span>
          <span className="admin-gestao-hub-card__desc muted small">
            Criar contas, perfis de admin e senhas
          </span>
          {stats && (
            <span className="admin-gestao-hub-card__meta">
              {stats.total_registered}{" "}
              {stats.total_registered === 1 ? "conta cadastrada" : "contas cadastradas"}
            </span>
          )}
        </button>
      </div>

      {panel === null && (
        <p className="admin-gestao-hint muted small">Toque em um card para ver os detalhes.</p>
      )}

      {panel === "indicadores" && (
        <section
          id="admin-gestao-panel-indicadores"
          className="admin-gestao-panel"
          role="tabpanel"
          aria-labelledby="admin-stats-heading"
        >
          <div className="admin-gestao-panel__head">
            <h2 id="admin-stats-heading">Indicadores</h2>
            <button type="button" className="btn btn-ghost btn-sm" onClick={closePanel}>
              Fechar
            </button>
          </div>
          <p className="admin-section__lead muted small">
            Cadastros e acessos com login registrado a partir desta versão. Logins anteriores não entram no
            histórico.
          </p>
          {stats ? (
            <div className="admin-stat-grid">
              <StatCard label="Total cadastrados" value={stats.total_registered} />
              <StatCard label="Cadastros (7 dias)" value={stats.registered_last_7d} />
              <StatCard label="Cadastros (30 dias)" value={stats.registered_last_30d} />
              <StatCard label="Já fizeram login" value={stats.users_ever_logged_in} />
              <StatCard label="Ativos (7 dias)" value={stats.active_users_last_7d} />
              <StatCard label="Logins (7 dias)" value={stats.logins_last_7d} />
              <StatCard label="Logins (30 dias)" value={stats.logins_last_30d} />
              <StatCard label="Erros (7 dias)" value={stats.errors_last_7d} />
            </div>
          ) : (
            <p className="muted">Indicadores indisponíveis.</p>
          )}
        </section>
      )}

      {panel === "logs" && (
        <section
          id="admin-gestao-panel-logs"
          className="admin-gestao-panel"
          role="tabpanel"
          aria-labelledby="admin-logs-heading"
        >
          <div className="admin-gestao-panel__head">
            <h2 id="admin-logs-heading">Logs de erros</h2>
            <button type="button" className="btn btn-ghost btn-sm" onClick={closePanel}>
              Fechar
            </button>
          </div>
          <p className="admin-section__lead muted small">
            Requisições com status 4xx ou 5xx e exceções não tratadas. Ordenado do mais recente.
          </p>
          <div className="admin-logs-panel card">
            {logs.length === 0 ? (
              <p className="muted" style={{ margin: 0 }}>
                Nenhum erro registrado ainda.
              </p>
            ) : (
              <>
                <ul className="admin-log-list admin-logs-mobile-only" aria-label="Logs de erros">
                  {logs.map((row) => (
                    <li key={row.id} className="admin-log-entry">
                      <LogEntryBody
                        row={row}
                        expanded={logDetailId === row.id}
                        onToggle={() =>
                          setLogDetailId((current) => (current === row.id ? null : row.id))
                        }
                      />
                    </li>
                  ))}
                </ul>
                <div className="table-scroll-wrap admin-logs-desktop-only">
                  <table className="admin-logs-table">
                    <thead>
                      <tr>
                        <th>Quando</th>
                        <th>Status</th>
                        <th>Método</th>
                        <th>Caminho</th>
                        <th>Usuário</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {logs.map((row) => (
                        <Fragment key={row.id}>
                          <tr>
                            <td className="admin-logs-table__when">{formatWhen(row.created_at)}</td>
                            <td>
                              <span
                                className={`admin-log-status admin-log-status--${statusTier(row.status_code)}`}
                              >
                                {row.status_code}
                              </span>
                            </td>
                            <td>
                              <span className="admin-log-method">{row.method}</span>
                            </td>
                            <td className="admin-log-path">{row.path}</td>
                            <td>{row.user_email ?? "—"}</td>
                            <td>
                              {(row.detail || row.traceback) && (
                                <button
                                  type="button"
                                  className="btn btn-ghost btn-sm"
                                  onClick={() =>
                                    setLogDetailId((current) => (current === row.id ? null : row.id))
                                  }
                                >
                                  {logDetailId === row.id ? "Ocultar" : "Detalhe"}
                                </button>
                              )}
                            </td>
                          </tr>
                          {logDetailId === row.id && (row.detail || row.traceback) && (
                            <tr className="admin-log-detail-row">
                              <td colSpan={6}>
                                {row.detail && (
                                  <p className="admin-log-detail-text">
                                    <strong>Detalhe:</strong> {row.detail}
                                  </p>
                                )}
                                {row.traceback && <pre className="admin-log-trace">{row.traceback}</pre>}
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        </section>
      )}

      {panel === "sessao" && (
        <section
          id="admin-gestao-panel-sessao"
          className="admin-gestao-panel"
          role="tabpanel"
          aria-labelledby="admin-sessao-heading"
        >
          <div className="admin-gestao-panel__head">
            <h2 id="admin-sessao-heading">Sessão e inatividade</h2>
            <button type="button" className="btn btn-ghost btn-sm" onClick={closePanel}>
              Fechar
            </button>
          </div>
          <AdminSessionSettingsPanel />
        </section>
      )}

      {panel === "usuarios" && (
        <section
          id="admin-gestao-panel-usuarios"
          className="admin-gestao-panel"
          role="tabpanel"
          aria-labelledby="admin-users-heading"
        >
          <div className="admin-gestao-panel__head">
            <h2 id="admin-users-heading">Usuários</h2>
            <button type="button" className="btn btn-ghost btn-sm" onClick={closePanel}>
              Fechar
            </button>
          </div>
          <AdminUsersPanel />
        </section>
      )}
    </div>
  );
}
