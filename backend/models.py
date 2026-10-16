"""Pydantic types shared by the agent (agent.py / tools.py) and the API (main.py)."""
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Database row types: what search_product / search_inventory (tools.py) return.
# These mirror the catalogue/inventory tables directly (full rows), per the
# reasoning in output/harness.md: returning the full row is no extra work and
# lets the agent answer a broader set of questions than just price/stock.
# ---------------------------------------------------------------------------


class CatalogueRow(BaseModel):
    """One row of the `catalogue` table, as returned by search_product."""

    product_id: str
    name: str
    garment_type: str
    description: str
    colors: list[str] = []
    search_tags: list[str] = []
    image_file_path: str
    image_url: str
    price: float
    total_stock: int = 0
    """Sum of inventory quantity across all sizes - real, not decorative."""
    going_fast: bool = False
    """True if total_stock is at or below the low-stock threshold."""
    trending: bool = False
    """True if this product has come up often in chat_messages.products_json."""


class InventoryRow(BaseModel):
    """One row of the `inventory` table, as returned by search_inventory."""

    id: int
    product_id: str
    size: str
    quantity: int


# ---------------------------------------------------------------------------
# Content blocks: a trace of what the agent did to produce its reply, mirrored
# from the agent run's message parts (text / thinking / tool use / tool result).
# ---------------------------------------------------------------------------


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ThinkingBlock(BaseModel):
    type: Literal["thinking"] = "thinking"
    thinking: str


class ToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    tool_call_id: str
    tool_name: str
    tool_args: dict[str, Any]


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    tool_name: str
    result: Any


ContentBlock = Annotated[
    Union[TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock],
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Agent / chat result shapes.
# ---------------------------------------------------------------------------


class AgentResult(BaseModel):
    """The minimal result of one agent run: what agent.py builds internally
    before main.py/ChatReply adds the full trace and product cards."""

    reply: str
    tools_used: list[str] = []


class ChatRequest(BaseModel):
    message: str
    user_id: int | None = None
    current_product_id: str | None = None
    """Page context: the product_id of the page the shopper is currently viewing
    (e.g. a product detail page), if any. Lets the agent resolve a generic
    question ("does this come in blue?") to the right product."""


class ChatHistoryMessage(BaseModel):
    """One stored turn, as returned by GET /api/chat/history."""

    role: str
    content: str
    products: list[CatalogueRow] = []
    created_at: str


class ChatReply(BaseModel):
    reply: str
    """Final assistant text, for a simple chat bubble."""

    tools_used: list[str] = []
    """Names of the tools the agent called while answering, in call order."""

    blocks: list[ContentBlock] = []
    """Full trace of the agent run: text/thinking/tool_use/tool_result blocks, in order."""

    products: list[CatalogueRow] = []
    """Catalogue rows the agent looked up while answering, for rendering as cards."""


# ---------------------------------------------------------------------------
# Hit counter and guestbook: real, persisted site features (not decorative).
# ---------------------------------------------------------------------------


class VisitCount(BaseModel):
    count: int


class GuestbookEntry(BaseModel):
    id: int
    name: str
    message: str
    created_at: str


class GuestbookEntryCreate(BaseModel):
    name: str
    message: str
