from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.extensions import db
from app.models import MoneyMovement, Opportunity, Project
from app.services.world_service import WorldService


def parse_cents(value) -> int:
    try:
        quantized = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Importe no válido.") from exc
    cents = int(quantized * 100)
    if cents == 0 and quantized != 0:
        raise ValueError("Importe no válido.")
    return cents


class FinanceService:
    @staticmethod
    def totals(project_id: int | None = None) -> dict:
        q = MoneyMovement.query
        if project_id:
            q = q.filter_by(project_id=project_id)
        by: dict[str, dict[str, int]] = {}
        for row in q.all():
            bucket = by.setdefault(
                row.currency,
                {"received": 0, "paid": 0, "receivable": 0, "payable": 0},
            )
            if row.direction == "in" and row.status == "settled":
                bucket["received"] += row.amount_cents
            elif row.direction == "out" and row.status == "settled":
                bucket["paid"] += row.amount_cents
            elif row.direction == "in" and row.status == "pending":
                bucket["receivable"] += row.amount_cents
            elif row.direction == "out" and row.status == "pending":
                bucket["payable"] += row.amount_cents
        return {
            "disclaimer": "Totales de movimientos registrados, no saldo bancario ni utilidad contable.",
            "currencies": by,
        }

    @staticmethod
    def add(
        *,
        direction: str,
        amount_cents: int,
        concept: str,
        currency: str | None = None,
        status: str = "settled",
        project_id: int | None = None,
        opportunity_id: int | None = None,
        parent_id: int | None = None,
        occurred_on: date | None = None,
        category: str = "general",
    ) -> MoneyMovement:
        if amount_cents <= 0:
            raise ValueError("El importe debe ser mayor que cero.")
        if direction not in {"in", "out"}:
            raise ValueError("direction")
        mv = MoneyMovement(
            direction=direction,
            amount_cents=int(amount_cents),
            concept=concept.strip(),
            currency=(currency or WorldService.prefs().get("currency") or "USD").upper()[:8],
            status=status,
            project_id=project_id,
            opportunity_id=opportunity_id,
            parent_id=parent_id,
            occurred_on=occurred_on or WorldService.today(),
            category=category,
        )
        db.session.add(mv)
        db.session.commit()
        return mv

    @staticmethod
    def settle_partial(parent: MoneyMovement, amount_cents: int) -> MoneyMovement:
        if amount_cents <= 0 or amount_cents > parent.amount_cents:
            raise ValueError("El cobro parcial no puede superar el pendiente.")
        remaining = parent.amount_cents - amount_cents
        settled = FinanceService.add(
            direction=parent.direction,
            amount_cents=amount_cents,
            concept=parent.concept + " (parcial)",
            currency=parent.currency,
            status="settled",
            project_id=parent.project_id,
            opportunity_id=parent.opportunity_id,
            parent_id=parent.id,
        )
        parent.amount_cents = remaining
        if remaining == 0:
            parent.status = "settled"
        db.session.commit()
        return settled

    @staticmethod
    def from_won_opportunity(opp: Opportunity, create_receivable: bool) -> MoneyMovement | None:
        if not create_receivable:
            return None
        if getattr(opp, "converted_movement_id", None):
            return db.session.get(MoneyMovement, opp.converted_movement_id)
        if not opp.estimated_value:
            return None
        mv = FinanceService.add(
            direction="in",
            amount_cents=int(opp.estimated_value),
            concept=f"Cuenta por {opp.name}",
            currency=getattr(opp, "currency", None),
            status="pending",
            project_id=opp.project_id,
            opportunity_id=opp.id,
        )
        opp.converted_movement_id = mv.id
        db.session.commit()
        return mv
