import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDateEdit

from autodar.gui import EmployeeCombo, MainWindow


ROOT = Path(__file__).resolve().parents[1]


def _window() -> MainWindow:
    QApplication.instance() or QApplication([])
    return MainWindow(ROOT)


def test_gui_has_one_date_picker_and_one_patrol_selector():
    window = _window()
    try:
        assert len(window.findChildren(QDateEdit)) == 1
        assert isinstance(window.patrol_officer, EmployeeCombo)
        assert not hasattr(window, "patrols")
        assert not hasattr(window, "dar_date")
    finally:
        window.close()


def test_employee_dropdowns_show_names_and_store_pins():
    window = _window()
    try:
        combos = [window.team_leader, *window.officers, window.control_room, window.patrol_officer, window.dar_officer]
        for combo in combos:
            for index in range(1, combo.count()):
                pin = combo.itemData(index)
                assert combo.itemText(index) == window.employees[pin].name
                assert pin not in combo.itemText(index)
        assert window.dar_officer.count() == len(window.employees) + 1
        assert window.patrol_officer.count() == len(window.employees) + 1
    finally:
        window.close()
