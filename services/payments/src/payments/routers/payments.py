from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from payments.db import get_session
from payments.models import Payment, PaymentStatus
from payments.schemas import ChargeRequest, ChargeResponse, RefundRequest, RefundResponse

router = APIRouter(tags=["payments"])

# No role checks in this router: every route is admin-only (no
# browser-facing endpoint at all) -- enforced ahead of this app entirely
# by payments-gate (nginx, auth_request) + payments-verify (OPA-backed,
# policies/payments.rego). See docker-compose.yml's payments-gate/
# payments-verify.


def _simulate_outcome(amount: float, fail_on_suffix: str) -> PaymentStatus:
    """Dev-only failure simulation (no real payment gateway integration in
    this ticket — see config.py's payment_fail_on_amount_suffix)."""
    if fail_on_suffix and f"{amount:.2f}".endswith(fail_on_suffix):
        return PaymentStatus.FAILED
    return PaymentStatus.CHARGED


@router.post("/charge", response_model=ChargeResponse, status_code=201)
async def charge(
    body: ChargeRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChargeResponse:
    # Idempotent by order_id: a same-order_id retry (Temporal activity
    # retry, or a genuinely duplicate request) returns the existing charge
    # instead of charging twice.
    existing = await session.scalar(select(Payment).where(Payment.order_id == body.order_id))
    if existing is not None:
        return ChargeResponse(payment_id=existing.id, status=existing.status)

    fail_on_suffix = request.app.state.settings.payment_fail_on_amount_suffix
    status = _simulate_outcome(body.amount, fail_on_suffix)
    payment = Payment(order_id=body.order_id, amount=body.amount, status=status)
    session.add(payment)
    try:
        await session.commit()
    except IntegrityError:
        # Lost a race against a concurrent charge for the same order_id —
        # the unique constraint on order_id caught it. Re-fetch and return
        # the winner's row rather than erroring, same "no-op on conflict"
        # idea as Orders' Stripe webhook handler.
        await session.rollback()
        existing = await session.scalar(select(Payment).where(Payment.order_id == body.order_id))
        assert existing is not None
        return ChargeResponse(payment_id=existing.id, status=existing.status)

    return ChargeResponse(payment_id=payment.id, status=payment.status)


@router.post("/refund", response_model=RefundResponse)
async def refund(
    body: RefundRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RefundResponse:
    payment = await session.scalar(select(Payment).where(Payment.id == body.payment_id))
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Idempotent by payment_id: already-refunded is a no-op returning the
    # current (refunded) status rather than refunding twice.
    if payment.status != PaymentStatus.REFUNDED:
        payment.status = PaymentStatus.REFUNDED
        await session.commit()

    return RefundResponse(status=payment.status)
