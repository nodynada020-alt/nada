from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "oasis_pos.db"

app = FastAPI(title="Oasis Market POS")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOKENS: dict[str, dict[str, Any]] = {}


class LoginPayload(BaseModel):
    username: str
    password: str


class SaleItemPayload(BaseModel):
    product_id: int
    quantity: float
    unit_price: float


class SalePayload(BaseModel):
    branch_id: int
    cashier_name: str
    payment_method: str
    items: list[SaleItemPayload]
    created_at: str | None = None


class ProductPayload(BaseModel):
    name: str
    barcode: str
    branch_id: int
    stock_qty: float
    min_stock: float
    buy_price: float
    sell_price: float
    supplier_id: int | None = None


class SupplierPayload(BaseModel):
    name: str
    phone: str
    notes: str | None = None


class UserPayload(BaseModel):
    username: str
    password: str
    role: str
    branch_id: int | None = None


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def require_auth(token: str | None) -> dict[str, Any]:
    if not token or token not in TOKENS:
        raise HTTPException(status_code=401, detail="غير مصرح")
    return TOKENS[token]


def setup_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS branches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            city TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            branch_id INTEGER,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            barcode TEXT NOT NULL UNIQUE,
            branch_id INTEGER NOT NULL,
            stock_qty REAL NOT NULL DEFAULT 0,
            min_stock REAL NOT NULL DEFAULT 0,
            buy_price REAL NOT NULL,
            sell_price REAL NOT NULL,
            supplier_id INTEGER,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            branch_id INTEGER NOT NULL,
            cashier_name TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            total_amount REAL NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            line_total REAL NOT NULL
        );
        """
    )
    conn.commit()

    if cur.execute("SELECT COUNT(*) c FROM branches").fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO branches (name, city) VALUES (?, ?)",
            ("oasis cafe & restaurant", "قرية سيدي عبد الرحمن الساحل الشمالي"),
        )
    else:
        cur.execute(
            "UPDATE branches SET name=?, city=? WHERE id=1",
            ("oasis cafe & restaurant", "قرية سيدي عبد الرحمن الساحل الشمالي"),
        )

    if cur.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO users (username, password, role, branch_id, created_at) VALUES (?, ?, ?, ?, ?)",
            ("karam", "123456", "owner", 1, now_iso()),
        )

    if cur.execute("SELECT COUNT(*) c FROM suppliers").fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO suppliers (name, phone, notes, created_at) VALUES (?, ?, ?, ?)",
            ("مورد الواحة", "0500000000", "توريد أسبوعي", now_iso()),
        )

    if cur.execute("SELECT COUNT(*) c FROM products").fetchone()["c"] == 0:
        cur.execute(
            """
            INSERT INTO products
            (name, barcode, branch_id, stock_qty, min_stock, buy_price, sell_price, supplier_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("مياه معدنية", "6280001111001", 1, 300, 40, 1.5, 2.5, 1, now_iso()),
        )
        cur.execute(
            """
            INSERT INTO products
            (name, barcode, branch_id, stock_qty, min_stock, buy_price, sell_price, supplier_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("قهوة عربية", "6280001111002", 1, 120, 20, 12, 18, 1, now_iso()),
        )

    conn.commit()
    conn.close()


def extract_token(authorization: str | None) -> str | None:
    return authorization.replace("Bearer ", "") if authorization else None


@app.on_event("startup")
def on_startup() -> None:
    setup_db()


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/app.js")
def serve_app_js() -> FileResponse:
    return FileResponse(STATIC_DIR / "app.js", media_type="application/javascript")


@app.get("/styles.css")
def serve_styles() -> FileResponse:
    return FileResponse(STATIC_DIR / "styles.css", media_type="text/css")


@app.get("/sw.js")
def serve_sw() -> FileResponse:
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


@app.post("/api/login")
def login(payload: LoginPayload) -> dict[str, Any]:
    conn = get_conn()
    row = conn.execute(
        "SELECT id, username, role, branch_id FROM users WHERE username=? AND password=?",
        (payload.username, payload.password),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")
    token = str(uuid.uuid4())
    TOKENS[token] = dict(row)
    return {"token": token, "user": dict(row)}


@app.get("/api/bootstrap")
def bootstrap(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = require_auth(extract_token(authorization))
    conn = get_conn()
    branches = [dict(r) for r in conn.execute("SELECT * FROM branches ORDER BY id").fetchall()]
    suppliers = [dict(r) for r in conn.execute("SELECT * FROM suppliers ORDER BY id DESC").fetchall()]
    products = [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()]
    users = [
        dict(r)
        for r in conn.execute(
            "SELECT id, username, role, branch_id, created_at FROM users ORDER BY id DESC"
        ).fetchall()
    ]
    conn.close()
    return {"user": user, "branches": branches, "suppliers": suppliers, "products": products, "users": users}


@app.post("/api/sales")
def create_sale(payload: SalePayload, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_auth(extract_token(authorization))
    if not payload.items:
        raise HTTPException(status_code=400, detail="لا يمكن إنشاء فاتورة بدون أصناف")

    conn = get_conn()
    cur = conn.cursor()
    total = sum(item.quantity * item.unit_price for item in payload.items)
    created_at = payload.created_at or now_iso()
    cur.execute(
        "INSERT INTO sales (branch_id, cashier_name, payment_method, total_amount, created_at) VALUES (?, ?, ?, ?, ?)",
        (payload.branch_id, payload.cashier_name, payload.payment_method, total, created_at),
    )
    sale_id = cur.lastrowid

    for item in payload.items:
        cur.execute(
            "INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, line_total) VALUES (?, ?, ?, ?, ?)",
            (sale_id, item.product_id, item.quantity, item.unit_price, item.quantity * item.unit_price),
        )
        cur.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id = ?", (item.quantity, item.product_id))
    conn.commit()
    conn.close()
    return {"sale_id": sale_id, "total": total}


@app.post("/api/sync")
def sync_offline_sales(payload: list[SalePayload], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = extract_token(authorization)
    require_auth(token)
    synced = 0
    for sale in payload:
        create_sale(sale, authorization=f"Bearer {token}")
        synced += 1
    return {"synced_sales": synced}


@app.post("/api/products")
def add_product(payload: ProductPayload, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = require_auth(extract_token(authorization))
    if user["role"] not in {"owner", "manager"}:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO products
        (name, barcode, branch_id, stock_qty, min_stock, buy_price, sell_price, supplier_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.name,
            payload.barcode,
            payload.branch_id,
            payload.stock_qty,
            payload.min_stock,
            payload.buy_price,
            payload.sell_price,
            payload.supplier_id,
            now_iso(),
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@app.put("/api/products/{product_id}")
def update_product(product_id: int, payload: ProductPayload, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = require_auth(extract_token(authorization))
    if user["role"] not in {"owner", "manager"}:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE products
        SET name=?, barcode=?, branch_id=?, stock_qty=?, min_stock=?, buy_price=?, sell_price=?, supplier_id=?
        WHERE id=?
        """,
        (
            payload.name,
            payload.barcode,
            payload.branch_id,
            payload.stock_qty,
            payload.min_stock,
            payload.buy_price,
            payload.sell_price,
            payload.supplier_id,
            product_id,
        ),
    )
    conn.commit()
    changed = cur.rowcount
    conn.close()
    if changed == 0:
        raise HTTPException(status_code=404, detail="المنتج غير موجود")
    return {"updated": True}


@app.delete("/api/products/{product_id}")
def delete_product(product_id: int, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = require_auth(extract_token(authorization))
    if user["role"] not in {"owner", "manager"}:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    changed = cur.rowcount
    conn.close()
    if changed == 0:
        raise HTTPException(status_code=404, detail="المنتج غير موجود")
    return {"deleted": True}


@app.post("/api/suppliers")
def add_supplier(payload: SupplierPayload, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = require_auth(extract_token(authorization))
    if user["role"] not in {"owner", "manager"}:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO suppliers (name, phone, notes, created_at) VALUES (?, ?, ?, ?)",
        (payload.name, payload.phone, payload.notes, now_iso()),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@app.post("/api/users")
def add_user(payload: UserPayload, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = require_auth(extract_token(authorization))
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="فقط مالك النظام يمكنه إضافة مستخدمين")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password, role, branch_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (payload.username, payload.password, payload.role, payload.branch_id, now_iso()),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@app.get("/api/reports/daily")
def daily_report(branch_id: int | None = None, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_auth(extract_token(authorization))
    conn = get_conn()
    if branch_id:
        summary = conn.execute(
            """
            SELECT COUNT(*) AS invoices, COALESCE(SUM(total_amount), 0) AS total_sales
            FROM sales
            WHERE branch_id=? AND date(created_at)=date('now')
            """,
            (branch_id,),
        ).fetchone()
    else:
        summary = conn.execute(
            """
            SELECT COUNT(*) AS invoices, COALESCE(SUM(total_amount), 0) AS total_sales
            FROM sales
            WHERE date(created_at)=date('now')
            """
        ).fetchone()

    low_stock = [
        dict(r)
        for r in conn.execute(
            "SELECT id, name, stock_qty, min_stock FROM products WHERE stock_qty <= min_stock ORDER BY stock_qty ASC"
        ).fetchall()
    ]
    if branch_id:
        sales_rows = conn.execute(
            """
            SELECT id, cashier_name, payment_method, total_amount, created_at
            FROM sales
            WHERE branch_id=? AND date(created_at)=date('now')
            ORDER BY id DESC
            """,
            (branch_id,),
        ).fetchall()
    else:
        sales_rows = conn.execute(
            """
            SELECT id, cashier_name, payment_method, total_amount, created_at
            FROM sales
            WHERE date(created_at)=date('now')
            ORDER BY id DESC
            """
        ).fetchall()

    detailed_invoices: list[dict[str, Any]] = []
    for sale in sales_rows:
        items = [
            dict(r)
            for r in conn.execute(
                """
                SELECT
                    si.product_id,
                    p.name AS product_name,
                    si.quantity,
                    si.unit_price,
                    si.line_total
                FROM sale_items si
                JOIN products p ON p.id = si.product_id
                WHERE si.sale_id=?
                ORDER BY si.id ASC
                """,
                (sale["id"],),
            ).fetchall()
        ]
        detailed_invoices.append(
            {
                "id": sale["id"],
                "cashier_name": sale["cashier_name"],
                "payment_method": sale["payment_method"],
                "total_amount": sale["total_amount"],
                "created_at": sale["created_at"],
                "items": items,
            }
        )
    if branch_id:
        sold_today = [
            dict(r)
            for r in conn.execute(
                """
                SELECT
                    p.name AS product_name,
                    SUM(si.quantity) AS total_qty,
                    SUM(si.line_total) AS total_amount
                FROM sale_items si
                JOIN sales s ON s.id = si.sale_id
                JOIN products p ON p.id = si.product_id
                WHERE s.branch_id=? AND date(s.created_at)=date('now')
                GROUP BY p.id, p.name
                ORDER BY total_qty DESC
                """,
                (branch_id,),
            ).fetchall()
        ]
    else:
        sold_today = [
            dict(r)
            for r in conn.execute(
                """
                SELECT
                    p.name AS product_name,
                    SUM(si.quantity) AS total_qty,
                    SUM(si.line_total) AS total_amount
                FROM sale_items si
                JOIN sales s ON s.id = si.sale_id
                JOIN products p ON p.id = si.product_id
                WHERE date(s.created_at)=date('now')
                GROUP BY p.id, p.name
                ORDER BY total_qty DESC
                """
            ).fetchall()
        ]
    conn.close()
    return {
        "summary": dict(summary),
        "low_stock": low_stock,
        "invoices": detailed_invoices,
        "sold_today": sold_today,
    }
