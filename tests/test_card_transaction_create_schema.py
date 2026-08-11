from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.schemas.card_schema import CardTransactionCreate


def _base():
    return dict(
        descricao="Teste",
        valor=Decimal("100.00"),
        card_id=uuid4(),
        period_id=uuid4(),
        data=date(2026, 4, 10),
    )


def test_vista_nunca_auto_generate() -> None:
    d = CardTransactionCreate(
        **_base(),
        installment_total=1,
        installment_number=3,
        auto_generate_future_installments=True,
    )
    assert d.auto_generate_future_installments is False


def test_parcela_fatura_default_auto_generate() -> None:
    d = CardTransactionCreate(
        **_base(),
        installment_total=9,
        installment_number=2,
        auto_generate_future_installments=None,
    )
    assert d.auto_generate_future_installments is True


def test_parcela_manual_sem_numero_sem_auto() -> None:
    """Valor total em N parcelas iguais (sem installment_number): não usa geração por fatura."""
    b = _base()
    b["valor"] = Decimal("900.00")
    d = CardTransactionCreate(
        **b,
        installment_total=9,
        installment_number=None,
        auto_generate_future_installments=None,
    )
    assert d.auto_generate_future_installments is False


def test_parcela_um_lancamento_explicito_false() -> None:
    d = CardTransactionCreate(
        **_base(),
        installment_total=10,
        installment_number=3,
        auto_generate_future_installments=False,
    )
    assert d.auto_generate_future_installments is False
