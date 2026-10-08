# Windows-side checks for build.ps1. Dot-source this file.

# The WSL disk (ext4.vhdx) grows on the Windows drive that holds it, while df inside
# WSL reports the virtual size (~1 TB). So free space must be checked from Windows.
function Test-HostDiskSpace {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][int]$MinGB
    )
    $drive = $Path.Substring(0, 1)
    $freeGB = [math]::Floor((Get-PSDrive -Name $drive).Free / 1GB)
    if ($freeGB -lt $MinGB) {
        Write-Error "${drive}: has only $freeGB GB free, need $MinGB GB. Fix: free up space or move the distro with 'wsl --manage rocket-build --move <dir>'."
        return $false
    }
    return $true
}

function Get-WslDistroPath {
    param([Parameter(Mandatory)][string]$Name)
    foreach ($key in Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss') {
        $p = Get-ItemProperty -Path $key.PSPath
        if ($p.DistributionName -eq $Name) { return $p.BasePath }
    }
    return $null
}

# Copies a file and verifies its SHA-256; writes "<hash>  <name>" to <name>.sha256.
# Large writes from WSL to /mnt/<drive> can fail with ENOMEM, so the ISO is
# copied from the Windows side instead.
function Copy-VerifiedFile {
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Destination,
        [Parameter(Mandatory)][string]$ExpectedSha256
    )
    $name = Split-Path $Source -Leaf
    $target = Join-Path $Destination $name
    Copy-Item -LiteralPath $Source -Destination $target -Force
    $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $ExpectedSha256.ToLower()) {
        Remove-Item -LiteralPath $target -Force
        throw "checksum mismatch for ${name}: expected $ExpectedSha256, got $actual"
    }
    [IO.File]::WriteAllText("$target.sha256", "$actual  $name`n")
}
