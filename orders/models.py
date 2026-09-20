import django
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.db.models import F, Q


class Category(models.Model):
    name = models.CharField(max_length=128)

    def __str__(self):
        return self.name


class Good(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="goods",
    )
    is_excluded_from_promotions = models.BooleanField(default=False)

    def __str__(self):
        return self.name


def _promo_use_count_constraint():
    """use_count cannot exceed max_uses (Django 4.2 `check` / 5.1+ `condition`)."""
    bound = Q(use_count__lte=F("max_uses"))
    kwargs = {"name": "promo_use_count_lte_max_uses"}
    if django.VERSION >= (5, 1):
        return models.CheckConstraint(condition=bound, **kwargs)
    return models.CheckConstraint(check=bound, **kwargs)


class PromoCode(models.Model):
    code = models.CharField(max_length=64, unique=True)
    discount = models.DecimalField(max_digits=5, decimal_places=4)
    expiration = models.DateTimeField()
    max_uses = models.PositiveIntegerField()
    use_count = models.PositiveIntegerField(default=0)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="promo_codes",
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [_promo_use_count_constraint()]

    def __str__(self):
        return self.code


class Order(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.SET_NULL,
        related_name="orders",
        null=True,
        blank=True,
    )
    price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=4)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    good = models.ForeignKey(
        Good,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=4)
    total = models.DecimalField(max_digits=12, decimal_places=2)


class PromoCodeUsage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="promo_code_usages",
    )
    promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.CASCADE,
        related_name="usages",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="promo_usages",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "promo_code"],
                name="unique_user_promo_code_usage",
            )
        ]

    def save(self, *args, **kwargs):
        """Claim a max_uses slot with an atomic increment that cannot overshoot.

        `SELECT FOR UPDATE` is a no-op on SQLite (the test DB). A single
        `UPDATE ... WHERE use_count < max_uses` is serialized by SQLite's
        writer lock and is the enforcement that cannot overshoot.
        """
        with transaction.atomic():
            if self._state.adding:
                claimed = PromoCode.objects.filter(
                    pk=self.promo_code_id,
                    use_count__lt=F("max_uses"),
                ).update(use_count=F("use_count") + 1)
                if claimed == 0:
                    raise IntegrityError("promo max uses reached")
            super().save(*args, **kwargs)
