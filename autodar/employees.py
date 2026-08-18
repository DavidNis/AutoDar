from __future__ import annotations

import json
from pathlib import Path

from .errors import ConfigurationError
from .models import Employee


def load_employees(path: Path) -> dict[str, Employee]:
    if not path.is_file():
        raise ConfigurationError(f"Employee database was not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Employee database is not valid JSON: {path}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("Employee database must be a JSON object of PIN-to-name entries.")

    employees: dict[str, Employee] = {}
    for pin, name in raw.items():
        if not isinstance(pin, str) or not pin.isdigit() or not pin:
            raise ConfigurationError(f"Invalid employee PIN: {pin!r}")
        if not isinstance(name, str) or not name.strip():
            raise ConfigurationError(f"Employee {pin} has an invalid name.")
        employees[pin] = Employee(name=name.strip(), pin=pin)
    if not employees:
        raise ConfigurationError("Employee database is empty.")
    return employees


def sorted_employees(employees: dict[str, Employee]) -> list[Employee]:
    return sorted(employees.values(), key=lambda item: (item.name.casefold(), item.pin))

