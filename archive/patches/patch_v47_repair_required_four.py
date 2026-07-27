from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0.')

s = chat_service.read_text(encoding='utf-8')

# Remove the broken v45/v46 appended override area and replace it with a clean version.
markers = [
    '# v0.45 required four workflow overrides',
    '# v0.46 intern-name cleanup helper',
]
cut_positions = [s.find(m) for m in markers if s.find(m) != -1]
if cut_positions:
    cut = min(cut_positions)
    s = s[:cut].rstrip() + '\n\n'

clean_block = r'''
# v0.47 repaired required-four chat workflow overrides
# Focuses on: Edit Plan, Extend Intern, Update Capstone/Main Project,
# Update Real-World Scenario. This clean block replaces broken v45/v46 code.
_v47_original_message = ChatService.message


def _v47_clean_name(value: str) -> str:
    value = (value or '').strip().strip(' .,:;')
    value = re.sub(r'^(of|for|intern|the intern)\s+', '', value, flags=re.I).strip()
    if not value:
        return value
    parts = []
    for p in value.split():
        low = p.lower()
        if low == 'ai': parts.append('AI')
        elif low == 'ml': parts.append('ML')
        elif low == 'llm': parts.append('LLM')
        elif low == 'devops': parts.append('DevOps')
        elif low == 'secops': parts.append('SecOps')
        else: parts.append(p[:1].upper() + p[1:])
    return ' '.join(parts)


def _v47_first_date(text: str):
    m = re.search(r'20\d{2}-\d{2}-\d{2}', text or '')
    return m.group(0) if m else None


def _v47_output(command: str):
    return f'{command}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'


def _v47_edit_plan_draft(self, text: str, current_workbook: str | None):
    lower = text.lower()
    if not any(x in lower for x in ['rename plan', 'edit plan', 'update plan', 'change plan']):
        return None
    if 'week' in lower:
        return None
    args = {}
    if current_workbook:
        args['source'] = current_workbook

    m = re.search(r'(?:rename|change)\s+plan\s+(.+?)\s+to\s+(.+)$', text, re.I)
    if m:
        args['plan_name'] = _v47_clean_name(m.group(1))
        args['new_name'] = _v47_clean_name(m.group(2))
    else:
        m = re.search(r'(?:edit|update|change)\s+plan\s+(.+?)\s+description\s+(?:to|as)\s+(.+)$', text, re.I)
        if m:
            args['plan_name'] = _v47_clean_name(m.group(1))
            args['description'] = m.group(2).strip()
        else:
            m = re.search(r'(?:edit|update)\s+plan\s+(.+)$', text, re.I)
            if m:
                args['plan_name'] = _v47_clean_name(m.group(1))
    args.setdefault('output', _v47_output('edit_plan'))
    return ChatDraft(str(uuid.uuid4()), 'edit_plan', args)


def _v47_extend_intern_draft(self, text: str, current_workbook: str | None):
    lower = text.lower()
    if not ('extend' in lower or 'end date' in lower or 'new end' in lower):
        return None
    date = _v47_first_date(text)
    args = {}
    if current_workbook:
        args['source'] = current_workbook
    if date:
        args['new_end'] = date

    m = re.search(r'extend\s+(?:intern\s+)?(.+?)\s+(?:to|until)\s+20\d{2}-\d{2}-\d{2}', text, re.I)
    if not m:
        m = re.search(r'(?:change|update|set)\s+(?:intern\s+)?(.+?)\s+(?:end date|new end)\s+(?:to|as)\s+20\d{2}-\d{2}-\d{2}', text, re.I)
    if m:
        args['intern'] = _v47_clean_name(m.group(1))
    args.setdefault('output', _v47_output('extend_intern'))
    return ChatDraft(str(uuid.uuid4()), 'extend_intern', args)


def _v47_capstone_draft(self, text: str, current_workbook: str | None):
    lower = text.lower()
    if not any(x in lower for x in ['main project', 'capstone']):
        return None
    args = {}
    if current_workbook:
        args['source'] = current_workbook

    # update main project of Saleem to Agentic AI platform
    m = re.search(r'(?:update|edit|change|set)\s+(?:main project|capstone)\s+(?:of|for)\s+(.+?)\s+(?:to|as)\s+(.+)$', text, re.I)
    if m:
        args['intern'] = _v47_clean_name(m.group(1))
        args['title'] = m.group(2).strip()
    else:
        # update Saleem main project to Agentic AI platform
        m = re.search(r'(?:update|edit|change|set)\s+(?:intern\s+)?(.+?)\s+(?:main project|capstone)\s+(?:to|as)\s+(.+)$', text, re.I)
        if m:
            args['intern'] = _v47_clean_name(m.group(1))
            args['title'] = m.group(2).strip()
        else:
            m = re.search(r'(?:update|edit|change)\s+(?:intern\s+)?(.+?)\s+(?:main project|capstone)', text, re.I)
            if m:
                args['intern'] = _v47_clean_name(m.group(1))

    obj = re.search(r'objective\s+(?:to|as)\s+(.+?)(?:\s+tech stack|\s+status|$)', text, re.I)
    if obj:
        args['objective'] = obj.group(1).strip()
    tech = re.search(r'tech stack\s+(?:to|as)\s+(.+?)(?:\s+status|$)', text, re.I)
    if tech:
        args['tech_stack'] = tech.group(1).strip()
    status = re.search(r'\b(pending|in progress|completed)\b', lower)
    if status:
        args['status'] = {'pending':'Pending','in progress':'In Progress','completed':'Completed'}[status.group(1)]
    target_end = _v47_first_date(text)
    if target_end:
        args['target_end'] = target_end
    args.setdefault('output', _v47_output('update_capstone'))
    return ChatDraft(str(uuid.uuid4()), 'update_capstone', args)


def _v47_scenario_draft(self, text: str, current_workbook: str | None):
    lower = text.lower()
    if not any(x in lower for x in ['real-world scenario', 'real world scenario', 'scenario', 'scenrio']):
        return None
    args = {}
    if current_workbook:
        args['source'] = current_workbook

    # update scenario of Saleem to something new
    m = re.search(r'(?:update|edit|change|set)\s+(?:real-world scenario|real world scenario|scenario|scenrio)\s+(?:of|for)\s+(.+?)\s+(?:to|as)\s+(.+)$', text, re.I)
    if m:
        args['intern'] = _v47_clean_name(m.group(1))
        args['scenario'] = m.group(2).strip()
    else:
        # update Saleem scenario to something new
        m = re.search(r'(?:update|edit|change|set)\s+(?:intern\s+)?(.+?)\s+(?:real-world scenario|real world scenario|scenario|scenrio)\s+(?:to|as)\s+(.+)$', text, re.I)
        if m:
            args['intern'] = _v47_clean_name(m.group(1))
            args['scenario'] = m.group(2).strip()
        else:
            m = re.search(r'(?:update|edit|change)\s+(?:intern\s+)?(.+?)\s+(?:real-world scenario|real world scenario|scenario|scenrio)', text, re.I)
            if m:
                args['intern'] = _v47_clean_name(m.group(1))

    skills = re.search(r'skills\s+(?:to|as)\s+(.+?)(?:\s+deliverable|\s+due date|\s+status|$)', text, re.I)
    if skills:
        args['skills'] = skills.group(1).strip()
    deliverable = re.search(r'deliverable\s+(?:to|as)\s+(.+?)(?:\s+due date|\s+status|$)', text, re.I)
    if deliverable:
        args['deliverable'] = deliverable.group(1).strip()
    week = re.search(r'week\s+(\d+)', lower)
    if week:
        args['assigned_week'] = int(week.group(1))
    due = _v47_first_date(text)
    if due:
        args['due_date'] = due
    status = re.search(r'\b(pending|in progress|completed)\b', lower)
    if status:
        args['status'] = {'pending':'Pending','in progress':'In Progress','completed':'Completed'}[status.group(1)]
    args.setdefault('output', _v47_output('update_scenario'))
    return ChatDraft(str(uuid.uuid4()), 'update_scenario', args)


def _v47_required_four_draft(self, text: str, current_workbook: str | None):
    for builder in [_v47_edit_plan_draft, _v47_extend_intern_draft, _v47_capstone_draft, _v47_scenario_draft]:
        draft = builder(self, text, current_workbook)
        if draft:
            return draft
    return None


def _v47_message(self, text: str, current_workbook: str | None = None):
    draft = _v47_required_four_draft(self, text, current_workbook)
    if draft:
        return self._response_for_draft(draft)
    return _v47_original_message(self, text, current_workbook)

ChatService.message = _v47_message
'''

s = s.rstrip() + '\n\n' + clean_block + '\n'
chat_service.write_text(s, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.47 Repair required-four chat workflow syntax

- Repairs syntax error introduced by previous v46 patch.
- Replaces broken v45/v46 appended override block with a clean version.
- Supports:
  - Edit Plan
  - Extend Intern
  - Update Capstone/Main Project
  - Update Real-World Scenario
- Fixes `update main project of Saleem to ...` extracting intern as `Saleem`.
''', encoding='utf-8')

print('v0.47 repaired required-four chat workflow patch applied successfully.')
