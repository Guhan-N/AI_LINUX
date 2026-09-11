from linagent.core.agent import LinAgent
from linagent.core.config import LinAgentConfig
from linagent.core.llm import BaseLLMClient, LLMResponse, Message
from linagent.core.tools import ToolRegistry

def test_agent_react_execution():
    test_registry = ToolRegistry()

    @test_registry.register(name="mock_calculator", description="Add numbers")
    def mock_calculator(a: int, b: int) -> str:
        return f"Result: {a + b}"

    # Mock LLM that requests tool call on step 1, then provides final answer on step 2
    class ScriptedLLM(BaseLLMClient):
        def __init__(self):
            self.turn = 0

        def chat(self, messages, tools=None):
            self.turn += 1
            if self.turn == 1:
                return LLMResponse(
                    content="Let me compute that.",
                    tool_calls=[{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "mock_calculator",
                            "arguments": '{"a": 25, "b": 75}'
                        }
                    }]
                )
            else:
                return LLMResponse(
                    content="The calculated sum is 100."
                )

    agent = LinAgent(
        config=LinAgentConfig(safe_mode=False),
        registry=test_registry,
        llm_client=ScriptedLLM(),
    )

    steps_recorded = []
    def on_step(evt):
        steps_recorded.append(evt)

    result = agent.step("Calculate 25 + 75", on_step_callback=on_step)
    assert "100" in result
    assert any(s.get("type") == "tool_start" for s in steps_recorded)
    assert any(s.get("type") == "tool_end" and s.get("success") for s in steps_recorded)
