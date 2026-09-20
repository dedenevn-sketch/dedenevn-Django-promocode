from django.contrib.auth import get_user_model
from rest_framework import serializers

from orders.models import Good, Order, OrderItem


class OrderItemInputSerializer(serializers.Serializer):
    good_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class CreateOrderSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    goods = OrderItemInputSerializer(many=True, allow_empty=False)
    promo_code = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    def validate_user_id(self, value):
        User = get_user_model()
        if not User.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Invalid user_id.")
        return value

    def validate_goods(self, value):
        good_ids = [item["good_id"] for item in value]
        found = set(
            Good.objects.filter(pk__in=good_ids).values_list("pk", flat=True)
        )
        missing = set(good_ids) - found
        if missing:
            raise serializers.ValidationError("Invalid good_id.")
        return value


class OrderItemOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("good_id", "quantity", "price", "discount", "total")


class OrderOutputSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(read_only=True)
    order_id = serializers.IntegerField(source="id", read_only=True)
    goods = OrderItemOutputSerializer(source="items", many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "user_id",
            "order_id",
            "goods",
            "price",
            "discount",
            "total",
        )
