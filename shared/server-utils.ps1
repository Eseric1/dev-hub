# ============================================================
# server-utils.ps1
# Shared PowerShell utility layer for Personal Dev Hub
# Called by Python launchers — not intended for direct use
#
# Functions:
#   Get-FreePort        — find an available TCP port
#   New-SecretToken     — generate a cryptographic token
#   Test-PortReady      — poll until a port accepts connections
#   Get-ProjectRegistry — read projects.json manifest
#   Set-ProjectStatus   — update a project's running status
#   Get-FileMetadata    — rich metadata for a file or folder
# ============================================================

# ── Port Utilities ────────────────────────────────────────────────────────────

function Get-FreePort {
    <#
    .SYNOPSIS
        Returns a random available TCP port on 127.0.0.1
    .EXAMPLE
        $port = Get-FreePort
    #>
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = $listener.LocalEndpoint.Port
    $listener.Stop()
    return $port
}

function Test-PortReady {
    <#
    .SYNOPSIS
        Polls a TCP port until it accepts connections or times out
    .PARAMETER Port
        Port number to test
    .PARAMETER TimeoutSeconds
        How long to wait before giving up (default: 15)
    .EXAMPLE
        $ready = Test-PortReady -Port 8421 -TimeoutSeconds 10
    #>
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 15
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $tcp = [System.Net.Sockets.TcpClient]::new()
            $tcp.Connect("127.0.0.1", $Port)
            $tcp.Close()
            return $true
        } catch {
            Start-Sleep -Milliseconds 100
        }
    }
    return $false
}

# ── Token Generation ──────────────────────────────────────────────────────────

function New-SecretToken {
    <#
    .SYNOPSIS
        Generates a cryptographically secure URL-safe token
    .PARAMETER ByteLength
        Number of random bytes (default: 32 → 43 char token)
    .EXAMPLE
        $token = New-SecretToken
    #>
    param([int]$ByteLength = 32)
    $bytes = [byte[]]::new($ByteLength)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes).Replace('+','-').Replace('/','_').TrimEnd('=')
}

# ── Project Registry ──────────────────────────────────────────────────────────

$REGISTRY_PATH = Join-Path $PSScriptRoot "..\hub\projects.json"

function Get-ProjectRegistry {
    <#
    .SYNOPSIS
        Reads and returns the project registry as a PowerShell object
    .EXAMPLE
        $projects = Get-ProjectRegistry
        $projects | Where-Object { $_.status -eq "running" }
    #>
    if (-not (Test-Path $REGISTRY_PATH)) {
        return @()
    }
    $json = Get-Content $REGISTRY_PATH -Raw | ConvertFrom-Json
    return $json.projects
}

function Set-ProjectStatus {
    <#
    .SYNOPSIS
        Updates a project's port and status in the registry
    .PARAMETER Name
        Project name (must match registry entry)
    .PARAMETER Port
        Current running port
    .PARAMETER Status
        "running" or "stopped"
    .EXAMPLE
        Set-ProjectStatus -Name "file-explorer" -Port 8421 -Status "running"
    #>
    param(
        [string]$Name,
        [int]$Port,
        [ValidateSet("running","stopped")]
        [string]$Status
    )
    if (-not (Test-Path $REGISTRY_PATH)) { return }

    $registry = Get-Content $REGISTRY_PATH -Raw | ConvertFrom-Json
    $project  = $registry.projects | Where-Object { $_.name -eq $Name }

    if ($project) {
        $project.port        = $Port
        $project.status      = $Status
        $project.lastUpdated = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    }

    $registry | ConvertTo-Json -Depth 5 | Set-Content $REGISTRY_PATH
}

# ── File Metadata (PowerShell's strength) ─────────────────────────────────────

function Get-FileMetadata {
    <#
    .SYNOPSIS
        Returns rich metadata for a file or folder as a structured object
    .PARAMETER Path
        Full path to the file or folder
    .EXAMPLE
        Get-FileMetadata -Path "C:\Users\Eric\Documents"
        Get-FileMetadata -Path "C:\project\notes.txt" | ConvertTo-Json
    #>
    param([string]$Path)

    $item = Get-Item $Path -ErrorAction SilentlyContinue
    if (-not $item) { return $null }

    if ($item.PSIsContainer) {
        # Folder — collect aggregate stats
        $children = Get-ChildItem $Path -Recurse -ErrorAction SilentlyContinue
        $files    = $children | Where-Object { -not $_.PSIsContainer }
        $total    = ($files | Measure-Object -Property Length -Sum).Sum

        return [PSCustomObject]@{
            Name          = $item.Name
            FullPath      = $item.FullName
            IsDirectory   = $true
            FileCount     = ($files | Measure-Object).Count
            TotalSizeBytes= $total
            TotalSize     = "{0:N2} MB" -f ($total / 1MB)
            Created       = $item.CreationTime.ToString("yyyy-MM-dd HH:mm:ss")
            Modified      = $item.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
            Extension     = $null
        }
    } else {
        # File — detailed properties
        return [PSCustomObject]@{
            Name          = $item.Name
            FullPath      = $item.FullName
            IsDirectory   = $false
            FileCount     = 1
            TotalSizeBytes= $item.Length
            TotalSize     = "{0:N2} KB" -f ($item.Length / 1KB)
            Created       = $item.CreationTime.ToString("yyyy-MM-dd HH:mm:ss")
            Modified      = $item.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
            Extension     = $item.Extension.TrimStart(".")
        }
    }
}

# ── Export all functions ───────────────────────────────────────────────────────
Export-ModuleMember -Function * -ErrorAction SilentlyContinue