"""Recuperação local: redefinir senha, criar usuário comum ou criar admin.

Exemplos:
  python -m app.cli.manage_user reset-password --email voce@email.com --password "NovaSenhaSegura"
  python -m app.cli.manage_user set-username --email voce@email.com --username "nome.sobrenome"
  python -m app.cli.manage_user create-user --username nome.sobrenome --email user@local --name "Nome" --password "SenhaSegura"
  python -m app.cli.manage_user create-admin --username admin.sistema --email admin@local --name "Admin" --password "SenhaSegura"
  python -m app.cli.manage_user promote-admin --email voce@email.com
"""

from __future__ import annotations

import argparse

from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import get_password_hash
from app.core.username import is_valid_username, normalize_username
from app.database.connection import SessionLocal
from app.models.user import User
from app.schemas.auth_schema import RegisterRequest
from app.services.auth_service import AuthService


def _validate_username(username: str) -> str:
    normalized = normalize_username(username)
    if not is_valid_username(normalized):
        raise SystemExit("Usuário inválido. Informe de 1 a 64 caracteres.")
    return normalized


def cmd_reset_password(email: str, password: str) -> None:
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            raise SystemExit(f"Usuário não encontrado: {email}")
        user.password_hash = get_password_hash(password)
        db.add(user)
        db.commit()
        print(f"Senha atualizada para {email}.")
    finally:
        db.close()


def cmd_set_username(email: str, username: str) -> None:
    login_username = _validate_username(username)
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            raise SystemExit(f"Usuário não encontrado: {email}")
        existing = db.execute(select(User).where(User.username == login_username)).scalar_one_or_none()
        if existing is not None and existing.id != user.id:
            raise SystemExit(f"Usuário de login já em uso: {login_username}")
        user.username = login_username
        db.add(user)
        db.commit()
        print(f"Login atualizado: {login_username} ({email})")
    finally:
        db.close()


def cmd_create_user(username: str, email: str, name: str, password: str) -> None:
    login_username = _validate_username(username)
    db = SessionLocal()
    try:
        try:
            AuthService(db).register_as_admin(
                RegisterRequest(
                    username=login_username,
                    name=name,
                    email=email,
                    password=password,
                )
            )
        except HTTPException as e:
            raise SystemExit(str(e.detail)) from None
        print(f"Usuário criado: {login_username} ({email})")
    finally:
        db.close()


def cmd_promote_admin(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            raise SystemExit(f"Usuário não encontrado: {email}")
        if user.is_admin:
            print(f"Usuário já é admin: {email}")
            return
        user.is_admin = True
        db.add(user)
        db.commit()
        print(f"Usuário promovido para admin: {email}")
    finally:
        db.close()


def cmd_create_admin(username: str, email: str, name: str, password: str) -> None:
    login_username = _validate_username(username)
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is not None:
            existing = db.execute(select(User).where(User.username == login_username)).scalar_one_or_none()
            if existing is not None and existing.id != user.id:
                raise SystemExit(f"Usuário de login já em uso: {login_username}")
            user.username = login_username
            user.name = name
            user.password_hash = get_password_hash(password)
            user.is_admin = True
            db.add(user)
            db.commit()
            print(f"Usuário promovido para admin: {login_username} ({email})")
            return

        try:
            user = AuthService(db).register_as_admin(
                RegisterRequest(
                    username=login_username,
                    name=name,
                    email=email,
                    password=password,
                )
            )
        except HTTPException as e:
            raise SystemExit(str(e.detail)) from None
        user.is_admin = True
        db.add(user)
        db.commit()
        print(f"Usuário admin criado: {login_username} ({email})")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Gerenciar usuário local (SQLite/DB configurado no .env).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_reset = sub.add_parser("reset-password", help="Redefine a senha de um e-mail já cadastrado.")
    p_reset.add_argument("--email", required=True)
    p_reset.add_argument("--password", required=True)

    p_set_username = sub.add_parser(
        "set-username",
        help="Define o username de login (não gera a partir do e-mail).",
    )
    p_set_username.add_argument("--email", required=True)
    p_set_username.add_argument("--username", required=True)

    p_create = sub.add_parser("create-user", help="Cria um novo usuário (mesmo fluxo do cadastro na API).")
    p_create.add_argument("--username", required=True)
    p_create.add_argument("--email", required=True)
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--password", required=True)

    p_create_admin = sub.add_parser("create-admin", help="Cria (ou promove) um usuário administrador.")
    p_create_admin.add_argument("--username", required=True)
    p_create_admin.add_argument("--email", required=True)
    p_create_admin.add_argument("--name", required=True)
    p_create_admin.add_argument("--password", required=True)

    p_promote = sub.add_parser(
        "promote-admin",
        help="Promove um usuário já cadastrado a admin (não altera a senha).",
    )
    p_promote.add_argument("--email", required=True)

    args = parser.parse_args()
    if args.command == "reset-password":
        cmd_reset_password(args.email, args.password)
    elif args.command == "set-username":
        cmd_set_username(args.email, args.username)
    elif args.command == "create-user":
        cmd_create_user(args.username, args.email, args.name, args.password)
    elif args.command == "create-admin":
        cmd_create_admin(args.username, args.email, args.name, args.password)
    elif args.command == "promote-admin":
        cmd_promote_admin(args.email)


if __name__ == "__main__":
    main()
