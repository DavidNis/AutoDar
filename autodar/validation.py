from __future__ import annotations

from .models import ReportData, RoleConfig, TemplateConfig


def validate_report(data: ReportData, template: TemplateConfig, roles: RoleConfig) -> list[str]:
    errors: list[str] = []
    if len(data.security_officers) != len(template.cells.security_officers):
        errors.append(f"Select all {len(template.cells.security_officers)} Security Officers.")
    if len(data.patrols) != len(template.cells.patrols):
        errors.append(f"Select all {len(template.cells.patrols)} Patrol officers.")
    officer_pins = [employee.pin for employee in data.security_officers]
    if len(officer_pins) != len(set(officer_pins)):
        errors.append("Security Officers must be different employees.")
    if not roles.allow_primary_role_overlap:
        primary = [data.team_leader.pin, *officer_pins, data.control_room.pin]
        if len(primary) != len(set(primary)):
            errors.append("An employee cannot occupy more than one primary position.")
    if roles.patrol_source == "assigned_security_officers":
        invalid = [employee.name for employee in data.patrols if employee.pin not in set(officer_pins)]
        if invalid:
            errors.append("Patrol employees must be assigned Security Officers.")
    if roles.dar_source == "assigned_shift_employees":
        assigned = {data.team_leader.pin, *officer_pins, data.control_room.pin}
        if data.dar_officer.pin not in assigned:
            errors.append("DAR completed by must be an employee assigned to this shift.")
    return errors

