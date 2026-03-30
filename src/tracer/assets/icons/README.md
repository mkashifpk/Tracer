# Icon Asset

Place the Windows application icon at:

`src/tracer/assets/icons/tracer.ico`

Notes:
- Use `.ico` format for PyInstaller on Windows.
- Recommended sizes inside the ICO: `16, 24, 32, 48, 64, 128, 256`.
- The build script and runtime icon loader will use this path automatically if the file exists.
