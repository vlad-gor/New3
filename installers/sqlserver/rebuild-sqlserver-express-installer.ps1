$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$partsDir = Join-Path $scriptDir "parts"
$outputFile = Join-Path $scriptDir "SQLEXPR_x64_ENU.exe"
$partFiles = @(
    "SQLEXPR_x64_ENU.exe.part00",
    "SQLEXPR_x64_ENU.exe.part01",
    "SQLEXPR_x64_ENU.exe.part02"
) | ForEach-Object { Join-Path $partsDir $_ }

$expectedHash = "2e61c8bbde6021f9026c54ad9db4bbb1227e68761d4c00a6a50a2c70fe7afe05"

foreach ($part in $partFiles) {
    if (-not (Test-Path $part)) {
        throw "Missing SQL Server installer part: $part"
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
