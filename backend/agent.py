"""Campus Customs chat agent: wiring for the PydanticAI agent used by main.py.

Reads its configuration from the .env file at the repo root / backend dir:
    OPENAI_API_KEY   - key for the OpenAI-compatible endpoint
    OPENAI_BASE_URL  - e.g. https://api.portkey.ai/v1
    OPEN_AI_MODEL    - model name to request through that endpoint
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Union

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import TextPart, ThinkingPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from models import (
    AgentResult,
    CatalogueRow,
    ChatReply,
    ContentBlock,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from tools import AgentDeps, build_deps, get_current_user, search_inventory, search_product

load_dotenv()

PROMPT_PATH = Path(__file__).parent / "prompts" / "prompt.md"
AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"
LOOP_LIMIT = 10  # max tool calls per agent run, so a confused loop can't run forever
USAGE_LIMITS = UsageLimits(tool_calls_limit=LOOP_LIMIT)


def _load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _build_model() -> OpenAIChatModel:
    provider = OpenAIProvider(
        base_url=os.environ.get("OPENAI_BASE_URL"),
        api_key=os.environ.get("OPENAI_API_KEY"),
    )
    model_name = os.environ.get("OPEN_AI_MODEL", "gpt-4o-mini")
    return OpenAIChatModel(model_name, provider=provider)


agent = Agent(
    _build_model(),
    deps_type=AgentDeps,
    system_prompt=_load_system_prompt(),
)
agent.tool(search_product)
agent.tool(search_inventory)
agent.tool(get_current_user)


@agent.system_prompt
def customer_context(ctx: RunContext[AgentDeps]) -> str:
    """Dynamic context, rebuilt every run from AgentDeps: who's chatting, their
    recent history and past product interest (returning, logged-in customers
    only), and the page they're currently on (page context, for all shoppers)."""
    deps = ctx.deps
    lines: list[str] = []

    if deps.user_id is not None and deps.name:
        lines.append(f"You are chatting with a logged-in, returning customer: {deps.name} ({deps.email}).")
    else:
        lines.append(
            "This shopper is browsing as a guest (not logged in). You can still help them, "
            "but their chat history won't be saved for next time."
        )

    if deps.chat_history:
        transcript = "\n".join(f"{turn.role}: {turn.content}" for turn in deps.chat_history)
        lines.append(f"Recent conversation history with this customer:\n{transcript}")

    if deps.products_discussed:
        lines.append(
            "Product ids this customer has previously asked about: "
            + ", ".join(deps.products_discussed)
        )

    if deps.current_product_id:
        lines.append(
            f"Page context: the shopper is currently viewing the product page for "
            f"product_id '{deps.current_product_id}'. If they ask a generic question "
            "(e.g. about its color, size, price, or stock) without naming a product, "
            "assume they mean this one and look it up with search_product/search_inventory "
            "using this product_id."
        )

    return "\n\n".join(lines)


def _coerce_args(args) -> dict:
    if isinstance(args, str):
        try:
            return json.loads(args)
        except ValueError:
            return {"raw": args}
    return dict(args or {})


def _products_from_tool_result(content) -> list[CatalogueRow]:
    """Pull CatalogueRow(s) out of whatever search_product returned."""
    items = content if isinstance(content, list) else [content]
    products: list[CatalogueRow] = []
    for item in items:
        if isinstance(item, CatalogueRow):
            products.append(item)
        elif isinstance(item, dict) and "product_id" in item:
            products.append(CatalogueRow.model_validate(item))
    return products


def _parts_to_blocks(messages) -> tuple[list[ContentBlock], list[CatalogueRow], list[str]]:
    blocks: list[ContentBlock] = []
    products: list[CatalogueRow] = []
    tools_used: list[str] = []
    for message in messages:
        for part in message.parts:
            if isinstance(part, TextPart):
                blocks.append(TextBlock(text=part.content))
            elif isinstance(part, ThinkingPart):
                blocks.append(ThinkingBlock(thinking=part.content))
            elif isinstance(part, ToolCallPart):
                blocks.append(
                    ToolUseBlock(
                        tool_call_id=part.tool_call_id,
                        tool_name=part.tool_name,
                        tool_args=_coerce_args(part.args),
                    )
                )
                if part.tool_name not in tools_used:
                    tools_used.append(part.tool_name)
            elif isinstance(part, ToolReturnPart):
                blocks.append(
                    ToolResultBlock(
                        tool_call_id=part.tool_call_id,
                        tool_name=part.tool_name,
                        result=part.content,
                    )
                )
                products.extend(_products_from_tool_result(part.content))

    # The agent can call search_product more than once in a turn; de-dupe by
    # product_id (keeping first-seen order) so the same card isn't shown twice.
    seen: set[str] = set()
    deduped_products = []
    for p in products:
        if p.product_id not in seen:
            seen.add(p.product_id)
            deduped_products.append(p)

    return blocks, deduped_products, tools_used


def _short(value: Any, limit: int = 200) -> str | None:
    """A short, human-readable summary of a tool's args/result for the audit
    trail - not the full payload (which can be a whole list of catalogue rows)."""
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            text = "[]"
        else:
            def label(item: Any) -> str:
                for attr in ("product_id", "id"):
                    if hasattr(item, attr):
                        return str(getattr(item, attr))
                return str(item)

            shown = ", ".join(label(v) for v in value[:5])
            text = f"{len(value)} result(s): {shown}" + (", ..." if len(value) > 5 else "")
    else:
        text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _append_audit(record: dict) -> None:
    """Appends one JSON-line record to output/audit_trail.json. Opens the file
    in append mode and writes exactly one line - never reads or rewrites the
    file - so this is genuinely append-only: nothing here can wipe prior runs,
    whether that's an earlier line from this process or from a previous one."""
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _log_turn(blocks: list[ContentBlock], stop_reason: str, reply: str | None = None) -> None:
    """One audit record per tool call this turn (time, tool name, short args,
    short result), plus one closing record with the stop reason."""
    now = datetime.now(timezone.utc).isoformat()
    tool_args = {b.tool_call_id: b.tool_args for b in blocks if isinstance(b, ToolUseBlock)}
    for block in blocks:
        if isinstance(block, ToolResultBlock):
            _append_audit(
                {
                    "time": now,
                    "tool_name": block.tool_name,
                    "args": tool_args.get(block.tool_call_id),
                    "result": _short(block.result),
                    "stop_reason": None,
                }
            )
    _append_audit(
        {
            "time": now,
            "tool_name": None,
            "args": None,
            "result": _short(reply),
            "stop_reason": stop_reason,
        }
    )


async def run_agent_stream(
    message: str, user_id: int | None = None, current_product_id: str | None = None
) -> AsyncGenerator[Union[str, ChatReply], None]:
    """Run one turn of the agent via agent.run_stream(), yielding the reply's
    text token-by-token as the model generates it (so the frontend can render
    it progressively, the way a chat UI normally feels), then a final ChatReply
    with the full trace, tools used, and any product cards - once streaming
    finishes. Tool calls (if any) happen before text starts streaming, same as
    the non-streaming flow did.
    """
    deps = build_deps(user_id, current_product_id)
    try:
        async with agent.run_stream(message, deps=deps, usage_limits=USAGE_LIMITS) as stream_result:
            async for delta in stream_result.stream_text(delta=True, debounce_by=None):
                yield delta
            blocks, products, tools_used = _parts_to_blocks(stream_result.new_messages())
            agent_result = AgentResult(reply=await stream_result.get_output(), tools_used=tools_used)
    except Exception as exc:
        _append_audit(
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "tool_name": None,
                "args": None,
                "result": None,
                "stop_reason": _short(f"error: {exc}"),
            }
        )
        raise

    _log_turn(blocks, stop_reason="completed", reply=agent_result.reply)

    yield ChatReply(
        reply=agent_result.reply,
        tools_used=agent_result.tools_used,
        blocks=blocks,
        products=products,
    )
