import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { usePeriod } from "../context/PeriodContext";
import { formatBRL } from "../money";
import type { DashboardSummary } from "../types";

const PERSON_GRADIENTS = [
  "linear-gradient(135deg,#f43f5e,#a855f7)",
  "linear-gradient(135deg,#3b82f6,#22d3ee)",
  "linear-gradient(135deg,#22c55e,#16a34a)",
  "linear-gradient(135deg,#f59e0b,#ef4444)",
  "linear-gradient(135deg,#a78bfa,#6366f1)",
  "linear-gradient(135deg,#14b8a6,#0ea5e9)",
];

function normalizePersonName(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function isUnassignedPerson(value?: string | null) {
  if (!value) return true;
  const normalized = normalizePersonName(value);
  return normalized.length === 0 || normalized.includes("sem pessoa") || normalized.includes("nao informado");
}

function isMePerson(value: string) {
  const normalized = normalizePersonName(value);
  return normalized === "eu" || normalized.startsWith("eu ") || normalized.includes("(eu)");
}

function personInitial(name: string): string {
  const trimmed = name.trim();
  return trimmed ? trimmed.charAt(0).toUpperCase() : "?";
}

function personGradient(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash + name.charCodeAt(i) * (i + 1)) % PERSON_GRADIENTS.length;
  }
  return PERSON_GRADIENTS[hash] ?? PERSON_GRADIENTS[0];
}

function capitalizePeriodLabel(label: string) {
  if (!label) return label;
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function PersonUsageList() {
  const navigate = useNavigate();
  const { periodId, ready, monthLabel, currentPeriod } = usePeriod();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!periodId) return;
    let cancelled = false;
    (async () => {
      try {
        if (!cancelled) setError("");
        const s = await api.dashboardSummary(periodId);
        if (!cancelled) setSummary(s);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Erro ao carregar pessoas");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [periodId]);

  const sortedUsageByPerson = useMemo(
    () =>
      summary
        ? [...summary.usage_by_person_cards]
            .filter((row) => row.pessoa_id && !isUnassignedPerson(row.pessoa_nome))
            .sort((a, b) => {
              const aIsMe = isMePerson(a.pessoa_nome);
              const bIsMe = isMePerson(b.pessoa_nome);
              if (aIsMe && !bIsMe) return -1;
              if (!aIsMe && bIsMe) return 1;
              return parseFloat(b.total_geral) - parseFloat(a.total_geral);
            })
        : [],
    [summary],
  );

  const usageByPersonTotal = useMemo(
    () => sortedUsageByPerson.reduce((acc, row) => acc + parseFloat(row.total_geral), 0),
    [sortedUsageByPerson],
  );

  const periodTitle =
    currentPeriod != null
      ? capitalizePeriodLabel(monthLabel(currentPeriod.mes, currentPeriod.ano))
      : "";

  if (!ready) return null;

  if (error && !summary) {
    return (
      <div className="padded dashboard-page person-detail-page">
        <p className="error">{error}</p>
      </div>
    );
  }

  const peopleMeta =
    sortedUsageByPerson.length > 0
      ? `${sortedUsageByPerson.length} pessoa${sortedUsageByPerson.length === 1 ? "" : "s"} · ${formatBRL(usageByPersonTotal)}`
      : "";

  return (
    <div className="padded dashboard-page person-detail-page">
      <header className="pd-detail-header">
        <button type="button" className="pd-detail-back" onClick={() => navigate("/")}>
          ← Voltar
        </button>
        <div className="pd-detail-person-row">
          <div className="pd-detail-av" style={{ background: PERSON_GRADIENTS[1] }}>
            👥
          </div>
          <div>
            <h1 className="pd-detail-name">Pessoas</h1>
            <div className="pd-detail-sub">
              {[peopleMeta, periodTitle.toLowerCase()].filter(Boolean).join(" · ")}
            </div>
          </div>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      {sortedUsageByPerson.length === 0 ? (
        <p className="muted" style={{ padding: "0 1rem" }}>
          Sem uso por pessoa neste período.
        </p>
      ) : (
        <div className="db-pessoas-list">
          {sortedUsageByPerson.map((row) => (
            <Link
              key={row.pessoa_id ?? row.pessoa_nome}
              className="db-pessoa-item"
              to={`/dashboard/uso-pessoa/${encodeURIComponent(row.pessoa_id ?? row.pessoa_nome)}`}
            >
              <div className="db-pessoa-av" style={{ background: personGradient(row.pessoa_nome) }}>
                {personInitial(row.pessoa_nome)}
              </div>
              <div className="db-pessoa-info">
                <div className="db-pessoa-name">{row.pessoa_nome}</div>
                <div className="db-pessoa-sub">Cartões · Fixos · Devedores</div>
              </div>
              <div className="db-pessoa-val">{formatBRL(row.total_geral)}</div>
              <span className="db-pessoa-chev">›</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
