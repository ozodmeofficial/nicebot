"""Q / F expressions and the lazy, chainable QuerySet."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator, Generic, Iterable, TypeVar

from ..errors import DoesNotExist, MultipleObjectsReturned

if TYPE_CHECKING:
    from .model import Model

M = TypeVar("M", bound="Model")

LOOKUPS = {
    "exact", "ne", "not", "gt", "gte", "lt", "lte", "in", "not_in",
    "contains", "icontains", "startswith", "istartswith", "endswith", "iendswith", "isnull", "between",
}


class Q:
    """A combinable filter: ``&`` (and), ``|`` (or), ``~`` (not).

    Example::

        adults_or_admins = await User.filter(Q(age__gte=18) | Q(is_admin=True))
        not_tashkent = await Customer.filter(~Q(city="Tashkent"))
    """

    __slots__ = ("op", "children", "negated")

    def __init__(self, *children: Any, _op: str = "AND", _negated: bool = False, **lookups: Any):
        self.op = _op
        self.negated = _negated
        self.children: list[Any] = list(children)
        for key, value in lookups.items():
            field, _, lookup = key.partition("__")
            lookup = lookup or "exact"
            if lookup not in LOOKUPS:
                raise ValueError(f"Unknown lookup __{lookup} (available: {', '.join(sorted(LOOKUPS))})")
            if lookup == "not":
                lookup = "ne"
            self.children.append((field, lookup, value))

    def _combine(self, other: "Q", op: str) -> "Q":
        return Q(self, other, _op=op)

    def __and__(self, other: "Q") -> "Q":
        return self._combine(other, "AND")

    def __or__(self, other: "Q") -> "Q":
        return self._combine(other, "OR")

    def __invert__(self) -> "Q":
        return Q(*self.children, _op=self.op, _negated=not self.negated)

    def __bool__(self) -> bool:
        return bool(self.children)

    def __repr__(self) -> str:
        return f"Q({'NOT ' if self.negated else ''}{self.op} {self.children})"


class F:
    """Refer to a column's current value inside ``update()`` (atomic arithmetic).

    Example::

        await User.filter(id=ctx.user_id).update(balance=F("balance") + 100)
    """

    __slots__ = ("field", "ops")

    def __init__(self, field: str, ops: tuple = ()):
        self.field, self.ops = field, ops

    def __add__(self, v: Any) -> "F":
        return F(self.field, self.ops + (("+", v),))

    def __sub__(self, v: Any) -> "F":
        return F(self.field, self.ops + (("-", v),))

    def __mul__(self, v: Any) -> "F":
        return F(self.field, self.ops + (("*", v),))

    def __repr__(self) -> str:
        return f"F({self.field}{''.join(f' {o} {v}' for o, v in self.ops)})"


class QuerySet(Generic[M]):
    """Lazy query. Nothing hits the database until you ``await`` it.

    >>> users = await User.filter(lang="uz").order_by("-created_at").limit(10)
    >>> n = await User.filter(is_blocked=False).count()
    
    Example::

        qs = Product.filter(active=True).order_by("-price").limit(10)   # nothing runs yet
        products = await qs                                           # one query
        async for p in Product.filter(stock__gt=0):
            print(p.title)
    """

    def __init__(self, model: type[M]):
        self.model = model
        self.where = Q()
        self.ordering: list[str] = []
        self._limit: int | None = None
        self._offset: int | None = None
        self._values: tuple[str, ...] | None = None
        self._flat = False

    def _clone(self) -> "QuerySet[M]":
        qs = QuerySet(self.model)
        qs.where, qs.ordering = self.where, list(self.ordering)
        qs._limit, qs._offset, qs._values, qs._flat = self._limit, self._offset, self._values, self._flat
        return qs

    @property
    def backend(self) -> Any:
        """The database backend of the model.

        Example::

            qs.backend
        """
        return self.model._meta.backend()

    # ---------------------------------------------------------------- building
    def filter(self, *qs: Q, **lookups: Any) -> "QuerySet[M]":
        """Narrow the query (lookups or ``Q``).

        Example::

            qs = Product.all().filter(active=True).filter(price__gte=10_000)
        """
        new = self._clone()
        cond = Q(*qs, **self.model._normalize_lookups(lookups))
        new.where = cond if not self.where else (self.where & cond)
        return new

    def exclude(self, *qs: Q, **lookups: Any) -> "QuerySet[M]":
        """Remove rows matching the lookups.

        Example::

            qs = Product.all().exclude(stock=0)
        """
        new = self._clone()
        cond = ~Q(*qs, **self.model._normalize_lookups(lookups))
        new.where = cond if not self.where else (self.where & cond)
        return new

    def order_by(self, *fields: str) -> "QuerySet[M]":
        """Sort by fields; ``"-field"`` means descending.

        Example::

            newest = await Order.all().order_by("-created_at")
        """
        new = self._clone()
        for f in fields:
            name = f.lstrip("-")
            self.model._meta.field(name)
        new.ordering = list(fields)
        return new

    def limit(self, n: int) -> "QuerySet[M]":
        """At most ``n`` rows.

        Example::

            top = await Product.all().order_by("-sold").limit(5)
        """
        new = self._clone()
        new._limit = int(n)
        return new

    def offset(self, n: int) -> "QuerySet[M]":
        """Skip ``n`` rows.

        Example::

            rest = await Product.all().offset(10)
        """
        new = self._clone()
        new._offset = int(n)
        return new

    def page(self, number: int, size: int = 10) -> "QuerySet[M]":
        """Page ``number`` (from 1) of ``size`` rows.

        Example::

            second = await Product.all().page(2, 10)   # rows 11..20
        """
        return self.offset((max(number, 1) - 1) * size).limit(size)

    def values(self, *fields: str) -> "QuerySet[M]":
        """Return dicts with only these fields.

        Example::

            rows = await Product.all().values("id", "title")
        """
        new = self._clone()
        new._values = fields or tuple(self.model._meta.fields)
        return new

    def values_list(self, field: str, flat: bool = True) -> "QuerySet[M]":
        """Return one field's values (``flat=True``) or tuples.

        Example::

            ids = await User.filter(is_blocked=False).values_list("id")
        """
        new = self.values(field)
        new._flat = flat
        return new

    # ---------------------------------------------------------------- executing
    async def _fetch(self) -> list[Any]:
        rows = await self.backend.select(self.model, self)
        if self._values is not None:
            meta = self.model._meta
            out = [{k: meta.field(k).from_db(r.get(meta.field(k).column), self.backend.dialect) for k in self._values} for r in rows]
            if self._flat:
                return [o[self._values[0]] for o in out]
            return out
        return [self.model._from_db(r) for r in rows]

    def __await__(self):  # type: ignore[no-untyped-def]
        return self._fetch().__await__()

    async def __aiter__(self) -> AsyncIterator[M]:
        for obj in await self._fetch():
            yield obj

    async def all(self) -> list[M]:
        """Run the query and return a list (same as ``await qs``).

        Example::

            items = await Product.filter(active=True).all()
        """
        return await self._fetch()

    async def first(self) -> M | None:
        """The first row or ``None``.

        Example::

            latest = await Order.all().order_by("-id").first()
        """
        items = await self.limit(1)._fetch()
        return items[0] if items else None

    async def last(self) -> M | None:
        """The last row or ``None``.

        Example::

            oldest = await Order.all().order_by("-id").last()
        """
        order = self.ordering or [self.model._meta.pk.name]
        reverse = [o[1:] if o.startswith("-") else f"-{o}" for o in order]
        return await self.order_by(*reverse).first()

    async def get(self, *qs: Q, **lookups: Any) -> M:
        """Exactly one row of this query.

        Example::

            o = await Order.filter(user_id=1).get(id=5)
        """
        items = await self.filter(*qs, **lookups).limit(2)._fetch()
        if not items:
            raise DoesNotExist(f"{self.model.__name__} not found: {lookups}")
        if len(items) > 1:
            raise MultipleObjectsReturned(f"{self.model.__name__}: more than one row matches {lookups}")
        return items[0]

    async def get_or_none(self, *qs: Q, **lookups: Any) -> M | None:
        """One row or ``None``.

        Example::

            o = await Order.filter(user_id=1).get_or_none(status="new")
        """
        items = await self.filter(*qs, **lookups).limit(1)._fetch()
        return items[0] if items else None

    async def count(self) -> int:
        """Number of rows.

        Example::

            n = await Order.filter(status="new").count()
        """
        return await self.backend.count(self.model, self.where)

    async def exists(self) -> bool:
        """Is there any row?

        Example::

            if await Order.filter(user_id=ctx.user_id).exists(): ...
        """
        return bool(await self.limit(1).values(self.model._meta.pk.name)._fetch())

    async def update(self, **values: Any) -> int:
        """Update every matching row; returns how many changed.

        Example::

            await Order.filter(status="new").update(status="seen")
        """
        data = self.model._prepare_update(values)
        return await self.backend.update(self.model, self.where, data)

    async def increment(self, field: str, amount: int | float = 1) -> int:
        """Add ``amount`` to a field in every matching row.

        Example::

            await Product.filter(id=5).increment("views")
        """
        return await self.update(**{field: F(field) + amount})

    async def delete(self) -> int:
        """Delete every matching row; returns how many.

        Example::

            await Order.filter(status="cancelled").delete()
        """
        return await self.backend.delete(self.model, self.where)

    async def _agg(self, func: str, field: str) -> Any:
        return await self.backend.aggregate(self.model, self.where, func, self.model._meta.field(field))

    async def sum(self, field: str) -> float | int:
        """Sum of a field.

        Example::

            total = await Order.filter(user_id=ctx.user_id).sum("price")
        """
        return (await self._agg("SUM", field)) or 0

    async def avg(self, field: str) -> float | None:
        """Average of a field (``None`` if no rows).

        Example::

            avg = await Review.filter(product_id=5).avg("stars")
        """
        v = await self._agg("AVG", field)
        return None if v is None else float(v)

    async def max(self, field: str) -> Any:
        """Largest value of a field.

        Example::

            await Order.all().max("price")
        """
        return await self._agg("MAX", field)

    async def min(self, field: str) -> Any:
        """Smallest value of a field.

        Example::

            await Order.all().min("price")
        """
        return await self._agg("MIN", field)

    def __repr__(self) -> str:
        return f"<QuerySet {self.model.__name__} where={self.where!r} order={self.ordering}>"


def iter_leaves(q: Q) -> Iterable[tuple[str, str, Any]]:
    """Walk a ``Q`` tree and yield ``(field, lookup, value)`` (used by backends).

    Example::

        list(iter_leaves(Q(price__lt=5)))   # [("price", "lt", 5)]
    """
    for c in q.children:
        if isinstance(c, Q):
            yield from iter_leaves(c)
        else:
            yield c
