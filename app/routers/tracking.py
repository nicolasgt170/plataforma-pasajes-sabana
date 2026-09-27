from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Bus, Company
from ..services.tracking import SIMULATED_ROUTE_PATTERNS, SIMULATION_STOPS

router = APIRouter(prefix="/tracking")

@router.get("", response_class=HTMLResponse)
def tracking_page(request: Request):
    return request.app.state.templates.TemplateResponse(request=request, name="public/tracking.html", context={"maps_api_key": request.app.state.maps_api_key})

@router.get("/api/buses")
def simulated_buses(db: Session = Depends(get_db)):
    """Diez vehículos estables de demostración; el movimiento queda en el navegador."""
    persisted = db.scalars(select(Bus).options(joinedload(Bus.company)).order_by(Bus.id)).all()
    companies = db.scalars(select(Company).where(Company.active.is_(True)).order_by(Company.id)).all()
    source = []
    for index in range(10):
        if index < len(persisted):
            item, company = persisted[index], persisted[index].company
            bus_id, plate = item.bus_code, item.simulated_plate
        else:
            company = companies[index % len(companies)]
            bus_id, plate = f"BUS-{index + 1:03d}", f"DEM{index + 1:03d}"
        path = SIMULATED_ROUTE_PATTERNS[index % len(SIMULATED_ROUTE_PATTERNS)]
        source.append({"id": bus_id, "company": company.name, "short_name": company.short_name, "color": company.marker_color, "plate": plate, "route_stops": path, "route": f"{path[0]} → {path[1]}", "status": "En ruta", "speed": 25 + (index * 4) % 22, "initial_progress": round((index * 0.097) % 1, 3), "stop_seconds": 2 + index % 4})
    return {"simulation": True, "buses": source, "stops": SIMULATION_STOPS}
