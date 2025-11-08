"""Tests for GroqClient"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from trading.infrastructure.llm.groq_client import GroqClient, get_groq_client


@pytest.fixture
def mock_groq_api_key():
    """Mock GROQ_API_KEY environment variable"""
    with patch.dict(os.environ, {"GROQ_API_KEY": "test_api_key"}):
        yield "test_api_key"


@pytest.fixture
def mock_groq_client(mock_groq_api_key):
    """Create a GroqClient with mocked Groq API"""
    with patch("trading.infrastructure.llm.groq_client.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client

        # Mock chat completion response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "llama-3.3-70b-versatile"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        mock_client.chat.completions.create.return_value = mock_response

        client = GroqClient()
        client.client = mock_client
        yield client


def test_initialization_with_api_key(mock_groq_api_key):
    """Test GroqClient initialization with API key from env"""
    with patch("trading.infrastructure.llm.groq_client.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client

        client = GroqClient()

        assert client.api_key == "test_api_key"
        assert client.model == "llama-3.3-70b-versatile"  # Default
        mock_groq_class.assert_called_once_with(api_key="test_api_key")


def test_initialization_with_custom_api_key():
    """Test GroqClient initialization with custom API key"""
    with patch("trading.infrastructure.llm.groq_client.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client

        client = GroqClient(api_key="custom_key", model="custom-model")

        assert client.api_key == "custom_key"
        assert client.model == "custom-model"
        mock_groq_class.assert_called_once_with(api_key="custom_key")


def test_initialization_without_api_key():
    """Test GroqClient initialization fails without API key"""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="GROQ_API_KEY not found"):
            GroqClient()


def test_initialization_with_model_env_var(mock_groq_api_key):
    """Test GroqClient uses GROQ_MODEL env var if provided"""
    with patch.dict(os.environ, {"GROQ_MODEL": "custom-model"}):
        with patch("trading.infrastructure.llm.groq_client.Groq") as mock_groq_class:
            mock_client = MagicMock()
            mock_groq_class.return_value = mock_client

            client = GroqClient()

            assert client.model == "custom-model"


def test_chat(mock_groq_client):
    """Test chat() sends request and returns response"""
    messages = [{"role": "user", "content": "Hello"}]

    response = mock_groq_client.chat(messages)

    # Verify API was called
    mock_groq_client.client.chat.completions.create.assert_called_once()
    call_kwargs = mock_groq_client.client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "llama-3.3-70b-versatile"
    assert call_kwargs["messages"] == messages
    assert call_kwargs["temperature"] == 0.7
    assert call_kwargs["max_tokens"] == 2048

    # Verify response structure
    assert response["content"] == "Test response"
    assert response["model"] == "llama-3.3-70b-versatile"
    assert response["usage"]["total_tokens"] == 30
    assert response["finish_reason"] == "stop"


def test_chat_with_custom_params(mock_groq_client):
    """Test chat() with custom temperature and max_tokens"""
    messages = [{"role": "user", "content": "Hello"}]

    mock_groq_client.chat(messages, temperature=0.5, max_tokens=1000)

    call_kwargs = mock_groq_client.client.chat.completions.create.call_args[1]
    assert call_kwargs["temperature"] == 0.5
    assert call_kwargs["max_tokens"] == 1000


def test_chat_with_extra_kwargs(mock_groq_client):
    """Test chat() passes extra kwargs to API"""
    messages = [{"role": "user", "content": "Hello"}]

    mock_groq_client.chat(messages, top_p=0.9, stream=False)

    call_kwargs = mock_groq_client.client.chat.completions.create.call_args[1]
    assert call_kwargs["top_p"] == 0.9
    assert call_kwargs["stream"] is False


def test_chat_error_handling(mock_groq_client):
    """Test chat() handles API errors"""
    mock_groq_client.client.chat.completions.create.side_effect = Exception("API Error")

    with pytest.raises(Exception, match="API Error"):
        mock_groq_client.chat([{"role": "user", "content": "Hello"}])


def test_chat_json(mock_groq_client):
    """Test chat_json() returns parsed JSON"""
    # Mock JSON response
    json_response = {"key": "value", "number": 123}
    mock_groq_client.client.chat.completions.create.return_value.choices[0].message.content = json.dumps(json_response)

    messages = [{"role": "user", "content": "Return JSON"}]
    response = mock_groq_client.chat_json(messages)

    assert response == json_response

    # Verify JSON instruction was added
    call_kwargs = mock_groq_client.client.chat.completions.create.call_args[1]
    assert len(call_kwargs["messages"]) == 2
    assert call_kwargs["messages"][-1]["role"] == "system"
    assert "JSON" in call_kwargs["messages"][-1]["content"]


def test_chat_json_with_markdown_code_block(mock_groq_client):
    """Test chat_json() handles markdown code blocks"""
    json_content = {"key": "value"}
    # Simulate response wrapped in markdown
    mock_groq_client.client.chat.completions.create.return_value.choices[0].message.content = f"```json\n{json.dumps(json_content)}\n```"

    messages = [{"role": "user", "content": "Return JSON"}]
    response = mock_groq_client.chat_json(messages)

    assert response == json_content


def test_chat_json_with_code_block_no_json(mock_groq_client):
    """Test chat_json() handles code blocks without json tag"""
    json_content = {"key": "value"}
    # Simulate response wrapped in code block without json tag
    mock_groq_client.client.chat.completions.create.return_value.choices[0].message.content = f"```\n{json.dumps(json_content)}\n```"

    messages = [{"role": "user", "content": "Return JSON"}]
    response = mock_groq_client.chat_json(messages)

    assert response == json_content


def test_chat_json_empty_response(mock_groq_client):
    """Test chat_json() raises error on empty response"""
    mock_groq_client.client.chat.completions.create.return_value.choices[0].message.content = None

    with pytest.raises(ValueError, match="Empty response from Groq API"):
        mock_groq_client.chat_json([{"role": "user", "content": "Hello"}])


def test_chat_json_invalid_json(mock_groq_client):
    """Test chat_json() raises error on invalid JSON"""
    mock_groq_client.client.chat.completions.create.return_value.choices[0].message.content = "Not valid JSON"

    with pytest.raises(ValueError, match="Invalid JSON response"):
        mock_groq_client.chat_json([{"role": "user", "content": "Hello"}])


def test_chat_json_lower_temperature(mock_groq_client):
    """Test chat_json() uses lower temperature by default"""
    # Mock JSON response
    json_response = {"key": "value"}
    mock_groq_client.client.chat.completions.create.return_value.choices[0].message.content = json.dumps(json_response)

    messages = [{"role": "user", "content": "Return JSON"}]

    mock_groq_client.chat_json(messages)

    call_kwargs = mock_groq_client.client.chat.completions.create.call_args[1]
    assert call_kwargs["temperature"] == 0.3  # Lower for JSON


def test_get_groq_client_singleton(mock_groq_api_key):
    """Test get_groq_client returns singleton instance"""
    with patch("trading.infrastructure.llm.groq_client.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client

        # Reset singleton
        import trading.infrastructure.llm.groq_client as groq_module
        groq_module._groq_client = None

        client1 = get_groq_client()
        client2 = get_groq_client()

        # Should be the same instance
        assert client1 is client2

        # Should only create Groq client once
        assert mock_groq_class.call_count == 1


def test_get_groq_client_with_params_first_call(mock_groq_api_key):
    """Test get_groq_client uses params on first call"""
    with patch("trading.infrastructure.llm.groq_client.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client

        # Reset singleton
        import trading.infrastructure.llm.groq_client as groq_module
        groq_module._groq_client = None

        client = get_groq_client(api_key="custom_key", model="custom-model")

        assert client.api_key == "custom_key"
        assert client.model == "custom-model"


def test_get_groq_client_ignores_params_after_first_call(mock_groq_api_key):
    """Test get_groq_client ignores params after first call"""
    with patch("trading.infrastructure.llm.groq_client.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client

        # Reset singleton
        import trading.infrastructure.llm.groq_client as groq_module
        groq_module._groq_client = None

        client1 = get_groq_client(api_key="first_key", model="first-model")
        client2 = get_groq_client(api_key="second_key", model="second-model")

        # Should still use first params
        assert client1 is client2
        assert client1.api_key == "first_key"
        assert client1.model == "first-model"

