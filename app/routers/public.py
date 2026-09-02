from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Route, TripSchedule
from ..seed import CITIES
from ..services.qr import qr_image_data_uri
from ..services.tickets import create_purchase

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def purchase_page(request: Request, db: Session = Depends(get_db)):
    # La plantilla necesita solo la lista de ciudades y la selección inicial.
    # Los horarios se consultan después por /api/schedules según la ruta elegida.
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="public/purchase.html",
        context={
            "cities": CITIES,
            "default_origin": "Tocancipá",
            "default_destination": "Bogotá",
        },
    )


@router.get("/api/schedules")
def schedules(origin: str, destination: str, db: Session = Depends(get_db)):
    if origin == destination:
        return {"route": None, "schedules": []}
    route = db.scalar(select(Route).where(Route.origin == origin, Route.destination == destination, Route.active.is_(True)))
    if not route:
        return {"route": None, "schedules": []}
    rows = db.scalars(select(TripSchedule).where(TripSchedule.route_id == route.id, TripSchedule.active.is_(True)).order_by(TripSchedule.departure_time)).all()
    return {"route": {"id": route.id, "fare": float(route.base_fare), "duration_minutes": route.duration_minutes}, "schedules": [
        {"id": row.id, "departure_time": row.departure_time, "vehicle_label": row.vehicle_label} for row in rows
    ]}


@router.post("/purchase", response_class=HTMLResponse)
def complete_purchase(
    request: Request, schedule_id: int = Form(...), passenger_name: str = Form(...),
    passenger_document: str = Form(...), passenger_email: str = Form(...), quantity: int = Form(1),
    db: Session = Depends(get_db),
):
    purchase = create_purchase(db, schedule_id, passenger_name.strip(), passenger_document.strip(), passenger_email.strip(), quantity)
    tickets = [{"ticket": ticket, "qr": qr_image_data_uri(ticket.qr_token)} for ticket in purchase.tickets]
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="public/receipt.html",
        context={"purchase": purchase, "tickets": tickets},
    )
