param(
    [switch]$Global,
    [switch]$Dev,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repo = if ($env:REASFLOW_DEV_REPO) { $env:REASFLOW_DEV_REPO } else { "sillyDaibo/reasflow-dev" }
$ref = if ($env:REASFLOW_DEV_REF) { $env:REASFLOW_DEV_REF } else { "main" }
$sourceOverride = $env:REASFLOW_DEV_SOURCE_DIR

function Get-UserHomeDir {
    if ($env:USERPROFILE) { return $env:USERPROFILE }

    $homeFromDotNet = [Environment]::GetFolderPath("UserProfile")
    if ($homeFromDotNet) { return $homeFromDotNet }

    if ($HOME) { return $HOME }

    throw "cannot determine user home directory"
}

if ($Global) {
    $homeDir = Get-UserHomeDir
    $targetRoot = $homeDir
    $defaultStateDir = Join-Path $homeDir ".reasflow-dev"
    $stateDir = if ($env:REASFLOW_DEV_STATE_DIR) { $env:REASFLOW_DEV_STATE_DIR } else { $defaultStateDir }
} else {
    $targetRoot = (Get-Location).Path
    $stateDir = if ($env:REASFLOW_DEV_STATE_DIR) { $env:REASFLOW_DEV_STATE_DIR } else { Join-Path $targetRoot ".reasflow-dev" }
}

$agentsDir = Join-Path $targetRoot ".codex/agents"
$skillsDir = Join-Path $targetRoot ".agents/skills"
$manifest = Join-Path $stateDir "manifest.txt"
$tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("reasflow-dev-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null

try {
    New-Item -ItemType Directory -Force -Path $agentsDir, $skillsDir, $stateDir | Out-Null

    if (Test-Path $manifest) {
        foreach ($line in Get-Content $manifest) {
            if ($line.StartsWith("FILE ")) {
                $path = $line.Substring(5)
                if (Test-Path $path) {
                    Remove-Item -Recurse -Force $path
                }
            }
        }
    }

    if ($sourceOverride) {
        $sourceDir = (Resolve-Path $sourceOverride).Path
    } elseif ($Dev) {
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            throw "git is required for --Dev"
        }
        $sourceDir = Join-Path $stateDir "source"
        if (-not (Test-Path (Join-Path $sourceDir ".git"))) {
            git clone "https://github.com/$repo.git" $sourceDir | Out-Null
        }
        git -C $sourceDir fetch --tags origin | Out-Null
        git -C $sourceDir checkout $ref | Out-Null
        try {
            git -C $sourceDir pull --ff-only origin $ref | Out-Null
        } catch {
        }
    } else {
        $zipPath = Join-Path $tmpDir "reasflow-dev.zip"
        Invoke-WebRequest -Uri "https://codeload.github.com/$repo/zip/$ref" -OutFile $zipPath -UseBasicParsing
        Expand-Archive -Path $zipPath -DestinationPath $tmpDir -Force
        $sourceDir = (Get-ChildItem -Path $tmpDir -Directory | Select-Object -First 1).FullName
    }

    if (-not (Test-Path (Join-Path $sourceDir "skills"))) { throw "invalid source: missing skills directory" }
    if (-not (Test-Path (Join-Path $sourceDir "agents"))) { throw "invalid source: missing agents directory" }

    $manifestLines = @(
        "MODE " + $(if ($Dev) { "dev" } else { "release" }),
        "SCOPE " + $(if ($Global) { "global" } else { "local" }),
        "SOURCE $sourceDir"
    )

    foreach ($skill in Get-ChildItem -Path (Join-Path $sourceDir "skills") -Directory) {
        $dest = Join-Path $skillsDir $skill.Name
        if ((Test-Path $dest) -and -not $Force) { throw "target already exists: $dest" }
        if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
        if ($Dev) {
            New-Item -ItemType SymbolicLink -Path $dest -Target $skill.FullName | Out-Null
        } else {
            Copy-Item -Recurse -Force $skill.FullName $dest
        }
        $manifestLines += "FILE $dest"
    }

    foreach ($agent in Get-ChildItem -Path (Join-Path $sourceDir "agents") -Filter *.toml -File) {
        $dest = Join-Path $agentsDir $agent.Name
        if ((Test-Path $dest) -and -not $Force) { throw "target already exists: $dest" }
        if (Test-Path $dest) { Remove-Item -Force $dest }
        if ($Dev) {
            New-Item -ItemType SymbolicLink -Path $dest -Target $agent.FullName | Out-Null
        } else {
            Copy-Item -Force $agent.FullName $dest
        }
        $manifestLines += "FILE $dest"
    }

    Set-Content -Path $manifest -Value $manifestLines

    $skillCount = (Get-ChildItem -Path $skillsDir -Directory).Count
    $agentCount = (Get-ChildItem -Path $agentsDir -Filter *.toml -File).Count
    Write-Host "Installed reasflow-dev"
    Write-Host "  scope: $(if ($Global) { 'global' } else { 'local' })"
    Write-Host "  mode: $(if ($Dev) { 'dev' } else { 'release' })"
    Write-Host "  skills: $skillCount -> $skillsDir"
    Write-Host "  agents: $agentCount -> $agentsDir"
    Write-Host "  manifest: $manifest"
}
finally {
    Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
}
