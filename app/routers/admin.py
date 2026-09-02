from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import SimulatedPayment, Ticket, TripSchedule, Validation

router = APIRouter(prefix="/admin")


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    tickets = db.scalars(select(Ticket).options(joinedload(Ticket.purchase), joinedload(Ticket.schedule).joinedload(TripSchedule.route)).order_by(Ticket.issued_at.desc())).unique().all()
    payments = db.scalars(select(SimulatedPayment).options(joinedload(SimulatedPayment.purchase)).order_by(SimulatedPayment.approved_at.desc())).all()
    validations = db.scalars(select(Validation).options(joinedload(Validation.ticket).joinedload(Ticket.schedule).joinedload(TripSchedule.route)).order_by(Validation.validated_at.desc()).limit(100)).unique().all()
    stats = {
        "issued": db.scalar(select(func.count(Ticket.id))) or 0,
        "used": db.scalar(select(func.count(Ticket.id)).where(Ticket.status == "USADO")) or 0,
        "payments": db.scalar(select(func.count(SimulatedPayment.id))) or 0,
        "validations": db.scalar(select(func.count(Validation.id))) or 0,
    }
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context={
            "tickets": tickets,
            "payments": payments,
            "validations": validations,
            "stats": stats,
        },
    )
