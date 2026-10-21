"""Pure Pydantic request/response schemas for the NomNom API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from nomnom_service.models import Category, OrderStatus


class ProductRead(BaseModel):
    id: int
    name: str
    description: str
    price: float
    category: Category


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int


class OrderItemRead(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    total_price: float


class OrderCreate(BaseModel):
    location: str
    delivery_date: date
    items: list[OrderItemCreate]
    note: str = ""


class OrderRead(BaseModel):
    order_id: str
    location: str
    delivery_date: date
    order_timestamp: datetime
    note: str
    status: OrderStatus
    total_amount: float
    items: list[OrderItemRead]


class OrderSummary(BaseModel):
    total_orders: int
    total_items_sold: int
    total_revenue: float
    average_order_value: float
