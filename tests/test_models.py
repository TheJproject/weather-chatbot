# ABOUTME: Contract tests for Pydantic models used in weather data parsing.
# ABOUTME: Validates that models correctly parse, validate, and default weather API data.

from datetime import date, datetime

from src.models import DailyWeather, GeoLocation, HourlyWeather, WeatherResponse


class TestGeoLocation:
    def test_valid_location_parses(self):
        """GeoLocation accepts valid coordinate data.

        Implementation: Constructs a GeoLocation with all fields.
        Passing implies: The model correctly stores lat, lon, timezone, name, country.
        """
        loc = GeoLocation(
            latitude=55.6761, longitude=12.5683, timezone="Europe/Copenhagen", name="Copenhagen", country="Denmark"
        )
        assert loc.latitude == 55.6761
        assert loc.longitude == 12.5683
        assert loc.timezone == "Europe/Copenhagen"
        assert loc.name == "Copenhagen"
        assert loc.country == "Denmark"

    def test_country_is_optional(self):
        """GeoLocation works without country field.

        Implementation: Constructs a GeoLocation without country.
        Passing implies: country defaults to None when omitted.
        """
        loc = GeoLocation(latitude=0.0, longitude=0.0, timezone="UTC", name="Test")
        assert loc.country is None


class TestDailyWeather:
    def test_valid_daily_parses(self):
        """DailyWeather accepts a complete day of weather data.

        Implementation: Constructs DailyWeather with all fields populated.
        Passing implies: All daily weather fields are stored correctly.
        """
        day = DailyWeather(
            date=date(2025, 1, 15),
            temperature_2m_max=5.2,
            temperature_2m_min=-1.3,
            sunrise="2025-01-15T08:45",
            sunset="2025-01-15T16:00",
            sunshine_duration=18000.0,
            daylight_duration=26100.0,
            wind_speed_10m_max=12.5,
            precipitation_sum=2.1,
            weather_code=3,
        )
        assert day.date == date(2025, 1, 15)
        assert day.temperature_2m_max == 5.2
        assert day.temperature_2m_min == -1.3
        assert day.wind_speed_10m_max == 12.5
        assert day.weather_code == 3

    def test_optional_fields_default_to_none(self):
        """DailyWeather only requires date field.

        Implementation: Constructs DailyWeather with only the date.
        Passing implies: All optional fields default to None.
        """
        day = DailyWeather(date=date(2025, 6, 1))
        assert day.temperature_2m_max is None
        assert day.sunrise is None
        assert day.precipitation_sum is None


class TestHourlyWeather:
    def test_valid_hourly_parses(self):
        """HourlyWeather accepts a complete hourly observation.

        Implementation: Constructs HourlyWeather with all fields.
        Passing implies: All hourly weather fields are stored correctly.
        """
        hour = HourlyWeather(
            time=datetime(2025, 1, 15, 12, 0),
            temperature_2m=3.5,
            wind_speed_10m=8.2,
            precipitation=0.0,
            weather_code=1,
            is_day=1,
        )
        assert hour.time == datetime(2025, 1, 15, 12, 0)
        assert hour.temperature_2m == 3.5
        assert hour.is_day == 1

    def test_optional_fields_default_to_none(self):
        """HourlyWeather only requires time field.

        Implementation: Constructs HourlyWeather with only the time.
        Passing implies: All optional fields default to None.
        """
        hour = HourlyWeather(time=datetime(2025, 1, 15, 12, 0))
        assert hour.temperature_2m is None
        assert hour.wind_speed_10m is None


class TestWeatherResponse:
    def test_valid_response_with_daily(self):
        """WeatherResponse holds coordinate info and daily weather list.

        Implementation: Constructs a WeatherResponse with one daily entry.
        Passing implies: The response correctly associates location with weather data.
        """
        resp = WeatherResponse(
            latitude=55.68,
            longitude=12.57,
            timezone="Europe/Copenhagen",
            daily=[DailyWeather(date=date(2025, 1, 15), temperature_2m_max=5.0)],
        )
        assert resp.latitude == 55.68
        assert len(resp.daily) == 1
        assert resp.daily[0].temperature_2m_max == 5.0

    def test_empty_lists_by_default(self):
        """WeatherResponse defaults to empty daily and hourly lists.

        Implementation: Constructs a WeatherResponse without daily or hourly.
        Passing implies: Lists default to empty, not None.
        """
        resp = WeatherResponse(latitude=0.0, longitude=0.0, timezone="UTC")
        assert resp.daily == []
        assert resp.hourly == []
