param(
    [Parameter(Mandatory = $true)]
    [string]$RepoPath,

    [Parameter(Mandatory = $true)]
    [string]$Name,

    [string]$Branch = "",

    [string]$Base = "HEAD",

    [string]$RootPath = "",

    [switch]$Detach
)

$ErrorActionPreference = "Stop"

function Resolve-GitRoot {
    param([string]$Path)
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $gitRoot = git -C $resolved rev-parse --show-toplevel 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($gitRoot)) {
        throw "Impossible de trouver un repo Git depuis: $resolved"
    }
    return $gitRoot.Trim()
}

function Test-BranchExists {
    param(
        [string]$GitRoot,
        [string]$BranchName
    )
    git -C $GitRoot rev-parse --verify --quiet "refs/heads/$BranchName" | Out-Null
    return ($LASTEXITCODE -eq 0)
}

$gitRoot = Resolve-GitRoot -Path $RepoPath
$repoName = Split-Path -Leaf $gitRoot

if ([string]::IsNullOrWhiteSpace($RootPath)) {
    $RootPath = Join-Path (Split-Path -Parent $gitRoot) "_worktrees"
}

$branchName = if ([string]::IsNullOrWhiteSpace($Branch)) { $Name } else { $Branch }
$worktreePath = Join-Path $RootPath (Join-Path $repoName $Name)
$worktreeParent = Split-Path -Parent $worktreePath

New-Item -ItemType Directory -Force -Path $worktreeParent | Out-Null

if (Test-Path -LiteralPath $worktreePath) {
    throw "Le dossier existe deja: $worktreePath"
}

if ($Detach) {
    git -C $gitRoot worktree add -d $worktreePath $Base
} elseif (Test-BranchExists -GitRoot $gitRoot -BranchName $branchName) {
    git -C $gitRoot worktree add $worktreePath $branchName
} else {
    git -C $gitRoot worktree add -b $branchName $worktreePath $Base
}

if ($LASTEXITCODE -ne 0) {
    throw "La creation du worktree a echoue."
}

Write-Host "Worktree cree:"
Write-Host "  repo     : $gitRoot"
Write-Host "  branche  : $branchName"
Write-Host "  chemin   : $worktreePath"
