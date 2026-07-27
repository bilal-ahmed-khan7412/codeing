from dataclasses import dataclass, field
from typing import Any, List, Optional

# For now, renderer parser owns the detailed visible-sheet dataclasses.
# These models define the command/service-facing objects that can grow later.

@dataclass
class InternIdentity:
    name: str
    manager: str = ""
    skip_manager: str = ""
    plan_name: str = "Custom"
    start_date: str = ""
    end_date: str = ""
    final_project: str = ""

@dataclass
class CommandResult:
    ok: bool
    message: str
    output_path: Optional[str] = None
    data: dict = field(default_factory=dict)
