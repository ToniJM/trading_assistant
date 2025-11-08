"""Groq LLM client for AI agents"""
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from trading.infrastructure.logging import get_logger

# Load environment variables
load_dotenv()

logger = get_logger("llm.groq")


class GroqClient:
    """Client for Groq LLM API"""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """Initialize Groq client

        Args:
            api_key: Groq API key (default: from GROQ_API_KEY env var)
            model: Model name (default: llama-3.3-70b-versatile)
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY not found. Set it in .env file or pass as parameter."
            )

        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.client = Groq(api_key=self.api_key)

        logger.info(f"GroqClient initialized with model: {self.model}")

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send chat completion request to Groq

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters for Groq API

        Returns:
            Response dict with 'content', 'model', 'usage', etc.

        Raises:
            Exception: If API call fails
        """
        try:
            logger.debug(
                f"Sending chat request to Groq (model={self.model}, messages={len(messages)})"
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            # Extract response content
            content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

            logger.debug(
                f"Groq response received (tokens={usage['total_tokens']}, "
                f"content_length={len(content) if content else 0})"
            )

            return {
                "content": content,
                "model": response.model,
                "usage": usage,
                "finish_reason": response.choices[0].finish_reason,
            }

        except Exception as e:
            logger.error(f"Error calling Groq API: {e}", exc_info=True)
            raise

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send chat completion request with JSON response format

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (lower for more deterministic JSON)
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters

        Returns:
            Parsed JSON dict from response

        Raises:
            Exception: If API call fails or response is not valid JSON
        """
        import json

        # Add JSON format instruction to messages
        json_messages = messages + [
            {
                "role": "system",
                "content": "You must respond with valid JSON only. No markdown, no code blocks, just raw JSON.",
            }
        ]

        response = self.chat(
            messages=json_messages, temperature=temperature, max_tokens=max_tokens, **kwargs
        )

        content = response["content"]
        if not content:
            raise ValueError("Empty response from Groq API")

        # Try to extract JSON from response (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]  # Remove ```json
        if content.startswith("```"):
            content = content[3:]  # Remove ```
        if content.endswith("```"):
            content = content[:-3]  # Remove closing ```
        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {content[:200]}...")
            raise ValueError(f"Invalid JSON response from Groq: {e}") from e


# Singleton instance
_groq_client: GroqClient | None = None


def get_groq_client(api_key: str | None = None, model: str | None = None) -> GroqClient:
    """Get or create singleton Groq client instance

    Args:
        api_key: Optional API key (only used on first call)
        model: Optional model name (only used on first call)

    Returns:
        GroqClient instance
    """
    global _groq_client

    if _groq_client is None:
        _groq_client = GroqClient(api_key=api_key, model=model)

    return _groq_client

