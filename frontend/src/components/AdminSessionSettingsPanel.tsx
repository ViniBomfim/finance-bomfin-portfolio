import { useEffect, useState } from "react";
import { api } from "../api";
import type { SessionSettingsDefaults, SessionSettingsResponse } from "../types";

function formatDuration(minutes: number): string {
  if (minutes < 60) {
    return `${minutes} minuto${minutes === 1 ? "" : "s"}`;
  }
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (rest === 0) {
    return `${hours} hora${hours === 1 ? "" : "s"}`;
  }
  return `${hours}h ${rest}min`;
}

export function AdminSessionSettingsPanel() {
  const [limits, setLimits] = useState<SessionSettingsDefaults | null>(null);
  const [enabled, setEnabled] = useState(true);
  const [minutes, setMinutes] = useState(60);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const [settings, lim] = await Promise.all([
          api.adminSessionSettings(),
          api.adminSessionSettingsLimits(),
        ]);
        if (!cancelled) {
          setEnabled(settings.inactivity_logout_enabled);
          setMinutes(settings.inactivity_logout_minutes);
          setLimits(lim);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Erro ao carregar configurações");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const updated: SessionSettingsResponse = await api.adminUpdateSessionSettings({
        inactivity_logout_enabled: enabled,
        inactivity_logout_minutes: minutes,
      });
      setEnabled(updated.inactivity_logout_enabled);
      setMinutes(updated.inactivity_logout_minutes);
      if (updated.inactivity_logout_enabled) {
        setSuccess(
          `Logout por inatividade ativo: ${formatDuration(updated.inactivity_logout_minutes)} sem interação.`,
        );
      } else {
        setSuccess("Logout por inatividade desativado.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="muted">Carregando configurações de sessão…</p>;
  }

  const min = limits?.min_inactivity_logout_minutes ?? 1;
  const max = limits?.max_inactivity_logout_minutes ?? 10080;
  const defaultMinutes = limits?.default_inactivity_logout_minutes ?? 60;

  return (
    <form className="admin-session-settings card" onSubmit={onSave}>
      <p className="admin-section__lead muted small">
        Quando ativo, o usuário é desconectado após o tempo configurado sem interação (mouse,
        teclado ou toque). Um minuto antes do logout, aparece um aviso com contagem regressiva e a
        opção de continuar a sessão. O padrão da plataforma é {formatDuration(defaultMinutes)}.
      </p>

      <label className="admin-session-settings__toggle">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        <span>Ativar logout por inatividade</span>
      </label>

      <div className="field">
        <label htmlFor="inactivity-minutes">Tempo de inatividade (minutos)</label>
        <input
          id="inactivity-minutes"
          type="number"
          min={min}
          max={max}
          step={1}
          value={minutes}
          onChange={(e) => setMinutes(Number(e.target.value))}
          required
          disabled={!enabled}
        />
        <p className="muted small" style={{ margin: "0.35rem 0 0" }}>
          {enabled
            ? `Entre ${min} e ${max} minutos (${formatDuration(minutes)}).`
            : "O tempo permanece salvo e será usado ao reativar a funcionalidade."}
        </p>
      </div>

      {error && <p className="error">{error}</p>}
      {success && <p className="muted small">{success}</p>}

      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? "Salvando…" : "Salvar"}
        </button>
      </div>
    </form>
  );
}
