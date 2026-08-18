from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .config import eligible_pins, load_roles, load_templates
from .employees import load_employees, sorted_employees
from .errors import AutoDARError, ConfigurationError
from .ooxml_writer import write_report
from .models import Employee, ReportData, RoleConfig, TemplateConfig
from .validation import validate_report

LOGGER = logging.getLogger(__name__)

APP_STYLESHEET = """
QMainWindow, QWidget#appRoot {
    background: #f3f5f4;
    color: #172321;
}
QLabel#appTitle {
    color: #102421;
    font-size: 24px;
    font-weight: 700;
}
QLabel#appContext {
    color: #64716f;
    font-size: 12px;
}
QFrame#accentLine {
    background: #168277;
    border: 0;
}
QGroupBox {
    background: #ffffff;
    border: 1px solid #d8dfdd;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    margin-top: 12px;
    padding: 16px 14px 14px 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #344441;
}
QLabel#fieldLabel {
    color: #53615f;
    font-size: 11px;
    font-weight: 600;
}
QComboBox, QDateEdit {
    min-height: 36px;
    padding: 0 10px;
    background: #ffffff;
    color: #172321;
    border: 1px solid #bdc9c6;
    border-radius: 5px;
    selection-background-color: #168277;
}
QComboBox:hover, QDateEdit:hover {
    border-color: #718d87;
}
QComboBox:focus, QDateEdit:focus {
    border: 2px solid #168277;
    padding-left: 9px;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #172321;
    border: 1px solid #bdc9c6;
    selection-background-color: #dcefeb;
    selection-color: #102421;
    outline: 0;
    padding: 4px;
}
QPushButton {
    min-height: 36px;
    padding: 0 16px;
    border: 1px solid #bdc9c6;
    border-radius: 5px;
    background: #ffffff;
    color: #263532;
    font-weight: 600;
}
QPushButton:hover {
    background: #edf2f0;
    border-color: #8ba09b;
}
QPushButton:pressed {
    background: #e1e8e6;
}
QPushButton#primaryButton {
    background: #168277;
    border-color: #168277;
    color: #ffffff;
    padding: 0 20px;
}
QPushButton#primaryButton:hover {
    background: #116e65;
    border-color: #116e65;
}
QPushButton#openButton {
    background: #fff8e8;
    border-color: #e3c77c;
    color: #644d12;
}
QLabel#statusLabel {
    color: #53615f;
    font-size: 11px;
}
QCalendarWidget QWidget {
    background: #ffffff;
    color: #172321;
}
QCalendarWidget QAbstractItemView:enabled {
    selection-background-color: #168277;
    selection-color: #ffffff;
}
"""


class EmployeeCombo(QComboBox):
    def __init__(self) -> None:
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMinimumWidth(260)
        self.setFixedHeight(38)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setPlaceholderText("Select employee")
        completer = self.completer()
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_employees(self, employees: list[Employee], preserve_pin: str | None = None) -> None:
        self.blockSignals(True)
        self.clear()
        self.addItem("", None)
        selected_index = 0
        for employee in employees:
            self.addItem(employee.name, employee.pin)
            if employee.pin == preserve_pin:
                selected_index = self.count() - 1
        self.setCurrentIndex(selected_index)
        self.blockSignals(False)

    def employee_pin(self) -> str | None:
        value = self.currentData()
        return value if isinstance(value, str) else None


class MainWindow(QMainWindow):
    def __init__(self, project_dir: Path) -> None:
        super().__init__()
        self.project_dir = project_dir
        self.employees = load_employees(project_dir / "names_by_number.json")
        self.roles = load_roles(project_dir / "roles.json", set(self.employees))
        self.templates = load_templates(project_dir / "templates.json", project_dir)
        self.last_report: Path | None = None
        self._build_ui()
        self._load_template(self.template_combo.currentData())

    def _build_ui(self) -> None:
        self.setWindowTitle("AutoDAR Shift Report")
        self.setMinimumSize(780, 680)
        self.resize(900, 700)
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(APP_STYLESHEET)
        central = QWidget()
        central.setObjectName("appRoot")
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("Shift Report")
        title.setObjectName("appTitle")
        context = QLabel("HFA18 Operations")
        context.setObjectName("appContext")
        header.addWidget(title)
        header.addWidget(context)
        root.addLayout(header)
        accent = QFrame()
        accent.setObjectName("accentLine")
        accent.setFixedHeight(3)
        root.addWidget(accent)

        shift_box = QGroupBox("Shift")
        shift_form = QFormLayout(shift_box)
        shift_form.setContentsMargins(14, 18, 14, 12)
        shift_form.setHorizontalSpacing(18)
        shift_form.setVerticalSpacing(8)
        shift_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.template_combo = QComboBox()
        for key, template in self.templates.items():
            self.template_combo.addItem(template.display_name, key)
        self.shift_date = QDateEdit(QDate.currentDate())
        self.shift_date.setFixedHeight(38)
        self.shift_date.setCalendarPopup(True)
        self.shift_date.setDisplayFormat("dd/MM/yyyy")
        shift_form.addRow("Template", self.template_combo)
        shift_form.addRow("Shift Date", self.shift_date)
        root.addWidget(shift_box)

        personnel = QGroupBox("Personnel")
        personnel.setMinimumHeight(236)
        grid = QGridLayout(personnel)
        grid.setContentsMargins(14, 18, 14, 14)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)
        self.team_leader = EmployeeCombo()
        self.officers = [EmployeeCombo() for _ in range(3)]
        self.control_room = EmployeeCombo()
        personnel_fields = [("Security Team Leader", self.team_leader)]
        personnel_fields += [(f"Security Officer {index + 1}", combo) for index, combo in enumerate(self.officers)]
        personnel_fields.append(("Control Room", self.control_room))
        for index, (label, combo) in enumerate(personnel_fields):
            row, column = divmod(index, 2)
            field = QWidget()
            field_layout = QVBoxLayout(field)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(5)
            label_widget = QLabel(label)
            label_widget.setObjectName("fieldLabel")
            label_widget.setFixedHeight(16)
            field_layout.addWidget(label_widget)
            field_layout.addWidget(combo)
            grid.addWidget(field, row, column)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        root.addWidget(personnel)

        lower = QHBoxLayout()
        lower.setSpacing(12)
        patrol_box = QGroupBox("Patrol")
        patrol_form = QFormLayout(patrol_box)
        self.patrol_officer = EmployeeCombo()
        patrol_form.addRow("Patrol by Security Officer", self.patrol_officer)
        lower.addWidget(patrol_box)
        dar_box = QGroupBox("DAR")
        dar_form = QFormLayout(dar_box)
        self.dar_officer = EmployeeCombo()
        dar_form.addRow("DAR completed by", self.dar_officer)
        lower.addWidget(dar_box)
        root.addLayout(lower)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(line)
        buttons = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        buttons.addWidget(self.status_label, 1)
        self.open_button = QPushButton("Open Report")
        self.open_button.setObjectName("openButton")
        self.open_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.open_button.setToolTip("Open the last generated report")
        self.open_button.setVisible(False)
        clear_button = QPushButton("Clear Form")
        clear_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton))
        clear_button.setToolTip("Reset all selections")
        generate_button = QPushButton("Generate Report")
        generate_button.setObjectName("primaryButton")
        generate_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        generate_button.setToolTip("Generate and save the Excel report")
        generate_button.setDefault(True)
        buttons.addWidget(self.open_button)
        buttons.addWidget(clear_button)
        buttons.addWidget(generate_button)
        root.addLayout(buttons)
        self.setCentralWidget(central)

        self.template_combo.currentIndexChanged.connect(lambda: self._load_template(self.template_combo.currentData()))
        for combo in [self.team_leader, *self.officers, self.control_room]:
            combo.currentIndexChanged.connect(self._validate_primary_selection)
        clear_button.clicked.connect(self.clear_form)
        generate_button.clicked.connect(self.generate_report)
        self.open_button.clicked.connect(self.open_report)

    @property
    def template(self) -> TemplateConfig:
        return self.templates[self.template_combo.currentData()]

    def _eligible(self, role_value: tuple[str, ...] | str) -> list[Employee]:
        pins = eligible_pins(role_value, self.employees)
        return [employee for employee in sorted_employees(self.employees) if employee.pin in pins]

    def _load_template(self, _key: str) -> None:
        template = self.template
        if len(template.cells.security_officers) != 3 or len(template.cells.patrols) != 3:
            raise ConfigurationError("The current GUI requires three officer positions and three patrol output rows.")
        self.team_leader.set_employees(self._eligible(self.roles.team_leaders))
        officer_pool = self._eligible(self.roles.security_officers)
        for combo in self.officers:
            combo.set_employees(officer_pool)
        self.control_room.set_employees(self._eligible(self.roles.control_room))
        self.patrol_officer.set_employees(officer_pool)
        self.dar_officer.set_employees(sorted_employees(self.employees))
        missing = []
        if not self._eligible(self.roles.team_leaders):
            missing.append("team_leaders")
        if not self._eligible(self.roles.control_room):
            missing.append("control_room")
        self.status_label.setText(f"Configure {', '.join(missing)} in roles.json" if missing else "")

    def _primary_pins(self) -> list[str]:
        return [pin for pin in [self.team_leader.employee_pin(), *(c.employee_pin() for c in self.officers), self.control_room.employee_pin()] if pin]

    def _validate_primary_selection(self) -> None:
        if not self.roles.allow_primary_role_overlap:
            selected = self._primary_pins()
            if len(selected) != len(set(selected)):
                sender = self.sender()
                if isinstance(sender, EmployeeCombo):
                    QMessageBox.warning(self, "Duplicate employee", "That employee already occupies another primary position.")
                    sender.setCurrentIndex(0)

    def clear_form(self) -> None:
        for combo in [self.team_leader, *self.officers, self.control_room, self.patrol_officer, self.dar_officer]:
            combo.setCurrentIndex(0)
        self.shift_date.setDate(QDate.currentDate())
        self.last_report = None
        self.open_button.setVisible(False)
        self.status_label.setText("")

    def _selected(self, combo: EmployeeCombo, label: str, missing: list[str]) -> Employee | None:
        pin = combo.employee_pin()
        if not pin:
            missing.append(label)
            return None
        return self.employees[pin]

    def _report_data(self) -> ReportData | None:
        missing: list[str] = []
        leader = self._selected(self.team_leader, "Security Team Leader", missing)
        officers = [self._selected(combo, f"Security Officer {i + 1}", missing) for i, combo in enumerate(self.officers)]
        control = self._selected(self.control_room, "Control Room", missing)
        patrol = self._selected(self.patrol_officer, "Patrol by Security Officer", missing)
        dar = self._selected(self.dar_officer, "DAR completed by", missing)
        if missing:
            QMessageBox.warning(self, "Missing information", "Complete these fields:\n\n" + "\n".join(f"- {field}" for field in missing))
            return None
        return ReportData(
            shift_date=self.shift_date.date().toPython(),
            team_leader=leader,
            security_officers=tuple(officers),
            control_room=control,
            patrol_officer=patrol,
            dar_officer=dar,
        )

    def generate_report(self) -> None:
        data = self._report_data()
        if data is None:
            return
        errors = validate_report(data, self.template, self.roles)
        if errors:
            QMessageBox.warning(self, "Cannot generate report", "\n".join(errors))
            return
        suggested = self.template.output_filename.format(date=data.shift_date.isoformat())
        destination, _ = QFileDialog.getSaveFileName(self, "Save Shift Report", str(self.project_dir / suggested), "Excel Workbook (*.xlsx)")
        if not destination:
            return
        if not destination.lower().endswith(".xlsx"):
            destination += ".xlsx"
        try:
            write_report(self.template, data, Path(destination))
        except AutoDARError as exc:
            QMessageBox.critical(self, "Report generation failed", str(exc))
            return
        self.last_report = Path(destination)
        self.open_button.setVisible(True)
        self.status_label.setText(str(self.last_report))
        QMessageBox.information(self, "Report generated", f"Report generated successfully.\n\n{self.last_report}")

    def open_report(self) -> None:
        if self.last_report and self.last_report.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_report)))


def run(project_dir: Path) -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("AutoDAR")
    try:
        window = MainWindow(project_dir)
    except AutoDARError as exc:
        LOGGER.exception("Application startup failed")
        QMessageBox.critical(None, "AutoDAR could not start", str(exc))
        return 1
    window.show()
    return app.exec()
