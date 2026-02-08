# ABOUTME: Integration tests for the weather agent and tool registration.
# ABOUTME: Uses TestModel to verify tools are registered and callable without real LLM calls.

from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models.test import TestModel

from src.agent import agent, guard_agent
from src.deps import WeatherDeps


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

    def test_agent_has_output_validator(self):
        """Agent has an output validator registered for weather topic enforcement.

        Implementation: Inspects the agent's output validators list.
        Passing implies: The guard agent output validator is registered.
        """
        assert len(agent._output_validators) >= 1

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

        # The guard agent has output_type=TopicCheck
        assert guard_agent._output_schema is not None


# TestModel override for the guard agent that approves weather responses
_guard_approve = TestModel(custom_output_args={"is_weather_related": True, "reason": "weather content"})
_guard_reject = TestModel(custom_output_args={"is_weather_related": False, "reason": "off-topic content"})


class TestAgentExecution:
    @pytest.mark.asyncio
    async def test_agent_runs_with_test_model(self):
        """Agent executes without errors using TestModel.

        Implementation: Runs the agent with TestModel and mock deps, guard agent approves output.
        Passing implies: Tool chain (geocode + forecast) works end-to-end with mocked HTTP.
        """
        deps = _mock_deps()
        # Override both the main agent and the guard agent
        with agent.override(model=TestModel(call_tools=["get_location_coordinates", "get_weather_forecast"])):
            with guard_agent.override(model=_guard_approve):
                result = await agent.run("What is the weather in Copenhagen?", deps=deps)
                assert result.output is not None

    @pytest.mark.asyncio
    async def test_historical_tool_handles_bad_dates(self):
        """Historical tool raises ModelRetry for invalid dates instead of crashing.

        Implementation: Runs agent with TestModel calling historical tool. TestModel passes
        placeholder 'a' for date strings, which triggers ValueError → ModelRetry.
        After max retries, raises UnexpectedModelBehavior (not raw ValueError).
        Passing implies: Bad date inputs are wrapped in ModelRetry for graceful retry handling.
        """
        deps = _mock_deps()
        with agent.override(model=TestModel(call_tools=["get_historical_weather_data"])):
            with guard_agent.override(model=_guard_approve):
                with pytest.raises(UnexpectedModelBehavior, match="get_historical_weather_data"):
                    await agent.run("What was the weather last year?", deps=deps)

    @pytest.mark.asyncio
    async def test_output_validator_rejects_off_topic(self):
        """Output validator rejects responses when guard agent classifies them as off-topic.

        Implementation: Runs agent with guard agent set to reject. After retries exhaust,
        raises UnexpectedModelBehavior.
        Passing implies: The guard agent output validator enforces topic boundaries.
        """
        deps = _mock_deps()
        with agent.override(model=TestModel(call_tools=[])):
            with guard_agent.override(model=_guard_reject):
                with pytest.raises(UnexpectedModelBehavior):
                    await agent.run("What is the capital of France?", deps=deps)
