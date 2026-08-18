import json

import pytest

from autodar.employees import load_employees
from autodar.errors import ConfigurationError


def test_employee_lookup_preserves_pin_and_name(tmp_path):
    path = tmp_path / "employees.json"
    path.write_text(json.dumps({"001234567": "Test Person"}), encoding="utf-8")
    employees = load_employees(path)
    assert employees["001234567"].name == "Test Person"
    assert employees["001234567"].pin == "001234567"


def test_malformed_employee_json_has_clear_error(tmp_path):
    path = tmp_path / "employees.json"
    path.write_text("{bad", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="not valid JSON"):
        load_employees(path)

