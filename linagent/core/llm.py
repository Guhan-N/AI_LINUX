"""Unified LLM interface for LinAgent with Key Rotation & Multi-Provider Failover Waterfall."""

import json
import os
import sys
import time
from typing import Any, Dict, Generator, List, Optional
from pydantic import BaseModel, Field

from linagent.core.config import LinAgentConfig, ProviderSpec

class Message(BaseModel):
    role: str  # "system", "user", "assistant", "tool"
    content: Optional[str] = ""
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

class LLMResponse(BaseModel):
    content: str = ""
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Dict[str, int] = Field(default_factory=dict)
    is_error: bool = False
    error_type: Optional[str] = None  # "rate_limit", "auth", "connection", "general"

class BaseLLMClient:
    def chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None) -> LLMResponse:
        raise NotImplementedError

    def stream_chat(self, messages: List[Message]) -> Generator[str, None, None]:
        raise NotImplementedError

class MockLLMClient(BaseLLMClient):
    """Fallback client when no live LLM or API key is configured."""
    def __init__(self, message: str = "LinAgent is currently running in offline mock mode.") -> None:
        self.message = message

    def chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None) -> LLMResponse:
        last_msg = messages[-1].content if messages else ""
        return LLMResponse(
            content=f"[LinAgent Offline Mode] Received: '{last_msg}'. Run 'linagent config' to set up local Ollama or your free Groq/Gemini API keys."
        )

    def stream_chat(self, messages: List[Message]) -> Generator[str, None, None]:
        yield self.message

class OpenAICompatibleClient(BaseLLMClient):
    """Unified client for OpenAI, Groq, Gemini, OpenRouter, and Ollama's v1 endpoint."""

    def __init__(
        self,
        api_key: Optional[str],
        base_url: Optional[str],
        model: str,
        temperature: float = 0.2,
        timeout: float = 12.0,
        provider_name: str = "openai",
    ):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=api_key or "not-needed-for-local",
            base_url=base_url,
            timeout=timeout,
        )
        self.model = model
        self.temperature = temperature
        self.provider_name = provider_name
        self.current_api_key = api_key

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        converted = []
        for m in messages:
            msg: Dict[str, Any] = {"role": m.role, "content": m.content or ""}
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            if m.name:
                msg["name"] = m.name
            converted.append(msg)
        return converted

    def chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None) -> LLMResponse:
        converted_msgs = self._convert_messages(messages)
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": converted_msgs,
            "temperature": self.temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        from openai import APIConnectionError, AuthenticationError, RateLimitError
        try:
            response = self.client.chat.completions.create(**kwargs)
        except RateLimitError as rle:
            return LLMResponse(
                is_error=True,
                error_type="rate_limit",
                content=f"Rate limit exceeded (HTTP 429) for {self.provider_name}: {rle}",
            )
        except AuthenticationError as aue:
            return LLMResponse(
                is_error=True,
                error_type="auth",
                content=f"Authentication error (HTTP 401) for {self.provider_name}: {aue}",
            )
        except APIConnectionError as ace:
            return LLMResponse(
                is_error=True,
                error_type="connection",
                content=f"Connection error to {self.provider_name}: {ace}",
            )
        except Exception as ex:
            return LLMResponse(
                is_error=True,
                error_type="general",
                content=f"LLM Error on {self.provider_name}: {ex}",
            )

        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                })

        usage_dict = {}
        if response.usage:
            usage_dict = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            usage=usage_dict,
        )

    def stream_chat(self, messages: List[Message]) -> Generator[str, None, None]:
        converted_msgs = self._convert_messages(messages)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=converted_msgs,
            temperature=self.temperature,
            stream=True,
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

class RotationalProvider:
    """Manages key rotation across multiple API keys for a single provider."""

    def __init__(self, spec: ProviderSpec):
        self.spec = spec
        self.api_keys = list(spec.api_keys) or []
        self.key_index = 0
        self.cooldowns: Dict[str, float] = {}

    def get_next_client(self) -> OpenAICompatibleClient:
        """Instantiate client using current rotated API key."""
        key = None
        if self.api_keys:
            key = self.api_keys[self.key_index]

        p = self.spec.provider.lower()
        base_url = self.spec.base_url

        # Canonical endpoints for standard providers:
        # Prevent local Ollama base_url from leaking when user switches to cloud providers
        if p == "gemini" and (not base_url or "localhost" in base_url or "127.0.0.1" in base_url):
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        elif p == "groq" and (not base_url or "localhost" in base_url or "127.0.0.1" in base_url):
            base_url = "https://api.groq.com/openai/v1"
        elif p == "openrouter" and (not base_url or "localhost" in base_url or "127.0.0.1" in base_url):
            base_url = "https://openrouter.ai/api/v1"
        elif p == "ollama" and (not base_url or "googleapis" in base_url or "api.groq" in base_url or "openrouter" in base_url):
            base_url = "http://localhost:11434/v1"

        return OpenAICompatibleClient(
            api_key=key,
            base_url=base_url,
            model=self.spec.model,
            temperature=self.spec.temperature,
            provider_name=self.spec.provider,
        )

    def rotate_key(self) -> Optional[str]:
        """Advance to next API key upon quota exhaustion."""
        if not self.api_keys:
            return None
        current_key = self.api_keys[self.key_index]
        self.cooldowns[current_key] = time.time() + 60.0  # 1 min cooldown
        self.key_index = (self.key_index + 1) % len(self.api_keys)
        return self.api_keys[self.key_index]

class FailoverLLMClient(BaseLLMClient):
    """
    Multi-Provider Waterfall & Key-Rotation Coordinator.
    Attempts providers in order. On 429 RateLimit, key exhaustion, or network disconnect,
    seamlessly rotates to the next key or cascades down the waterfall to local Ollama.
    """

    def __init__(self, providers: List[ProviderSpec]):
        self.providers = [RotationalProvider(spec) for spec in providers]

    def chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None) -> LLMResponse:
        errors = []

        for provider in self.providers:
            num_keys = max(1, len(provider.api_keys))

            for attempt in range(num_keys):
                client = provider.get_next_client()
                response = client.chat(messages, tools=tools)

                # If successful, return immediately!
                if not response.is_error:
                    return response

                # Handle failure
                err_msg = response.content
                errors.append(f"{provider.spec.provider.upper()} ({provider.spec.model}): {err_msg}")

                # If rate limited and has alternate keys, rotate key and retry immediately
                if response.error_type == "rate_limit" and len(provider.api_keys) > 1:
                    new_key = provider.rotate_key()
                    sys.stderr.write(f"\n[LinAgent Rotation] Rate limit on {provider.spec.provider}. Rotating to next API key...\n")
                    continue
                else:
                    # Move to next provider in the waterfall
                    break

            sys.stderr.write(f"\n[LinAgent Failover] Provider '{provider.spec.provider}' failed. Cascading down waterfall...\n")

        # If all providers in waterfall failed
        diag = "\n".join(f"  * {e}" for e in errors)
        return LLMResponse(
            is_error=True,
            content=(
                f"⚠️ [LinAgent Failover Exhausted] All providers in the waterfall chain failed:\n"
                f"{diag}\n\n"
                f"Tips:\n"
                f"1. If using Ollama, make sure local daemon is active: `ollama run llama3.2:1b`\n"
                f"2. Add a free Groq or Gemini API key using `linagent config`\n"
            ),
        )

    def stream_chat(self, messages: List[Message]) -> Generator[str, None, None]:
        for provider in self.providers:
            try:
                client = provider.get_next_client()
                for chunk in client.stream_chat(messages):
                    yield chunk
                return
            except Exception as e:
                sys.stderr.write(f"\n[LinAgent Failover] Streaming failed on {provider.spec.provider}: {e}\n")
                continue
        yield "⚠️ All providers failed during stream."

def create_llm_client(config: LinAgentConfig) -> BaseLLMClient:
    """Instantiate FailoverLLMClient or direct client based on configuration."""
    # If failover is enabled and providers are defined, use FailoverLLMClient
    if config.failover_enabled and config.failover_providers:
        return FailoverLLMClient(config.failover_providers)

    # Fallback to single primary client
    provider = config.provider.lower().strip()
    primary_spec = ProviderSpec(
        provider=provider,
        model=config.model,
        api_keys=config.api_keys if config.api_keys else ([config.api_key] if config.api_key else []),
        base_url=config.base_url,
        temperature=config.temperature,
    )
    return FailoverLLMClient([primary_spec])
