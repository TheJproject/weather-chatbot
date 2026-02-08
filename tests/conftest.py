# ABOUTME: Shared test fixtures for the weather chatbot test suite.
# ABOUTME: Provides TestModel setup and mock HTTP client fixtures.

import pydantic_ai.models

# Prevent accidental LLM calls during testing
pydantic_ai.models.ALLOW_MODEL_REQUESTS = False
