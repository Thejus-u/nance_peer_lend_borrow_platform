from __future__ import annotations

from django.db.models import Q
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.loans.api.permissions import IsAuthenticatedAndActive, IsLoanParticipantOrStaff
from apps.loans.api.serializers import (
    LoanAcceptSerializer,
    LoanCancelSerializer,
    LoanCreateSerializer,
    LoanRejectSerializer,
    LoanSerializer,
    RepaymentCreateSerializer,
    RepaymentPaySerializer,
    RepaymentSerializer,
)
from apps.loans.choices import LoanStatus
from apps.loans.models import Loan


class LoanCreateAPIView(generics.CreateAPIView):
    serializer_class = LoanCreateSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        loan = serializer.save()
        output = LoanSerializer(loan)
        return Response(output.data, status=status.HTTP_201_CREATED)


class LoanListAPIView(generics.ListAPIView):
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        user = self.request.user
        return Loan.objects.select_related("borrower", "lender").filter(
            Q(borrower_id=user.id) | Q(lender_id=user.id)
        )


class LoanDetailAPIView(generics.RetrieveAPIView):
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticatedAndActive, IsLoanParticipantOrStaff]
    queryset = Loan.objects.select_related("borrower", "lender")


class LoanAcceptAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, loan_id: int, *args, **kwargs) -> Response:
        serializer = LoanAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        loan = serializer.save(loan_id=loan_id, borrower_id=request.user.id)
        return Response(LoanSerializer(loan).data, status=status.HTTP_200_OK)


class LoanRejectAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, loan_id: int, *args, **kwargs) -> Response:
        serializer = LoanRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        loan = serializer.save(loan_id=loan_id, borrower_id=request.user.id)
        return Response(LoanSerializer(loan).data, status=status.HTTP_200_OK)


class LoanCancelAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, loan_id: int, *args, **kwargs) -> Response:
        serializer = LoanCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        loan = serializer.save(loan_id=loan_id, requested_by_user_id=request.user.id)
        return Response(LoanSerializer(loan).data, status=status.HTTP_200_OK)


class RepaymentCreateAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, loan_id: int, *args, **kwargs) -> Response:
        serializer = RepaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repayment = serializer.save(loan_id=loan_id)
        response_status = status.HTTP_201_CREATED if getattr(repayment, "_created", True) else status.HTTP_200_OK
        return Response(RepaymentSerializer(repayment).data, status=response_status)


class RepaymentPayAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, repayment_id: int, *args, **kwargs) -> Response:
        serializer = RepaymentPaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repayment = serializer.save(repayment_id=repayment_id)
        return Response(RepaymentSerializer(repayment).data, status=status.HTTP_200_OK)


class IncomingLoanRequestListAPIView(generics.ListAPIView):
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        return Loan.objects.select_related("borrower", "lender").filter(
            borrower_id=self.request.user.id,
            status__in=[LoanStatus.PENDING_REVIEW, LoanStatus.PENDING_INVITE],
        )


class LoansLentListAPIView(generics.ListAPIView):
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        return Loan.objects.select_related("borrower", "lender").filter(lender_id=self.request.user.id)


class LoansBorrowedListAPIView(generics.ListAPIView):
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        return Loan.objects.select_related("borrower", "lender").filter(borrower_id=self.request.user.id)


class ActiveLoansListAPIView(generics.ListAPIView):
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        return Loan.objects.select_related("borrower", "lender").filter(
            (Q(borrower_id=self.request.user.id) | Q(lender_id=self.request.user.id)),
            status=LoanStatus.ACTIVE,
        )


class SettledLoansListAPIView(generics.ListAPIView):
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        return Loan.objects.select_related("borrower", "lender").filter(
            (Q(borrower_id=self.request.user.id) | Q(lender_id=self.request.user.id)),
            status=LoanStatus.CLOSED,
        )
