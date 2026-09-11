"""Load and register all standard tools for LinAgent."""

import sys

# Import all tool modules so decorators execute
from linagent.tools.automation import shell, system, packages, services, scheduler
from linagent.tools.files import manager
from linagent.tools.web import search, browser
from linagent.tools.memory import store, skills

# Load custom user skills
skills.load_user_skills()

from linagent.core.tools import default_registry

__all__ = ["default_registry"]
