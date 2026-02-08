# ABOUTME: Integration tests for the weather agent and tool registration.
# ABOUTME: Uses TestModel to verify tools are registered and callable without real LLM calls.

from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models.test import TestModel

from src.agent import agent, guard_agent
from src.deps import WeatherDeps
from src.web import build_refusal_sse, extract_last_user_text


def _mock_deps() -> WeatherDeps:
    """Create WeatherDeps with a mock HTTP client that returns geocoding + forecast data."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    # Return geocoding result first, then forecast result for subsequent calls
    geocode_response = httpx.Response(
        200,
        json={
            "results": [
                {
                    "latitude": 55.6761,
                    "longitude": 12.5683,
                    "timezone": "Europe/Copenhagen",
                    "name": "Copenhagen",
                    "country": "Denmark",
                }
            ]
        },
        request=httpx.Request("GET", "https://test"),
    )
    forecast_response = httpx.Response(
        200,
        json={
            "latitude": 55.68,
            "longitude": 12.57,
            "timezone": "Europe/Copenhagen",
            "daily": {
                "time": ["2025-01-15"],
                "temperature_2m_max": [5.0],
                "temperature_2m_min": [-1.0],
                "wind_speed_10m_max": [12.0],
                "precipitation_sum": [0.0],
                "weather_code": [1],
            },
            "hourly": {},
        },
        request=httpx.Request("GET", "https://test"),
    )
    mock_client.get.side_effect = [geocode_response, forecast_response, forecast_response]
    return WeatherDeps(http_client=mock_client)


class TestAgentToolRegistration:
    def test_agent_has_expected_tools(self):
        """Agent has all three weather tools registered.

        Implementation: Inspects the agent's internal tool registry.
        Passing implies: All tool decorators executed and registered correctly.
        """
        tool_names = set(agent._function_toolset.tools.keys())
        assert "get_location_coordinates" in tool_names
        assert "get_weather_forecast" in tool_names
        assert "get_historical_weather_data" in tool_names

    def test_agent_has_three_tools(self):
        """Agent has exactly three tools registered.

        Implementation: Counts the tools in the agent's registry.
        Passing implies: No extra or missing tool registrations.
        """
        assert len(agent._function_toolset.tools) == 3


class TestAgentConfiguration:
    def test_agent_has_retries_configured(self):
        """Agent is configured with retries=2 for tool call retries.

        Implementation: Inspects the agent's internal retry configuration.
        Passing implies: Failed tool calls will be retried up to 2 times.
        """
        assert agent._max_tool_retries == 2

    def test_system_prompt_includes_topic_restriction(self):
        """System prompt instructs the agent to only answer weather questions.

        Implementation: Checks the system prompt tuple for topic restriction text.
        Passing implies: The guardrail rule for off-topic refusal is present.
        """
        prompt_text = " ".join(agent._system_prompts)
        assert "ONLY answer questions about weather" in prompt_text

    def test_system_prompt_includes_prompt_injection_defense(self):
        """System prompt instructs the agent to refuse prompt injection attempts.

        Implementation: Checks the system prompt for prompt injection defense text.
        Passing implies: The guardrail rules for manipulation refusal are present.
        """
        prompt_text = " ".join(agent._system_prompts)
        assert "prompt injection" in prompt_text
        assert "ignore your system prompt" in prompt_text

    def test_guard_agent_uses_structured_output(self):
        """Guard agent returns TopicCheck with is_weather_related and reason fields.

        Implementation: Inspects the guard agent's output type.
        Passing implies: The guard agent is configured to return structured classification.
        """
        assert guard_agent._output_schema is not None


class TestAgentExecution:
    @pytest.mark.asyncio
    async def test_agent_runs_with_test_model(self):
        """Agent executes without errors using TestModel.

        Implementation: Runs the agent with TestModel and mock deps.
        Passing implies: Tool chain (geocode + forecast) works end-to-end with mocked HTTP.
        """
        deps = _mock_deps()
        with agent.override(model=TestModel(call_tools=["get_location_coordinates", "get_weather_forecast"])):
            result = await agent.run("What is the weather in Copenhagen?", deps=deps)
            assert result.output is not None

    @pytest.mark.asyncio
    async def test_historical_tool_handles_bad_dates(self):
        """Historical tool raises ModelRetry for invalid dates instead of crashing.

        Implementation: Runs agent with TestModel calling historical tool. TestModel passes
        placeholder 'a' for date strings, which triggers ValueError -> ModelRetry.
        After max retries, raises UnexpectedModelBehavior (not raw ValueError).
        Passing implies: Bad date inputs are wrapped in ModelRetry for graceful retry handling.
        """
        deps = _mock_deps()
        with agent.override(model=TestModel(call_tools=["get_historical_weather_data"])):
            with pytest.raises(UnexpectedModelBehavior, match="get_historical_weather_data"):
                await agent.run("What was the weather last year?", deps=deps)


class TestInputGuard:
    def test_extract_user_text_from_chat_request(self):
        """extract_last_user_text parses the last user message from Vercel AI protocol.

        Implementation: Passes a realistic Vercel AI chat request body.
        Passing implies: The function correctly extracts user text from the protocol format.
        """
        body = b'{"messages":[{"role":"user","parts":[{"type":"text","text":"Hello weather"}]}]}'
        assert extract_last_user_text(body) == "Hello weather"

    def test_extract_user_text_returns_last_message(self):
        """extract_last_user_text returns the most recent user message.

        Implementation: Passes a multi-message conversation.
        Passing implies: The function finds the last user message, not the first.
        """
        body = b'{"messages":[{"role":"user","parts":[{"type":"text","text":"first"}]},{"role":"assistant","parts":[{"type":"text","text":"reply"}]},{"role":"user","parts":[{"type":"text","text":"second"}]}]}'
        assert extract_last_user_text(body) == "second"

    def test_extract_user_text_returns_none_for_invalid_json(self):
        """extract_last_user_text returns None for malformed input.

        Implementation: Passes invalid JSON.
        Passing implies: The function handles parse errors gracefully.
        """
        assert extract_last_user_text(b"not json") is None

    def test_extract_user_text_returns_none_for_no_messages(self):
        """extract_last_user_text returns None when no user messages exist.

        Implementation: Passes a request with no messages.
        Passing implies: The function handles missing data gracefully.
        """
        assert extract_last_user_text(b'{"messages":[]}') is None

    def test_build_refusal_sse_contains_text(self):
        """build_refusal_sse produces a valid SSE response with the refusal text.

        Implementation: Checks the SSE response body for required protocol events.
        Passing implies: The canned response follows the Vercel AI Data Stream Protocol.
        """
        result = build_refusal_sse("Sorry, weather only!")
        text = result.decode()
        assert "text-start" in text
        assert "text-delta" in text
        assert "Sorry, weather only!" in text
        assert "text-end" in text
        assert "finish-step" in text
        assert "[DONE]" in text

    def test_build_refusal_sse_is_valid_sse_format(self):
        """build_refusal_sse produces properly formatted SSE events.

        Implementation: Checks that each event starts with 'data: ' and ends with double newlines.
        Passing implies: The response is parseable by SSE clients.
        """
        result = build_refusal_sse("test")
        text = result.decode()
        for line in text.strip().split("\n\n"):
            assert line.startswith("data: ")
