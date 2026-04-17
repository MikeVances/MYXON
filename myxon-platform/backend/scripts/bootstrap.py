"""
MYXON Bootstrap — первоначальная настройка БД.

Создаёт 4-tier иерархию тенантов и первого platform_admin.
Запускать один раз после первого `alembic upgrade head`.

Использование:
    docker compose -f docker-compose.prod.yml exec backend python -m scripts.bootstrap

Или с переменными:
    ADMIN_EMAIL=admin@agrovnt.ru ADMIN_PASSWORD=supersecret \
      docker compose -f docker-compose.prod.yml exec backend python -m scripts.bootstrap
"""
import asyncio
import os
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password
from app.models.site import Site
from app.models.tenant import Tenant
from app.models.user import User

# ── Конфигурация через env-переменные (можно переопределить) ──────────────────
ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL",    "admin@myxon.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")
ADMIN_NAME     = os.environ.get("ADMIN_NAME",     "Platform Admin")

PARTNER_NAME   = os.environ.get("PARTNER_NAME",   "HOTRACO")
DEALER_NAME    = os.environ.get("DEALER_NAME",    "Агровент")
CUSTOMER_NAME  = os.environ.get("CUSTOMER_NAME",  "Тестовая Ферма")


async def bootstrap():
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:

        # ── Проверка: уже запускали? ──────────────────────────────────────────
        existing = await db.execute(
            select(Tenant).where(Tenant.tier == "platform")
        )
        if existing.scalar_one_or_none():
            print("⚠  Platform tenant уже существует. Bootstrap пропущен.")
            print("   Для пересоздания удалите данные из БД вручную.")
            return

        # ── Tier 1: Platform (MYXON Corp) ─────────────────────────────────────
        platform = Tenant(
            id=uuid.uuid4(),
            name="MYXON Platform",
            slug="myxon-platform",
            tier="platform",
        )
        db.add(platform)
        await db.flush()

        admin = User(
            id=uuid.uuid4(),
            email=ADMIN_EMAIL,
            hashed_password=hash_password(ADMIN_PASSWORD),
            full_name=ADMIN_NAME,
            role="platform_admin",
            tenant_id=platform.id,
        )
        db.add(admin)

        # ── Tier 2: Partner (HOTRACO или другой вендор железа) ────────────────
        partner = Tenant(
            id=uuid.uuid4(),
            name=PARTNER_NAME,
            slug=PARTNER_NAME.lower().replace(" ", "-"),
            tier="partner",
            parent_id=platform.id,
        )
        db.add(partner)
        await db.flush()

        partner_admin = User(
            id=uuid.uuid4(),
            email=f"admin@{PARTNER_NAME.lower()}.local",
            hashed_password=hash_password("partner123"),
            full_name=f"{PARTNER_NAME} Admin",
            role="partner_admin",
            tenant_id=partner.id,
        )
        db.add(partner_admin)

        # ── Tier 3: Dealer (Агровент или другой дилер) ────────────────────────
        dealer = Tenant(
            id=uuid.uuid4(),
            name=DEALER_NAME,
            slug=DEALER_NAME.lower().replace(" ", "-"),
            tier="dealer",
            parent_id=partner.id,
        )
        db.add(dealer)
        await db.flush()

        dealer_admin = User(
            id=uuid.uuid4(),
            email=f"admin@{DEALER_NAME.lower()}.local",
            hashed_password=hash_password("dealer123"),
            full_name=f"{DEALER_NAME} Инженер",
            role="dealer_admin",
            tenant_id=dealer.id,
        )
        db.add(dealer_admin)

        # ── Tier 4: Customer (тестовая ферма) ─────────────────────────────────
        customer = Tenant(
            id=uuid.uuid4(),
            name=CUSTOMER_NAME,
            slug="test-farm-001",
            tier="customer",
            parent_id=dealer.id,
        )
        db.add(customer)
        await db.flush()

        customer_admin = User(
            id=uuid.uuid4(),
            email="farmer@test.local",
            hashed_password=hash_password("farmer123"),
            full_name="Фермер Тестовый",
            role="customer_admin",
            tenant_id=customer.id,
        )
        db.add(customer_admin)

        # ── Site для тестовой фермы ───────────────────────────────────────────
        site = Site(
            id=uuid.uuid4(),
            name="Корпус 1",
            address="Тестовый адрес, 1",
            tenant_id=customer.id,
        )
        db.add(site)

        await db.commit()

    await engine.dispose()

    # ── Вывод результата ──────────────────────────────────────────────────────
    print()
    print("✅ MYXON Bootstrap завершён!")
    print()
    print("  Иерархия тенантов:")
    print(f"  [platform]  MYXON Platform")
    print(f"  [partner]   {PARTNER_NAME}")
    print(f"  [dealer]    {DEALER_NAME}")
    print(f"  [customer]  {CUSTOMER_NAME}")
    print()
    print("  Пользователи:")
    print(f"  platform_admin  : {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"  partner_admin   : admin@{PARTNER_NAME.lower()}.local / partner123")
    print(f"  dealer_admin    : admin@{DEALER_NAME.lower()}.local / dealer123")
    print(f"  customer_admin  : farmer@test.local / farmer123")
    print()
    print("  ⚠  Смени пароли после первого входа!")
    print()
    print("  Следующий шаг — зарегистрировать устройство через dealer_admin:")
    print("  POST /api/v0/devices/register  { serial_number: 'MYXON-ORN-001' }")
    print()


if __name__ == "__main__":
    asyncio.run(bootstrap())
