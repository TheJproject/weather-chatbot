# Weather & Climate AI Chatbot - Implementation Summary

## Architecture Overview

```
User (browser) --> Pydantic AI Web UI --> Agent (LLM via OpenRouter) --> Tools --> Weather Service --> Open-Meteo APIs
                   (agent.to_web())        |                              |
                                      System Prompt               WeatherDeps
                                      + Dynamic Date              (httpx.AsyncClient)
```

The project follows a layered architecture with clear separation of concerns:

| Layer | File | Responsibility |
|-------|------|----------------|
| **Models** | `src/models.py` | Pydantic BaseModels for API data (GeoLocation, DailyWeather, HourlyWeather, WeatherResponse) |
| **Service** | `src/weather_service.py` | Open-Meteo API calls + column-to-row data parsing |
| **Dependencies** | `src/deps.py` | Dependency injection container (httpx.AsyncClient) |
| **Agent** | `src/agent.py` | LLM configuration, system prompt, dynamic date injection |
| **Tools** | `src/tools.py` | Three `@agent.tool` functions: geocode, forecast, historical |
| **Web** | `src/web.py` | ASGI entry point via `agent.to_web()` |

The LLM decides which tools to call and in what order. A typical flow is: geocode a city first, then fetch forecast or historical data, then compose the answer. The LLM does the comparison math itself (e.g. "how much longer is daylight today vs the solstice").

## Thought Process and Decisions

### Why Pydantic AI?

I chose Pydantic AI because it provides a clean, type-safe framework for building LLM agents with tool calling. The `@agent.tool` decorator pattern keeps tool definitions close to the agent, and `agent.to_web()` gives a polished browser UI with zero frontend code. This let me focus entirely on the backend logic and data layer.

### Why three tools and not more?

I followed the KISS principle. Three tools (geocode, forecast, historical) are the minimal set that covers all four example questions. The LLM handles the reasoning -- chaining tools, computing differences, and formatting the answer. Adding more specialized tools (e.g. "compare two periods") would have duplicated logic that the LLM already does well.

### Why a separate service layer?

The weather service (`weather_service.py`) is a pure data layer with no LLM awareness. This makes it independently testable with mocked HTTP, and the tools become thin wrappers that just delegate to the service. If I needed to swap Open-Meteo for another provider, only the service layer changes.

### Why OpenRouter?

OpenRouter provides access to many models through a single API key. Pydantic AI has native OpenRouter support (`OpenRouterModel` + `OpenRouterProvider`), which avoids the deprecation warnings from using `OpenAIModel` for non-OpenAI providers. The model choice is configurable via the `OPENROUTER_MODEL` environment variable.

### Why contract-based tests?

Tests define *what* the code must do, not *how*. Each test has a docstring explaining the contract: what behavior it validates, how the test works, and what passing implies. This means the implementation can be refactored freely as long as the contracts hold. External systems (httpx) are mocked, but internal modules are never mocked.

### Column-to-row parsing

Open-Meteo returns data in column-oriented format (`{"time": [...], "temperature_2m_max": [...]}`). The `parse_daily_data` and `parse_hourly_data` functions zip these columns into row-oriented Pydantic models, which are much easier for the LLM to reason about.

### Dynamic date injection

The `@agent.instructions` decorator injects today's date into the system prompt on every request. This is essential because questions like "is tomorrow going to be cold?" or "this January vs last January" require the LLM to know the current date.

## How the Four Example Questions Are Answered

| Question | Tool Chain | What the LLM Does |
|----------|------------|-------------------|
| Daytime duration vs shortest day | `geocode` -> `forecast` (today) + `historical` (Dec 21) | Compares daylight_duration fields, converts seconds to hours/minutes |
| January temperature vs last year | `geocode` -> `historical` (Jan this year) + `historical` (Jan last year) | Computes average temps, builds comparison table |
| Is wind in Copenhagen common? | `geocode` -> `forecast` (today) + `historical` (same period last year) | Compares wind speeds, explains seasonal norms |
| Is tomorrow cold? | `geocode` -> `forecast` (tomorrow) | Reads forecast data and gives a concise weather summary |

## How Happy Am I With the Outcome?

Very happy. All four example questions from the task are answered correctly with real data. The architecture is clean and each layer has a clear responsibility. The test suite (21 tests) gives confidence that refactoring won't break anything. The web UI works out of the box with `agent.to_web()`, which saved significant time that would have been spent on frontend work.

The LLM produces well-formatted responses with tables, bullet points, and contextual analysis -- not just raw numbers. It correctly chains tools (geocode first, then data retrieval) without explicit orchestration code.

## What Would Be the First Thing to Improve?

**Done -- implemented in the second iteration:**

1. **Retry logic with backoff** -- Tenacity-based `AsyncTenacityTransport` wraps the httpx client with exponential backoff for transient network errors (connection refused, timeouts, 429/5xx). Pydantic AI's `ModelRetry` provides tool-level retries with `retries=2`.
2. **Graceful error messages** -- All three tools catch `httpx.HTTPError` and `ValueError` and raise `ModelRetry` with descriptive messages, letting the LLM retry or relay the error to the user.
3. **Model selection** -- Web UI dropdown lets users choose between Minimax M2.1, Ministral 14B, Claude Haiku 4.5, and the default model via `to_web(models={...})`.
4. **Guardrails** -- System prompt rules 10-12 enforce weather-only topics and refuse prompt injection attempts.

**Remaining improvements:**

- **Caching** geocoding results and recent forecasts to reduce API calls and improve response time.
- **Streaming responses** so the user sees the answer being built in real-time rather than waiting for all tool calls to complete.
