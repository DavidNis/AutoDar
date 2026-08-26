from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openpyxl.utils.cell import coordinate_to_tuple

from .errors import ConfigurationError
from .models import PersonCells, RoleConfig, TemplateCells, TemplateConfig


def _load_json(path: Path, label: str) -> Any:
    if not path.is_file():
        raise ConfigurationError(f"{label} was not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"{label} is not valid JSON: {path}") from exc


def _pins(value: Any, field: str) -> tuple[str, ...] | str:
    if value == "all":
        return "all"
    if not isinstance(value, list) or any(not isinstance(pin, str) or not pin.isdigit() for pin in value):
        raise ConfigurationError(f"roles.json field '{field}' must be 'all' or a list of PIN strings.")
    return tuple(value)


def load_roles(path: Path, employee_pins: set[str]) -> RoleConfig:
    raw = _load_json(path, "Role configuration")
    if not isinstance(raw, dict):
        raise ConfigurationError("roles.json must contain a JSON object.")
    settings = raw.get("settings", {})
    if not isinstance(settings, dict):
        raise ConfigurationError("roles.json 'settings' must be a JSON object.")
    roles = RoleConfig(
        team_leaders=_pins(raw.get("team_leaders"), "team_leaders"),
        security_officers=_pins(raw.get("security_officers"), "security_officers"),
        control_room=_pins(raw.get("control_room"), "control_room"),
        allow_primary_role_overlap=bool(settings.get("allow_primary_role_overlap", False)),
        patrol_source=str(settings.get("patrol_source", "all_security_officers")),
        dar_source=str(settings.get("dar_source", "all_employees")),
    )
    for field in ("team_leaders", "security_officers", "control_room"):
        value = getattr(roles, field)
        if value != "all":
            unknown = sorted(set(value) - employee_pins)
            if unknown:
                raise ConfigurationError(f"Unknown PIN(s) in roles.json '{field}': {', '.join(unknown)}")
    if roles.patrol_source not in {"assigned_security_officers", "all_security_officers"}:
        raise ConfigurationError("Unsupported patrol_source setting.")
    if roles.dar_source not in {"assigned_shift_employees", "all_employees"}:
        raise ConfigurationError("Unsupported dar_source setting.")
    return roles


def _cell(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(f"Template cell '{field}' must be an Excel cell reference.")
    try:
        coordinate_to_tuple(value)
    except ValueError as exc:
        raise ConfigurationError(f"Invalid Excel cell reference for '{field}': {value}") from exc
    return value.upper()


def _person(value: Any, field: str) -> PersonCells:
    if not isinstance(value, dict):
        raise ConfigurationError(f"Template field '{field}' must contain name and pin cells.")
    return PersonCells(_cell(value.get("name"), f"{field}.name"), _cell(value.get("pin"), f"{field}.pin"))


def load_templates(path: Path, project_dir: Path) -> dict[str, TemplateConfig]:
    raw = _load_json(path, "Template configuration")
    if not isinstance(raw, dict) or not raw:
        raise ConfigurationError("templates.json must contain at least one template.")
    templates: dict[str, TemplateConfig] = {}
    for key, item in raw.items():
        if not isinstance(item, dict) or not isinstance(item.get("cells"), dict):
            raise ConfigurationError(f"Template '{key}' is invalid.")
        cells = item["cells"]
        officers = cells.get("security_officers")
        patrols = cells.get("patrols")
        if not isinstance(officers, list) or not officers:
            raise ConfigurationError(f"Template '{key}' requires security officer cell mappings.")
        if not isinstance(patrols, list) or not patrols:
            raise ConfigurationError(f"Template '{key}' requires patrol cell mappings.")
        filename = item.get("file")
        if not isinstance(filename, str) or not filename:
            raise ConfigurationError(f"Template '{key}' requires a file name.")
        templates[key] = TemplateConfig(
            key=key,
            display_name=str(item.get("display_name", key)),
            file=project_dir / filename,
            sheet=str(item.get("sheet", "")),
            output_filename=str(item.get("output_filename", f"{key} {{date}}.xlsx")),
            patrol_prefix=str(item.get("patrol_prefix", "Patrol by security officer:")),
            cells=TemplateCells(
                shift_date=_cell(cells.get("shift_date"), "shift_date"),
                team_leader=_person(cells.get("team_leader"), "team_leader"),
                security_officers=tuple(_person(value, "security_officers") for value in officers),
                control_room=_person(cells.get("control_room"), "control_room"),
                patrols=tuple(_cell(value, "patrols") for value in patrols),
                dar_officer=_cell(cells.get("dar_officer"), "dar_officer"),
                dar_date=_cell(cells.get("dar_date"), "dar_date"),
            ),
            security_officers_required=bool(item.get("security_officers_required", True)),
        )
    return templates


def eligible_pins(value: tuple[str, ...] | str, employees: dict[str, object]) -> set[str]:
    return set(employees) if value == "all" else set(value)
