# push_to_github.ps1 - one-time setup to push this project to a new GitHub repo.
# Run this from the sma-trader folder in PowerShell.

$ErrorActionPreference = "Stop"
$projectDir = $PSScriptRoot
Set-Location $projectDir

Write-Host "Checking for git..." -ForegroundColor Cyan
$gitExists = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitExists) {
    Write-Host "git is not installed. Install it from https://git-scm.com/download/win and re-run this script." -ForegroundColor Red
    exit 1
}
Write-Host "OK: git found." -ForegroundColor Green

$repoName = Read-Host "Repo name to create (default: sma-trader)"
if ([string]::IsNullOrWhiteSpace($repoName)) { $repoName = "sma-trader" }

$visibilityInput = Read-Host "Private or public repo? (default: private)"
$visFlag = "--private"
if ($visibilityInput -match "^(?i)public$") { $visFlag = "--public" }

# Init the local git repo if it isn't one already.
if (-not (Test-Path ".git")) {
    Write-Host "Initializing git repo..." -ForegroundColor Cyan
    git init | Out-Null
    git branch -M main
} else {
    Write-Host "Already a git repo, continuing." -ForegroundColor Yellow
}

Write-Host "Staging files (.env, cache/, logs are excluded via .gitignore; config.py is included)..." -ForegroundColor Cyan
git add .
$hasChanges = git status --porcelain
if ($hasChanges) {
    git commit -m "SMA crossover + AI/news trading strategy with Streamlit dashboard" | Out-Null
    Write-Host "OK: committed." -ForegroundColor Green
} else {
    Write-Host "Nothing new to commit." -ForegroundColor Yellow
}

$ghExists = Get-Command gh -ErrorAction SilentlyContinue

if ($ghExists) {
    Write-Host ""
    Write-Host "GitHub CLI (gh) found - using it to create and push in one step." -ForegroundColor Cyan
    $ghAuthCheck = gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "You need to log in to GitHub CLI first. Running: gh auth login" -ForegroundColor Yellow
        gh auth login
    }
    $existingRemote = git remote 2>$null
    if ($existingRemote -notcontains "origin") {
        gh repo create $repoName $visFlag --source=. --remote=origin --push
    } else {
        Write-Host "An 'origin' remote already exists - pushing to it directly." -ForegroundColor Yellow
        git push -u origin main
    }
} else {
    Write-Host ""
    Write-Host "GitHub CLI (gh) not found. Manual steps:" -ForegroundColor Yellow
    Write-Host "1. Go to https://github.com/new and create a repo named '$repoName' (do NOT initialize it with a README)."
    Write-Host "2. Paste the repo URL it gives you below (the one ending in .git)."
    $remoteUrl = Read-Host "Repo URL"
    if ([string]::IsNullOrWhiteSpace($remoteUrl)) {
        Write-Host "No URL given - stopping. Re-run this script once you have created the repo." -ForegroundColor Red
        exit 1
    }
    $existingRemote = git remote 2>$null
    if ($existingRemote -contains "origin") {
        git remote set-url origin $remoteUrl
    } else {
        git remote add origin $remoteUrl
    }
    git push -u origin main
}

Write-Host ""
Write-Host "Done. Your code is on GitHub." -ForegroundColor Green
Write-Host "Note: config.py (including your News API key) was committed as-is, per your choice." -ForegroundColor Cyan
