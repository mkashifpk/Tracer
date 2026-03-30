# Windows Packaging

## Build Prerequisites

- Windows 10 or 11
- Python 3.12
- A virtual environment at `.venv`
- Project dependencies installed with `pip install -e .[dev]`
- Optional application icon at `src/tracer/assets/icons/tracer.ico`
- Optional Potrace binary at `src/tracer/assets/bin/potrace.exe`

## Build Script

Use:

```powershell
.\scripts\build_windows.ps1
```

This runs the PyInstaller spec file:

```powershell
python -m PyInstaller --noconfirm --clean Tracer.spec
```

## Build Output

PyInstaller creates:

- `dist\Tracer\Tracer.exe`
- `dist\Tracer\tracer-cli.exe`
- bundled runtime files in `dist\Tracer\`

Use:

- `Tracer.exe` for the desktop UI
- `tracer-cli.exe` for command-line batch tracing

## Bundled Resources

The spec bundles:

- Python application code from `src\tracer`
- `src\tracer\assets\**`
- optional `src\tracer\assets\bin\potrace.exe`
- PySide6 runtime dependencies
- OpenCV runtime dependencies
- Pillow, NumPy, and other Python package dependencies discovered by PyInstaller

## Runtime Resource Paths

Use `tracer.utils.resources.resource_path(...)` for packaged resource resolution.

For application icon loading at runtime, the app checks:

- `assets/icons/tracer.ico`
- `tracer/assets/icons/tracer.ico`

## Recommended Release Flow

1. Add a production `.ico` file.
2. Run `.\scripts\build_windows.ps1`.
3. Smoke test `dist\Tracer\Tracer.exe`.
4. Smoke test `dist\Tracer\tracer-cli.exe --help`.
5. Package with an installer later.
