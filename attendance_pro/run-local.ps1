param(
    [string]$Python = '.\.venv-app311\Scripts\python.exe',
    [ValidateRange(1, 65535)][int]$ApiPort = 8000,
    [switch]$Operational
)

$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonCandidate = if ([System.IO.Path]::IsPathRooted($Python)) { $Python } else { Join-Path $project $Python }
$pythonPath = (Resolve-Path -LiteralPath $pythonCandidate).Path
$frontend = Join-Path $project 'frontend'
$env:ATTENDANCE_API_PORT = [string]$ApiPort
if (-not (Test-Path -LiteralPath (Join-Path $frontend 'node_modules'))) {
    throw 'Frontend dependencies are missing. Run npm ci from attendance_pro\frontend first.'
}
$logFolder = Join-Path $project '.local-run'
New-Item -ItemType Directory -Path $logFolder -Force | Out-Null
if ($Operational) {
    $env:ATTENDANCE_DB = Join-Path $project 'attendance_system.db'
    $env:KNOWN_FACES_DIR = Join-Path $project 'known_faces'
    Write-Host 'Using the operational local database and enrolled photos.'
} else {
    $demoFolder = Join-Path $project '.demo-data'
    New-Item -ItemType Directory -Path $demoFolder -Force | Out-Null
    $env:ATTENDANCE_DB = Join-Path $demoFolder 'attendance.db'
    $env:KNOWN_FACES_DIR = Join-Path $demoFolder 'known_faces'
    Write-Host 'Using the isolated local demonstration database.'
}
$api = Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', [string]$ApiPort, '--no-access-log') -WorkingDirectory $project -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logFolder 'api.out.log') -RedirectStandardError (Join-Path $logFolder 'api.err.log')
try {
    Start-Sleep -Seconds 2
    if ($api.HasExited) { throw "FastAPI stopped during startup. See $logFolder\api.err.log" }
    Write-Host 'Open http://127.0.0.1:5173/ after Vite reports ready. Press Ctrl+C to stop.'
    Push-Location $frontend
    try { npm run dev } finally { Pop-Location }
} finally {
    if (-not $api.HasExited) { Stop-Process -Id $api.Id -ErrorAction SilentlyContinue }
}
