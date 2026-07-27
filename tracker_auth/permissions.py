
MUTATING_COMMANDS = {
    'create_workbook','render_workbook','extend_intern','extend_intern_with_plan','edit_task','update_task_status',
    'update_capstone','update_scenario','edit_project','update_project_status','add_intern',
    'add_intern_basic','add_intern_with_plan','add_holiday','create_plan','create_plan_from_draft',
    'edit_plan','edit_plan_week','apply_plan_to_intern'
}


def role_name(user: dict | None) -> str:
    if not user:
        return ''
    return (user.get('role') or '').strip()


def is_super_admin(user: dict | None) -> bool:
    return role_name(user).lower() == 'super admin'


def is_admin(user: dict | None) -> bool:
    return role_name(user).lower() == 'admin'


def is_user(user: dict | None) -> bool:
    return role_name(user).lower() == 'user'


def can_execute(user: dict | None, command: str) -> bool:
    if not user or user.get('status') != 'Active':
        return False
    # Normal users can use the tracker application normally.
    if is_super_admin(user) or is_admin(user) or is_user(user):
        return True
    # Legacy roles from earlier builds stay supported.
    if role_name(user) in {'Manager'}:
        return True
    if role_name(user) in {'Viewer'}:
        return command == 'summary'
    return False


def can_manage_users(user: dict | None) -> bool:
    return bool(user and user.get('status') == 'Active' and (is_super_admin(user) or is_admin(user)))


def can_view_logs(user: dict | None) -> bool:
    return bool(user and user.get('status') == 'Active' and (is_super_admin(user) or is_admin(user)))


def can_manage_admins(user: dict | None) -> bool:
    return is_super_admin(user)


def can_assign_role(actor: dict | None, role: str) -> bool:
    role = (role or '').strip()
    if is_super_admin(actor):
        return role in {'Admin', 'User'}
    if is_admin(actor):
        return role == 'User'
    return False


def can_modify_target(actor: dict | None, target: dict | None) -> bool:
    if not actor or not target:
        return False
    target_role = role_name(target)
    if is_super_admin(actor):
        # Super Admin can manage admins and users, but should not deactivate itself through simple UI.
        return target_role in {'Admin', 'User'}
    if is_admin(actor):
        return target_role == 'User'
    return False
