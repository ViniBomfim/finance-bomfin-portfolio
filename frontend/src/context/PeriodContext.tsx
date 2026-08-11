import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api";
import type { Period } from "../types";

const PERIOD_KEY = "fm_period_id";

function periodKey(ano: number, mes: number): number {
  return ano * 12 + mes;
}

/** Prefere mês civil atual se open; senão próximo futuro open; senão aberto mais recente no passado. */
function pickOpenPeriod(
  list: Period[],
  preferYear: number,
  preferMonth: number,
): Period | undefined {
  const open = list.filter((p) => p.status === "open");
  if (open.length === 0) return undefined;

  const prefer = periodKey(preferYear, preferMonth);
  const current = open.find((p) => p.ano === preferYear && p.mes === preferMonth);
  if (current) return current;

  const future = open
    .filter((p) => periodKey(p.ano, p.mes) > prefer)
    .sort((a, b) => periodKey(a.ano, a.mes) - periodKey(b.ano, b.mes));
  if (future[0]) return future[0];

  const past = open
    .filter((p) => periodKey(p.ano, p.mes) < prefer)
    .sort((a, b) => periodKey(b.ano, b.mes) - periodKey(a.ano, a.mes));
  return past[0];
}

const DEFAULT_EXPENSE_CATEGORIES: Array<{ nome: string; cor: string }> = [
  { nome: "Geral", cor: "#3d8bfd" },
  { nome: "Metas", cor: "#22c55e" },
  { nome: "Carro", cor: "#2563eb" },
  { nome: "Contas", cor: "#4A90D9" },
  { nome: "Educação", cor: "#7B68EE" },
  { nome: "Saúde", cor: "#50C878" },
  { nome: "Restaurante", cor: "#F5A623" },
  { nome: "Transporte", cor: "#BD10E0" },
  { nome: "Streaming", cor: "#D0021B" },
  { nome: "Mercado", cor: "#8B572A" },
  { nome: "Pet", cor: "#F8E71C" },
  { nome: "Outros", cor: "#9B9B9B" },
];
const DEFAULT_INCOME_CATEGORIES: Array<{ nome: string; cor: string }> = [
  { nome: "Salários", cor: "#34c759" },
];

async function ensureDefaultCategories(): Promise<void> {
  const exp = await api.categories("expense");
  const expSet = new Set(exp.map((c) => c.nome.toLowerCase().trim()));
  const expMissing = DEFAULT_EXPENSE_CATEGORIES.filter(
    (cat) => !expSet.has(cat.nome.toLowerCase().trim()),
  );
  await Promise.all(
    expMissing.map((cat) => api.createCategory({ nome: cat.nome, cor: cat.cor, tipo: "expense" })),
  );

  const inc = await api.categories("income");
  const incSet = new Set(inc.map((c) => c.nome.toLowerCase().trim()));
  const incMissing = DEFAULT_INCOME_CATEGORIES.filter(
    (cat) => !incSet.has(cat.nome.toLowerCase().trim()),
  );
  await Promise.all(
    incMissing.map((cat) => api.createCategory({ nome: cat.nome, cor: cat.cor, tipo: "income" })),
  );
}

type Ctx = {
  periods: Period[];
  periodId: string;
  setPeriodId: (id: string) => void;
  loading: boolean;
  error: string;
  ready: boolean;
  monthLabel: (mes: number, ano: number) => string;
  currentPeriod: Period | null;
  periodClosed: boolean;
  refreshPeriods: () => Promise<void>;
};

const PeriodContext = createContext<Ctx | null>(null);

export function PeriodProvider({ children }: { children: ReactNode }) {
  const [periods, setPeriods] = useState<Period[]>([]);
  const [periodId, setPeriodIdState] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const monthLabel = useCallback((mes: number, ano: number) => {
    const d = new Date(ano, mes - 1, 1);
    return d.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
  }, []);

  const setPeriodId = useCallback((id: string) => {
    setPeriodIdState(id);
    if (id) localStorage.setItem(PERIOD_KEY, id);
  }, []);

  const refreshPeriods = useCallback(async () => {
    setError("");
    const list = await api.periods();
    setPeriods(list);
    setPeriodIdState((prev) => {
      // Mantém o período atual (mesmo fechado) para não pular ao fechar o mês na UI.
      if (prev && list.some((p) => p.id === prev)) return prev;
      const year = new Date().getFullYear();
      const currentMonth = new Date().getMonth() + 1;
      const open = pickOpenPeriod(list, year, currentMonth);
      const matchCurrent = list.find((p) => p.ano === year && p.mes === currentMonth);
      const pick = open?.id ?? matchCurrent?.id ?? list[0]?.id ?? "";
      if (pick) localStorage.setItem(PERIOD_KEY, pick);
      return pick;
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        let list = await api.periods();
        const year = new Date().getFullYear();
        const hasCurrentYear = list.some((p) => p.ano === year);
        if (!hasCurrentYear) {
          try {
            await api.createYear(year);
          } catch {
            // Requisições paralelas (ex.: React StrictMode) podem criar o ano antes desta concluir.
          }
          list = await api.periods();
        }
        if (list.length === 0) {
          throw new Error("Não foi possível carregar os períodos. Tente recarregar a página.");
        }
        if (cancelled) return;
        setPeriods(list);
        const saved = localStorage.getItem(PERIOD_KEY);
        const valid = saved && list.some((p) => p.id === saved);
        const currentMonth = new Date().getMonth() + 1;
        const matchCurrent = list.find((p) => p.ano === year && p.mes === currentMonth);
        let pick = valid ? saved! : matchCurrent?.id ?? list[0]?.id ?? "";
        const picked = list.find((p) => p.id === pick);
        if (picked?.status === "closed") {
          const open = pickOpenPeriod(list, year, currentMonth);
          if (open) pick = open.id;
        }
        setPeriodIdState(pick);
        if (pick) localStorage.setItem(PERIOD_KEY, pick);

        // Não bloqueia a renderização inicial do app com tarefas administrativas.
        void ensureDefaultCategories();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Erro ao carregar períodos");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const currentPeriod = useMemo(
    () => periods.find((p) => p.id === periodId) ?? null,
    [periods, periodId],
  );
  const periodClosed = currentPeriod?.status === "closed";

  const value = useMemo<Ctx>(
    () => ({
      periods,
      periodId,
      setPeriodId,
      loading,
      error,
      ready: !loading && periods.length > 0 && !!periodId,
      monthLabel,
      currentPeriod,
      periodClosed,
      refreshPeriods,
    }),
    [
      periods,
      periodId,
      setPeriodId,
      loading,
      error,
      monthLabel,
      currentPeriod,
      periodClosed,
      refreshPeriods,
    ],
  );

  return <PeriodContext.Provider value={value}>{children}</PeriodContext.Provider>;
}

export function usePeriod() {
  const ctx = useContext(PeriodContext);
  if (!ctx) throw new Error("usePeriod outside PeriodProvider");
  return ctx;
}
