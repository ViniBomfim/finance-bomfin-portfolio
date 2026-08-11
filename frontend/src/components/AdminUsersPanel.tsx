import { useEffect, useState } from "react";
import { api } from "../api";
import { useAppDialog } from "../context/DialogContext";
import type { AccessRequestRow, AdminUserRow } from "../types";

export function AdminUsersPanel() {
  const { confirm, alert } = useAppDialog();
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [accessRequests, setAccessRequests] = useState<AccessRequestRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createUsername, setCreateUsername] = useState("");
  const [createName, setCreateName] = useState("");
  const [createEmail, setCreateEmail] = useState("");
  const [createPassword, setCreatePassword] = useState("");
  const [createIsAdmin, setCreateIsAdmin] = useState(false);
  const [createMustChangePassword, setCreateMustChangePassword] = useState(true);
  const [createSaving, setCreateSaving] = useState(false);
  const [createError, setCreateError] = useState("");
  const [editingUser, setEditingUser] = useState<AdminUserRow | null>(null);
  const [editUsername, setEditUsername] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState("");
  const [resetUser, setResetUser] = useState<AdminUserRow | null>(null);
  const [resetPasswordValue, setResetPasswordValue] = useState("");
  const [resetSaving, setResetSaving] = useState(false);
  const [resetError, setResetError] = useState("");

  async function load() {
    const [rows, pending] = await Promise.all([api.listUsers(), api.listAccessRequests()]);
    setUsers(rows);
    setAccessRequests(pending);
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        await load();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Erro ao carregar usuários");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function openCreateModal() {
    setCreateUsername("");
    setCreateName("");
    setCreateEmail("");
    setCreatePassword("");
    setCreateIsAdmin(false);
    setCreateMustChangePassword(true);
    setCreateError("");
    setShowCreateModal(true);
  }

  function closeCreateModal() {
    setShowCreateModal(false);
    setCreateError("");
  }

  function openEditModal(user: AdminUserRow) {
    setEditingUser(user);
    setEditUsername(user.username);
    setEditEmail(user.email);
    setEditError("");
  }

  function closeEditModal() {
    setEditingUser(null);
    setEditError("");
  }

  async function handleEditUser(e: { preventDefault: () => void }) {
    e.preventDefault();
    if (!editingUser) return;
    setEditSaving(true);
    setEditError("");
    try {
      await api.adminUpdateUser(editingUser.id, {
        username: editUsername.trim(),
        email: editEmail.trim(),
      });
      closeEditModal();
      await load();
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Erro ao atualizar usuário");
    } finally {
      setEditSaving(false);
    }
  }

  async function handleCreateUser(e: { preventDefault: () => void }) {
    e.preventDefault();
    if (createPassword.trim().length < 6) {
      setCreateError("A senha precisa ter ao menos 6 caracteres.");
      return;
    }
    setCreateSaving(true);
    setCreateError("");
    try {
      await api.adminCreateUser({
        username: createUsername.trim(),
        name: createName.trim(),
        email: createEmail.trim(),
        password: createPassword,
        is_admin: createIsAdmin,
        must_change_password: createMustChangePassword,
      });
      closeCreateModal();
      await load();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Erro ao criar usuário");
    } finally {
      setCreateSaving(false);
    }
  }

  async function approveRequest(request: AccessRequestRow) {
    setError("");
    try {
      await api.approveAccessRequest(request.id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao aprovar solicitação");
    }
  }

  async function rejectRequest(request: AccessRequestRow) {
    const ok = await confirm({
      title: "Recusar solicitação",
      message: `Recusar acesso de ${request.username} (${request.email})?`,
      confirmLabel: "Recusar",
      danger: true,
    });
    if (!ok) return;
    setError("");
    try {
      await api.rejectAccessRequest(request.id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao recusar solicitação");
    }
  }

  async function toggleAdmin(user: AdminUserRow) {
    setError("");
    try {
      await api.adminUpdateUser(user.id, { is_admin: !user.is_admin });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao atualizar perfil de admin");
    }
  }

  function openResetModal(user: AdminUserRow) {
    setResetUser(user);
    setResetPasswordValue("");
    setResetError("");
  }

  function closeResetModal() {
    setResetUser(null);
    setResetPasswordValue("");
    setResetError("");
  }

  async function handleResetPassword(e: { preventDefault: () => void }) {
    e.preventDefault();
    if (!resetUser) return;
    if (resetPasswordValue.trim().length < 6) {
      setResetError("A senha precisa ter ao menos 6 caracteres.");
      return;
    }
    setResetSaving(true);
    setResetError("");
    try {
      await api.adminResetUserPassword(resetUser.id, resetPasswordValue.trim());
      closeResetModal();
      await alert({ title: "Sucesso", message: "Senha redefinida com sucesso." });
    } catch (e) {
      setResetError(e instanceof Error ? e.message : "Erro ao redefinir senha");
    } finally {
      setResetSaving(false);
    }
  }

  async function deleteUser(user: AdminUserRow) {
    const ok = await confirm({
      title: "Excluir usuário",
      message: `Excluir usuário ${user.email}?`,
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    setError("");
    try {
      await api.adminDeleteUser(user.id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao excluir usuário");
    }
  }

  if (loading) {
    return <p className="muted">Carregando usuários…</p>;
  }

  return (
    <>
      <section className="admin-access-requests" aria-labelledby="admin-access-requests-heading">
        <div className="admin-gestao-panel__toolbar">
          <h3 id="admin-access-requests-heading" className="admin-access-requests__title">
            Solicitações de acesso
            {accessRequests.length > 0 && (
              <span className="admin-access-requests__badge">{accessRequests.length}</span>
            )}
          </h3>
        </div>
        <div className="card">
          {accessRequests.length === 0 ? (
            <p className="muted">Nenhuma solicitação pendente.</p>
          ) : (
            <>
              <ul
                className="card-tx-list card-lancamentos-mobile-only"
                aria-label="Solicitações de acesso"
              >
                {accessRequests.map((request) => (
                  <li key={request.id} className="card-tx-item">
                    <div className="card-tx-item-main">
                      <span className="card-tx-desc">{request.username}</span>
                    </div>
                    <p className="muted small" style={{ margin: "0.2rem 0 0", overflowWrap: "anywhere" }}>
                      {request.email}
                    </p>
                    <div className="card-tx-item-actions">
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => void approveRequest(request)}
                      >
                        Aprovar
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => void rejectRequest(request)}
                      >
                        Recusar
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
              <div className="table-scroll-wrap card-lancamentos-desktop-only">
                <table>
                  <thead>
                    <tr>
                      <th>Usuário</th>
                      <th>E-mail</th>
                      <th>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accessRequests.map((request) => (
                      <tr key={request.id}>
                        <td>{request.username}</td>
                        <td>{request.email}</td>
                        <td>
                          <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                            <button
                              type="button"
                              className="btn btn-sm"
                              onClick={() => void approveRequest(request)}
                            >
                              Aprovar
                            </button>
                            <button
                              type="button"
                              className="btn btn-ghost btn-sm"
                              onClick={() => void rejectRequest(request)}
                            >
                              Recusar
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </section>

      <div className="admin-gestao-panel__toolbar" style={{ marginTop: "1.25rem" }}>
        <p className="muted small" style={{ margin: 0 }}>
          Edite login e e-mail, promova administradores, redefina senha e exclua usuários ativos.
        </p>
        <button type="button" className="btn btn-sm" onClick={openCreateModal}>
          Adicionar usuário
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="card">
        {users.length === 0 ? (
          <p className="muted">Nenhum usuário ativo.</p>
        ) : (
          <>
            <ul className="card-tx-list card-lancamentos-mobile-only" aria-label="Usuários">
              {users.map((user) => (
                <li key={user.id} className="card-tx-item">
                  <div className="card-tx-item-main">
                    <span className="card-tx-desc">{user.name}</span>
                    <span className="muted small">{user.is_admin ? "Admin" : "Padrão"}</span>
                  </div>
                  <p className="muted small" style={{ margin: "0.15rem 0 0" }}>
                    @{user.username}
                  </p>
                  <p className="muted small" style={{ margin: "0.2rem 0 0", overflowWrap: "anywhere" }}>
                    {user.email}
                  </p>
                  <div className="card-tx-item-actions">
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => openEditModal(user)}>
                      Editar
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => void toggleAdmin(user)}>
                      {user.is_admin ? "Remover admin" : "Tornar admin"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => openResetModal(user)}
                    >
                      Reset senha
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => void deleteUser(user)}>
                      Excluir
                    </button>
                  </div>
                </li>
              ))}
            </ul>
            <div className="table-scroll-wrap card-lancamentos-desktop-only">
              <table>
                <thead>
                  <tr>
                    <th>Nome</th>
                    <th>Usuário</th>
                    <th>E-mail</th>
                    <th>Perfil</th>
                    <th>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td>{user.name}</td>
                      <td>{user.username}</td>
                      <td>{user.email}</td>
                      <td>{user.is_admin ? "Admin" : "Padrão"}</td>
                      <td>
                        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                          <button type="button" className="btn btn-ghost btn-sm" onClick={() => openEditModal(user)}>
                            Editar
                          </button>
                          <button type="button" className="btn btn-ghost btn-sm" onClick={() => void toggleAdmin(user)}>
                            {user.is_admin ? "Remover admin" : "Tornar admin"}
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => openResetModal(user)}
                          >
                            Reset senha
                          </button>
                          <button type="button" className="btn btn-ghost btn-sm" onClick={() => void deleteUser(user)}>
                            Excluir
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {showCreateModal && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeCreateModal();
          }}
        >
          <div
            className="modal-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-user-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-panel-head">
              <h2 id="create-user-modal-title" className="modal-panel-title">
                Novo usuário
              </h2>
              <button
                type="button"
                className="btn btn-ghost btn-sm modal-close"
                aria-label="Fechar"
                onClick={closeCreateModal}
              >
                ×
              </button>
            </div>
            <form onSubmit={handleCreateUser} className="stack-form modal-panel-form">
              <div className="field">
                <label htmlFor="create-user-username">Usuário (login)</label>
                <input
                  id="create-user-username"
                  value={createUsername}
                  onChange={(e) => setCreateUsername(e.target.value)}
                  required
                  minLength={1}
                  maxLength={64}
                  autoComplete="off"
                />
              </div>
              <div className="field">
                <label htmlFor="create-user-name">Nome</label>
                <input
                  id="create-user-name"
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  required
                  autoComplete="name"
                />
              </div>
              <div className="field">
                <label htmlFor="create-user-email">E-mail</label>
                <input
                  id="create-user-email"
                  type="email"
                  value={createEmail}
                  onChange={(e) => setCreateEmail(e.target.value)}
                  required
                  autoComplete="off"
                />
              </div>
              <div className="field">
                <label htmlFor="create-user-password">Senha inicial</label>
                <input
                  id="create-user-password"
                  type="password"
                  value={createPassword}
                  onChange={(e) => setCreatePassword(e.target.value)}
                  required
                  minLength={6}
                  autoComplete="new-password"
                />
              </div>
              <div className="field">
                <label>
                  <input
                    type="checkbox"
                    checked={createIsAdmin}
                    onChange={(e) => setCreateIsAdmin(e.target.checked)}
                  />{" "}
                  Administrador
                </label>
              </div>
              <div className="field">
                <label>
                  <input
                    type="checkbox"
                    checked={createMustChangePassword}
                    onChange={(e) => setCreateMustChangePassword(e.target.checked)}
                  />{" "}
                  Exigir troca de senha no primeiro acesso
                </label>
              </div>
              {createError && <p className="error">{createError}</p>}
              <div className="modal-panel-actions">
                <button type="submit" className="btn" disabled={createSaving}>
                  {createSaving ? "Criando…" : "Criar usuário"}
                </button>
                <button type="button" className="btn btn-ghost" onClick={closeCreateModal}>
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {editingUser && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeEditModal();
          }}
        >
          <div
            className="modal-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-user-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-panel-head">
              <h2 id="edit-user-modal-title" className="modal-panel-title">
                Editar usuário
              </h2>
              <button
                type="button"
                className="btn btn-ghost btn-sm modal-close"
                aria-label="Fechar"
                onClick={closeEditModal}
              >
                ×
              </button>
            </div>
            <form onSubmit={handleEditUser} className="stack-form modal-panel-form">
              <p className="muted small" style={{ margin: 0 }}>
                {editingUser.name}
              </p>
              <div className="field">
                <label htmlFor="edit-user-username">Usuário (login)</label>
                <input
                  id="edit-user-username"
                  value={editUsername}
                  onChange={(e) => setEditUsername(e.target.value)}
                  required
                  minLength={1}
                  maxLength={64}
                  autoComplete="off"
                />
              </div>
              <div className="field">
                <label htmlFor="edit-user-email">E-mail</label>
                <input
                  id="edit-user-email"
                  type="email"
                  value={editEmail}
                  onChange={(e) => setEditEmail(e.target.value)}
                  required
                  autoComplete="off"
                />
              </div>
              {editError && <p className="error">{editError}</p>}
              <div className="modal-panel-actions">
                <button type="submit" className="btn" disabled={editSaving}>
                  {editSaving ? "Salvando…" : "Salvar"}
                </button>
                <button type="button" className="btn btn-ghost" onClick={closeEditModal}>
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {resetUser && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeResetModal();
          }}
        >
          <div
            className="modal-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="reset-user-password-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-panel-head">
              <h2 id="reset-user-password-modal-title" className="modal-panel-title">
                Redefinir senha
              </h2>
              <button
                type="button"
                className="btn btn-ghost btn-sm modal-close"
                aria-label="Fechar"
                onClick={closeResetModal}
              >
                ×
              </button>
            </div>
            <form onSubmit={handleResetPassword} className="stack-form modal-panel-form">
              <p className="muted small" style={{ margin: 0 }}>
                {resetUser.name} ({resetUser.email})
              </p>
              <div className="field">
                <label htmlFor="reset-user-password">Nova senha</label>
                <input
                  id="reset-user-password"
                  type="password"
                  value={resetPasswordValue}
                  onChange={(e) => setResetPasswordValue(e.target.value)}
                  required
                  minLength={6}
                  autoComplete="new-password"
                  autoFocus
                />
              </div>
              {resetError && <p className="error">{resetError}</p>}
              <div className="modal-panel-actions">
                <button type="submit" className="btn" disabled={resetSaving}>
                  {resetSaving ? "Salvando…" : "Redefinir senha"}
                </button>
                <button type="button" className="btn btn-ghost" onClick={closeResetModal}>
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
