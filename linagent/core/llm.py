"""Unified LLM interface for LinAgent supporting Ollama, Groq, Gemini, and OpenAI."""

import json
import os
import sys
from typing import Any, Dict, Generator, List, Optional
from pydantic import BaseModel, Field

from linagent.core.config import LinAgentConfig

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

class BaseLLMClient:
    def chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None) -> LLMResponse:
        raise NotImplementedError

    def stream_chat(self, messages: List[Message]) -> Generator[str, None, None]:
        raise NotImplementedError

class MockLLMClient(BaseLLMClient):
    """Fallback client when no live LLM or API key is configured yet."""
    def __init__(self, message: str = "LinAgent is currently running in offline mock mode.") -> None:
        self.message = message

    def chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None) -> LLMResponse:
        last_msg = messages[-1].content if messages else ""
        return LLMResponse(
            content=f"[LinAgent Offline Mode] Received: '{last_msg}'. Please run 'linagent config' to configure Ollama (local) or your Groq/Gemini/OpenAI API key."
        )

    def stream_chat(self, messages: List[Message]) -> Generator[str, None, None]:
        yield self.message

class OpenAICompatibleClient(BaseLLMClient):
    """Unified client for OpenAI, Groq, OpenRouter, vLLM, LocalAI, and Ollama's v1 endpoint."""

    def __init__(self, api_key: Optional[str], base_url: Optional[str], model: str, temperature: float = 0.2, timeout: float = 10.0):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key or "not-needed-for-local", base_url=base_url, timeout=timeout)
        self.model = model
        self.temperature = temperature

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
        except APIConnectionError as ace:
            return LLMResponse(
                content=(
                    f"⚠️ [LinAgent Connection Error] Could not connect to LLM provider.\n"
                    f"If you are using local Ollama, ensure it is running (`ollama serve` or `ollama run {self.model}`).\n"
                    f"Or run `linagent config` to switch to Groq, Gemini, or OpenAI.\n"
                    f"Details: {ace}"
                )
            )
        except AuthenticationError as aue:
            return LLMResponse(
                content=f"⚠️ [LinAgent Auth Error] Invalid API key for provider. Run `linagent config` to update your API key.\nDetails: {aue}"
            )
        except RateLimitError as rle:
            return LLMResponse(
                content=f"⚠️ [LinAgent Rate Limit] The API rate limit was exceeded. Please wait a moment or switch models.\nDetails: {rle}"
            )
        except Exception as ex:
            return LLMResponse(
                content=f"⚠️ [LinAgent LLM Error] {ex}"
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

def create_llm_client(config: LinAgentConfig) -> BaseLLMClient:
    """Factory function to instantiate the correct LLM provider."""
    provider = config.provider.lower().strip()

    try:
        if provider == "ollama":
            base_url = config.base_url or "http://localhost:11434/v1"
            model = config.model or "llama3.2:3b"
            return OpenAICompatibleClient(api_key="ollama", base_url=base_url, model=model, temperature=config.temperature)

        elif provider == "groq":
            api_key = config.api_key or os.getenv("GROQ_API_KEY")
            if not api_key:
                return MockLLMClient("Groq API key not found. Set GROQ_API_KEY or configure via 'linagent config'.")
            model = config.model or "llama-3.3-70b-versatile"
            return OpenAICompatibleClient(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
                model=model,
                temperature=config.temperature,
            )

        elif provider == "openai":
            api_key = config.api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                return MockLLMClient("OpenAI API key not found. Set OPENAI_API_KEY or configure via 'linagent config'.")
            model = config.model or "gpt-4o-mini"
            return OpenAICompatibleClient(
                api_key=api_key,
                base_url=config.base_url,
                model=model,
                temperature=config.temperature,
            )

        elif provider == "gemini":
            api_key = config.api_key or os.getenv("GEMINI_API_KEY")
            if not api_key:
                return MockLLMClient("Gemini API key not found. Set GEMINI_API_KEY or configure via 'linagent config'.")
            # Gemini provides an official OpenAI-compatible endpoint
            return OpenAICompatibleClient(
                api_key=api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                model=config.model or "gemini-2.0-flash",
                temperature=config.temperature,
            )

        elif provider == "custom":
            return OpenAICompatibleClient(
                api_key=config.api_key or "custom",
                base_url=config.base_url or "http://localhost:8000/v1",
                model=config.model,
                temperature=config.temperature,
            )

        else:
            return MockLLMClient(f"Unknown provider '{provider}'. Supported: ollama, groq, gemini, openai, custom.")

    except Exception as e:
        return MockLLMClient(f"LLM initialization error: {e}")
