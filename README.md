# Tracer

Offline Windows-first desktop tool for bulk PNG/JPG to SVG tracing.

Monochrome tracing uses Potrace when `potrace.exe` is available.
Color tracing uses the `vtracer` Python package and is selected from the app's `Trace mode` control or via the `Color Illustration Trace` preset.

Place `potrace.exe` here for local/project use:

- `src\tracer\assets\bin\potrace.exe`

Or install `potrace.exe` on your system `PATH`.

## Development

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
python -m tracer.main
```

## CLI Usage

Run bulk tracing without opening the desktop UI:

```powershell
python -m tracer.main --input "C:\input" --output "C:\output" --preset "Minimal Smooth Vector"
python -m tracer.main --input "C:\input" --output "C:\output" --trace-mode color --preset "Color Illustration Trace"
```

Show available CLI options:

```powershell
python -m tracer.main --help
```
python -m tracer.main