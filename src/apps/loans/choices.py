from django.db import models


class LoanStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING_INVITE = "pending_invite", "Pending Invite"
    PENDING_REVIEW = "pending_review", "Pending Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    DISBURSED = "disbursed", "Disbursed"
    ACTIVE = "active", "Active"
    CLOSED = "closed", "Closed"
    CANCELLED = "cancelled", "Cancelled"
