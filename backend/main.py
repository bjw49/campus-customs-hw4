"""Campus Customs backend.

Serves catalogue/inventory data from SQLite, product images, account
signup/login, and the chat endpoint backed by the PydanticAI agent in agent.py.

Run from HW/hw4/backend:  uvicorn main:app --reload --port 8000
"""
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, field_validator

from agent import run_agent_stream
from models import (
    ChatHistoryMessage,
    ChatReply,
    ChatRequest,
    GuestbookEntry,
    GuestbookEntryCreate,
    VisitCount,
)
from security import hash_password, verify_password

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
GOING_FAST_THRESHOLD = 40  # total units across all sizes; ~20% of the catalogue falls under this
TRENDING_MIN_MENTIONS = 2  # times a product must appear in chat_messages.products_json

FAKE_GUESTBOOK_SEED = [
    ("xXx_yalie_2004", "omg this site is SO cash, signing before i dial up and lose connection"),
    ("bulldog4lyfe", "copped the big yale hoodie, it is literally bussin no cap"),
    ("skaterboi99", "this is the best website i have ever visited period. webmaster please email me back"),
    ("ur_mom_123", "lol found this on a webring, actually kinda fire ngl"),
    ("cassette_tape_kid", "i love how this feels like geocities but the hoodies are real. 10/10"),
    ("new_haven_native", "been shopping here since before it was cool, this is my era fr fr"),
    ("floppy_disk_stan", "the crewnecks are giving old money new money. will be back"),
    ("tamagotchi_mom", "my tamagotchi died while i was checking out but the hoodie was worth it"),
]

PASSWORD_RULES = (
    "Password must be at least 8 characters and include at least one uppercase "
    "letter, one lowercase letter, one number, and one special character."
)
PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9])\S{8,}$"
)

app = FastAPI(title="Campus Customs API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# catalogue.image_file_path is "products/<file>.jpg", so mount at /products
app.mount("/products", StaticFiles(directory=DATA_DIR / "products"), name="products")


def _ensure_extra_tables() -> None:
    """Create the hit-counter and guestbook tables if they don't exist yet
    (they aren't part of the original seeded schema), and seed the guestbook
    with fake testimonials the first time, so the 90s guestbook wall isn't empty."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS site_visits (id INTEGER PRIMARY KEY AUTOINCREMENT, visited_at TEXT NOT NULL)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS guestbook_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM guestbook_entries").fetchone()[0]
        if count == 0:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            conn.executemany(
                "INSERT INTO guestbook_entries (name, message, created_at) VALUES (?, ?, ?)",
                [(name, message, now) for name, message in FAKE_GUESTBOOK_SEED],
            )
        conn.commit()
    finally:
        conn.close()


_ensure_extra_tables()


def db() -> sqlite3.Connection:
    """Read-only connection. Also imported by tools.py (lazily, at call time,
    to avoid a circular import with agent.py -> tools.py -> main.py)."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def db_write() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_product(row: sqlite3.Row) -> dict:
    p = dict(row)
    p["colors"] = json.loads(p["colors"])
    p["search_tags"] = json.loads(p["search_tags"])
    p["image_url"] = "/" + p["image_file_path"]
    return p


def get_sizes(conn: sqlite3.Connection, product_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)
    ).fetchall()
    sizes = [dict(r) for r in rows]
    sizes.sort(key=lambda s: SIZE_ORDER.index(s["size"]) if s["size"] in SIZE_ORDER else 99)
    return sizes


def stock_totals(conn: sqlite3.Connection) -> dict[str, int]:
    """Total units in stock per product, across all sizes - the real number
    behind the "going fast" sticker badge."""
    rows = conn.execute(
        "SELECT product_id, COALESCE(SUM(quantity), 0) AS total FROM inventory GROUP BY product_id"
    ).fetchall()
    return {r["product_id"]: r["total"] for r in rows}


def trending_product_ids(conn: sqlite3.Connection) -> set[str]:
    """product_ids that at least TRENDING_MIN_MENTIONS different customers have
    been shown - the real signal behind the "trending" badge. Counting by
    distinct user_id, not raw appearances, matters because one reply can list
    many products at once (e.g. "here are 8 hoodies"): that's one customer
    browsing one category, not 8 separate signs of real demand."""
    rows = conn.execute(
        "SELECT user_id, products_json FROM chat_messages WHERE products_json IS NOT NULL"
    ).fetchall()
    product_users: dict[str, set[int]] = {}
    for r in rows:
        try:
            items = json.loads(r["products_json"])
        except (TypeError, ValueError):
            continue
        for item in items:
            product_id = item.get("product_id")
            if product_id:
                product_users.setdefault(product_id, set()).add(r["user_id"])
    return {pid for pid, users in product_users.items() if len(users) >= TRENDING_MIN_MENTIONS}


def _with_badges(product: dict, stock: dict[str, int], trending: set[str]) -> dict:
    total = stock.get(product["product_id"], 0)
    product["total_stock"] = total
    product["going_fast"] = total <= GOING_FAST_THRESHOLD
    product["trending"] = product["product_id"] in trending
    return product


@app.get("/api/products")
def list_products() -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM catalogue ORDER BY name").fetchall()
        stock = stock_totals(conn)
        trending = trending_product_ids(conn)
    return [_with_badges(row_to_product(r), stock, trending) for r in rows]


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> dict:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM catalogue WHERE product_id = ?", (product_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        product = _with_badges(row_to_product(row), stock_totals(conn), trending_product_ids(conn))
        product["sizes"] = get_sizes(conn, product_id)
    return product


@app.post("/api/visits", response_model=VisitCount)
def record_visit() -> VisitCount:
    """Records one real visit and returns the new total. The frontend calls
    this once per browser session, so the hit counter reflects actual traffic."""
    visited_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with db_write() as conn:
        conn.execute("INSERT INTO site_visits (visited_at) VALUES (?)", (visited_at,))
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM site_visits").fetchone()[0]
    return VisitCount(count=count)


@app.get("/api/visits", response_model=VisitCount)
def get_visit_count() -> VisitCount:
    with db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM site_visits").fetchone()[0]
    return VisitCount(count=count)


# ---------------------------------------------------------------------------
# Guestbook: a 90s guestbook wall, seeded with fake testimonials, that real
# visitors can also sign.
# ---------------------------------------------------------------------------


@app.get("/api/guestbook", response_model=list[GuestbookEntry])
def list_guestbook() -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, name, message, created_at FROM guestbook_entries ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/guestbook", response_model=GuestbookEntry, status_code=201)
def sign_guestbook(entry: GuestbookEntryCreate) -> dict:
    name = entry.name.strip()[:40]
    message = entry.message.strip()[:300]
    if not name or not message:
        raise HTTPException(status_code=400, detail="Enter a name and a message.")
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with db_write() as conn:
        cur = conn.execute(
            "INSERT INTO guestbook_entries (name, message, created_at) VALUES (?, ?, ?)",
            (name, message, created_at),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, name, message, created_at FROM guestbook_entries WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


# ---------------------------------------------------------------------------
# Chat: routes a message from the website to the PydanticAI agent.
# ---------------------------------------------------------------------------


def _log_chat_message(user_id: int, role: str, content: str, products: list) -> None:
    """Persist a chat turn for a logged-in user. Anonymous turns aren't saved,
    since chat_messages.user_id is NOT NULL."""
    products_json = json.dumps([p.model_dump() for p in products]) if products else None
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with db_write() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (user_id, role, content, products_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, role, content, products_json, created_at),
        )
        conn.commit()


@app.post("/api/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    """Streams the agent's reply as it's generated: one newline-delimited JSON
    object per line, `{"type": "token", "text": "..."}` for each text chunk as
    it arrives, followed by one `{"type": "final", ...ChatReply fields...}` once
    the agent has finished (with the full trace, tools used, and product cards).
    """
    if req.user_id is not None:
        _log_chat_message(req.user_id, "user", req.message, [])

    async def event_stream():
        final: ChatReply | None = None
        async for chunk in run_agent_stream(
            req.message, user_id=req.user_id, current_product_id=req.current_product_id
        ):
            if isinstance(chunk, str):
                yield json.dumps({"type": "token", "text": chunk}) + "\n"
            else:
                final = chunk
                yield json.dumps({"type": "final", **final.model_dump(mode="json")}) + "\n"

        if req.user_id is not None and final is not None:
            _log_chat_message(req.user_id, "assistant", final.reply, final.products)

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.get("/api/chat/history", response_model=list[ChatHistoryMessage])
def chat_history(user_id: int) -> list[dict]:
    """A logged-in user's saved chat history, oldest first, so the chat widget
    can reload their conversation when they return."""
    with db() as conn:
        rows = conn.execute(
            "SELECT role, content, products_json, created_at FROM chat_messages WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    return [
        {
            "role": r["role"],
            "content": r["content"],
            "products": json.loads(r["products_json"]) if r["products_json"] else [],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Accounts: signup / login
# ---------------------------------------------------------------------------


class UserOut(BaseModel):
    id: int
    first_name: str | None
    last_name: str | None
    name: str
    email: str


class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("first_name", "last_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("This field is required.")
        return v

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not PASSWORD_PATTERN.match(v):
            raise ValueError(PASSWORD_RULES)
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def row_to_user(row: sqlite3.Row) -> UserOut:
    return UserOut(
        id=row["id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        name=row["name"],
        email=row["email"],
    )


@app.post("/api/signup", response_model=UserOut, status_code=201)
def signup(req: SignupRequest) -> UserOut:
    if req.password != req.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    email = req.email.lower()
    password_hash = hash_password(req.password)
    name = f"{req.first_name} {req.last_name}"
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with db_write() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE lower(email) = ?", (email,)
        ).fetchone()
        if existing is not None:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        try:
            cur = conn.execute(
                """
                INSERT INTO users (name, email, password_hash, created_at, first_name, last_name)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, email, password_hash, created_at, req.first_name, req.last_name),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()

    return row_to_user(row)


@app.post("/api/login", response_model=UserOut)
def login(req: LoginRequest) -> UserOut:
    email = req.email.lower()
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE lower(email) = ?", (email,)
        ).fetchone()

    # Same generic error whether the email is unknown or the password is
    # wrong, so a caller can't use this to discover which emails are registered.
    invalid = HTTPException(status_code=401, detail="Invalid email or password.")
    if row is None:
        raise invalid
    if not verify_password(req.password, row["password_hash"]):
        raise invalid

    return row_to_user(row)
