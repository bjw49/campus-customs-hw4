"""Tools the Campus Customs agent can call to look up products, stock, and
the current shopper's account.

Pulls its DB helpers (db, row_to_product) from main.py rather than a separate
module. Those imports are deliberately done inside each function (not at
module load time): main.py imports agent.py, which imports this module, so a
top-level `from main import ...` here would be a circular import that fails
before main.py finishes defining anything. By the time these functions
actually run (a real chat request), main.py has already finished loading, so
the import just works.
"""
import json
import time
from dataclasses import dataclass, field

from pydantic_ai import RunContext

from models import CatalogueRow, InventoryRow

CHAT_HISTORY_TURNS = 10  # how many past chat_messages rows to pull into deps
CATALOGUE_CACHE_TTL = 60.0  # seconds search_product serves from memory before re-querying


@dataclass
class ChatTurn:
    role: str
    content: str


@dataclass
class AgentDeps:
    """Per-request context: who's chatting, their chat history and past product
    interest (returning, logged-in customers only), and the page they're on."""

    user_id: int | None = None
    name: str | None = None
    email: str | None = None
    chat_history: list[ChatTurn] = field(default_factory=list)
    products_discussed: list[str] = field(default_factory=list)
    current_product_id: str | None = None
    """product_id of the page the shopper is currently viewing, if any (page context)."""


def build_deps(user_id: int | None, current_product_id: str | None = None) -> AgentDeps:
    """Assemble the AgentDeps for one chat request: looks up the customer's
    name/email and recent chat history for a logged-in user, and carries
    through whatever page context the frontend sent. Guests get an AgentDeps
    with just the page context - they can still chat, just without memory.
    """
    from main import db  # see module docstring

    if user_id is None:
        return AgentDeps(current_product_id=current_product_id)

    with db() as conn:
        user_row = conn.execute(
            "SELECT name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        history_rows = conn.execute(
            """
            SELECT role, content, products_json FROM chat_messages
            WHERE user_id = ? ORDER BY id DESC LIMIT ?
            """,
            (user_id, CHAT_HISTORY_TURNS),
        ).fetchall()

    history_rows = list(reversed(history_rows))  # oldest first
    chat_history = [ChatTurn(role=r["role"], content=r["content"]) for r in history_rows]

    products_discussed: list[str] = []
    for r in history_rows:
        if not r["products_json"]:
            continue
        for p in json.loads(r["products_json"]):
            product_id = p.get("product_id")
            if product_id and product_id not in products_discussed:
                products_discussed.append(product_id)

    return AgentDeps(
        user_id=user_id,
        name=user_row["name"] if user_row else None,
        email=user_row["email"] if user_row else None,
        chat_history=chat_history,
        products_discussed=products_discussed,
        current_product_id=current_product_id,
    )


def _catalogue_row(row) -> CatalogueRow:
    from main import row_to_product  # see module docstring

    p = row_to_product(row)
    return CatalogueRow(
        product_id=p["product_id"],
        name=p["name"],
        garment_type=p["garment_type"],
        description=p["description"],
        colors=p["colors"],
        search_tags=p["search_tags"],
        image_file_path=p["image_file_path"],
        image_url=p["image_url"],
        price=p["price"],
    )


_catalogue_cache: list[CatalogueRow] | None = None
_catalogue_cache_at: float = 0.0


def _get_catalogue() -> list[CatalogueRow]:
    """The full catalogue, served from an in-memory cache rather than re-querying
    SQLite on every search_product call. Refreshed at most every
    CATALOGUE_CACHE_TTL seconds, so it can't go stale forever, but repeated or
    rapid-fire searches (one shopper, or several at once) hit memory instead of
    disk. Only the catalogue is cached - inventory changes more (stock), so
    search_inventory still queries the database directly every call.
    """
    global _catalogue_cache, _catalogue_cache_at
    from main import db  # see module docstring

    now = time.monotonic()
    if _catalogue_cache is None or (now - _catalogue_cache_at) > CATALOGUE_CACHE_TTL:
        with db() as conn:
            rows = conn.execute("SELECT * FROM catalogue").fetchall()
        _catalogue_cache = [_catalogue_row(r) for r in rows]
        _catalogue_cache_at = now
    return _catalogue_cache


def _variants(word: str) -> list[str]:
    """A word and its naive singular/plural counterpart, so "sweatshirts"
    still matches a field that only contains "sweatshirt"."""
    word = word.strip().lower()
    if len(word) > 3 and word.endswith("s"):
        return [word, word[:-1]]
    return [word, f"{word}s"]


def search_product(ctx: RunContext[AgentDeps], query: str, limit: int = 8) -> list[CatalogueRow]:
    """Search the Campus Customs catalogue by product id, name, description, garment
    type, color, or search tags, and return the full matching catalogue rows (id,
    name, garment_type, description, colors, search_tags, image, and price).

    Use this for anything about what a product IS: its description, price, or
    available colors. This does NOT include stock — use search_inventory for that.
    Always call this (or search_inventory) rather than guessing a price; never
    state a price that didn't come from this tool.

    Results are shown to the shopper as product cards. `query` can be a single
    keyword or a short natural-language phrase (e.g. "crewneck", "red hoodie",
    "Yale crewneck sweatshirts") — each word in it is matched independently, so
    a multi-word phrase won't fail to match just because no single field
    contains that exact phrase. `limit` caps how many rows come back (default
    8); lower it for a narrower result, or search again with a more specific
    word if the first search is too broad (e.g. "Yale" alone will match nearly
    everything).
    """
    words = query.split() or [query]

    def matches(row: CatalogueRow) -> bool:
        haystack = " ".join(
            [row.product_id, row.name, row.description, row.garment_type]
            + row.search_tags
            + row.colors
        ).lower()
        # Each word (or its singular/plural variant) must appear somewhere (OR
        # across variants), and every word must match (AND across words) - so
        # "Yale crewneck" needs both "Yale" and "crewneck" present, not just either.
        return all(any(v in haystack for v in _variants(word)) for word in words)

    results = [row for row in _get_catalogue() if matches(row)]
    results.sort(key=lambda r: r.name)
    return _with_badges(results[:limit])


def _with_badges(rows: list[CatalogueRow]) -> list[CatalogueRow]:
    """Attach total_stock/going_fast/trending to a (small) result set. Computed
    fresh each call rather than cached with the catalogue, since stock and chat
    activity change far more often than product descriptions do."""
    from main import GOING_FAST_THRESHOLD, db, stock_totals, trending_product_ids  # see module docstring

    with db() as conn:
        stock = stock_totals(conn)
        trending = trending_product_ids(conn)
    return [
        row.model_copy(
            update={
                "total_stock": stock.get(row.product_id, 0),
                "going_fast": stock.get(row.product_id, 0) <= GOING_FAST_THRESHOLD,
                "trending": row.product_id in trending,
            }
        )
        for row in rows
    ]


def search_inventory(
    ctx: RunContext[AgentDeps], query: str, size: str | None = None
) -> list[InventoryRow]:
    """Search inventory by product id or product name, and return the full matching
    inventory rows (inventory id, product_id, size, and quantity in stock).

    Use this for anything about HOW MANY are in stock, optionally narrowed to one
    `size` (XS, S, M, L, XL, or XXL). Never state a quantity that didn't come from
    this tool. Note: inventory only tracks stock by size, not by color — colors for
    a product come from search_product, but stock isn't split out per color.
    """
    from main import db  # see module docstring

    like = f"%{query.strip()}%"
    with db() as conn:
        sql = """
            SELECT inventory.id, inventory.product_id, inventory.size, inventory.quantity
            FROM inventory
            JOIN catalogue ON catalogue.product_id = inventory.product_id
            WHERE inventory.product_id LIKE ? OR catalogue.name LIKE ?
        """
        params: list = [like, like]
        if size:
            sql += " AND inventory.size = ?"
            params.append(size.strip().upper())
        sql += " ORDER BY inventory.product_id, inventory.size"
        rows = conn.execute(sql, params).fetchall()
    return [
        InventoryRow(id=r["id"], product_id=r["product_id"], size=r["size"], quantity=r["quantity"])
        for r in rows
    ]


def get_current_user(ctx: RunContext[AgentDeps]) -> str:
    """Look up the name of the shopper currently chatting, if they're logged in.

    Use this if the shopper asks whether you remember them, what their name is, or
    anything else about their own account. If they aren't logged in, say so. (Note:
    this same info is also given upfront in context, so this tool is mainly a
    fallback / explicit double-check.)
    """
    if ctx.deps.user_id is None or not ctx.deps.name:
        return "This shopper is not logged in, so no account info is available."
    return f"The shopper is logged in as {ctx.deps.name} ({ctx.deps.email})."
