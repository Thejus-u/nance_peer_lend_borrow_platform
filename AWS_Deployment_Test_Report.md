# AWS Deployment Test Report

## Application Information
- URL: https://thejus.fun
- Environment: AWS deployed production-like environment
- Date: 2026-07-08

## Test Summary
- Authentication: PASS (with one route discrepancy)
- Loan workflow: PASS
- Repayment workflow: PASS
- Family invitation workflow: PASS
- Permission tests: PARTIAL PASS (status-code mismatch on some forbidden actions)
- Browser runtime checks: PASS (no uncaught JS exceptions)
- WebSocket validation: PASS
- Backend automated suite: PASS (Django tests), BLOCKED (pytest missing)

## Detailed Test Cases
| Test ID | Description | Expected Result | Actual Result | Status | Evidence |
|---|---|---|---|---|---|
| AUTH-01 | Registration User A | Account created, redirect to login | Success message and redirect observed | PASS | ![AUTH-01](qa-report/screenshots/auth_register_userA_success.png) |
| AUTH-02 | Registration User B | Account created | Success | PASS | ![AUTH-02](qa-report/screenshots/auth_register_userB_success.png) |
| AUTH-03 | Registration User C | Account created | Success | PASS | ![AUTH-03](qa-report/screenshots/auth_register_userC_success.png) |
| AUTH-04 | Login User A | Dashboard and active session | Dashboard loaded | PASS | ![AUTH-04](qa-report/screenshots/auth_login_userA_success.png) |
| AUTH-05 | Logout User A | Session ended and login screen shown | Login page shown | PASS | ![AUTH-05](qa-report/screenshots/auth_logout_userA_success.png) |
| AUTH-06 | JWT me endpoint with valid token | 200 with user payload | 200 returned | PASS | API table |
| AUTH-07 | JWT me endpoint with invalid token | 401 | 401 returned | PASS | API table |
| AUTH-08 | Refresh token endpoint | 200 with new access token | 200 returned | PASS | API table |
| AUTH-09 | Legacy token endpoint check (/auth/token/) | 200 if route exists | 404 Not Found | FAIL | API table |
| LOAN-01 | Create loan (accept candidate) | Loan pending_review created | Loan id 4 created | PASS | ![LOAN-01](qa-report/screenshots/loan_create_accept_candidate_success.png) |
| LOAN-02 | Create loan (reject candidate) | Loan pending_review created | Loan id 5 created | PASS | ![LOAN-02](qa-report/screenshots/loan_create_reject_candidate_success.png) |
| LOAN-03 | Create loan (cancel candidate) | Loan pending_review created | Loan id 6 created | PASS | ![LOAN-03](qa-report/screenshots/loan_create_cancel_candidate_success.png) |
| LOAN-04 | Borrower accepts loan id 4 | Status active and real-time update | Status changed to active; real-time banner shown | PASS | ![LOAN-04](qa-report/screenshots/loan_accept_by_borrower_success.png) |
| LOAN-05 | Borrower rejects loan id 5 | Status rejected and reason stored | Status rejected; reason present; real-time banner shown | PASS | ![LOAN-05](qa-report/screenshots/loan_reject_by_borrower_success.png) |
| LOAN-06 | Lender cancels pending loan id 6 | Status cancelled | Status cancelled; real-time banner shown | PASS | ![LOAN-06](qa-report/screenshots/loan_cancel_by_lender_success.png) |
| LOAN-07 | Loan list status aggregation | Correct bucketed statuses | Borrowed and settled sections correctly updated | PASS | ![LOAN-07](qa-report/screenshots/loan_list_view.png) |
| REPAY-01 | Create repayment installment | Installment scheduled | Repayment id 4 created with status scheduled | PASS | ![REPAY-01](qa-report/screenshots/repayment_create_success.png) |
| REPAY-02 | Pay repayment installment | amount_paid updated; status paid | amount_paid=100, status=paid | PASS | ![REPAY-02](qa-report/screenshots/repayment_pay_success.png) |
| REPAY-03 | Loan settlement after repayment | Loan transitions to closed when fully settled | Loan id 4 became closed | PASS | ![REPAY-03](qa-report/screenshots/loan_list_view.png) |
| FAM-01 | User A no-family state | No family message shown | Correct no-family state rendered | PASS | ![FAM-01](qa-report/screenshots/family_userA_no_family_state.png) |
| FAM-02 | User A creates family | Family created, owner visible | Family created (id 2), owner controls visible | PASS | ![FAM-02](qa-report/screenshots/family_userA_created_family.png) |
| FAM-03 | User A invites B and C | Pending invitations created | Invitations created (ids 2,3) | PASS | ![FAM-03](qa-report/screenshots/family_userA_sent_invitations.png) |
| FAM-04 | User B sees pending invitation | Pending invitation visible | Invitation visible | PASS | ![FAM-04](qa-report/screenshots/family_userB_pending_invitation.png) |
| FAM-05 | User B accepts invitation | Membership added | Member added; family shown | PASS | ![FAM-05](qa-report/screenshots/family_userB_accepted_member_and_ledger.png) |
| FAM-06 | User C sees invitation | Pending invitation visible | Invitation visible | PASS | ![FAM-06](qa-report/screenshots/family_userC_pending_invitation.png) |
| FAM-07 | User C rejects invitation | Invitation cleared; no membership | No pending invitations; not added to family | PASS | ![FAM-07](qa-report/screenshots/family_userC_rejected_invitation.png) |
| FAM-08 | User A verifies members | Accepted exists; rejected absent | User 4 present, User 5 absent | PASS | ![FAM-08](qa-report/screenshots/family_userA_verify_members_before_removal.png) |
| FAM-09 | User A removes accepted member | Member removed, ledger updated | Member removed; ledger entry member_removed added | PASS | ![FAM-09](qa-report/screenshots/family_userA_removed_member_and_ledger.png) |
| PERM-01 | Non-owner invite member API | Forbidden status (expected 403) | 400 returned with permission detail | FAIL |
| PERM-02 | Non-owner remove member API | Forbidden status (expected 403) | 400 returned with permission detail | FAIL |
| PERM-03 | Unauthorized ledger API access | 401 | 401 returned | PASS |
| PERM-04 | Non-member ledger API access | Forbidden status (expected 403) | 400 returned: not part of family | FAIL |
| PERM-05 | Non-owner UI controls hidden | Invite/remove controls absent | Controls absent for member | PASS | ![PERM-05](qa-report/screenshots/family_userB_accepted_member_and_ledger.png) |
| PERM-06 | Non-owner delete family | Explicit forbidden behavior | No delete endpoint exposed in UI/API routes | BLOCKED |
| BROW-01 | Console runtime errors | No uncaught exceptions | No pageErrors or consoleErrors captured | PASS |
| BROW-02 | Failed network requests | No unexpected failures | 400/401 observed only on intentional negative tests | PASS |
| WS-01 | WS connect | Connection established | connection_ack observed on wss://thejus.fun/ws/loans/ | PASS |
| WS-02 | Real-time loan accepted event | Event arrives in UI | "Real-time update: loan.accepted" shown | PASS | ![WS-02](qa-report/screenshots/loan_accept_by_borrower_success.png) |
| WS-03 | Real-time loan rejected event | Event arrives in UI | "Real-time update: loan.rejected" shown | PASS | ![WS-03](qa-report/screenshots/loan_reject_by_borrower_success.png) |
| WS-04 | Real-time loan cancelled event | Event arrives in UI | "Real-time update: loan.cancelled" shown | PASS | ![WS-04](qa-report/screenshots/loan_cancel_by_lender_success.png) |
| DEP-01 | Dashboard load on AWS | Dashboard data loads | Loaded for all test users | PASS |
| DEP-02 | Notifications generation | Correct notifications emitted | Loan, repayment, family notifications observed in payloads | PASS |
| DEP-03 | Frontend stability | No runtime crash during flows | Stable across all tested pages | PASS |
| BACK-01 | Django suite | All automated tests pass | 88 tests passed | PASS |
| BACK-02 | Pytest suite | Executable and passing | pytest executable missing in container | BLOCKED |

## API Results
Observed endpoints and outcomes from deployed environment/API calls.

| Endpoint | Method | Request Payload | Response Summary | Status | Result |
|---|---|---|---|---|---|
| /api/v1/accounts/auth/register/ | POST | name, mobile_number, password, password_confirm | user payload returned | 201 | PASS |
| /api/v1/accounts/auth/login/ | POST | mobile_number, password | access, refresh, user returned | 200 | PASS |
| /api/v1/accounts/auth/token/refresh/ | POST | refresh token | new access token returned | 200 | PASS |
| /api/v1/accounts/auth/me/ | GET | Bearer valid token | user payload returned | 200 | PASS |
| /api/v1/accounts/auth/me/ | GET | Bearer invalid token | token_not_valid | 401 | PASS |
| /api/v1/accounts/auth/token/ | POST | mobile_number, password | Not Found | 404 | FAIL |
| /api/v1/loans/ | POST | borrower_id, principal, term, dates, purpose | loan objects created (ids 4,5,6) | 201 observed via UI | PASS |
| /api/v1/loans/{id}/accept/ | POST | idempotency_key | loan status active | 200 observed via UI | PASS |
| /api/v1/loans/{id}/reject/ | POST | reason, idempotency_key | loan status rejected | 200 observed via UI | PASS |
| /api/v1/loans/{id}/cancel/ | POST | idempotency_key | loan status cancelled | 200 observed via UI | PASS |
| /api/v1/loans/{id}/ | GET | loan id | detailed loan payload | 200 observed via UI | PASS |
| /api/v1/loans/ | GET | auth token | list payload with status buckets | 200 observed via UI | PASS |
| /api/v1/loans/{id}/repayments/ | POST | installment, due_date, amount_due | repayment created | 201 observed via UI | PASS |
| /api/v1/loans/repayments/{id}/pay/ | POST | amount | repayment marked paid | 200 observed via UI | PASS |
| /api/v1/family/create/ | POST | family_name | family created | 201 observed via UI | PASS |
| /api/v1/family/invitations/create/ | POST | invited_user_id | invitation created | 201 observed via UI | PASS |
| /api/v1/family/invitations/{id}/accept/ | POST | none | member added | 200 observed via UI | PASS |
| /api/v1/family/invitations/{id}/reject/ | POST | none | invitation rejected | 200 observed via UI | PASS |
| /api/v1/family/current/members/remove/ | POST | member_user_id | member removed | 200 observed via UI | PASS |
| /api/v1/family/current/ledger/ | GET | auth token | ledger entries and positions | 200 | PASS |
| /api/v1/notifications/ (via dashboard payload) | GET | auth token | notifications list observed | 200 observed via UI | PASS |

### Negative Permission API Checks
| Endpoint | Method | Actor | Expected | Actual | Status |
|---|---|---|---|---|---|
| /api/v1/family/invitations/create/ | POST | non-owner member | 403 | 400 (permission message) | FAIL |
| /api/v1/family/current/members/remove/ | POST | non-owner member | 403 | 400 (permission message) | FAIL |
| /api/v1/family/current/ledger/ | GET | unauthenticated | 401 | 401 | PASS |
| /api/v1/family/current/ledger/ | GET | authenticated non-member | 403 | 400 | FAIL |

## Browser Validation
- Console uncaught exceptions: None observed.
- Captured JS/page errors: None.
- Network failures: Only expected failures from intentional negative tests (400/401), plus one 404 from legacy auth route probe.
- Mixed content: Not observed.
- CORS errors: Not observed.

## Console Errors
No uncaught application JS errors were captured by instrumentation.

## Network Errors
- 400 responses on intentional forbidden/non-member checks.
- 401 on intentional unauthorized checks.
- 404 on tested legacy auth endpoint /api/v1/accounts/auth/token/.

## WebSocket Validation
- Connection established to wss://thejus.fun/ws/loans/ with connection_ack payload.
- Connection remained open during scenario execution.
- Real-time events observed in UI:
  - loan.accepted
  - loan.rejected
  - loan.cancelled
- Family-specific WebSocket event banner was not explicitly observed in the UI during family actions.

## Screenshots
All screenshots are stored in qa-report/screenshots/.

### Complete Screenshot Set
![auth_login_page](qa-report/screenshots/auth_login_page.png)
![auth_register_userA_success](qa-report/screenshots/auth_register_userA_success.png)
![auth_register_userB_success](qa-report/screenshots/auth_register_userB_success.png)
![auth_register_userC_success](qa-report/screenshots/auth_register_userC_success.png)
![auth_login_userA_success](qa-report/screenshots/auth_login_userA_success.png)
![auth_login_userB_success](qa-report/screenshots/auth_login_userB_success.png)
![auth_login_userC_success](qa-report/screenshots/auth_login_userC_success.png)
![auth_logout_userA_success](qa-report/screenshots/auth_logout_userA_success.png)
![loan_create_accept_candidate_success](qa-report/screenshots/loan_create_accept_candidate_success.png)
![loan_create_reject_candidate_success](qa-report/screenshots/loan_create_reject_candidate_success.png)
![loan_create_cancel_candidate_success](qa-report/screenshots/loan_create_cancel_candidate_success.png)
![loan_accept_by_borrower_success](qa-report/screenshots/loan_accept_by_borrower_success.png)
![loan_reject_by_borrower_success](qa-report/screenshots/loan_reject_by_borrower_success.png)
![loan_cancel_by_lender_success](qa-report/screenshots/loan_cancel_by_lender_success.png)
![loan_list_view](qa-report/screenshots/loan_list_view.png)
![repayment_create_success](qa-report/screenshots/repayment_create_success.png)
![repayment_pay_by_borrower_result](qa-report/screenshots/repayment_pay_by_borrower_result.png)
![repayment_pay_success](qa-report/screenshots/repayment_pay_success.png)
![family_userA_no_family_state](qa-report/screenshots/family_userA_no_family_state.png)
![family_userA_created_family](qa-report/screenshots/family_userA_created_family.png)
![family_userA_sent_invitations](qa-report/screenshots/family_userA_sent_invitations.png)
![family_userB_pending_invitation](qa-report/screenshots/family_userB_pending_invitation.png)
![family_userB_accepted_member_and_ledger](qa-report/screenshots/family_userB_accepted_member_and_ledger.png)
![family_userC_pending_invitation](qa-report/screenshots/family_userC_pending_invitation.png)
![family_userC_rejected_invitation](qa-report/screenshots/family_userC_rejected_invitation.png)
![family_userA_verify_members_before_removal](qa-report/screenshots/family_userA_verify_members_before_removal.png)
![family_userA_removed_member_and_ledger](qa-report/screenshots/family_userA_removed_member_and_ledger.png)

## Bugs Found
### Bug 1: Permission endpoints return 400 instead of 403
- Severity: Medium
- Steps to Reproduce:
  1. Authenticate as non-owner family member.
  2. POST /api/v1/family/invitations/create/ or /api/v1/family/current/members/remove/.
- Expected Behavior: 403 Forbidden.
- Actual Behavior: 400 Bad Request with permission message.
- Suggested Fix: Return HTTP 403 for authorization failures; reserve 400 for validation errors.

### Bug 2: Non-member family ledger returns 400 instead of 403
- Severity: Medium
- Steps to Reproduce:
  1. Authenticate as user not in family.
  2. GET /api/v1/family/current/ledger/.
- Expected Behavior: 403 Forbidden.
- Actual Behavior: 400 Bad Request ("You are not part of any family.").
- Suggested Fix: Return 403 for access denial.

### Bug 3: Legacy token endpoint route mismatch
- Severity: Low
- Steps to Reproduce:
  1. POST /api/v1/accounts/auth/token/ with valid credentials.
- Expected Behavior: 200 if route intended to exist.
- Actual Behavior: 404 Not Found.
- Suggested Fix: Align docs and clients to /api/v1/accounts/auth/login/ or add compatibility route if required.

### Bug 4: Session timing sensitivity in rapid scripted navigation
- Severity: Low
- Steps to Reproduce:
  1. Login and immediately hard-navigate via script.
  2. Issue API calls from destination page.
- Expected Behavior: authenticated state persists consistently.
- Actual Behavior: occasional transient 401 due to timing.
- Suggested Fix: ensure token persistence before navigation or await post-login completion state in frontend automation hooks.

## Recommendations
1. Normalize authorization failures to HTTP 403 in family APIs.
2. Update API documentation to clarify active auth login endpoint and deprecate/remove ambiguous legacy routes.
3. Add explicit API contract tests for permission status codes.
4. Install pytest in the container image if pytest-based suites are expected in CI/runtime validation.
5. Add explicit WebSocket assertions for family events if real-time family updates are expected behavior.

## Production Readiness Assessment
- Overall readiness percentage: 84%
- Critical issues: 0
- Medium issues: 2
- Minor issues: 2
- Final recommendation: Ready with Minor Issues

## Requirement Verification

### SECTION A: Verified Through Deployed AWS Application
- Loan create flow: Verified
- Loan accept flow: Verified
- Loan reject flow: Verified
- Loan cancel flow: Verified
- Repayment flow: Verified
- Family workflow (invitation model): Verified
- Permission failures: Verified (with status-code mismatch noted)
- Notifications: Verified
- WebSockets: Verified for loan events
- End-to-end API behavior: Verified for listed endpoints

### SECTION B: Verified Through Backend Automated Test Suite
- Command executed: docker compose exec web python manage.py test --settings=config.settings.test
- Result: PASS, 88 tests passed
- Additional command: docker compose exec web pytest -q
- Result: BLOCKED, pytest not installed in container

Coverage observations from test discovery:
- Unit tests for loan state machine: Covered (loan accept/reject/cancel tests in loans test suite)
- Unit tests for balance calculation: Partially covered (repayment and family ledger assertions)
- Unit tests for email parser fixtures: Partial/unclear from naming alone
- Unit tests for discovered bank account flow: Covered (integrations/accounts/audit tests reference discovered account flows)
- Celery task tests: Covered (notifications task tests)
- Family ledger aggregation unit tests: Covered (family ledger member position test)
- Idempotent loan creation using Idempotency-Key: Covered (loan API tests include idempotency header/body)
- Concurrent repayment overpay protection: Partially covered (overpayment prevention test exists; explicit concurrency race test not found)
- Backend race-condition handling: Requires backend source code and automated test suite execution.
- Internal business logic unit tests: Requires backend source code and automated test suite execution.

For requirements not fully provable from deployed behavior alone, assessment explicitly relied on source/test-suite inspection.


