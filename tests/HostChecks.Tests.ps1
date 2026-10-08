# Pester 3 tests for scripts/lib/HostChecks.ps1 (Windows-side checks in build.ps1).
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. "$here\..\scripts\lib\HostChecks.ps1"

Describe 'Test-HostDiskSpace' {
    It 'fails when the drive holding the path has less than the minimum free' {
        Mock Get-PSDrive { [pscustomobject]@{ Name = 'C'; Free = 5GB } } -ParameterFilter { $Name -eq 'C' }
        Test-HostDiskSpace -Path 'C:\Users\x\AppData\Local\wsl\{id}' -MinGB 25 -ErrorAction SilentlyContinue |
            Should Be $false
    }

    It 'reports the drive and both sizes in the error' {
        Mock Get-PSDrive { [pscustomobject]@{ Name = 'C'; Free = 5GB } } -ParameterFilter { $Name -eq 'C' }
        $err = $null
        Test-HostDiskSpace -Path 'C:\wsl' -MinGB 25 -ErrorVariable err -ErrorAction SilentlyContinue | Out-Null
        "$err" | Should Match 'C: has only 5 GB free, need 25 GB'
    }

    It 'passes at exactly the minimum' {
        Mock Get-PSDrive { [pscustomobject]@{ Name = 'E'; Free = 25GB } } -ParameterFilter { $Name -eq 'E' }
        Test-HostDiskSpace -Path 'E:\WSL\rocket-build' -MinGB 25 | Should Be $true
    }
}

Describe 'Get-WslDistroPath' {
    It 'returns the BasePath registered for the distro' {
        Mock Get-ChildItem { @([pscustomobject]@{ PSPath = 'k1' }, [pscustomobject]@{ PSPath = 'k2' }) }
        Mock Get-ItemProperty { [pscustomobject]@{ DistributionName = 'other'; BasePath = 'C:\o' } } -ParameterFilter { $Path -eq 'k1' }
        Mock Get-ItemProperty { [pscustomobject]@{ DistributionName = 'rocket-build'; BasePath = 'E:\WSL\rocket-build' } } -ParameterFilter { $Path -eq 'k2' }
        Get-WslDistroPath -Name 'rocket-build' | Should Be 'E:\WSL\rocket-build'
    }
}
