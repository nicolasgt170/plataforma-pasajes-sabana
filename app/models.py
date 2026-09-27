from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    origin: Mapped[str] = mapped_column(String(80), index=True)
    destination: Mapped[str] = mapped_column(String(80), index=True)
    base_fare: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(default=True)
    schedules: Mapped[list[TripSchedule]] = relationship(back_populates="route")
    company_fares: Mapped[list[CompanyFare]] = relationship(back_populates="route")


class TripSchedule(Base):
    __tablename__ = "trip_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), index=True)
    departure_time: Mapped[str] = mapped_column(String(5))
    vehicle_label: Mapped[str] = mapped_column(String(80))
    capacity: Mapped[int] = mapped_column(default=40)
    active: Mapped[bool] = mapped_column(default=True)
    route: Mapped[Route] = relationship(back_populates="schedules")
    tickets: Mapped[list[Ticket]] = relationship(back_populates="schedule")


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    short_name: Mapped[str] = mapped_column(String(24))
    marker_color: Mapped[str] = mapped_column(String(7), default="#066b5e")
    active: Mapped[bool] = mapped_column(default=True)
    fares: Mapped[list[CompanyFare]] = relationship(back_populates="company")
    buses: Mapped[list[Bus]] = relationship(back_populates="company")


class CompanyFare(Base):
    __tablename__ = "company_fares"
    __table_args__ = (UniqueConstraint("company_id", "route_id", name="uq_company_route_fare"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), index=True)
    fare: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    company: Mapped[Company] = relationship(back_populates="fares")
    route: Mapped[Route] = relationship(back_populates="company_fares")


class Bus(Base):
    __tablename__ = "buses"
    id: Mapped[int] = mapped_column(primary_key=True)
    bus_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    simulated_plate: Mapped[str] = mapped_column(String(12), unique=True)
    route_label: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40), default="En ruta")
    company: Mapped[Company] = relationship(back_populates="buses")


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    buyer_name: Mapped[str] = mapped_column(String(120))
    buyer_document: Mapped[str] = mapped_column(String(50), index=True)
    buyer_email: Mapped[str] = mapped_column(String(120))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(30), default="CONFIRMADA")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    payment: Mapped[SimulatedPayment] = relationship(back_populates="purchase", uselist=False)
    tickets: Mapped[list[Ticket]] = relationship(back_populates="purchase")
    company: Mapped[Company | None] = relationship()


class SimulatedPayment(Base):
    __tablename__ = "simulated_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), unique=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(40), default="APROBADO_SIMULADO")
    approved_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    purchase: Mapped[Purchase] = relationship(back_populates="payment")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), index=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("trip_schedules.id"), index=True)
    passenger_name: Mapped[str] = mapped_column(String(120))
    passenger_document: Mapped[str] = mapped_column(String(50), index=True)
    ticket_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    qr_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="EMITIDO", index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    purchase: Mapped[Purchase] = relationship(back_populates="tickets")
    schedule: Mapped[TripSchedule] = relationship(back_populates="tickets")
    validations: Mapped[list[Validation]] = relationship(back_populates="ticket")


class Validation(Base):
    __tablename__ = "validations"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id"), nullable=True, index=True)
    scanned_code: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(30), index=True)
    validator_name: Mapped[str] = mapped_column(String(80), default="Validador demo")
    validated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ticket: Mapped[Ticket | None] = relationship(back_populates="validations")
