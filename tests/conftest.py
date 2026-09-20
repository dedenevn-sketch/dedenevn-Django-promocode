"""Fixtures for POST /api/orders/ tests.

Expected models (implemented in a later step) and fields used here:

- User — Django auth via get_user_model()
- Category(name)
- Good(name, price, is_excluded_from_promotions, category)
- PromoCode(code, discount, expiration, max_uses, category=None)
- PromoCodeUsage(user, promo_code) — one row per successful user+promo use
- Order / OrderItem — created by the endpoint, not by these fixtures
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

ORDERS_URL = "/api/orders/"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="password",
    )


@pytest.fixture
def other_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="bob",
        email="bob@example.com",
        password="password",
    )


@pytest.fixture
def category_clothing(db):
    from orders.models import Category

    return Category.objects.create(name="Clothing")


@pytest.fixture
def category_electronics(db):
    from orders.models import Category

    return Category.objects.create(name="Electronics")


@pytest.fixture
def categories(category_clothing, category_electronics):
    return {
        "clothing": category_clothing,
        "electronics": category_electronics,
    }


@pytest.fixture
def good_clothing(db, category_clothing):
    """Normal clothing item, eligible for promotions, unit price 100."""
    from orders.models import Good

    return Good.objects.create(
        name="T-shirt",
        price=Decimal("100.00"),
        category=category_clothing,
        is_excluded_from_promotions=False,
    )


@pytest.fixture
def good_electronics(db, category_electronics):
    """Normal electronics item in a different category, unit price 200."""
    from orders.models import Good

    return Good.objects.create(
        name="Headphones",
        price=Decimal("200.00"),
        category=category_electronics,
        is_excluded_from_promotions=False,
    )


@pytest.fixture
def good_excluded(db, category_clothing):
    """Clothing item that must never receive a promo discount."""
    from orders.models import Good

    return Good.objects.create(
        name="Sale rack shirt",
        price=Decimal("150.00"),
        category=category_clothing,
        is_excluded_from_promotions=True,
    )


@pytest.fixture
def goods(good_clothing, good_electronics, good_excluded):
    return {
        "clothing": good_clothing,
        "electronics": good_electronics,
        "excluded": good_excluded,
    }


@pytest.fixture
def promo_valid(db):
    """Global 10% promo: SUMMER2025, not expired, uses remaining."""
    from orders.models import PromoCode

    return PromoCode.objects.create(
        code="SUMMER2025",
        discount=Decimal("0.1"),
        expiration=timezone.now() + timedelta(days=30),
        max_uses=10,
        category=None,
    )


@pytest.fixture
def promo_expired(db):
    from orders.models import PromoCode

    return PromoCode.objects.create(
        code="EXPIRED2020",
        discount=Decimal("0.1"),
        expiration=timezone.now() - timedelta(days=1),
        max_uses=10,
        category=None,
    )


@pytest.fixture
def promo_max_uses_reached(db, other_user):
    """max_uses=1 and that use is already consumed by another user."""
    from orders.models import PromoCode, PromoCodeUsage

    promo = PromoCode.objects.create(
        code="MAXEDOUT",
        discount=Decimal("0.1"),
        expiration=timezone.now() + timedelta(days=30),
        max_uses=1,
        category=None,
    )
    PromoCodeUsage.objects.create(user=other_user, promo_code=promo)
    return promo


@pytest.fixture
def promo_category_restricted(db, category_clothing):
    """10% off, but only goods in the Clothing category."""
    from orders.models import PromoCode

    return PromoCode.objects.create(
        code="CLOTHES10",
        discount=Decimal("0.1"),
        expiration=timezone.now() + timedelta(days=30),
        max_uses=10,
        category=category_clothing,
    )


@pytest.fixture
def promo_codes(
    promo_valid,
    promo_expired,
    promo_max_uses_reached,
    promo_category_restricted,
):
    return {
        "valid": promo_valid,
        "expired": promo_expired,
        "max_uses_reached": promo_max_uses_reached,
        "category_restricted": promo_category_restricted,
    }


@pytest.fixture
def promo_already_used_by_user(db, user, promo_valid):
    """Same user already applied SUMMER2025 (must be rejected on reuse)."""
    from orders.models import PromoCodeUsage

    PromoCodeUsage.objects.create(user=user, promo_code=promo_valid)
    return promo_valid
