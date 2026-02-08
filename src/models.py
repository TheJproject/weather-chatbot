# ABOUTME: Pydantic BaseModels for weather API responses and geocoding data.
# ABOUTME: Defines structured types for Open-Meteo API data used throughout the app.

from datetime import date, datetime

from pydantic import BaseModel


class GeoLocation(BaseModel):
    """Geocoded location with coordinates and metadata."""

    latitude: float
    longitude: float
    timezone: str
    name: str
    country: str | None = None


class DailyWeather(BaseModel):
    """One day of weather data from Open-Meteo daily endpoint."""

    date: date
    temperature_2m_max: float | None = None
    temperature_2m_min: float | None = None
    sunrise: str | None = None
    sunset: str | None = None
    sunshine_duration: float | None = None
    daylight_duration: float | None = None
    wind_speed_10m_max: float | None = None
    precipitation_sum: float | None = None
    weather_code: int | None = None


class HourlyWeather(BaseModel):
    """One hour of weather data from Open-Meteo hourly endpoint."""

    time: datetime
    temperature_2m: float | None = None
    wind_speed_10m: float | None = None
    precipitation: float | None = None
    weather_code: int | None = None
    is_day: int | None = None


class WeatherResponse(BaseModel):
    """Parsed response from Open-Meteo forecast or archive endpoint."""

    latitude: float
    longitude: float
    timezone: str
    daily: list[DailyWeather] = []
    hourly: list[HourlyWeather] = []
