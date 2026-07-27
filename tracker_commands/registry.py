
COMMAND_SCHEMAS = {
    "add_intern_with_plan": {"required": ["source", "name", "start_date", "end_date", "plan_name", "output"], "optional": ["manager", "skip_manager", "final_project", "main_title", "objective", "tech_stack", "scenario", "skills", "deliverable"], "description": "Add an intern and apply a selected plan in one approved workflow."},
    "create_plan_from_draft": {"required": ["source", "plan_name", "weeks", "output"], "optional": ["description"], "description": "Create a full plan from an approved LLM draft."},
    "create_plan": {"required": ["source", "plan_name"], "optional": ["plan_type", "description", "weeks", "output"], "description": "Create a reusable learning plan."},
    "edit_plan": {"required": ["source", "plan_name"], "optional": ["new_name", "description", "output"], "description": "Edit plan metadata."},
    "edit_plan_week": {"required": ["source", "plan_name", "week"], "optional": ["theme", "task", "weekly_project", "notes", "output"], "description": "Edit one week of a plan."},
    "apply_plan_to_intern": {"required": ["source", "intern", "plan_name"], "optional": ["output"], "description": "Apply plan schedule to an intern."},
    "add_intern_basic": {
        "required": ["source", "name", "start_date", "end_date"],
        "optional": ["manager", "skip_manager", "plan_name", "final_project", "main_title", "objective", "tech_stack", "scenario", "skills", "deliverable", "output"],
        "description": "Add intern from form fields and create placeholder daily tasks, weekly updates, and weekly projects."
    },
    "add_holiday": {
        "required": ["source", "name", "date"],
        "optional": ["scope", "intern_name", "output"],
        "description": "Add global or intern-specific holiday and refresh schedules."
    },
    "create_workbook": {
        "required": ["output"],
        "optional": [],
        "description": "Create a fresh blank automation-ready tracker workbook without source."
    },
    "render_workbook": {
        "required": ["source"],
        "optional": ["output"],
        "description": "Create a clean rendered workbook from an uploaded workbook."
    },
    "summary": {
        "required": ["workbook"],
        "optional": ["intern"],
        "description": "Generate progress summary for all interns or one intern."
    },
    "extend_intern": {
        "required": ["source", "intern", "new_end"],
        "optional": ["output"],
        "description": "Extend intern end date and add daily tasks, weekly updates, weekly projects."
    },
    "extend_intern_with_plan": {
        "required": ["source", "intern", "new_end", "plan_name"],
        "optional": ["output", "update_main_project"],
        "description": "Extend intern end date using a second plan as context for the extension period's daily tasks, weekly updates, and weekly projects."
    },
    "edit_task": {
        "required": ["source", "intern", "task_ref"],
        "optional": ["date", "week", "theme", "task", "status", "remarks", "output"],
        "description": "Edit an existing task row. No add/delete."
    },
    "update_task_status": {
        "required": ["source", "intern", "task_ref", "status"],
        "optional": ["output"],
        "description": "Update an existing task status."
    },
    "update_capstone": {
        "required": ["source", "intern"],
        "optional": ["title", "objective", "tech_stack", "status", "target_end", "output"],
        "description": "Update main project/capstone section."
    },
    "update_scenario": {
        "required": ["source", "intern"],
        "optional": ["scenario", "skills", "deliverable", "assigned_week", "due_date", "status", "output"],
        "description": "Update real-world scenario section."
    },
    "edit_project": {
        "required": ["source", "intern", "project_number"],
        "optional": ["title", "description", "assigned_date", "due_date", "status", "output"],
        "description": "Edit existing small/weekly project row."
    },
    "update_project_status": {
        "required": ["source", "intern", "project_number", "status"],
        "optional": ["output"],
        "description": "Update existing weekly project status."
    },
    "add_intern": {
        "required": ["source", "spec"],
        "optional": ["output"],
        "description": "Add intern from JSON spec."
    }
}

ALLOWED_STATUSES = {"Pending", "In Progress", "Completed"}
