param(
    [switch]$Clean = $true
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Virtual environment not found at .venv. Create it first."
}

$Python = Resolve-Path ".venv\Scripts\python.exe"
$IconPath = Join-Path $RepoRoot "src\tracer\assets\icons\tracer.ico"

if (-not (Test-Path $IconPath)) {
    Write-Warning "Icon file not found at $IconPath. Build will continue without a custom icon."
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -e .[dev]

if ($Clean) {
    if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
    if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }
}

& $Python -m PyInstaller --noconfirm --clean "Tracer.spec"

Write-Host ""
Write-Host "Build complete."
Write-Host "Executable folder: $RepoRoot\dist\Tracer"
Write-Host "GUI executable: $RepoRoot\dist\Tracer\Tracer.exe"
Write-Host "CLI executable: $RepoRoot\dist\Tracer\tracer-cli.exe"
