from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Route, TripSchedule

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


def seed_database(db: Session) -> None:
    """Completa los datos de demostración sin duplicarlos."""
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
