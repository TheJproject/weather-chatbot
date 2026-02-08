# ABOUTME: Dependency container for the weather agent using Pydantic BaseModel.
# ABOUTME: Holds the httpx.AsyncClient used by tools to call weather APIs.

import httpx
from pydantic import BaseModel, ConfigDict


class WeatherDeps(BaseModel):
    """Dependencies injected into agent tools via RunContext."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    http_client: httpx.AsyncClient
