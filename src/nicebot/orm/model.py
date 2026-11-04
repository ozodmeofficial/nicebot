"""Model base class: declare a table with fields, query it with one API on any database."""
from __future__ import annotations

import re
from typing import Any, ClassVar, TypeVar

from ..errors import DoesNotExist, IntegrityError
from .fields import BigInt, DateTime, Field, ForeignKey
from .query import F, Q, QuerySet

M = TypeVar("M", bound="Model")

_REGISTRY: dict[str, type["Model"]] = {}  # table -> latest model class


def registry() -> dict[str, type["Model"]]:
    """All model classes by table name.

    Example::

        registry()["nb_users"]   # the User model
    """
    return _REGISTRY


def registry_by_name(name: str) -> type["Model"]:
    """Find a model class by class or table name (used by string ``ForeignKey("Product")``).

    Example::

        registry_by_name("Product")
    """
    for cls in _REGISTRY.values():
        if cls.__name__ == name:
            return cls
    for cls in _REGISTRY.values():  # e.g. "User" when it was extended by a subclass
        if any(b.__name__ == name for b in cls.__mro__):
            return cls
    raise LookupError(f"Model {name!r} not found (is its module imported?)")


def _table_name(cls_name: str) -> str:
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", cls_name).lower()
    if snake.endswith("y") and not snake.endswith(("ay", "ey", "oy", "uy")):
        return snake[:-1] + "ies"
    return snake if snake.endswith("s") else snake + "s"


class Meta:
    """Model metadata: table name, fields, indexes (``Product._meta``).

    Example::

        Product._meta.table          # "products"
        list(Product._meta.fields)   # ["id", "title", "price"]
    """
    def __init__(self, model: type, table: str, fields: dict[str, Field], indexes: list[tuple[str, ...]], unique_together: list[tuple[str, ...]], abstract: bool):
        self.model = model
        self.table = table
        self.fields = fields
        self.indexes = indexes
        self.unique_together = unique_together
        self.abstract = abstract
        self.database: Any = None
        self.synced = False
        pks = [f for f in fields.values() if f.pk]
        self.pk: Field = pks[0] if pks else None  # type: ignore[assignment]
        self.fk_attrs = {f.attr: f for f in fields.values() if isinstance(f, ForeignKey)}

    def field(self, name: str) -> Field:
        """A field by name.

        Example::

            Product._meta.field("price")
        """
        if name == "pk":
            return self.pk
        try:
            return self.fields[name]
        except KeyError:
            if name in self.fk_attrs:
                return self.fk_attrs[name]
            raise AttributeError(f"{self.model.__name__} has no field {name!r}. Fields: {', '.join(self.fields)}") from None

    def backend(self) -> Any:
        """The database backend this model uses.

        Example::

            Product._meta.backend
        """
        from .db import current_database

        db = self.database or current_database()
        return db.backend


class _FK:
    """Descriptor: ``order.user`` → awaitable that loads the related object (cached)."""

    def __init__(self, field: ForeignKey):
        self.field = field

    def __get__(self, obj: Any, owner: Any = None) -> Any:
        if obj is None:
            return self.field
        return _Related(obj, self.field)

    def __set__(self, obj: Any, value: Any) -> None:
        if value is None or isinstance(value, (int, str)):
            obj.__dict__[self.field.name] = value
            obj.__dict__.pop(f"_cache_{self.field.attr}", None)
        else:
            obj.__dict__[self.field.name] = value._pk_value
            obj.__dict__[f"_cache_{self.field.attr}"] = value


class _Related:
    __slots__ = ("obj", "field")

    def __init__(self, obj: Any, field: ForeignKey):
        self.obj, self.field = obj, field

    async def _load(self) -> Any:
        key = f"_cache_{self.field.attr}"
        if key in self.obj.__dict__:
            return self.obj.__dict__[key]
        fk = self.obj.__dict__.get(self.field.name)
        if fk is None:
            return None
        target = self.field.target()
        value = await target.get_or_none(**{target._meta.pk.name: fk})
        self.obj.__dict__[key] = value
        return value

    def __await__(self):  # type: ignore[no-untyped-def]
        return self._load().__await__()


class ModelMeta(type):
    """Metaclass that collects fields and registers models. Internal.

    Example::

        class Product(Model): ...    # ModelMeta builds Product._meta
    """
    def __new__(mcs, name: str, bases: tuple, ns: dict[str, Any]) -> Any:
        meta_cls = ns.pop("Meta", None)
        own_fields = {k: v for k, v in list(ns.items()) if isinstance(v, Field)}
        for k in own_fields:
            ns.pop(k)
        cls = super().__new__(mcs, name, bases, ns)
        if not bases:  # the Model base class itself
            return cls

        parent_meta: Meta | None = None
        for b in cls.__mro__[1:]:
            pm = b.__dict__.get("_meta")
            if isinstance(pm, Meta):
                parent_meta = pm
                break

        fields: dict[str, Field] = {}
        if parent_meta:
            import copy

            for fname, f in parent_meta.fields.items():
                nf = copy.copy(f)
                fields[fname] = nf
        abstract = bool(getattr(meta_cls, "abstract", False))
        for attr, f in own_fields.items():
            f.bind(cls, attr)
            fields[f.name] = f
        for f in fields.values():
            f.model = cls
        if not any(f.pk for f in fields.values()):
            pk = BigInt(pk=True, generated=True)
            pk.bind(cls, "id")
            fields = {"id": pk, **fields}
        for f in fields.values():
            if f.pk and f.generated is None:
                f.generated = isinstance(f, BigInt) or type(f).__name__ == "Int"

        if meta_cls is not None and getattr(meta_cls, "table", None):
            table = meta_cls.table
        elif parent_meta and not parent_meta.abstract:
            table = parent_meta.table  # extending a concrete model keeps its table
        else:
            table = _table_name(name)

        indexes = [tuple(i) if isinstance(i, (list, tuple)) else (i,) for i in getattr(meta_cls, "indexes", [])]
        unique_together = [tuple(u) for u in getattr(meta_cls, "unique_together", [])]
        if parent_meta:
            indexes = parent_meta.indexes + indexes
            unique_together = parent_meta.unique_together + unique_together
        cls._meta = Meta(cls, table, fields, indexes, unique_together, abstract)
        for f in fields.values():
            if isinstance(f, ForeignKey):
                setattr(cls, f.attr, _FK(f))
        if not abstract:
            _REGISTRY[table] = cls
        return cls


class Model(metaclass=ModelMeta):
    """Base class of your tables.

    >>> class Product(Model):
    ...     title = fields.Str()
    ...     price = fields.Int(default=0)
    >>> p = await Product.create(title="Kitob", price=50_000)
    >>> cheap = await Product.filter(price__lt=100_000).order_by("price")
    
    Example::

        class Product(Model):
            title = fields.Str(100)
            price = fields.Int(default=0)
            active = fields.Bool(default=True)

        p = await Product.create(title="Book", price=50_000)
        cheap = await Product.filter(price__lt=100_000).order_by("price")
        await p.update(price=45_000)
    """

    _meta: ClassVar[Meta]

    def __init__(self, **values: Any):
        meta = self._meta
        self.__dict__["_persisted"] = False
        for name, f in meta.fields.items():
            if name in values:
                continue
            self.__dict__[name] = f.get_default()
        for k, v in values.items():
            if k in meta.fk_attrs:
                setattr(self, k, v)
            elif k in meta.fields:
                self.__dict__[k] = meta.fields[k].validate(v)
            else:
                raise AttributeError(f"{type(self).__name__} has no field {k!r}")

    # ------------------------------------------------------------ helpers
    @property
    def _pk_value(self) -> Any:
        return self.__dict__.get(self._meta.pk.name)

    @property
    def pk(self) -> Any:
        """The primary key value (usually ``id``).

        Example::

            order.pk   # 15
        """
        return self._pk_value

    def __setattr__(self, key: str, value: Any) -> None:
        meta = self._meta
        if key in meta.fields:
            value = meta.fields[key].validate(value)
        object.__setattr__(self, key, value)

    @classmethod
    def _from_db(cls: type[M], row: dict[str, Any]) -> M:
        obj = cls.__new__(cls)
        d = obj.__dict__
        dialect = cls._meta.backend().dialect
        for name, f in cls._meta.fields.items():
            v = f.from_db(row.get(f.column), dialect)
            if v is None and not f.null and f.has_default():
                v = f.get_default()
            d[name] = v
        d["_persisted"] = True
        return obj

    def to_dict(self, *exclude: str) -> dict[str, Any]:
        """The row as a dict (pass field names to leave out).

        Example::

            return {"user": ctx.user.to_dict("data")}
        """
        return {k: self.__dict__.get(k) for k in self._meta.fields if k not in exclude}

    def __repr__(self) -> str:
        pk = self._meta.pk.name
        label = next((self.__dict__.get(k) for k in ("title", "name", "username", "first_name") if self.__dict__.get(k)), None)
        return f"<{type(self).__name__} {pk}={self._pk_value}{' ' + repr(label) if label else ''}>"

    def __eq__(self, other: Any) -> bool:
        return type(other) is type(self) and other._pk_value is not None and other._pk_value == self._pk_value

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._pk_value))

    @classmethod
    def _normalize_lookups(cls, lookups: dict[str, Any]) -> dict[str, Any]:
        out = {}
        meta = cls._meta
        for key, value in lookups.items():
            field, sep, rest = key.partition("__")
            if field == "pk":
                field = meta.pk.name
            elif field in meta.fk_attrs:
                field = meta.fk_attrs[field].name
                if isinstance(value, Model):
                    value = value._pk_value
            meta.field(field)  # raises with a helpful message
            if isinstance(value, Model):
                value = value._pk_value
            out[field + (sep + rest if sep else "")] = value
        return out

    @classmethod
    def _prepare_update(cls, values: dict[str, Any]) -> dict[Field, Any]:
        meta = cls._meta
        data: dict[Field, Any] = {}
        for k, v in values.items():
            if k in meta.fk_attrs:
                f = meta.fk_attrs[k]
                v = v._pk_value if isinstance(v, Model) else v
            else:
                f = meta.field(k)
            data[f] = v if isinstance(v, F) else f.validate(v)
        for f in meta.fields.values():
            if isinstance(f, DateTime) and f.auto_now and f not in data:
                data[f] = DateTime.now()
        return data

    # ------------------------------------------------------------ queries
    @classmethod
    def objects(cls: type[M]) -> QuerySet[M]:
        """A ``QuerySet`` of every row (same as ``Model.all()``).

        Example::

            async for p in Product.objects():
                print(p.title)
        """
        return QuerySet(cls)

    @classmethod
    def all(cls: type[M]) -> QuerySet[M]:
        """Every row as a lazy ``QuerySet``.

        Example::

            products = await Product.all().order_by("title")
        """
        return QuerySet(cls)

    @classmethod
    def filter(cls: type[M], *qs: Q, **lookups: Any) -> QuerySet[M]:
        """Rows matching lookups (``price__lt=100``) or ``Q`` objects.

        Example::

            cheap = await Product.filter(price__lt=100_000, active=True)
        """
        return QuerySet(cls).filter(*qs, **lookups)

    @classmethod
    def exclude(cls: type[M], *qs: Q, **lookups: Any) -> QuerySet[M]:
        """Rows NOT matching the lookups.

        Example::

            others = await Product.exclude(category="books")
        """
        return QuerySet(cls).exclude(*qs, **lookups)

    @classmethod
    async def get(cls: type[M], *qs: Q, **lookups: Any) -> M:
        """Exactly one row; raises ``DoesNotExist`` / ``MultipleObjectsReturned``.

        Example::

            p = await Product.get(id=5)
        """
        return await QuerySet(cls).get(*qs, **lookups)

    @classmethod
    async def get_or_none(cls: type[M], *qs: Q, **lookups: Any) -> M | None:
        """One row or ``None``.

        Example::

            p = await Product.get_or_none(slug="book")
        """
        return await QuerySet(cls).get_or_none(*qs, **lookups)

    @classmethod
    async def count(cls, *qs: Q, **lookups: Any) -> int:
        """Number of matching rows.

        Example::

            n = await Order.count(status="new")
        """
        return await QuerySet(cls).filter(*qs, **lookups).count()

    @classmethod
    async def exists(cls, *qs: Q, **lookups: Any) -> bool:
        """Is there at least one matching row?

        Example::

            if await Order.exists(user_id=ctx.user_id): ...
        """
        return await QuerySet(cls).filter(*qs, **lookups).exists()

    @classmethod
    async def create(cls: type[M], **values: Any) -> M:
        """Insert a row and return it.

        Example::

            order = await Order.create(user_id=ctx.user_id, product="Book", price=50_000)
        """
        obj = cls(**values)
        await obj.save(force_insert=True)
        return obj

    @classmethod
    async def get_or_create(cls: type[M], defaults: dict[str, Any] | None = None, **lookups: Any) -> tuple[M, bool]:
        """Get a row or create it with ``defaults``. Returns ``(obj, created)``.

        Example::

            city, created = await City.get_or_create(name="Tashkent", defaults={"population": 3_000_000})
        """
        obj = await cls.get_or_none(**lookups)
        if obj is not None:
            return obj, False
        try:
            return await cls.create(**{**lookups, **(defaults or {})}), True
        except IntegrityError:
            obj = await cls.get_or_none(**lookups)
            if obj is None:
                raise
            return obj, False

    @classmethod
    async def update_or_create(cls: type[M], defaults: dict[str, Any] | None = None, **lookups: Any) -> tuple[M, bool]:
        """Update a row with ``defaults`` or create it. Returns ``(obj, created)``.

        Example::

            s, _ = await Setting.update_or_create(key="theme", defaults={"value": "dark"})
        """
        obj = await cls.get_or_none(**lookups)
        if obj is None:
            return await cls.create(**{**lookups, **(defaults or {})}), True
        if defaults:
            await obj.update(**defaults)
        return obj, False

    @classmethod
    async def bulk_create(cls: type[M], objects: list[M] | list[dict[str, Any]]) -> list[M]:
        """Insert many rows at once (objects or dicts).

        Example::

            await Product.bulk_create([{"title": "A", "price": 1}, {"title": "B", "price": 2}])
        """
        objs = [o if isinstance(o, Model) else cls(**o) for o in objects]
        if not objs:
            return []
        for o in objs:
            o._apply_auto_times(insert=True)
        rows = [o._db_row(insert=True) for o in objs]
        ids = await cls._meta.backend().bulk_insert(cls, rows)
        for o, pk in zip(objs, ids):
            if pk is not None and o._pk_value is None:
                o.__dict__[cls._meta.pk.name] = pk
            o.__dict__["_persisted"] = True
        return objs

    # ------------------------------------------------------------ instance
    def _apply_auto_times(self, insert: bool) -> None:
        now = None
        for name, f in self._meta.fields.items():
            if isinstance(f, DateTime) and (f.auto_now or (insert and f.auto_now_add and self.__dict__.get(name) is None)):
                now = now or DateTime.now()
                self.__dict__[name] = now

    def _db_row(self, insert: bool) -> dict[str, Any]:
        row = {}
        dialect = self._meta.backend().dialect
        for name, f in self._meta.fields.items():
            value = self.__dict__.get(name)
            if insert and f.pk and f.generated and value is None:
                continue
            if value is None and not f.null and not f.pk:
                if f.has_default():
                    value = f.get_default()
                    self.__dict__[name] = value
                else:
                    raise IntegrityError(f"{type(self).__name__}.{name} cannot be empty (null=False)")
            row[f.column] = f.to_db(value, dialect)
        return row

    async def save(self, force_insert: bool = False) -> "Model":
        """Insert or update the whole row.

        Example::

            p.price = 60_000
            await p.save()
        """
        backend = self._meta.backend()
        meta = self._meta
        insert = force_insert or not self.__dict__.get("_persisted")
        self._apply_auto_times(insert)
        if insert:
            pk = await backend.insert(type(self), self._db_row(insert=True))
            if self._pk_value is None:
                self.__dict__[meta.pk.name] = pk
            self.__dict__["_persisted"] = True
        else:
            data = {f: self.__dict__.get(n) for n, f in meta.fields.items() if not f.pk}
            await backend.update(type(self), Q(**{meta.pk.name: self._pk_value}), data)
        return self

    async def update(self, **values: Any) -> "Model":
        """Change some fields and save only them (``F`` expressions allowed).

        Example::

            await ctx.user.update(phone=phone, data={**ctx.user.data, "city": "Tashkent"})
        """
        meta = self._meta
        data = type(self)._prepare_update(values)
        await meta.backend().update(type(self), Q(**{meta.pk.name: self._pk_value}), data)
        if any(isinstance(v, F) for v in data.values()):
            await self.refresh()
        else:
            for f, v in data.items():
                self.__dict__[f.name] = v
        return self

    async def increment(self, field: str, amount: int | float = 1) -> "Model":
        """Add ``amount`` to a numeric field atomically.

        Example::

            await ctx.user.increment("balance", 1000)
        """
        return await self.update(**{field: F(field) + amount})

    async def delete(self) -> None:
        """Delete the row.

        Example::

            await order.delete()
        """
        meta = self._meta
        await meta.backend().delete(type(self), Q(**{meta.pk.name: self._pk_value}))
        self.__dict__["_persisted"] = False

    async def refresh(self) -> "Model":
        """Reload the row from the database.

        Example::

            await order.refresh()
        """
        meta = self._meta
        fresh = await type(self).get_or_none(**{meta.pk.name: self._pk_value})
        if fresh is None:
            raise DoesNotExist(f"{type(self).__name__} was deleted")
        for n in meta.fields:
            self.__dict__[n] = fresh.__dict__[n]
        return self
