"""ORM field types."""
from __future__ import annotations

import datetime as dt
import json
from typing import Any, Callable

_MISSING: Any = object()


class Field:
    """Base field.

    Common options:
        default   – value or callable (``default=list``)
        null      – allow NULL (default: True unless ``pk``/default given)
        unique    – unique constraint
        index     – create an index
        pk        – primary key
    """

    py_type: type | tuple = object
    sql_kind = "TEXT"

    def __init__(
        self,
        *,
        default: Any = _MISSING,
        null: bool | None = None,
        unique: bool = False,
        index: bool = False,
        pk: bool = False,
        generated: bool | None = None,
        choices: list | tuple | None = None,
        description: str | None = None,
    ):
        self.default = default
        self.pk = pk
        self.unique = unique or pk
        self.index = index
        self.generated = generated
        self.choices = tuple(choices) if choices else None
        self.description = description
        self.null = (not pk and default is _MISSING) if null is None else null
        self.name: str = ""
        self.column: str = ""
        self.model: Any = None

    # called by the metaclass
    def bind(self, model: Any, name: str) -> None:
        self.model, self.name = model, name
        self.column = self.column or name

    def has_default(self) -> bool:
        return self.default is not _MISSING

    def get_default(self) -> Any:
        if self.default is _MISSING:
            return None
        return self.default() if callable(self.default) else self.default

    # python <-> db
    def to_db(self, value: Any, dialect: str) -> Any:
        return value

    def from_db(self, value: Any, dialect: str) -> Any:
        return value

    def validate(self, value: Any) -> Any:
        if value is None:
            return None
        if self.choices and value not in self.choices:
            raise ValueError(f"{self.name}: {value!r} ruxsat etilmagan ({self.choices})")
        return value

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"


class Int(Field):
    py_type = int
    sql_kind = "INT"

    def validate(self, value: Any) -> Any:
        return None if value is None else super().validate(int(value))

    def from_db(self, value: Any, dialect: str) -> Any:
        return None if value is None else int(value)


class BigInt(Int):
    sql_kind = "BIGINT"


class Float(Field):
    py_type = float
    sql_kind = "FLOAT"

    def validate(self, value: Any) -> Any:
        return None if value is None else super().validate(float(value))

    def from_db(self, value: Any, dialect: str) -> Any:
        return None if value is None else float(value)


class Str(Field):
    py_type = str

    def __init__(self, max_length: int = 255, **kw: Any):
        super().__init__(**kw)
        self.max_length = max_length

    @property
    def sql_kind(self) -> str:  # type: ignore[override]
        return f"VARCHAR({self.max_length})"

    def validate(self, value: Any) -> Any:
        if value is None:
            return None
        value = str(value)
        if len(value) > self.max_length:
            raise ValueError(f"{self.name}: {self.max_length} belgidan uzun bo'lmasin")
        return super().validate(value)


class Text(Field):
    py_type = str
    sql_kind = "TEXT"

    def validate(self, value: Any) -> Any:
        return None if value is None else super().validate(str(value))


class Bool(Field):
    py_type = bool
    sql_kind = "BOOL"

    def validate(self, value: Any) -> Any:
        return None if value is None else bool(value)

    def to_db(self, value: Any, dialect: str) -> Any:
        if value is None or dialect in ("postgres", "mongo"):
            return value
        return int(bool(value))

    def from_db(self, value: Any, dialect: str) -> Any:
        return None if value is None else bool(value)


class DateTime(Field):
    """Timezone-aware datetimes (UTC stored). ``auto_now_add`` / ``auto_now``."""

    py_type = dt.datetime
    sql_kind = "DATETIME"

    def __init__(self, auto_now: bool = False, auto_now_add: bool = False, **kw: Any):
        if auto_now or auto_now_add:
            kw.setdefault("null", True)
        super().__init__(**kw)
        self.auto_now, self.auto_now_add = auto_now, auto_now_add

    @staticmethod
    def now() -> dt.datetime:
        return dt.datetime.now(dt.timezone.utc)

    def validate(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            value = dt.datetime.fromisoformat(value)
        if isinstance(value, (int, float)):
            value = dt.datetime.fromtimestamp(value, dt.timezone.utc)
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value

    def to_db(self, value: Any, dialect: str) -> Any:
        if value is None:
            return None
        value = self.validate(value).astimezone(dt.timezone.utc)
        if dialect == "sqlite":
            return value.isoformat()
        if dialect == "mysql":
            return value.replace(tzinfo=None)
        return value

    def from_db(self, value: Any, dialect: str) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            value = dt.datetime.fromisoformat(value)
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value


class Date(Field):
    py_type = dt.date
    sql_kind = "DATE"

    def validate(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return dt.date.fromisoformat(value)
        if isinstance(value, dt.datetime):
            return value.date()
        return value

    def to_db(self, value: Any, dialect: str) -> Any:
        if value is None:
            return None
        value = self.validate(value)
        if dialect in ("sqlite", "mongo"):
            return value.isoformat()
        return value

    def from_db(self, value: Any, dialect: str) -> Any:
        if value is None:
            return None
        if isinstance(value, dt.datetime):
            return value.date()
        if isinstance(value, str):
            return dt.date.fromisoformat(value)
        return value


class JSON(Field):
    """Any JSON value: dict, list, str, number."""

    py_type = (dict, list)
    sql_kind = "JSON"

    def to_db(self, value: Any, dialect: str) -> Any:
        if value is None or dialect == "mongo":
            return value
        return json.dumps(value, ensure_ascii=False)

    def from_db(self, value: Any, dialect: str) -> Any:
        if value is None or not isinstance(value, (str, bytes)):
            return value
        return json.loads(value)


class ForeignKey(BigInt):
    """Link to another model. Stored as ``<name>_id``.

    >>> class Order(Model):
    ...     user = fields.ForeignKey(User)
    >>> order.user_id          # int
    >>> await order.user       # User object (loaded once, then cached)
    """

    def __init__(self, to: Any, *, on_delete: str = "CASCADE", **kw: Any):
        kw.setdefault("index", True)
        super().__init__(**kw)
        self.to = to
        self.on_delete = on_delete.upper()
        self.attr = ""

    def bind(self, model: Any, name: str) -> None:
        self.attr = name
        self.column = f"{name}_id"
        super().bind(model, f"{name}_id")

    def target(self) -> Any:
        if isinstance(self.to, str):
            from .model import registry_by_name

            return registry_by_name(self.to)
        return self.to


__all__ = ["Field", "Int", "BigInt", "Float", "Str", "Text", "Bool", "DateTime", "Date", "JSON", "ForeignKey"]
