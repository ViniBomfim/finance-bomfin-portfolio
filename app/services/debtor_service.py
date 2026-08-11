from decimal import Decimal
from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.debtor_loan import DebtorLoan
from app.models.debtor_payment import DebtorPayment
from app.repositories.debtor_repository import DebtorRepository
from app.repositories.spender_repository import SpenderRepository
from app.schemas.debtor_schema import DebtorLoanCreate, DebtorLoanUpdate, DebtorPaymentCreate


class DebtorService:
    def __init__(self, db: Session) -> None:
        self._repo = DebtorRepository(db)
        self._spenders = SpenderRepository(db)

    def list_loans(self, user_id: UUID) -> list[dict]:
        rows = self._repo.list_loans_by_user(user_id)
        return [self._serialize_loan(row) for row in rows]

    def create_loan(self, user_id: UUID, data: DebtorLoanCreate) -> dict:
        spender_id = self._validate_spender(data.spender_id, user_id)
        row = DebtorLoan(
            devedor_nome=data.devedor_nome.strip(),
            valor_emprestado=data.valor_emprestado,
            data_emprestimo=data.data_emprestimo,
            destino_dinheiro=data.destino_dinheiro.strip(),
            observacoes=data.observacoes.strip() if data.observacoes else None,
            spender_id=spender_id,
            user_id=user_id,
        )
        created = self._repo.create_loan(row)
        hydrated = self._repo.get_loan_by_id(created.id, user_id)
        if hydrated is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Loan not found")
        return self._serialize_loan(hydrated)

    def update_loan(self, user_id: UUID, loan_id: UUID, data: DebtorLoanUpdate) -> dict:
        row = self._repo.get_loan_by_id(loan_id, user_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
        if data.devedor_nome is not None:
            row.devedor_nome = data.devedor_nome.strip()
        if data.valor_emprestado is not None:
            valor_pago = self._sum_paid(row.pagamentos)
            if data.valor_emprestado < valor_pago:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Valor emprestado não pode ser menor que o total já pago.",
                )
            row.valor_emprestado = data.valor_emprestado
        if data.data_emprestimo is not None:
            row.data_emprestimo = data.data_emprestimo
        if data.destino_dinheiro is not None:
            row.destino_dinheiro = data.destino_dinheiro.strip()
        if data.observacoes is not None:
            row.observacoes = data.observacoes.strip()
        if "spender_id" in data.model_fields_set:
            row.spender_id = self._validate_spender(data.spender_id, user_id)
        updated = self._repo.update_loan(row)
        hydrated = self._repo.get_loan_by_id(updated.id, user_id)
        if hydrated is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Loan not found")
        return self._serialize_loan(hydrated)

    def delete_loan(self, user_id: UUID, loan_id: UUID) -> None:
        row = self._repo.get_loan_by_id(loan_id, user_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
        self._repo.delete_loan(row)

    def add_payment(self, user_id: UUID, loan_id: UUID, data: DebtorPaymentCreate) -> dict:
        row = self._repo.get_loan_by_id(loan_id, user_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
        restante = self._remaining(row)
        if data.valor_pago > restante:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Valor do pagamento excede o valor restante do empréstimo.",
            )
        payment = DebtorPayment(
            data_pagamento=data.data_pagamento,
            valor_pago=data.valor_pago,
            observacao=data.observacao.strip() if data.observacao else None,
            emprestimo_id=row.id,
        )
        self._repo.create_payment(payment)
        refreshed = self._repo.get_loan_by_id(row.id, user_id)
        if refreshed is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Loan not found")
        serialized = self._serialize_loan(refreshed)
        try:
            from app.services.notification_service import NotificationService, _money

            NotificationService(self._repo.db).create_event(
                user_id=user_id,
                modulo="devedores",
                tipo="pagamento_recebido",
                severidade="info",
                titulo=f"Pagamento recebido de {row.devedor_nome}",
                subtitulo=f"{_money(data.valor_pago)} · restante {_money(serialized['valor_restante'])}",
                link="/devedores",
                referencia_id=str(payment.id),
            )
        except Exception:
            pass
        return serialized

    def delete_payment(self, user_id: UUID, payment_id: UUID) -> dict:
        payment = self._repo.get_payment_by_id(payment_id, user_id)
        if payment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        loan_id = payment.emprestimo_id
        self._repo.delete_payment(payment)
        refreshed = self._repo.get_loan_by_id(loan_id, user_id)
        if refreshed is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
        return self._serialize_loan(refreshed)

    def _serialize_loan(self, row: DebtorLoan) -> dict:
        valor_pago = self._sum_paid(row.pagamentos)
        valor_restante = (row.valor_emprestado - valor_pago).quantize(Decimal("0.01"))
        if valor_restante < Decimal("0.00"):
            valor_restante = Decimal("0.00")
        status_value = "quitado" if valor_restante == Decimal("0.00") else "pendente"
        ultimo_pagamento_em = self._latest_payment_date(row.pagamentos)
        base_date = ultimo_pagamento_em or row.data_emprestimo
        dias_sem_pagamento = max(0, (date.today() - base_date).days) if base_date else None
        return {
            "id": row.id,
            "devedor_nome": row.devedor_nome,
            "valor_emprestado": row.valor_emprestado,
            "data_emprestimo": row.data_emprestimo,
            "destino_dinheiro": row.destino_dinheiro,
            "observacoes": row.observacoes,
            "user_id": row.user_id,
            "spender_id": row.spender_id,
            "spender_nome": row.spender.nome if row.spender is not None else None,
            "valor_pago": valor_pago,
            "valor_restante": valor_restante,
            "status": status_value,
            "ultimo_pagamento_em": ultimo_pagamento_em,
            "dias_sem_pagamento": dias_sem_pagamento,
            "pagamentos": list(row.pagamentos),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _sum_paid(payments: list[DebtorPayment]) -> Decimal:
        return sum((p.valor_pago for p in payments), start=Decimal("0.00")).quantize(Decimal("0.01"))

    @staticmethod
    def _latest_payment_date(payments: list[DebtorPayment]) -> date | None:
        if not payments:
            return None
        return max((p.data_pagamento for p in payments), default=None)

    def _remaining(self, row: DebtorLoan) -> Decimal:
        return (row.valor_emprestado - self._sum_paid(row.pagamentos)).quantize(Decimal("0.01"))

    def _validate_spender(self, spender_id: UUID | None, user_id: UUID) -> UUID | None:
        if spender_id is None:
            return None
        spender = self._spenders.get_by_id(spender_id, user_id)
        if spender is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pessoa do cartão inválida para este usuário.",
            )
        return spender.id
