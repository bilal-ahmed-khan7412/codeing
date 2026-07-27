from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
chat_service_path = ROOT / "tracker_chat" / "chat_service.py"
prompts_path = ROOT / "tracker_llm" / "prompts.py"

if not chat_service_path.exists():
    raise FileNotFoundError(f"Missing file: {chat_service_path}")

chat_html = chat_service_path.read_text(encoding="utf-8")
chat_backup = chat_service_path.with_suffix(".py.bak_v100")
chat_backup.write_text(chat_html, encoding="utf-8")

# Optional but useful: make the global system prompt actually include schemas.
if prompts_path.exists():
    prompts_html = prompts_path.read_text(encoding="utf-8")
    prompts_backup = prompts_path.with_suffix(".py.bak_v100")
    prompts_backup.write_text(prompts_html, encoding="utf-8")

    if "json.dumps(COMMAND_SCHEMAS" not in prompts_html:
        if "from tracker_commands.registry import COMMAND_SCHEMAS" in prompts_html and "import json" not in prompts_html.splitlines()[:5]:
            prompts_html = prompts_html.replace(
                "from tracker_commands.registry import COMMAND_SCHEMAS",
                "import json\nfrom tracker_commands.registry import COMMAND_SCHEMAS",
                1
            )

        prompts_html = prompts_html.replace(
            "Supported commands and schemas:  ",
            "Supported commands and schemas:\n{json.dumps(COMMAND_SCHEMAS, indent=2)}  ",
            1
        )

        prompts_path.write_text(prompts_html, encoding="utf-8")
        print(f"Patched prompts.py schema injection. Backup: {prompts_backup}")
    else:
        print("prompts.py already has schema injection. Skipping prompts.py.")

marker = "# ===== v100 create-plan LLM shape + sanitize override ====="

patch = r'''

# ===== v100 create-plan LLM shape + sanitize override =====
# Fixes:
# 1) Provider system prompt expects {"command": "...", "args": {...}},
#    while the old plan drafter expected top-level {"plan_name": ..., "weeks": ...}.
# 2) HTML/Lexical tags from LLM output leaked into proposal text.
# 3) Generic safe draft appeared because valid weeks were hidden under args or invalid.

import html as _v100_html

def _v100_clean_text(value):
    s = str(value or "")
    s = _v100_html.unescape(s)
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
    s = re.sub(r'</?(strong|b|em|i|span|p|div)[^>]*>', '', s, flags=re.I)
    s = re.sub(r'data-lexical-text="true"', '', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'\s+\n', '\n', s)
    s = re.sub(r'\n\s+', '\n', s)
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()

def _v100_normalize_llm_plan_payload(data):
    """Accept both top-level plan JSON and command/args JSON."""
    if not isinstance(data, dict):
        return {}

    # Preferred shape because provider SYSTEM_PROMPT asks for it.
    if isinstance(data.get("args"), dict):
        args = dict(data.get("args") or {})
    else:
        args = dict(data)

    return args

def _v100_clean_weeks(raw_weeks, expected_count):
    if not isinstance(raw_weeks, list):
        return []

    cleaned = []
    for idx, item in enumerate(raw_weeks, start=1):
        if not isinstance(item, dict):
            continue

        week_no = item.get("week") or idx
        try:
            week_no = int(week_no)
        except Exception:
            week_no = idx

        theme = _v100_clean_text(item.get("theme"))
        task = _v100_clean_text(item.get("task") or item.get("daily_task"))
        weekly_project = _v100_clean_text(item.get("weekly_project") or item.get("project"))
        notes = _v100_clean_text(item.get("notes"))

        # Skip totally empty rows.
        if not any([theme, task, weekly_project, notes]):
            continue

        cleaned.append({
            "week": week_no,
            "theme": theme or f"Week {week_no} Focus",
            "task": task or "Complete practical learning tasks for this week.",
            "weekly_project": weekly_project or "Complete a weekly practical project.",
            "notes": notes,
        })

    # Keep expected week limit if the model returned too many.
    if expected_count and len(cleaned) > expected_count:
        cleaned = cleaned[:expected_count]

    return cleaned

def _v100_weeks_look_usable(weeks):
    if not isinstance(weeks, list) or not weeks:
        return False

    bad_markers = [
        "llm returned no detailed weeks",
        "generated safe draft",
        "foundation and environment setup",
        "core concepts",
        "hands-on practice",
        "final demo",
    ]

    usable = 0
    for w in weeks:
        if not isinstance(w, dict):
            continue
        text = " ".join(str(w.get(k, "")) for k in ("theme", "task", "weekly_project", "notes")).lower()
        if any(marker in text for marker in bad_markers):
            continue
        if len(str(w.get("task", "")).strip()) >= 30 and len(str(w.get("weekly_project", "")).strip()) >= 20:
            usable += 1

    return usable >= max(1, min(3, len(weeks)))

def _v100_plan_prompt(user_text, weeks_count):
    return f"""
Create a practical intern learning plan from this request:

{user_text}

Return ONLY valid JSON in this exact shape:
{{
  "command": "create_plan_from_draft",
  "args": {{
    "plan_name": "short clear plan name",
    "description": "one sentence description",
    "weeks": [
      {{
        "week": 1,
        "theme": "specific weekly theme",
        "task": "specific daily-learning task description for this week",
        "weekly_project": "specific weekly practical project",
        "notes": "short practical guidance"
      }}
    ]
  }}
}}

Rules:
- Create exactly {weeks_count} weeks unless the user clearly asked otherwise.
- Each week must be specific to the requested topic.
- Do not return generic placeholder weeks.
- Do not include HTML tags.
- Do not include markdown.
- Do not include <strong>, <br>, or data-lexical-text.
- Do not invent source, output, or workbook paths.
"""

def _v100_draft_plan_with_llm(self, text: str, current_workbook: str | None):
    fallback_name = self._extract_plan_name(text) or "Custom Learning Plan"
    fallback_name = self._normalize_plan_name(fallback_name, text)
    weeks_count = self._extract_weeks_count(text) or 8
    source = current_workbook or ""
    output = f"Plan_{self._safe_name(fallback_name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    plan_name = fallback_name
    description = _v100_clean_text(text)
    weeks = []
    generation_error = ""

    if self.provider:
        for attempt in range(2):
            try:
                prompt = _v100_plan_prompt(text, weeks_count)
                if attempt == 1:
                    prompt += """

Your previous response was not usable. Try again.
Make sure weeks is inside args.weeks and contains detailed topic-specific week objects.
"""

                raw = self.provider.complete_json(prompt)
                args = _v100_normalize_llm_plan_payload(raw)

                candidate_name = _v100_clean_text(args.get("plan_name")) or fallback_name
                candidate_name = self._normalize_plan_name(candidate_name, text)

                explicit_prompt_name = self._explicit_plan_name_from_prompt(text)
                if explicit_prompt_name:
                    candidate_name = explicit_prompt_name

                candidate_description = _v100_clean_text(args.get("description")) or description
                candidate_weeks = _v100_clean_weeks(args.get("weeks"), weeks_count)

                if _v100_weeks_look_usable(candidate_weeks):
                    plan_name = candidate_name
                    description = candidate_description
                    weeks = candidate_weeks
                    break

                generation_error = "LLM returned no usable detailed weeks."

            except Exception as e:
                generation_error = str(e)

    # If LLM still fails, do NOT silently present generic fallback as a good draft.
    # Keep deterministic fallback, but make warning clear so user should not approve blindly.
    if not weeks:
        weeks = self._fallback_weeks(
            plan_name,
            weeks_count,
            "Plan generation fallback used because LLM did not return detailed topic-specific weeks. Regenerate or edit before approval."
        )

    # Final cleanup safety.
    plan_name = _v100_clean_text(plan_name) or fallback_name
    description = _v100_clean_text(description)
    weeks = _v100_clean_weeks(weeks, weeks_count)

    warnings = self._plan_quality_warnings(weeks, plan_name)
    if generation_error:
        warnings.append(f"LLM generation issue: {generation_error}")
    if any("fallback" in str(w.get("notes", "")).lower() for w in weeks if isinstance(w, dict)):
        warnings.append("This draft used fallback content. Review or regenerate before approval.")

    return ChatDraft(str(uuid.uuid4()), "create_plan_from_draft", {
        "source": source,
        "plan_name": plan_name,
        "description": description,
        "weeks": weeks,
        "quality_warnings": warnings,
        "output": output,
    })

ChatService._draft_plan_with_llm = _v100_draft_plan_with_llm
'''

if marker in chat_html:
    print("v100 chat_service patch already exists. Skipping.")
else:
    chat_html = chat_html.rstrip() + "\n" + patch + "\n"
    chat_service_path.write_text(chat_html, encoding="utf-8")
    print(f"Patched chat_service.py. Backup: {chat_backup}")

print("Applied v100 create-plan LLM shape and cleanup patch.")