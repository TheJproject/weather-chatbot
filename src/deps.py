# ABOUTME: Dependency container for the weather agent using Pydantic BaseModel.
# ABOUTME: Holds the httpx.AsyncClient used by tools to call weather APIs.

import httpx
from pydantic import BaseModel, ConfigDict
from pydantic_ai.retries import AsyncTenacityTransport, RetryConfig, wait_retry_after
from tenacity import retry_if_exception_type, stop_after_attempt


class WeatherDeps(BaseModel):
    """Dependencies injected into agent tools via RunContext."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    http_client: httpx.AsyncClient


def create_http_client() -> httpx.AsyncClient:
    """Create an httpx client with tenacity retry on transient HTTP errors.

    Retries connection errors, timeouts, and 429/5xx responses with exponential backoff.
    """
    transport = AsyncTenacityTransport(
        RetryConfig(
            retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError)),
            wait=wait_retry_after(max_wait=30),
            stop=stop_after_attempt(3),
            reraise=True,
        ),
        validate_response=lambda r: r.raise_for_status(),
    )
    return httpx.AsyncClient(transport=transport)
