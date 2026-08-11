import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAppDialog } from "../context/DialogContext";
import { usePeriod } from "../context/PeriodContext";
import { formatBRL } from "../money";
import type {
  Period,
  SpenderRow,
  TripCategory,
  TripExpenseRow,
  TripPaymentMethod,
  TripRow,
  TripSettlementRow,
  TripStatus,
} from "../types";

const CATEGORY_LABEL: Record<TripCategory, string> = {
  hotel: "Hospedagem",
  transport: "Passagem / Transporte",
  tour: "Passeios",
  meal: "Refeição",
  shopping: "Compras",
  leisure: "Lazer",
  other: "Outros",
};

type SaldoDisplayRow = {
  spender_id: string;
  spender_nome: string;
  total_pago: string;
  total_consumido: string;
  saldo: string;
};

function SaldoTable({ rows }: { rows: SaldoDisplayRow[] }) {
  return (
    <>
      <ul className="card-tx-list card-lancamentos-mobile-only" aria-label="Saldos por pessoa">
        {rows.map((row) => {
          const saldo = parseFloat(row.saldo);
          return (
            <li key={row.spender_id} className="card-tx-item">
              <div className="card-tx-item-main">
                <span className="card-tx-desc">{row.spender_nome}</span>
                <span
                  className={`card-tx-val${saldo > 0 ? " positive" : saldo < 0 ? " negative" : ""}`}
                >
                  {formatBRL(row.saldo)}
                </span>
              </div>
              <div className="card-tx-item-meta muted small">
                <span>Pagou {formatBRL(row.total_pago)}</span>
                <span>Consumiu {formatBRL(row.total_consumido)}</span>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="trip-table-wrap card-lancamentos-desktop-only">
        <table className="trip-table">
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>Pessoa</th>
              <th style={{ textAlign: "right" }}>Pagou</th>
              <th style={{ textAlign: "right" }}>Consumiu</th>
              <th style={{ textAlign: "right" }}>Saldo</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const saldo = parseFloat(row.saldo);
              return (
                <tr key={row.spender_id}>
                  <td>{row.spender_nome}</td>
                  <td style={{ textAlign: "right" }}>{formatBRL(row.total_pago)}</td>
                  <td style={{ textAlign: "right" }}>{formatBRL(row.total_consumido)}</td>
                  <td
                    style={{ textAlign: "right" }}
                    className={saldo > 0 ? "trip-amount--pos" : saldo < 0 ? "trip-amount--neg" : undefined}
                  >
                    {formatBRL(row.saldo)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

const CATEGORY_COLOR: Record<TripCategory, string> = {
  hotel: "#1d9bf0",
  transport: "#22c55e",
  tour: "#a855f7",
  meal: "#f59e0b",
  shopping: "#ef4444",
  leisure: "#ec4899",
  other: "#94a3b8",
};

const PAYMENT_LABEL: Record<TripPaymentMethod, string> = {
  cash: "Dinheiro",
  card: "Cartão",
  transfer: "Transferência",
  other: "Outro",
};

const STATUS_LABEL: Record<TripStatus, string> = {
  planning: "Planejada",
  ongoing: "Em andamento",
  closed: "Encerrada",
};

const CATEGORY_OPTIONS: TripCategory[] = [
  "hotel",
  "transport",
  "tour",
  "meal",
  "shopping",
  "leisure",
  "other",
];

const PAYMENT_OPTIONS: TripPaymentMethod[] = ["cash", "card", "transfer", "other"];

type Tab = "summary" | "expenses" | "settlement" | "participants";

function formatDateBR(value: string | null): string {
  if (!value) return "—";
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("pt-BR");
}

function normalizeDecimal(value: string): string {
  return value.trim().replace(",", ".");
}

export function TripDetail() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const { periods, monthLabel } = usePeriod();
  const { alert } = useAppDialog();
  const [trip, setTrip] = useState<TripRow | null>(null);
  const [expenses, setExpenses] = useState<TripExpenseRow[]>([]);
  const [settlement, setSettlement] = useState<TripSettlementRow | null>(null);
  const [spenders, setSpenders] = useState<SpenderRow[]>([]);
  const [meSpenderId, setMeSpenderId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function reload() {
    try {
      setLoading(true);
      setError("");
      const [t, exps, s, me] = await Promise.all([
        api.getTrip(id),
        api.listTripExpenses(id),
        api.listSpenders(),
        api.getMe(),
      ]);
      setTrip(t);
      setExpenses(exps);
      setSpenders(s);
      setMeSpenderId(me.me_spender_id ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar viagem");
    } finally {
      setLoading(false);
    }
  }

  async function reloadSettlement() {
    if (!id) return;
    try {
      const s = await api.tripSettlement(id);
      setSettlement(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao calcular acerto");
    }
  }

  useEffect(() => {
    reload();
  }, [id]);

  useEffect(() => {
    if (tab === "settlement") reloadSettlement();
  }, [tab, expenses.length]);

  if (loading || !trip) {
    return (
      <div className="padded trip-page">
        <p className="muted">Carregando viagem…</p>
        {error && <p className="error">{error}</p>}
      </div>
    );
  }

  const closed = trip.status === "closed";

  async function handleStatusChange(next: TripStatus) {
    try {
      await api.updateTrip(trip!.id, { status: next });
      await reload();
    } catch (e) {
      await alert(e instanceof Error ? e.message : "Erro ao atualizar status");
    }
  }

  return (
    <div className="padded trip-page">
      <header className="page-head">
        <button type="button" className="btn btn-ghost" onClick={() => nav("/viagens")}>
          ← Viagens
        </button>
        <div style={{ flex: 1 }} />
        <select
          value={trip.status}
          onChange={(e) => handleStatusChange(e.target.value as TripStatus)}
          aria-label="Status da viagem"
        >
          {(Object.keys(STATUS_LABEL) as TripStatus[]).map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>
      </header>

      <div className="trip-section trip-section--hero">
        <h1 className="trip-section__title--hero">{trip.nome}</h1>
        <p className="trip-section__lead muted" style={{ marginBottom: 0 }}>
          {trip.destino || "Sem destino"} · {formatDateBR(trip.data_inicio)} →{" "}
          {formatDateBR(trip.data_fim)} · Moeda base: {trip.moeda_base}
        </p>
      </div>

      <nav className="trip-page-tabs" aria-label="Seções da viagem">
        {(
          [
            ["summary", "Resumo"],
            ["expenses", "Gastos"],
            ["settlement", "Acerto de contas"],
            ["participants", "Participantes"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`trip-page-tabs__btn${tab === key ? " trip-page-tabs__btn--active" : ""}`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {tab === "summary" && <SummaryTab trip={trip} meSpenderId={meSpenderId} />}
      {tab === "expenses" && (
        <ExpensesTab
          trip={trip}
          expenses={expenses}
          meSpenderId={meSpenderId}
          periods={periods}
          monthLabel={monthLabel}
          closed={closed}
          onChanged={reload}
        />
      )}
      {tab === "settlement" && (
        <SettlementTab settlement={settlement} moedaBase={trip.moeda_base} />
      )}
      {tab === "participants" && (
        <ParticipantsTab
          trip={trip}
          spenders={spenders}
          closed={closed}
          onChanged={reload}
        />
      )}
    </div>
  );
}

function SummaryTab({ trip, meSpenderId }: { trip: TripRow; meSpenderId: string | null }) {
  const [openBreakdownId, setOpenBreakdownId] = useState<string | null>(null);
  const consumoRows = trip.consumo_por_pessoa ?? [];
  const euSpenderInTrip = Boolean(
    meSpenderId && trip.participants.some((p) => p.spender_id === meSpenderId),
  );
  const euBreakdown = meSpenderId
    ? consumoRows.find((r) => r.spender_id === meSpenderId)
    : undefined;
  const consumoEuNum = euBreakdown ? parseFloat(euBreakdown.total) : 0;

  const totalGastoTrip = parseFloat(trip.total_gasto || "0");
  const orcado = trip.orcamento_total ? parseFloat(trip.orcamento_total) : 0;

  const saldoRows = trip.total_por_pessoa.filter((row) => {
    const totalPago = parseFloat(row.total_pago || "0");
    const totalConsumido = parseFloat(row.total_consumido || "0");
    const saldo = parseFloat(row.saldo || "0");
    return Math.abs(totalPago) > 0.009 || Math.abs(totalConsumido) > 0.009 || Math.abs(saldo) > 0.009;
  });

  const dias =
    trip.data_inicio && trip.data_fim
      ? Math.max(
          1,
          Math.round(
            (new Date(`${trip.data_fim}T00:00:00`).getTime() -
              new Date(`${trip.data_inicio}T00:00:00`).getTime()) /
              86_400_000,
          ) + 1,
        )
      : 0;

  const custoDiaEu = euSpenderInTrip && dias > 0 ? consumoEuNum / dias : 0;
  const restanteOrcamento =
    euSpenderInTrip && orcado > 0 ? orcado - consumoEuNum : null;

  return (
    <div className="trip-page">
      <div className="trip-section">
        <div
          className={
            restanteOrcamento !== null
              ? "trip-kpi-strip trip-kpi-strip--4"
              : "trip-kpi-strip trip-kpi-strip--3"
          }
        >
          <KPI
            label="Total gasto"
            value={euSpenderInTrip ? formatBRL(consumoEuNum) : "—"}
          />
          <KPI label="Orçamento" value={orcado > 0 ? formatBRL(orcado) : "—"} />
          {restanteOrcamento !== null && (
            <KPI
              label="Disponível"
              value={formatBRL(restanteOrcamento)}
              valueClassName={restanteOrcamento < 0 ? "trip-kpi__value--warn" : undefined}
            />
          )}
          <KPI
            label={`Custo / dia${dias > 0 ? ` (${dias} dias)` : ""}`}
            value={euSpenderInTrip && dias > 0 ? formatBRL(custoDiaEu) : "—"}
          />
        </div>
      </div>

      {(!meSpenderId || !euSpenderInTrip) && (
        <div className="trip-section">
          <p className="muted" style={{ margin: 0 }}>
            {!meSpenderId ? (
              <>
                Indique <strong>quem é você</strong> no perfil para ver totais pessoais neste resumo.
              </>
            ) : (
              <>
                Adicione <strong>você</strong> em <strong>Participantes</strong> desta viagem para
                acompanhar seu consumo aqui.
              </>
            )}
          </p>
        </div>
      )}

      {consumoRows.length > 0 && (
        <section className="trip-section">
          <h2 className="trip-section__title">Custo por pessoa (consumo na viagem)</h2>
          <p className="trip-section__lead muted">
            Parte de cada um nas divisões dos gastos, em {trip.moeda_base}. Custo/dia usa a duração da
            viagem.
          </p>
          <ul className="trip-section__stack" style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {consumoRows.map((row) => {
              const total = parseFloat(row.total);
              const porDia = dias > 0 ? total / dias : 0;
              return (
                <li key={row.spender_id} className="trip-list-row">
                  <span>{row.spender_nome}</span>
                  <span style={{ textAlign: "right" }}>
                    <strong>{formatBRL(total)}</strong>
                    {dias > 0 && (
                      <span className="muted" style={{ marginLeft: 8, fontSize: 13 }}>
                        ({formatBRL(porDia)} / dia)
                      </span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section className="trip-section">
        <h2 className="trip-section__title">Gasto por categoria (viagem)</h2>
        {trip.total_por_categoria.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            Nenhum gasto lançado ainda.
          </p>
        ) : (
          <ul className="trip-section__stack" style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {trip.total_por_categoria.map((row) => {
              const valor = parseFloat(row.total);
              const pctRow = totalGastoTrip > 0 ? (valor / totalGastoTrip) * 100 : 0;
              return (
                <li key={row.categoria}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginBottom: 2,
                    }}
                  >
                    <span>{CATEGORY_LABEL[row.categoria]}</span>
                    <span>
                      {formatBRL(valor)} ({pctRow.toFixed(0)}%)
                    </span>
                  </div>
                  <div className="trip-progress-track">
                    <div
                      className="trip-progress-fill"
                      style={{
                        width: `${pctRow}%`,
                        background: CATEGORY_COLOR[row.categoria],
                      }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="trip-section">
        <h2 className="trip-section__title">Gasto por pessoa (por categoria)</h2>
        {consumoRows.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            Nenhum consumo registrado nas divisões ainda.
          </p>
        ) : (
          <ul className="trip-section__stack" style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {consumoRows.map((row) => {
              const open = openBreakdownId === row.spender_id;
              const total = parseFloat(row.total);
              return (
                <li key={row.spender_id} className="trip-list-row trip-list-row--expandable">
                  <button
                    type="button"
                    className="trip-list-row__toggle"
                    onClick={() =>
                      setOpenBreakdownId((id) => (id === row.spender_id ? null : row.spender_id))
                    }
                  >
                    <span>
                      <strong>{row.spender_nome}</strong>
                      <span className="muted" style={{ marginLeft: 8, fontSize: 13 }}>
                        {open ? "▼" : "▶"}
                      </span>
                    </span>
                    <span style={{ fontWeight: 600 }}>{formatBRL(total)}</span>
                  </button>
                  {open && (
                    <ul className="trip-list-row__body">
                      {row.por_categoria.map((line) => (
                        <li key={line.categoria}>
                          <span>{CATEGORY_LABEL[line.categoria]}</span>
                          <span>{formatBRL(parseFloat(line.total))}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="trip-section">
        <h2 className="trip-section__title">Saldos (quem pagou vs consumiu)</h2>
        <p className="trip-section__lead muted">
          Para sugestões de transferências, abra a aba <strong>Acerto de contas</strong>.
        </p>
        {saldoRows.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            Sem movimentação para exibir.
          </p>
        ) : (
          <SaldoTable rows={saldoRows} />
        )}
      </section>
    </div>
  );
}

function KPI({
  label,
  value,
  valueClassName,
}: {
  label: string;
  value: ReactNode;
  valueClassName?: string;
}) {
  return (
    <div className="trip-kpi-cell">
      <div className="trip-kpi__label">{label}</div>
      <div className={`trip-kpi__value${valueClassName ? ` ${valueClassName}` : ""}`}>{value}</div>
    </div>
  );
}

type ExpensesTabProps = {
  trip: TripRow;
  expenses: TripExpenseRow[];
  meSpenderId: string | null;
  periods: Period[];
  monthLabel: (mes: number, ano: number) => string;
  closed: boolean;
  onChanged: () => Promise<void>;
};

function ExpensesTab({
  trip,
  expenses,
  meSpenderId,
  periods,
  monthLabel,
  closed,
  onChanged,
}: ExpensesTabProps) {
  const { confirm, alert } = useAppDialog();
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  const [descricao, setDescricao] = useState("");
  const [valor, setValor] = useState("");
  const [data, setData] = useState(() => new Date().toISOString().slice(0, 10));
  const [categoria, setCategoria] = useState<TripCategory>("meal");
  const [paidBy, setPaidBy] = useState("");
  const [forma, setForma] = useState<TripPaymentMethod>("cash");
  const [observacao, setObservacao] = useState("");
  const [splitMode, setSplitMode] = useState<"none" | "even" | "custom">("none");
  const [splitRecipients, setSplitRecipients] = useState<string[]>([]);
  const [customShares, setCustomShares] = useState<Record<string, string>>({});
  const payerOptions = useMemo(() => {
    const rows = trip.participants.map((participant) => ({
      id: participant.spender_id,
      nome:
        meSpenderId && participant.spender_id === meSpenderId
          ? `${participant.spender_nome} (Eu)`
          : participant.spender_nome,
      isMe: Boolean(meSpenderId && participant.spender_id === meSpenderId),
    }));
    rows.sort((a, b) =>
      a.isMe === b.isMe ? a.nome.localeCompare(b.nome, "pt-BR") : a.isMe ? -1 : 1,
    );
    return rows;
  }, [trip.participants, meSpenderId]);
  const effectiveMeSpenderId =
    meSpenderId && trip.participants.some((p) => p.spender_id === meSpenderId) ? meSpenderId : null;
  const canUseSplitUi = Boolean(effectiveMeSpenderId);

  function normalizeSplitRecipients(ids: string[]): string[] {
    const validIds = new Set(payerOptions.map((p) => p.id));
    const unique = Array.from(new Set(ids)).filter((id) => validIds.has(id));
    if (!effectiveMeSpenderId || unique.length === 0) return unique;
    if (!unique.includes(effectiveMeSpenderId)) {
      return [effectiveMeSpenderId, ...unique];
    }
    return unique;
  }

  function handleSplitModeChange(next: "none" | "even" | "custom") {
    if (next === "none") {
      setSplitMode("none");
      setSplitRecipients([]);
      return;
    }
    if (splitMode === "none") {
      if (effectiveMeSpenderId && paidBy && paidBy !== effectiveMeSpenderId) {
        setSplitRecipients(normalizeSplitRecipients([effectiveMeSpenderId, paidBy]));
      } else if (effectiveMeSpenderId) {
        setSplitRecipients([effectiveMeSpenderId]);
      } else if (paidBy) {
        setSplitRecipients([paidBy]);
      }
    }
    setSplitMode(next);
  }

  useEffect(() => {
    if (paidBy && !payerOptions.some((p) => p.id === paidBy)) {
      setPaidBy("");
    }
  }, [payerOptions, paidBy]);

  useEffect(() => {
    if (paidBy) return;
    if (effectiveMeSpenderId) {
      setPaidBy(effectiveMeSpenderId);
      return;
    }
    if (payerOptions.length > 0) {
      setPaidBy(payerOptions[0].id);
    }
  }, [paidBy, effectiveMeSpenderId, payerOptions]);

  useEffect(() => {
    const validIds = new Set(trip.participants.map((p) => p.spender_id));
    setCustomShares((prev) =>
      Object.fromEntries(Object.entries(prev).filter(([spenderId]) => validIds.has(spenderId))),
    );
  }, [trip.participants]);

  useEffect(() => {
    setSplitRecipients((prev) => normalizeSplitRecipients(prev));
  }, [payerOptions, effectiveMeSpenderId]);

  function resetForm() {
    setDescricao("");
    setValor("");
    setData(new Date().toISOString().slice(0, 10));
    setCategoria("meal");
    setPaidBy(effectiveMeSpenderId ?? "");
    setForma("cash");
    setObservacao("");
    setSplitMode("none");
    setSplitRecipients([]);
    setCustomShares({});
    setFormError("");
  }

  function toggleSplitRecipient(spenderId: string) {
    if (splitMode !== "none" && effectiveMeSpenderId && spenderId === effectiveMeSpenderId) {
      return;
    }
    setSplitRecipients((prev) => {
      const next = normalizeSplitRecipients(
        prev.includes(spenderId) ? prev.filter((id) => id !== spenderId) : [...prev, spenderId],
      );
      return next;
    });
  }

  useEffect(() => {
    if (splitMode === "none") return;
    if (splitRecipients.length > 0) {
      setSplitRecipients((prev) => normalizeSplitRecipients(prev));
      return;
    }
    if (effectiveMeSpenderId) {
      setSplitRecipients([effectiveMeSpenderId]);
      return;
    }
    if (paidBy) setSplitRecipients([paidBy]);
  }, [splitMode, splitRecipients.length, effectiveMeSpenderId, paidBy]);

  useEffect(() => {
    if (!effectiveMeSpenderId && splitMode !== "none") {
      setSplitMode("none");
      setSplitRecipients([]);
    }
  }, [effectiveMeSpenderId, splitMode]);

  useEffect(() => {
    if (splitMode === "none" || !paidBy) return;
    setSplitRecipients((prev) => {
      const n = normalizeSplitRecipients(prev);
      if (n.includes(paidBy)) return n;
      return normalizeSplitRecipients([...n, paidBy]);
    });
  }, [paidBy, splitMode]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    const effectivePaidBy = paidBy || effectiveMeSpenderId || "";
    if (!valor || !descricao || !effectivePaidBy) {
      setFormError("Preencha descrição e valor, e defina quem pagou (ou indique você no perfil).");
      return;
    }
    const totalNum = parseFloat(normalizeDecimal(valor));
    if (!Number.isFinite(totalNum) || totalNum <= 0) {
      setFormError("Valor inválido.");
      return;
    }

    const recipients = normalizeSplitRecipients(splitRecipients);
    const splitOwner = effectiveMeSpenderId || effectivePaidBy;
    if (!splitOwner) {
      setFormError("Indique quem é você entre os participantes para usar divisão de gastos.");
      return;
    }

    let shares: { spender_id: string; valor: string }[] | null = null;
    try {
      if (splitMode === "none") {
        shares = [{ spender_id: splitOwner, valor: totalNum.toFixed(2) }];
      } else if (splitMode === "custom") {
        if (recipients.length === 0) {
          setFormError("Selecione pelo menos uma pessoa para dividir.");
          return;
        }
        const entries = recipients
          .map((sid) => ({ spender_id: sid, valor: normalizeDecimal(customShares[sid] ?? "") }))
          .map((row) => ({ ...row, parsed: parseFloat(row.valor) }));
        if (entries.some((row) => !row.valor || !Number.isFinite(row.parsed) || row.parsed <= 0)) {
          setFormError("Preencha valores válidos para todas as pessoas selecionadas.");
          return;
        }
        const sum = entries.reduce((acc, row) => acc + row.parsed, 0);
        if (Math.abs(sum - totalNum) > 0.02) {
          setFormError(
            `Soma das partes (${formatBRL(sum)}) precisa bater com o total (${formatBRL(totalNum)}).`,
          );
          return;
        }
        shares = entries.map(({ spender_id, valor: value }) => ({ spender_id, valor: value }));
      } else {
        if (recipients.length === 0) {
          setFormError("Selecione pelo menos uma pessoa para dividir.");
          return;
        }
        const per = totalNum / recipients.length;
        shares = recipients.map((sid, i) => ({
          spender_id: sid,
          valor:
            i === recipients.length - 1
              ? (totalNum - per * (recipients.length - 1)).toFixed(2)
              : per.toFixed(2),
        }));
      }
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Erro ao preparar divisão do gasto.");
      return;
    }

    setSaving(true);
    try {
      await api.createTripExpense(trip.id, {
        descricao: descricao.trim(),
        valor: normalizeDecimal(valor),
        data,
        categoria,
        paid_by_spender_id: effectivePaidBy,
        forma_pagamento: forma,
        observacao: observacao.trim() || null,
        shares,
      });
      resetForm();
      setShowForm(false);
      await onChanged();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Erro ao salvar gasto");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(expenseId: string) {
    const ok = await confirm({
      title: "Excluir gasto",
      message: "Excluir este gasto?",
      confirmLabel: "Excluir",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.deleteTripExpense(expenseId);
      await onChanged();
    } catch (e) {
      await alert(e instanceof Error ? e.message : "Erro ao excluir");
    }
  }

  async function handlePushToMonth(expense: TripExpenseRow) {
    if (periods.length === 0) {
      await alert("Crie períodos antes de empurrar para o mês.");
      return;
    }
    const choices = periods
      .map((p, idx) => `${idx + 1}) ${monthLabel(p.mes, p.ano)} (${p.id.slice(0, 6)})`)
      .join("\n");
    const answer = window.prompt(
      `Empurrar "${expense.descricao}" para qual mês?\n${choices}\n\nDigite o número:`,
    );
    const idx = answer ? parseInt(answer, 10) - 1 : -1;
    if (idx < 0 || idx >= periods.length) return;
    const periodId = periods[idx].id;
    const pago = await confirm({
      title: "Marcar como pago",
      message: "Marcar essa despesa como já paga no mês?",
      confirmLabel: "Sim, já pago",
      cancelLabel: "Não, pendente",
    });
    try {
      await api.pushTripExpenseToMonth(expense.id, { period_id: periodId, pago });
      await onChanged();
    } catch (e) {
      await alert(e instanceof Error ? e.message : "Erro ao empurrar para o mês");
    }
  }

  const sortedExpenses = useMemo(
    () => [...expenses].sort((a, b) => b.data.localeCompare(a.data)),
    [expenses],
  );

  return (
    <div className="trip-page">
      {!closed && (
        <button
          type="button"
          className="btn"
          onClick={() => {
            setShowForm((v) => !v);
            if (showForm) resetForm();
          }}
        >
          {showForm ? "Cancelar" : "Novo gasto"}
        </button>
      )}

      {showForm && !closed && (
        <div className="trip-section">
          <h2 className="trip-section__title">Novo gasto</h2>
          <form onSubmit={handleCreate}>
            <div className="field">
              <label htmlFor="te-desc">Descrição</label>
              <input
                id="te-desc"
                value={descricao}
                onChange={(e) => setDescricao(e.target.value)}
                required
              />
            </div>
            <div style={{ display: "flex", gap: 12 }}>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="te-val">Valor (R$)</label>
                <input
                  id="te-val"
                  inputMode="decimal"
                  placeholder="0,00"
                  value={valor}
                  onChange={(e) => setValor(e.target.value)}
                  required
                />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="te-data">Data</label>
                <input
                  id="te-data"
                  type="date"
                  value={data}
                  onChange={(e) => setData(e.target.value)}
                  required
                />
              </div>
            </div>
            <div style={{ display: "flex", gap: 12 }}>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="te-cat">Categoria</label>
                <select
                  id="te-cat"
                  value={categoria}
                  onChange={(e) => setCategoria(e.target.value as TripCategory)}
                >
                  {CATEGORY_OPTIONS.map((c) => (
                    <option key={c} value={c}>
                      {CATEGORY_LABEL[c]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label htmlFor="te-forma">Forma de pagamento</label>
                <select
                  id="te-forma"
                  value={forma}
                  onChange={(e) => setForma(e.target.value as TripPaymentMethod)}
                >
                  {PAYMENT_OPTIONS.map((p) => (
                    <option key={p} value={p}>
                      {PAYMENT_LABEL[p]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="field">
              <div className="trip-expense-pay-split">
                <section
                  className="trip-expense-pay-split__section"
                  aria-labelledby="trip-pay-split-payer-heading"
                >
                  <h3 id="trip-pay-split-payer-heading" className="trip-expense-pay-split__title">
                    Quem pagou
                  </h3>
                  <p className="trip-expense-pay-split__sub muted">
                    Quem desembolsou o valor total. Independe da divisão do consumo abaixo.
                  </p>
                  <select
                    id="te-paid"
                    aria-labelledby="trip-pay-split-payer-heading"
                    value={paidBy}
                    onChange={(e) => setPaidBy(e.target.value)}
                  >
                    {payerOptions.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.nome}
                      </option>
                    ))}
                    <option value="" disabled>
                      {payerOptions.length === 0 ? "Sem pessoas cadastradas" : "Selecione..."}
                    </option>
                  </select>
                  <details className="trip-expense-pay-split__details">
                    <summary>Como adicionar pessoas à viagem?</summary>
                    <p className="muted">
                      Use a aba <strong>Participantes</strong> e selecione em{" "}
                      <strong>Cartões → Pessoas</strong>.
                    </p>
                  </details>
                </section>

                {canUseSplitUi && (
                  <>
                    <hr className="trip-expense-pay-split__divider" />
                    <section
                      className="trip-expense-pay-split__section"
                      aria-labelledby="trip-pay-split-div-heading"
                    >
                      <h3 id="trip-pay-split-div-heading" className="trip-expense-pay-split__title">
                        Dividir o consumo
                      </h3>
                      <p className="trip-expense-pay-split__sub muted">
                        Quem entra na conta deste gasto.
                      </p>

                      <fieldset className="trip-split-segment">
                        <legend className="trip-split-segment__legend">Modo de divisão</legend>
                        <div className="trip-split-segment__inner">
                          <label className="trip-split-segment__item">
                            <input
                              type="radio"
                              name="splitmode"
                              checked={splitMode === "none"}
                              onChange={() => handleSplitModeChange("none")}
                            />
                            Não dividir
                          </label>
                          <label className="trip-split-segment__item">
                            <input
                              type="radio"
                              name="splitmode"
                              checked={splitMode === "even"}
                              onChange={() => handleSplitModeChange("even")}
                            />
                            Igualitária
                          </label>
                          <label className="trip-split-segment__item">
                            <input
                              type="radio"
                              name="splitmode"
                              checked={splitMode === "custom"}
                              onChange={() => handleSplitModeChange("custom")}
                            />
                            Personalizada
                          </label>
                        </div>
                      </fieldset>

                      {splitMode === "none" ? (
                        <p className="trip-expense-pay-split__hint muted">
                          Sem dividir, todo o consumo fica <strong>com você</strong>. O pagador
                          continua sendo quem você escolheu acima.
                        </p>
                      ) : (
                        <div>
                          {paidBy && !normalizeSplitRecipients(splitRecipients).includes(paidBy) && (
                            <p className="trip-pay-split-callout error" role="alert">
                              <strong>
                                {payerOptions.find((p) => p.id === paidBy)?.nome ?? "Quem pagou"}
                              </strong>{" "}
                              desembolsou, mas não está entre os participantes — marque essa pessoa nos
                              chips.
                            </p>
                          )}
                          <div className="trip-split-chip-row">
                            {payerOptions.map((p) => {
                              const checked = splitRecipients.includes(p.id);
                              const lockMe = Boolean(
                                splitMode !== "none" &&
                                  effectiveMeSpenderId &&
                                  p.id === effectiveMeSpenderId,
                              );
                              return (
                                <label
                                  key={p.id}
                                  className={`trip-split-chip${checked ? " trip-split-chip--active" : ""}${lockMe ? " trip-split-chip--locked" : ""}`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() => toggleSplitRecipient(p.id)}
                                    disabled={lockMe}
                                  />
                                  {p.nome}
                                </label>
                              );
                            })}
                          </div>
                          {splitMode === "even" ? (
                            <p className="trip-expense-pay-split__hint muted">
                              Divide o total em partes iguais entre os nomes marcados.
                            </p>
                          ) : (
                            <>
                              <p className="trip-expense-pay-split__hint muted">
                                Informe o valor de cada um; a soma deve fechar com o total do gasto.
                              </p>
                              <div className="trip-expense-pay-split__custom-grid">
                                {payerOptions
                                  .filter((p) => splitRecipients.includes(p.id))
                                  .map((p) => (
                                    <div
                                      key={p.id}
                                      className="trip-expense-pay-split__custom-row"
                                    >
                                      <span style={{ flex: 1 }}>{p.nome}</span>
                                      <input
                                        inputMode="decimal"
                                        placeholder="0,00"
                                        value={customShares[p.id] ?? ""}
                                        onChange={(e) =>
                                          setCustomShares((prev) => ({
                                            ...prev,
                                            [p.id]: e.target.value,
                                          }))
                                        }
                                      />
                                    </div>
                                  ))}
                              </div>
                            </>
                          )}
                        </div>
                      )}
                    </section>
                  </>
                )}
              </div>
            </div>

            <div className="field">
              <label htmlFor="te-obs">Observação</label>
              <input
                id="te-obs"
                value={observacao}
                onChange={(e) => setObservacao(e.target.value)}
              />
            </div>

            {formError && <p className="error">{formError}</p>}
            <button
              type="submit"
              className="btn"
              disabled={saving || payerOptions.length === 0}
              style={{ width: "100%" }}
            >
              {saving ? "Salvando…" : "Lançar gasto"}
            </button>
          </form>
        </div>
      )}

      {sortedExpenses.length === 0 ? (
        <div className="trip-section">
          <p className="muted" style={{ margin: 0 }}>
            Nenhum gasto lançado.
          </p>
        </div>
      ) : (
        <div className="trip-section__stack">
          {sortedExpenses.map((exp) => (
            <article key={exp.id} className="trip-section trip-expense-card">
              <header>
                <div>
                  <span
                    className="trip-expense-card__badge"
                    style={{ background: CATEGORY_COLOR[exp.categoria] }}
                  >
                    {CATEGORY_LABEL[exp.categoria]}
                  </span>
                  <strong>{exp.descricao}</strong>
                  <div className="muted trip-expense-card__meta">
                    {formatDateBR(exp.data)} · {PAYMENT_LABEL[exp.forma_pagamento]} · pago por{" "}
                    {exp.paid_by_nome}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontWeight: 600 }}>{formatBRL(exp.valor_base)}</div>
                  {exp.pushed_expense_id && (
                    <div className="muted" style={{ fontSize: 11 }}>
                      ✓ enviado para o mês
                    </div>
                  )}
                </div>
              </header>
              <div className="muted trip-expense-card__meta" style={{ marginTop: 6 }}>
                Divisão:{" "}
                {exp.shares.map((sh) => `${sh.spender_nome} ${formatBRL(sh.valor)}`).join(" · ") ||
                  "—"}
              </div>
              {exp.observacao && (
                <p className="muted trip-expense-card__meta" style={{ marginTop: 4 }}>
                  {exp.observacao}
                </p>
              )}
              {!closed && (
                <div className="trip-expense-card__actions">
                  {!exp.pushed_expense_id && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => handlePushToMonth(exp)}
                    >
                      Empurrar para o mês
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleDelete(exp.id)}
                  >
                    Excluir
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}

    </div>
  );
}

function SettlementTab({
  settlement,
  moedaBase,
}: {
  settlement: TripSettlementRow | null;
  moedaBase: string;
}) {
  if (!settlement) {
    return (
      <div className="trip-page">
        <div className="trip-section">
          <p className="muted" style={{ margin: 0 }}>
            Calculando acerto…
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="trip-page">
      <section className="trip-section">
        <h2 className="trip-section__title">Saldos por pessoa</h2>
        <p className="trip-section__lead muted">
          Saldo positivo = a pessoa tem a receber. Negativo = a pessoa deve.
        </p>
        <SaldoTable rows={settlement.saldos} />
      </section>

      <section className="trip-section">
        <h2 className="trip-section__title">Transferências sugeridas</h2>
        <p className="trip-section__lead muted">
          Forma mais simples de zerar todas as dívidas ({moedaBase}).
        </p>
        {settlement.transferencias.length === 0 ? (
          <p style={{ margin: 0 }}>Tudo certo — ninguém deve nada.</p>
        ) : (
          <ul className="trip-section__stack" style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {settlement.transferencias.map((t, i) => (
              <li
                key={`${t.from_spender_id}-${t.to_spender_id}-${i}`}
                className="trip-list-row"
                style={{ justifyContent: "flex-start" }}
              >
                <span>
                  <strong>{t.from_spender_nome}</strong> paga <strong>{formatBRL(t.valor)}</strong>{" "}
                  para <strong>{t.to_spender_nome}</strong>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function ParticipantsTab({
  trip,
  spenders,
  closed,
  onChanged,
}: {
  trip: TripRow;
  spenders: SpenderRow[];
  closed: boolean;
  onChanged: () => Promise<void>;
}) {
  const [adding, setAdding] = useState("");
  const [error, setError] = useState("");

  const available = spenders.filter(
    (sp) => !trip.participants.some((p) => p.spender_id === sp.id),
  );

  async function handleAdd() {
    if (!adding) return;
    setError("");
    try {
      await api.addTripParticipant(trip.id, { spender_id: adding });
      setAdding("");
      await onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao adicionar");
    }
  }

  async function handleRemove(spenderId: string) {
    setError("");
    try {
      await api.removeTripParticipant(trip.id, spenderId);
      await onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao remover");
    }
  }

  return (
    <div className="trip-page">
      {error && <p className="error">{error}</p>}
      {!closed && (
        <div className="trip-section">
          <h2 className="trip-section__title">Adicionar participante</h2>
          {available.length === 0 ? (
            <p className="muted" style={{ margin: 0 }}>
              Todos os seus spenders já estão na viagem. Cadastre mais em{" "}
              <Link to="/cartoes/pessoas">Cartões → Pessoas</Link>.
            </p>
          ) : (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <select
                value={adding}
                onChange={(e) => setAdding(e.target.value)}
                style={{ flex: "1 1 12rem" }}
              >
                <option value="">Selecione…</option>
                {available.map((sp) => (
                  <option key={sp.id} value={sp.id}>
                    {sp.nome}
                  </option>
                ))}
              </select>
              <button type="button" className="btn" onClick={handleAdd} disabled={!adding}>
                Adicionar
              </button>
            </div>
          )}
          <p className="trip-section__lead muted" style={{ marginBottom: 0, marginTop: "0.75rem" }}>
            A viagem só copia vínculos de pessoas já cadastradas em{" "}
            <Link to="/cartoes/pessoas">Cartões → Pessoas</Link>. Adicionar ou remover aqui não altera o
            cadastro base.
          </p>
        </div>
      )}

      <section className="trip-section">
        <h2 className="trip-section__title">Participantes</h2>
        {trip.participants.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            Nenhum participante.
          </p>
        ) : (
          <ul className="trip-section__stack" style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {trip.participants.map((p) => (
              <li key={p.spender_id} className="trip-list-row">
                <span>{p.spender_nome}</span>
                {!closed && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleRemove(p.spender_id)}
                  >
                    Remover
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
