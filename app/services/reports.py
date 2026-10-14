"""Consultas de ventas: solo pagos simulados aprobados y compras confirmadas."""
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Company, Purchase, SimulatedPayment, Ticket

APPROVED_PAYMENT = "APROBADO_SIMULADO"
CONFIRMED_PURCHASE = "CONFIRMADA"


def sales_report(db: Session) -> dict:
    eligible = (SimulatedPayment.status == APPROVED_PAYMENT, Purchase.status == CONFIRMED_PURCHASE)
    global_row = db.execute(
        select(
            func.coalesce(func.sum(SimulatedPayment.amount), 0),
            func.count(Purchase.id),
        ).join(Purchase, SimulatedPayment.purchase_id == Purchase.id).where(*eligible)
    ).one()
    total_revenue, total_purchases = Decimal(global_row[0]), global_row[1]

    ticket_counts = dict(db.execute(
        select(Purchase.company_id, func.count(Ticket.id))
        .join(Purchase, Ticket.purchase_id == Purchase.id)
        .join(SimulatedPayment, SimulatedPayment.purchase_id == Purchase.id)
        .where(*eligible).group_by(Purchase.company_id)
    ).all())
    rows = db.execute(
        select(Company.id, Company.name, func.coalesce(func.sum(SimulatedPayment.amount), 0), func.count(Purchase.id))
        .join(Purchase, Purchase.company_id == Company.id)
        .join(SimulatedPayment, SimulatedPayment.purchase_id == Purchase.id)
        .where(*eligible).group_by(Company.id, Company.name).order_by(Company.name)
    ).all()
    companies = [{"id": row[0], "name": row[1], "revenue": Decimal(row[2]), "purchases": row[3], "tickets": ticket_counts.get(row[0], 0)} for row in rows]
    assigned_revenue = sum((row["revenue"] for row in companies), Decimal("0"))
    assigned_tickets = sum(row["tickets"] for row in companies)
    return {"global": {"revenue": total_revenue, "purchases": total_purchases, "tickets": sum(ticket_counts.values()), "companies_with_sales": len(companies), "unassigned_revenue": total_revenue - assigned_revenue, "unassigned_tickets": ticket_counts.get(None, 0)}, "companies": companies}
