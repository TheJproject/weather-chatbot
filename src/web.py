# ABOUTME: ASGI web entry point for the weather chatbot UI.
# ABOUTME: Creates a Starlette app via agent.to_web() for browser-based chat.

import httpx

from src.agent import agent
from src.deps import WeatherDeps

app = agent.to_web(deps=WeatherDeps(http_client=httpx.AsyncClient()))
