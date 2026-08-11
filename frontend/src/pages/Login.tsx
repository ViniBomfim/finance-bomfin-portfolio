import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { api, getToken, setToken } from "../api";
import { touchSessionActivity } from "../lib/sessionActivity";
import { AuthPageShell } from "../components/AuthPageShell";
import { PasswordField } from "../components/PasswordField";

const REMEMBER_USER_KEY = "fm_remember_username";

export function Login() {
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  const inactivityLogout = searchParams.get("inativo") === "1";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const inFlightRef = useRef(false);
  const requestGenRef = useRef(0);

  useEffect(() => {
    const saved = localStorage.getItem(REMEMBER_USER_KEY);
    if (saved) {
      setUsername(saved);
      setRemember(true);
    }
  }, []);

  if (getToken()) return <Navigate to="/" replace />;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    const gen = ++requestGenRef.current;
    setSubmitting(true);
    setError("");
    try {
      const r = await api.login(username.trim(), password);
      if (gen !== requestGenRef.current) return;
      if (remember) {
        localStorage.setItem(REMEMBER_USER_KEY, username.trim());
      } else {
        localStorage.removeItem(REMEMBER_USER_KEY);
      }
      setToken(r.access_token);
      touchSessionActivity();
      nav("/");
    } catch (err) {
      if (gen !== requestGenRef.current) return;
      setError(err instanceof Error ? err.message : "Falha no login");
    } finally {
      if (gen === requestGenRef.current) {
        inFlightRef.current = false;
        setSubmitting(false);
      }
    }
  }

  const hasError = !!error;

  return (
    <AuthPageShell
      eyebrow="Bem-vindo de volta"
      title="Entrar"
      subtitle="Acesse sua conta para continuar"
      footer={
        <>
          <div className="auth-page__divider">
            <div className="auth-page__div-line" />
            <span className="auth-page__div-txt">Novo por aqui?</span>
            <div className="auth-page__div-line" />
          </div>
          <Link to="/register" className="auth-page__btn-create">
            Criar conta
          </Link>
        </>
      }
    >
      {inactivityLogout && (
        <p className="auth-page__success" role="status">
          Sessão encerrada por inatividade. Entre novamente para continuar.
        </p>
      )}
      <form className="auth-page__form" onSubmit={onSubmit} noValidate>
        <div className={`auth-page__field${hasError ? " auth-page__field--error" : ""}`}>
          <label className="auth-page__field-lbl" htmlFor="username">
            Usuário ou e-mail
          </label>
          <div className="auth-page__field-wrap">
            <input
              id="username"
              className="auth-page__field-input"
              type="text"
              autoComplete="username"
              placeholder="nome.sobrenome ou e-mail"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={1}
              disabled={submitting}
              aria-invalid={hasError || undefined}
              aria-describedby={hasError ? "login-error" : undefined}
            />
          </div>
          <div className="auth-page__field-hint">Formato: nome.sobrenome</div>
        </div>
        <PasswordField
          id="password"
          label="Senha"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
          required
          disabled={submitting}
          invalid={hasError}
          errorId="login-error"
          appearance="auth"
        />
        <div className="auth-page__extras">
          <label className="auth-page__remember">
            <input
              type="checkbox"
              className="auth-page__remember-input"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              disabled={submitting}
            />
            <span className={`auth-page__chk${remember ? " auth-page__chk--on" : ""}`} aria-hidden="true" />
            <span>Lembrar neste dispositivo</span>
          </label>
          <a className="auth-page__forgot" href="#recuperar-senha">
            Esqueceu a senha?
          </a>
        </div>
        {error && (
          <p id="login-error" className="auth-page__error" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          className={`auth-page__btn-enter${submitting ? " auth-page__btn-enter--loading" : ""}`}
          disabled={submitting}
        >
          {submitting ? "Entrando" : "Entrar"}
        </button>
      </form>
    </AuthPageShell>
  );
}
