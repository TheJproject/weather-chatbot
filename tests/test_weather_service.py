# ABOUTME: Contract tests for the weather service layer.
# ABOUTME: Validates geocoding, forecast, historical API calls and data parsing with mocked HTTP.

from datetime import date
from unittest.mock import AsyncMock

import httpx
import pytest

from src.models import DailyWeather
from src.weather_service import geocode, get_forecast, get_historical_weather, parse_daily_data, parse_hourly_data


def _mock_client(json_data: dict, status_code: int = 200) -> httpx.AsyncClient:
    """Create a mock httpx.AsyncClient that returns the given JSON response."""
    mock = AsyncMock(spec=httpx.AsyncClient)
    response = httpx.Response(status_code=status_code, json=json_data, request=httpx.Request("GET", "https://test"))
    mock.get.return_value = response
    return mock


class TestGeocode:
    @pytest.mark.asyncio
    async def test_resolves_known_city(self):
        """Geocode returns a GeoLocation for a known city.

        Implementation: Mocks the geocoding API to return Copenhagen data.
        Passing implies: The service correctly parses geocoding results into GeoLocation.
        """
        client = _mock_client(
            {
                "results": [
                    {
                        "latitude": 55.6761,
                        "longitude": 12.5683,
                        "timezone": "Europe/Copenhagen",
                        "name": "Copenhagen",
                        "country": "Denmark",
                    }
                ]
            }
        )
        result = await geocode(client, "Copenhagen")

        assert result is not None
        assert result.name == "Copenhagen"
        assert result.latitude == 55.6761
        assert result.longitude == 12.5683
        assert result.timezone == "Europe/Copenhagen"
        assert result.country == "Denmark"

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_city(self):
        """Geocode returns None when the city is not found.

        Implementation: Mocks the geocoding API to return empty results.
        Passing implies: The service handles missing results gracefully.
        """
        client = _mock_client({"results": []})
        result = await geocode(client, "Xyzzyville")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_no_results_key(self):
        """Geocode returns None when the response has no 'results' key.

        Implementation: Mocks the geocoding API to return an empty object.
        Passing implies: The service handles malformed responses gracefully.
        """
        client = _mock_client({})
        result = await geocode(client, "Nowhere")
        assert result is None


class TestParseDailyData:
    def test_zips_columns_into_rows(self):
        """parse_daily_data converts Open-Meteo column arrays into DailyWeather rows.

        Implementation: Provides a column-oriented dict matching Open-Meteo format.
        Passing implies: Each column value at index i maps to the correct DailyWeather field.
        """
        raw = {
            "time": ["2025-01-15", "2025-01-16"],
            "temperature_2m_max": [5.2, 6.1],
            "temperature_2m_min": [-1.3, 0.2],
            "wind_speed_10m_max": [12.5, 8.0],
            "precipitation_sum": [2.1, 0.0],
            "weather_code": [3, 0],
            "sunrise": ["2025-01-15T08:45", "2025-01-16T08:44"],
            "sunset": ["2025-01-15T16:00", "2025-01-16T16:02"],
            "sunshine_duration": [18000.0, 22000.0],
            "daylight_duration": [26100.0, 26200.0],
        }
        result = parse_daily_data(raw)

        assert len(result) == 2
        assert isinstance(result[0], DailyWeather)
        assert result[0].date == date(2025, 1, 15)
        assert result[0].temperature_2m_max == 5.2
        assert result[0].wind_speed_10m_max == 12.5
        assert result[1].date == date(2025, 1, 16)
        assert result[1].precipitation_sum == 0.0

    def test_empty_time_returns_empty_list(self):
        """parse_daily_data returns empty list when no time data is present.

        Implementation: Passes empty dict to parser.
        Passing implies: Parser handles missing data without errors.
        """
        assert parse_daily_data({}) == []
        assert parse_daily_data({"time": []}) == []


class TestParseHourlyData:
    def test_zips_columns_into_rows(self):
        """parse_hourly_data converts Open-Meteo hourly columns into HourlyWeather rows.

        Implementation: Provides a column-oriented dict with hourly data.
        Passing implies: Each column value maps to the correct HourlyWeather field.
        """
        raw = {
            "time": ["2025-01-15T12:00", "2025-01-15T13:00"],
            "temperature_2m": [3.5, 4.0],
            "wind_speed_10m": [8.2, 7.5],
            "precipitation": [0.0, 0.1],
            "weather_code": [1, 2],
            "is_day": [1, 1],
        }
        result = parse_hourly_data(raw)

        assert len(result) == 2
        assert result[0].temperature_2m == 3.5
        assert result[1].wind_speed_10m == 7.5


class TestGetForecast:
    @pytest.mark.asyncio
    async def test_returns_weather_response(self):
        """get_forecast returns a WeatherResponse with daily data.

        Implementation: Mocks the forecast API with a minimal valid response.
        Passing implies: The service correctly calls the API and parses the response.
        """
        client = _mock_client(
            {
                "latitude": 55.68,
                "longitude": 12.57,
                "timezone": "Europe/Copenhagen",
                "daily": {
                    "time": ["2025-01-15"],
                    "temperature_2m_max": [5.0],
                    "temperature_2m_min": [-1.0],
                },
                "hourly": {},
            }
        )
        result = await get_forecast(client, 55.68, 12.57, "Europe/Copenhagen", forecast_days=1)

        assert result.latitude == 55.68
        assert len(result.daily) == 1
        assert result.daily[0].temperature_2m_max == 5.0

    @pytest.mark.asyncio
    async def test_sends_correct_params(self):
        """get_forecast sends the expected query parameters to the API.

        Implementation: Inspects the mock client's call args.
        Passing implies: The service constructs correct API requests.
        """
        client = _mock_client({"latitude": 0, "longitude": 0, "timezone": "UTC", "daily": {}, "hourly": {}})
        await get_forecast(client, 55.68, 12.57, "Europe/Copenhagen", forecast_days=3)

        params = client.get.call_args.kwargs["params"]
        assert params["latitude"] == 55.68
        assert params["longitude"] == 12.57
        assert params["timezone"] == "Europe/Copenhagen"
        assert params["forecast_days"] == 3


class TestGetHistoricalWeather:
    @pytest.mark.asyncio
    async def test_returns_weather_response(self):
        """get_historical_weather returns a WeatherResponse with daily data.

        Implementation: Mocks the archive API with a minimal valid response.
        Passing implies: The service correctly calls the archive API and parses the response.
        """
        client = _mock_client(
            {
                "latitude": 55.68,
                "longitude": 12.57,
                "timezone": "Europe/Copenhagen",
                "daily": {
                    "time": ["2024-01-15"],
                    "temperature_2m_max": [3.0],
                    "temperature_2m_min": [-2.0],
                },
                "hourly": {},
            }
        )
        result = await get_historical_weather(
            client, 55.68, 12.57, "Europe/Copenhagen", date(2024, 1, 1), date(2024, 1, 31)
        )

        assert result.latitude == 55.68
        assert len(result.daily) == 1
        assert result.daily[0].temperature_2m_max == 3.0

    @pytest.mark.asyncio
    async def test_sends_date_range_params(self):
        """get_historical_weather sends start_date and end_date as ISO strings.

        Implementation: Inspects the mock client's call args for date params.
        Passing implies: The service correctly formats date range in API requests.
        """
        client = _mock_client({"latitude": 0, "longitude": 0, "timezone": "UTC", "daily": {}, "hourly": {}})
        await get_historical_weather(client, 55.68, 12.57, "Europe/Copenhagen", date(2024, 1, 1), date(2024, 1, 31))

        params = client.get.call_args.kwargs["params"]
        assert params["start_date"] == "2024-01-01"
        assert params["end_date"] == "2024-01-31"
