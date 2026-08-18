from datetime import date
from pathlib import Path

from autodar.models import Employee, PersonCells, ReportData, RoleConfig, TemplateCells, TemplateConfig
from autodar.validation import validate_report


def _template():
    return TemplateConfig(
        key="test", display_name="Test", file=Path("test.xlsx"), sheet="Sheet",
        output_filename="test.xlsx", patrol_prefix="Patrol:",
        cells=TemplateCells(
            shift_date="A1", team_leader=PersonCells("A2", "B2"),
            security_officers=(PersonCells("A3", "B3"), PersonCells("A4", "B4"), PersonCells("A5", "B5")),
            control_room=PersonCells("A6", "B6"), patrols=("A7", "A8", "A9"),
            dar_officer="A10", dar_date="A11",
        ),
    )


def test_duplicate_security_officers_are_rejected():
    leader = Employee("Leader", "1")
    officer = Employee("Officer", "2")
    control = Employee("Control", "3")
    data = ReportData(date.today(), leader, (officer, officer, Employee("Other", "4")), control, officer, leader)
    roles = RoleConfig(("1",), "all", ("3",))
    errors = validate_report(data, _template(), roles)
    assert "Security Officers must be different employees." in errors
