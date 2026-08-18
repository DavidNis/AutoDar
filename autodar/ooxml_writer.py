from __future__ import annotations

import logging
import os
import re
import tempfile
from copy import deepcopy
from io import BytesIO
from datetime import date
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .errors import ReportError
from .models import ReportData, TemplateConfig

LOGGER = logging.getLogger(__name__)
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CELL_RE = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")
ET.register_namespace("", MAIN_NS)
ET.register_namespace("r", REL_NS)


def _qname(local: str) -> str:
    return f"{{{MAIN_NS}}}{local}"


def _register_source_namespaces(xml: bytes) -> dict[str, str]:
    """Keep prefixes referenced by mc:Ignorable valid after serialization."""
    namespaces: dict[str, str] = {}
    for _event, (prefix, uri) in ET.iterparse(BytesIO(xml), events=("start-ns",)):
        namespaces[prefix] = uri
        if prefix != "xml":
            ET.register_namespace(prefix, uri)
    return namespaces


def _serialize_xml(root: ET.Element, namespaces: dict[str, str], root_name: str) -> bytes:
    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    missing = [
        f' xmlns:{prefix}="{uri}"'.encode("utf-8")
        for prefix, uri in namespaces.items()
        if prefix and f"xmlns:{prefix}=".encode("utf-8") not in xml
    ]
    if missing:
        marker = f"<{root_name}".encode("utf-8")
        xml = xml.replace(marker, marker + b"".join(missing), 1)
    return xml


def _worksheet_path(archive: ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    sheet = next((node for node in workbook.findall(f".//{_qname('sheet')}") if node.get("name") == sheet_name), None)
    if sheet is None:
        raise ReportError(f"Worksheet '{sheet_name}' was not found in the template.")
    relationship_id = sheet.get(f"{{{REL_NS}}}id")
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationship = next(
        (node for node in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship") if node.get("Id") == relationship_id),
        None,
    )
    if relationship is None or not relationship.get("Target"):
        raise ReportError(f"Worksheet relationship for '{sheet_name}' is invalid.")
    target = PurePosixPath(relationship.get("Target"))
    return str(target if target.parts[:1] == ("xl",) else PurePosixPath("xl") / target)


def _cell_sort_key(reference: str) -> tuple[int, int]:
    match = CELL_RE.fullmatch(reference)
    if not match:
        raise ReportError(f"Invalid configured Excel cell: {reference}")
    column = 0
    for character in match.group(1):
        column = column * 26 + ord(character) - 64
    return int(match.group(2)), column


def _get_or_create_cell(root: ET.Element, reference: str) -> ET.Element:
    row_number, column_number = _cell_sort_key(reference)
    sheet_data = root.find(_qname("sheetData"))
    if sheet_data is None:
        raise ReportError("The configured worksheet has no sheet data.")
    row = next((node for node in sheet_data.findall(_qname("row")) if int(node.get("r", "0")) == row_number), None)
    if row is None:
        row = ET.Element(_qname("row"), {"r": str(row_number)})
        insert_at = next((index for index, node in enumerate(sheet_data) if int(node.get("r", "0")) > row_number), len(sheet_data))
        sheet_data.insert(insert_at, row)
    for cell in row.findall(_qname("c")):
        if cell.get("r") == reference:
            return cell
    cell = ET.Element(_qname("c"), {"r": reference})
    insert_at = len(row)
    for index, existing in enumerate(row):
        existing_ref = existing.get("r")
        if existing.tag == _qname("c") and existing_ref and _cell_sort_key(existing_ref)[1] > column_number:
            insert_at = index
            break
    row.insert(insert_at, cell)
    return cell


def _clear_value(cell: ET.Element) -> None:
    for child in list(cell):
        if child.tag in {_qname("v"), _qname("is"), _qname("f")}:
            cell.remove(child)


def _set_text(root: ET.Element, reference: str, value: str) -> None:
    cell = _get_or_create_cell(root, reference)
    _clear_value(cell)
    cell.set("t", "inlineStr")
    inline = ET.SubElement(cell, _qname("is"))
    ET.SubElement(inline, _qname("t")).text = value


def _set_date(root: ET.Element, reference: str, value: date, style_id: int) -> None:
    cell = _get_or_create_cell(root, reference)
    _clear_value(cell)
    # ISO date cells are true Excel dates without requiring a new workbook style.
    cell.set("t", "d")
    cell.set("s", str(style_id))
    ET.SubElement(cell, _qname("v")).text = value.isoformat()


def _add_date_style(styles_xml: bytes, base_style_id: int) -> tuple[bytes, int]:
    namespaces = _register_source_namespaces(styles_xml)
    root = ET.fromstring(styles_xml)
    num_fmts = root.find(_qname("numFmts"))
    if num_fmts is None:
        num_fmts = ET.Element(_qname("numFmts"), {"count": "0"})
        root.insert(0, num_fmts)
    existing_formats = num_fmts.findall(_qname("numFmt"))
    date_format = next(
        (item for item in existing_formats if item.get("formatCode", "").lower() == "dd/mm/yyyy"),
        None,
    )
    if date_format is None:
        used_ids = [int(item.get("numFmtId", "163")) for item in existing_formats]
        date_format_id = max([163, *used_ids]) + 1
        date_format = ET.SubElement(
            num_fmts,
            _qname("numFmt"),
            {"numFmtId": str(date_format_id), "formatCode": "dd/mm/yyyy"},
        )
        num_fmts.set("count", str(len(existing_formats) + 1))
    else:
        date_format_id = int(date_format.get("numFmtId"))
    cell_xfs = root.find(_qname("cellXfs"))
    if cell_xfs is None or base_style_id >= len(cell_xfs):
        raise ReportError("The template's date cell style is invalid.")
    date_style = deepcopy(cell_xfs[base_style_id])
    date_style.set("numFmtId", str(date_format_id))
    date_style.set("applyNumberFormat", "1")
    cell_xfs.append(date_style)
    cell_xfs.set("count", str(len(cell_xfs)))
    return _serialize_xml(root, namespaces, "styleSheet"), len(cell_xfs) - 1


def _verify_top_left_targets(root: ET.Element, addresses: list[str]) -> None:
    merged = [node.get("ref", "") for node in root.findall(f".//{_qname('mergeCell')}")]
    for address in addresses:
        row, column = _cell_sort_key(address)
        for merged_range in merged:
            start, separator, end = merged_range.partition(":")
            if not separator:
                continue
            start_row, start_column = _cell_sort_key(start)
            end_row, end_column = _cell_sort_key(end)
            inside = start_row <= row <= end_row and start_column <= column <= end_column
            if inside and address != start:
                raise ReportError(f"Configured cell {address} is not the top-left cell of merged range {merged_range}.")


def _copy_archive(source: Path, destination: Path, replacements: dict[str, bytes]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="autodar-", suffix=".xlsx", dir=destination.parent, delete=False) as temporary:
            temporary_name = temporary.name
        with ZipFile(source, "r") as original, ZipFile(temporary_name, "w") as result:
            for info in original.infolist():
                result.writestr(info, replacements.get(info.filename, original.read(info.filename)))
        os.replace(temporary_name, destination)
        temporary_name = None
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def write_report(template: TemplateConfig, data: ReportData, destination: Path) -> None:
    if not template.file.is_file():
        raise ReportError(f"Excel template was not found: {template.file}")
    if destination.resolve() == template.file.resolve():
        raise ReportError("Choose a different file name. The original template cannot be overwritten.")
    cells = template.cells
    addresses = [
        cells.shift_date, cells.team_leader.name, cells.team_leader.pin,
        *(address for person in cells.security_officers for address in (person.name, person.pin)),
        cells.control_room.name, cells.control_room.pin, *cells.patrols, cells.dar_officer, cells.dar_date,
    ]
    try:
        with ZipFile(template.file, "r") as archive:
            sheet_path = _worksheet_path(archive, template.sheet)
            source_xml = archive.read(sheet_path)
            namespaces = _register_source_namespaces(source_xml)
            root = ET.fromstring(source_xml)
            styles_xml = archive.read("xl/styles.xml")
        _verify_top_left_targets(root, addresses)
        base_date_style = int(_get_or_create_cell(root, cells.shift_date).get("s", "0"))
        styles_xml, date_style_id = _add_date_style(styles_xml, base_date_style)
        _set_date(root, cells.shift_date, data.shift_date, date_style_id)
        _set_text(root, cells.team_leader.name, data.team_leader.name)
        _set_text(root, cells.team_leader.pin, data.team_leader.pin)
        for mapping, employee in zip(cells.security_officers, data.security_officers, strict=True):
            _set_text(root, mapping.name, employee.name)
            _set_text(root, mapping.pin, employee.pin)
        _set_text(root, cells.control_room.name, data.control_room.name)
        _set_text(root, cells.control_room.pin, data.control_room.pin)
        for address in cells.patrols:
            _set_text(root, address, f"{template.patrol_prefix} {data.patrol_officer.name}")
        _set_text(root, cells.dar_officer, data.dar_officer.name)
        _set_date(root, cells.dar_date, data.shift_date, date_style_id)
        _copy_archive(
            template.file,
            destination,
            {
                sheet_path: _serialize_xml(root, namespaces, "worksheet"),
                "xl/styles.xml": styles_xml,
            },
        )
    except ReportError:
        raise
    except PermissionError as exc:
        LOGGER.exception("Permission error saving report to %s", destination)
        raise ReportError("The report could not be saved. Close it in Excel or choose another location.") from exc
    except (OSError, KeyError, ET.ParseError) as exc:
        LOGGER.exception("Workbook processing error")
        raise ReportError("The Excel template could not be read or the report could not be saved.") from exc
    except Exception as exc:
        LOGGER.exception("Unexpected Excel error")
        raise ReportError("An unexpected Excel error occurred while generating the report.") from exc
