"""Server-rendered UI (Jinja2 + HTMX) for the NomNom service."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, col, select

from nomnom_service.db import get_session
from nomnom_service.models import Order, OrderItem, OrderStatus, Product

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory="src/nomnom_service/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@router.get("/products", response_class=HTMLResponse)
def products_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    products = session.exec(select(Product)).all()
    by_category: dict[str, list[Product]] = {}
    for product in products:
        by_category.setdefault(product.category.value, []).append(product)
    return templates.TemplateResponse(request, "products.html", {"by_category": by_category})


@router.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    orders = session.exec(select(Order).order_by(col(Order.order_timestamp).desc())).all()
    return templates.TemplateResponse(request, "orders.html", {"orders": orders})


@router.get("/orders/{order_id}", response_class=HTMLResponse)
def order_detail_page(
    request: Request, order_id: str, session: Session = Depends(get_session)
) -> HTMLResponse:
    order = session.exec(select(Order).where(Order.order_id == order_id)).first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Unknown order: {order_id}")
    items = session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    return templates.TemplateResponse(
        request, "order_detail.html", {"order": order, "items": items}
    )


@router.get("/orders/new", response_class=HTMLResponse)
def new_order_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    products = session.exec(select(Product)).all()
    return templates.TemplateResponse(request, "order_form.html", {"products": products, "result": None})


@router.post("/orders/new", response_class=HTMLResponse)
def create_order_submit(
    request: Request,
    location: str = Form(...),
    delivery_date: str = Form(...),
    note: str = Form(""),
    product_id: list[int] = Form(default=[]),
    quantity: list[int] = Form(default=[]),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    items = [(pid, qty) for pid, qty in zip(product_id, quantity, strict=False) if qty > 0]

    if not items:
        result = {"success": False, "message": "Select at least one product with quantity > 0."}
    else:
        total = 0.0
        resolved = []
        for pid, qty in items:
            product = session.get(Product, pid)
            if product is None:
                continue
            resolved.append((product, qty))
            total += product.price * qty

        order = Order(
            order_id=str(uuid.uuid4()),
            location=location,
            delivery_date=date.fromisoformat(delivery_date),
            order_timestamp=datetime.now(UTC),
            note=note,
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
        result = {"success": True, "message": f"Order placed (total: {total:.2f})."}

    products = session.exec(select(Product)).all()
    return templates.TemplateResponse(request, "order_form.html", {"products": products, "result": result})
