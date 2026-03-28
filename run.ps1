$ErrorActionPreference = "Stop"

$SCRIPT_DIR = $PSScriptRoot

# Check for original maps directory argument
if ($args.Count -eq 0) {
    Write-Host "Usage: .\run.ps1 <directory_with_original_maps>"
    Write-Host ""
    Write-Host "Example:"
    Write-Host "  .\run.ps1 backup\"
    Write-Host "  .\run.ps1 'C:\Users\me\igpsport-maps\original'"
    exit 1
}

$MAPS_DIR = $args[0]

if (-not (Test-Path $MAPS_DIR -PathType Container)) {
    Write-Error "Error: '$MAPS_DIR' is not a directory."
    exit 1
}

# Step 1: Generate maps.csv
Write-Host ""
Write-Host "=========================================="
Write-Host "Step 1: Generating maps.csv"
Write-Host "=========================================="
Write-Host ""

python (Join-Path $SCRIPT_DIR "generate_maps_csv.py") $MAPS_DIR -o (Join-Path $SCRIPT_DIR "maps.csv")

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to generate maps.csv"
    exit 1
}

# Step 2: Generate maps
Write-Host ""
Write-Host "=========================================="
Write-Host "Step 2: Generating maps"
Write-Host "=========================================="
Write-Host ""

& (Join-Path $SCRIPT_DIR "script.ps1")
