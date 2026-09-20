from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from orders.models import Good, Order, OrderItem, PromoCode, PromoCodeUsage

ZERO = Decimal("0")
MONEY = Decimal("0.01")


class PromoValidationError(Exception):
    """Raised when a submitted promo code cannot be applied."""


def _line_discount_rate(promo, good):
    if promo is None:
        return ZERO
    if good.is_excluded_from_promotions:
        return ZERO
    if promo.category_id is not None and good.category_id != promo.category_id:
        return ZERO
    return promo.discount


def _reraise_promo_integrity_error(exc):
    message = str(exc).lower()
    if "max uses" in message or "promo_use_count_lte_max_uses" in message:
        raise PromoValidationError("Promo code max uses reached") from exc
    raise PromoValidationError("Promo code already used by user") from exc


def validate_promo(code, user):
    if not code:
        return None

    try:
        promo = PromoCode.objects.get(code=code)
    except PromoCode.DoesNotExist as exc:
        raise PromoValidationError("Promo code does not exist") from exc

    if promo.expiration <= timezone.now():
        raise PromoValidationError("Promo code expired")

    if promo.use_count >= promo.max_uses:
        raise PromoValidationError("Promo code max uses reached")

    already_used = PromoCodeUsage.objects.filter(
        promo_code=promo,
        user=user,
    ).exists()
    if already_used:
        raise PromoValidationError("Promo code already used by user")

    return promo


def compute_line(good, quantity, promo):
    unit_price = good.price
    rate = _line_discount_rate(promo, good)
    pre_discount = (unit_price * quantity).quantize(MONEY)
    total = (pre_discount * (1 - rate)).quantize(MONEY)
    return {
        "good": good,
        "quantity": quantity,
        "price": unit_price,
        "discount": rate,
        "total": total,
        "pre_discount": pre_discount,
    }


@transaction.atomic
def create_order(*, user, goods, promo_code=None):
    """Create an order, applying a promo when one is supplied and valid."""
    promo = validate_promo(promo_code, user)

    good_ids = [item["good_id"] for item in goods]
    goods_by_id = Good.objects.in_bulk(good_ids)
    lines = [
        compute_line(goods_by_id[item["good_id"]], item["quantity"], promo)
        for item in goods
    ]

    order_price = sum((line["pre_discount"] for line in lines), ZERO).quantize(MONEY)
    order_total = sum((line["total"] for line in lines), ZERO).quantize(MONEY)
    order_discount = promo.discount if promo is not None else ZERO

    order = Order.objects.create(
        user=user,
        promo_code=promo,
        price=order_price,
        discount=order_discount,
        total=order_total,
    )
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                good=line["good"],
                quantity=line["quantity"],
                price=line["price"],
                discount=line["discount"],
                total=line["total"],
            )
            for line in lines
        ]
    )
    if promo is not None:
        try:
            with transaction.atomic():
                PromoCodeUsage.objects.create(
                    user=user,
                    promo_code=promo,
                    order=order,
                )
        except IntegrityError as exc:
            _reraise_promo_integrity_error(exc)
    return order
