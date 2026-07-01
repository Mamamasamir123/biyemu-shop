# Tengeneza folda za kupakia GitHub (kipengele 90 faili kwa mara moja)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$out = Join-Path $root "github-pakia"
$skip = @('__pycache__', 'tools', 'mobile-app', 'biyemu-kivy', '.git', 'github-pakia')

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Path $out | Out-Null

$all = Get-ChildItem -Path $root -Recurse -File | Where-Object {
    $rel = $_.FullName.Substring($root.Length + 1)
    -not ($skip | Where-Object { $rel -like "$_*" -or $rel -like "*\$_\*" })
}

function Priority($rel) {
    if ($rel -match '^(app|seed_data|main|wsgi|requirements|Procfile|render|runtime|\.gitignore)') { return 0 }
    if ($rel -match '^(web|models|services|storage|ui|data)\\') { return 1 }
    if ($rel -match '^static\\') { return 2 }
    if ($rel -match '^templates\\') { return 3 }
    return 4
}

$files = $all | Sort-Object { Priority($_.FullName.Substring($root.Length + 1)) }, FullName

$batch = 1
$count = 0
$batchDir = Join-Path $out "batch-$batch"
New-Item -ItemType Directory -Path $batchDir | Out-Null

foreach ($f in $files) {
    if ($count -ge 90) {
        $batch++
        $count = 0
        $batchDir = Join-Path $out "batch-$batch"
        New-Item -ItemType Directory -Path $batchDir | Out-Null
    }
    $rel = $f.FullName.Substring($root.Length + 1)
    $dest = Join-Path $batchDir $rel
    $parent = Split-Path $dest -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Copy-Item $f.FullName $dest
    $count++
}

Write-Host ""
Write-Host "  Tayari! Folda: $out"
Write-Host "  Jumla faili: $($files.Count)"
Write-Host "  Batch: $batch"
Write-Host "  batch-1 ina code muhimu (web, models, services, n.k.)"
Write-Host ""
Write-Host "  Fuata REKEBISHA_RENDER_FAIL.txt"