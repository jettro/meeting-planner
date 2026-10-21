"""Unit tests for the product matching helper."""

from nomnom_service.models import Category, Product, find_best_matching_product


def make_products() -> list[Product]:
    return [
        Product(id=1, name="Burger", description="", price=15.0, category=Category.DINER),
        Product(id=2, name="Soda", description="", price=2.5, category=Category.DRINKS),
        Product(id=3, name="Sandwich", description="", price=5.0, category=Category.LUNCH),
    ]


def test_exact_match():
    products = make_products()
    match = find_best_matching_product(products, "Soda")
    assert match is not None
    assert match.name == "Soda"


def test_case_insensitive_match():
    products = make_products()
    match = find_best_matching_product(products, "burger")
    assert match is not None
    assert match.name == "Burger"


def test_substring_match():
    products = make_products()
    match = find_best_matching_product(products, "sandwiches please")
    assert match is not None
    assert match.name == "Sandwich"


def test_no_match_returns_none():
    products = make_products()
    assert find_best_matching_product(products, "Pizza") is None
