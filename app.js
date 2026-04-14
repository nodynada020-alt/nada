const state = {
  token: localStorage.getItem("oasis_token"),
  user: null,
  branches: [],
  suppliers: [],
  products: [],
  users: [],
  cart: [],
};

const byId = (id) => document.getElementById(id);
const statusBar = byId("statusBar");

function setStatus(text) {
  statusBar.textContent = `الحالة: ${text}`;
}

function authHeaders() {
  return { Authorization: `Bearer ${state.token}`, "Content-Type": "application/json" };
}

function branchName(branchId) {
  const b = state.branches.find((x) => x.id === branchId);
  return b ? b.name : "-";
}

function renderSelectOptions() {
  const branches = state.branches
    .map((b) => `<option value="${b.id}">${b.name} - ${b.city}</option>`)
    .join("");
  byId("saleBranch").innerHTML = branches;
  byId("pBranch").innerHTML = branches;
  byId("uBranch").innerHTML = `<option value="">بدون تحديد</option>${branches}`;

  byId("pSupplier").innerHTML = state.suppliers
    .map((s) => `<option value="${s.id}">${s.name}</option>`)
    .join("");

  byId("productPicker").innerHTML = state.products
    .map((p) => `<option value="${p.id}">${p.name} (${p.sell_price} ج.م)</option>`)
    .join("");
  if (!state.products.length) {
    byId("productPicker").innerHTML = `<option value="">لا توجد منتجات بعد</option>`;
  }
}

function renderProducts() {
  byId("productsTable").querySelector("tbody").innerHTML = state.products
    .map(
      (p) => `<tr>
        <td>${p.name}</td>
        <td>${p.barcode}</td>
        <td>${p.stock_qty}</td>
        <td>${p.min_stock}</td>
        <td class="${p.stock_qty <= p.min_stock ? "danger" : ""}">${p.stock_qty <= p.min_stock ? "نقص" : "طبيعي"}</td>
      </tr>`
    )
    .join("");
}

function renderSuppliers() {
  byId("suppliersList").innerHTML = state.suppliers
    .map((s) => `<li>${s.name} - ${s.phone} ${s.notes ? `(${s.notes})` : ""}</li>`)
    .join("");
}

function renderUsers() {
  byId("usersTable").querySelector("tbody").innerHTML = state.users
    .map((u) => `<tr><td>${u.username}</td><td>${u.role}</td><td>${branchName(u.branch_id)}</td></tr>`)
    .join("");
}

function renderCart() {
  byId("cartTable").querySelector("tbody").innerHTML = state.cart
    .map((item) => `<tr><td>${item.name}</td><td>${item.quantity}</td><td>${item.unit_price}</td><td>${item.line_total}</td></tr>`)
    .join("");
  const total = state.cart.reduce((a, b) => a + b.line_total, 0);
  byId("cartTotal").textContent = `الإجمالي: ${total.toFixed(2)} ج.م`;
}

async function fetchBootstrap() {
  const res = await fetch("/api/bootstrap", { headers: authHeaders() });
  if (!res.ok) throw new Error("فشل تحميل البيانات");
  const data = await res.json();
  state.user = data.user;
  state.branches = data.branches;
  state.suppliers = data.suppliers;
  state.products = data.products;
  state.users = data.users;

  byId("currentUser").textContent = `المستخدم: ${state.user.username} (${state.user.role})`;
  renderSelectOptions();
  renderProducts();
  renderSuppliers();
  renderUsers();
}

async function login(username, password) {
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("بيانات الدخول غير صحيحة");
  const data = await res.json();
  state.token = data.token;
  localStorage.setItem("oasis_token", state.token);
}

function initTabs() {
  document.querySelectorAll(".tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.add("hidden"));
      byId(`tab-${btn.dataset.tab}`).classList.remove("hidden");
    });
  });
}

function addCartItem() {
  const productId = Number(byId("productPicker").value);
  const quantity = Number(byId("qtyInput").value || "1");
  const product = state.products.find((p) => p.id === productId);
  if (!product) return;
  state.cart.push({
    product_id: product.id,
    name: product.name,
    quantity,
    unit_price: Number(product.sell_price),
    line_total: Number(product.sell_price) * quantity,
  });
  renderCart();
}

function queueOfflineSale(payload) {
  const q = JSON.parse(localStorage.getItem("offline_sales") || "[]");
  q.push(payload);
  localStorage.setItem("offline_sales", JSON.stringify(q));
}

async function syncOfflineSales() {
  const q = JSON.parse(localStorage.getItem("offline_sales") || "[]");
  if (!q.length || !navigator.onLine || !state.token) return;
  const res = await fetch("/api/sync", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(q),
  });
  if (res.ok) {
    localStorage.removeItem("offline_sales");
    setStatus("تمت مزامنة المبيعات الأوفلاين");
  }
}

async function submitSale() {
  if (!state.cart.length) return;
  const payload = {
    branch_id: Number(byId("saleBranch").value),
    cashier_name: state.user.username,
    payment_method: byId("paymentMethod").value,
    items: state.cart.map((c) => ({
      product_id: c.product_id,
      quantity: c.quantity,
      unit_price: c.unit_price,
    })),
    created_at: new Date().toISOString(),
  };
  if (!navigator.onLine) {
    queueOfflineSale(payload);
    state.cart = [];
    renderCart();
    setStatus("تم حفظ الفاتورة أوفلاين وسيتم رفعها عند عودة الإنترنت");
    return;
  }

  const res = await fetch("/api/sales", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("تعذر حفظ الفاتورة");
  state.cart = [];
  renderCart();
  await fetchBootstrap();
  setStatus("تم حفظ الفاتورة بنجاح");
}

async function refreshReport() {
  const branchId = Number(byId("saleBranch").value);
  const res = await fetch(`/api/reports/daily?branch_id=${branchId}`, { headers: authHeaders() });
  const data = await res.json();
  byId("reportSummary").textContent = `عدد الفواتير اليوم: ${data.summary.invoices} | إجمالي المبيعات: ${Number(data.summary.total_sales).toFixed(2)} ج.م`;
  byId("lowStockList").innerHTML = data.low_stock
    .map((p) => `<li class="danger">${p.name} - الكمية ${p.stock_qty} (الحد ${p.min_stock})</li>`)
    .join("");
  byId("soldTodayDetails").innerHTML = (data.sold_today || [])
    .map(
      (x) =>
        `<div class="card"><strong>${x.product_name}</strong> | الكمية المباعة: ${Number(x.total_qty).toFixed(2)} | قيمة المبيعات: ${Number(x.total_amount).toFixed(2)} ج.م</div>`
    )
    .join("");
  if (!data.sold_today || !data.sold_today.length) {
    byId("soldTodayDetails").innerHTML = "<p>لا توجد مبيعات أصناف اليوم.</p>";
  }
  byId("invoicesDetails").innerHTML = (data.invoices || [])
    .map((inv) => {
      const itemsHtml = (inv.items || [])
        .map(
          (item) =>
            `<tr>
              <td>${item.product_name}</td>
              <td>${item.quantity}</td>
              <td>${Number(item.unit_price).toFixed(2)} ج.م</td>
              <td>${Number(item.line_total).toFixed(2)} ج.م</td>
            </tr>`
        )
        .join("");
      return `
        <div class="card">
          <div><strong>رقم الفاتورة:</strong> ${inv.id}</div>
          <div><strong>الكاشير:</strong> ${inv.cashier_name} | <strong>الدفع:</strong> ${inv.payment_method}</div>
          <div><strong>الوقت:</strong> ${inv.created_at}</div>
          <div><strong>الإجمالي:</strong> ${Number(inv.total_amount).toFixed(2)} ج.م</div>
          <button class="print-invoice-btn" data-invoice-id="${inv.id}">طباعة الفاتورة</button>
          <table>
            <thead><tr><th>الصنف</th><th>الكمية</th><th>السعر</th><th>الإجمالي</th></tr></thead>
            <tbody>${itemsHtml || `<tr><td colspan="4">لا توجد أصناف</td></tr>`}</tbody>
          </table>
        </div>
      `;
    })
    .join("");
  document.querySelectorAll(".print-invoice-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const invId = Number(btn.dataset.invoiceId);
      const inv = (data.invoices || []).find((x) => x.id === invId);
      if (inv) printInvoice(inv);
    });
  });
  if (!data.invoices || !data.invoices.length) {
    byId("invoicesDetails").innerHTML = "<p>لا توجد فواتير اليوم.</p>";
  }
}

async function addProduct(event) {
  event.preventDefault();
  const payload = {
    name: byId("pName").value,
    barcode: byId("pBarcode").value,
    branch_id: Number(byId("pBranch").value),
    stock_qty: Number(byId("pStock").value),
    min_stock: Number(byId("pMin").value),
    buy_price: Number(byId("pBuy").value),
    sell_price: Number(byId("pSell").value),
    supplier_id: Number(byId("pSupplier").value),
  };
  const res = await fetch("/api/products", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("لا تملك صلاحية إضافة منتج");
  await fetchBootstrap();
  event.target.reset();
}

async function addSupplier(event) {
  event.preventDefault();
  const payload = {
    name: byId("sName").value,
    phone: byId("sPhone").value,
    notes: byId("sNotes").value,
  };
  const res = await fetch("/api/suppliers", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("لا تملك صلاحية إضافة مورد");
  await fetchBootstrap();
  event.target.reset();
}

async function addUser(event) {
  event.preventDefault();
  const branchRaw = byId("uBranch").value;
  const payload = {
    username: byId("uName").value,
    password: byId("uPass").value,
    role: byId("uRole").value,
    branch_id: branchRaw ? Number(branchRaw) : null,
  };
  const res = await fetch("/api/users", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("فقط مالك النظام يمكنه إضافة مستخدمين");
  await fetchBootstrap();
  event.target.reset();
}

function setOnlineStatus() {
  const pendingCount = JSON.parse(localStorage.getItem("offline_sales") || "[]").length;
  setStatus(`${navigator.onLine ? "أونلاين" : "أوفلاين"} | فواتير غير متزامنة: ${pendingCount} | متوافق مع الجوال والتابلت`);
}

function printInvoice(inv) {
  const itemsRows = (inv.items || [])
    .map(
      (item) => `
      <tr>
        <td>${item.product_name}</td>
        <td>${item.quantity}</td>
        <td>${Number(item.unit_price).toFixed(2)} ج.م</td>
        <td>${Number(item.line_total).toFixed(2)} ج.م</td>
      </tr>
    `
    )
    .join("");
  const html = `
    <html lang="ar" dir="rtl">
      <head><meta charset="UTF-8"><title>فاتورة ${inv.id}</title></head>
      <body style="font-family:Arial;padding:18px">
        <h2>Oasis - فاتورة رقم ${inv.id}</h2>
        <p>الكاشير: ${inv.cashier_name}</p>
        <p>الدفع: ${inv.payment_method}</p>
        <p>الوقت: ${inv.created_at}</p>
        <p>الإجمالي: ${Number(inv.total_amount).toFixed(2)} ج.م</p>
        <table border="1" cellspacing="0" cellpadding="6" style="width:100%;border-collapse:collapse">
          <thead><tr><th>الصنف</th><th>الكمية</th><th>السعر</th><th>الإجمالي</th></tr></thead>
          <tbody>${itemsRows}</tbody>
        </table>
      </body>
    </html>
  `;
  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(html);
  w.document.close();
  w.focus();
  w.print();
}

function logout() {
  localStorage.removeItem("oasis_token");
  state.token = null;
  state.user = null;
  state.cart = [];
  byId("appView").classList.add("hidden");
  byId("loginView").classList.remove("hidden");
  setStatus("تم تسجيل الخروج");
}

async function startApp() {
  byId("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await login(byId("username").value, byId("password").value);
      byId("loginView").classList.add("hidden");
      byId("appView").classList.remove("hidden");
      await fetchBootstrap();
      await syncOfflineSales();
      await refreshReport();
      setOnlineStatus();
    } catch (error) {
      setStatus(error.message);
    }
  });

  byId("addItemBtn").addEventListener("click", addCartItem);
  byId("submitSaleBtn").addEventListener("click", async () => {
    try {
      await submitSale();
      await refreshReport();
      setOnlineStatus();
    } catch (error) {
      setStatus(error.message);
    }
  });
  byId("refreshReport").addEventListener("click", refreshReport);
  byId("logoutBtn").addEventListener("click", logout);
  byId("productForm").addEventListener("submit", async (event) => {
    try {
      await addProduct(event);
      setStatus("تمت إضافة المنتج");
    } catch (error) {
      setStatus(error.message);
    }
  });
  byId("supplierForm").addEventListener("submit", async (event) => {
    try {
      await addSupplier(event);
      setStatus("تمت إضافة المورد");
    } catch (error) {
      setStatus(error.message);
    }
  });
  byId("userForm").addEventListener("submit", async (event) => {
    try {
      await addUser(event);
      setStatus("تمت إضافة المستخدم");
    } catch (error) {
      setStatus(error.message);
    }
  });

  window.addEventListener("online", async () => {
    await syncOfflineSales();
    setOnlineStatus();
  });
  window.addEventListener("offline", setOnlineStatus);
  initTabs();
  setOnlineStatus();

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js");
  }

  if (state.token) {
    try {
      byId("loginView").classList.add("hidden");
      byId("appView").classList.remove("hidden");
      await fetchBootstrap();
      await syncOfflineSales();
      await refreshReport();
      setOnlineStatus();
    } catch {
      localStorage.removeItem("oasis_token");
      state.token = null;
      byId("loginView").classList.remove("hidden");
      byId("appView").classList.add("hidden");
      setStatus("يرجى تسجيل الدخول");
    }
  }
}

startApp();
