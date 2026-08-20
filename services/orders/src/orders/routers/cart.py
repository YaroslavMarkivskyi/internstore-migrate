import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from orders.auth import InternalClaims, get_internal_claims
from orders.db import get_session
from orders.models import Cart, CartItem
from orders.schemas import CartItemCreate, CartItemUpdate, CartRead

router = APIRouter(prefix="/cart", tags=["cart"])

# claims here come from orders-gate's forwarded X-User-Id/X-User-Role (see
# orders/auth.py) -- already-verified identity, not this service's own
# jwt.decode() anymore.


async def _get_cart(session: AsyncSession, owner_id: str) -> Cart | None:
    result = await session.execute(
        select(Cart).options(selectinload(Cart.items)).where(Cart.owner_id == owner_id)
    )
    return result.scalar_one_or_none()


async def _get_or_create_cart(session: AsyncSession, owner_id: str) -> Cart:
    cart = await _get_cart(session, owner_id)
    if cart is None:
        cart = Cart(owner_id=owner_id)
        session.add(cart)
        await session.flush()
    return cart


@router.get("", response_model=CartRead)
async def get_cart(
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CartRead:
    cart = await _get_cart(session, claims.sub)
    if cart is None:
        return CartRead(items=[])
    return CartRead.model_validate({"items": cart.items})


@router.post("", response_model=CartRead, status_code=201)
async def add_cart_item(
    payload: CartItemCreate,
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CartRead:
    cart = await _get_or_create_cart(session, claims.sub)

    existing = await session.execute(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == payload.product_id)
    )
    item = existing.scalar_one_or_none()
    if item is not None:
        item.quantity += payload.quantity
    else:
        item = CartItem(cart_id=cart.id, product_id=payload.product_id, quantity=payload.quantity)
        session.add(item)

    await session.commit()
    await session.refresh(cart, attribute_names=["items"])
    return CartRead.model_validate({"items": cart.items})


@router.put("/items/{product_id}", response_model=CartRead)
async def update_cart_item(
    product_id: uuid.UUID,
    payload: CartItemUpdate,
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CartRead:
    cart = await _get_cart(session, claims.sub)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart is empty")

    existing = await session.execute(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
    )
    item = existing.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not in cart")

    item.quantity = payload.quantity
    await session.commit()
    await session.refresh(cart, attribute_names=["items"])
    return CartRead.model_validate({"items": cart.items})


@router.delete("/items/{product_id}", status_code=204)
async def remove_cart_item(
    product_id: uuid.UUID,
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    cart = await _get_cart(session, claims.sub)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart is empty")

    existing = await session.execute(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
    )
    item = existing.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not in cart")

    await session.delete(item)
    await session.commit()
    return Response(status_code=204)
