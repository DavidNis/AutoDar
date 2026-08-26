from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True, order=True)
class Employee:
    name: str
    pin: str


@dataclass(frozen=True)
class PersonCells:
    name: str
    pin: str


@dataclass(frozen=True)
class TemplateCells:
    shift_date: str
    team_leader: PersonCells
    security_officers: tuple[PersonCells, ...]
    control_room: PersonCells
    patrols: tuple[str, ...]
    dar_officer: str
    dar_date: str


@dataclass(frozen=True)
class TemplateConfig:
    key: str
    display_name: str
    file: Path
    sheet: str
    output_filename: str
    patrol_prefix: str
    cells: TemplateCells
    security_officers_required: bool = True


@dataclass(frozen=True)
class RoleConfig:
    team_leaders: tuple[str, ...] | str
    security_officers: tuple[str, ...] | str
    control_room: tuple[str, ...] | str
    allow_primary_role_overlap: bool = False
    patrol_source: str = "all_security_officers"
    dar_source: str = "all_employees"


@dataclass(frozen=True)
class ReportData:
    shift_date: date
    team_leader: Employee
    security_officers: tuple[Employee, ...]
    control_room: Employee
    patrol_officer: Employee
    dar_officer: Employee
