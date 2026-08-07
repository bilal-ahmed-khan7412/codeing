from dataclasses import dataclass, field
from pathlib import Path
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

    def public_dict(self) -> dict:
        """Response dict safe to hand to an API client. Service methods
        build output_path as a full server-side absolute path and often
        interpolate that same path straight into message (e.g. f"Added
        intern {name}: {out}"), which otherwise discloses server directory
        structure - reduce both to just the filename."""
        filename = Path(self.output_path).name if self.output_path else None
        message = self.message
        if filename and self.output_path and self.output_path in message:
            message = message.replace(self.output_path, filename)
        return {'ok': self.ok, 'message': message, 'output_path': filename, 'data': self.data}
