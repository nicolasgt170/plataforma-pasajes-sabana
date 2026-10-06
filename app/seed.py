from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AdminUser, Bus, Company, CompanyFare, Route, TripSchedule
from .services.auth import hash_password

CITIES = ["Zipaquirá", "Tenjo", "Sopó", "Tocancipá", "Bogotá"]

# Cada ruta se inserta en ambos sentidos para la demostración.
ROUTE_EXAMPLES = [
    ("Tocancipá", "Bogotá", "12000", 55),
    ("Zipaquirá", "Bogotá", "14500", 70),
    ("Tenjo", "Bogotá", "11000", 50),
    ("Sopó", "Bogotá", "13000", 60),
    ("Zipaquirá", "Tocancipá", "7000", 35),
    ("Tenjo", "Zipaquirá", "8500", 45),
    ("Sopó", "Tocancipá", "6500", 30),
    ("Zipaquirá", "Sopó", "9000", 48),
    ("Tenjo", "Tocancipá", "10500", 58),
    ("Tenjo", "Sopó", "11500", 62),
]
TIMES = ["06:00", "08:00", "12:00", "16:00", "18:00"]
COMPANIES = [
    ("Rápido del Carmen", "RÁPIDO", "#0b6e4f"), ("La Reina", "REINA", "#7c3aed"),
    ("Gómez Villa", "GÓMEZ", "#b45309"), ("Río Negro", "RÍO", "#1d4ed8"),
    ("Trans Libertadores", "LIBRE", "#be123c"), ("Cotranzipa", "COTRA", "#0369a1"),
    ("Alianza", "ALIANZA", "#15803d"), ("Valle del Tenza", "TENZA", "#a16207"),
    ("Águila", "ÁGUILA", "#4338ca"),
]


def seed_database(db: Session) -> None:
    """Completa los datos de demostración sin duplicarlos."""
    print("SEED_DATABASE: INICIO")
    existing = {(route.origin, route.destination) for route in db.scalars(select(Route)).all()}
    for origin, destination, fare, duration in ROUTE_EXAMPLES:
        for route_origin, route_destination in ((origin, destination), (destination, origin)):
            if (route_origin, route_destination) in existing:
                continue
            route = Route(
                origin=route_origin,
                destination=route_destination,
                base_fare=Decimal(fare),
                duration_minutes=duration,
            )
            db.add(route)
            db.flush()
            for index, departure_time in enumerate(TIMES, start=1):
                db.add(
                    TripSchedule(
                        route_id=route.id,
                        departure_time=departure_time,
                        vehicle_label=f"Sabana {route_origin[:3].upper()}-{index:02d}",
                        capacity=40,
                    )
                )
            existing.add((route_origin, route_destination))
    db.commit()

    legacy_company = db.scalar(select(Company).where(Company.name == "Trans Libertador"))
    if legacy_company and not db.scalar(select(Company).where(Company.name == "Trans Libertadores")):
        legacy_company.name = "Trans Libertadores"
        db.commit()
    existing_companies = {company.name for company in db.scalars(select(Company)).all()}
    for name, short_name, color in COMPANIES:
        if name not in existing_companies:
            db.add(Company(name=name, short_name=short_name, marker_color=color))
    db.commit()

    # Las tarifas son una simulación y varían ligeramente por empresa y trayecto.
    companies = db.scalars(select(Company).order_by(Company.id)).all()
    for route in db.scalars(select(Route)).all():
        for index, company in enumerate(companies):
            if not db.scalar(select(CompanyFare.id).where(CompanyFare.company_id == company.id, CompanyFare.route_id == route.id)):
                variation = Decimal((index - 4) * 150)
                db.add(CompanyFare(company_id=company.id, route_id=route.id, fare=max(Decimal("5000"), route.base_fare + variation)))
    db.commit()

    if not db.scalar(select(Bus.id)):
        routes = db.scalars(select(Route).limit(6)).all()
        for index, route in enumerate(routes, start=1):
            company = companies[(index - 1) % len(companies)]
            db.add(Bus(bus_code=f"BUS-{index:03d}", company_id=company.id, simulated_plate=f"SIM{index:03d}", route_label=f"{route.origin} → {route.destination}", status="En ruta"))
        db.commit()

            # Inicialización y recuperación del usuario administrador.
    import os

    username = os.getenv("ADMIN_INITIAL_USERNAME", "").strip()
    password = os.getenv("ADMIN_INITIAL_PASSWORD", "")
    force_reset = os.getenv("ADMIN_FORCE_RESET", "").strip().lower() == "true"
    
    print(
        "ADMIN_ENV: "
        f"username_presente={bool(username)}, "
        f"password_presente={bool(password)}, "
        f"force_reset={force_reset}, "
        f"password_placeholder={password == 'change-this-before-running'}"
    )

    if username and password and password != "change-this-before-running":
        configured_user = db.scalar(
            select(AdminUser).where(AdminUser.username == username)
        )

        legacy_user = db.scalar(
            select(AdminUser).where(AdminUser.username == "admin")
        )

        print(
            f"ADMIN_DIAGNOSTIC: username_configurado={username!r}, "
            f"force_reset={force_reset}"
        )

        if configured_user:
            print(
                f"ADMIN_DIAGNOSTIC: usuario encontrado={configured_user.username!r}, "
                f"failed_attempts={configured_user.failed_attempts}, "
                f"locked_until={configured_user.locked_until}"
            )

            if force_reset:
                configured_user.password_hash = hash_password(password)
                configured_user.failed_attempts = 0
                configured_user.locked_until = None
                db.commit()

                print(
                    "ADMIN_DIAGNOSTIC: contraseña restablecida"
                )

        elif legacy_user:
            print(
                f"ADMIN_DIAGNOSTIC: usuario legado encontrado="
                f"{legacy_user.username!r}; se migrará"
            )

            legacy_user.username = username
            legacy_user.password_hash = hash_password(password)
            legacy_user.failed_attempts = 0
            legacy_user.locked_until = None
            db.commit()

            print(
                f"ADMIN_DIAGNOSTIC: usuario migrado a {username!r}"
            )

        else:
            print(
                "ADMIN_DIAGNOSTIC: no existe usuario configurado ni usuario legado; "
                "se creará uno nuevo"
            )

            db.add(
                AdminUser(
                    username=username,
                    password_hash=hash_password(password),
                )
            )
            db.commit()

            print(
                f"ADMIN_DIAGNOSTIC: usuario {username!r} creado"
            )

        # Diagnóstico final de los usuarios administradores.
        all_admins = db.scalars(
            select(AdminUser).order_by(AdminUser.id)
        ).all()

        print(
            "ADMIN_DIAGNOSTIC: administradores en BD="
            + repr(
                [
                    {
                        "id": user.id,
                        "username": user.username,
                        "failed_attempts": user.failed_attempts,
                        "locked": user.locked_until is not None,
                    }
                    for user in all_admins
                ]
            )
        )