# Foundry 바이너리 설치 (evaluation/forge/bin). 버전은 평가에 쓴 것으로 고정.
$ErrorActionPreference = "Stop"
$ver = "v1.8.4"
$dst = Join-Path $PSScriptRoot "bin"
$zip = Join-Path $env:TEMP "foundry_$ver.zip"
New-Item -ItemType Directory -Force $dst | Out-Null
Invoke-WebRequest "https://github.com/foundry-rs/foundry/releases/download/$ver/foundry_${ver}_win32_amd64.zip" -OutFile $zip
Expand-Archive $zip -DestinationPath $dst -Force
Remove-Item $zip
& (Join-Path $dst "forge.exe") --version
