from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUserId
from app.expenses.deps import ExpenseListFilterDep, ExpenseServiceDep
from app.expenses.schemas import (
    ExpenseCreate,
    ExpenseResponse,
    ExpenseShareResponse,
    ExpenseUpdate,
    GenerateInstallmentsRequest,
)
from app.schemas.installment_schema import InstallmentResponse

router = APIRouter(prefix="/expenses", tags=["expenses"])


def _expense_response(expense) -> ExpenseResponse:
    shares: list[ExpenseShareResponse] = []
    for sh in expense.shares or []:
        shares.append(
            ExpenseShareResponse(
                spender_id=sh.spender_id,
                spender_nome=sh.spender.nome if sh.spender else "",
                valor=sh.valor,
                pago=bool(getattr(sh, "pago", False)),
            )
        )
    return ExpenseResponse(
        id=expense.id,
        descricao=expense.descricao,
        valor=expense.valor,
        data=expense.data,
        tipo=expense.tipo,
        recorrente=expense.recorrente,
        pago=expense.pago,
        period_id=expense.period_id,
        categoria_id=expense.categoria_id,
        user_id=expense.user_id,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
        shares=shares,
    )


@router.post(
    "",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar despesa",
)
def create_expense(
    data: ExpenseCreate,
    user_id: CurrentUserId,
    svc: ExpenseServiceDep,
) -> ExpenseResponse:
    expense = svc.create(user_id, data)
    return _expense_response(expense)


@router.get(
    "",
    response_model=list[ExpenseResponse],
    summary="Listar despesas",
    description="Obrigatório informar `period_id` **ou** `categoria_id` (query).",
)
def list_expenses(
    user_id: CurrentUserId,
    filters: ExpenseListFilterDep,
    svc: ExpenseServiceDep,
) -> list[ExpenseResponse]:
    if filters.period_id is not None:
        rows = svc.list_by_period(user_id, filters.period_id)
    else:
        assert filters.categoria_id is not None
        rows = svc.list_by_category(user_id, filters.categoria_id)
    return [_expense_response(x) for x in rows]


@router.get(
    "/{expense_id}",
    response_model=ExpenseResponse,
    summary="Obter despesa por ID",
)
def get_expense(
    expense_id: UUID,
    user_id: CurrentUserId,
    svc: ExpenseServiceDep,
) -> ExpenseResponse:
    expense = svc.get(user_id, expense_id)
    return _expense_response(expense)


@router.patch(
    "/{expense_id}",
    response_model=ExpenseResponse,
    summary="Atualizar despesa",
)
def update_expense(
    expense_id: UUID,
    data: ExpenseUpdate,
    user_id: CurrentUserId,
    svc: ExpenseServiceDep,
) -> ExpenseResponse:
    expense = svc.update(user_id, expense_id, data)
    return _expense_response(expense)


@router.delete(
    "/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover despesa",
)
def delete_expense(
    expense_id: UUID,
    user_id: CurrentUserId,
    svc: ExpenseServiceDep,
) -> None:
    svc.delete(user_id, expense_id)


@router.post(
    "/{expense_id}/paid",
    response_model=ExpenseResponse,
    summary="Marcar como paga (ou não paga)",
)
def mark_paid(
    expense_id: UUID,
    user_id: CurrentUserId,
    svc: ExpenseServiceDep,
    pago: bool = Query(True, description="true = pago, false = pendente"),
) -> ExpenseResponse:
    expense = svc.mark_paid(user_id, expense_id, pago=pago)
    return _expense_response(expense)


@router.post(
    "/{expense_id}/shares/{spender_id}/paid",
    response_model=ExpenseResponse,
    summary="Marcar parte de uma pessoa como paga (ou pendente)",
)
def mark_share_paid(
    expense_id: UUID,
    spender_id: UUID,
    user_id: CurrentUserId,
    svc: ExpenseServiceDep,
    pago: bool = Query(True, description="true = pago, false = pendente"),
) -> ExpenseResponse:
    expense = svc.set_share_paid(user_id, expense_id, spender_id, pago=pago)
    return _expense_response(expense)


@router.post(
    "/{expense_id}/installments",
    response_model=list[InstallmentResponse],
    summary="Gerar parcelas a partir do valor total",
)
def generate_installments(
    expense_id: UUID,
    body: GenerateInstallmentsRequest,
    user_id: CurrentUserId,
    svc: ExpenseServiceDep,
) -> list[InstallmentResponse]:
    rows = svc.generate_installments(user_id, expense_id, body)
    return [InstallmentResponse.model_validate(x) for x in rows]
