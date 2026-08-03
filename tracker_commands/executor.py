
from tracker_services.workbook_service import WorkbookService
from tracker_services.summary_service import SummaryService
from tracker_services.intern_service import InternService
from tracker_services.plan_service import PlanService
from tracker_commands.validator import CommandValidator


class CommandExecutor:
    def __init__(self):
        self.validator = CommandValidator()
        self.intern_service = InternService()
        self.workbook_service = WorkbookService()
        self.plan_service = PlanService()
        self.summary_service = SummaryService()

    def execute(self, payload: dict):
        item = self.validator.validate(payload)
        command = item["command"]
        args = item["args"]
        if command == "extend_intern_with_plan":
            return self.plan_service.extend_intern_with_plan(
                args["source"],
                args["intern"],
                args["new_end"],
                args["plan_name"],
                args.get("output"),
                bool(args.get("update_main_project", True)),
                args.get("extension_schedule_preview"),
                args.get("extension_main_title", ""),
                args.get("extension_objective", ""),
                args.get("extension_tech_stack", ""),
                args.get("extension_scenario", ""),
                args.get("extension_skills", ""),
                args.get("extension_deliverable", ""),
            )
        if command == "create_workbook":
            return self.workbook_service.create_fresh_workbook(args["output"])
        if command == "add_intern_with_plan":
            return self.plan_service.add_intern_with_plan(args["source"], args["name"], args["start_date"], args["end_date"], args["plan_name"], args.get("output"), args.get("manager", ""), args.get("skip_manager", ""), args.get("final_project", ""), args.get("main_title", ""), args.get("objective", ""), args.get("tech_stack", ""), args.get("scenario", ""), args.get("skills", ""), args.get("deliverable", ""), args.get("schedule_preview"))
        if command == "create_plan_from_draft":
            return self.plan_service.create_plan_from_draft(args["source"], args["plan_name"], args.get("description", ""), args.get("weeks", []), args.get("output"))
        if command == "create_plan":
            return self.plan_service.create_plan(args["source"], args["plan_name"], args.get("plan_type", "weekly"), args.get("description", ""), args.get("weeks", 8), args.get("output"))
        if command == "edit_plan":
            return self.plan_service.edit_plan(args["source"], args["plan_name"], args.get("new_name"), args.get("description"), args.get("output"))
        if command == "edit_plan_week":
            return self.plan_service.edit_plan_week(args["source"], args["plan_name"], args["week"], args.get("theme"), args.get("task"), args.get("weekly_project"), args.get("notes"), args.get("output"))
        if command == "apply_plan_to_intern":
            return self.plan_service.apply_plan_to_intern(args["source"], args["intern"], args["plan_name"], args.get("output"))
        if command == "add_intern_basic":
            return self.intern_service.add_intern_basic(args["source"], args.get("output"), args.get("name"), args.get("start_date"), args.get("end_date"), args.get("manager", ""), args.get("skip_manager", ""), args.get("plan_name", "Custom Plan"), args.get("final_project", ""), args.get("main_title", ""), args.get("objective", ""), args.get("tech_stack", ""), args.get("scenario", ""), args.get("skills", ""), args.get("deliverable", ""))
        if command == "add_holiday":
            return self.intern_service.add_holiday(args["source"], args["name"], args["date"], args.get("scope", "global"), args.get("output"), args.get("intern_name"))
        if command == "render_workbook":
            return self.workbook_service.create_clean_version(args["source"], args.get("output"))
        if command == "summary":
            return self.summary_service.generate_progress_summary(args["workbook"], args.get("intern"))
        if command == "extend_intern":
            return self.intern_service.extend_internship(args["source"], args["intern"], args["new_end"], args.get("output"))
        if command == "edit_task":
            return self.intern_service.edit_task(args["source"], args["intern"], args["task_ref"], args.get("output"), args.get("date"), args.get("week"), args.get("theme"), args.get("task"), args.get("status"), args.get("remarks"))
        if command == "update_task_status":
            return self.intern_service.update_task_status(args["source"], args["intern"], args["task_ref"], args["status"], args.get("output"))
        if command == "update_capstone":
            return self.intern_service.update_capstone(args["source"], args["intern"], args.get("output"), args.get("title"), args.get("objective"), args.get("tech_stack"), args.get("status"), args.get("target_end"))
        if command == "update_scenario":
            return self.intern_service.update_scenario(args["source"], args["intern"], args.get("output"), args.get("scenario"), args.get("skills"), args.get("deliverable"), args.get("assigned_week"), args.get("due_date"), args.get("status"))
        if command == "edit_project":
            return self.intern_service.edit_project(args["source"], args["intern"], args["project_number"], args.get("output"), args.get("title"), args.get("description"), args.get("assigned_date"), args.get("due_date"), args.get("status"))
        if command == "update_project_status":
            return self.intern_service.update_project_status(args["source"], args["intern"], args["project_number"], args["status"], args.get("output"))
        if command == "add_intern":
            return self.intern_service.add_intern_from_json(args["source"], args["spec"], args.get("output"))
        raise ValueError(f"Executor has no handler for command: {command}")
