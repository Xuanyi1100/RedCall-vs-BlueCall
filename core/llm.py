"""LLM abstraction layer for the multi-agent system."""

import os
from functools import lru_cache

from langchain_openai import ChatOpenAI


@lru_cache(maxsize=1)
def get_llm(
    model: str | None = None,
    temperature: float = 0.7,
) -> ChatOpenAI:
    """
    Get a configured LLM instance with automatic fallback.
    
    Priority:
    1. OpenAI (if OPENAI_API_KEY is set)
    2. DeepSeek (if DEEPSEEK_API_KEY is set)
    
    Args:
        model: The model to use. If None, uses default for the provider.
               - OpenAI default: "gpt-4o-mini"
               - DeepSeek default: "deepseek-chat"
        temperature: Sampling temperature for generation.
    
    Returns:
        Configured ChatOpenAI instance (works with OpenAI-compatible APIs).
    
    Raises:
        ValueError: If neither OPENAI_API_KEY nor DEEPSEEK_API_KEY is set.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    
    if openai_key:
        # Use OpenAI
        return ChatOpenAI(
            model=model or "gpt-4o-mini",
            api_key=openai_key,
            temperature=temperature,
        )
    elif deepseek_key:
        # Use DeepSeek (OpenAI-compatible API)
        return ChatOpenAI(
            model=model or "deepseek-chat",
            api_key=deepseek_key,
            base_url="https://api.deepseek.com",
            temperature=temperature,
        )
    else:
        raise ValueError(
            "No API key found. Please set either OPENAI_API_KEY or DEEPSEEK_API_KEY "
            "in your .env file or environment."
        )
