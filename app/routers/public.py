from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Company, CompanyFare, Route, TripSchedule
from ..seed import CITIES
from ..services.qr import qr_image_data_uri
from ..services.tickets import create_purchase

router = APIRouter()


def valid_city(value: str) -> str:
    if value not in CITIES:
        raise HTTPException(400, detail="El municipio seleccionado no es válido.")
    return value


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return request.app.state.templates.TemplateResponse(request=request, name="public/home.html")


@router.get("/purchase", response_class=HTMLResponse)
def purchase_page(request: Request):
    return request.app.state.templates.TemplateResponse(request=request, name="public/purchase.html", context={"cities": CITIES, "default_origin": "Tocancipá", "default_destination": "Bogotá"})


@router.get("/api/schedules")
def schedules(origin: str = Query(..., max_length=80), destination: str = Query(..., max_length=80), db: Session = Depends(get_db)):
    origin, destination = valid_city(origin), valid_city(destination)
    if origin == destination:
        return {"route": None, "companies": [], "schedules": []}
    route = db.scalar(select(Route).where(Route.origin == origin, Route.destination == destination, Route.active.is_(True)))
    if not route:
        return {"route": None, "companies": [], "schedules": []}
    fares = db.execute(select(CompanyFare, Company).join(Company).where(CompanyFare.route_id == route.id, Company.active.is_(True)).order_by(Company.name)).all()
    rows = db.scalars(select(TripSchedule).where(TripSchedule.route_id == route.id, TripSchedule.active.is_(True)).order_by(TripSchedule.departure_time)).all()
    return {"route": {"id": route.id, "duration_minutes": route.duration_minutes}, "companies": [{"id": fare.company_id, "name": company.name, "fare": float(fare.fare)} for fare, company in fares], "schedules": [{"id": row.id, "departure_time": row.departure_time, "vehicle_label": row.vehicle_label} for row in rows]}


@router.post("/purchase", response_class=HTMLResponse)
def complete_purchase(request: Request, schedule_id: int = Form(..., ge=1), company_id: int = Form(..., ge=1), passenger_name: str = Form(..., max_length=120), passenger_document: str = Form(..., max_length=50), passenger_email: str = Form(..., max_length=120), quantity: int = Form(1, ge=1, le=5), db: Session = Depends(get_db)):
    purchase = create_purchase(db, schedule_id, company_id, passenger_name, passenger_document, passenger_email, quantity)
    tickets = [{"ticket": ticket, "qr": qr_image_data_uri(ticket.qr_token)} for ticket in purchase.tickets]
    return request.app.state.templates.TemplateResponse(request=request, name="public/receipt.html", context={"purchase": purchase, "tickets": tickets})
