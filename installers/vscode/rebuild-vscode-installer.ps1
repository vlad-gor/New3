$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputFile = Join-Path $scriptDir "VSCodeUserSetup-x64-1.126.0.exe"
$partFiles = @(
    "parts/VSCodeUserSetup-x64-1.126.0.exe.part00",
    "parts/VSCodeUserSetup-x64-1.126.0.exe.part01",
    "parts/VSCodeUserSetup-x64-1.126.0.exe.part02"
) | ForEach-Object { Join-Path $scriptDir $_ }

$expectedHash = "1e883039671841218ef4be1fc308f79d0512ed7bc3213578f4931a2581a7de37"

foreach ($part in $partFiles) {
    if (-not (Test-Path $part)) {
        throw "Missing installer part: $part"
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
