
from tracker_commands.registry import COMMAND_SCHEMAS, ALLOWED_STATUSES

class CommandValidationError(Exception):
    pass

class CommandValidator:
    def validate(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise CommandValidationError("Command payload must be a JSON object.")
        command = payload.get("command")
        args = payload.get("args") or {}
        if command not in COMMAND_SCHEMAS:
            raise CommandValidationError(f"Unknown command: {command}")
        schema = COMMAND_SCHEMAS[command]
        missing = [k for k in schema["required"] if args.get(k) in [None, ""]]
        if missing:
            raise CommandValidationError(f"Missing required fields for {command}: {', '.join(missing)}")
        if "status" in args and args["status"] and args["status"] not in ALLOWED_STATUSES:
            raise CommandValidationError(f"Invalid status: {args['status']}. Allowed: {', '.join(sorted(ALLOWED_STATUSES))}")
        return {"command": command, "args": args}
