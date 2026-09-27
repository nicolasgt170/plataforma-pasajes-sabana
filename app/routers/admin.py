from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Bus, Company, SimulatedPayment, Ticket, TripSchedule, Validation
from ..services.auth import authenticate_admin
from ..services.validation import USERNAME_RE

router = APIRouter(prefix="/admin")


def logged_in(request: Request) -> bool:
    return bool(request.session.get("admin_user_id"))


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if logged_in(request): return RedirectResponse("/admin", 303)
    return request.app.state.templates.TemplateResponse(request=request, name="admin/login.html", context={"error": None})


@router.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(..., max_length=50), password: str = Form(..., max_length=256), db: Session = Depends(get_db)):
    normalized = username.strip()
    user = authenticate_admin(db, normalized if USERNAME_RE.fullmatch(normalized) else "invalid-user", password)
    if not user:
        return request.app.state.templates.TemplateResponse(request=request, name="admin/login.html", context={"error": "usuario y/o contraseña incorrectos"}, status_code=401)
    request.session.clear(); request.session["admin_user_id"] = user.id
    return RedirectResponse("/admin", 303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear(); return RedirectResponse("/", 303)


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    if not logged_in(request): return RedirectResponse("/admin/login", 303)
    tickets = db.scalars(select(Ticket).options(joinedload(Ticket.purchase), joinedload(Ticket.schedule).joinedload(TripSchedule.route)).order_by(Ticket.issued_at.desc())).unique().all()
    payments = db.scalars(select(SimulatedPayment).options(joinedload(SimulatedPayment.purchase)).order_by(SimulatedPayment.approved_at.desc())).all()
    validations = db.scalars(select(Validation).options(joinedload(Validation.ticket).joinedload(Ticket.schedule).joinedload(TripSchedule.route)).order_by(Validation.validated_at.desc()).limit(100)).unique().all()
    stats = {"issued": db.scalar(select(func.count(Ticket.id))) or 0, "used": db.scalar(select(func.count(Ticket.id)).where(Ticket.status == "USADO")) or 0, "payments": db.scalar(select(func.count(SimulatedPayment.id))) or 0, "validations": db.scalar(select(func.count(Validation.id))) or 0, "buses": db.scalar(select(func.count(Bus.id))) or 0, "companies": db.scalar(select(func.count(Company.id))) or 0, "revenue": db.scalar(select(func.coalesce(func.sum(SimulatedPayment.amount), 0))) or 0}
    return request.app.state.templates.TemplateResponse(request=request, name="admin/dashboard.html", context={"tickets": tickets, "payments": payments, "validations": validations, "stats": stats, "buses": db.scalars(select(Bus).options(joinedload(Bus.company))).all(), "companies": db.scalars(select(Company).order_by(Company.name)).all()})
