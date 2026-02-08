# ABOUTME: ASGI web entry point for the weather chatbot UI.
# ABOUTME: Creates a Starlette app via agent.to_web() with input guard middleware for topic enforcement.

import json
import logging
import os
from uuid import uuid4

from src.agent import agent, guard_agent
from src.deps import WeatherDeps, create_http_client

logger = logging.getLogger(__name__)

REFUSAL_MESSAGE = (
    "I'm a weather and climate assistant, so I can only help with weather-related questions. "
    "Try asking me about forecasts, temperature, historical climate data, or atmospheric conditions "
    "for any location worldwide!"
)

# Vercel AI Data Stream Protocol headers
_SSE_HEADERS = [
    [b"content-type", b"text/event-stream"],
    [b"x-vercel-ai-ui-message-stream", b"v1"],
]


def extract_last_user_text(body: bytes) -> str | None:
    """Extract the last user message text from a Vercel AI chat request body."""
    try:
        data = json.loads(body)
        for msg in reversed(data.get("messages", [])):
            if msg.get("role") == "user":
                for part in msg.get("parts", []):
                    if part.get("type") == "text":
                        return part.get("text", "")
        return None
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def build_refusal_sse(text: str) -> bytes:
    """Build a complete Vercel AI SSE response body for a simple text message."""
    msg_id = str(uuid4())
    events = [
        '{"type":"start"}',
        '{"type":"start-step"}',
        json.dumps({"type": "text-start", "id": msg_id}),
        json.dumps({"type": "text-delta", "id": msg_id, "delta": text}),
        json.dumps({"type": "text-end", "id": msg_id}),
        '{"type":"finish-step"}',
        '{"type":"finish","finishReason":"stop"}',
        "[DONE]",
    ]
    return "".join(f"data: {e}\n\n" for e in events).encode()


class TopicGuardMiddleware:
    """ASGI middleware that pre-validates user messages with the guard agent.

    Intercepts POST /api/chat requests, extracts the last user message, and runs the
    guard agent to classify it. Off-topic questions get an instant refusal response
    without ever reaching the main agent — avoiding streaming retry issues.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("method") == "POST" and scope["path"] == "/api/chat":
            await self._handle_chat(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    async def _handle_chat(self, scope, receive, send):
        """Read the request body, check topic relevance, and either refuse or pass through."""
        # Buffer the full request body
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break

        user_text = extract_last_user_text(body)
        if user_text:
            try:
                check = await guard_agent.run(
                    f"Is this user question about weather, climate, or atmospheric conditions?\n\n{user_text}"
                )
                if not check.output.is_weather_related:
                    await self._send_refusal(send)
                    return
            except Exception:
                # If the guard agent fails, let the request through rather than blocking
                logger.exception("Guard agent failed, passing request through")

        # Pass through to the inner app, replaying the buffered body
        body_sent = False

        async def replay_receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)

    async def _send_refusal(self, send):
        """Send a canned off-topic refusal as a Vercel AI SSE response."""
        response_body = build_refusal_sse(REFUSAL_MESSAGE)
        await send({"type": "http.response.start", "status": 200, "headers": _SSE_HEADERS})
        await send({"type": "http.response.body", "body": response_body})


# Build the model selection dropdown for the web UI.
# The agent's default model is always included automatically by to_web().
# The string shorthand "openrouter:model_name" reads OPENROUTER_API_KEY from env.
_models: dict[str, str] = {
    "Minimax M2.1": "openrouter:minimax/minimax-m2.1",
    "Ministral 14B": "openrouter:mistralai/ministral-14b-2512",
    "Claude Haiku 4.5": "openrouter:anthropic/claude-haiku-4.5",
}

# Include the default model from env var with a readable label
_default_model = os.environ.get("OPENROUTER_MODEL")
if _default_model and f"openrouter:{_default_model}" not in _models.values():
    _label = _default_model.split("/")[-1].replace("-", " ").title()
    _models[f"{_label} (Default)"] = f"openrouter:{_default_model}"

_inner_app = agent.to_web(
    deps=WeatherDeps(http_client=create_http_client()),
    models=_models,
)

app = TopicGuardMiddleware(_inner_app)
