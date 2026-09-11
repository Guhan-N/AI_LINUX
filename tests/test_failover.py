import pytest
from linagent.core.config import ProviderSpec
from linagent.core.llm import FailoverLLMClient, LLMResponse, Message, RotationalProvider

class MockClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0

    def chat(self, messages, tools=None):
        res = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return res

def test_key_rotation_on_ratelimit(monkeypatch):
    spec = ProviderSpec(
        provider="gemini",
        model="gemini-2.0-flash",
        api_keys=["key_A", "key_B"],
    )
    rotational = RotationalProvider(spec)
    assert rotational.key_index == 0
    next_key = rotational.rotate_key()
    assert next_key == "key_B"
    assert rotational.key_index == 1

def test_multi_provider_waterfall_failover(monkeypatch):
    """
    Test scenario:
    1. Provider 1 (Gemini) fails with rate_limit (HTTP 429)
    2. Provider 2 (Groq) fails with auth error (HTTP 401)
    3. Provider 3 (Ollama) succeeds with final answer
    """
    client_p1 = MockClient([
        LLMResponse(is_error=True, error_type="rate_limit", content="Quota exceeded (429)")
    ])
    client_p2 = MockClient([
        LLMResponse(is_error=True, error_type="auth", content="Invalid API Key (401)")
    ])
    client_p3 = MockClient([
        LLMResponse(is_error=False, content="Hello from local Ollama!")
    ])

    mock_clients = [client_p1, client_p2, client_p3]
    client_idx = 0

    def mock_get_next_client(self):
        nonlocal client_idx
        c = mock_clients[client_idx]
        client_idx += 1
        return c

    monkeypatch.setattr(RotationalProvider, "get_next_client", mock_get_next_client)

    providers = [
        ProviderSpec(provider="gemini", model="gemini-2.0-flash", api_keys=["g_key"]),
        ProviderSpec(provider="groq", model="llama-3.3-70b-versatile", api_keys=["groq_key"]),
        ProviderSpec(provider="ollama", model="llama3.2:1b"),
    ]

    failover_client = FailoverLLMClient(providers)
    resp = failover_client.chat([Message(role="user", content="Hi")])

    assert resp.is_error is False
    assert resp.content == "Hello from local Ollama!"
    assert client_p1.call_count == 1
    assert client_p2.call_count == 1
    assert client_p3.call_count == 1

def test_waterfall_all_exhausted(monkeypatch):
    client_p1 = MockClient([
        LLMResponse(is_error=True, error_type="rate_limit", content="429 Too Many Requests")
    ])
    monkeypatch.setattr(RotationalProvider, "get_next_client", lambda self: client_p1)

    providers = [
        ProviderSpec(provider="groq", model="llama-3.3-70b", api_keys=["k1"]),
    ]

    failover_client = FailoverLLMClient(providers)
    resp = failover_client.chat([Message(role="user", content="Hi")])

    assert resp.is_error is True
    assert "Failover Exhausted" in resp.content
