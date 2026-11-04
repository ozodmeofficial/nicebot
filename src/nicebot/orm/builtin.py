"""Built-in tables: ``User`` (every user of the bot), ``KV`` (storage) and ``Stat`` (statistics).

Example::

    from nicebot import User, fields

    class Customer(User):                 # add your own columns to the users table
        city = fields.Str(50, null=True)

    bot = Nicebot(token="...", user_model=Customer)
"""
from __future__ import annotations

from . import fields
from .model import Model


class User(Model):
    """Every Telegram user who talks to your bot (saved automatically as ``ctx.user``).

    Extend it with your own columns — the table stays the same::

        class User(nicebot.User):
            balance = fields.Int(default=0)
    
    Example::

        @bot.command("me")
        async def me(ctx: Context):
            u = ctx.user
            await ctx.reply(f"{u.full_name}, with us since {u.created_at:%d.%m.%Y}, language {u.lang}")

        blocked = await User.filter(is_blocked=True).count()
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
        """Table settings (``nb_users``)."""
        table = "nb_users"

    @property
    def full_name(self) -> str:
        """First and last name together.

        Example::

            ctx.user.full_name   # "Ali Valiyev"
        """
        return " ".join(p for p in (self.first_name, self.last_name) if p)

    @property
    def mention(self) -> str:
        """A clickable HTML mention of the user.

        Example::

            await ctx.reply(f"Hi {ctx.user.mention}")
        """
        from ..utils import mention

        return mention(self.full_name or str(self.id), self.id)

    async def referrals(self) -> list["User"]:
        """Users who joined through this user's referral link.

        Example::

            friends = await ctx.user.referrals()
        """
        return await type(self).filter(referrer_id=self.id)

    async def referrals_count(self) -> int:
        """How many users joined through this user's link.

        Example::

            await ctx.reply(f"You invited {await ctx.user.referrals_count()} friends")
        """
        return await type(self).filter(referrer_id=self.id).count()


class KV(Model):
    """Key–value rows used by ``DBStorage`` (table ``nb_kv``). Internal.

    Example::

        await KV.filter(key__startswith="st:").delete()
    """
    key = fields.Str(255, pk=True, generated=False)
    value = fields.Text(default="null")
    expires_at = fields.Float(null=True, index=True)

    class Meta:
        """Table settings (``nb_kv``)."""
        table = "nb_kv"


class Stat(Model):
    """Daily usage counters behind ``bot.stats()`` (table ``nb_stats``). Internal.

    Example::

        rows = await Stat.filter(day="2026-11-04")
    """
    day = fields.Str(10)
    name = fields.Str(128)
    count = fields.BigInt(default=0)

    class Meta:
        """Table settings (``nb_stats``)."""
        table = "nb_stats"
        unique_together = [("day", "name")]
