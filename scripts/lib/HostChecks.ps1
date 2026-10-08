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
