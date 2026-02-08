# ABOUTME: ASGI web entry point for the weather chatbot UI.
# ABOUTME: Creates a Starlette app via agent.to_web() for browser-based chat with model selection.

import os

from src.agent import agent
from src.deps import WeatherDeps, create_http_client

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

app = agent.to_web(
    deps=WeatherDeps(http_client=create_http_client()),
    models=_models,
)
