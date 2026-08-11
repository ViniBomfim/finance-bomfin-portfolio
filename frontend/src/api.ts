const PREFIX = "/api/v1";

function normalizeBaseUrl(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

function requestUrl(path: string): string {
  const envBase = import.meta.env.VITE_API_URL;
  if (!envBase) return `${PREFIX}${path}`;

  const base = normalizeBaseUrl(envBase);
  const lowerBase = base.toLowerCase();
  const prefix = lowerBase.endsWith("/api/v1")
    ? ""
    : lowerBase.endsWith("/api")
      ? "/v1"
      : PREFIX;

  return `${base}${prefix}${path}`;
}

export function getToken(): string | null {
  return localStorage.getItem("fm_token");
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem("fm_token", token);
  else localStorage.removeItem("fm_token");
}

function isHtmlBody(text: string): boolean {
  const head = text.trim().slice(0, 32).toLowerCase();
  return head.startsWith("<!doctype") || head.startsWith("<html");
}

/** Produção no Netlify/outro host sem proxy local: exige URL absoluta da API. */
export function isApiUrlConfigured(): boolean {
  return Boolean(import.meta.env.VITE_API_URL?.trim());
}

function missingApiUrlMessage(): string {
  return (
    "API não configurada: no Netlify, em Site settings → Environment variables, " +
    "defina VITE_API_URL com a URL pública do backend (ex.: https://sua-api.onrender.com) " +
    "e faça um novo deploy."
  );
}

function formatApiDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return "";
  return detail
    .map((item) => {
      if (!item || typeof item !== "object" || !("msg" in item)) return "";
      const msg = String((item as { msg: unknown }).msg);
      return msg.replace(/^Value error,\s*/i, "").trim();
    })
    .filter(Boolean)
    .join(", ");
}

function errorDetailMessage(
  data: unknown,
  text: string,
  statusText: string,
  status?: number,
): string {
  if (text && isHtmlBody(text)) {
    if (import.meta.env.PROD && !isApiUrlConfigured()) return missingApiUrlMessage();
    if (status === 404) {
      return "API não encontrada. Confira VITE_API_URL no Netlify e se o backend está no ar.";
    }
    return "Resposta inválida do servidor. Verifique a URL da API.";
  }

  const errObj = data as { detail?: unknown } | null;
  const detail = errObj?.detail;
  const fromBody = formatApiDetail(detail) || text?.slice(0, 200)?.trim() || "";
  if (/^internal server error$/i.test(fromBody)) {
    return import.meta.env.DEV
      ? "Erro interno no servidor. Verifique o terminal do backend (uvicorn) — em geral é falha de conexão com o banco (DATABASE_URL / rede)."
      : "Erro interno no servidor. Tente novamente em instantes.";
  }
  if (fromBody) return fromBody;
  if (status === 500) return "Erro interno no servidor. Tente novamente em instantes.";
  if (status === 502) {
    return import.meta.env.DEV
      ? "Backend indisponível ou reiniciando. Confira o terminal do uvicorn, aguarde subir e tente de novo."
      : "Servidor temporariamente indisponível. Aguarde um instante e tente novamente.";
  }
  if (status === 503 || status === 504) {
    return import.meta.env.DEV
      ? "Servidor ocupado ou reiniciando. Aguarde alguns segundos e tente de novo."
      : "Servidor temporariamente indisponível. Aguarde um instante e tente novamente.";
  }
  if (status === 404 && import.meta.env.PROD && !isApiUrlConfigured()) return missingApiUrlMessage();
  return statusText || (status ? `Erro HTTP ${status}` : "Erro de comunicação com o servidor");
}

async function request<T>(
  path: string,
  options: RequestInit & { json?: unknown; skipAuth?: boolean } = {},
): Promise<T> {
  const skipAuth = options.skipAuth ?? false;
  const headers: HeadersInit = {
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token && !skipAuth) (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  if (options.json !== undefined) {
    (headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  let res: Response;
  try {
    res = await fetch(requestUrl(path), {
      ...options,
      headers,
      body: options.json !== undefined ? JSON.stringify(options.json) : options.body,
    });
  } catch {
    throw new Error(
      "Não foi possível conectar ao servidor. Verifique sua conexão e se o backend está no ar.",
    );
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    const trimmed = text.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        data = JSON.parse(text) as unknown;
      } catch {
        data = null;
      }
    }
  }
  if (text && isHtmlBody(text)) {
    throw new Error(errorDetailMessage(data, text, res.statusText, res.status));
  }
  if (res.status === 403 && skipAuth) {
    const msg = errorDetailMessage(data, text, res.statusText, res.status);
    throw new Error(msg || `HTTP ${res.status}`);
  }
  if (res.status === 401) {
    const msg = errorDetailMessage(data, text, res.statusText, res.status);
    if (skipAuth) {
      const friendly =
        msg === "Invalid credentials" ? "Usuário ou senha incorretos." : msg;
      throw new Error(friendly || `HTTP ${res.status}`);
    }
    setToken(null);
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new Error("Sessão expirada. Faça login novamente.");
  }
  if (!res.ok) {
    throw new Error(errorDetailMessage(data, text, res.statusText, res.status) || `HTTP ${res.status}`);
  }
  return data as T;
}

export const api = {
  getMe: () => request<import("./types").UserMe>("/users/me"),

  patchMe: (body: { name?: string; me_spender_id?: string | null }) =>
    request<import("./types").UserMe>("/users/me", { method: "PATCH", json: body }),

  uploadMyAvatar: async (file: File): Promise<import("./types").UserMe> => {
    const fd = new FormData();
    fd.append("file", file);
    const token = getToken();
    const res = await fetch(requestUrl("/users/me/avatar"), {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });
    if (res.status === 401) {
      setToken(null);
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
      throw new Error("Sessão expirada. Faça login novamente.");
    }
    const text = await res.text();
    let data: unknown = null;
    if (text) {
      try {
        data = JSON.parse(text) as unknown;
      } catch {
        data = null;
      }
    }
    if (!res.ok) {
      const errObj = data as { detail?: unknown } | null;
      const msg =
        (typeof errObj?.detail === "string" ? errObj.detail : null) ||
        text?.slice(0, 200)?.trim() ||
        res.statusText;
      throw new Error(msg || `HTTP ${res.status}`);
    }
    return data as import("./types").UserMe;
  },

  deleteMyAvatar: () =>
    request<import("./types").UserMe>("/users/me/avatar", { method: "DELETE" }),

  fetchMyAvatarBlob: async (): Promise<Blob> => {
    const token = getToken();
    const res = await fetch(requestUrl("/users/me/avatar"), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (res.status === 401) {
      setToken(null);
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
      throw new Error("Sessão expirada. Faça login novamente.");
    }
    if (res.status === 404) {
      throw new Error("Sem foto de perfil");
    }
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    return res.blob();
  },

  listUsers: () => request<import("./types").AdminUserRow[]>("/users"),

  listAccessRequests: () =>
    request<import("./types").AccessRequestRow[]>("/users/access-requests"),

  approveAccessRequest: (userId: string) =>
    request<void>(`/users/${userId}/approve`, { method: "POST" }),

  rejectAccessRequest: (userId: string) =>
    request<void>(`/users/${userId}/reject`, { method: "POST" }),

  adminCreateUser: (body: {
    username: string;
    name: string;
    email: string;
    password: string;
    is_admin?: boolean;
    must_change_password?: boolean;
  }) =>
    request<import("./types").AdminUserRow>("/users", { method: "POST", json: body }),

  adminUpdateUser: (
    userId: string,
    body: { username?: string; name?: string; email?: string; is_admin?: boolean },
  ) => request<import("./types").AdminUserRow>(`/users/${userId}`, { method: "PATCH", json: body }),

  adminResetUserPassword: (userId: string, password: string) =>
    request<void>(`/users/${userId}/reset-password`, { method: "PATCH", json: { password } }),

  adminDeleteUser: (userId: string) => request<void>(`/users/${userId}`, { method: "DELETE" }),

  adminManagementStats: () =>
    request<import("./types").AdminManagementStats>("/admin/management/stats"),

  adminErrorLogs: (limit = 200) =>
    request<import("./types").SystemErrorLogRow[]>(
      `/admin/management/error-logs?limit=${limit}`,
    ),

  getSessionSettings: () =>
    request<import("./types").SessionSettingsResponse>("/settings/session"),

  adminSessionSettings: () =>
    request<import("./types").SessionSettingsResponse>("/admin/management/session-settings"),

  adminSessionSettingsLimits: () =>
    request<import("./types").SessionSettingsDefaults>(
      "/admin/management/session-settings/limits",
    ),

  adminUpdateSessionSettings: (body: import("./types").SessionSettingsUpdate) =>
    request<import("./types").SessionSettingsResponse>("/admin/management/session-settings", {
      method: "PATCH",
      json: body,
    }),

  login: (username: string, password: string) =>
    request<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      json: { username, password },
      skipAuth: true,
    }),

  register: (username: string, email: string, password: string) =>
    request<{ id: string; username: string; email: string; name: string }>("/auth/register", {
      method: "POST",
      json: { username, email, password },
      skipAuth: true,
    }),

  periods: () => request<Array<{ id: string; mes: number; ano: number; status: string }>>("/periods"),

  createYear: (ano: number) =>
    request<Array<{ id: string; mes: number; ano: number; status: string }>>("/periods/year", {
      method: "POST",
      json: { ano },
    }),

  closePeriod: (periodId: string) =>
    request<{ id: string; mes: number; ano: number; status: string }>(
      `/periods/${periodId}/close`,
      { method: "POST" },
    ),

  reopenPeriod: (periodId: string) =>
    request<{ id: string; mes: number; ano: number; status: string }>(
      `/periods/${periodId}/open`,
      { method: "POST" },
    ),

  categories: (tipo?: "income" | "expense") => {
    const q = tipo ? `?tipo=${tipo}` : "";
    return request<Array<{ id: string; nome: string; cor: string; tipo: string }>>(
      `/categories${q}`,
    );
  },

  createCategory: (body: { nome: string; tipo: "expense" | "income"; cor?: string }) =>
    request<{ id: string; nome: string; cor: string; tipo: "expense" | "income" }>(
      "/categories",
      { method: "POST", json: body },
    ),

  deleteCategory: (id: string) => request<void>(`/categories/${id}`, { method: "DELETE" }),

  dashboardSummary: (periodId: string) =>
    request<import("./types").DashboardSummary>(`/dashboard/summary?period_id=${periodId}`),

  // Expenses
  listExpenses: (periodId: string) =>
    request<import("./types").ExpenseRow[]>(`/expenses?period_id=${periodId}`),

  listExpensesByCategory: (categoryId: string) =>
    request<import("./types").ExpenseRow[]>(`/expenses?categoria_id=${categoryId}`),

  createExpense: (body: Record<string, unknown>) =>
    request<import("./types").ExpenseRow>("/expenses", { method: "POST", json: body }),

  updateExpense: (id: string, body: Record<string, unknown>) =>
    request<import("./types").ExpenseRow>(`/expenses/${id}`, { method: "PATCH", json: body }),

  setExpensePaid: (id: string, pago: boolean) =>
    request<import("./types").ExpenseRow>(`/expenses/${id}/paid?pago=${pago ? "true" : "false"}`, {
      method: "POST",
    }),

  setExpenseSharePaid: (expenseId: string, spenderId: string, pago: boolean) =>
    request<import("./types").ExpenseRow>(
      `/expenses/${expenseId}/shares/${spenderId}/paid?pago=${pago ? "true" : "false"}`,
      { method: "POST" },
    ),

  deleteExpense: (id: string) => request<void>(`/expenses/${id}`, { method: "DELETE" }),

  // Incomes
  listIncomes: (periodId: string) => request<unknown[]>(`/incomes?period_id=${periodId}`),

  createIncome: (body: Record<string, string | boolean>) =>
    request<unknown[]>("/incomes", { method: "POST", json: body }),

  updateIncome: (id: string, body: Record<string, string | boolean>) =>
    request<unknown>(`/incomes/${id}`, { method: "PATCH", json: body }),

  deleteIncome: (id: string) => request<void>(`/incomes/${id}`, { method: "DELETE" }),

  // Budgets
  listBudgets: (periodId: string) =>
    request<import("./types").BudgetListItem[]>(`/budgets?period_id=${periodId}`),

  budgetCompare: (periodId: string) =>
    request<import("./types").BudgetCompareRow[]>(`/budgets/compare?period_id=${periodId}`),

  copyBudgetsFromPrevious: (periodId: string) =>
    request<Array<{ id: string; categoria_id: string; period_id: string; valor: string }>>(
      `/budgets/copy-from-previous?period_id=${periodId}`,
      { method: "POST" },
    ),

  replicateYearBudgets: (fromAno: number, toAno: number) =>
    request<Array<{ id: string; categoria_id: string; period_id: string; valor: string }>>(
      "/budgets/replicate-year",
      { method: "POST", json: { from_ano: fromAno, to_ano: toAno } },
    ),

  createBudget: (body: { categoria_id: string; period_id: string; valor: string }) =>
    request("/budgets", { method: "POST", json: body }),

  updateBudget: (id: string, body: { valor: string }) =>
    request<import("./types").BudgetListItem>(`/budgets/${id}`, { method: "PATCH", json: body }),

  deleteBudget: (id: string) => request<void>(`/budgets/${id}`, { method: "DELETE" }),

  // Goals
  listGoals: () => request<import("./types").GoalRow[]>("/goals"),

  getGoal: (id: string) => request<import("./types").GoalRow>(`/goals/${id}`),

  createGoal: (body: Record<string, string | undefined>) =>
    request("/goals", { method: "POST", json: body }),

  updateGoal: (id: string, body: Record<string, string | null | undefined>) =>
    request<import("./types").GoalRow>(`/goals/${id}`, { method: "PATCH", json: body }),

  deleteGoal: (id: string) => request<void>(`/goals/${id}`, { method: "DELETE" }),

  goalProgress: (id: string) => request<import("./types").GoalProgressApi>(`/goals/${id}/progress`),

  goalPoolSummary: (periodId: string) =>
    request<import("./types").GoalPoolSummaryApi>(
      `/goals/pool-summary?period_id=${encodeURIComponent(periodId)}`,
    ),

  addGoalTransaction: (goalId: string, body: Record<string, string | boolean | undefined>) =>
    request(`/goals/${goalId}/transactions`, { method: "POST", json: body }),

  listGoalTransactions: (goalId: string) =>
    request<unknown[]>(`/goals/${goalId}/transactions`),

  deleteGoalTransaction: (goalId: string, txId: string) =>
    request<void>(`/goals/${goalId}/transactions/${txId}`, { method: "DELETE" }),

  // Cards
  listCards: () => request<import("./types").CardRow[]>("/cards"),

  createCard: (body: Record<string, string | number>) =>
    request("/cards", { method: "POST", json: body }),

  getCard: (id: string) => request<import("./types").CardRow>(`/cards/${id}`),

  updateCard: (id: string, body: Record<string, string | number>) =>
    request<import("./types").CardRow>(`/cards/${id}`, { method: "PATCH", json: body }),

  deleteCard: (id: string) => request<void>(`/cards/${id}`, { method: "DELETE" }),

  listSpenders: () => request<import("./types").SpenderRow[]>("/spenders"),

  createSpender: (body: { nome: string }) =>
    request<import("./types").SpenderRow>("/spenders", { method: "POST", json: body }),

  updateSpender: (id: string, body: { nome?: string }) =>
    request<import("./types").SpenderRow>(`/spenders/${id}`, { method: "PATCH", json: body }),

  deleteSpender: (id: string) => request<void>(`/spenders/${id}`, { method: "DELETE" }),

  cardSpenderSummary: (cardId: string, periodId: string) =>
    request<import("./types").CardSpenderSummary>(
      `/cards/${cardId}/spender-summary?period_id=${encodeURIComponent(periodId)}`,
    ),

  listCardTransactions: (cardId: string, periodId: string) =>
    request<import("./types").CardTransactionRow[]>(
      `/card-transactions?card_id=${cardId}&period_id=${periodId}`,
    ),

  createCardTransaction: (body: Record<string, unknown>) =>
    request<import("./types").CardTransactionRow[]>("/card-transactions", { method: "POST", json: body }),

  updateCardTransaction: (id: string, body: Record<string, unknown>) =>
    request<import("./types").CardTransactionRow>(`/card-transactions/${id}`, { method: "PATCH", json: body }),

  setCardTransactionPaid: (id: string, pago: boolean) =>
    request<import("./types").CardTransactionRow>(
      `/card-transactions/${id}/paid?pago=${pago ? "true" : "false"}`,
      { method: "POST" },
    ),

  setCardTransactionSharePaid: (txId: string, spenderId: string, pago: boolean) =>
    request<import("./types").CardTransactionRow>(
      `/card-transactions/${txId}/shares/${spenderId}/paid?pago=${pago ? "true" : "false"}`,
      { method: "POST" },
    ),

  deleteCardTransaction: (id: string) =>
    request<void>(`/card-transactions/${id}`, { method: "DELETE" }),

  deleteAllCardTransactions: (cardId: string, periodId: string) =>
    request<{ deleted: number; card_id: string; period_id: string }>(
      `/cards/${cardId}/transactions?period_id=${encodeURIComponent(periodId)}`,
      { method: "DELETE" },
    ),

  deleteAllCardTransactionsAllMonths: (cardId: string) =>
    request<{ deleted: number; card_id: string }>(
      `/cards/${cardId}/transactions/all-months`,
      { method: "DELETE" },
    ),

  markAllCardTransactionsPaid: (cardId: string, periodId: string) =>
    request<{ updated: number; card_id: string; period_id: string }>(
      `/cards/${cardId}/transactions/mark-paid?period_id=${encodeURIComponent(periodId)}`,
      { method: "POST" },
    ),

  invoiceTotal: (cardId: string, periodId: string) =>
    request<{
      total: string;
      unpaid_total: string;
      unpaid_count: number;
      paid_at: string | null;
    }>(`/card-transactions/invoice-total?card_id=${cardId}&period_id=${periodId}`),

  cardSpentTotal: (cardId: string) =>
    request<{ total: string }>(`/card-transactions/spent-total?card_id=${cardId}`),

  parseStatement: async (
    file: File,
    formatId: string,
    defaultDate: string,
    cardId?: string,
    periodId?: string,
  ): Promise<{
    rows: {
      data: string;
      descricao: string;
      valor: string;
      parcela_atual: number | null;
      parcela_total: number | null;
    }[];
    ignored_rows: {
      data: string;
      descricao: string;
      valor: string;
      parcela_atual: number | null;
      parcela_total: number | null;
      reason: "already_exists" | "duplicate_in_file" | string;
    }[];
    warnings: string[];
    format_used: string;
  }> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("format_id", formatId);
    fd.append("default_date", defaultDate);
    if (cardId && periodId) {
      fd.append("card_id", cardId);
      fd.append("period_id", periodId);
    }
    const token = getToken();
    const res = await fetch(requestUrl("/statement-import/parse"), {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });
    if (res.status === 401) {
      setToken(null);
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
      throw new Error("Sessão expirada. Faça login novamente.");
    }
    const text = await res.text();
    let data: unknown = null;
    if (text) {
      try {
        data = JSON.parse(text) as unknown;
      } catch {
        data = null;
      }
    }
    if (!res.ok) {
      const errObj = data as { detail?: unknown } | null;
      const msg =
        formatApiDetail(errObj?.detail) || text?.slice(0, 200)?.trim() || res.statusText;
      throw new Error(msg || `HTTP ${res.status}`);
    }
    return data as {
      rows: {
        data: string;
        descricao: string;
        valor: string;
        parcela_atual: number | null;
        parcela_total: number | null;
      }[];
      ignored_rows: {
        data: string;
        descricao: string;
        valor: string;
        parcela_atual: number | null;
        parcela_total: number | null;
        reason: "already_exists" | "duplicate_in_file" | string;
      }[];
      warnings: string[];
      format_used: string;
    };
  },

  previewStatement: async (
    file: File,
    formatId: string,
    defaultDate: string,
    cardId: string,
    periodId: string,
  ): Promise<import("./statementImportTypes").ImportPreviewResponse> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("format_id", formatId);
    fd.append("default_date", defaultDate);
    fd.append("card_id", cardId);
    fd.append("period_id", periodId);
    const token = getToken();
    const res = await fetch(requestUrl("/statement-import/preview"), {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });
    if (res.status === 401) {
      setToken(null);
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
      throw new Error("Sessão expirada. Faça login novamente.");
    }
    const text = await res.text();
    let data: unknown = null;
    if (text) {
      try {
        data = JSON.parse(text) as unknown;
      } catch {
        data = null;
      }
    }
    if (!res.ok) {
      const errObj = data as { detail?: unknown } | null;
      const msg =
        formatApiDetail(errObj?.detail) || text?.slice(0, 200)?.trim() || res.statusText;
      throw new Error(msg || `HTTP ${res.status}`);
    }
    return data as import("./statementImportTypes").ImportPreviewResponse;
  },

  confirmStatementImport: (body: {
    card_id: string;
    period_id: string;
    creates: {
      data: string;
      descricao: string;
      valor: string;
      parcela_atual?: number | null;
      parcela_total?: number | null;
      categoria_id?: string | null;
    }[];
    updates: {
      transaction_id: string;
      apply: boolean;
      descricao?: string;
      valor?: string;
      data?: string;
      categoria_id?: string | null;
    }[];
    deletes?: string[];
  }) =>
    request<{ created: number; updated: number; deleted: number; message: string }>(
      "/statement-import/confirm",
      {
        method: "POST",
        json: body,
      },
    ),

  // Transfers
  listTransfers: () => request<import("./types").TransferRow[]>("/transfers"),

  createTransfer: (body: Record<string, string | undefined>) =>
    request("/transfers", { method: "POST", json: body }),

  reportsMonthlyFlow: (ano: number) =>
    request<import("./types").MonthlyFlowRow[]>(`/reports/monthly-flow?ano=${ano}`),

  reportsExpensesByCategory: (periodId: string) =>
    request<import("./types").CategoryExpenseReportRow[]>(
      `/reports/expenses-by-category?period_id=${periodId}`,
    ),

  reportsBudgetVsActual: (periodId: string) =>
    request<import("./types").BudgetCompareRow[]>(`/reports/budget-vs-actual?period_id=${periodId}`),

  listInvestmentCatalog: () => request<import("./types").ListedAssetRow[]>("/investments/catalog"),

  listInvestments: () => request<import("./types").InvestmentRow[]>("/investments"),

  investmentsTotal: () => request<{ total_valor_atual: number }>("/investments/total"),

  createInvestment: (body: {
    listed_asset_id?: string | null;
    descricao?: string;
    tipo?: "renda_fixa" | "stock" | "fii" | "crypto";
    valor_aplicado: string;
    valor_atual: string;
    quantidade?: string;
    preco_medio?: string;
    preco_unitario_atual?: string;
  }) => request<import("./types").InvestmentRow>("/investments", { method: "POST", json: body }),

  updateInvestment: (
    id: string,
    body: Partial<{
      listed_asset_id: string | null;
      descricao: string;
      tipo: "renda_fixa" | "stock" | "fii" | "crypto";
      valor_aplicado: string;
      valor_atual: string;
      quantidade: string;
      preco_medio: string;
      preco_unitario_atual: string;
    }>,
  ) => request<import("./types").InvestmentRow>(`/investments/${id}`, { method: "PATCH", json: body }),

  deleteInvestment: (id: string) => request<void>(`/investments/${id}`, { method: "DELETE" }),

  // Debtors
  listDebtors: () => request<import("./types").DebtorLoanRow[]>("/debtors"),

  createDebtor: (body: {
    devedor_nome: string;
    valor_emprestado: string;
    data_emprestimo: string;
    destino_dinheiro: string;
    observacoes?: string;
    spender_id?: string | null;
  }) => request<import("./types").DebtorLoanRow>("/debtors", { method: "POST", json: body }),

  updateDebtor: (
    id: string,
    body: Partial<{
      devedor_nome: string;
      valor_emprestado: string;
      data_emprestimo: string;
      destino_dinheiro: string;
      observacoes: string;
      spender_id: string | null;
    }>,
  ) => request<import("./types").DebtorLoanRow>(`/debtors/${id}`, { method: "PATCH", json: body }),

  deleteDebtor: (id: string) => request<void>(`/debtors/${id}`, { method: "DELETE" }),

  addDebtorPayment: (
    loanId: string,
    body: { data_pagamento: string; valor_pago: string; observacao?: string },
  ) => request<import("./types").DebtorLoanRow>(`/debtors/${loanId}/payments`, { method: "POST", json: body }),

  deleteDebtorPayment: (paymentId: string) =>
    request<import("./types").DebtorLoanRow>(`/debtors/payments/${paymentId}`, { method: "DELETE" }),

  // Trips
  listTrips: () => request<import("./types").TripRow[]>("/trips"),

  getTrip: (id: string) => request<import("./types").TripRow>(`/trips/${id}`),

  createTrip: (body: {
    nome: string;
    destino?: string | null;
    data_inicio?: string | null;
    data_fim?: string | null;
    moeda_base?: string;
    orcamento_total?: string | null;
    status?: import("./types").TripStatus;
    observacoes?: string | null;
    participant_spender_ids?: string[];
  }) => request<import("./types").TripRow>("/trips", { method: "POST", json: body }),

  updateTrip: (
    id: string,
    body: Partial<{
      nome: string;
      destino: string | null;
      data_inicio: string | null;
      data_fim: string | null;
      moeda_base: string;
      orcamento_total: string | null;
      status: import("./types").TripStatus;
      observacoes: string | null;
    }>,
  ) => request<import("./types").TripRow>(`/trips/${id}`, { method: "PATCH", json: body }),

  deleteTrip: (id: string) => request<void>(`/trips/${id}`, { method: "DELETE" }),

  addTripParticipant: (tripId: string, body: { spender_id?: string; nome?: string }) =>
    request<import("./types").TripRow>(`/trips/${tripId}/participants`, {
      method: "POST",
      json: body,
    }),

  removeTripParticipant: (tripId: string, spenderId: string) =>
    request<import("./types").TripRow>(`/trips/${tripId}/participants/${spenderId}`, {
      method: "DELETE",
    }),

  listTripExpenses: (tripId: string) =>
    request<import("./types").TripExpenseRow[]>(`/trips/${tripId}/expenses`),

  createTripExpense: (
    tripId: string,
    body: {
      descricao: string;
      valor: string;
      moeda?: string;
      taxa_cambio?: string | null;
      data: string;
      categoria: import("./types").TripCategory;
      forma_pagamento?: import("./types").TripPaymentMethod;
      paid_by_spender_id: string;
      observacao?: string | null;
      shares?: { spender_id: string; valor: string }[] | null;
    },
  ) =>
    request<import("./types").TripExpenseRow>(`/trips/${tripId}/expenses`, {
      method: "POST",
      json: body,
    }),

  updateTripExpense: (
    expenseId: string,
    body: Partial<{
      descricao: string;
      valor: string;
      moeda: string;
      taxa_cambio: string | null;
      data: string;
      categoria: import("./types").TripCategory;
      forma_pagamento: import("./types").TripPaymentMethod;
      paid_by_spender_id: string;
      observacao: string | null;
      shares: { spender_id: string; valor: string }[] | null;
    }>,
  ) =>
    request<import("./types").TripExpenseRow>(`/trips/expenses/${expenseId}`, {
      method: "PATCH",
      json: body,
    }),

  deleteTripExpense: (expenseId: string) =>
    request<void>(`/trips/expenses/${expenseId}`, { method: "DELETE" }),

  pushTripExpenseToMonth: (expenseId: string, body: { period_id: string; pago?: boolean }) =>
    request<import("./types").TripExpenseRow>(
      `/trips/expenses/${expenseId}/push-to-month`,
      { method: "POST", json: body },
    ),

  tripSettlement: (tripId: string) =>
    request<import("./types").TripSettlementRow>(`/trips/${tripId}/settlement`),

  generateNotifications: () =>
    request<{ created: number; cleaned: number; ran: boolean }>("/notifications/gerar", {
      method: "POST",
    }),

  listNotifications: () =>
    request<import("./types").NotificationListResponse>("/notifications"),

  listNotificationHistory: () =>
    request<import("./types").NotificationListResponse>("/notifications/historico"),

  markNotificationRead: (id: string) =>
    request<import("./types").NotificationRow>(`/notifications/${id}/lida`, { method: "PATCH" }),

  markAllNotificationsRead: () =>
    request<{ count: number }>("/notifications/todas-lidas", { method: "PATCH" }),

  clearNotificationHistory: () =>
    request<{ count: number }>("/notifications/historico", { method: "DELETE" }),
};
