param(
    [Parameter(Mandatory = $true)][string]$ManualDir,
    [string]$ImagesDir = "",
    [string]$TocPath = ""
)

# Mirrors app.js slugify(): strip markdown inline markup, lowercase,
# drop everything except [-a-z0-9\s], trim, then spaces -> "-".
function Get-Slug([string]$text) {
    $t = $text
    $t = $t -replace '\*\*(.+?)\*\*', '$1'
    $t = $t -replace '`(.+?)`', '$1'
    $t = $t.ToLowerInvariant()
    $t = $t -replace '[^-a-z0-9\s]', ''
    $t = $t.Trim()
    $t = $t -replace '\s+', '-'
    return $t
}

$files = Get-ChildItem -Path $ManualDir -Filter *.md -File
$slugs = @{}
foreach ($f in $files) {
    $slugs[$f.BaseName] = New-Object System.Collections.Generic.HashSet[string]
    foreach ($line in Get-Content -LiteralPath $f.FullName) {
        if ($line -match '^#{1,4}\s+(.+?)\s*$') {
            [void]$slugs[$f.BaseName].Add((Get-Slug $Matches[1]))
        }
    }
}

$problems = New-Object System.Collections.Generic.List[string]
$linkCount = 0
$imageCount = 0

foreach ($f in $files) {
    $lineNo = 0
    $h1 = 0
    $inFence = $false
    foreach ($line in Get-Content -LiteralPath $f.FullName) {
        $lineNo++
        if ($line -match '^\s*```') { $inFence = -not $inFence; continue }
        if ($inFence) { continue }
        if ($line -match '^#\s+\S') { $h1++ }

        foreach ($m in [regex]::Matches($line, '!?\[[^\]]*\]\(([^)]+)\)')) {
            $target = $m.Groups[1].Value.Trim()
            if ($target -match '^(https?:|mailto:|data:|/)') { continue }

            if ($target -match '^images/') {
                $imageCount++
                if ($ImagesDir -and -not (Test-Path -LiteralPath (Join-Path $ImagesDir ($target -replace '^images/', '')))) {
                    $problems.Add("$($f.Name):$lineNo missing image $target")
                }
                continue
            }

            $linkCount++
            if ($target -match '^(?:\./)?([^/\\?#]+\.md)(?:#(.*))?$') {
                $doc = $Matches[1] -replace '\.md$', ''
                $anchor = $Matches[2]
                if ($anchor) { $anchor = [uri]::UnescapeDataString($anchor) }
                if (-not $slugs.ContainsKey($doc)) {
                    $problems.Add("$($f.Name):$lineNo broken doc link $target")
                }
                elseif ($anchor -and -not $slugs[$doc].Contains($anchor)) {
                    $problems.Add("$($f.Name):$lineNo missing anchor '$anchor' in $doc.md")
                }
            }
            elseif ($target -match '^#(.+)$') {
                $anchor = [uri]::UnescapeDataString($Matches[1])
                if (-not $slugs[$f.BaseName].Contains($anchor)) {
                    $problems.Add("$($f.Name):$lineNo missing local anchor '$anchor'")
                }
            }
            else {
                $problems.Add("$($f.Name):$lineNo unrecognised link target $target")
            }
        }
    }
    if ($h1 -ne 1) { $problems.Add("$($f.Name): has $h1 level-1 headings (expected 1)") }
}

if ($TocPath -and (Test-Path -LiteralPath $TocPath)) {
    $toc = Get-Content -LiteralPath $TocPath -Raw | ConvertFrom-Json
    function Walk($items) {
        foreach ($item in $items) {
            if (-not $slugs.ContainsKey($item.doc)) {
                $problems.Add("toc.json: doc '$($item.doc)' has no markdown file")
            }
            elseif ($item.section -and -not $slugs[$item.doc].Contains($item.section)) {
                $problems.Add("toc.json: section '$($item.section)' not found in $($item.doc).md")
            }
            if ($item.children) { Walk $item.children }
        }
    }
    Walk $toc

    $inToc = New-Object System.Collections.Generic.HashSet[string]
    function Collect($items) {
        foreach ($item in $items) {
            [void]$inToc.Add($item.doc)
            if ($item.children) { Collect $item.children }
        }
    }
    Collect $toc
    foreach ($f in $files) {
        if (-not $inToc.Contains($f.BaseName)) { $problems.Add("toc.json: missing entry for $($f.BaseName).md") }
    }
}

Write-Host "Checked $($files.Count) files, $linkCount links, $imageCount images."
if ($problems.Count -eq 0) {
    Write-Host "OK - no problems found." -ForegroundColor Green
}
else {
    Write-Host "$($problems.Count) problem(s):" -ForegroundColor Yellow
    $problems | Sort-Object -Unique | ForEach-Object { Write-Host "  $_" }
}
