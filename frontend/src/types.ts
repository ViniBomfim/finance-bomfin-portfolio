export type UserMe = {
  id: string;
  username: string;
  name: string;
  email: string;
  is_admin: boolean;
  me_spender_id: string | null;
  has_avatar: boolean;
  created_at: string;
  updated_at: string;
};

export type AdminUserRow = UserMe;

export type AccessRequestRow = {
  id: string;
  username: string;
  email: string;
  created_at: string;
};

export type SessionSettingsResponse = {
  inactivity_logout_enabled: boolean;
  inactivity_logout_minutes: number;
};

export type SessionSettingsUpdate = {
  inactivity_logout_enabled?: boolean;
  inactivity_logout_minutes?: number;
};

export type SessionSettingsDefaults = {
  default_inactivity_logout_enabled: boolean;
  default_inactivity_logout_minutes: number;
  min_inactivity_logout_minutes: number;
  max_inactivity_logout_minutes: number;
};

export type AdminManagementStats = {
  total_registered: number;
  registered_last_7d: number;
  registered_last_30d: number;
  users_ever_logged_in: number;
  active_users_last_7d: number;
  logins_last_7d: number;
  logins_last_30d: number;
  errors_last_7d: number;
  errors_last_30d: number;
};

export type SystemErrorLogRow = {
  id: string;
  created_at: string;
  method: string;
  path: string;
  status_code: number;
  detail: string | null;
  traceback: string | null;
  user_id: string | null;
  user_email: string | null;
};

export type Period = {
  id: string;
  mes: number;
  ano: number;
  status: string;
};

export type Category = {
  id: string;
  nome: string;
  cor: string;
  tipo: "income" | "expense";
};

export type DashboardSummary = {
  period_id: string;
  total_income: string;
  total_expenses: string;
  monthly_balance: string;
  pending_expenses: string;
  expenses_by_category: {
    categoria_id: string;
    categoria_nome: string;
    total: string;
  }[];
  expenses_by_person: {
    pessoa_id: string | null;
    pessoa_nome: string;
    total: string;
  }[];
  expenses_by_person_category: {
    pessoa_id: string | null;
    pessoa_nome: string;
    total: string;
    categorias: {
      categoria_id: string | null;
      categoria_nome: string;
      total: string;
    }[];
  }[];
  usage_by_person_cards: {
    pessoa_id: string | null;
    pessoa_nome: string;
    total_cartoes: string;
    total_cartoes_falta_pagar: string;
    total_gastos_fixos: string;
    total_gastos_fixos_falta_pagar: string;
    total_divida_devedores: string;
    total_divida_devedores_falta_pagar: string;
    total_geral: string;
    total_falta_pagar: string;
    cartoes: {
      card_id: string | null;
      card_nome: string;
      total: string;
      lancamentos: {
        transaction_id: string;
        descricao: string;
        data: string;
        valor: string;
        pago: boolean;
        falta_pagar: string;
        parcela_atual: number;
        parcela_total: number;
      }[];
    }[];
    gastos_fixos: {
      expense_id: string;
      descricao: string;
      total: string;
      pago: boolean;
      falta_pagar: string;
    }[];
    devedores: {
      loan_id: string;
      spender_id?: string | null;
      devedor_nome: string;
      valor_emprestado: string;
      valor_pago: string;
      valor_restante: string;
      pago: boolean;
      falta_pagar: string;
      data_emprestimo?: string | null;
      ultimo_pagamento_em?: string | null;
      dias_sem_pagamento?: number | null;
    }[];
  }[];
  total_installments_month: string;
  person_installments: {
    pessoa_id: string | null;
    pessoa_nome: string;
    compras_parceladas: number;
    total_parcelas_mes: string;
    compras: {
      compra_id: string;
      card_id: string;
      card_nome: string;
      descricao: string;
      valor_parcela: string;
      parcela_atual: number;
      total_parcelas: number;
      ate_data: string;
    }[];
  }[];
  goal_progress: {
    goal_id: string;
    nome: string;
    tipo: "short" | "medium" | "long";
    valor_meta: string;
    valor_atual: string;
    progress_percent: number;
  }[];
  card_totals: { card_id: string; card_nome: string; total: string }[];
  fixed_expense_lines: {
    expense_id: string;
    descricao: string;
    data: string;
    categoria_id: string;
    categoria_nome: string;
    valor: string;
  }[];
  goals_total_saved: string;
};

export type BudgetCompareRow = {
  categoria_id: string;
  categoria_nome: string;
  planejado: string;
  realizado: string;
  diferenca: string;
};

/** Orçamento do período (lista em `/budgets`). */
export type BudgetListItem = {
  id: string;
  categoria_id: string;
  period_id: string;
  valor: string;
};

export type GoalRow = {
  id: string;
  nome: string;
  tipo: string;
  valor_meta: string;
  valor_atual: string;
  data_inicio: string;
  data_fim: string | null;
  status: string;
};

export type GoalProgressApi = {
  goal_id: string;
  tipo: "short" | "medium" | "long";
  valor_meta: string;
  valor_atual: string;
  progress_percent: number;
};

export type GoalPoolSummaryApi = {
  period_id: string;
  pool_total: string;
  deposited_total: string;
  available: string;
};

export type CardRow = {
  id: string;
  nome: string;
  banco: string;
  limite: string;
  fechamento: number;
  vencimento: number;
};

export type ExpenseRow = {
  id: string;
  descricao: string;
  valor: string;
  data: string;
  tipo: "fixed" | "variable" | "card";
  recorrente: boolean;
  pago: boolean;
  period_id: string;
  categoria_id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  shares?: {
    spender_id: string;
    spender_nome: string;
    valor: string;
    pago?: boolean;
  }[];
};

export type CardTransactionShareRow = {
  spender_id: string;
  spender_nome: string;
  valor: string;
  pago?: boolean;
};

export type CardTransactionRow = {
  id: string;
  descricao: string;
  valor: string;
  data: string;
  pago: boolean;
  from_statement: boolean;
  installment_number: number;
  installment_total: number;
  installment_group_id?: string | null;
  card_id: string;
  categoria_id: string | null;
  categoria_nome: string | null;
  period_id: string;
  shares?: CardTransactionShareRow[];
};

export type SpenderRow = {
  id: string;
  nome: string;
  user_id: string;
  created_at: string;
  updated_at: string;
};

export type CardSpenderSummaryLine = {
  transaction_id: string;
  descricao: string;
  data: string;
  valor_parte: string;
};

export type CardSpenderSummaryGroup = {
  spender_id: string | null;
  spender_nome: string | null;
  total: string;
  lines: CardSpenderSummaryLine[];
};

export type CardSpenderSummary = {
  card_id: string;
  period_id: string;
  groups: CardSpenderSummaryGroup[];
};

export type TransferRow = {
  id: string;
  source_type: string;
  source_id: string | null;
  destination_type: string;
  destination_id: string | null;
  valor: string;
  data: string;
};

export type MonthlyFlowRow = {
  mes: number;
  ano: number;
  period_id: string;
  receitas: string;
  despesas: string;
  saldo: string;
};

export type CategoryExpenseReportRow = {
  categoria_id: string;
  categoria_nome: string;
  cor: string;
  total: string;
};

/** Alinhado a `InvestmentTipo` no backend (`app/schemas/investment_schema.py`). */
export type InvestmentTipo = "renda_fixa" | "stock" | "fii" | "crypto";

export type ListedAssetRow = {
  id: string;
  codigo: string;
  nome: string;
  tipo: InvestmentTipo;
};

export type InvestmentRow = {
  id: string;
  descricao: string;
  tipo: InvestmentTipo;
  listed_asset_id: string | null;
  /** Valores monetários como string (serialização JSON do `Decimal` no backend). */
  valor_aplicado: string;
  valor_atual: string;
  /** Cotas (FII); opcional. */
  quantidade: string | null;
  preco_medio: string | null;
  preco_unitario_atual: string | null;
};

export type DebtorPaymentRow = {
  id: string;
  data_pagamento: string;
  valor_pago: string;
  observacao: string | null;
  emprestimo_id: string;
  created_at: string;
  updated_at: string;
};

export type DebtorLoanRow = {
  id: string;
  devedor_nome: string;
  valor_emprestado: string;
  data_emprestimo: string;
  destino_dinheiro: string;
  observacoes: string | null;
  user_id: string;
  spender_id?: string | null;
  spender_nome?: string | null;
  valor_pago: string;
  valor_restante: string;
  status: "pendente" | "quitado";
  ultimo_pagamento_em?: string | null;
  dias_sem_pagamento?: number | null;
  pagamentos: DebtorPaymentRow[];
  created_at: string;
  updated_at: string;
};

export type TripStatus = "planning" | "ongoing" | "closed";

export type TripCategory =
  | "hotel"
  | "transport"
  | "tour"
  | "meal"
  | "shopping"
  | "leisure"
  | "other";

export type TripPaymentMethod = "cash" | "card" | "transfer" | "other";

export type TripParticipantRow = {
  spender_id: string;
  spender_nome: string;
};

export type TripCategoryTotalRow = {
  categoria: TripCategory;
  total: string;
};

export type TripPersonTotalRow = {
  spender_id: string;
  spender_nome: string;
  total_pago: string;
  total_consumido: string;
  saldo: string;
};

export type TripPersonCategoryLineRow = {
  categoria: TripCategory;
  total: string;
};

export type TripPersonConsumptionBreakdownRow = {
  spender_id: string;
  spender_nome: string;
  total: string;
  por_categoria: TripPersonCategoryLineRow[];
};

export type TripRow = {
  id: string;
  nome: string;
  destino: string | null;
  data_inicio: string | null;
  data_fim: string | null;
  moeda_base: string;
  orcamento_total: string | null;
  status: TripStatus;
  observacoes: string | null;
  user_id: string;
  participants: TripParticipantRow[];
  total_gasto: string;
  total_por_categoria: TripCategoryTotalRow[];
  total_por_pessoa: TripPersonTotalRow[];
  consumo_por_pessoa?: TripPersonConsumptionBreakdownRow[];
  created_at: string;
  updated_at: string;
};

export type TripExpenseShareRow = {
  spender_id: string;
  spender_nome: string;
  valor: string;
};

export type TripExpenseRow = {
  id: string;
  trip_id: string;
  user_id: string;
  descricao: string;
  valor: string;
  moeda: string;
  taxa_cambio: string | null;
  valor_base: string;
  data: string;
  categoria: TripCategory;
  forma_pagamento: TripPaymentMethod;
  paid_by_spender_id: string;
  paid_by_nome: string;
  observacao: string | null;
  pushed_expense_id: string | null;
  shares: TripExpenseShareRow[];
  created_at: string;
  updated_at: string;
};

export type TripSettlementTransferRow = {
  from_spender_id: string;
  from_spender_nome: string;
  to_spender_id: string;
  to_spender_nome: string;
  valor: string;
};

export type TripSettlementRow = {
  trip_id: string;
  moeda_base: string;
  saldos: TripPersonTotalRow[];
  transferencias: TripSettlementTransferRow[];
};

export type NotificationModulo =
  | "cartoes"
  | "devedores"
  | "metas"
  | "viagens"
  | "gastos_fixos";

export type NotificationSeveridade = "urgente" | "atencao" | "info";

export type NotificationRow = {
  id: string;
  user_id: string;
  modulo: NotificationModulo;
  tipo: string;
  severidade: NotificationSeveridade;
  titulo: string;
  subtitulo: string;
  lida: boolean;
  link: string;
  referencia_id: string;
  criado_em: string;
  lida_em: string | null;
};

export type NotificationGrupos = {
  cartoes: NotificationRow[];
  devedores: NotificationRow[];
  metas: NotificationRow[];
  viagens: NotificationRow[];
  gastos_fixos: NotificationRow[];
};

export type NotificationListResponse = {
  total: number;
  grupos: NotificationGrupos;
};

