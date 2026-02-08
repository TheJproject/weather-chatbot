# ABOUTME: Service layer for Open-Meteo API calls and response parsing.
# ABOUTME: Handles geocoding, forecast, and historical weather data retrieval.

from datetime import date, datetime

import httpx

from src.models import DailyWeather, GeoLocation, HourlyWeather, WeatherResponse

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

DAILY_PARAMS = (
    "temperature_2m_max,temperature_2m_min,sunrise,sunset,"
    "sunshine_duration,daylight_duration,wind_speed_10m_max,"
    "precipitation_sum,weather_code"
)

HOURLY_PARAMS = "temperature_2m,wind_speed_10m,precipitation,weather_code,is_day"


async def geocode(client: httpx.AsyncClient, city_name: str) -> GeoLocation | None:
    """Geocode a city name to coordinates using Open-Meteo geocoding API."""
    resp = await client.get(GEOCODING_URL, params={"name": city_name, "count": 1, "language": "en"})
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results")
    if not results:
        return None

    r = results[0]
    return GeoLocation(
        latitude=r["latitude"],
        longitude=r["longitude"],
        timezone=r.get("timezone", "UTC"),
        name=r["name"],
        country=r.get("country"),
    )


async def get_forecast(
    client: httpx.AsyncClient,
    latitude: float,
    longitude: float,
    timezone: str,
    forecast_days: int = 7,
) -> WeatherResponse:
    """Fetch weather forecast from Open-Meteo forecast API."""
    resp = await client.get(
        FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "daily": DAILY_PARAMS,
            "hourly": HOURLY_PARAMS,
            "forecast_days": forecast_days,
        },
    )
    resp.raise_for_status()
    data = resp.json()

    return WeatherResponse(
        latitude=data["latitude"],
        longitude=data["longitude"],
        timezone=data.get("timezone", timezone),
        daily=parse_daily_data(data.get("daily", {})),
        hourly=parse_hourly_data(data.get("hourly", {})),
    )


async def get_historical_weather(
    client: httpx.AsyncClient,
    latitude: float,
    longitude: float,
    timezone: str,
    start_date: date,
    end_date: date,
) -> WeatherResponse:
    """Fetch historical weather data from Open-Meteo archive API."""
    resp = await client.get(
        ARCHIVE_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "daily": DAILY_PARAMS,
            "hourly": HOURLY_PARAMS,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )
    resp.raise_for_status()
    data = resp.json()

    return WeatherResponse(
        latitude=data["latitude"],
        longitude=data["longitude"],
        timezone=data.get("timezone", timezone),
        daily=parse_daily_data(data.get("daily", {})),
        hourly=parse_hourly_data(data.get("hourly", {})),
    )


def parse_daily_data(raw: dict) -> list[DailyWeather]:
    """Parse Open-Meteo column-oriented daily data into row-oriented DailyWeather objects."""
    dates = raw.get("time", [])
    if not dates:
        return []

    result = []
    for i, d in enumerate(dates):
        result.append(
            DailyWeather(
                date=date.fromisoformat(d),
                temperature_2m_max=_get_at(raw, "temperature_2m_max", i),
                temperature_2m_min=_get_at(raw, "temperature_2m_min", i),
                sunrise=_get_at(raw, "sunrise", i),
                sunset=_get_at(raw, "sunset", i),
                sunshine_duration=_get_at(raw, "sunshine_duration", i),
                daylight_duration=_get_at(raw, "daylight_duration", i),
                wind_speed_10m_max=_get_at(raw, "wind_speed_10m_max", i),
                precipitation_sum=_get_at(raw, "precipitation_sum", i),
                weather_code=_get_at(raw, "weather_code", i),
            )
        )
    return result


def parse_hourly_data(raw: dict) -> list[HourlyWeather]:
    """Parse Open-Meteo column-oriented hourly data into row-oriented HourlyWeather objects."""
    times = raw.get("time", [])
    if not times:
        return []

    result = []
    for i, t in enumerate(times):
        result.append(
            HourlyWeather(
                time=datetime.fromisoformat(t),
                temperature_2m=_get_at(raw, "temperature_2m", i),
                wind_speed_10m=_get_at(raw, "wind_speed_10m", i),
                precipitation=_get_at(raw, "precipitation", i),
                weather_code=_get_at(raw, "weather_code", i),
                is_day=_get_at(raw, "is_day", i),
            )
        )
    return result


def _get_at(data: dict, key: str, index: int):
    """Safely get value at index from a column array, returning None if missing."""
    col = data.get(key)
    if col is None or index >= len(col):
        return None
    return col[index]
