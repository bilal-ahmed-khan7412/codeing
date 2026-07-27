from pathlib import Path

root = Path(__file__).resolve().parent
plan_service = root / 'tracker_services' / 'plan_service.py'
chat_service = root / 'tracker_chat' / 'chat_service.py'
chat_html = root / 'web' / 'chat.html'

if not plan_service.exists():
    raise SystemExit('tracker_services/plan_service.py not found. Run this patch inside intern_tracker_system_v0.')

s = plan_service.read_text(encoding='utf-8')

# 1) Strip intern_name/plan_name inside apply_plan_to_intern and set main project/scenario defaults after applying plan.
old = """    def apply_plan_to_intern(self, source_path: str, intern_name: str, plan_name: str, output_path: str | None = None) -> CommandResult:\n        data = parse_workbook(source_path)\n        plan = self._find_plan(data, plan_name)\n        if not plan:\n            return CommandResult(False, f'Plan not found: {plan_name}')\n        intern = None\n        for item in data.interns:\n            if item.name.lower() == intern_name.lower():\n                intern = item\n                break\n        if not intern:\n            return CommandResult(False, f'Intern not found: {intern_name}')\n        start = intern.main_row[3] if len(intern.main_row) > 3 else None\n        end = intern.main_row[4] if len(intern.main_row) > 4 else None\n        if not isinstance(start, datetime) or not isinstance(end, datetime):\n            return CommandResult(False, 'Intern start/end dates are missing or invalid')\n        tasks, weekly_reports, projects = self._build_schedule_from_plan(plan, start, end)\n        intern.tasks = tasks\n        intern.weekly_reports = weekly_reports\n        intern.projects = projects\n        intern.title = f'{intern.title.split(\"(\")[0].rstrip()}    ({plan.title.replace(\"Plan — \", \"\")})'\n        out = output_path or VersionService.next_version_path(source_path)\n        RenderService.render_data(data, out)\n        return CommandResult(True, f'Applied plan {plan_name} to {intern_name}: {out}', out)\n"""
new = """    def apply_plan_to_intern(self, source_path: str, intern_name: str, plan_name: str, output_path: str | None = None) -> CommandResult:\n        intern_name = (intern_name or '').strip()\n        plan_name = (plan_name or '').strip()\n        data = parse_workbook(source_path)\n        plan = self._find_plan(data, plan_name)\n        if not plan:\n            return CommandResult(False, f'Plan not found: {plan_name}')\n        intern = None\n        for item in data.interns:\n            if item.name.strip().lower() == intern_name.lower():\n                intern = item\n                break\n        if not intern:\n            return CommandResult(False, f'Intern not found: {intern_name}')\n        start = intern.main_row[3] if len(intern.main_row) > 3 else None\n        end = intern.main_row[4] if len(intern.main_row) > 4 else None\n        if not isinstance(start, datetime) or not isinstance(end, datetime):\n            return CommandResult(False, 'Intern start/end dates are missing or invalid')\n        tasks, weekly_reports, projects = self._build_schedule_from_plan(plan, start, end)\n        intern.tasks = tasks\n        intern.weekly_reports = weekly_reports\n        intern.projects = projects\n        intern.title = f'{intern.title.split(\"(\")[0].rstrip()}    ({plan.title.replace(\"Plan — \", \"\")})'\n        self._apply_project_and_scenario_defaults(intern, plan_name, start, end)\n        out = output_path or VersionService.next_version_path(source_path)\n        RenderService.render_data(data, out)\n        return CommandResult(True, f'Applied plan {plan_name} to {intern_name} and updated related project/scenario defaults: {out}', out)\n"""
if old in s:
    s = s.replace(old, new)
elif '_apply_project_and_scenario_defaults' not in s:
    print('Warning: exact apply_plan_to_intern block not found. Manual merge may be needed.')

# 2) Add helper methods before _build_schedule_from_plan.
if 'def _apply_project_and_scenario_defaults' not in s:
    helper = r'''
    def _apply_project_and_scenario_defaults(self, intern, plan_name: str, start: datetime, end: datetime):
        """Set main project and real-world scenario defaults based on plan topic.

        Safety rule: overwrite only when the existing value is blank or clearly generic.
        This prevents accidental overwrite of a manager-authored capstone/scenario.
        """
        defaults = self._topic_defaults(plan_name)
        while len(intern.main_row) < 6:
            intern.main_row.append('')
        while len(intern.scenario_row) < 6:
            intern.scenario_row.append('')

        generic_project_values = {'', 'aiops', 'custom plan', 'project to be assigned', 'task to be assigned', None}
        current_title = str(intern.main_row[0]).strip().lower() if intern.main_row[0] is not None else ''
        current_objective = str(intern.main_row[1]).strip().lower() if intern.main_row[1] is not None else ''
        current_stack = str(intern.main_row[2]).strip().lower() if intern.main_row[2] is not None else ''

        if current_title in generic_project_values:
            intern.main_row[0] = defaults['project_title']
        if current_objective in generic_project_values:
            intern.main_row[1] = defaults['objective']
        if current_stack in generic_project_values:
            intern.main_row[2] = defaults['tech_stack']
        if not intern.main_row[3]:
            intern.main_row[3] = start
        intern.main_row[4] = end
        if not intern.main_row[5]:
            intern.main_row[5] = 'Pending'

        generic_scenario_values = {'', 'scenario to be assigned', 'task to be assigned', None}
        current_scenario = str(intern.scenario_row[0]).strip().lower() if intern.scenario_row[0] is not None else ''
        current_skills = str(intern.scenario_row[1]).strip().lower() if intern.scenario_row[1] is not None else ''
        current_deliverable = str(intern.scenario_row[2]).strip().lower() if intern.scenario_row[2] is not None else ''

        if current_scenario in generic_scenario_values:
            intern.scenario_row[0] = defaults['scenario']
        if current_skills in generic_scenario_values:
            intern.scenario_row[1] = defaults['skills']
        if current_deliverable in generic_scenario_values:
            intern.scenario_row[2] = defaults['deliverable']
        if not intern.scenario_row[3]:
            intern.scenario_row[3] = max(1, min(6, len(intern.weekly_reports) or 1))
        if not intern.scenario_row[4]:
            intern.scenario_row[4] = end
        if not intern.scenario_row[5]:
            intern.scenario_row[5] = 'Pending'

    def _topic_defaults(self, plan_name: str) -> dict:
        p = (plan_name or '').lower()
        if 'openshift' in p:
            return {
                'project_title': 'OpenShift Deployment and Troubleshooting Demo',
                'objective': 'Deploy, configure, monitor, and troubleshoot a sample application on OpenShift, then document the solution in a short runbook.',
                'tech_stack': 'Linux, Kubernetes, OpenShift, YAML, oc CLI, container images',
                'scenario': 'A sample application is deployed on OpenShift but has route, pod, configuration, and storage issues. The intern must investigate the failure, apply fixes, validate the deployment, and document the troubleshooting process.',
                'skills': 'OpenShift, Kubernetes, Linux, container troubleshooting, YAML, logs, routes, pods, configuration',
                'deliverable': 'Working OpenShift deployment, troubleshooting notes, validation screenshots or outputs, and a short runbook.'
            }
        if 'security' in p or 'infosec' in p or 'cyber' in p or 'soc' in p:
            return {
                'project_title': 'Information Security Assessment and Incident Triage Demo',
                'objective': 'Review security controls, investigate sample alerts, triage vulnerabilities, and produce a concise security assessment with remediation recommendations.',
                'tech_stack': 'Linux logs, SIEM concepts, IAM, vulnerability management, incident response, security checklists',
                'scenario': 'A sample environment has suspicious authentication activity, vulnerable services, and incomplete access controls. The intern must review logs, triage findings, prioritize risk, and recommend remediation steps.',
                'skills': 'Information security, log analysis, vulnerability triage, IAM review, incident response, risk assessment, reporting',
                'deliverable': 'Security assessment report, incident triage notes, prioritized remediation list, and final presentation.'
            }
        if 'kubernetes' in p or 'k8s' in p:
            return {
                'project_title': 'Kubernetes Application Deployment and Troubleshooting Demo',
                'objective': 'Deploy, expose, observe, and troubleshoot a containerized application on Kubernetes.',
                'tech_stack': 'Linux, Docker/containers, Kubernetes, kubectl, YAML, Helm basics',
                'scenario': 'A containerized application has deployment, service, configuration, and health-check issues in Kubernetes. The intern must diagnose and fix the workload.',
                'skills': 'Kubernetes, kubectl, YAML, pods, deployments, services, logs, probes, troubleshooting',
                'deliverable': 'Working Kubernetes deployment, troubleshooting report, and short demo.'
            }
        return {
            'project_title': f'{plan_name} Final Practical Demo',
            'objective': f'Complete a practical project aligned with the {plan_name} plan and document the final outcome.',
            'tech_stack': plan_name,
            'scenario': f'A realistic work scenario aligned with the {plan_name} plan requires the intern to investigate, implement, validate, and document a solution.',
            'skills': plan_name,
            'deliverable': 'Working demo, notes, and final summary report.'
        }

'''
    marker = '    def _build_schedule_from_plan'
    if marker not in s:
        raise SystemExit('Could not find _build_schedule_from_plan insertion point.')
    s = s.replace(marker, helper + marker)

plan_service.write_text(s, encoding='utf-8')

# 3) Patch chat UI human summary to mention project/scenario when applying a plan.
if chat_html.exists():
    hs = chat_html.read_text(encoding='utf-8')
    old = "if(cmd === 'apply_plan_to_intern') return `I can apply ${args.plan_name || 'the selected plan'} to ${args.intern || 'the intern'}.`;"
    new = "if(cmd === 'apply_plan_to_intern') return `I can apply ${args.plan_name || 'the selected plan'} to ${args.intern || 'the intern'} and fill related main project/scenario defaults if they are blank.`;"
    if old in hs:
        hs = hs.replace(old, new)
    chat_html.write_text(hs, encoding='utf-8')

# 4) README note.
readme = root / 'README.md'
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.22 Apply Plan also fills project/scenario defaults

- Applying a plan now also fills Main Project and Real-World Scenario defaults when those fields are blank or generic.
- Topic-aware defaults are included for OpenShift, Information Security/Cybersecurity, and Kubernetes.
- Intern and plan names are stripped before lookup to avoid errors like `Intern not found: Musab Khan `.
- Existing manager-authored project/scenario text is preserved unless it is blank/generic.
''', encoding='utf-8')

print('v0.22 apply-plan project/scenario defaults patch applied successfully.')
