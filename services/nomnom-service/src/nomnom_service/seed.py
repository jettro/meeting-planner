"""Seed demo data: the product catalog from the old Java project, plus a sample order."""

from datetime import UTC, date, datetime, timedelta

from sqlmodel import Session, select

from nomnom_service.models import Category, Order, OrderItem, OrderStatus, Product

PRODUCTS = [
    ("Chips", "Crispy potato chips.", 2.5, Category.SNACKS),
    ("Cookie", "A tasty cookie.", 1.0, Category.SNACKS),
    ("Soda", "Carbonated soft drink.", 2.5, Category.DRINKS),
    ("Coffee", "Keeps the engine running.", 1.5, Category.DRINKS),
    ("Tea", "A soothing hot cup of tea.", 1.5, Category.DRINKS),
    ("Juice", "Freshly squeezed juice.", 3.0, Category.DRINKS),
    ("Burger", "Juicy beef burger with cheese.", 15.0, Category.DINER),
    ("Pizza", "Freshly ordered near you.", 12.5, Category.DINER),
    ("Salad", "For the smaller appetite.", 9.5, Category.DINER),
    ("Sushi", "Fashionable food, all fresh.", 23.0, Category.DINER),
    ("Sandwich", "Have a Dutch lunch.", 5.0, Category.LUNCH),
    ("Wrap", "A hip lunch bite.", 5.5, Category.LUNCH),
    ("Soup", "For those colder days.", 3.5, Category.LUNCH),
]


def seed(session: Session) -> None:
    existing = session.exec(select(Product)).first()
    if existing is not None:
        return

    products: list[Product] = []
    for name, description, price, category in PRODUCTS:
        product = Product(name=name, description=description, price=price, category=category)
        session.add(product)
        products.append(product)
    session.commit()

    for product in products:
        session.refresh(product)

    burger = next(p for p in products if p.name == "Burger")
    soda = next(p for p in products if p.name == "Soda")

    order = Order(
        order_id="seed-order-1",
        location="yuma",
        delivery_date=date.today() + timedelta(days=1),
        order_timestamp=datetime.now(UTC),
        note="Seeded demo order",
        status=OrderStatus.CONFIRMED,
        total_amount=burger.price * 2 + soda.price * 3,
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    session.add_all(
        [
            OrderItem(
                order_id=order.id,  # type: ignore[arg-type]
                product_id=burger.id,  # type: ignore[arg-type]
                product_name=burger.name,
                quantity=2,
                unit_price=burger.price,
            ),
            OrderItem(
                order_id=order.id,  # type: ignore[arg-type]
                product_id=soda.id,  # type: ignore[arg-type]
                product_name=soda.name,
                quantity=3,
                unit_price=soda.price,
            ),
        ]
    )
    session.commit()
