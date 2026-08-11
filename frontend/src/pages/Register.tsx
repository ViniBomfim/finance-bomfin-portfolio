import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api, getToken } from "../api";
import { AuthPageShell } from "../components/AuthPageShell";
import { PasswordField } from "../components/PasswordField";

export function Register() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  if (getToken()) return <Navigate to="/" replace />;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess(false);
    try {
      await api.register(username.trim(), email, password);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no cadastro");
    }
  }

  const hasError = !!error;

  return (
    <AuthPageShell
      title="Criar conta"
      footer={
        <p className="muted auth-page__footer">
          Já tem conta? <Link to="/login">Entrar</Link>
        </p>
      }
    >
      {success ? (
        <p className="auth-page__success" role="status">
          Solicitação enviada. Um administrador precisa aprovar seu acesso antes de você poder entrar.
        </p>
      ) : (
        <form className="auth-form" onSubmit={onSubmit} noValidate>
          <div className={`field${hasError ? " field--error" : ""}`}>
            <label htmlFor="username">Usuário</label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={1}
              maxLength={64}
              aria-invalid={hasError || undefined}
            />
          </div>
          <div className={`field${hasError ? " field--error" : ""}`}>
            <label htmlFor="email">E-mail</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              aria-invalid={hasError || undefined}
            />
          </div>
          <PasswordField
            id="password"
            label="Senha desejada (mín. 6 caracteres)"
            value={password}
            onChange={setPassword}
            autoComplete="new-password"
            required
            minLength={6}
            invalid={hasError}
            errorId="register-error"
          />
          {error && (
            <p id="register-error" className="error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="btn auth-page__submit">
            Cadastrar
          </button>
        </form>
      )}
    </AuthPageShell>
  );
}
