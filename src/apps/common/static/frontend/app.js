(function () {
  const API_BASE = "/api/v1";
  let realtimeSocket = null;
  let reconnectTimer = null;
  let shouldReconnect = true;
  let refreshDashboardFn = null;
  let refreshLoanDetailFn = null;
  let subscribedLoanId = null;

  function token() {
    return localStorage.getItem("accessToken");
  }

  function refreshToken() {
    return localStorage.getItem("refreshToken");
  }

  function decodeJwtPayload(jwt) {
    if (!jwt) return null;
    try {
      const payload = jwt.split(".")[1];
      const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
      const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
      return JSON.parse(atob(padded));
    } catch (e) {
      return null;
    }
  }

  function isJwtExpired(jwt) {
    const payload = decodeJwtPayload(jwt);
    if (!payload || !payload.exp) return false;
    return Date.now() >= payload.exp * 1000 - 30000;
  }

  async function getLatestAccessToken() {
    const currentAccessToken = token();
    if (currentAccessToken && !isJwtExpired(currentAccessToken)) {
      return currentAccessToken;
    }

    const currentRefreshToken = refreshToken();
    if (!currentRefreshToken) {
      return currentAccessToken;
    }

    try {
      const response = await fetch(API_BASE + "/accounts/auth/token/refresh/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: currentRefreshToken }),
      });

      if (!response.ok) {
        return currentAccessToken;
      }

      const data = await response.json();
      if (data.access) {
        localStorage.setItem("accessToken", data.access);
      }
      if (data.refresh) {
        localStorage.setItem("refreshToken", data.refresh);
      }
      return localStorage.getItem("accessToken");
    } catch (e) {
      return currentAccessToken;
    }
  }

  function setFlash(message, level) {
    const flash = document.getElementById("flash");
    if (!flash) return;
    flash.className = "alert";
    flash.classList.add(level || "alert-info");
    flash.textContent = message;
  }

  function clearFlash() {
    const flash = document.getElementById("flash");
    if (!flash) return;
    flash.className = "alert d-none";
    flash.textContent = "";
  }

  function flattenApiErrors(data) {
    if (!data) return "Request failed";
    if (typeof data === "string") return data;
    if (Array.isArray(data)) return data.map(flattenApiErrors).filter(Boolean).join(" ");
    if (typeof data === "object") {
      if (data.detail) return String(data.detail);
      const parts = [];
      Object.keys(data).forEach(function (key) {
        const value = data[key];
        if (Array.isArray(value)) {
          parts.push(key + ": " + value.map(String).join(", "));
        } else if (typeof value === "object" && value !== null) {
          parts.push(key + ": " + flattenApiErrors(value));
        } else if (value !== undefined && value !== null) {
          parts.push(key + ": " + String(value));
        }
      });
      return parts.length ? parts.join(" | ") : "Request failed";
    }
    return "Request failed";
  }

  async function api(path, options) {
    clearFlash();
    const headers = { "Content-Type": "application/json" };
    if (token()) {
      headers.Authorization = "Bearer " + token();
    }

    const response = await fetch(API_BASE + path, {
      ...options,
      headers: { ...headers, ...(options && options.headers ? options.headers : {}) },
    });

    let data = null;
    try {
      data = await response.json();
    } catch (e) {
      data = null;
    }

    if (!response.ok) {
      throw new Error(flattenApiErrors(data));
    }

    return data;
  }

  function qs(selector) {
    return document.querySelector(selector);
  }

  function updateText(selector, value) {
    const node = qs(selector);
    if (!node) return;
    node.textContent = value;
  }

  function generateIdempotencyKey(prefix) {
    return prefix + "-" + Date.now() + "-" + Math.floor(Math.random() * 1000000);
  }

  function getCurrentUserId() {
    try {
      const user = JSON.parse(localStorage.getItem("currentUser") || "null");
      return user && user.id ? user.id : null;
    } catch (e) {
      return null;
    }
  }

  function setupLogout() {
    const btn = qs("#logoutBtn");
    if (!btn) return;
    btn.addEventListener("click", function () {
      shouldReconnect = false;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      localStorage.removeItem("accessToken");
      localStorage.removeItem("refreshToken");
      localStorage.removeItem("currentUser");
      if (realtimeSocket) {
        try {
          realtimeSocket.close();
        } catch (e) {}
      }
      window.location.href = "/app/login/";
    });
  }

  function wsUrl(accessToken) {
    const protocol = window.location.protocol === "https:" ? "wss://" : "ws://";
    return protocol + window.location.host + "/ws/loans/?token=" + encodeURIComponent(accessToken || token());
  }

  function subscribeLoan(loanId) {
    if (!realtimeSocket || realtimeSocket.readyState !== WebSocket.OPEN || !loanId) return;
    if (subscribedLoanId === loanId) return;
    realtimeSocket.send(JSON.stringify({ action: "subscribe_loan", loan_id: Number(loanId) }));
    subscribedLoanId = Number(loanId);
  }

  function handleRealtimeMessage(message) {
    if (!message || !message.type) return;

    if (message.type === "loan_event") {
      if (qs('[data-page="loan-list"]')) {
        loadLoanList();
      }
      if (qs('[data-page="loan-detail"]') && refreshLoanDetailFn) {
        refreshLoanDetailFn();
      }
      if (qs('[data-page="notifications"]')) {
        renderNotifications();
      }
      if (qs('[data-page="dashboard"]') && refreshDashboardFn) {
        refreshDashboardFn();
      }
      setFlash("Real-time update: " + (message.event || "loan event"), "alert-info");
      return;
    }

    if (message.type === "notification_event") {
      if (qs('[data-page="notifications"]')) {
        renderNotifications();
      }
      if (qs('[data-page="dashboard"]') && refreshDashboardFn) {
        refreshDashboardFn();
      }
      return;
    }
  }

  async function initRealtimeSocket() {
    if (!token() || qs('[data-page="login"]')) return;

    const accessToken = await getLatestAccessToken();
    if (!accessToken) return;

    try {
      realtimeSocket = new WebSocket(wsUrl(accessToken));
    } catch (e) {
      return;
    }

    realtimeSocket.onopen = function () {
      if (qs('[data-page="loan-detail"]')) {
        const loanIdInput = qs("#loanDetailId");
        if (loanIdInput && loanIdInput.value) {
          subscribeLoan(loanIdInput.value);
        }
      }
    };

    realtimeSocket.onmessage = function (event) {
  console.log("======================================");
  console.log("WEBSOCKET MESSAGE RECEIVED");
  console.log("Raw Data:", event.data);

  try {
    const message = JSON.parse(event.data);

    console.log("Parsed Message:", message);
    console.log("Message Type:", message.type);
    console.log("Event:", message.event);

    handleRealtimeMessage(message);

    console.log("handleRealtimeMessage() completed successfully");
    console.log("======================================");
  } catch (e) {
    console.error("WebSocket parsing/handling error:", e);
    console.log("======================================");
  }
};

    realtimeSocket.onclose = function () {
      subscribedLoanId = null;
      if (!shouldReconnect || qs('[data-page="login"]')) {
        return;
      }
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      reconnectTimer = setTimeout(initRealtimeSocket, 2000);
    };
  }

  async function initLogin() {
    const form = qs("#loginForm");
    if (!form) return;

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      const payload = {
        mobile_number: form.mobile_number.value,
        password: form.password.value,
      };
      try {
        const data = await api("/accounts/auth/login/", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        localStorage.setItem("accessToken", data.access);
        localStorage.setItem("refreshToken", data.refresh);
        localStorage.setItem("currentUser", JSON.stringify(data.user));
        setFlash("Login successful", "alert-success");
        window.location.href = "/app/dashboard/";
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });

    if (localStorage.getItem("registerSuccess") === "1") {
      localStorage.removeItem("registerSuccess");
      setFlash("Registration successful. Please login.", "alert-success");
    }
  }

  function validateMobileNumber(value) {
    return /^\+?[0-9]{10,15}$/.test((value || "").trim());
  }

  function initRegister() {
    const form = qs("#registerForm");
    if (!form) return;

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      clearFlash();

      const name = (form.name.value || "").trim();
      const mobileNumber = (form.mobile_number.value || "").trim();
      const password = form.password.value || "";
      const passwordConfirm = form.password_confirm.value || "";
      const gmailAddress = (form.gmail_address.value || "").trim();
      const hasProfileImage = form.profile_image.files && form.profile_image.files.length > 0;
      const csrfTokenInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
      const csrfToken = csrfTokenInput ? csrfTokenInput.value : "";

      if (!name || !mobileNumber || !password || !passwordConfirm) {
        setFlash("Please fill all required fields.", "alert-danger");
        return;
      }

      if (!validateMobileNumber(mobileNumber)) {
        setFlash("Enter a valid mobile number.", "alert-danger");
        return;
      }

      if (password.length < 8) {
        setFlash("Password must be at least 8 characters.", "alert-danger");
        return;
      }

      if (password !== passwordConfirm) {
        setFlash("Password and Confirm Password must match.", "alert-danger");
        return;
      }

      const payload = {
        name: name,
        mobile_number: mobileNumber,
        password: password,
        password_confirm: passwordConfirm,
      };
      if (gmailAddress) {
        payload.gmail_address = gmailAddress;
      }

      // Registration API currently accepts JSON only. Ignore optional file upload in this flow.
      if (hasProfileImage) {
        setFlash("Profile image upload is skipped for JSON registration.", "alert-warning");
      }

      try {
        const response = await fetch(API_BASE + "/accounts/auth/register/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
          },
          credentials: "same-origin",
          body: JSON.stringify(payload),
        });

        let data = null;
        try {
          data = await response.json();
        } catch (e) {
          data = null;
        }

        if (!response.ok) {
          throw new Error(flattenApiErrors(data));
        }

        setFlash("Registration successful. Redirecting to login...", "alert-success");
        localStorage.setItem("registerSuccess", "1");
        setTimeout(function () {
          window.location.href = "/app/login/";
        }, 1000);
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });
  }

  async function initDashboard() {
    if (!qs('[data-page="dashboard"]')) return;
    refreshDashboardFn = async function () {
      const me = await api("/accounts/auth/me/");
      const loans = await api("/loans/list/");
      const tx = await api("/payments/transactions/");
      const notifications = await api("/notifications/");

      qs("#currentUser").textContent = me.mobile_number;
      qs("#loanCount").textContent = (loans.results || loans).length;
      qs("#txCount").textContent = (tx.results || tx).length;
      qs("#notificationCount").textContent = (notifications.results || notifications).length;
      qs("#dashboardRaw").textContent = JSON.stringify({ me, loans, tx, notifications }, null, 2);
    };

    try {
      await refreshDashboardFn();
    } catch (error) {
      setFlash(error.message, "alert-danger");
    }
  }

  function initCreateLoan() {
    const form = qs("#createLoanForm");
    if (!form) return;
    const result = qs("#createLoanResult");
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      const payload = {
        borrower_id: parseInt(form.borrower_id.value, 10),
        principal_amount: form.principal_amount.value,
        currency: form.currency.value,
        interest_rate: form.interest_rate.value,
        repayment_term_months: parseInt(form.repayment_term_months.value, 10),
        starts_at: form.starts_at.value,
        ends_at: form.ends_at.value,
        purpose: form.purpose.value,
        idempotency_key: generateIdempotencyKey("loan-create"),
      };
      try {
        const data = await api("/loans/", { method: "POST", body: JSON.stringify(payload) });
        result.textContent = JSON.stringify(data, null, 2);
        setFlash("Loan created", "alert-success");
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });
  }

  async function loadLoanList() {
    const incoming = qs("#incomingLoansResult");
    const lent = qs("#lentLoansResult");
    const borrowed = qs("#borrowedLoansResult");
    const active = qs("#activeLoansResult");
    const settled = qs("#settledLoansResult");
    if (!incoming || !lent || !borrowed || !active || !settled) return;
    try {
      const incomingData = await api("/loans/incoming/");
      const lentData = await api("/loans/lent/");
      const borrowedData = await api("/loans/borrowed/");
      const activeData = await api("/loans/active/");
      const settledData = await api("/loans/settled/");

      incoming.textContent = JSON.stringify(incomingData, null, 2);
      lent.textContent = JSON.stringify(lentData, null, 2);
      borrowed.textContent = JSON.stringify(borrowedData, null, 2);
      active.textContent = JSON.stringify(activeData, null, 2);
      settled.textContent = JSON.stringify(settledData, null, 2);
    } catch (error) {
      setFlash(error.message, "alert-danger");
    }
  }

  function initLoanList() {
    if (!qs('[data-page="loan-list"]')) return;
    const btn = qs("#refreshLoanList");
    if (btn) btn.addEventListener("click", loadLoanList);
    loadLoanList();
  }

  function initLoanDetail() {
    if (!qs('[data-page="loan-detail"]')) return;
    const loanIdInput = qs("#loanDetailId");
    const output = qs("#loanDetailResult");

    qs("#acceptLoanBtn").style.display = "none";
    qs("#rejectLoanBtn").style.display = "none";
    qs("#cancelLoanBtn").style.display = "none";

    async function load() {
      if (!loanIdInput.value) return;
      const data = await api("/loans/" + loanIdInput.value + "/");
      output.textContent = JSON.stringify(data, null, 2);
      subscribeLoan(data.id);

      const currentUserId = getCurrentUserId();
      const isBorrower = currentUserId !== null && Number(data.borrower) === Number(currentUserId);
      const isLender = currentUserId !== null && Number(data.lender) === Number(currentUserId);
      const isPending = data.status === "pending_review";

      qs("#acceptLoanBtn").style.display = isBorrower && isPending ? "inline-block" : "none";
      qs("#rejectLoanBtn").style.display = isBorrower && isPending ? "inline-block" : "none";
      qs("#cancelLoanBtn").style.display = isLender && isPending ? "inline-block" : "none";
    }

    refreshLoanDetailFn = load;

    qs("#loadLoanDetail").addEventListener("click", async function () {
      try {
        await load();
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });

    qs("#acceptLoanBtn").addEventListener("click", async function () {
      try {
        const data = await api("/loans/" + loanIdInput.value + "/accept/", {
          method: "POST",
          body: JSON.stringify({ idempotency_key: generateIdempotencyKey("loan-accept") }),
        });
        output.textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });

    qs("#rejectLoanBtn").addEventListener("click", async function () {
      try {
        const data = await api("/loans/" + loanIdInput.value + "/reject/", {
          method: "POST",
          body: JSON.stringify({ reason: "Rejected from frontend", idempotency_key: generateIdempotencyKey("loan-reject") }),
        });
        output.textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });

    qs("#cancelLoanBtn").addEventListener("click", async function () {
      try {
        const data = await api("/loans/" + loanIdInput.value + "/cancel/", {
          method: "POST",
          body: JSON.stringify({ idempotency_key: generateIdempotencyKey("loan-cancel") }),
        });
        output.textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });
  }

  function initRepayment() {
    if (!qs('[data-page="repayment"]')) return;
    const result = qs("#repaymentResult");
    const createForm = qs("#createRepaymentForm");
    const payForm = qs("#payRepaymentForm");

    createForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      try {
        const loanId = createForm.loan_id.value;
        const data = await api("/loans/" + loanId + "/repayments/", {
          method: "POST",
          body: JSON.stringify({
            installment_number: parseInt(createForm.installment_number.value, 10),
            due_date: createForm.due_date.value,
            amount_due: createForm.amount_due.value,
          }),
        });
        result.textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });

    payForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      try {
        const repaymentId = payForm.repayment_id.value;
        const data = await api("/loans/repayments/" + repaymentId + "/pay/", {
          method: "POST",
          body: JSON.stringify({ payment_amount: payForm.payment_amount.value }),
        });
        result.textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });
  }

  function initFamilyLedger() {
    if (!qs('[data-page="family-ledger"]')) return;
    const statusBox = qs("#familyLedgerStatus");
    const createSection = qs("#familyCreateSection");
    const createForm = qs("#createFamilyForm");
    const createNameInput = qs("#createFamilyName");
    const invitationsSection = qs("#familyInvitationsSection");
    const invitationsList = qs("#familyInvitationsList");
    const detailsSection = qs("#familyDetailsSection");
    const ownerActions = qs("#familyOwnerActions");
    const inviteForm = qs("#inviteFamilyMemberForm");
    const inviteUserIdInput = qs("#inviteUserId");
    const removeForm = qs("#removeFamilyMemberForm");
    const removeUserIdInput = qs("#removeUserId");
    const loadForm = qs("#loadFamilyLedgerForm");
    const result = qs("#familyLedgerResult");
    const familyMembersList = qs("#familyMembersList");
    const familyNameNode = qs("#familyLedgerFamilyName");
    const familyIdNode = qs("#familyLedgerFamilyId");
    const ownerLabel = qs("#familyOwnerLabel");

    function setHidden(node, hidden) {
      if (!node) return;
      if (hidden) {
        node.classList.add("d-none");
      } else {
        node.classList.remove("d-none");
      }
    }

    function renderInvitations(invitations) {
      if (!invitationsList) return;
      if (!invitations || !invitations.length) {
        invitationsList.innerHTML = "<div class='text-muted'>No pending invitations.</div>";
        return;
      }

      invitationsList.innerHTML = invitations
        .map(function (invitation) {
          return "<div class='border rounded p-2 mb-2'>"
            + "<div><strong>Family ID:</strong> " + invitation.family + "</div>"
            + "<div><strong>Invited By:</strong> " + invitation.invited_by + "</div>"
            + "<div class='mt-2'>"
            + "<button class='btn btn-sm btn-success me-2' data-action='accept' data-id='" + invitation.id + "'>Accept</button>"
            + "<button class='btn btn-sm btn-outline-danger' data-action='reject' data-id='" + invitation.id + "'>Reject</button>"
            + "</div></div>";
        })
        .join("");

      invitationsList.querySelectorAll("button[data-action]").forEach(function (button) {
        button.addEventListener("click", async function () {
          const invitationId = button.getAttribute("data-id");
          const action = button.getAttribute("data-action");
          try {
            await api("/family/invitations/" + invitationId + "/" + action + "/", {
              method: "POST",
              body: JSON.stringify({}),
            });
            setFlash("Invitation " + action + "ed successfully.", "alert-success");
            await refreshFamilyView();
          } catch (error) {
            setFlash(error.message, "alert-danger");
          }
        });
      });
    }

    function renderMembers(members) {
      if (!familyMembersList) return;
      if (!members || !members.length) {
        familyMembersList.innerHTML = "<li class='text-muted'>No members found.</li>";
        return;
      }

      familyMembersList.innerHTML = members
        .map(function (member) {
          return "<li>User " + member.user + " (" + member.role + ")</li>";
        })
        .join("");
    }

    function renderFamilyContext(context, invitations) {
      const hasFamily = !!(context && context.has_family);

      if (statusBox) {
        statusBox.textContent = hasFamily
          ? "You are part of a family."
          : "You are not part of any family.";
      }

      setHidden(createSection, hasFamily);
      setHidden(detailsSection, !hasFamily);

      if (!hasFamily) {
        if (statusBox) {
          statusBox.textContent = "You are not part of any family.";
        }
        renderInvitations(invitations);
        setHidden(invitationsSection, false);
        if (result) {
          result.textContent = "";
        }
        return;
      }

      const family = context.family || {};
      if (familyNameNode) {
        familyNameNode.textContent = family.name || "-";
      }
      if (familyIdNode) {
        familyIdNode.textContent = family.id ? "(ID: " + family.id + ")" : "";
      }
      if (ownerLabel) {
        ownerLabel.textContent = family.created_by ? String(family.created_by) : "-";
      }

      renderMembers(context.members || []);
      setHidden(ownerActions, !context.can_manage_members);
      renderInvitations(invitations);
      setHidden(invitationsSection, !invitations || invitations.length === 0);
    }

    async function refreshFamilyView() {
      const context = await api("/family/current/");
      const invitations = await api("/family/invitations/");
      renderFamilyContext(context, invitations);
    }

    if (createForm && createNameInput) {
      createForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        try {
          const name = (createNameInput.value || "").trim();
          if (!name) {
            throw new Error("Family name is required.");
          }
          await api("/family/create/", {
            method: "POST",
            body: JSON.stringify({ name: name }),
          });
          setFlash("Family created successfully.", "alert-success");
          createNameInput.value = "";
          await refreshFamilyView();
        } catch (error) {
          setFlash(error.message, "alert-danger");
        }
      });
    }

    if (inviteForm && inviteUserIdInput) {
      inviteForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        try {
          const invitedUserId = parseInt(inviteUserIdInput.value, 10);
          if (!invitedUserId) {
            throw new Error("Valid user ID is required.");
          }
          const data = await api("/family/invitations/", {
            method: "POST",
            body: JSON.stringify({ invited_user_id: invitedUserId }),
          });
          if (result) {
            result.textContent = JSON.stringify(data, null, 2);
          }
          inviteUserIdInput.value = "";
          setFlash("Invitation sent.", "alert-success");
          await refreshFamilyView();
        } catch (error) {
          setFlash(error.message, "alert-danger");
        }
      });
    }

    if (removeForm && removeUserIdInput) {
      removeForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        try {
          const memberUserId = parseInt(removeUserIdInput.value, 10);
          if (!memberUserId) {
            throw new Error("Valid member user ID is required.");
          }
          await api("/family/current/members/remove/", {
            method: "POST",
            body: JSON.stringify({ member_user_id: memberUserId }),
          });
          removeUserIdInput.value = "";
          setFlash("Member removed.", "alert-success");
          await refreshFamilyView();
        } catch (error) {
          setFlash(error.message, "alert-danger");
        }
      });
    }

    if (loadForm && result) {
      loadForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        try {
          const data = await api("/family/current/ledger/");
          result.textContent = JSON.stringify(data, null, 2);
        } catch (error) {
          setFlash(error.message, "alert-danger");
        }
      });
    }

    refreshFamilyView().catch(function (error) {
      if (statusBox) {
        statusBox.textContent = "Unable to load family context.";
      }
      setFlash(error.message, "alert-danger");
    });
  }

  async function loadTransactions() {
    const output = qs("#transactionsResult");
    if (!output) return;
    try {
      const data = await api("/payments/transactions/");
      output.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
      setFlash(error.message, "alert-danger");
    }
  }

  async function loadTransactionSummary() {
    const output = qs("#transactionSummary");
    if (!output) return;
    try {
      const data = await api("/payments/transactions/summary/");
      output.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
      setFlash(error.message, "alert-danger");
    }
  }

  function initTransactions() {
    if (!qs('[data-page="transactions"]')) return;
    const form = qs("#createTransactionForm");
    qs("#loadTransactions").addEventListener("click", loadTransactions);
    qs("#loadTransactionSummary").addEventListener("click", loadTransactionSummary);

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      try {
        const payload = {
          amount: form.amount.value,
          transaction_date: new Date(form.transaction_date.value).toISOString(),
          narration: form.narration.value,
          direction: form.direction.value,
          account_number: form.account_number.value,
          bank: form.bank.value,
          account_type: form.account_type.value,
        };
        await api("/payments/transactions/create/", { method: "POST", body: JSON.stringify(payload) });
        setFlash("Transaction created", "alert-success");
        loadTransactions();
        loadTransactionSummary();
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });

    loadTransactions();
    loadTransactionSummary();
  }

  async function renderDiscoveredAccounts() {
    const body = qs("#discoveredAccountsBody");
    if (!body) return;
    try {
      const data = await api("/payments/discovered-accounts/");
      const rows = data.results || data;
      body.innerHTML = rows.map(function (row) {
        return "<tr><td>" + row.id + "</td><td>" + row.bank + "</td><td>" + row.account_number + "</td><td>" + row.account_type + "</td><td>" + row.status + "</td><td><button class='btn btn-sm btn-success' data-action='linked' data-id='" + row.id + "'>Link</button> <button class='btn btn-sm btn-warning' data-action='dismissed' data-id='" + row.id + "'>Dismiss</button> <button class='btn btn-sm btn-secondary' data-action='unlinked' data-id='" + row.id + "'>Unlink</button></td></tr>";
      }).join("");

      body.querySelectorAll("button[data-action]").forEach(function (btn) {
        btn.addEventListener("click", async function () {
          try {
            await api("/payments/discovered-accounts/" + btn.getAttribute("data-id") + "/" + btn.getAttribute("data-action") + "/", {
              method: "POST",
              body: JSON.stringify({}),
            });
            renderDiscoveredAccounts();
          } catch (error) {
            setFlash(error.message, "alert-danger");
          }
        });
      });
    } catch (error) {
      setFlash(error.message, "alert-danger");
    }
  }

  function handleGmailCallbackFeedback() {
    if (!qs('[data-page="discovered-accounts"]')) return;
    const params = new URLSearchParams(window.location.search);
    const gmailStatus = params.get("gmail");
    if (!gmailStatus) return;

    if (gmailStatus === "connected") {
      const email = params.get("email");
      setFlash("Gmail connected" + (email ? ": " + email : ""), "alert-success");
    } else if (gmailStatus === "error") {
      setFlash(params.get("message") || "Gmail connection failed", "alert-danger");
    }

    const cleanUrl = window.location.pathname;
    window.history.replaceState({}, document.title, cleanUrl);
  }

  async function loadGmailStatus() {
    if (!qs('[data-page="discovered-accounts"]')) return;
    try {
      const data = await api("/integrations/gmail/status/");
      updateText("#gmailConnectionStatus", data.connected ? "Connected" : "Not connected");
      updateText("#gmailConnectedEmail", data.email || "-");
      updateText("#gmailLastSync", data.last_sync ? new Date(data.last_sync).toLocaleString() : "-");
      updateText("#gmailFetchedEmailCount", String(data.fetched_email_count || 0));
      const syncBtn = qs("#syncGmailBtn");
      if (syncBtn) {
        syncBtn.disabled = !data.connected;
      }
    } catch (error) {
      updateText("#gmailConnectionStatus", "Unavailable");
      updateText("#gmailConnectedEmail", "-");
      updateText("#gmailLastSync", "-");
      updateText("#gmailFetchedEmailCount", "0");
      const syncBtn = qs("#syncGmailBtn");
      if (syncBtn) {
        syncBtn.disabled = true;
      }
      setFlash(error.message, "alert-danger");
    }
  }

  async function connectGmail() {
    const redirectUri = window.location.origin + API_BASE + "/integrations/gmail/callback/";
    const frontendRedirect = window.location.origin + "/app/discovered-accounts/";
    const query = "?redirect_uri=" + encodeURIComponent(redirectUri) + "&frontend_redirect=" + encodeURIComponent(frontendRedirect);
    const data = await api("/integrations/gmail/connect/" + query);
    if (!data.oauth_url) {
      throw new Error("OAuth URL was not returned.");
    }
    window.location.href = data.oauth_url;
  }

  async function syncGmail() {
    const payload = await api("/integrations/gmail/sync/", {
      method: "POST",
      body: JSON.stringify({ max_results: 20 }),
    });
    setFlash("Gmail sync complete. Imported " + payload.parsed_count + " transaction email(s).", "alert-success");
    await loadGmailStatus();
    await renderDiscoveredAccounts();
  }

  function initDiscoveredAccounts() {
    if (!qs('[data-page="discovered-accounts"]')) return;
    const form = qs("#discoverAccountForm");
    const loadBtn = qs("#loadDiscoveredAccounts");
    const connectBtn = qs("#connectGmailBtn");
    const syncBtn = qs("#syncGmailBtn");

    handleGmailCallbackFeedback();

    loadBtn.addEventListener("click", async function () {
      await renderDiscoveredAccounts();
      await loadGmailStatus();
    });

    connectBtn.addEventListener("click", async function () {
      try {
        await connectGmail();
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });

    syncBtn.addEventListener("click", async function () {
      try {
        await syncGmail();
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      try {
        await api("/payments/discovered-accounts/discover/", {
          method: "POST",
          body: JSON.stringify({
            account_number: form.account_number.value,
            bank: form.bank.value,
            account_type: form.account_type.value,
          }),
        });
        renderDiscoveredAccounts();
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });

    renderDiscoveredAccounts();
    loadGmailStatus();
  }

  async function renderNotifications() {
    const body = qs("#notificationsBody");
    if (!body) return;
    try {
      const data = await api("/notifications/");
      const rows = data.results || data;
      body.innerHTML = rows.map(function (row) {
        return "<tr><td>" + row.id + "</td><td>" + row.channel + "</td><td>" + row.status + "</td><td>" + row.title + "</td><td><button class='btn btn-sm btn-success' data-send='" + row.id + "'>Send</button> <button class='btn btn-sm btn-danger' data-fail='" + row.id + "'>Fail</button></td></tr>";
      }).join("");

      body.querySelectorAll("button[data-send]").forEach(function (btn) {
        btn.addEventListener("click", async function () {
          try {
            await api("/notifications/" + btn.getAttribute("data-send") + "/send/", { method: "POST", body: JSON.stringify({}) });
            renderNotifications();
          } catch (error) {
            setFlash(error.message, "alert-danger");
          }
        });
      });

      body.querySelectorAll("button[data-fail]").forEach(function (btn) {
        btn.addEventListener("click", async function () {
          const reason = window.prompt("Failure reason", "Manual failure from frontend");
          if (!reason) return;
          try {
            await api("/notifications/" + btn.getAttribute("data-fail") + "/fail/", {
              method: "POST",
              body: JSON.stringify({ failed_reason: reason }),
            });
            renderNotifications();
          } catch (error) {
            setFlash(error.message, "alert-danger");
          }
        });
      });
    } catch (error) {
      setFlash(error.message, "alert-danger");
    }
  }

  function initNotifications() {
    if (!qs('[data-page="notifications"]')) return;
    const form = qs("#createNotificationForm");
    qs("#loadNotifications").addEventListener("click", renderNotifications);

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      try {
        await api("/notifications/create/", {
          method: "POST",
          body: JSON.stringify({
            channel: form.channel.value,
            title: form.title.value,
            message: form.message.value,
            payload: {},
          }),
        });
        renderNotifications();
      } catch (error) {
        setFlash(error.message, "alert-danger");
      }
    });

    renderNotifications();
  }

  document.addEventListener("DOMContentLoaded", function () {
    shouldReconnect = true;
    setupLogout();
    initRealtimeSocket();
    initLogin();
    initRegister();
    initDashboard();
    initCreateLoan();
    initLoanList();
    initLoanDetail();
    initRepayment();
    initFamilyLedger();
    initTransactions();
    initDiscoveredAccounts();
    initNotifications();
  });
})();
