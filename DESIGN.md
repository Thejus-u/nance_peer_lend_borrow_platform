# DESIGN

<p align="center">
  <img src="images(workflow)/aws_workflow.png" width="900">
</p>

<p align="center">
<b>Figure 1. AWS Production Architecture</b>
</p>

## Architecture Summary

The system is organized by Django apps with service-layer orchestration:

- accounts: registration, login/JWT, Gmail OAuth, Gmail sync metadata.
- loans: loan lifecycle, repayments, status events, WebSocket broadcasts.
- payments: bank transactions, Gmail transaction parsing, discovered accounts, reconciliation.
- family: family links and ledger aggregation.
- notifications: notification persistence, dedupe, dispatch workflow.
- audit: append-only state-change records.

## Core Sequence: Lend -> Accept -> Repay -> Settle
<p align="center">
  <img src="images(workflow)/Idempotency Key Payment.svg" width="900">
</p>

<p align="center">
<b>Figure 1. Core Sequence Lend -> Accept -> Repay -> Settle</b>
</p>


## Core Sequence: Gmail Sync -> Parse -> Discover Account

<p align="center">
  <img src="images(workflow)/Gmail Ingestion Service.svg" width="900">
</p>

<p align="center">
<b>Core Sequence: Gmail Sync -> Parse -> Discover Account</b>
</p>

# Data Model Diagram

The following ER diagram is validated directly against Django model source code in:
- apps/accounts/models.py
- apps/loans/models.py
- apps/family/models.py
- apps/payments/models.py
- apps/notifications/models.py
- apps/audit/models.py
- apps/integrations/models.py

<p align="center">
  <img src="images(workflow)\Gmail Account Integration-2026-07-08-202401.svg" width="900">
</p>

<p align="center">
<b>ER diagram </b>
</p>

### Validation Notes 

2. Added all implemented Django models (15 entities):
- User -> apps.accounts.models.User
- AccountsGmailAccount -> apps.accounts.models.GmailAccount
- GmailSyncedEmail -> apps.accounts.models.GmailSyncedEmail
- IntegrationsGmailAccount -> apps.integrations.models.GmailAccount
- DiscoveredEmail -> apps.integrations.models.DiscoveredEmail
- Loan -> apps.loans.models.Loan
- Repayment -> apps.loans.models.Repayment
- BankTransaction -> apps.payments.models.BankTransaction
- DiscoveredAccount -> apps.payments.models.DiscoveredAccount
- Family -> apps.family.models.Family
- FamilyMember -> apps.family.models.FamilyMember
- FamilyInvitation -> apps.family.models.FamilyInvitation
- FamilyLedgerEntry -> apps.family.models.FamilyLedgerEntry
- Notification -> apps.notifications.models.Notification
- AuditEvent -> apps.audit.models.AuditEvent

3. Added every ForeignKey relationship and labeled each with its related_name/source field:
- AccountsGmailAccount.user -> User
- GmailSyncedEmail.gmail_account -> AccountsGmailAccount
- IntegrationsGmailAccount.user -> User
- DiscoveredEmail.gmail_account -> IntegrationsGmailAccount
- Loan.borrower -> User
- Loan.lender (nullable) -> User
- Repayment.loan -> Loan
- Repayment.matched_transaction (nullable) -> BankTransaction
- BankTransaction.user -> User
- DiscoveredAccount.user -> User
- Family.owner -> User
- FamilyMember.family -> Family
- FamilyMember.user -> User
- FamilyInvitation.family -> Family
- FamilyInvitation.invited_user -> User
- FamilyInvitation.invited_by -> User
- FamilyLedgerEntry.family -> Family
- FamilyLedgerEntry.actor -> User
- FamilyLedgerEntry.member (nullable) -> User
- Notification.user -> User
- AuditEvent.actor (nullable) -> User

4. Explicitly represented nullable FK cardinalities where implemented:
- Loan.lender
- Repayment.matched_transaction
- FamilyLedgerEntry.member
- AuditEvent.actor

5. Included implementation-critical fields per entity:
- primary keys and FK columns
- status fields (Loan.status, Repayment.status, Notification.status, FamilyInvitation.status, DiscoveredAccount.status)
- timestamps (created_at/updated_at and lifecycle timestamps)
- unique identifiers and uniqueness-relevant fields (User.mobile_number, Loan.public_id, Gmail addresses/Google IDs)

6. Removed ambiguity from duplicate class names.
Why: both apps.accounts.models and apps.integrations.models define GmailAccount. The ERD uses AccountsGmailAccount and IntegrationsGmailAccount to keep app-level identity explicit while preserving one-to-one mapping to source classes.

7. Verified relationship types across all apps:
- ForeignKey count: complete and represented
- OneToOneField: none in project models
- ManyToManyField: none in project models

8. Corrected narrative risk in the previous overview by grounding model states in implementation fields rather than inferred lifecycle assumptions.

## Security and Permission Model

- API authentication uses JWT bearer tokens.
- Most endpoints require active authenticated users.
- Loan detail is restricted to lender/borrower participant or staff.
- Loan accept/reject restricted to borrower.
- Loan cancel restricted to lender.
- WebSocket connection requires authenticated active user.
- User-level WebSocket groups isolate events per user.

## WebSocket Event Contract

Endpoint: `/ws/loans/`

Server push envelope for domain events:

```json
{
  "type": "loan_event",
  "event": "loan.accepted",
  "loan": {"id": 123, "status": "active"},
  "actor_user_id": 99,
  "timestamp": "2026-07-07T12:00:00Z"
}
```

Connection ack includes reconnect strategy metadata:

```json
{
  "type": "connection_ack",
  "data": {
    "heartbeat_interval_seconds": 30,
    "reconnect": {
      "enabled": true,
      "strategy": "exponential_backoff_with_jitter",
      "initial_delay_ms": 1000,
      "max_delay_ms": 30000,
      "max_attempts": 20,
      "jitter_ratio": 0.2
    }
  }
}
```

## Trade-offs and Assumptions

- Gmail parsing uses rule-based parser classes and fixtures (not ML classification).
- Bank sender validation relies on configurable sender-domain whitelist.
- Reconciliation only considers linked savings/current accounts and may require manual review when no match is found.
- Loan status `closed` is used as settled state in persisted data.
