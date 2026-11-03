"""Built-in tables nicebot manages for you."""
from __future__ import annotations

from . import fields
from .model import Model


class User(Model):
    """Every Telegram user who talks to your bot (saved automatically as ``ctx.user``).

    Extend it with your own columns — the table stays the same::

        class User(nicebot.User):
            balance = fields.Int(default=0)
    """

    id = fields.BigInt(pk=True, generated=False)
    first_name = fields.Str(255, default="")
    last_name = fields.Str(255, null=True)
    username = fields.Str(64, null=True, index=True)
    lang = fields.Str(8, null=True)
    phone = fields.Str(32, null=True)
    is_blocked = fields.Bool(default=False)
    is_premium = fields.Bool(default=False)
    referrer_id = fields.BigInt(null=True, index=True)
    data = fields.JSON(default=dict)
    created_at = fields.DateTime(auto_now_add=True)
    last_seen = fields.DateTime(null=True)

    class Meta:
        table = "nb_users"

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p)

    @property
    def mention(self) -> str:
        from ..utils import mention

        return mention(self.full_name or str(self.id), self.id)

    async def referrals(self) -> list["User"]:
        return await type(self).filter(referrer_id=self.id)

    async def referrals_count(self) -> int:
        return await type(self).filter(referrer_id=self.id).count()


class KV(Model):
    key = fields.Str(255, pk=True, generated=False)
    value = fields.Text(default="null")
    expires_at = fields.Float(null=True, index=True)

    class Meta:
        table = "nb_kv"


class Stat(Model):
    day = fields.Str(10)
    name = fields.Str(128)
    count = fields.BigInt(default=0)

    class Meta:
        table = "nb_stats"
        unique_together = [("day", "name")]
