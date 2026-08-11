import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Cell, Pie, PieChart, Tooltip } from "recharts";
import { ChartBox } from "../../components/ChartBox";
import { formatBRL, formatCompactBRL } from "../../money";
import type { InvestmentRow, InvestmentTipo } from "../../types";

export type InvestmentTab = "overview" | "assets" | "rebalance" | "dividends";

const CLASS_INFO: Record<InvestmentTipo, { label: string; color: string; icon: string; target: number }> = {
  renda_fixa: { label: "Renda fixa", color: "#a78bfa", icon: "🏦", target: 30 },
  stock: { label: "Ações", color: "#3b82f6", icon: "📈", target: 25 },
  fii: { label: "FIIs", color: "#22c55e", icon: "🏢", target: 35 },
  crypto: { label: "Cripto", color: "#f97316", icon: "₿", target: 10 },
};

const CLASS_ORDER = Object.keys(CLASS_INFO) as InvestmentTipo[];

const FEED = [
  { kind: "Dividendo pago", icon: "💰", color: "#22c55e", title: "BBAS3 pagou dividendo", text: "R$ 0,80 por cota · 36 cotas na carteira", foot: "22/07/2026", value: "+R$ 28,80" },
  { kind: "Rendimento pago", icon: "💰", color: "#22c55e", title: "MXRF11 distribuiu rendimento", text: "R$ 0,10 por cota · crédito confirmado", foot: "20/07/2026", value: "+R$ 3,90" },
  { kind: "Dividendo previsto", icon: "📅", color: "#f59e0b", title: "MXRF11 · previsão", text: "Pagamento estimado para 08/08/2026", foot: "Ex-div: 05/08", value: "≈ R$ 3,90" },
  { kind: "Evento corporativo", icon: "⚠️", color: "#f59e0b", title: "Subscrição KDIF11", text: "R$ 4,50/cota · prazo para exercer o direito", foot: "Até 15/08/2026", value: "Atenção" },
  { kind: "Notícia", icon: "📰", color: "#3b82f6", title: "BBAS3 eleva projeção de lucro", text: "Banco revisa indicadores para 2026 acima do esperado", foot: "29/07/2026", value: "Positivo" },
  { kind: "Cenário macro", icon: "📊", color: "#3b82f6", title: "Selic mantida em 10,50%", text: "FIIs de papel e renda fixa tendem a se beneficiar", foot: "28/07/2026", value: "Macro" },
  { kind: "Maior alta", icon: "📈", color: "#a78bfa", title: "KDIF11 lidera as altas", text: "Melhor desempenho semanal entre os ativos acompanhados", foot: "Semana 28/07", value: "+2,78%" },
  { kind: "Maior baixa", icon: "📉", color: "#f43f5e", title: "BTC lidera as quedas", text: "Ativo recuou na semana com maior volatilidade", foot: "Semana 28/07", value: "-2,08%" },
] as const;

const DIVIDENDS = [
  { date: "22/07/2026", asset: "BBAS3", type: "Dividendo", unit: 0.8, qty: 36, total: 28.8 },
  { date: "20/07/2026", asset: "MXRF11", type: "Rendimento", unit: 0.1, qty: 39, total: 3.9 },
  { date: "15/07/2026", asset: "KDIF11", type: "Rendimento", unit: 1.2, qty: 4, total: 4.8 },
  { date: "10/07/2026", asset: "VISC11", type: "Rendimento", unit: 0.72, qty: 3, total: 2.16 },
] as const;

const FORECASTS = [
  { date: "08/08/2026", asset: "MXRF11", type: "Rendimento", unit: 0.1, qty: 39, total: 3.9 },
  { date: "10/08/2026", asset: "KDIF11", type: "Rendimento", unit: 1.2, qty: 4, total: 4.8 },
  { date: "20/08/2026", asset: "BBAS3", type: "Dividendo", unit: 0.8, qty: 36, total: 28.8 },
  { date: "25/08/2026", asset: "JURO11", type: "Rendimento", unit: 1.1, qty: 5, total: 5.5 },
] as const;

function numberFrom(value: string | number | null | undefined) {
  const parsed = Number(String(value ?? 0).replace(",", "."));
  return Number.isFinite(parsed) ? parsed : 0;
}

export function InvestmentTabs({
  active,
  onChange,
}: {
  active: InvestmentTab;
  onChange: (tab: InvestmentTab) => void;
}) {
  const tabs: Array<[InvestmentTab, string]> = [
    ["overview", "Visão geral"],
    ["assets", "Meus ativos"],
    ["rebalance", "Rebalanceamento"],
    ["dividends", "Dividendos"],
  ];
  return (
    <div className="inv-tabs" role="tablist" aria-label="Seções de investimentos">
      {tabs.map(([id, label]) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={active === id}
          className={`inv-tab${active === id ? " inv-tab--active" : ""}`}
          onClick={() => onChange(id)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function InvestmentCarousel() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const touchStart = useRef(0);
  const [perPage, setPerPage] = useState(4);
  const [page, setPage] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const update = () => {
      const width = el.getBoundingClientRect().width;
      setPerPage(width < 560 ? 1 : width < 820 ? 2 : width < 1180 ? 3 : 4);
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const pages = useMemo(() => {
    const result: (typeof FEED[number])[][] = [];
    for (let i = 0; i < FEED.length; i += perPage) result.push(FEED.slice(i, i + perPage));
    return result;
  }, [perPage]);

  useEffect(() => setPage((current) => Math.min(current, Math.max(0, pages.length - 1))), [pages.length]);
  useEffect(() => {
    if (paused || pages.length < 2) return;
    const timer = window.setInterval(() => setPage((current) => (current + 1) % pages.length), 5000);
    return () => window.clearInterval(timer);
  }, [paused, pages.length]);

  const move = (direction: number) =>
    setPage((current) => (current + direction + pages.length) % pages.length);

  return (
    <section className="inv-carousel" aria-label="Informações da carteira">
      <div className="inv-carousel__head">
        <div>
          <span className="inv-eyebrow">Agenda da carteira</span>
          <strong>Esta semana · 28/07 – 01/08/2026</strong>
        </div>
        <div className="inv-carousel__nav">
          <div className="inv-carousel__dots" aria-label="Páginas do carrossel">
            {pages.map((_, index) => (
              <button
                key={index}
                type="button"
                className={index === page ? "is-active" : ""}
                aria-label={`Ir para página ${index + 1}`}
                aria-current={index === page ? "true" : undefined}
                onClick={() => setPage(index)}
              />
            ))}
          </div>
          <button type="button" onClick={() => move(-1)} aria-label="Informações anteriores">‹</button>
          <button type="button" onClick={() => move(1)} aria-label="Próximas informações">›</button>
        </div>
      </div>
      <div
        ref={wrapRef}
        className="inv-carousel__viewport"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        onFocus={() => setPaused(true)}
        onBlur={() => setPaused(false)}
        onTouchStart={(event) => {
          touchStart.current = event.touches[0]?.clientX ?? 0;
          setPaused(true);
        }}
        onTouchEnd={(event) => {
          const delta = touchStart.current - (event.changedTouches[0]?.clientX ?? touchStart.current);
          if (Math.abs(delta) > 45) move(delta > 0 ? 1 : -1);
          setPaused(false);
        }}
      >
        <div className="inv-carousel__track" style={{ transform: `translate3d(-${page * 100}%, 0, 0)` }}>
          {pages.map((items, pageIndex) => (
            <div className="inv-carousel__page" style={{ gridTemplateColumns: `repeat(${perPage}, minmax(0, 1fr))` }} key={pageIndex}>
              {items.map((item) => (
                <article className="inv-feed-card" key={item.title} style={{ "--inv-card-color": item.color } as React.CSSProperties}>
                  <span className="inv-feed-card__type">{item.icon} {item.kind}</span>
                  <strong>{item.title}</strong>
                  <p>{item.text}</p>
                  <footer><span>{item.foot}</span><b>{item.value}</b></footer>
                </article>
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Panel({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="inv-panel">
      <header><h2>{title}</h2>{action}</header>
      {children}
    </section>
  );
}

export function InvestmentsOverview({
  rows,
  onOpenAssets,
  onOpenRebalance,
}: {
  rows: InvestmentRow[];
  onOpenAssets: () => void;
  onOpenRebalance: () => void;
}) {
  const applied = rows.reduce((sum, row) => sum + numberFrom(row.valor_aplicado), 0);
  const current = rows.reduce((sum, row) => sum + numberFrom(row.valor_atual), 0);
  const profit = current - applied;
  const allocation = CLASS_ORDER.map((type) => ({
    type,
    ...CLASS_INFO[type],
    value: rows.filter((row) => row.tipo === type).reduce((sum, row) => sum + numberFrom(row.valor_atual), 0),
  })).filter((item) => item.value > 0);
  const goal = Math.max(50000, current);

  return (
    <div className="inv-tab-panel" role="tabpanel">
      <div className="inv-alert">
        <span>⚠️</span>
        <div><strong>Evento corporativo — KDIF11</strong><p>Subscrição demonstrativa disponível até 15/08/2026.</p></div>
        <button className="btn btn-ghost btn-sm" type="button">Ver detalhes</button>
      </div>
      <section className="inv-balance">
        <span className="inv-balance__icon">💰</span>
        <div><span className="inv-eyebrow">Saldo disponível para aportar</span><strong>R$ 568,73</strong><p>Dividendos R$ 68,73 · Aporte planejado R$ 500,00</p></div>
        <button className="btn btn-sm" type="button" onClick={onOpenRebalance}>Aportar agora →</button>
      </section>
      <div className="inv-kpis">
        <article><span>Valor atual</span><strong>{formatBRL(current)}</strong><small>{rows.length} posições cadastradas</small></article>
        <article><span>Valor investido</span><strong>{formatBRL(applied)}</strong><small className={profit >= 0 ? "positive" : "negative"}>{profit >= 0 ? "+" : ""}{formatBRL(profit)}</small></article>
        <article><span>Valor meta</span><strong>{formatBRL(goal)}</strong><div className="inv-progress"><i style={{ width: `${Math.min(100, (current / goal) * 100)}%` }} /></div><small>{((current / goal) * 100).toFixed(1)}% atingida</small></article>
        <article><span>Aporte pendente</span><strong>R$ 500,00</strong><small>julho · demonstrativo</small></article>
      </div>
      <div className="inv-overview-grid">
        <Panel title="📊 Distribuição por classe" action={<button type="button" className="inv-link" onClick={onOpenAssets}>Ver ativos →</button>}>
          {allocation.length ? (
            <div className="inv-allocation">
              <div className="inv-donut">
                <ChartBox height={190}>
                  {({ width, height }) => (
                    <PieChart width={width} height={height}>
                      <Pie data={allocation} dataKey="value" nameKey="label" cx="50%" cy="50%" innerRadius={54} outerRadius={78} stroke="none" paddingAngle={2}>
                        {allocation.map((item) => <Cell key={item.type} fill={item.color} />)}
                      </Pie>
                      <Tooltip formatter={(value: number) => formatBRL(value)} />
                    </PieChart>
                  )}
                </ChartBox>
                <div><strong>{formatCompactBRL(current)}</strong><span>atual</span></div>
              </div>
              <div className="inv-allocation__list">
                {allocation.map((item) => {
                  const pct = current ? (item.value / current) * 100 : 0;
                  return <div key={item.type}><span style={{ background: item.color }} /><b>{item.label}</b><i><em style={{ width: `${pct}%`, background: item.color }} /></i><strong>{pct.toFixed(0)}%</strong></div>;
                })}
              </div>
            </div>
          ) : <div className="inv-empty">Cadastre um ativo para visualizar a distribuição.</div>}
        </Panel>
        <div className="inv-side-stack">
          <Panel title="💰 Dividendos (9 meses)">
            <div className="inv-dividend-summary"><strong>R$ 68,73</strong><span>julho · demonstrativo</span></div>
            <div className="inv-bars" aria-label="Histórico demonstrativo de dividendos">
              {[42, 55, 48, 72, 60, 84, 63, 78, 68].map((height, index) => <i key={index} style={{ height: `${height}%` }}><span>{["N","D","J","F","M","A","M","J","J"][index]}</span></i>)}
            </div>
          </Panel>
          <Panel title="🎯 Aportes recentes">
            <div className="inv-contributions">
              <div><b>Julho/2026</b><span className="inv-warning">Em andamento</span><progress value="50" max="100" /></div>
              <div><b>Junho/2026</b><span className="positive">Concluído</span><progress value="100" max="100" /></div>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

export function InvestmentsRebalance({ rows }: { rows: InvestmentRow[] }) {
  const [input, setInput] = useState("1000");
  const [done, setDone] = useState<string[]>([]);
  const current = rows.reduce((sum, row) => sum + numberFrom(row.valor_atual), 0);
  const contribution = Math.max(0, numberFrom(input));
  const nextTotal = current + contribution;
  const suggestions = CLASS_ORDER.map((type) => {
    const info = CLASS_INFO[type];
    const value = rows.filter((row) => row.tipo === type).reduce((sum, row) => sum + numberFrom(row.valor_atual), 0);
    const difference = (info.target / 100) * nextTotal - value;
    return { type, ...info, value, difference };
  });
  const buys = suggestions.filter((item) => item.difference > 1);
  const sells = suggestions.filter((item) => item.difference < -1);

  const renderRows = (items: typeof suggestions, action: "Comprar" | "Vender") =>
    items.length ? items.map((item) => (
      <tr key={item.type} className={done.includes(`${action}-${item.type}`) ? "is-done" : ""}>
        <td>{item.icon} <b>{item.label}</b></td>
        <td>{current ? ((item.value / current) * 100).toFixed(1) : "0.0"}%</td>
        <td>{item.target}%</td>
        <td className={action === "Comprar" ? "positive" : "negative"}>{formatBRL(Math.abs(item.difference))}</td>
        <td><button type="button" className="inv-check" aria-label={`Marcar ${item.label} como concluído`} onClick={() => setDone((old) => [...old, `${action}-${item.type}`])}>✓</button></td>
      </tr>
    )) : <tr><td colSpan={5} className="inv-empty">Nenhum ajuste sugerido.</td></tr>;

  return (
    <div className="inv-tab-panel" role="tabpanel">
      <section className="inv-rebalance-head">
        <label><span>Quanto vou aportar?</span><div>R$ <input value={input} inputMode="decimal" onChange={(event) => setInput(event.target.value)} /></div></label>
        <div><span>Carteira atual</span><strong>{formatBRL(current)}</strong></div>
        <b>→</b>
        <div><span>Novo total</span><strong className="positive">{formatBRL(nextTotal)}</strong></div>
        <small>Simulação demonstrativa por classe</small>
      </section>
      <div className="inv-rebalance-grid">
        <Panel title={`📈 Comprar · ${buys.length} classes`}>
          <div className="inv-table-wrap"><table className="inv-table"><thead><tr><th>Classe</th><th>Atual</th><th>Meta</th><th>Valor sugerido</th><th /></tr></thead><tbody>{renderRows(buys, "Comprar")}</tbody></table></div>
        </Panel>
        <Panel title={`📉 Vender · ${sells.length} classes`}>
          <div className="inv-table-wrap"><table className="inv-table"><thead><tr><th>Classe</th><th>Atual</th><th>Meta</th><th>Valor sugerido</th><th /></tr></thead><tbody>{renderRows(sells, "Vender")}</tbody></table></div>
        </Panel>
      </div>
    </div>
  );
}

function DividendTable({ forecast = false }: { forecast?: boolean }) {
  const data = forecast ? FORECASTS : DIVIDENDS;
  return (
    <div className="inv-table-wrap">
      <table className="inv-table">
        <thead><tr><th>Data</th><th>Ativo</th><th>Tipo</th><th>R$/cota</th><th>Qtd.</th><th>Total</th></tr></thead>
        <tbody>{data.map((item) => <tr key={`${item.date}-${item.asset}`}><td>{item.date}</td><td><b className="inv-ticker">{item.asset}</b></td><td>{item.type}</td><td>{forecast ? "≈ " : ""}{formatBRL(item.unit)}</td><td>{item.qty}</td><td className={forecast ? "inv-warning" : "positive"}>{forecast ? "≈ " : "+"}{formatBRL(item.total)}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

export function InvestmentsDividends() {
  const month = DIVIDENDS.reduce((sum, item) => sum + item.total, 0);
  return (
    <div className="inv-tab-panel" role="tabpanel">
      <div className="inv-kpis">
        <article><span>Mês atual</span><strong>{formatBRL(month)}</strong><small>julho/2026 · demonstrativo</small></article>
        <article><span>Acumulado no ano</span><strong>R$ 412,38</strong><small>jan–jul/2026</small></article>
        <article><span>Média mensal</span><strong>R$ 58,91</strong><small>últimos 6 meses</small></article>
        <article><span>Próximo previsto</span><strong>08/08/2026</strong><small>MXRF11 ≈ R$ 3,90</small></article>
      </div>
      <Panel title="📋 Histórico recebido" action={<span className="inv-demo-badge">Dados demonstrativos</span>}><DividendTable /></Panel>
      <Panel title="📅 Previsão futura" action={<span className="inv-demo-badge">Previsão demonstrativa</span>}><DividendTable forecast /></Panel>
    </div>
  );
}
