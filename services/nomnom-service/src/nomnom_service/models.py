"""Domain and persistence models for the NomNom food & drinks ordering service."""

from collections.abc import Sequence
from datetime import date, datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class Category(str, Enum):
    SNACKS = "SNACKS"
    DRINKS = "DRINKS"
    DINER = "DINER"
    LUNCH = "LUNCH"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    price: float
    category: Category


class Order(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    order_id: str = Field(index=True, unique=True)
    location: str
    delivery_date: date
    order_timestamp: datetime
    note: str = ""
    status: OrderStatus = OrderStatus.PENDING
    total_amount: float = 0.0


class OrderItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id")
    product_id: int = Field(foreign_key="product.id")
    product_name: str
    quantity: int
    unit_price: float

    @property
    def total_price(self) -> float:
        return self.quantity * self.unit_price


def find_best_matching_product(products: Sequence[Product], query: str) -> Product | None:
    """Very simple best-match: case-insensitive exact match first, then substring match.

    This replaces the old vector-store similarity search; no embeddings/LLM in this
    phase, kept deliberately simple.
    """
    query_lower = query.strip().lower()
    for product in products:
        if product.name.lower() == query_lower:
            return product
    for product in products:
        if query_lower in product.name.lower() or product.name.lower() in query_lower:
            return product
    return None
