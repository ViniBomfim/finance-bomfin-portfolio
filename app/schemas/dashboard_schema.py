from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ExpenseCategoryBreakdown(BaseModel):
    """Despesas agregadas por categoria no período."""

    categoria_id: UUID
    categoria_nome: str
    total: Decimal


class ExpensePersonBreakdown(BaseModel):
    """Despesas agregadas por pessoa no período (com base no rateio de cartão)."""

    pessoa_id: UUID | None
    pessoa_nome: str
    total: Decimal


class ExpensePersonCategoryBreakdownRow(BaseModel):
    """Gasto por categoria dentro do agrupamento de uma pessoa."""

    categoria_id: UUID | None
    categoria_nome: str
    total: Decimal


class ExpensePersonCategoryBreakdown(BaseModel):
    """Despesas por pessoa, com detalhamento de categorias no período."""

    pessoa_id: UUID | None
    pessoa_nome: str
    total: Decimal
    categorias: list[ExpensePersonCategoryBreakdownRow]


class PersonInstallmentPurchaseRow(BaseModel):
    """Compra parcelada individual de uma pessoa."""

    compra_id: str
    card_id: UUID
    card_nome: str
    descricao: str
    valor_parcela: Decimal
    parcela_atual: int
    total_parcelas: int
    ate_data: date


class PersonInstallmentDashboardRow(BaseModel):
    """Resumo de compras parceladas por pessoa."""

    pessoa_id: UUID | None
    pessoa_nome: str
    compras_parceladas: int
    total_parcelas_mes: Decimal
    compras: list[PersonInstallmentPurchaseRow]


class CardPeriodTotal(BaseModel):
    """Total de transações de cartão no período."""

    card_id: UUID
    card_nome: str
    total: Decimal


class PersonCardUsageRow(BaseModel):
    """Total de gasto da pessoa em um cartão no período."""

    class TransactionRow(BaseModel):
        """Lançamento da pessoa dentro do cartão no período."""

        transaction_id: UUID
        descricao: str
        data: date
        valor: Decimal
        pago: bool
        falta_pagar: Decimal
        parcela_atual: int
        parcela_total: int

    card_id: UUID | None
    card_nome: str
    total: Decimal
    lancamentos: list[TransactionRow]


class PersonFixedExpenseUsageRow(BaseModel):
    """Total de gasto fixo da pessoa no período."""

    expense_id: UUID
    descricao: str
    total: Decimal
    pago: bool
    falta_pagar: Decimal


class PersonDebtorUsageRow(BaseModel):
    """Dívida pendente associada ao nome da pessoa em devedores."""

    loan_id: UUID
    spender_id: UUID | None = None
    devedor_nome: str
    valor_emprestado: Decimal
    valor_pago: Decimal
    valor_restante: Decimal
    pago: bool
    falta_pagar: Decimal
    data_emprestimo: date | None = None
    ultimo_pagamento_em: date | None = None
    dias_sem_pagamento: int | None = None


class PersonUsageDashboardRow(BaseModel):
    """Consolidado de uso por pessoa com totais por cartão e dívida pendente."""

    pessoa_id: UUID | None
    pessoa_nome: str
    total_cartoes: Decimal
    total_cartoes_falta_pagar: Decimal
    total_gastos_fixos: Decimal
    total_gastos_fixos_falta_pagar: Decimal
    total_divida_devedores: Decimal
    total_divida_devedores_falta_pagar: Decimal
    total_geral: Decimal
    total_falta_pagar: Decimal
    cartoes: list[PersonCardUsageRow]
    gastos_fixos: list[PersonFixedExpenseUsageRow]
    devedores: list[PersonDebtorUsageRow]


class FixedExpensePeriodLine(BaseModel):
    """Linha individual de despesa fixa no período (sem agregação)."""

    expense_id: UUID
    descricao: str
    data: date
    categoria_id: UUID
    categoria_nome: str
    valor: Decimal


class GoalProgressRow(BaseModel):
    """Progresso de uma meta financeira."""

    goal_id: UUID
    nome: str
    tipo: str = Field(..., pattern="^(short|medium|long)$")
    valor_meta: Decimal
    valor_atual: Decimal
    progress_percent: float = Field(..., description="valor_atual / valor_meta * 100")


class DashboardSummary(BaseModel):
    """Painel do período: saldo mensal, gastos por categoria, metas e cartões."""

    period_id: UUID
    total_income: Decimal
    total_expenses: Decimal
    monthly_balance: Decimal = Field(
        ...,
        description="Receitas − despesas no período (saldo do mês).",
    )
    pending_expenses: Decimal
    expenses_by_category: list[ExpenseCategoryBreakdown]
    expenses_by_person: list[ExpensePersonBreakdown]
    expenses_by_person_category: list[ExpensePersonCategoryBreakdown]
    usage_by_person_cards: list[PersonUsageDashboardRow]
    total_installments_month: Decimal
    person_installments: list[PersonInstallmentDashboardRow]
    goal_progress: list[GoalProgressRow]
    card_totals: list[CardPeriodTotal]
    fixed_expense_lines: list[FixedExpensePeriodLine]
    goals_total_saved: Decimal
    patrimonio_total: Decimal = Field(
        ...,
        description="monthly_balance + soma de valor_atual das metas (métrica simplificada).",
    )
