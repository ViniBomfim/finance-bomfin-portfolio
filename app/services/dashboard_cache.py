from __future__ import annotations

from time import monotonic
from typing import Any
from uuid import UUID

from app.schemas.dashboard_schema import DashboardSummary


class DashboardCache:
    SUMMARY_TTL_SECONDS = 30.0
    _summary_cache: dict[tuple[UUID, UUID], tuple[float, DashboardSummary]] = {}
    _block_cache: dict[tuple[str, UUID, UUID | None], tuple[float, Any]] = {}

    @classmethod
    def get_summary(cls, user_id: UUID, period_id: UUID) -> DashboardSummary | None:
        cached = cls._summary_cache.get((user_id, period_id))
        if cached is None:
            return None
        expires_at, payload = cached
        if monotonic() >= expires_at:
            return None
        return payload.model_copy(deep=True)

    @classmethod
    def set_summary(cls, user_id: UUID, period_id: UUID, payload: DashboardSummary) -> None:
        cls._summary_cache[(user_id, period_id)] = (monotonic() + cls.SUMMARY_TTL_SECONDS, payload)

    @classmethod
    def get_block(cls, block_name: str, user_id: UUID, period_id: UUID | None) -> Any | None:
        cached = cls._block_cache.get((block_name, user_id, period_id))
        if cached is None:
            return None
        expires_at, payload = cached
        if monotonic() >= expires_at:
            return None
        return payload

    @classmethod
    def set_block(cls, block_name: str, user_id: UUID, period_id: UUID | None, payload: Any) -> None:
        cls._block_cache[(block_name, user_id, period_id)] = (
            monotonic() + cls.SUMMARY_TTL_SECONDS,
            payload,
        )

    @classmethod
    def invalidate_user_period(cls, user_id: UUID, period_id: UUID) -> None:
        cls._summary_cache.pop((user_id, period_id), None)
        block_keys = [key for key in cls._block_cache.keys() if key[1] == user_id and key[2] == period_id]
        for key in block_keys:
            cls._block_cache.pop(key, None)

    @classmethod
    def invalidate_user(cls, user_id: UUID) -> None:
        summary_keys = [key for key in cls._summary_cache.keys() if key[0] == user_id]
        for key in summary_keys:
            cls._summary_cache.pop(key, None)
        block_keys = [key for key in cls._block_cache.keys() if key[1] == user_id]
        for key in block_keys:
            cls._block_cache.pop(key, None)
