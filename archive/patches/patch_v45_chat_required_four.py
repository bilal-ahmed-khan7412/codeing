from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0.')

s = chat_service.read_text(encoding='utf-8')

# v0.45 focuses only on these required chat workflows:
# 1. Edit Plan
# 2. Extend Intern
# 3. Update Capstone/Main Project
# 4. Update Real-World Scenario
# It does not change Add Intern With Plan, Create Plan, or workbook generation logic.

if 'v0.45 required four workflow overrides' not in s:
    s += r'''

# v0.45 required four workflow overrides
# These overrides make the four required workflows reliable in chat without
# disturbing the existing Add Intern With Plan and Create Plan flows.
_v45_original_message = ChatService.message


def _v45_clean_name(value: str) -> str:
    value = (value or '').strip().strip(' .,:;')
    # Preserve common acronym casing but title-case normal names.
    parts = []
    for p in value.split():
        low = p.lower()
        if low in {'ai', 'ml', 'llm', 'devops', 'secops'}:
            parts.append({'ai':'AI','ml':'ML','llm':'LLM','devops':'DevOps','secops':'SecOps'}[low])
        else:
            parts.append(p[:1].upper() + p[1:])
    return ' '.join(parts)


def _v45_first_date(text: str):
    m = re.search(r'20\d{2}-\d{2}-\d{2}', text or '')
    return m.group(0) if m else None


def _v45_output(command: str):
    return f'{command}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'


def _v45_plan_edit_draft(self, text: str, current_workbook: str | None):
    lower = text.lower()
    if not any(x in lower for x in ['rename plan', 'edit plan', 'update plan', 'change plan']):
        return None
    # Avoid intercepting week-specific edits.
    if 'week' in lower:
        return None
    args = {}
    if current_workbook:
        args['source'] = current_workbook

    # rename plan DevOps Foundation to DevOps Advanced
    m = re.search(r'(?:rename|change)\s+plan\s+(.+?)\s+to\s+(.+)$', text, re.I)
    if m:
        args['plan_name'] = _v45_clean_name(m.group(1))
        args['new_name'] = _v45_clean_name(m.group(2))
    else:
        # edit plan DevOps Foundation description to ...
        m = re.search(r'(?:edit|update|change)\s+plan\s+(.+?)\s+description\s+(?:to|as)\s+(.+)$', text, re.I)
        if m:
            args['plan_name'] = _v45_clean_name(m.group(1))
            args['description'] = m.group(2).strip()
        else:
            m = re.search(r'(?:edit|update)\s+plan\s+(.+)$', text, re.I)
            if m:
                args['plan_name'] = _v45_clean_name(m.group(1))
    args.setdefault('output', _v45_output('edit_plan'))
    return ChatDraft(str(uuid.uuid4()), 'edit_plan', args)


def _v45_extend_intern_draft(self, text: str, current_workbook: str | None):
    lower = text.lower()
    if not ('extend' in lower or 'end date' in lower or 'new end' in lower):
        return None
    if 'intern' not in lower and 'extend' not in lower:
        return None
    date = _v45_first_date(text)
    args = {}
    if current_workbook:
        args['source'] = current_workbook
    if date:
        args['new_end'] = date

    # extend Basit to 2026-09-15
    m = re.search(r'extend\s+(?:intern\s+)?(.+?)\s+(?:to|until)\s+20\d{2}-\d{2}-\d{2}', text, re.I)
    if not m:
        # change Basit end date to 2026-09-15
        m = re.search(r'(?:change|update|set)\s+(?:intern\s+)?(.+?)\s+(?:end date|new end)\s+(?:to|as)\s+20\d{2}-\d{2}-\d{2}', text, re.I)
    if m:
        args['intern'] = _v45_clean_name(m.group(1))
    args.setdefault('output', _v45_output('extend_intern'))
    return ChatDraft(str(uuid.uuid4()), 'extend_intern', args)


def _v45_capstone_draft(self, text: str, current_workbook: str | None):
    lower = text.lower()
    if not any(x in lower for x in ['main project', 'capstone']):
        return None
    args = {}
    if current_workbook:
        args['source'] = current_workbook

    # update Bilal main project to Kubernetes Monitoring Dashboard
    m = re.search(r'(?:update|edit|change|set)\s+(?:intern\s+)?(.+?)\s+(?:main project|capstone)\s+(?:to|as)\s+(.+)$', text, re.I)
    if m:
        args['intern'] = _v45_clean_name(m.group(1))
        args['title'] = m.group(2).strip()
    else:
        m = re.search(r'(?:update|edit|change|set)\s+(?:main project|capstone)\s+(?:for\s+)?(.+?)\s+(?:to|as)\s+(.+)$', text, re.I)
        if m:
            args['intern'] = _v45_clean_name(m.group(1))
            args['title'] = m.group(2).strip()
        else:
            m = re.search(r'(?:update|edit|change)\s+(?:intern\s+)?(.+?)\s+(?:main project|capstone)', text, re.I)
            if m:
                args['intern'] = _v45_clean_name(m.group(1))

    obj = re.search(r'objective\s+(?:to|as)\s+(.+?)(?:\s+tech stack|\s+status|$)', text, re.I)
    if obj:
        args['objective'] = obj.group(1).strip()
    tech = re.search(r'tech stack\s+(?:to|as)\s+(.+?)(?:\s+status|$)', text, re.I)
    if tech:
        args['tech_stack'] = tech.group(1).strip()
    status = re.search(r'\b(pending|in progress|completed)\b', lower)
    if status:
        args['status'] = {'pending':'Pending','in progress':'In Progress','completed':'Completed'}[status.group(1)]
    target_end = _v45_first_date(text)
    if target_end:
        args['target_end'] = target_end
    args.setdefault('output', _v45_output('update_capstone'))
    return ChatDraft(str(uuid.uuid4()), 'update_capstone', args)


def _v45_scenario_draft(self, text: str, current_workbook: str | None):
    lower = text.lower()
    if not any(x in lower for x in ['real-world scenario', 'real world scenario', 'scenario']):
        return None
    args = {}
    if current_workbook:
        args['source'] = current_workbook

    # update Bilal real-world scenario to investigate failed deployment
    m = re.search(r'(?:update|edit|change|set)\s+(?:intern\s+)?(.+?)\s+(?:real-world scenario|real world scenario|scenario)\s+(?:to|as)\s+(.+)$', text, re.I)
    if m:
        args['intern'] = _v45_clean_name(m.group(1))
        args['scenario'] = m.group(2).strip()
    else:
        m = re.search(r'(?:update|edit|change|set)\s+(?:real-world scenario|real world scenario|scenario)\s+(?:for\s+)?(.+?)\s+(?:to|as)\s+(.+)$', text, re.I)
        if m:
            args['intern'] = _v45_clean_name(m.group(1))
            args['scenario'] = m.group(2).strip()
        else:
            m = re.search(r'(?:update|edit|change)\s+(?:intern\s+)?(.+?)\s+(?:real-world scenario|real world scenario|scenario)', text, re.I)
            if m:
                args['intern'] = _v45_clean_name(m.group(1))

    skills = re.search(r'skills\s+(?:to|as)\s+(.+?)(?:\s+deliverable|\s+due date|\s+status|$)', text, re.I)
    if skills:
        args['skills'] = skills.group(1).strip()
    deliverable = re.search(r'deliverable\s+(?:to|as)\s+(.+?)(?:\s+due date|\s+status|$)', text, re.I)
    if deliverable:
        args['deliverable'] = deliverable.group(1).strip()
    week = re.search(r'week\s+(\d+)', lower)
    if week:
        args['assigned_week'] = int(week.group(1))
    due = _v45_first_date(text)
    if due:
        args['due_date'] = due
    status = re.search(r'\b(pending|in progress|completed)\b', lower)
    if status:
        args['status'] = {'pending':'Pending','in progress':'In Progress','completed':'Completed'}[status.group(1)]
    args.setdefault('output', _v45_output('update_scenario'))
    return ChatDraft(str(uuid.uuid4()), 'update_scenario', args)


def _v45_required_four_draft(self, text: str, current_workbook: str | None):
    for builder in [_v45_plan_edit_draft, _v45_extend_intern_draft, _v45_capstone_draft, _v45_scenario_draft]:
        draft = builder(self, text, current_workbook)
        if draft:
            return draft
    return None


def _v45_message(self, text: str, current_workbook: str | None = None):
    draft = _v45_required_four_draft(self, text, current_workbook)
    if draft:
        return self._response_for_draft(draft)
    return _v45_original_message(self, text, current_workbook)

ChatService.message = _v45_message
'''

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.45 Chat workflows for required four commands

Added reliable chat routing/proposals for:

- Edit Plan
- Extend Intern
- Update Capstone/Main Project
- Update Real-World Scenario

Examples:

- `rename plan DevOps Foundation to DevOps Advanced`
- `extend Basit to 2026-09-15`
- `update Basit main project to Kubernetes Monitoring Dashboard`
- `update Basit real-world scenario to investigate failed CI/CD deployment`
''', encoding='utf-8')

chat_service.write_text(s, encoding='utf-8')
print('v0.45 required four chat workflow patch applied successfully.')
