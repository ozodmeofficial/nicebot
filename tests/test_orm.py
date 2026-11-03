import datetime as dt

import pytest

from nicebot.errors import DoesNotExist, IntegrityError
from nicebot.orm import F, Model, Q, fields


class Shop(Model):
    title = fields.Str(100, unique=True)
    rating = fields.Float(default=0.0)


class Product(Model):
    title = fields.Str(120)
    price = fields.Int(default=0)
    active = fields.Bool(default=True)
    tags = fields.JSON(default=list)
    shop = fields.ForeignKey(Shop, null=True)
    released = fields.Date(null=True)
    created = fields.DateTime(auto_now_add=True)

    class Meta:
        indexes = [("price", "active")]


async def setup(db):
    await db.migrate([Shop, Product])
    shop = await Shop.create(title="Navoiy Market", rating=4.5)
    await Product.bulk_create([
        {"title": "Kitob", "price": 50_000, "tags": ["edu"], "shop": shop},
        {"title": "Daftar", "price": 5_000, "tags": [], "shop": shop},
        {"title": "Ruchka", "price": 2_000, "active": False},
        {"title": "Kompyuter", "price": 9_000_000, "released": dt.date(2026, 1, 5)},
    ])
    return shop


async def test_crud_and_filters(db):
    shop = await setup(db)
    assert await Product.count() == 4
    cheap = await Product.filter(price__lt=10_000).order_by("price")
    assert [p.title for p in cheap] == ["Ruchka", "Daftar"]
    assert await Product.filter(title__icontains="KITOB").count() == 1
    assert await Product.filter(title__startswith="Ko").count() == 1
    assert await Product.filter(title__endswith="ka").count() == 1
    assert await Product.filter(price__in=[5_000, 2_000]).count() == 2
    assert await Product.filter(price__not_in=[5_000]).count() == 3
    assert await Product.filter(active=False).count() == 1
    assert await Product.filter(released__isnull=False).count() == 1
    assert await Product.filter(price__between=(4_000, 60_000)).count() == 2
    assert await Product.filter(Q(price__gt=1_000_000) | Q(active=False)).count() == 2
    assert await Product.exclude(title="Kitob").count() == 3
    assert await Product.filter(shop=shop).count() == 2

    p = await Product.get(title="Kitob")
    assert p.tags == ["edu"] and p.active is True and isinstance(p.created, dt.datetime)
    assert (await p.shop).title == "Navoiy Market"
    pc = await Product.get(title="Kompyuter")
    assert pc.released == dt.date(2026, 1, 5)

    with pytest.raises(DoesNotExist):
        await Product.get(title="yo'q")
    assert await Product.get_or_none(title="yo'q") is None


async def test_update_delete_aggregates(db):
    await setup(db)
    n = await Product.filter(price__lt=10_000).update(price=F("price") + 1_000)
    assert n == 2
    p = await Product.get(title="Daftar")
    assert p.price == 6_000
    await p.increment("price", 500)
    assert p.price == 6_500
    await p.update(title="Daftar 96")
    assert (await Product.get(pk=p.pk)).title == "Daftar 96"

    assert await Product.all().sum("price") == 50_000 + 6_500 + 3_000 + 9_000_000
    assert await Product.all().max("price") == 9_000_000
    assert await Product.all().min("price") == 3_000
    assert round(await Product.filter(price__lt=100_000).avg("price")) == round((50_000 + 6_500 + 3_000) / 3)

    titles = await Product.all().order_by("-price").values_list("title")
    assert titles[0] == "Kompyuter"
    page2 = await Product.all().order_by("price").page(2, 2)
    assert [x.title for x in page2] == ["Kitob", "Kompyuter"]
    assert (await Product.all().order_by("price").last()).title == "Kompyuter"

    assert await Product.filter(active=False).delete() == 1
    assert await Product.count() == 3
    assert await Product.exists(title="Kitob")


async def test_get_or_create_unique_and_save(db):
    await db.migrate([Shop, Product])
    s, created = await Shop.get_or_create(title="A", defaults={"rating": 3.0})
    assert created and s.rating == 3.0
    s2, created2 = await Shop.get_or_create(title="A")
    assert not created2 and s2.pk == s.pk
    with pytest.raises(IntegrityError):
        await Shop.create(title="A")
    s.rating = 5.0
    await s.save()
    assert (await Shop.get(title="A")).rating == 5.0
    obj, created = await Shop.update_or_create(title="A", defaults={"rating": 1.0})
    assert not created and obj.rating == 1.0
    await s.delete()
    assert await Shop.count() == 0


async def test_auto_migration_adds_columns(db):
    class Note(Model):
        text = fields.Text()

        class Meta:
            table = "notes_mig"

    await db.migrate([Note])
    await Note.create(text="eski")

    class Note2(Model):  # same table, one more column
        text = fields.Text()
        stars = fields.Int(default=5)

        class Meta:
            table = "notes_mig"

    await db.migrate([Note2])
    old = await Note2.get(text="eski")
    assert old.stars == 5
    await Note2.create(text="yangi", stars=1)
    assert await Note2.filter(stars=1).count() == 1


async def test_transaction_rollback(db):
    if db.dialect == "mongo":
        pytest.skip("MongoDB transactions need a replica set")
    await db.migrate([Shop])
    with pytest.raises(RuntimeError):
        async with db.transaction():
            await Shop.create(title="X")
            raise RuntimeError
    assert await Shop.count() == 0


async def test_builtin_user_model(db):
    from nicebot.orm.builtin import User

    await db.migrate([User])
    u = await User.create(id=777, first_name="Ali", username="ali")
    assert u.data == {} and u.is_blocked is False
    await User.create(id=778, first_name="Vali", referrer_id=777)
    assert await u.referrals_count() == 1
    assert "tg://user?id=777" in u.mention
