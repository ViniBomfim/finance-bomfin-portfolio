"""Compatibilidade: o modelo ORM de despesa está em `app.expenses.model`."""

from app.expenses.model import Expense

__all__ = ["Expense"]
