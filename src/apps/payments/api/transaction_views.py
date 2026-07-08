from __future__ import annotations

from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.permissions import IsAuthenticatedAndActive
from apps.payments.api.transaction_serializers import (
    BankTransactionCreateSerializer,
    BankTransactionSerializer,
)
from apps.payments.models import BankTransaction
from apps.payments.services.transaction_service import BankTransactionService


class BankTransactionListAPIView(generics.ListAPIView):
    serializer_class = BankTransactionSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        return BankTransaction.objects.filter(user=self.request.user)


class BankTransactionCreateAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = BankTransactionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save(user_id=request.user.id)
        return Response(BankTransactionSerializer(transaction).data, status=status.HTTP_201_CREATED)


class BankTransactionSummaryAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request: Request, *args, **kwargs) -> Response:
        summary = BankTransactionService.get_user_ledger_summary(user_id=request.user.id)
        payload = {
            "total_credit": str(summary["total_credit"]),
            "total_debit": str(summary["total_debit"]),
            "net": str(summary["net"]),
            "total_count": summary["total_count"],
        }
        return Response(payload, status=status.HTTP_200_OK)
