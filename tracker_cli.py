import argparse
from tracker_services.workbook_service import WorkbookService
from tracker_services.summary_service import SummaryService
from tracker_services.intern_service import InternService


def print_result(result):
    print(result.message)
    if result.output_path:
        print(result.output_path)
    if result.data.get('summary'):
        print(result.data['summary'])


def main():
    parser = argparse.ArgumentParser(prog='intern-tracker', description='Intern Tracker command-first system')
    sub = parser.add_subparsers(dest='command', required=True)


    p = sub.add_parser('create-workbook', help='Create a fresh blank tracker workbook without source')
    p.add_argument('--output', required=True)

    p = sub.add_parser('render', help='Create a clean rendered workbook from an uploaded workbook')
    p.add_argument('--source', required=True)
    p.add_argument('--output')

    p = sub.add_parser('summary', help='Generate progress summary')
    p.add_argument('--workbook', required=True)
    p.add_argument('--intern')

    p = sub.add_parser('add-intern', help='Add intern from JSON spec and create a new workbook version')
    p.add_argument('--source', required=True)
    p.add_argument('--spec', required=True)
    p.add_argument('--output')






    p = sub.add_parser('create-plan', help='Create a reusable learning plan')
    p.add_argument('--source', required=True)
    p.add_argument('--plan-name', required=True)
    p.add_argument('--plan-type', default='weekly')
    p.add_argument('--description', default='')
    p.add_argument('--weeks', type=int, default=8)
    p.add_argument('--output')

    p = sub.add_parser('edit-plan', help='Edit plan metadata')
    p.add_argument('--source', required=True)
    p.add_argument('--plan-name', required=True)
    p.add_argument('--new-name')
    p.add_argument('--description')
    p.add_argument('--output')

    p = sub.add_parser('edit-plan-week', help='Edit one week in a plan')
    p.add_argument('--source', required=True)
    p.add_argument('--plan-name', required=True)
    p.add_argument('--week', required=True, type=int)
    p.add_argument('--theme')
    p.add_argument('--task')
    p.add_argument('--weekly-project')
    p.add_argument('--notes')
    p.add_argument('--output')

    p = sub.add_parser('apply-plan-to-intern', help='Apply a plan to an intern schedule')
    p.add_argument('--source', required=True)
    p.add_argument('--intern', required=True)
    p.add_argument('--plan-name', required=True)
    p.add_argument('--output')

    p = sub.add_parser('add-intern-basic', help='Add intern from form-style fields, no JSON required')
    p.add_argument('--source', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--start-date', required=True)
    p.add_argument('--end-date', required=True)
    p.add_argument('--manager', default='')
    p.add_argument('--skip-manager', default='')
    p.add_argument('--plan-name', default='Custom Plan')
    p.add_argument('--final-project', default='')
    p.add_argument('--main-title', default='')
    p.add_argument('--objective', default='')
    p.add_argument('--tech-stack', default='')
    p.add_argument('--scenario', default='')
    p.add_argument('--skills', default='')
    p.add_argument('--deliverable', default='')
    p.add_argument('--output')

    p = sub.add_parser('add-holiday', help='Add global or intern-specific holiday')
    p.add_argument('--source', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--date', required=True)
    p.add_argument('--scope', default='global', choices=['global','intern'])
    p.add_argument('--intern-name')
    p.add_argument('--output')

    p = sub.add_parser('update-scenario', help='Update real-world scenario details')
    p.add_argument('--source', required=True)
    p.add_argument('--intern', required=True)
    p.add_argument('--scenario')
    p.add_argument('--skills')
    p.add_argument('--deliverable')
    p.add_argument('--assigned-week', type=int)
    p.add_argument('--due-date')
    p.add_argument('--status', choices=['Pending','In Progress','Completed'])
    p.add_argument('--output')

    p = sub.add_parser('edit-project', help='Edit an existing weekly/small project')
    p.add_argument('--source', required=True)
    p.add_argument('--intern', required=True)
    p.add_argument('--project-number', required=True, type=int)
    p.add_argument('--title')
    p.add_argument('--description')
    p.add_argument('--assigned-date')
    p.add_argument('--due-date')
    p.add_argument('--status', choices=['Pending','In Progress','Completed'])
    p.add_argument('--output')

    p = sub.add_parser('edit-task', help='Edit an existing daily task without adding/deleting rows')
    p.add_argument('--source', required=True)
    p.add_argument('--intern', required=True)
    p.add_argument('--task-ref', required=True, help='Task number, date YYYY-MM-DD, or text contained in task description')
    p.add_argument('--date')
    p.add_argument('--week', type=int)
    p.add_argument('--theme')
    p.add_argument('--task')
    p.add_argument('--status', choices=['Pending','In Progress','Completed'])
    p.add_argument('--remarks')
    p.add_argument('--output')

    p = sub.add_parser('update-task-status', help='Update a daily task status')
    p.add_argument('--source', required=True)
    p.add_argument('--intern', required=True)
    p.add_argument('--task-ref', required=True, help='Task number, date YYYY-MM-DD, or text contained in task description')
    p.add_argument('--status', required=True, choices=['Pending','In Progress','Completed'])
    p.add_argument('--output')

    p = sub.add_parser('edit-task-remarks', help='Edit daily task remarks')
    p.add_argument('--source', required=True)
    p.add_argument('--intern', required=True)
    p.add_argument('--task-ref', required=True)
    p.add_argument('--remarks', required=True)
    p.add_argument('--output')

    p = sub.add_parser('update-capstone', help='Update main project / capstone details')
    p.add_argument('--source', required=True)
    p.add_argument('--intern', required=True)
    p.add_argument('--title')
    p.add_argument('--objective')
    p.add_argument('--tech-stack')
    p.add_argument('--status')
    p.add_argument('--target-end')
    p.add_argument('--output')

    p = sub.add_parser('update-project-status', help='Update weekly project status')
    p.add_argument('--source', required=True)
    p.add_argument('--intern', required=True)
    p.add_argument('--project-number', required=True, type=int)
    p.add_argument('--status', required=True, choices=['Pending','In Progress','Completed'])
    p.add_argument('--output')

    p = sub.add_parser('extend-intern', help='Extend intern by new end date and create a new workbook version')
    p.add_argument('--source', required=True)
    p.add_argument('--intern', required=True)
    p.add_argument('--new-end', required=True)
    p.add_argument('--output')

    args = parser.parse_args()
    if args.command == 'create-workbook':
        result = WorkbookService().create_fresh_workbook(args.output)
    elif args.command == 'render':
        result = WorkbookService().create_clean_version(args.source, args.output)
    elif args.command == 'summary':
        result = SummaryService().generate_progress_summary(args.workbook, args.intern)
    elif args.command == 'add-intern':
        result = InternService().add_intern_from_json(args.source, args.spec, args.output)
    elif args.command == 'extend-intern':
        result = InternService().extend_internship(args.source, args.intern, args.new_end, args.output)
    elif args.command == 'create-plan':
        from tracker_services.plan_service import PlanService
        result = PlanService().create_plan(args.source, args.plan_name, args.plan_type, args.description, args.weeks, args.output)
    elif args.command == 'edit-plan':
        from tracker_services.plan_service import PlanService
        result = PlanService().edit_plan(args.source, args.plan_name, args.new_name, args.description, args.output)
    elif args.command == 'edit-plan-week':
        from tracker_services.plan_service import PlanService
        result = PlanService().edit_plan_week(args.source, args.plan_name, args.week, args.theme, args.task, args.weekly_project, args.notes, args.output)
    elif args.command == 'apply-plan-to-intern':
        from tracker_services.plan_service import PlanService
        result = PlanService().apply_plan_to_intern(args.source, args.intern, args.plan_name, args.output)
    elif args.command == 'add-intern-basic':
        result = InternService().add_intern_basic(args.source, args.output, args.name, args.start_date, args.end_date, args.manager, args.skip_manager, args.plan_name, args.final_project, args.main_title, args.objective, args.tech_stack, args.scenario, args.skills, args.deliverable)
    elif args.command == 'add-holiday':
        result = InternService().add_holiday(args.source, args.name, args.date, args.scope, args.output, args.intern_name)
    elif args.command == 'update-scenario':
        result = InternService().update_scenario(args.source, args.intern, args.output, args.scenario, args.skills, args.deliverable, args.assigned_week, args.due_date, args.status)
    elif args.command == 'edit-project':
        result = InternService().edit_project(args.source, args.intern, args.project_number, args.output, args.title, args.description, args.assigned_date, args.due_date, args.status)
    elif args.command == 'edit-task':
        result = InternService().edit_task(args.source, args.intern, args.task_ref, args.output, args.date, args.week, args.theme, args.task, args.status, args.remarks)
    elif args.command == 'update-task-status':
        result = InternService().update_task_status(args.source, args.intern, args.task_ref, args.status, args.output)
    elif args.command == 'edit-task-remarks':
        result = InternService().edit_task_remarks(args.source, args.intern, args.task_ref, args.remarks, args.output)
    elif args.command == 'update-capstone':
        result = InternService().update_capstone(args.source, args.intern, args.output, args.title, args.objective, args.tech_stack, args.status, args.target_end)
    elif args.command == 'update-project-status':
        result = InternService().update_project_status(args.source, args.intern, args.project_number, args.status, args.output)
    else:
        raise SystemExit('Unknown command')
    print_result(result)

if __name__ == '__main__':
    main()
