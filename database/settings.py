from typing import Optional

from sqlalchemy.orm import Session

from backend.utils.schemas import DuplicateStrategy
from database.models import Base, SystemSetting
from database.connection import engine


DUPLICATE_STRATEGY_KEY = "duplicate_strategy"

_tables_ready = False


def _ensure_tables() -> None:
    global _tables_ready
    if _tables_ready:
        return
    Base.metadata.create_all(bind=engine)
    _tables_ready = True


def get_setting(db: Session, key: str) -> Optional[str]:
    _ensure_tables()
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    return row.value if row else None


def set_setting(db: Session, key: str, value: str) -> None:
    _ensure_tables()
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = value
    else:
        row = SystemSetting(key=key, value=value)
        db.add(row)
    db.commit()


def get_duplicate_strategy(db: Session) -> DuplicateStrategy:
    raw = get_setting(db, DUPLICATE_STRATEGY_KEY)
    if not raw:
        set_setting(db, DUPLICATE_STRATEGY_KEY, DuplicateStrategy.PROMPT.value)
        return DuplicateStrategy.PROMPT

    try:
        return DuplicateStrategy(raw)
    except Exception:
        set_setting(db, DUPLICATE_STRATEGY_KEY, DuplicateStrategy.PROMPT.value)
        return DuplicateStrategy.PROMPT


def set_duplicate_strategy(db: Session, strategy: DuplicateStrategy) -> None:
    set_setting(db, DUPLICATE_STRATEGY_KEY, strategy.value)
