# Install / refresh the three-layer UI skill stack for Cursor.
# Baseline (floor) + Impeccable (spec) + Taste (quality) + local orchestrator.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Installing baseline-ui, design-taste-frontend, and imagegen-frontend-web via skills CLI..."
npx --yes skills add ibelick/ui-skills --skill baseline-ui --agent cursor -y --copy
npx --yes skills add Leonxlnx/taste-skill --skill design-taste-frontend --agent cursor -y --copy
npx --yes skills add Leonxlnx/taste-skill --skill imagegen-frontend-web --agent cursor -y --copy

Write-Host "Installing ui-ux-pro-max via uipro CLI..."
npx --yes uipro-cli init --ai cursor

# uipro templates omit Cursor frontmatter; patch for agent discovery
$uipSkill = Join-Path $Root ".cursor\skills\ui-ux-pro-max\SKILL.md"
if (Test-Path $uipSkill) {
    $content = Get-Content $uipSkill -Raw
    if ($content -notmatch '^---\s*\r?\nname:\s*ui-ux-pro-max') {
        $frontmatter = @"
---
name: ui-ux-pro-max
description: AI-powered design intelligence with 67 UI styles, 161 color palettes, 57 font pairings, 99 UX guidelines, and 25 chart types across 15+ tech stacks. Use when building, designing, reviewing, or improving UI/UX for web or mobile apps.
---

"@
        Set-Content -Path $uipSkill -Value ($frontmatter + $content) -NoNewline
    }
}

Write-Host "Installing impeccable (curl from GitHub)..."
$impDir = Join-Path $Root ".cursor\skills\impeccable"
$refDir = Join-Path $impDir "reference"
New-Item -ItemType Directory -Force -Path $refDir | Out-Null
curl.exe -fsSL "https://raw.githubusercontent.com/pbakaus/impeccable/main/skill/SKILL.src.md" `
    -o (Join-Path $impDir "SKILL.md")

Write-Host "Syncing to .cursor/skills..."
$cursorSkills = Join-Path $Root ".cursor\skills"
New-Item -ItemType Directory -Force -Path $cursorSkills | Out-Null
foreach ($name in @("baseline-ui", "design-taste-frontend", "imagegen-frontend-web", "impeccable")) {
    $src = Join-Path $Root ".agents\skills\$name"
    $dst = Join-Path $cursorSkills $name
    if (Test-Path $src) {
        if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
        Copy-Item -Recurse -Force $src $dst
    }
}

Write-Host "Done. Reload Cursor. Use /ui-update-stack or /ui-ux-pro-max for UI work."
