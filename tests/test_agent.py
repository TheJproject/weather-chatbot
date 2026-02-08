# ABOUTME: Integration tests for the weather agent and tool registration.
# ABOUTME: Uses TestModel to verify tools are registered and callable without real LLM calls.

from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic_ai.models.test import TestModel

from src.agent import agent
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


class TestAgentExecution:
    @pytest.mark.asyncio
    async def test_agent_runs_with_test_model(self):
        """Agent executes without errors using TestModel.

        Implementation: Runs the agent with TestModel and mock deps.
        Passing implies: Tool chain (geocode + forecast) works end-to-end with mocked HTTP.
        """
        deps = _mock_deps()
        # Limit to geocode + forecast tools; historical needs valid ISO dates that TestModel can't generate
        with agent.override(model=TestModel(call_tools=["get_location_coordinates", "get_weather_forecast"])):
            result = await agent.run("What is the weather in Copenhagen?", deps=deps)
            assert result.output is not None
