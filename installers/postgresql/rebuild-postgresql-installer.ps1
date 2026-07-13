$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$partsDir = Join-Path $scriptDir "parts"
$outputFile = Join-Path $scriptDir "postgresql-15.18-1-windows-x64.exe"
$partFiles = @(
    "postgresql-15.18-1-windows-x64.exe.part00",
    "postgresql-15.18-1-windows-x64.exe.part01",
    "postgresql-15.18-1-windows-x64.exe.part02",
    "postgresql-15.18-1-windows-x64.exe.part03"
) | ForEach-Object { Join-Path $partsDir $_ }

$expectedHash = "8d1ac971810b819d861ac6bc47ceaa87a23251c9194f66255ec4ac208d15d688"

foreach ($part in $partFiles) {
    if (-not (Test-Path $part)) {
        throw "Missing PostgreSQL installer part: $part"
    }
}

$outputStream = [System.IO.File]::Open($outputFile, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
try {
    foreach ($part in $partFiles) {
        $bytes = [System.IO.File]::ReadAllBytes($part)
        $outputStream.Write($bytes, 0, $bytes.Length)
    }
}
finally {
    $outputStream.Dispose()
}

$actualHash = (Get-FileHash -Path $outputFile -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash) {
    throw "Checksum mismatch after rebuild. Expected $expectedHash, got $actualHash"
}

Write-Host "Rebuilt $outputFile"
Write-Host "SHA-256 verified: $actualHash"
