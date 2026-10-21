"""JSON REST API for the NomNom food & drinks ordering service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from nomnom_service.db import get_session
from nomnom_service.models import (
    Category,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    find_best_matching_product,
)
from nomnom_service.schemas import (
    OrderCancelResponse,
    OrderCreate,
    OrderItemRead,
    OrderRead,
    OrderSummary,
    ProductRead,
)

router = APIRouter(prefix="/api", tags=["nomnom"])


def _to_product_read(product: Product) -> ProductRead:
    return ProductRead(
        id=product.id,  # type: ignore[arg-type]
        name=product.name,
        description=product.description,
        price=product.price,
        category=product.category,
    )


def _to_order_read(session: Session, order: Order) -> OrderRead:
    items = session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    return OrderRead(
        order_id=order.order_id,
        location=order.location,
        delivery_date=order.delivery_date,
        order_timestamp=order.order_timestamp,
        note=order.note,
        status=order.status,
        total_amount=order.total_amount,
        items=[
            OrderItemRead(
                product_id=i.product_id,
                product_name=i.product_name,
                quantity=i.quantity,
                unit_price=i.unit_price,
                total_price=i.total_price,
            )
            for i in items
        ],
    )


@router.get("/categories", response_model=list[str])
def list_categories() -> list[str]:
    return [c.value for c in Category]


@router.get("/products", response_model=list[ProductRead])
def list_products(
    category: Category | None = None, session: Session = Depends(get_session)
) -> list[ProductRead]:
    query = select(Product)
    if category:
        query = query.where(Product.category == category)
    products = session.exec(query).all()
    return [_to_product_read(p) for p in products]


@router.get("/products/search", response_model=ProductRead | None)
def search_product(q: str, session: Session = Depends(get_session)) -> ProductRead | None:
    products = session.exec(select(Product)).all()
    match = find_best_matching_product(products, q)
    return _to_product_read(match) if match else None


@router.post("/orders", response_model=OrderRead)
def create_order(request: OrderCreate, session: Session = Depends(get_session)) -> OrderRead:
    if not request.items:
        raise HTTPException(status_code=400, detail="An order needs at least one item")

    resolved: list[tuple[Product, int]] = []
    for item in request.items:
        product = session.get(Product, item.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail=f"Unknown product id: {item.product_id}")
        resolved.append((product, item.quantity))

    total = sum(p.price * qty for p, qty in resolved)

    order = Order(
        order_id=str(uuid.uuid4()),
        location=request.location,
        delivery_date=request.delivery_date,
        order_timestamp=datetime.now(UTC),
        note=request.note,
        status=OrderStatus.CONFIRMED,
        total_amount=total,
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    for product, qty in resolved:
        session.add(
            OrderItem(
                order_id=order.id,  # type: ignore[arg-type]
                product_id=product.id,  # type: ignore[arg-type]
                product_name=product.name,
                quantity=qty,
                unit_price=product.price,
            )
        )
    session.commit()

    return _to_order_read(session, order)


@router.get("/orders", response_model=list[OrderRead])
def list_orders(location: str | None = None, session: Session = Depends(get_session)) -> list[OrderRead]:
    query = select(Order)
    if location:
        query = query.where(Order.location == location)
    orders = session.exec(query.order_by(col(Order.order_timestamp).desc())).all()
    return [_to_order_read(session, o) for o in orders]


@router.get("/orders/{order_id}", response_model=OrderRead)
def get_order(order_id: str, session: Session = Depends(get_session)) -> OrderRead:
    order = session.exec(select(Order).where(Order.order_id == order_id)).first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Unknown order: {order_id}")
    return _to_order_read(session, order)


@router.patch("/orders/{order_id}/status", response_model=OrderRead)
def update_order_status(
    order_id: str, status: OrderStatus, session: Session = Depends(get_session)
) -> OrderRead:
    order = session.exec(select(Order).where(Order.order_id == order_id)).first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Unknown order: {order_id}")
    order.status = status
    session.add(order)
    session.commit()
    session.refresh(order)
    return _to_order_read(session, order)


@router.post("/orders/{order_id}/cancel", response_model=OrderCancelResponse)
def cancel_order(order_id: str, session: Session = Depends(get_session)) -> OrderCancelResponse:
    order = session.exec(select(Order).where(Order.order_id == order_id)).first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Unknown order: {order_id}")
    if order.status == OrderStatus.CANCELLED:
        return OrderCancelResponse(success=False, message=f"Order {order_id} is already cancelled.")

    order.status = OrderStatus.CANCELLED
    session.add(order)
    session.commit()

    return OrderCancelResponse(success=True, message=f"Order {order_id} cancelled.")


@router.get("/orders-summary", response_model=OrderSummary)
def orders_summary(session: Session = Depends(get_session)) -> OrderSummary:
    orders = session.exec(select(Order)).all()
    total_orders = len(orders)
    total_revenue = sum(o.total_amount for o in orders)
    items = session.exec(select(OrderItem)).all()
    total_items_sold = sum(i.quantity for i in items)
    average_order_value = total_revenue / total_orders if total_orders else 0.0

    return OrderSummary(
        total_orders=total_orders,
        total_items_sold=total_items_sold,
        total_revenue=total_revenue,
        average_order_value=average_order_value,
    )
