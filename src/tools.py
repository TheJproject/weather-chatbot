# ABOUTME: Agent tool definitions for weather data retrieval.
# ABOUTME: Registers geocode, forecast, and historical tools on the agent via decorators.

from datetime import date

from pydantic_ai import RunContext

from src.agent import agent
from src.deps import WeatherDeps
from src.weather_service import geocode, get_forecast, get_historical_weather


@agent.tool
async def get_location_coordinates(ctx: RunContext[WeatherDeps], city_name: str) -> dict:
    """Look up the latitude, longitude, and timezone for a city name.

    Always call this first before fetching weather data.

    Args:
        ctx: Agent run context with HTTP client.
        city_name: Name of the city to geocode (e.g. "Copenhagen", "London").
    """
    result = await geocode(ctx.deps.http_client, city_name)
    if result is None:
        return {"error": f"Could not find location: {city_name}"}
    return result.model_dump()


@agent.tool
async def get_weather_forecast(
    ctx: RunContext[WeatherDeps],
    latitude: float,
    longitude: float,
    timezone: str,
    forecast_days: int = 7,
) -> dict:
    """Get current weather and forecast for a location.

    Use this for today's weather and forecasts up to 16 days ahead.

    Args:
        ctx: Agent run context with HTTP client.
        latitude: Location latitude from geocoding.
        longitude: Location longitude from geocoding.
        timezone: Location timezone from geocoding (e.g. "Europe/Copenhagen").
        forecast_days: Number of days to forecast (1-16, default 7).
    """
    result = await get_forecast(ctx.deps.http_client, latitude, longitude, timezone, forecast_days)
    return result.model_dump(mode="json")


@agent.tool
async def get_historical_weather_data(
    ctx: RunContext[WeatherDeps],
    latitude: float,
    longitude: float,
    timezone: str,
    start_date: str,
    end_date: str,
) -> dict:
    """Get historical weather data for a location and date range.

    Use this for past weather data and comparisons. Data available from 1940 to ~5 days ago.

    Args:
        ctx: Agent run context with HTTP client.
        latitude: Location latitude from geocoding.
        longitude: Location longitude from geocoding.
        timezone: Location timezone from geocoding (e.g. "Europe/Copenhagen").
        start_date: Start date in ISO format (YYYY-MM-DD).
        end_date: End date in ISO format (YYYY-MM-DD).
    """
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    result = await get_historical_weather(ctx.deps.http_client, latitude, longitude, timezone, start, end)
    return result.model_dump(mode="json")
