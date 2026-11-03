"""MongoDB backend (motor). Same Model API as SQL; integer auto-increment ids via a counters collection."""
from __future__ import annotations

import contextlib
import re
from typing import Any, AsyncIterator

from ..errors import IntegrityError
from .fields import Field, Float, Int
from .query import F, Q


class MongoBackend:
    dialect = "mongo"

    def __init__(self, url: str, client: Any = None, **options: Any):
        self.url = url
        self.options = options
        self.client = client
        self.db: Any = None

    async def connect(self) -> None:
        if self.client is None:
            try:
                from motor.motor_asyncio import AsyncIOMotorClient
            except ImportError as e:  # pragma: no cover
                raise ImportError("MongoDB uchun: pip install 'nicebot[mongo]'") from e
            self.client = AsyncIOMotorClient(self.url, tz_aware=True)
        from urllib.parse import urlparse

        name = (urlparse(self.url).path or "/").lstrip("/").split("?")[0] or self.options.get("database", "nicebot")
        self.db = self.client[name]

    async def close(self) -> None:
        if self.client is not None:
            self.client.close()

    def _col(self, model: Any) -> Any:
        return self.db[model._meta.table]

    @staticmethod
    def _key(f: Field) -> str:
        return "_id" if f.pk else f.column

    # ------------------------------------------------------------- schema
    async def sync_schema(self, model: Any) -> None:
        meta = model._meta
        col = self._col(model)
        for f in meta.fields.values():
            if f.pk:
                continue
            if f.unique:
                await col.create_index(f.column, unique=True, sparse=f.null)
            elif f.index:
                await col.create_index(f.column)
        for cols in meta.indexes:
            await col.create_index([(meta.field(c).column, 1) for c in cols])
        for cols in meta.unique_together:
            await col.create_index([(meta.field(c).column, 1) for c in cols], unique=True)

    async def _next_ids(self, table: str, n: int = 1) -> int:
        from pymongo import ReturnDocument

        doc = await self.db["nb_counters"].find_one_and_update(
            {"_id": table}, {"$inc": {"seq": n}}, upsert=True, return_document=ReturnDocument.AFTER
        )
        return int(doc["seq"])

    # ------------------------------------------------------------- compiler
    def compile_q(self, q: Q, model: Any) -> dict[str, Any]:
        parts = []
        for child in q.children:
            if isinstance(child, Q):
                if child.children:
                    parts.append(self.compile_q(child, model))
            else:
                parts.append(self.compile_leaf(child, model))
        if not parts:
            expr: dict[str, Any] = {}
        elif len(parts) == 1:
            expr = parts[0]
        else:
            expr = {"$and" if q.op == "AND" else "$or": parts}
        if q.negated:
            return {"$nor": [expr]} if expr else {"_id": {"$exists": False}}
        return expr

    def compile_leaf(self, leaf: tuple[str, str, Any], model: Any) -> dict[str, Any]:
        name, op, value = leaf
        f = model._meta.field(name)
        k = self._key(f)
        conv = lambda v: f.to_db(v, "mongo")  # noqa: E731
        if op == "exact":
            return {k: conv(value)}
        if op == "ne":
            return {k: {"$ne": conv(value)}}
        if op in ("gt", "gte", "lt", "lte"):
            return {k: {f"${op}": conv(value)}}
        if op == "in":
            return {k: {"$in": [conv(v) for v in value]}}
        if op == "not_in":
            return {k: {"$nin": [conv(v) for v in value]}}
        if op == "isnull":
            return {k: None} if value else {k: {"$ne": None}}
        if op == "between":
            lo, hi = value
            return {k: {"$gte": conv(lo), "$lte": conv(hi)}}
        esc = re.escape(str(value))
        ci = op.startswith("i")
        base = op[1:] if ci else op
        pattern = {"contains": esc, "startswith": f"^{esc}", "endswith": f"{esc}$"}[base]
        out: dict[str, Any] = {"$regex": pattern}
        if ci:
            out["$options"] = "i"
        return {k: out}

    def _doc_to_row(self, model: Any, doc: dict[str, Any]) -> dict[str, Any]:
        pk = model._meta.pk
        row = dict(doc)
        row[pk.column] = row.pop("_id", None)
        return row

    def _row_to_doc(self, model: Any, row: dict[str, Any]) -> dict[str, Any]:
        pk = model._meta.pk
        doc = dict(row)
        if pk.column in doc:
            doc["_id"] = doc.pop(pk.column)
        return doc

    # ------------------------------------------------------------- operations
    async def insert(self, model: Any, row: dict[str, Any]) -> Any:
        from pymongo.errors import DuplicateKeyError

        meta = model._meta
        doc = self._row_to_doc(model, row)
        if "_id" not in doc or doc["_id"] is None:
            if meta.pk.generated:
                doc["_id"] = await self._next_ids(meta.table)
        try:
            await self._col(model).insert_one(doc)
        except DuplicateKeyError as e:
            raise IntegrityError(str(e)) from e
        return doc["_id"]

    async def bulk_insert(self, model: Any, rows: list[dict[str, Any]]) -> list[Any]:
        from pymongo.errors import BulkWriteError

        meta = model._meta
        docs = [self._row_to_doc(model, r) for r in rows]
        need = [d for d in docs if d.get("_id") is None]
        if need and meta.pk.generated:
            last = await self._next_ids(meta.table, len(need))
            for i, d in enumerate(need):
                d["_id"] = last - len(need) + 1 + i
        try:
            await self._col(model).insert_many(docs)
        except BulkWriteError as e:
            raise IntegrityError(str(e)) from e
        return [d["_id"] for d in docs]

    async def select(self, model: Any, qs: Any) -> list[dict[str, Any]]:
        meta = model._meta
        projection = None
        if qs._values is not None:
            projection = {self._key(meta.field(v)): 1 for v in qs._values}
        cursor = self._col(model).find(self.compile_q(qs.where, model), projection)
        if qs.ordering:
            cursor = cursor.sort([(self._key(meta.field(o.lstrip("-"))), -1 if o.startswith("-") else 1) for o in qs.ordering])
        if qs._offset:
            cursor = cursor.skip(qs._offset)
        if qs._limit is not None:
            cursor = cursor.limit(qs._limit)
        return [self._doc_to_row(model, d) async for d in cursor]

    async def count(self, model: Any, where: Q) -> int:
        return int(await self._col(model).count_documents(self.compile_q(where, model)))

    async def aggregate(self, model: Any, where: Q, func: str, f: Field) -> Any:
        op = {"SUM": "$sum", "AVG": "$avg", "MAX": "$max", "MIN": "$min"}[func]
        pipeline = [{"$match": self.compile_q(where, model)}, {"$group": {"_id": None, "v": {op: f"${self._key(f)}"}}}]
        docs = [d async for d in self._col(model).aggregate(pipeline)]
        if not docs or docs[0].get("v") is None:
            return None
        v = docs[0]["v"]
        if func in ("MAX", "MIN"):
            return f.from_db(v, "mongo")
        if func == "SUM" and isinstance(f, Int) and not isinstance(f, Float):
            return int(v)
        return float(v)

    async def update(self, model: Any, where: Q, data: dict[Field, Any]) -> int:
        if not data:
            return 0
        sets: dict[str, Any] = {}
        incs: dict[str, Any] = {}
        muls: dict[str, Any] = {}
        for f, v in data.items():
            k = self._key(f)
            if isinstance(v, F):
                if v.field != f.name or len(v.ops) != 1:
                    raise NotImplementedError("MongoDB: F() faqat shu maydonning o'zi bilan bitta + - * amalda ishlaydi")
                op, operand = v.ops[0]
                if op == "+":
                    incs[k] = operand
                elif op == "-":
                    incs[k] = -operand
                else:
                    muls[k] = operand
            else:
                sets[k] = f.to_db(v, "mongo")
        upd: dict[str, Any] = {}
        if sets:
            upd["$set"] = sets
        if incs:
            upd["$inc"] = incs
        if muls:
            upd["$mul"] = muls
        res = await self._col(model).update_many(self.compile_q(where, model), upd)
        return int(res.matched_count)

    async def delete(self, model: Any, where: Q) -> int:
        res = await self._col(model).delete_many(self.compile_q(where, model))
        return int(res.deleted_count)

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        """MongoDB transactions need a replica set; here this is a no-op context."""
        yield
