from collections.abc import Collection, Sequence
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification

MODULES = ("cartoes", "devedores", "metas", "viagens", "gastos_fixos")


class NotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_unread(self, user_id: UUID) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id, Notification.lida.is_(False))
            .order_by(Notification.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_read(self, user_id: UUID, *, per_module: int = 50) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id, Notification.lida.is_(True))
            .order_by(Notification.lida_em.desc(), Notification.created_at.desc())
        )
        rows = list(self.db.execute(stmt).scalars().all())
        by_module: dict[str, list[Notification]] = {m: [] for m in MODULES}
        result: list[Notification] = []
        for row in rows:
            bucket = by_module.get(row.modulo)
            if bucket is None:
                continue
            if len(bucket) >= per_module:
                continue
            bucket.append(row)
            result.append(row)
        return result

    def get_by_id(self, notification_id: UUID, user_id: UUID) -> Notification | None:
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def exists_unread(self, user_id: UUID, tipo: str, referencia_id: str) -> bool:
        return self.get_unread(user_id, tipo, referencia_id) is not None

    def get_unread(self, user_id: UUID, tipo: str, referencia_id: str) -> Notification | None:
        stmt = (
            select(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.tipo == tipo,
                Notification.referencia_id == referencia_id,
                Notification.lida.is_(False),
            )
            .order_by(Notification.created_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def delete_unread_stale(
        self,
        user_id: UUID,
        tipos: Sequence[str],
        keep_keys: Collection[tuple[str, str]],
        *,
        commit: bool = True,
    ) -> int:
        """Remove não lidas dos `tipos` cujas chaves (tipo, referencia_id) não estão em `keep_keys`."""
        if not tipos:
            return 0
        stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.lida.is_(False),
            Notification.tipo.in_(tuple(tipos)),
        )
        rows = [
            row
            for row in self.db.execute(stmt).scalars().all()
            if (row.tipo, row.referencia_id) not in keep_keys
        ]
        for row in rows:
            self.db.delete(row)
        if rows and commit:
            self.db.commit()
        return len(rows)

    def create(self, row: Notification, *, commit: bool = True) -> Notification:
        self.db.add(row)
        if commit:
            self.db.commit()
            self.db.refresh(row)
        else:
            self.db.flush()
        return row

    def update_content(
        self,
        row: Notification,
        *,
        severidade: str,
        titulo: str,
        subtitulo: str,
        link: str,
        commit: bool = True,
    ) -> bool:
        """Atualiza o conteúdo visível da notificação. True quando algo mudou."""
        changed = (
            row.severidade != severidade
            or row.titulo != titulo
            or row.subtitulo != subtitulo
            or row.link != link
        )
        if not changed:
            return False
        row.severidade = severidade
        row.titulo = titulo
        row.subtitulo = subtitulo
        row.link = link
        self.db.add(row)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return True

    def mark_read(self, row: Notification) -> Notification:
        row.lida = True
        row.lida_em = datetime.now(timezone.utc)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def mark_all_read(self, user_id: UUID) -> int:
        rows = self.list_unread(user_id)
        if not rows:
            return 0
        now = datetime.now(timezone.utc)
        for row in rows:
            row.lida = True
            row.lida_em = now
            self.db.add(row)
        self.db.commit()
        return len(rows)

    def delete_old_read(self, *, days: int = 90, user_id: UUID | None = None) -> int:
        limite = datetime.now(timezone.utc) - timedelta(days=days)
        filters = [
            Notification.lida.is_(True),
            Notification.lida_em.is_not(None),
            Notification.lida_em < limite,
        ]
        if user_id is not None:
            filters.append(Notification.user_id == user_id)
        stmt = select(Notification).where(*filters)
        rows = list(self.db.execute(stmt).scalars().all())
        for row in rows:
            self.db.delete(row)
        if rows:
            self.db.commit()
        return len(rows)
