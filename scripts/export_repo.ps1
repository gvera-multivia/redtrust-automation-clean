param(
    [Parameter(Mandatory = $true)]
    [string]$DestinationPath,

    [string]$SourcePath,

    [switch]$OverwriteDestination
)

$ErrorActionPreference = "Stop"

function Resolve-FullPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $item = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
    if ($item) {
        return $item.FullName
    }

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    return $fullPath.TrimEnd("\")
}

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $SourcePath) {
    $SourcePath = (Resolve-Path (Join-Path $scriptDirectory "..")).Path
}

$sourceFullPath = Resolve-FullPath -Path $SourcePath
$destinationFullPath = [System.IO.Path]::GetFullPath($DestinationPath).TrimEnd("\")

if (-not (Test-Path -LiteralPath $sourceFullPath -PathType Container)) {
    throw "La carpeta de origen no existe: $sourceFullPath"
}

if ($destinationFullPath.StartsWith($sourceFullPath, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "La carpeta destino no puede estar dentro del repositorio origen."
}

if (Test-Path -LiteralPath $destinationFullPath) {
    $destinationHasFiles = @(Get-ChildItem -LiteralPath $destinationFullPath -Force -ErrorAction SilentlyContinue).Count -gt 0
    if ($destinationHasFiles -and -not $OverwriteDestination) {
        throw "La carpeta destino ya existe y no esta vacia. Usa -OverwriteDestination si quieres reutilizarla."
    }
} else {
    New-Item -ItemType Directory -Path $destinationFullPath | Out-Null
}

$excludeDirectories = @(
    ".git",
    ".venv",
    "venv",
    "env",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".idea",
    ".vscode",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "htmlcov",
    ".next",
    ".nuxt",
    ".cache",
    "tmp",
    "temp",
    "logs",
    "resultados",
    "files"
)

$excludeFiles = @(
    ".env",
    ".env.local",
    ".env.development.local",
    ".env.test.local",
    ".env.production.local",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.log",
    "*.tmp",
    "*.temp",
    "Thumbs.db",
    ".DS_Store"
)

$robocopyArgs = @(
    $sourceFullPath,
    $destinationFullPath,
    "*",
    "/E",
    "/R:1",
    "/W:1",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NP",
    "/XD"
) + $excludeDirectories + @(
    "/XF"
) + $excludeFiles

Write-Host "Exportando repositorio limpio..."
Write-Host "Origen:  $sourceFullPath"
Write-Host "Destino: $destinationFullPath"

& robocopy @robocopyArgs | Out-Host
$robocopyExitCode = $LASTEXITCODE

if ($robocopyExitCode -gt 7) {
    throw "Robocopy ha fallado con codigo de salida $robocopyExitCode"
}

Write-Host ""
Write-Host "Copia completada correctamente."
Write-Host "Siguiente paso sugerido:"
Write-Host "  cd `"$destinationFullPath`""
Write-Host "  git init"
Write-Host "  git add ."
Write-Host "  git commit -m `"Initial commit`""
