from datetime import datetime
from decimal import Decimal
from secrets import token_urlsafe
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import Purchase, SimulatedPayment, Ticket, TripSchedule, Validation


def new_reference(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10].upper()}"


def create_purchase(
    db: Session, schedule_id: int, name: str, document: str, email: str, quantity: int
) -> Purchase:
    schedule = db.scalar(
        select(TripSchedule).options(joinedload(TripSchedule.route)).where(TripSchedule.id == schedule_id, TripSchedule.active.is_(True))
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="El horario seleccionado no está disponible.")
    if quantity < 1 or quantity > 5:
        raise HTTPException(status_code=400, detail="La cantidad permitida es de 1 a 5 pasajes.")

    total = schedule.route.base_fare * quantity
    purchase = Purchase(
        reference=new_reference("COMPRA"), buyer_name=name, buyer_document=document,
        buyer_email=email, total_amount=total, status="CONFIRMADA"
    )
    db.add(purchase)
    db.flush()
    db.add(SimulatedPayment(
        purchase_id=purchase.id, reference=new_reference("PAGO"), amount=total,
        status="APROBADO_SIMULADO"
    ))
    for _ in range(quantity):
        db.add(Ticket(
            purchase_id=purchase.id, schedule_id=schedule.id, passenger_name=name,
            passenger_document=document, ticket_code=new_reference("SAB"),
            qr_token=token_urlsafe(24), status="EMITIDO"
        ))
    db.commit()
    return db.execute(
        select(Purchase).options(
            joinedload(Purchase.payment),
            joinedload(Purchase.tickets).joinedload(Ticket.schedule).joinedload(TripSchedule.route),
        ).where(Purchase.id == purchase.id)
    ).unique().scalar_one()


def validate_ticket(db: Session, raw_code: str) -> tuple[str, Ticket | None]:
    code = raw_code.strip()
    # A hardware scanner may return the QR URL; extract its token too.
    if "code=" in code:
        code = code.split("code=", 1)[1].split("&", 1)[0]
    ticket = db.scalar(
        select(Ticket)
        .options(joinedload(Ticket.schedule).joinedload(TripSchedule.route))
        .where((Ticket.qr_token == code) | (Ticket.ticket_code == code))
        .with_for_update()
    )
    if not ticket:
        db.add(Validation(scanned_code=raw_code, result="NO_ENCONTRADO"))
        db.commit()
        return "NO_ENCONTRADO", None
    if ticket.status == "EMITIDO":
        ticket.status = "USADO"
        ticket.used_at = datetime.now()
        result = "VALIDO_USADO"
    elif ticket.status == "USADO":
        result = "YA_UTILIZADO"
    else:
        result = "ANULADO"
    db.add(Validation(ticket_id=ticket.id, scanned_code=raw_code, result=result))
    db.commit()
    return result, ticket
