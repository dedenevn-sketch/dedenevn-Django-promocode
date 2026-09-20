"""Contract tests for POST /api/orders/.

These tests encode promo rules and the success payload shape. They are
expected to fail until models, discount logic, and the endpoint exist.
"""

from decimal import Decimal

from tests.conftest import ORDERS_URL


def as_decimal(value):
    return Decimal(str(value))


def line_for(goods, good_id):
    matches = [item for item in goods if item["good_id"] == good_id]
    assert len(matches) == 1, f"expected one line for good_id={good_id}, got {goods}"
    return matches[0]


def test_create_order_success_without_promo(api_client, user, good_clothing):
    payload = {
        "user_id": user.id,
        "goods": [{"good_id": good_clothing.id, "quantity": 2}],
    }

    response = api_client.post(ORDERS_URL, payload, format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == user.id
    assert body["order_id"]
    line = line_for(body["goods"], good_clothing.id)
    assert line["quantity"] == 2
    assert as_decimal(line["price"]) == Decimal("100")
    assert as_decimal(line["discount"]) == Decimal("0")
    assert as_decimal(line["total"]) == Decimal("200")
    assert as_decimal(body["price"]) == Decimal("200")
    assert as_decimal(body["discount"]) == Decimal("0")
    assert as_decimal(body["total"]) == Decimal("200")


def test_create_order_success_with_valid_promo(
    api_client, user, good_clothing, promo_valid
):
    payload = {
        "user_id": user.id,
        "goods": [{"good_id": good_clothing.id, "quantity": 2}],
        "promo_code": promo_valid.code,
    }

    response = api_client.post(ORDERS_URL, payload, format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == user.id
    assert body["order_id"]
    line = line_for(body["goods"], good_clothing.id)
    assert line["quantity"] == 2
    assert as_decimal(line["price"]) == Decimal("100")
    assert as_decimal(line["discount"]) == Decimal("0.1")
    assert as_decimal(line["total"]) == Decimal("180")
    assert as_decimal(body["price"]) == Decimal("200")
    assert as_decimal(body["discount"]) == Decimal("0.1")
    assert as_decimal(body["total"]) == Decimal("180")


def test_promo_code_does_not_exist(api_client, user, good_clothing):
    payload = {
        "user_id": user.id,
        "goods": [{"good_id": good_clothing.id, "quantity": 1}],
        "promo_code": "NO_SUCH_CODE",
    }

    response = api_client.post(ORDERS_URL, payload, format="json")

    assert response.status_code == 400


def test_promo_code_expired(api_client, user, good_clothing, promo_expired):
    payload = {
        "user_id": user.id,
        "goods": [{"good_id": good_clothing.id, "quantity": 1}],
        "promo_code": promo_expired.code,
    }

    response = api_client.post(ORDERS_URL, payload, format="json")

    assert response.status_code == 400


def test_promo_code_max_uses_reached(
    api_client, user, good_clothing, promo_max_uses_reached
):
    payload = {
        "user_id": user.id,
        "goods": [{"good_id": good_clothing.id, "quantity": 1}],
        "promo_code": promo_max_uses_reached.code,
    }

    response = api_client.post(ORDERS_URL, payload, format="json")

    assert response.status_code == 400


def test_promo_code_already_used_by_user(
    api_client, user, good_clothing, promo_already_used_by_user
):
    payload = {
        "user_id": user.id,
        "goods": [{"good_id": good_clothing.id, "quantity": 1}],
        "promo_code": promo_already_used_by_user.code,
    }

    response = api_client.post(ORDERS_URL, payload, format="json")

    assert response.status_code == 400


def test_promo_code_category_restriction(
    api_client,
    user,
    good_clothing,
    good_electronics,
    promo_category_restricted,
):
    payload = {
        "user_id": user.id,
        "goods": [
            {"good_id": good_clothing.id, "quantity": 1},
            {"good_id": good_electronics.id, "quantity": 1},
        ],
        "promo_code": promo_category_restricted.code,
    }

    response = api_client.post(ORDERS_URL, payload, format="json")

    assert response.status_code == 201
    body = response.json()
    clothing = line_for(body["goods"], good_clothing.id)
    electronics = line_for(body["goods"], good_electronics.id)
    assert as_decimal(clothing["price"]) == Decimal("100")
    assert as_decimal(clothing["discount"]) == Decimal("0.1")
    assert as_decimal(clothing["total"]) == Decimal("90")
    assert as_decimal(electronics["price"]) == Decimal("200")
    assert as_decimal(electronics["discount"]) == Decimal("0")
    assert as_decimal(electronics["total"]) == Decimal("200")
    assert as_decimal(body["price"]) == Decimal("300")
    assert as_decimal(body["total"]) == Decimal("290")


def test_promo_code_excluded_goods(
    api_client, user, good_clothing, good_excluded, promo_valid
):
    payload = {
        "user_id": user.id,
        "goods": [
            {"good_id": good_clothing.id, "quantity": 1},
            {"good_id": good_excluded.id, "quantity": 1},
        ],
        "promo_code": promo_valid.code,
    }

    response = api_client.post(ORDERS_URL, payload, format="json")

    assert response.status_code == 201
    body = response.json()
    eligible = line_for(body["goods"], good_clothing.id)
    excluded = line_for(body["goods"], good_excluded.id)
    assert as_decimal(eligible["price"]) == Decimal("100")
    assert as_decimal(eligible["discount"]) == Decimal("0.1")
    assert as_decimal(eligible["total"]) == Decimal("90")
    assert as_decimal(excluded["price"]) == Decimal("150")
    assert as_decimal(excluded["discount"]) == Decimal("0")
    assert as_decimal(excluded["total"]) == Decimal("150")
    assert as_decimal(body["price"]) == Decimal("250")
    assert as_decimal(body["total"]) == Decimal("240")


def test_invalid_user_or_goods(api_client, user, good_clothing):
    missing_user = api_client.post(
        ORDERS_URL,
        {"goods": [{"good_id": good_clothing.id, "quantity": 1}]},
        format="json",
    )
    assert missing_user.status_code == 400

    unknown_user = api_client.post(
        ORDERS_URL,
        {
            "user_id": user.id + 9999,
            "goods": [{"good_id": good_clothing.id, "quantity": 1}],
        },
        format="json",
    )
    assert unknown_user.status_code == 400

    missing_good_id = api_client.post(
        ORDERS_URL,
        {"user_id": user.id, "goods": [{"quantity": 1}]},
        format="json",
    )
    assert missing_good_id.status_code == 400

    unknown_good = api_client.post(
        ORDERS_URL,
        {
            "user_id": user.id,
            "goods": [{"good_id": good_clothing.id + 9999, "quantity": 1}],
        },
        format="json",
    )
    assert unknown_good.status_code == 400


def test_promo_usage_unique_integrity_error_is_400(
    api_client, user, good_clothing, promo_valid, monkeypatch
):
    """Race: unique constraint IntegrityError must be 400, not 500."""
    from orders.models import PromoCodeUsage
    from orders import services

    PromoCodeUsage.objects.create(user=user, promo_code=promo_valid)
    monkeypatch.setattr(services, "validate_promo", lambda code, user: promo_valid)

    response = api_client.post(
        ORDERS_URL,
        {
            "user_id": user.id,
            "goods": [{"good_id": good_clothing.id, "quantity": 1}],
            "promo_code": promo_valid.code,
        },
        format="json",
    )
    assert response.status_code == 400
