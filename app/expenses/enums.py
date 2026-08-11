from enum import StrEnum


class ExpenseType(StrEnum):
    """Tipo de despesa: fixa, variável ou cartão."""

    FIXED = "fixed"
    VARIABLE = "variable"
    CARD = "card"


class RecurrenceValueMode(StrEnum):
    """Define como preencher o valor das próximas recorrências."""

    SAME_VALUE = "same_value"
    BLANK = "blank"
