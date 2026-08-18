from datetime import date
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook

from autodar.config import load_templates
from autodar.employees import load_employees
from autodar.ooxml_writer import write_report
from autodar.models import ReportData


ROOT = Path(__file__).resolve().parents[1]


def test_morning_report_mapping_and_template_integrity(tmp_path):
    employees = list(load_employees(ROOT / "names_by_number.json").values())
    template = load_templates(ROOT / "templates.json", ROOT)["morning"]
    data = ReportData(
        shift_date=date(2026, 8, 19),
        team_leader=employees[0],
        security_officers=tuple(employees[1:4]),
        control_room=employees[4],
        patrol_officer=employees[1],
        dar_officer=employees[0],
    )
    output = tmp_path / "report.xlsx"
    write_report(template, data, output)

    original = load_workbook(template.file, data_only=False)
    generated = load_workbook(output, data_only=False)
    sheet = generated["Shift Report"]
    assert sheet["H9"].value == date(2026, 8, 19)
    assert (sheet["D17"].value, sheet["E17"].value) == (employees[0].name, employees[0].pin)
    for row, employee in zip((23, 24, 25), employees[1:4], strict=True):
        assert (sheet[f"D{row}"].value, sheet[f"E{row}"].value) == (employee.name, employee.pin)
    assert (sheet["D27"].value, sheet["E27"].value) == (employees[4].name, employees[4].pin)
    for row in (30, 31, 32):
        assert sheet[f"D{row}"].value == f"Patrol by security officer: {employees[1].name}"
    assert sheet["D35"].value == employees[0].name
    assert sheet["M35"].value == date(2026, 8, 19)
    assert generated.sheetnames == original.sheetnames
    assert set(generated["Shift Report"].merged_cells.ranges) == set(original["Shift Report"].merged_cells.ranges)
    for coordinate in ("F17", "H17", "J17", "L17", "F23", "H23", "J23", "L23", "M30"):
        assert sheet[coordinate].value == original["Shift Report"][coordinate].value
        assert sheet[coordinate].style_id == original["Shift Report"][coordinate].style_id
    original.close()
    generated.close()
    with ZipFile(template.file) as source, ZipFile(output) as result:
        assert source.read("xl/styles.xml") == result.read("xl/styles.xml")
        assert set(source.namelist()) == set(result.namelist())
        for name in source.namelist():
            if name != "xl/worksheets/sheet1.xml":
                assert source.read(name) == result.read(name)
