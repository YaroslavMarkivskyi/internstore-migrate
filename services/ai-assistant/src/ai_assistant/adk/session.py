"""Build a fresh ADK session per request, seeded with the conversation
history Chat owns.

Chat (not ADK) is the source of truth for conversation history — it handles
the clear-conversation cutoff and the support handoff. So each agent turn
gets a brand-new session whose prior events are replayed from the history
Chat returns, exactly as the old react_loop rebuilt `contents` every call.
"""

import uuid

from google.adk.events import Event
from google.adk.sessions import BaseSessionService, Session
from google.genai import types as genai_types


def _history_event(entry: dict, agent_name: str) -> Event | None:
    content = entry.get("content")
    if not content:
        return None
    is_assistant = entry.get("sender_type") == "assistant"
    return Event(
        author=agent_name if is_assistant else "user",
        content=genai_types.Content(
            role="model" if is_assistant else "user",
            parts=[genai_types.Part(text=content)],
        ),
    )


async def prepare_session(
    session_service: BaseSessionService,
    *,
    app_name: str,
    user_id: str,
    agent_name: str,
    history: list[dict] | None,
    context_note: str | None = None,
) -> Session:
    session = await session_service.create_session(
        app_name=app_name, user_id=user_id, session_id=str(uuid.uuid4())
    )
    for entry in history or []:
        event = _history_event(entry, agent_name)
        if event is not None:
            await session_service.append_event(session, event)
    if context_note:
        # A separate turn so the model reads it as context, not as something
        # the customer typed (mirrors the old react_loop `_build_contents`).
        await session_service.append_event(
            session,
            Event(
                author="user",
                content=genai_types.Content(role="user", parts=[genai_types.Part(text=context_note)]),
            ),
        )
    return session


def viewing_context_note(*, viewing_product_id: str | None, viewing_category_id: str | None) -> str | None:
    if viewing_product_id:
        return (
            f"(Context: the customer is viewing the product page for product_id {viewing_product_id}. "
            f"If they say 'this', 'it', or 'this product' without naming one, they mean that product. "
            f"Call get_product to confirm its current details before quoting them.)"
        )
    if viewing_category_id:
        return (
            f"(Context: the customer is browsing the category page for category_id {viewing_category_id}. "
            f"If they say 'here', 'this category', or ask for 'more like these' without naming a category, "
            f"they mean that one. Call list_categories to get its name, then search_products with that "
            f"name as the category filter.)"
        )
    return None
