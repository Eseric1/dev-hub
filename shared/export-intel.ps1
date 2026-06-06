# ============================================================
# export-intel.ps1
# Pipelines field intel observations into targeted reports
#
# Usage:
#   .\export-intel.ps1
#   .\export-intel.ps1 -Category sensor
#   .\export-intel.ps1 -Ref KCSCS8
#   .\export-intel.ps1 -Since 30
#   .\export-intel.ps1 -Category chemical -Since 60
# ============================================================

param(
    [string]$Category = "all",
    [string]$Ref      = "",
    [int]   $Since    = 0,
    [string]$Out      = ""
)

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$JSON_PATH  = Join-Path $SCRIPT_DIR "observations.json"

if (-not (Test-Path $JSON_PATH)) {
    Write-Host ""
    Write-Host "  observations.json not found." -ForegroundColor Yellow
    Write-Host "  1. Open field-intel/index.html in your browser" -ForegroundColor Gray
    Write-Host "  2. Click the export button in the header" -ForegroundColor Gray
    Write-Host "  3. Save observations.json into shared/" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

$raw = Get-Content $JSON_PATH -Raw

if ([string]::IsNullOrWhiteSpace($raw) -or $raw.Trim() -eq "null") {
    Write-Host ""
    Write-Host "  observations.json is empty." -ForegroundColor Yellow
    Write-Host "  Export your data from field-intel first." -ForegroundColor Gray
    Write-Host ""
    exit 1
}

$entries = $raw | ConvertFrom-Json

Write-Host ""
Write-Host "  field://intel -- export pipeline" -ForegroundColor Cyan
Write-Host "  ----------------------------------" -ForegroundColor DarkGray
Write-Host "  Loaded $($entries.Count) entries" -ForegroundColor Gray

# Filter: category
$filtered = if ($Category -ne "all") {
    $entries | Where-Object { $_.category -eq $Category }
} else {
    $entries
}

# Filter: reference ID
if ($Ref -ne "") {
    $filtered = $filtered | Where-Object {
        $_.references -contains $Ref.ToUpper()
    }
}

# Filter: date range
if ($Since -gt 0) {
    $cutoff   = (Get-Date).AddDays(-$Since)
    $filtered = $filtered | Where-Object {
        try { [datetime]$_.date -ge $cutoff } catch { $true }
    }
}

$filteredCount = @($filtered).Count
Write-Host "  Filtered to $filteredCount entries" -ForegroundColor Gray

if ($filteredCount -eq 0) {
    Write-Host ""
    Write-Host "  No entries match your filters." -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

# Shape output
$report = $filtered | Select-Object `
    @{N="Date";        E={ $_.date }},
    @{N="Time";        E={ $_.time }},
    @{N="Tool";        E={ $_.tool }},
    @{N="Category";    E={ $_.category }},
    @{N="Observation"; E={ $_.observation }},
    @{N="Question";    E={ $_.question }},
    @{N="References";  E={ ($_.references -join ", ") }},
    @{N="Tags";        E={ ($_.tags -join ", ") }}

# Summary
Write-Host ""
Write-Host "  SUMMARY" -ForegroundColor Cyan
Write-Host "  ----------------------------------" -ForegroundColor DarkGray

$report | Group-Object Category | Sort-Object Count -Descending | ForEach-Object {
    $bar = "=" * $_.Count
    Write-Host ("  {0,-18} {1,3}  {2}" -f $_.Name, $_.Count, $bar) -ForegroundColor Gray
}

Write-Host ""

# Top reference IDs
$allRefs = @($filtered | ForEach-Object { $_.references } | Where-Object { $_ -ne $null -and $_ -ne "" })

if ($allRefs.Count -gt 0) {
    Write-Host "  TOP REFERENCE IDs" -ForegroundColor Cyan
    Write-Host "  ----------------------------------" -ForegroundColor DarkGray
    $allRefs | Group-Object | Sort-Object Count -Descending | Select-Object -First 10 | ForEach-Object {
        Write-Host ("  {0,-20} {1,3}x" -f $_.Name, $_.Count) -ForegroundColor Green
    }
    Write-Host ""
}

# Open questions
$questions = @($filtered | Where-Object { $_.question -ne $null -and $_.question -ne "" })

if ($questions.Count -gt 0) {
    Write-Host "  OPEN QUESTIONS ($($questions.Count))" -ForegroundColor Cyan
    Write-Host "  ----------------------------------" -ForegroundColor DarkGray
    $questions | Select-Object -First 5 | ForEach-Object {
        Write-Host "  [$($_.tool)]" -ForegroundColor DarkGray -NoNewline
        Write-Host " $($_.question)" -ForegroundColor White
    }
    Write-Host ""
}

# Export CSV
$timestamp  = Get-Date -Format "yyyy-MM-dd_HHmm"
$cat        = if ($Category -ne "all") { "-$Category" } else { "" }
$ref        = if ($Ref -ne "")         { "-$Ref" }      else { "" }
$outputFile = if ($Out -ne "") { $Out } else {
    Join-Path $SCRIPT_DIR "intel-report${cat}${ref}_${timestamp}.csv"
}

$report | Export-Csv -Path $outputFile -NoTypeInformation

Write-Host "  Exported to:" -ForegroundColor Gray
Write-Host "  $outputFile" -ForegroundColor Cyan
Write-Host ""