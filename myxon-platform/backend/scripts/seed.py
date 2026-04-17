"""
Seed script — creates test tenant, users, and pre-registered devices.
Run once after DB init:
    docker compose exec backend python -m scripts.seed
"""
import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base
from app.core.security import hash_password
from app.models.device import Device
from app.models.site import Site
from app.models.tenant import Tenant
from app.models.user import User


async def seed():
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Check if already seeded
        existing = await db.execute(select(Tenant).where(Tenant.slug == "demo-integrator"))
        if existing.scalar_one_or_none():
            print("⚠  Seed data already exists. Skipping.")
            return

        # ── Tenant ──
        vendor = Tenant(
            id=uuid.uuid4(),
            name="MYXON Corp",
            slug="myxon-corp",
            tier="vendor",
        )
        integrator = Tenant(
            id=uuid.uuid4(),
            name="Demo Integrator",
            slug="demo-integrator",
            tier="integrator",
            parent_id=vendor.id,
        )
        db.add_all([vendor, integrator])
        await db.flush()

        # ── Users ──
        admin = User(
            id=uuid.uuid4(),
            email="admin@myxon.local",
            hashed_password=hash_password("admin123"),
            full_name="Admin User",
            role="admin",
            tenant_id=integrator.id,
        )
        engineer = User(
            id=uuid.uuid4(),
            email="engineer@myxon.local",
            hashed_password=hash_password("engineer123"),
            full_name="Field Engineer",
            role="engineer",
            tenant_id=integrator.id,
        )
        viewer = User(
            id=uuid.uuid4(),
            email="viewer@myxon.local",
            hashed_password=hash_password("viewer123"),
            full_name="Viewer User",
            role="viewer",
            tenant_id=integrator.id,
        )
        db.add_all([admin, engineer, viewer])
        await db.flush()

        # ── Site ──
        site = Site(
            id=uuid.uuid4(),
            name="Moscow Factory Floor",
            address="ul. Leninskaya 42, Moscow",
            tenant_id=integrator.id,
        )
        db.add(site)
        await db.flush()

        # ── Devices ──
        # Device 1: ready to claim
        activation_code_1 = "ABCD-1234-EFGH"
        device1 = Device(
            id=uuid.uuid4(),
            serial_number="MX-2024-00001",
            name="Gateway Alpha",
            model="MYXON-R1000",
            firmware_version="1.0.0",
            status="pre_registered",
            claim_state="ready_for_transfer",
            activation_code_hash=hash_password(activation_code_1),
            vendor_id="hotraco",
            device_family="orion",
            device_capabilities=[
                {"id": "screen-orion", "protocol": "tcp-direct", "transport": "tcp_direct"},
                {"id": "config-orion", "protocol": "tcp-direct", "transport": "tcp_direct"},
            ],
        )

        # Device 2: already claimed & online (Orion family)
        device2 = Device(
            id=uuid.uuid4(),
            serial_number="MX-2024-00002",
            name="Gateway Beta",
            model="MYXON-R1000",
            firmware_version="1.0.0",
            status="online",
            claim_state="claimed",
            vendor_id="hotraco",
            device_family="orion",
            tenant_id=integrator.id,
            site_id=site.id,
            published_resources=[
                {"id": "web-hmi", "name": "Web HMI Panel", "protocol": "http", "port": 80},
                {"id": "vnc-plc", "name": "PLC VNC Access", "protocol": "vnc", "port": 5900},
            ],
        )

        # Device 3: claimed but offline (Sirius family)
        device3 = Device(
            id=uuid.uuid4(),
            serial_number="MX-2024-00003",
            name="Gateway Gamma",
            model="MYXON-R2000",
            firmware_version="1.1.0",
            status="offline",
            claim_state="claimed",
            vendor_id="hotraco",
            device_family="sirius",
            device_capabilities=[
                {"id": "screen-sirius", "protocol": "tcp-direct", "transport": "tcp_direct"},
            ],
            tenant_id=integrator.id,
            site_id=site.id,
        )

        db.add_all([device1, device2, device3])
        await db.commit()

        print("✅ Seed data created:")
        print(f"   Tenants:  {vendor.name}, {integrator.name}")
        print(f"   Users:    admin@myxon.local / admin123")
        print(f"             engineer@myxon.local / engineer123")
        print(f"             viewer@myxon.local / viewer123")
        print(f"   Site:     {site.name}")
        print(f"   Devices:  {device1.serial_number} (unclaimed, code: {activation_code_1})")
        print(f"             {device2.serial_number} (online, 2 resources)")
        print(f"             {device3.serial_number} (offline)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
