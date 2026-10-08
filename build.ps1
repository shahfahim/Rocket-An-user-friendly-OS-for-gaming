<#
.SYNOPSIS
    Builds the Rocket OS ISO from Windows using an Arch Linux WSL2 distro.
.PARAMETER SetupOnly
    Only create/prepare the rocket-build distro, don't build.
.PARAMETER Clean
    Delete the previous work directory before building.
#>
param(
    [switch]$SetupOnly,
    [switch]$Clean
)
$ErrorActionPreference = 'Stop'
$Distro = 'rocket-build'
$MinHostFreeGB = 25
. "$PSScriptRoot\scripts\lib\HostChecks.ps1"

function Invoke-Wsl([string[]]$WslArgs) {
    # PowerShell 5.1 turns native stderr into terminating errors under 'Stop';
    # judge success by exit code only.
    $ErrorActionPreference = 'Continue'
    & wsl.exe -d $Distro -u root @WslArgs 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "WSL command failed (exit $LASTEXITCODE): $($WslArgs -join ' ')" }
}

# wsl.exe -l prints UTF-16; strip NULs before matching.
$installed = (& wsl.exe -l -q) -replace "`0", '' | Where-Object { $_.Trim() -eq $Distro }
if (-not $installed) {
    Write-Host "Creating WSL distro '$Distro' (Arch Linux)..."
    & wsl.exe --install archlinux --name $Distro --no-launch
    if ($LASTEXITCODE -ne 0) { throw "Failed to install the archlinux WSL distro." }
}

$repo = (& wsl.exe -d $Distro -u root wslpath -a ($PSScriptRoot -replace '\\', '/')).Trim()
Invoke-Wsl @('bash', "$repo/scripts/setup-build-host.sh")
if ($SetupOnly) { Write-Host 'Setup complete.'; exit 0 }

$distroPath = Get-WslDistroPath -Name $Distro
if (-not (Test-HostDiskSpace -Path $distroPath -MinGB $MinHostFreeGB)) { exit 1 }

$buildArgs = @('bash', "$repo/build.sh")
if ($Clean) { $buildArgs += '--clean' }
Invoke-Wsl $buildArgs
