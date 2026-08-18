# AutoDAR

AutoDAR is a Windows desktop application that fills the existing HFA18 Morning Shift Excel template. It copies the original OOXML package, changes only configured cells in the selected worksheet, and saves a new workbook. This preserves custom XML and worksheet extensions that normal workbook rewrites can discard.

## Windows setup

Python 3.11 or newer is recommended. From PowerShell in this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

If PowerShell blocks activation, run the venv Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Keep these files beside `main.py`:

- `HFA18 Morning Shift Template Copy.xlsx`
- `names_by_number.json`
- `roles.json`
- `templates.json`

The original Excel template is never an output target. AutoDAR asks where to save each generated report.

## Configure roles

Edit `roles.json` and list eligible employee PINs under `team_leaders` and `control_room`. These lists intentionally start empty because no authoritative eligible employees were supplied. Security officers currently use `"all"`.

```json
{
  "team_leaders": ["203913255"],
  "security_officers": "all",
  "control_room": ["204470291"],
  "settings": {
    "allow_primary_role_overlap": false,
    "patrol_source": "assigned_security_officers",
    "dar_source": "assigned_shift_employees"
  }
}
```

PINs must exist in `names_by_number.json`. Restart the application after editing configuration.

## Add another template

Add a top-level entry to `templates.json` with the new display name, source filename, worksheet, output filename, and cell mappings. The writer uses that mapping without template-specific Excel logic. The current interface expects three Security Officer mappings and three Patrol mappings; supporting a different count requires making those rows dynamic in the GUI.

Before using a new template, confirm every configured merged-cell target is the top-left cell of its merged range.

## Tests

Install development dependencies and run:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

The workbook test writes to pytest's temporary directory and does not modify the original template.

## Build an executable

After installing `pyinstaller`, run:

```powershell
python -m pip install pyinstaller
pyinstaller --noconfirm --windowed --name AutoDAR main.py
```

Place the four runtime data/configuration files listed above beside the built executable. For a packaged deployment, adjust `main.py` to select the executable directory when frozen.
