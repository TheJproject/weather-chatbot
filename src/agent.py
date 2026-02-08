# ABOUTME: Pydantic AI agent definition for the weather chatbot.
# ABOUTME: Configures the LLM, system instructions, and imports tool registrations.

import os
from datetime import date

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from src.deps import WeatherDeps

load_dotenv()

model = OpenRouterModel(
    os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-5"),
    provider=OpenRouterProvider(api_key=os.environ.get("OPENROUTER_API_KEY", "")),
)

agent = Agent(
    model,
    deps_type=WeatherDeps,
    system_prompt=(
        "You are a weather and climate assistant. You answer questions about current weather, "
        "forecasts, and historical climate data for any location worldwide.\n\n"
        "When answering questions:\n"
        "1. Always geocode the city first to get coordinates and timezone.\n"
        "2. Use the forecast tool for current and future weather (up to 16 days ahead).\n"
        "3. Use the historical weather tool for past data and comparisons.\n"
        "4. When comparing periods (e.g. 'this January vs last January'), fetch both and compute the difference.\n"
        "5. For questions about daylight duration, sunrise/sunset, fetch the relevant dates.\n"
        "6. Present temperatures in Celsius, wind in km/h, precipitation in mm.\n"
        "7. Be concise but informative. Include relevant numbers.\n"
        "8. Sunshine duration from the API is in seconds — convert to hours when presenting.\n"
        "9. Daylight duration from the API is in seconds — convert to hours and minutes when presenting.\n"
    ),
)


@agent.instructions
def add_current_date(ctx: RunContext[WeatherDeps]) -> str:
    """Inject the current date so the LLM knows what 'today' and 'tomorrow' mean."""
    today = date.today()
    return f"Today's date is {today.isoformat()} ({today.strftime('%A')})."


# Import tools module to register @agent.tool decorators
import src.tools  # noqa: E402, F401
