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


def test_configured_team_leader_and_control_room_membership():
    window = _window()
    try:
        team_leaders = {window.team_leader.itemText(index) for index in range(1, window.team_leader.count())}
        control_room = {window.control_room.itemText(index) for index in range(1, window.control_room.count())}
        assert team_leaders == {
            "Evgeni Kanaev", "Shlomo Esayas", "Omer Buzaglo", "Aviv Kobrin",
            "Avraham Taganiya", "Itay Bakar", "Meital Sabatan", "Michael Morozov",
            "Maxim Yarkho", "Neorai Kadosh", "Keren Or Belmut", "Ron Furman",
        }
        assert control_room == team_leaders | {"Lior Levy", "Adi Uliel", "David Nisanov"}
    finally:
        window.close()


def test_shift_selector_lists_all_templates_and_preserves_selections():
    window = _window()
    try:
        assert [window.template_combo.itemText(index) for index in range(window.template_combo.count())] == [
            "Morning", "Evening", "Night", "Weekend"
        ]
        window.team_leader.setCurrentIndex(1)
        window.officers[0].setCurrentIndex(1)
        window.control_room.setCurrentIndex(4)
        window.patrol_officer.setCurrentIndex(2)
        window.dar_officer.setCurrentIndex(3)
        selected = (
            window.team_leader.employee_pin(),
            window.officers[0].employee_pin(),
            window.control_room.employee_pin(),
            window.patrol_officer.employee_pin(),
            window.dar_officer.employee_pin(),
        )
        window.template_combo.setCurrentIndex(1)
        assert (
            window.team_leader.employee_pin(),
            window.officers[0].employee_pin(),
            window.control_room.employee_pin(),
            window.patrol_officer.employee_pin(),
            window.dar_officer.employee_pin(),
        ) == selected
    finally:
        window.close()
