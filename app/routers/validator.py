from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.tickets import validate_ticket

router = APIRouter(prefix="/validator")


@router.get("", response_class=HTMLResponse)
def validator_page(request: Request, code: str = ""):
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="validator/index.html",
        context={"code": code, "result": None, "ticket": None},
    )


@router.post("", response_class=HTMLResponse)
def validate(request: Request, code: str = Form(...), db: Session = Depends(get_db)):
    result, ticket = validate_ticket(db, code)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="validator/index.html",
        context={"code": code, "result": result, "ticket": ticket},
    )
