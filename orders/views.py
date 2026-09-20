from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.serializers import CreateOrderSerializer, OrderOutputSerializer
from orders.services import PromoValidationError, create_order


class OrderCreateView(APIView):
    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        User = get_user_model()
        user = User.objects.get(pk=serializer.validated_data["user_id"])
        promo_code = serializer.validated_data.get("promo_code") or None

        try:
            order = create_order(
                user=user,
                goods=serializer.validated_data["goods"],
                promo_code=promo_code,
            )
        except PromoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            OrderOutputSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )
