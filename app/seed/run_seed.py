"""Seed default categories and 12 months for the current year for a user.

Usage:
  python -m app.seed.run_seed --email user@example.com

Requires the user to exist (register via API first).
"""

from __future__ import annotations

import argparse
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models.category import Category
from app.models.period import Period
from app.models.user import User

DEFAULT_EXPENSE_CATEGORIES: list[tuple[str, str]] = [
    ("Geral", "#3d8bfd"),
    ("Carro", "#2563eb"),
    ("Contas", "#4A90D9"),
    ("Educação", "#7B68EE"),
    ("Saúde", "#50C878"),
    ("Restaurante", "#F5A623"),
    ("Transporte", "#BD10E0"),
    ("Streaming", "#D0021B"),
    ("Mercado", "#8B572A"),
    ("Pet", "#F8E71C"),
    ("Outros", "#9B9B9B"),
]
DEFAULT_INCOME_CATEGORIES: list[tuple[str, str]] = [
    ("Salários", "#34c759"),
]


def seed_user_data(db: Session, user: User) -> None:
    year = datetime.now().year
    for mes in range(1, 13):
        exists = db.execute(
            select(Period).where(
                Period.user_id == user.id,
                Period.mes == mes,
                Period.ano == year,
            )
        ).scalar_one_or_none()
        if exists is None:
            db.add(Period(mes=mes, ano=year, status="open", user_id=user.id))

    for nome, cor in DEFAULT_EXPENSE_CATEGORIES:
        exists = db.execute(
            select(Category).where(Category.user_id == user.id, Category.nome == nome)
        ).scalar_one_or_none()
        if exists is None:
            db.add(Category(nome=nome, cor=cor, tipo="expense", user_id=user.id))

    for nome, cor in DEFAULT_INCOME_CATEGORIES:
        exists = db.execute(
            select(Category).where(Category.user_id == user.id, Category.nome == nome)
        ).scalar_one_or_none()
        if exists is None:
            db.add(Category(nome=nome, cor=cor, tipo="income", user_id=user.id))

    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True, help="Registered user email")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == args.email)).scalar_one_or_none()
        if user is None:
            raise SystemExit(f"User not found: {args.email}")
        seed_user_data(db, user)
        print(f"Seed completed for {args.email} (year {datetime.now().year}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
