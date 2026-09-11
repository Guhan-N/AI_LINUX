import tempfile
from pathlib import Path
from linagent.core.tools import default_registry
from linagent.tools.memory.skills import create_new_skill, list_custom_skills

def test_dynamic_skill_creation(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch config skills_dir
        from linagent.core import config
        original_load = config.load_config

        class MockConfig(config.LinAgentConfig):
            skills_dir: str = tmpdir

        monkeypatch.setattr(config, "load_config", lambda: MockConfig())

        skill_code = """
@default_registry.register(name="custom_math_multiplier", description="Multiply two numbers")
def custom_math_multiplier(x: int, y: int) -> str:
    return f"Product: {x * y}"
"""
        res = create_new_skill("multiplier_skill", skill_code)
        assert res.success is True
        assert "multiplier_skill" in res.output

        # Verify tool was registered in runtime registry
        tool_obj = default_registry.get_tool("custom_math_multiplier")
        assert tool_obj is not None
        tool_res = tool_obj.execute(x=7, y=6)
        assert "Product: 42" in tool_res.output
