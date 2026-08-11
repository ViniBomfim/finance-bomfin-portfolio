from sqlalchemy.orm import Session

from app.models.platform_setting import PlatformSetting


class PlatformSettingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, key: str) -> PlatformSetting | None:
        return self.db.get(PlatformSetting, key)

    def set(self, key: str, value: str) -> PlatformSetting:
        row = self.get(key)
        if row is None:
            row = PlatformSetting(key=key, value=value)
            self.db.add(row)
        else:
            row.value = value
        self.db.commit()
        self.db.refresh(row)
        return row
