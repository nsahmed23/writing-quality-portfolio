#Requires -Version 5.1
<#
.SYNOPSIS
    Evidence collector v2 for laptop qualification (Playbook v2, Phase 1).
.DESCRIPTION
    Produces either a privacy-safe shareable bundle (the default) or an explicitly
    authorized restricted-internal bundle. Every collection failure and native exit
    status is retained. Files are SHA-256 hashed in an evidence manifest.
.PARAMETER BundleMode
    Safe (default) pseudonymizes identifiers with a fresh per-bundle salt and excludes
    WLAN state, raw battery XML, and sleepstudy. Restricted permits direct identifiers
    and those sensitive artifacts, and requires AuthorizationReference.
.PARAMETER IncludeIdentifiers
    Compatibility alias for -BundleMode Restricted. It is rejected unless a nonblank
    AuthorizationReference is also supplied.
.PARAMETER AuthorizationReference
    Required approval/ticket reference for Restricted mode. Recorded in the manifest.
.PARAMETER AgentClassificationPath
    External versioned classification envelope. No agent vendor is built into this
    collector; unmatched observations remain visible as unclassified.
.PARAMETER ApprovedAgentClassificationSha256
    Required preapproved SHA-256 before any nonempty classification rules can affect
    agent classes. Empty vendor-neutral templates do not require approval.
.PARAMETER ApprovedPlatformPublisher
    Optional approved platform publisher. When omitted, the collector derives this
    value from the operating-system manufacturer. Platform origin still requires a
    trusted signature; unsigned publisher text is never promoted.
.PARAMETER ApprovedCmslModulePath
    Exact absolute .psd1 entry path for the approved CMSL module. CMSL is never imported
    from discovery or PSModulePath selection alone.
.PARAMETER ApprovedCmslTreeSha256
    Preapproved SHA-256 over the complete CMSL module directory tree.
.PARAMETER LoadFunctionsOnly
    Dot-source functions without collecting. Used by the test file.
#>
[CmdletBinding()]
param(
    [string]$OutputRoot = "$env:USERPROFILE\Desktop",
    [ValidateSet('Safe', 'Restricted')][string]$BundleMode = 'Safe',
    [switch]$IncludeIdentifiers,
    [string]$AuthorizationReference,
    [string]$AgentClassificationPath = ([IO.Path]::Combine($PSScriptRoot, 'agent-classification.json')),
    [string]$ApprovedAgentClassificationSha256,
    [string]$ApprovedPlatformPublisher,
    [string]$ApprovedCmslModulePath,
    [string]$ApprovedCmslTreeSha256,
    [switch]$LoadFunctionsOnly,
    [switch]$InternalCleanProcess,
    [string]$InternalCleanNonce
)

$script:CollectorVersion = '2.0.1'
$script:CollectorScriptPath = $MyInvocation.MyCommand.Path
$script:BundleMode = 'Safe'
$script:IncludeIds = $false
$script:PlatformPublisher = $null
$script:PlatformPublisherAliases = @()
$script:report = [ordered]@{}
$script:NativeStatuses = @()
$script:CollectionErrors = @()
$script:PseudonymSalt = [byte[]]::new(32)
$collectorRng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $collectorRng.GetBytes($script:PseudonymSalt) } finally { $collectorRng.Dispose() }

# ----------------------------- helper functions ------------------------------

function Resolve-BundleMode {
    param(
        [ValidateSet('Safe', 'Restricted')][string]$RequestedMode = 'Safe',
        [bool]$IdentifiersSwitch,
        [string]$Authorization
    )
    $resolved = if ($IdentifiersSwitch) { 'Restricted' } else { $RequestedMode }
    if ($resolved -eq 'Restricted' -and [string]::IsNullOrWhiteSpace($Authorization)) {
        throw 'Restricted bundle mode requires a nonblank -AuthorizationReference.'
    }
    [pscustomobject]@{
        Mode = $resolved
        IncludesIdentifiers = ($resolved -eq 'Restricted')
        AuthorizationReference = if ($resolved -eq 'Restricted') { $Authorization.Trim() } else { $null }
    }
}

function Get-BundleHandling {
    param([ValidateSet('Safe','Restricted')][string]$Mode)
    if ($Mode -eq 'Restricted') { 'restricted-internal' } else { 'safe-shareable-after-manifest-review' }
}

function Get-CollectionPlan {
    param([ValidateSet('Safe','Restricted')][string]$Mode)
    $restricted = ($Mode -eq 'Restricted')
    [pscustomobject][ordered]@{
        activeWlanDetails = $restricted
        retainRawBatteryReport = $restricted
        sleepStudy = $restricted
        retainClassificationRules = $restricted
    }
}

function Get-SaltedSha256 {
    param([Parameter(Mandatory)][string]$Value, [byte[]]$Salt = $script:PseudonymSalt)
    $valueBytes = [Text.Encoding]::UTF8.GetBytes($Value)
    $payload = New-Object byte[] ($Salt.Length + $valueBytes.Length)
    [Buffer]::BlockCopy($Salt, 0, $payload, 0, $Salt.Length)
    [Buffer]::BlockCopy($valueBytes, 0, $payload, $Salt.Length, $valueBytes.Length)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { -join ($sha.ComputeHash($payload) | ForEach-Object { $_.ToString('x2') }) }
    finally { $sha.Dispose() }
}

function Get-Sha256File {
    param([Parameter(Mandatory)][string]$Path)
    $fullPath = [IO.Path]::GetFullPath($Path)
    $stream = [IO.File]::Open($fullPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { -join ($sha.ComputeHash($stream) | ForEach-Object { $_.ToString('X2') }) }
    finally { $sha.Dispose(); $stream.Dispose() }
}

function Resolve-TrustedNativeExecutable {
    param([Parameter(Mandatory)][string]$FilePath)
    $systemDirectory = [IO.Path]::GetFullPath([Environment]::SystemDirectory).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if ([IO.Path]::IsPathRooted($FilePath)) {
        $resolvedPath = [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($FilePath))
    } else {
        if ([IO.Path]::GetFileName($FilePath) -ne $FilePath) { throw 'Relative native executable paths are not permitted.' }
        $resolvedPath = [IO.Path]::GetFullPath((Join-Path $systemDirectory $FilePath))
    }
    $systemPrefix = $systemDirectory + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedPath.StartsWith($systemPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Native executable is outside the approved Windows system directory.'
    }
    if (-not [IO.File]::Exists($resolvedPath)) { throw 'Approved native executable was not found.' }
    if (@('.exe','.com') -notcontains [IO.Path]::GetExtension($resolvedPath).ToLowerInvariant()) { throw 'Native executable type is not permitted.' }
    $signature = Microsoft.PowerShell.Security\Get-AuthenticodeSignature -FilePath $resolvedPath -ErrorAction Stop
    $signer = if ($signature.SignerCertificate) { [string]$signature.SignerCertificate.Subject } else { $null }
    if ([string]$signature.Status -ne 'Valid') {
        throw 'Native executable did not have a valid trusted signature.'
    }
    [pscustomobject][ordered]@{
        Path = $resolvedPath
        Name = [IO.Path]::GetFileName($resolvedPath)
        Sha256 = Get-Sha256File -Path $resolvedPath
        SignatureStatus = [string]$signature.Status
        Signer = $signer
    }
}

function Protect-Id {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $Value }
    if ($script:IncludeIds) { return $Value.Trim() }
    'sha256:' + (Get-SaltedSha256 -Value $Value.Trim())
}

function Protect-SensitiveText {
    param([string]$Value)
    Protect-Id -Value $Value
}

function Protect-ErrorMessage {
    param([string]$Message)
    if ([string]::IsNullOrWhiteSpace($Message) -or $script:IncludeIds) { return $Message }
    'redacted-error:sha256:' + (Get-SaltedSha256 -Value $Message)
}

function New-CaptureEnvelope {
    param(
        [Parameter(Mandatory)][string]$BundleId,
        [ValidateSet('Safe','Restricted')][string]$Mode,
        [string]$ComputerName,
        $Elevated
    )
    $envelope = [ordered]@{
        collectorVersion = $script:CollectorVersion
        capturedAt = (Get-Date).ToString('o')
        bundleId = $BundleId
        bundleMode = $Mode
        handling = Get-BundleHandling -Mode $Mode
        devicePseudonym = if ([string]::IsNullOrWhiteSpace($ComputerName)) { $null } else { 'sha256:' + (Get-SaltedSha256 -Value $ComputerName.Trim()) }
        elevated = $Elevated
        identifiersIncluded = ($Mode -eq 'Restricted')
    }
    if ($Mode -eq 'Restricted') { $envelope['hostname'] = $ComputerName }
    $envelope
}

function Get-SafePathRecord {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return [ordered]@{ fileName = $null; path = $null; pathPseudonym = $null }
    }
    $trimmed = $Path.Trim().Trim('"')
    [ordered]@{
        fileName = [IO.Path]::GetFileName($trimmed)
        path = if ($script:IncludeIds) { $trimmed } else { $null }
        pathPseudonym = if ($script:IncludeIds) { $null } else { Protect-SensitiveText $trimmed }
    }
}

function Get-SensitiveLocationRecord {
    param([string]$Location)
    [ordered]@{
        location = if ($script:IncludeIds) { $Location } else { $null }
        locationPseudonym = if (-not $script:IncludeIds) { Protect-SensitiveText ([string]$Location) } else { $null }
    }
}

function Test-Elevation {
    ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Add-CollectionError {
    param(
        [string]$Section, [string]$Code, [string]$Message,
        [string]$Command, [Nullable[int]]$ExitCode,
        [bool]$Incomplete = $true, [bool]$ForcesInconclusive = $true,
        [string]$ErrorId = ([guid]::NewGuid().ToString('N'))
    )
    $script:CollectionErrors += [pscustomobject][ordered]@{
        errorId = $ErrorId
        section = $Section
        code = $Code
        command = $Command
        exitCode = $ExitCode
        incomplete = $Incomplete
        forcesInconclusive = $ForcesInconclusive
        message = Protect-ErrorMessage $Message
        recordedAt = (Get-Date).ToString('o')
    }
}

function Invoke-Native {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$Name,
        [string]$Section,
        [bool]$FailureForcesInconclusive = $true,
        [switch]$AllowFailure
    )
    if ([string]::IsNullOrWhiteSpace($Name)) { $Name = [IO.Path]::GetFileName($FilePath) }
    if ([string]::IsNullOrWhiteSpace($Section)) { $Section = 'native.' + $Name }
    $started = Get-Date
    $output = @()
    $exitCode = $null
    $launchError = $null
    $nativeBinding = $null
    try {
        $nativeBinding = Resolve-TrustedNativeExecutable -FilePath $FilePath
        # WinPS 5.1 promotes native stderr to NativeCommandError when a caller has
        # ErrorActionPreference=Stop. Keep stderr as evidence while always reading
        # the process exit code before the enclosing capture wrapper can intervene.
        $previousNativeErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $output = @(& $nativeBinding.Path @ArgumentList 2>&1)
            $exitCode = $LASTEXITCODE
        }
        finally { $ErrorActionPreference = $previousNativeErrorActionPreference }
    } catch {
        $launchError = Protect-ErrorMessage $_.Exception.Message
    }
    $success = ($null -eq $launchError -and $exitCode -eq 0)
    $message = if ($launchError) { $launchError } elseif (-not $success) { "Native command exited with code $exitCode." } else { $null }
    $collectionErrorId = $null
    if (-not $success) {
        $collectionErrorId = [guid]::NewGuid().ToString('N')
        Add-CollectionError -Section $Section -Code 'NATIVE_COMMAND_FAILED' -Message $message -Command $Name -ExitCode $exitCode -Incomplete $true -ForcesInconclusive $FailureForcesInconclusive -ErrorId $collectionErrorId
    }
    $status = [pscustomobject][ordered]@{
        name = $Name
        executable = if ($nativeBinding) { $nativeBinding.Name } else { [IO.Path]::GetFileName($FilePath) }
        executableSha256 = if ($nativeBinding) { $nativeBinding.Sha256 } else { $null }
        signatureStatus = if ($nativeBinding) { $nativeBinding.SignatureStatus } else { 'UNKNOWN' }
        signer = if ($nativeBinding) { $nativeBinding.Signer } else { $null }
        startedAt = $started.ToString('o')
        durationMs = [math]::Round(((Get-Date) - $started).TotalMilliseconds, 0)
        exitCode = $exitCode
        success = $success
        outputLines = @($output).Count
        error = $message
        incomplete = (-not $success)
        forcesInconclusive = (-not $success -and $FailureForcesInconclusive)
        collectionErrorId = $collectionErrorId
    }
    $script:NativeStatuses += $status
    $result = [pscustomobject]@{ ExitCode = $exitCode; Output = $output; Success = $success; Error = $message }
    if (-not $success -and -not $AllowFailure) { throw "Native command '$Name' failed. $message" }
    $result
}

function Add-Section {
    param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)][scriptblock]$Body)
    Write-Host "Capturing $Name..."
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Stop'
        $script:report[$Name] = & $Body
    }
    catch {
        $message = Protect-ErrorMessage $_.Exception.Message
        Add-CollectionError -Section $Name -Code 'SECTION_FAILED' -Message $message
        $script:report[$Name] = [ordered]@{ status = 'UNKNOWN'; error = $message; sectionFailed = $true }
    }
    finally { $ErrorActionPreference = $previousErrorActionPreference }
}

function Invoke-SubCapture {
    param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)][scriptblock]$Body)
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Stop'
        [pscustomobject]@{ status = 'OK'; data = @(& $Body); error = $null }
    }
    catch {
        $message = Protect-ErrorMessage $_.Exception.Message
        Add-CollectionError -Section $Name -Code 'SUBCOLLECTION_FAILED' -Message $message
        [pscustomobject]@{ status = 'UNKNOWN'; data = @(); error = $message }
    }
    finally { $ErrorActionPreference = $previousErrorActionPreference }
}

function Get-WheaEventEvidence {
    param([Parameter(Mandatory)][scriptblock]$Query)
    try {
        $events = @(& $Query)
        [pscustomobject]@{ status = 'OK'; count = $events.Count; error = $null }
    }
    catch {
        if ([string]$_.FullyQualifiedErrorId -match '^NoMatchingEventsFound(?:,|$)') {
            return [pscustomobject]@{ status = 'OK'; count = 0; error = $null }
        }
        $message = Protect-ErrorMessage $_.Exception.Message
        Add-CollectionError -Section 'problemDevices.events' -Code 'WHEA_QUERY_FAILED' -Message $_.Exception.Message -Incomplete $true -ForcesInconclusive $true
        [pscustomobject]@{ status = 'UNKNOWN'; count = $null; error = $message }
    }
}

function Get-AgentClassification {
    param([string]$Path)
    $base = [ordered]@{
        Status = 'missing'; SourceName = if ($Path) { Split-Path -Leaf $Path } else { $null }
        FullPath = $Path; SchemaVersion = $null; RulesVersion = $null; Sha256 = $null
        RawBytes = $null; Rules = @(); Errors = @('Classification file not found.')
    }
    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [pscustomobject]$base
    }
    try {
        $rawBytes = [IO.File]::ReadAllBytes($Path)
        $base.RawBytes = $rawBytes
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $base.Sha256 = -join ($sha.ComputeHash($rawBytes) | ForEach-Object { $_.ToString('X2') }) } finally { $sha.Dispose() }
        if ($rawBytes.Length -ge 2 -and $rawBytes[0] -eq 0xFF -and $rawBytes[1] -eq 0xFE) { $rawText = [Text.Encoding]::Unicode.GetString($rawBytes, 2, $rawBytes.Length - 2) }
        elseif ($rawBytes.Length -ge 2 -and $rawBytes[0] -eq 0xFE -and $rawBytes[1] -eq 0xFF) { $rawText = [Text.Encoding]::BigEndianUnicode.GetString($rawBytes, 2, $rawBytes.Length - 2) }
        elseif ($rawBytes.Length -ge 3 -and $rawBytes[0] -eq 0xEF -and $rawBytes[1] -eq 0xBB -and $rawBytes[2] -eq 0xBF) { $rawText = [Text.Encoding]::UTF8.GetString($rawBytes, 3, $rawBytes.Length - 3) }
        else { $rawText = [Text.Encoding]::UTF8.GetString($rawBytes) }
        $document = Microsoft.PowerShell.Utility\ConvertFrom-Json -InputObject $rawText -ErrorAction Stop
    }
    catch {
        $base.Status = 'invalid'; $base.Errors = @("JSON parse failed: $(Protect-ErrorMessage $_.Exception.Message)")
        return [pscustomobject]$base
    }
    $errors = @()
    if (-not ($document.PSObject.Properties.Name -contains 'schemaVersion') -or [string]::IsNullOrWhiteSpace([string]$document.schemaVersion)) { $errors += 'schemaVersion is required.' }
    elseif ([string]$document.schemaVersion -ne '1.0') { $errors += "Unsupported schemaVersion '$($document.schemaVersion)'." }
    if (-not ($document.PSObject.Properties.Name -contains 'rulesVersion') -or [string]::IsNullOrWhiteSpace([string]$document.rulesVersion)) { $errors += 'rulesVersion is required.' }
    if (-not ($document.PSObject.Properties.Name -contains 'rules')) { $errors += 'rules array is required.' }
    $allowedClasses = @('edr','dlp','ztna','vpn','management','monitoring','other')
    $allowedTargets = @('service','scheduledTask','kernelDriver','minifilter')
    $ids = @()
    foreach ($rule in @($document.rules)) {
        foreach ($required in @('id','match','product','class')) {
            if (-not ($rule.PSObject.Properties.Name -contains $required) -or [string]::IsNullOrWhiteSpace([string]$rule.$required)) { $errors += "Rule is missing $required." }
        }
        if ($rule.id) { if ($ids -contains [string]$rule.id) { $errors += "Duplicate rule id '$($rule.id)'." }; $ids += [string]$rule.id }
        if ($rule.class -and $allowedClasses -notcontains [string]$rule.class) { $errors += "Rule '$($rule.id)' has unsupported class '$($rule.class)'." }
        foreach ($target in @($rule.targets)) { if ($allowedTargets -notcontains [string]$target) { $errors += "Rule '$($rule.id)' has unsupported target '$target'." } }
        if ($rule.match) {
            try { [void][regex]::IsMatch('', [string]$rule.match, [Text.RegularExpressions.RegexOptions]::IgnoreCase, [TimeSpan]::FromMilliseconds(100)) }
            catch { $errors += "Rule '$($rule.id)' has an invalid or unsafe regular expression." }
        }
    }
    $base.SchemaVersion = [string]$document.schemaVersion
    $base.RulesVersion = [string]$document.rulesVersion
    $base.Rules = if ($errors.Count -eq 0) { @($document.rules) } else { @() }
    $base.Errors = @($errors)
    $base.Status = if ($errors.Count -eq 0) { 'valid' } else { 'invalid' }
    [pscustomobject]$base
}

function Copy-AgentClassificationEvidence {
    param(
        [Parameter(Mandatory)]$Classification,
        [Parameter(Mandatory)][string]$Directory,
        [bool]$RetainRulesFile = $true,
        [scriptblock]$HashProvider = { param($EvidencePath) Get-Sha256File -Path $EvidencePath }
    )
    if ($Classification.Status -ne 'valid') {
        return [pscustomobject]@{ status = $Classification.Status; file = $null; sha256 = $Classification.Sha256; schemaVersion = $Classification.SchemaVersion; rulesVersion = $Classification.RulesVersion }
    }
    # A Safe bundle needs the exact rules version/hash for reproducibility, but the
    # potentially internal rule content itself is retained only in Restricted mode.
    if (-not $RetainRulesFile) {
        return [pscustomobject]@{ status = 'valid'; file = $null; sha256 = $Classification.Sha256; schemaVersion = $Classification.SchemaVersion; rulesVersion = $Classification.RulesVersion }
    }
    $destination = Join-Path $Directory 'agent-classification.rules.json'
    try {
        [IO.File]::WriteAllBytes($destination, [byte[]]$Classification.RawBytes)
        $copyHash = & $HashProvider $destination
        if ($copyHash -ne $Classification.Sha256) { throw 'Classification evidence copy hash mismatch.' }
    }
    catch {
        $copyFailure = $_
        try { if ([IO.File]::Exists($destination)) { [IO.File]::Delete($destination) } }
        catch { throw 'Classification evidence copy failed and its partial output could not be removed.' }
        throw $copyFailure
    }
    [pscustomobject]@{ status = 'valid'; file = 'agent-classification.rules.json'; sha256 = $copyHash; schemaVersion = $Classification.SchemaVersion; rulesVersion = $Classification.RulesVersion }
}

function Get-ActiveClassificationRules {
    param($Classification, $ClassificationEvidence, $ClassificationApproval)
    if ($Classification.Status -eq 'valid' -and $ClassificationEvidence.status -eq 'valid' -and $ClassificationApproval.status -in @('APPROVED','NOT_REQUIRED')) { @($Classification.Rules) } else { @() }
}

function Test-AgentClassificationApproval {
    param($Classification, [string]$ApprovedSha256)
    if ($Classification.Status -ne 'valid') { return [pscustomobject]@{ status = 'INVALID'; approvedSha256 = $null } }
    if (@($Classification.Rules).Count -eq 0) { return [pscustomobject]@{ status = 'NOT_REQUIRED'; approvedSha256 = $null } }
    if ([string]::IsNullOrWhiteSpace($ApprovedSha256)) { return [pscustomobject]@{ status = 'APPROVAL_REQUIRED'; approvedSha256 = $null } }
    if ($ApprovedSha256 -notmatch '^[0-9A-Fa-f]{64}$') { return [pscustomobject]@{ status = 'DIGEST_INVALID'; approvedSha256 = $null } }
    if ($Classification.Sha256 -ne $ApprovedSha256.ToUpperInvariant()) { return [pscustomobject]@{ status = 'DIGEST_MISMATCH'; approvedSha256 = $ApprovedSha256.ToUpperInvariant() } }
    [pscustomobject]@{ status = 'APPROVED'; approvedSha256 = $ApprovedSha256.ToUpperInvariant() }
}

function Get-LocalModuleTreeFiles {
    param([Parameter(Mandatory)][string]$ModuleRoot)
    $root = [IO.Path]::GetFullPath($ModuleRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if ($root -notmatch '^[A-Za-z]:[\\/]') { throw 'Approved module tree must use a local drive-letter path.' }
    $drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($root))
    if ($drive.DriveType -ne [IO.DriveType]::Fixed) { throw 'Approved module tree must reside on a fixed local drive.' }
    $pending = [Collections.Generic.Queue[string]]::new()
    $pending.Enqueue($root)
    $files = [Collections.Generic.List[string]]::new()
    while ($pending.Count -gt 0) {
        $directory = $pending.Dequeue()
        if (([IO.File]::GetAttributes($directory) -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Approved module tree may not contain reparse points.' }
        foreach ($entry in [IO.Directory]::EnumerateFileSystemEntries($directory, '*', [IO.SearchOption]::TopDirectoryOnly)) {
            $attributes = [IO.File]::GetAttributes($entry)
            if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Approved module tree may not contain reparse points.' }
            if (($attributes -band [IO.FileAttributes]::Directory) -ne 0) { $pending.Enqueue($entry) } else { $files.Add([IO.Path]::GetFullPath($entry)) }
        }
    }
    $result = $files.ToArray()
    [Array]::Sort($result, [StringComparer]::OrdinalIgnoreCase)
    $result
}

function Get-ModuleTreeSha256 {
    param([Parameter(Mandatory)][string]$ModuleEntryPath)
    $entryPath = [IO.Path]::GetFullPath($ModuleEntryPath)
    if (-not [IO.File]::Exists($entryPath)) { throw 'Approved module entry file was not found.' }
    $moduleRoot = [IO.Path]::GetDirectoryName($entryPath).TrimEnd([IO.Path]::DirectorySeparatorChar)
    [string[]]$files = @(Get-LocalModuleTreeFiles -ModuleRoot $moduleRoot)
    $records = foreach ($file in $files) {
        $fullFile = [IO.Path]::GetFullPath($file)
        $relative = $fullFile.Substring($moduleRoot.Length).TrimStart([char[]]@('\','/')).Replace('\','/')
        $relative.ToLowerInvariant() + "`0" + (Get-Sha256File -Path $fullFile)
    }
    $payload = [Text.Encoding]::UTF8.GetBytes(($records -join "`n"))
    $sha = [Security.Cryptography.SHA256]::Create()
    try { -join ($sha.ComputeHash($payload) | ForEach-Object { $_.ToString('X2') }) }
    finally { $sha.Dispose() }
}

function Test-LocalModuleManifestReferences {
    param([Parameter(Mandatory)][string]$EntryPath, [Parameter(Mandatory)][string]$ModuleRoot)
    $manifest = Microsoft.PowerShell.Utility\Import-PowerShellDataFile -Path $EntryPath -ErrorAction Stop
    $root = [IO.Path]::GetFullPath($ModuleRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $rootPrefix = $root + [IO.Path]::DirectorySeparatorChar
    $references = @()
    foreach ($field in @('RootModule','ModuleToProcess','ScriptsToProcess','NestedModules','RequiredAssemblies','RequiredModules')) {
        foreach ($value in @($manifest[$field])) {
            if ($null -eq $value) { continue }
            $reference = if ($value -is [Collections.IDictionary] -and $value.Contains('ModuleName')) { [string]$value['ModuleName'] } else { [string]$value }
            if ([string]::IsNullOrWhiteSpace($reference)) { continue }
            $references += $reference
        }
    }
    foreach ($reference in $references) {
        if ([IO.Path]::IsPathRooted($reference)) { throw 'CMSL manifest code references must be relative and contained in the approved tree.' }
        $referencePath = [IO.Path]::GetFullPath([IO.Path]::Combine($root, $reference))
        if (-not $referencePath.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase) -or -not [IO.File]::Exists($referencePath)) {
            throw 'CMSL manifest code references must resolve to files inside the approved tree.'
        }
    }
    $true
}

function Set-PrivateDirectoryAcl {
    param([Parameter(Mandatory)][string]$Path)
    $security = [Security.AccessControl.DirectorySecurity]::new()
    $security.SetAccessRuleProtection($true, $false)
    $inheritance = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    $propagation = [Security.AccessControl.PropagationFlags]::None
    $access = [Security.AccessControl.AccessControlType]::Allow
    $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $systemSid = [Security.Principal.SecurityIdentifier]::new([Security.Principal.WellKnownSidType]::LocalSystemSid, $null)
    $security.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($currentSid, [Security.AccessControl.FileSystemRights]::FullControl, $inheritance, $propagation, $access))
    $security.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($systemSid, [Security.AccessControl.FileSystemRights]::FullControl, $inheritance, $propagation, $access))
    $directory = [IO.DirectoryInfo]::new([IO.Path]::GetFullPath($Path))
    $instanceSetter = [IO.DirectoryInfo].GetMethod(
        'SetAccessControl',
        [Reflection.BindingFlags]'Instance, Public',
        $null,
        [type[]]@([Security.AccessControl.DirectorySecurity]),
        $null
    )
    if ($null -ne $instanceSetter) {
        # .NET Framework exposes the ACL setter as a DirectoryInfo instance method.
        $null = $instanceSetter.Invoke($directory, [object[]]@($security))
        return
    }

    # .NET/Core exposes the same operation only through the framework extension API.
    [IO.FileSystemAclExtensions]::SetAccessControl($directory, $security)
}

function New-TrustedTemporaryDirectory {
    param(
        [string]$Purpose = 'work',
        [string]$CandidateRoot = ([IO.Path]::Combine([IO.Directory]::GetParent([Environment]::SystemDirectory).FullName, 'Temp')),
        [scriptblock]$AttributeProvider = { param($CandidatePath) [IO.File]::GetAttributes($CandidatePath) },
        [scriptblock]$DriveTypeProvider = { param($DriveRoot) ([IO.DriveInfo]::new($DriveRoot)).DriveType },
        [scriptblock]$DirectoryCreator = { param($NewDirectory) [IO.Directory]::CreateDirectory($NewDirectory) }
    )
    if ([string]::IsNullOrWhiteSpace($CandidateRoot) -or $CandidateRoot -match '^(?:\\\\|//|\\\?\\|\\\.\\|\\Device\\|[^:]+::)') { throw 'Temporary root must not be remote, device, or provider-qualified.' }
    if ($CandidateRoot -notmatch '^[A-Za-z]:[\\/]') { throw 'Temporary root must use a local drive-letter path.' }
    if ($CandidateRoot.Substring(2).Contains(':')) { throw 'Temporary root may not use alternate data streams.' }
    $root = [IO.Path]::GetFullPath($CandidateRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $driveRoot = [IO.Path]::GetPathRoot($root)
    if ((& $DriveTypeProvider $driveRoot) -ne [IO.DriveType]::Fixed) { throw 'Temporary root must reside on a fixed local drive.' }
    $current = $driveRoot
    foreach ($segment in $root.Substring($driveRoot.Length).Split([char[]]@('\','/'), [StringSplitOptions]::RemoveEmptyEntries)) {
        $current = [IO.Path]::Combine($current, $segment)
        $attributes = & $AttributeProvider $current
        if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Temporary root may not traverse a reparse point.' }
        if (($attributes -band [IO.FileAttributes]::Directory) -eq 0) { throw 'Temporary root component was not a directory.' }
    }
    $safePurpose = [regex]::Replace($Purpose.ToLowerInvariant(), '[^a-z0-9-]', '-')
    $privatePath = [IO.Path]::Combine($root, 'laptop-evidence-' + $safePurpose + '-' + [guid]::NewGuid().ToString('N'))
    $created = & $DirectoryCreator $privatePath
    if (-not [IO.Directory]::Exists($privatePath)) { throw 'Private temporary directory was not created.' }
    try { Set-PrivateDirectoryAcl -Path $privatePath }
    catch {
        $aclFailure = $_
        try { [IO.Directory]::Delete($privatePath, $true) } catch { throw 'Private temporary directory ACL failed and cleanup also failed.' }
        throw $aclFailure
    }
    $privatePath
}

function New-PrivateModuleSnapshot {
    param([Parameter(Mandatory)]$Binding)
    $snapshotRoot = New-TrustedTemporaryDirectory -Purpose 'cmsl'
    try {
        foreach ($sourceFile in @(Get-LocalModuleTreeFiles -ModuleRoot $Binding.moduleRoot)) {
            $relative = $sourceFile.Substring($Binding.moduleRoot.Length).TrimStart([char[]]@('\','/'))
            $destination = [IO.Path]::Combine($snapshotRoot, $relative)
            $destinationDirectory = [IO.Path]::GetDirectoryName($destination)
            if (-not [IO.Directory]::Exists($destinationDirectory)) { [IO.Directory]::CreateDirectory($destinationDirectory) | Out-Null }
            [IO.File]::Copy($sourceFile, $destination, $false)
        }
        $entryRelative = $Binding.entryPath.Substring($Binding.moduleRoot.Length).TrimStart([char[]]@('\','/'))
        $snapshotEntry = [IO.Path]::Combine($snapshotRoot, $entryRelative)
        $snapshotHash = Get-ModuleTreeSha256 -ModuleEntryPath $snapshotEntry
        if ($snapshotHash -ne $Binding.treeSha256) { throw 'Private CMSL snapshot did not match the approved module-tree SHA-256.' }
        $null = Test-LocalModuleManifestReferences -EntryPath $snapshotEntry -ModuleRoot $snapshotRoot
        [pscustomobject]@{ root = $snapshotRoot; entryPath = $snapshotEntry; treeSha256 = $snapshotHash }
    }
    catch {
        $snapshotFailure = $_
        try { if ([IO.Directory]::Exists($snapshotRoot)) { [IO.Directory]::Delete($snapshotRoot, $true) } } catch { throw 'CMSL snapshot creation failed and its private temporary directory could not be removed.' }
        throw $snapshotFailure
    }
}

function Test-ApprovedCmslModuleBinding {
    param([string]$ModulePath, [string]$ExpectedTreeSha256)
    $result = [ordered]@{ status = 'NOT_PROVIDED'; entryPath = $null; moduleRoot = $null; treeSha256 = $null; reason = $null }
    if ([string]::IsNullOrWhiteSpace($ModulePath) -and [string]::IsNullOrWhiteSpace($ExpectedTreeSha256)) { return [pscustomobject]$result }
    if ([string]::IsNullOrWhiteSpace($ModulePath) -or [string]::IsNullOrWhiteSpace($ExpectedTreeSha256)) {
        $result.status = 'INVALID'; $result.reason = 'Both approved CMSL module path and tree SHA-256 are required.'; return [pscustomobject]$result
    }
    try {
        if (-not [IO.Path]::IsPathRooted($ModulePath)) { throw 'Approved CMSL module path must be absolute.' }
        $entryPath = [IO.Path]::GetFullPath($ModulePath)
        if ([IO.Path]::GetExtension($entryPath).ToLowerInvariant() -ne '.psd1') { throw 'Approved CMSL entry must be an exact .psd1 manifest path.' }
        if ($ExpectedTreeSha256 -notmatch '^[0-9A-Fa-f]{64}$') { throw 'Approved CMSL tree SHA-256 must contain 64 hexadecimal characters.' }
        $actual = Get-ModuleTreeSha256 -ModuleEntryPath $entryPath
        if ($actual -ne $ExpectedTreeSha256.ToUpperInvariant()) { throw 'Approved CMSL module tree SHA-256 did not match.' }
        $null = Test-LocalModuleManifestReferences -EntryPath $entryPath -ModuleRoot ([IO.Path]::GetDirectoryName($entryPath))
        $result.status = 'VALID'; $result.entryPath = $entryPath
        $result.moduleRoot = [IO.Path]::GetDirectoryName($entryPath).TrimEnd([IO.Path]::DirectorySeparatorChar)
        $result.treeSha256 = $actual
    } catch {
        $result.status = 'INVALID'; $result.reason = Protect-ErrorMessage $_.Exception.Message
    }
    [pscustomobject]$result
}

function ConvertTo-NormalizedPublisherName {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
    ([regex]::Replace($Value.ToLowerInvariant(), '[^a-z0-9]+', ' ')).Trim()
}

function Test-PublisherLegalSuffix {
    param([string]$NormalizedName)
    -not [string]::IsNullOrWhiteSpace($NormalizedName) -and $NormalizedName -match '(?:^|\s)(?:corporation|corp|incorporated|inc|limited|ltd|llc|plc|company|co)$'
}

function Remove-PublisherLegalSuffix {
    param([string]$NormalizedName)
    ([regex]::Replace($NormalizedName, '\s+(?:corporation|corp|incorporated|inc|limited|ltd|llc|plc|company|co)$', '')).Trim()
}

function Get-PublisherDnValues {
    param([string]$Value, [ValidateSet('O','CN')][string]$Field)
    $values = @()
    foreach ($part in ([string]$Value -split ',')) {
        if ($part -match ('^\s*' + $Field + '\s*=\s*(.+?)\s*$')) {
            $normalized = ConvertTo-NormalizedPublisherName -Value $matches[1]
            if ($normalized -and $values -notcontains $normalized) { $values += $normalized }
        }
    }
    @($values)
}

function Test-PublisherAliasMatch {
    param(
        [string]$Candidate, [string[]]$PlatformPublishers,
        [ValidateSet('Provider','Signer')][string]$Role
    )
    if ([string]::IsNullOrWhiteSpace($Candidate)) { return $false }
    $exactOrganizations = @()
    $shortOrganizations = @()
    $signerDisplays = @()
    foreach ($platformPublisher in @($PlatformPublishers)) {
        $organizations = @(Get-PublisherDnValues -Value $platformPublisher -Field O)
        if ($organizations.Count -eq 0) {
            $plainIdentity = ConvertTo-NormalizedPublisherName -Value $platformPublisher
            if ($plainIdentity) { $organizations = @($plainIdentity) }
        } else {
            $signerDisplays += @(Get-PublisherDnValues -Value $platformPublisher -Field CN)
        }
        foreach ($organization in $organizations) {
            if ($exactOrganizations -notcontains $organization) { $exactOrganizations += $organization }
            if (Test-PublisherLegalSuffix $organization) {
                $short = Remove-PublisherLegalSuffix $organization
                if ($short -and $shortOrganizations -notcontains $short) { $shortOrganizations += $short }
            }
        }
    }
    $candidateOrganizations = @(Get-PublisherDnValues -Value $Candidate -Field O)
    if ($candidateOrganizations.Count -gt 0) {
        # A certificate O is authoritative; a colliding CN cannot override it.
        foreach ($organization in $candidateOrganizations) {
            if ($exactOrganizations -contains $organization) { return $true }
            if (-not (Test-PublisherLegalSuffix $organization) -and $shortOrganizations -contains $organization) { return $true }
        }
        return $false
    }
    $candidateName = ConvertTo-NormalizedPublisherName -Value $Candidate
    if ($exactOrganizations -contains $candidateName) { return $true }
    if (-not (Test-PublisherLegalSuffix $candidateName) -and $shortOrganizations -contains $candidateName) { return $true }
    if ($Role -eq 'Signer' -and $signerDisplays -contains $candidateName) { return $true }
    $false
}

function Resolve-PublisherOrigin {
    param(
        [string]$Provider, [string]$Signer, [bool]$SignatureTrusted = $false,
        [string]$PlatformPublisher = $script:PlatformPublisher,
        [string[]]$PlatformPublisherAliases = $script:PlatformPublisherAliases
    )
    $platformIdentities = @($PlatformPublisher) + @($PlatformPublisherAliases)
    $providerMatchesPlatform = Test-PublisherAliasMatch -Candidate $Provider -PlatformPublishers $platformIdentities -Role Provider
    $signerMatchesPlatform = Test-PublisherAliasMatch -Candidate $Signer -PlatformPublishers $platformIdentities -Role Signer
    # Provider metadata takes precedence so a third-party driver carrying a platform
    # compatibility signature remains third-party. Platform origin requires a trusted
    # signature and a publisher value derived from the OS or an approved override.
    if (-not [string]::IsNullOrWhiteSpace($Provider)) {
        if ($providerMatchesPlatform) {
            if ($SignatureTrusted -and ([string]::IsNullOrWhiteSpace($Signer) -or $signerMatchesPlatform)) { return 'platform-signed' }
            return 'unknown'
        }
        return 'third-party'
    }
    if ($SignatureTrusted -and -not [string]::IsNullOrWhiteSpace($Signer)) {
        if ($signerMatchesPlatform) { return 'platform-signed' }
        return 'third-party'
    }
    'unknown'
}

function Resolve-AgentClass {
    param(
        $Rules, [string]$EvidenceText, [string]$DefaultProduct, [string]$TargetType,
        [ValidateSet('platform-signed','third-party','unknown')][string]$PublisherOrigin = 'unknown'
    )
    foreach ($rule in @($Rules)) {
        $targets = @($rule.targets)
        if ($targets.Count -gt 0 -and $targets -notcontains $TargetType) { continue }
        $matched = $false
        try { $matched = [regex]::IsMatch([string]$EvidenceText, [string]$rule.match, [Text.RegularExpressions.RegexOptions]::IgnoreCase, [TimeSpan]::FromMilliseconds(100)) }
        catch {
            Add-CollectionError -Section 'agentClassification.runtime' -Code 'RULE_MATCH_FAILED' -Message 'A classification rule failed or exceeded its match-time limit.' -Incomplete $true -ForcesInconclusive $true
        }
        if ($matched) {
            return [pscustomobject]@{ product = [string]$rule.product; class = [string]$rule.class; ruleId = [string]$rule.id }
        }
    }
    $unmatchedClass = if ($PublisherOrigin -eq 'third-party') { 'unclassified-thirdparty' } else { 'unclassified' }
    [pscustomobject]@{ product = if ($DefaultProduct) { $DefaultProduct } else { 'Unknown' }; class = $unmatchedClass; ruleId = $null }
}

function Split-ExecutableCommandLine {
    param([string]$CommandLine)
    if ([string]::IsNullOrWhiteSpace($CommandLine)) { return [pscustomobject]@{ Executable = $null; Arguments = $null } }
    $expanded = [Environment]::ExpandEnvironmentVariables($CommandLine.Trim())
    $executable = $null
    $arguments = ''
    if ($expanded -match '^\s*"([^"]+)"\s*(.*)$') {
        $executable = $matches[1]; $arguments = $matches[2]
    } elseif ($expanded -match "^\s*'([^']+)'\s*(.*)$") {
        $executable = $matches[1]; $arguments = $matches[2]
    } elseif ($expanded -match '^\s*(.+?\.(?:exe|com|cmd|bat|sys|dll))(?=\s|$)\s*(.*)$') {
        $executable = $matches[1]; $arguments = $matches[2]
    } else {
        $parts = $expanded -split '\s+', 2
        $executable = $parts[0]
        if ($parts.Count -gt 1) { $arguments = $parts[1] }
    }
    $executable = $executable.Trim().Trim('"')
    if ($executable.StartsWith('\??\')) { $executable = $executable.Substring(4) }
    if ($executable -match '^\\SystemRoot\\(.+)$') { $executable = Join-Path $env:SystemRoot $matches[1] }
    elseif ($executable -match '^(?i)System32\\(.+)$') { $executable = Join-Path (Join-Path $env:SystemRoot 'System32') $matches[1] }
    [pscustomobject]@{ Executable = $executable; Arguments = $arguments }
}

function Resolve-LocalObservedExecutable {
    param(
        [string]$Path,
        [scriptblock]$AttributeProvider = { param($ObservedPath) [IO.File]::GetAttributes($ObservedPath) }
    )
    $result = [ordered]@{ status = 'REJECTED'; path = $null; reason = $null }
    if ([string]::IsNullOrWhiteSpace($Path)) { $result.status = 'MISSING'; $result.reason = 'No executable path was reported.'; return [pscustomobject]$result }
    $candidate = [Environment]::ExpandEnvironmentVariables($Path.Trim().Trim('"'))
    if ($candidate -match '^(?:\\\\|//|\\\?\\|\\\.\\|\\Device\\|[^:]+::)') {
        $result.reason = 'Remote, device, and provider-qualified executable paths are not permitted.'; return [pscustomobject]$result
    }
    if (-not [IO.Path]::IsPathRooted($candidate)) {
        if ([IO.Path]::GetFileName($candidate) -ne $candidate) { $result.reason = 'Relative observed executable paths are not permitted.'; return [pscustomobject]$result }
        $systemCandidate = [IO.Path]::GetFullPath([IO.Path]::Combine([Environment]::SystemDirectory, $candidate))
        if (-not [IO.File]::Exists($systemCandidate)) { $result.reason = 'Unqualified observed executable was not present in the trusted system directory.'; return [pscustomobject]$result }
        $candidate = $systemCandidate
    }
    if ($candidate -notmatch '^[A-Za-z]:[\\/]') { $result.reason = 'Only local drive-letter executable paths are permitted.'; return [pscustomobject]$result }
    if ($candidate.Substring(2).Contains(':')) { $result.reason = 'Alternate data stream executable paths are not permitted.'; return [pscustomobject]$result }
    try {
        $fullPath = [IO.Path]::GetFullPath($candidate)
        $root = [IO.Path]::GetPathRoot($fullPath)
        $drive = [IO.DriveInfo]::new($root)
        if ($drive.DriveType -ne [IO.DriveType]::Fixed) { throw 'Observed executable is not on a fixed local drive.' }
        $current = $root
        foreach ($segment in $fullPath.Substring($root.Length).Split([char[]]@('\','/'), [StringSplitOptions]::RemoveEmptyEntries)) {
            $current = [IO.Path]::Combine($current, $segment)
            try {
                $attributes = & $AttributeProvider $current
                if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Observed executable path traverses a reparse point.' }
            }
            catch [IO.FileNotFoundException] { break }
            catch [IO.DirectoryNotFoundException] { break }
        }
        $result.status = 'LOCAL'; $result.path = $fullPath
    } catch { $result.reason = Protect-ErrorMessage $_.Exception.Message }
    [pscustomobject]$result
}

function Get-ExecutableMetadata {
    param([string]$Path)
    $pathResolution = Resolve-LocalObservedExecutable -Path $Path
    $resolvedPath = if ($pathResolution.status -eq 'LOCAL') { $pathResolution.path } else { $Path }
    $safePath = Get-SafePathRecord -Path $resolvedPath
    $result = [ordered]@{
        status = 'UNAVAILABLE'; fileName = $safePath.fileName; path = $safePath.path
        pathPseudonym = $safePath.pathPseudonym; productName = $null; version = $null
        provider = $null; signatureStatus = $null; signer = $null; limitation = $null
    }
    if ($pathResolution.status -ne 'LOCAL') {
        $result.limitation = $pathResolution.reason
        if ($pathResolution.status -ne 'MISSING') { Add-CollectionError -Section 'agentInventory.executableMetadata' -Code 'EXECUTABLE_PATH_REJECTED' -Message $pathResolution.reason -Incomplete $true -ForcesInconclusive $true }
        return [pscustomobject]$result
    }
    try {
        if (-not [IO.File]::Exists($resolvedPath)) {
            $result.limitation = 'Executable was not available at collection time.'
            Add-CollectionError -Section 'agentInventory.executableMetadata' -Code 'EXECUTABLE_UNAVAILABLE' -Message $result.limitation -Incomplete $true -ForcesInconclusive $true
            return [pscustomobject]$result
        }
        $versionInfo = [Diagnostics.FileVersionInfo]::GetVersionInfo($resolvedPath)
        $metadataLimitations = @()
        $result.productName = $versionInfo.ProductName
        $result.version = if ($versionInfo.ProductVersion) { $versionInfo.ProductVersion } else { $versionInfo.FileVersion }
        $result.provider = $versionInfo.CompanyName
        if ([string]::IsNullOrWhiteSpace([string]$result.provider)) {
            $metadataLimitations += 'File provider metadata was unavailable.'
            Add-CollectionError -Section 'agentInventory.executableMetadata' -Code 'PROVIDER_UNKNOWN' -Message 'File provider metadata was unavailable.' -Incomplete $true -ForcesInconclusive $true
        }
        try {
            $signature = Microsoft.PowerShell.Security\Get-AuthenticodeSignature -FilePath $resolvedPath -ErrorAction Stop
            $result.signatureStatus = [string]$signature.Status
            if ($signature.SignerCertificate) { $result.signer = $signature.SignerCertificate.Subject }
            if ($result.signatureStatus -eq 'UnknownError') {
                $metadataLimitations += 'Authenticode returned an unknown result.'
                Add-CollectionError -Section 'agentInventory.executableMetadata' -Code 'SIGNATURE_UNKNOWN' -Message 'Authenticode returned an unknown result.' -Incomplete $true -ForcesInconclusive $true
            }
        } catch {
            $result.signatureStatus = 'UNKNOWN'; $metadataLimitations += Protect-ErrorMessage $_.Exception.Message
            Add-CollectionError -Section 'agentInventory.executableMetadata' -Code 'SIGNATURE_QUERY_FAILED' -Message $_.Exception.Message -Incomplete $true -ForcesInconclusive $true
        }
        $result.status = if ($metadataLimitations.Count -eq 0) { 'OK' } else { 'PARTIAL' }
        $result.limitation = if ($metadataLimitations.Count -gt 0) { $metadataLimitations -join ' ' } else { $null }
    } catch {
        $result.limitation = Protect-ErrorMessage $_.Exception.Message
        Add-CollectionError -Section 'agentInventory.executableMetadata' -Code 'METADATA_QUERY_FAILED' -Message $_.Exception.Message -Incomplete $true -ForcesInconclusive $true
    }
    [pscustomobject]$result
}

function New-AgentObservation {
    param(
        [Parameter(Mandatory)][string]$Kind,
        [string]$Name, [string]$DisplayName, [string]$State, [string]$CommandLine,
        $Rules
    )
    $command = Split-ExecutableCommandLine -CommandLine $CommandLine
    $metadata = Get-ExecutableMetadata -Path $command.Executable
    $defaultProduct = $null
    foreach ($candidate in @($metadata.productName, $metadata.provider)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$candidate)) { $defaultProduct = [string]$candidate; break }
    }
    if ([string]::IsNullOrWhiteSpace($defaultProduct)) {
        $defaultProduct = if ($Kind -eq 'scheduledTask') { 'Unclassified scheduled task' } elseif ($DisplayName) { $DisplayName } elseif ($Name) { $Name } else { 'Unknown' }
    }
    $evidenceText = @($Name, $DisplayName, $CommandLine, $metadata.productName, $metadata.provider, $metadata.signer) -join "`n"
    $publisherOrigin = Resolve-PublisherOrigin -Provider $metadata.provider -Signer $metadata.signer -SignatureTrusted ($metadata.signatureStatus -eq 'Valid')
    $classification = Resolve-AgentClass -Rules $Rules -EvidenceText $evidenceText -DefaultProduct $defaultProduct -TargetType $Kind -PublisherOrigin $publisherOrigin
    $configuredClassification = -not [string]::IsNullOrWhiteSpace([string]$classification.ruleId)
    [ordered]@{
        kind = $Kind
        name = if ($script:IncludeIds) { $Name } else { $null }
        displayName = if ($script:IncludeIds) { $DisplayName } else { $null }
        observationPseudonym = if ($script:IncludeIds) { $null } else { Protect-SensitiveText (@($Kind,$Name,$DisplayName) -join '|') }
        state = $State
        product = if ($script:IncludeIds) { $classification.product } else { $null }
        productPseudonym = if (-not $script:IncludeIds) { Protect-SensitiveText ([string]$classification.product) } else { $null }
        class = $classification.class
        publisherOrigin = $publisherOrigin
        classificationRuleId = if ($script:IncludeIds) { $classification.ruleId } else { $null }
        classificationRulePseudonym = if (-not $script:IncludeIds -and $configuredClassification) { Protect-SensitiveText ([string]$classification.ruleId) } else { $null }
        version = $metadata.version
        provider = if ($script:IncludeIds) { $metadata.provider } else { $null }
        providerPseudonym = if (-not $script:IncludeIds) { Protect-SensitiveText ([string]$metadata.provider) } else { $null }
        signatureStatus = $metadata.signatureStatus
        signer = if ($script:IncludeIds) { $metadata.signer } else { $null }
        signerPseudonym = if (-not $script:IncludeIds) { Protect-SensitiveText ([string]$metadata.signer) } else { $null }
        binary = [ordered]@{
            fileName = if ($script:IncludeIds) { $metadata.fileName } else { $null }
            fileNamePseudonym = if (-not $script:IncludeIds) { Protect-SensitiveText ([string]$metadata.fileName) } else { $null }
            path = $metadata.path; pathPseudonym = $metadata.pathPseudonym
        }
        metadataStatus = $metadata.status; knownLimitation = $metadata.limitation
    }
}

function Get-ReportValue {
    param($Object, [Parameter(Mandatory)][string]$Path, $Default = 'unknown')
    $current = $Object
    foreach ($segment in $Path.Split('.')) {
        if ($null -eq $current) { return $Default }
        if ($current -is [Collections.IDictionary]) {
            if (-not $current.Contains($segment)) { return $Default }
            $current = $current[$segment]
        } else {
            $property = $current.PSObject.Properties[$segment]
            if ($null -eq $property) { return $Default }
            $current = $property.Value
        }
    }
    if ($null -eq $current -or ([string]$current).Length -eq 0) { return $Default }
    $current
}

function Write-CollectorSummary {
    param([Parameter(Mandatory)]$Report, [Parameter(Mandatory)][string]$Path)
    $agentStatus = Get-ReportValue $Report 'agentInventory.status' 'MISSING'
    $agentCount = if ($agentStatus -eq 'UNKNOWN' -or $agentStatus -eq 'MISSING') { 'unknown' } else { @(Get-ReportValue $Report 'agentInventory.services' @()).Count }
    $lines = @(
        "Evidence bundle ID: $(Get-ReportValue $Report 'bundleId')"
        "Bundle mode: $(Get-ReportValue $Report 'bundleMode')"
        "Model: $(Get-ReportValue $Report 'identity.productName')  SKU: $(Get-ReportValue $Report 'identity.systemSku')"
        "BIOS: $(Get-ReportValue $Report 'bios.version')"
        "CPU: $(Get-ReportValue $Report 'cpu.name')"
        "OS: $(Get-ReportValue $Report 'os.caption') build $(Get-ReportValue $Report 'os.build')"
        "Security: TPM=$(Get-ReportValue $Report 'tpm.present') SecureBoot=$(Get-ReportValue $Report 'secureBoot.enabled') VBS=$(Get-ReportValue $Report 'vbs.vbsStatus')"
        "Agent services captured: $agentCount"
        "Collection errors: $(@($script:CollectionErrors).Count)"
    )
    [IO.File]::WriteAllLines($Path, [string[]]$lines, [Text.UTF8Encoding]::new($false))
    ,$lines
}

function Get-ObservedArtifactOptions {
    param([Parameter(Mandatory)][string]$Directory, [Parameter(Mandatory)]$Report, [bool]$RestrictedRequested)
    $wlanFile = Join-Path $Directory 'wlan.txt'
    $batteryFile = Join-Path $Directory 'battery-report.xml'
    $sleepFile = Join-Path $Directory 'sleepstudy.html'
    $wlanPresent = [IO.File]::Exists($wlanFile)
    $batteryPresent = [IO.File]::Exists($batteryFile)
    $sleepPresent = [IO.File]::Exists($sleepFile)
    $wlanSucceeded = ((Get-ReportValue $Report 'network.wlan.status' 'UNKNOWN') -eq 'OK')
    $batterySucceeded = [bool](Get-ReportValue $Report 'battery.rawReportCommandSucceeded' $false)
    $sleepSucceeded = ((Get-ReportValue $Report 'exportStatus.sleepStudy.status' 'UNKNOWN') -eq 'OK')
    [ordered]@{
        restrictedArtifactsRequested = $RestrictedRequested
        activeWlanFilePresent = $wlanPresent; activeWlanCommandSucceeded = $wlanSucceeded; activeWlanCollected = ($wlanPresent -and $wlanSucceeded)
        rawBatteryReportFilePresent = $batteryPresent; rawBatteryReportCommandSucceeded = $batterySucceeded; rawBatteryReportRetained = ($batteryPresent -and $batterySucceeded)
        sleepStudyFilePresent = $sleepPresent; sleepStudyCommandSucceeded = $sleepSucceeded; sleepStudyCollected = ($sleepPresent -and $sleepSucceeded)
    }
}

function Write-EvidenceManifest {
    param([Parameter(Mandatory)][string]$Directory, [hashtable]$Metadata = @{})
    $mode = if ($Metadata.bundleMode) { $Metadata.bundleMode } else { $script:BundleMode }
    if ($mode -eq 'Restricted' -and [string]::IsNullOrWhiteSpace([string]$Metadata.authorizationReference)) {
        throw 'A Restricted evidence manifest requires a nonblank authorization reference.'
    }
    $files = @()
    foreach ($filePath in [IO.Directory]::EnumerateFiles([IO.Path]::GetFullPath($Directory), '*', [IO.SearchOption]::TopDirectoryOnly)) {
        $fileInfo = [IO.FileInfo]::new($filePath)
        if ($fileInfo.Name -ne 'evidence-manifest.json') { $files += $fileInfo }
    }
    $entries = foreach ($file in $files) {
        [ordered]@{ file = $file.Name; sha256 = Get-Sha256File -Path $file.FullName; bytes = $file.Length }
    }
    $manifest = [ordered]@{
        collectorVersion = $script:CollectorVersion
        collectorScriptSha256 = $Metadata.collectorScriptSha256
        collectorScriptSha256AtManifest = $Metadata.collectorScriptSha256AtManifest
        generatedAt = (Get-Date).ToString('o')
        bundleId = $Metadata.bundleId
        bundleMode = $mode
        handling = Get-BundleHandling -Mode $mode
        containsDirectIdentifiers = ($mode -eq 'Restricted')
        privacyBoundary = [ordered]@{
            identifierTreatment = if ($mode -eq 'Restricted') { 'authorized-direct' } else { 'per-bundle-salted-sha256' }
            pseudonymSaltRetained = $false
            classificationRuleFileRetained = [IO.File]::Exists((Join-Path $Directory 'agent-classification.rules.json'))
            manifestReviewRequiredBeforeSharing = ($mode -eq 'Safe')
        }
        authorizationReference = if ($mode -eq 'Restricted') { $Metadata.authorizationReference } else { $null }
        restrictions = if ($mode -eq 'Restricted') {
            @('Internal access controls required','Do not publish or attach outside the approved case')
        } else {
            @('Share only after manifest review confirms the Safe privacy boundary','Classification rules are referenced by version and SHA-256 but their raw content is not included','Escalate unexpected artifacts or collection errors to the privacy owner before release')
        }
        powershellVersion = $Metadata.powershellVersion
        osBuild = $Metadata.osBuild
        elevated = $Metadata.elevated
        classification = $Metadata.classification
        commandOptions = $Metadata.commandOptions
        collectionErrors = @($Metadata.collectionErrors)
        nativeStatuses = @($Metadata.nativeStatuses)
        integrityBoundary = [ordered]@{
            algorithm = 'SHA-256'
            purpose = 'integrity-checking'
            authenticity = 'not-provided; release through an approved signed channel'
            verifyBeforeUse = $true
        }
        files = @($entries)
    }
    $manifestJson = Microsoft.PowerShell.Utility\ConvertTo-Json -InputObject $manifest -Depth 10
    [IO.File]::WriteAllText([IO.Path]::Combine($Directory, 'evidence-manifest.json'), $manifestJson, [Text.UTF8Encoding]::new($false))
    [pscustomobject]$manifest
}

if ($LoadFunctionsOnly) { return }

# Execute collection in a new no-profile process with only the inbox module path.
# The parent does no collection and uses an absolute, signed system PowerShell host.
if (-not $InternalCleanProcess) {
    $cleanNonce = [guid]::NewGuid().ToString('N')
    $nonceVariable = 'LAPTOP_EVIDENCE_CLEAN_NONCE'
    [Environment]::SetEnvironmentVariable($nonceVariable, $cleanNonce, 'Process')
    $systemModulePath = [IO.Path]::Combine([Environment]::SystemDirectory, 'WindowsPowerShell', 'v1.0', 'Modules')
    $previousModulePath = [Environment]::GetEnvironmentVariable('PSModulePath', 'Process')
    [Environment]::SetEnvironmentVariable('PSModulePath', $systemModulePath, 'Process')
    $hostPath = [IO.Path]::Combine([Environment]::SystemDirectory, 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    if (-not [IO.File]::Exists($hostPath)) { throw 'Trusted Windows PowerShell host was not found.' }
    $hostSignature = Microsoft.PowerShell.Security\Get-AuthenticodeSignature -FilePath $hostPath -ErrorAction Stop
    if ([string]$hostSignature.Status -ne 'Valid') { throw 'Trusted Windows PowerShell host signature validation failed.' }
    $childArguments = @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$script:CollectorScriptPath,'-InternalCleanProcess','-InternalCleanNonce',$cleanNonce,'-OutputRoot',$OutputRoot,'-BundleMode',$BundleMode,'-AgentClassificationPath',$AgentClassificationPath)
    if ($IncludeIdentifiers) { $childArguments += '-IncludeIdentifiers' }
    foreach ($forwarded in @(
        [pscustomobject]@{ Name = '-AuthorizationReference'; Value = $AuthorizationReference }
        [pscustomobject]@{ Name = '-ApprovedAgentClassificationSha256'; Value = $ApprovedAgentClassificationSha256 }
        [pscustomobject]@{ Name = '-ApprovedPlatformPublisher'; Value = $ApprovedPlatformPublisher }
        [pscustomobject]@{ Name = '-ApprovedCmslModulePath'; Value = $ApprovedCmslModulePath }
        [pscustomobject]@{ Name = '-ApprovedCmslTreeSha256'; Value = $ApprovedCmslTreeSha256 }
    )) {
        if (-not [string]::IsNullOrWhiteSpace([string]$forwarded.Value)) { $childArguments += @($forwarded.Name, [string]$forwarded.Value) }
    }
    try {
        & $hostPath @childArguments
        $childExitCode = $LASTEXITCODE
    }
    finally {
        [Environment]::SetEnvironmentVariable('PSModulePath', $previousModulePath, 'Process')
        [Environment]::SetEnvironmentVariable($nonceVariable, $null, 'Process')
    }
    if ($childExitCode -ne 0) { throw "Clean collector process failed with exit code $childExitCode." }
    return
}
$expectedCleanNonce = [Environment]::GetEnvironmentVariable('LAPTOP_EVIDENCE_CLEAN_NONCE', 'Process')
if ([string]::IsNullOrWhiteSpace($expectedCleanNonce) -or $InternalCleanNonce -ne $expectedCleanNonce) { throw 'Internal clean-process attestation failed.' }
[Environment]::SetEnvironmentVariable('LAPTOP_EVIDENCE_CLEAN_NONCE', $null, 'Process')
[Environment]::SetEnvironmentVariable('PSModulePath', [IO.Path]::Combine([Environment]::SystemDirectory, 'WindowsPowerShell', 'v1.0', 'Modules'), 'Process')

# ------------------------------- setup ---------------------------------------

$collectorScriptHashAtStart = if ($script:CollectorScriptPath -and [IO.File]::Exists($script:CollectorScriptPath)) { Get-Sha256File -Path $script:CollectorScriptPath } else { $null }

$resolvedMode = Resolve-BundleMode -RequestedMode $BundleMode -IdentifiersSwitch ([bool]$IncludeIdentifiers) -Authorization $AuthorizationReference
$script:BundleMode = $resolvedMode.Mode
$script:IncludeIds = $resolvedMode.IncludesIdentifiers
$artifactPlan = Get-CollectionPlan -Mode $script:BundleMode
$bundleId = [guid]::NewGuid().ToString('N')
$dir = Join-Path $OutputRoot "eval-capture-$bundleId"
New-Item -ItemType Directory -Path $dir -ErrorAction Stop | Out-Null

try { $elevated = Test-Elevation } catch { $elevated = $null; Add-CollectionError -Section 'setup' -Code 'ELEVATION_UNKNOWN' -Message $_.Exception.Message }
$platformPublisherSource = if ([string]::IsNullOrWhiteSpace($ApprovedPlatformPublisher)) { 'os-manufacturer' } else { 'approved-override' }
$platformPublisherError = $null
if (-not [string]::IsNullOrWhiteSpace($ApprovedPlatformPublisher)) {
    $script:PlatformPublisher = $ApprovedPlatformPublisher.Trim()
} else {
    try { $script:PlatformPublisher = ([string](Get-CimInstance Win32_OperatingSystem -ErrorAction Stop).Manufacturer).Trim() }
    catch { $platformPublisherError = $_.Exception.Message }
}
if ([string]::IsNullOrWhiteSpace($script:PlatformPublisher)) {
    $publisherMessage = if ($platformPublisherError) { $platformPublisherError } else { 'Platform publisher could not be derived or approved.' }
    Add-CollectionError -Section 'setup.platformPublisher' -Code 'PLATFORM_PUBLISHER_UNKNOWN' -Message $publisherMessage -Incomplete $true -ForcesInconclusive $true
}
$script:PlatformPublisherAliases = @($script:PlatformPublisher)
if ($platformPublisherSource -eq 'os-manufacturer') {
    try {
        $platformHostPath = [IO.Path]::Combine([Environment]::SystemDirectory, 'WindowsPowerShell', 'v1.0', 'powershell.exe')
        $platformHostSignature = Microsoft.PowerShell.Security\Get-AuthenticodeSignature -FilePath $platformHostPath -ErrorAction Stop
        if ([string]$platformHostSignature.Status -eq 'Valid' -and $platformHostSignature.SignerCertificate) { $script:PlatformPublisherAliases += [string]$platformHostSignature.SignerCertificate.Subject }
    }
    catch { Add-CollectionError -Section 'setup.platformPublisher' -Code 'PLATFORM_SIGNER_ALIAS_UNKNOWN' -Message $_.Exception.Message -Incomplete $true -ForcesInconclusive $false }
}
$classification = Get-AgentClassification -Path $AgentClassificationPath
$classificationApproval = Test-AgentClassificationApproval -Classification $classification -ApprovedSha256 $ApprovedAgentClassificationSha256
if ($classification.Status -ne 'valid') {
    Add-CollectionError -Section 'agentClassification' -Code ('CLASSIFICATION_' + $classification.Status.ToUpperInvariant()) -Message ($classification.Errors -join ' ')
} elseif (@($classification.Rules).Count -eq 0) {
    Add-CollectionError -Section 'agentClassification' -Code 'CLASSIFICATION_EMPTY' -Message 'Classification envelope is valid but contains no rules.' -Incomplete $true -ForcesInconclusive $true
} elseif ($classificationApproval.status -ne 'APPROVED') {
    Add-CollectionError -Section 'agentClassification' -Code ('CLASSIFICATION_' + $classificationApproval.status) -Message 'Nonempty classification rules require a matching preapproved SHA-256 digest.' -Incomplete $true -ForcesInconclusive $true
}
try { $classificationEvidence = Copy-AgentClassificationEvidence -Classification $classification -Directory $dir -RetainRulesFile $artifactPlan.retainClassificationRules }
catch {
    Add-CollectionError -Section 'agentClassification' -Code 'CLASSIFICATION_COPY_FAILED' -Message $_.Exception.Message
    $classificationEvidence = [pscustomobject]@{ status = 'invalid'; file = $null; sha256 = $classification.Sha256; schemaVersion = $classification.SchemaVersion; rulesVersion = $classification.RulesVersion }
}

$captureEnvelope = New-CaptureEnvelope -BundleId $bundleId -Mode $script:BundleMode -ComputerName $env:COMPUTERNAME -Elevated $elevated
foreach ($entry in $captureEnvelope.GetEnumerator()) { $report[$entry.Key] = $entry.Value }
$report['platformPublisher'] = if ($script:IncludeIds) { $script:PlatformPublisher } else { $null }
$report['platformPublisherPseudonym'] = if (-not $script:IncludeIds) { Protect-SensitiveText ([string]$script:PlatformPublisher) } else { $null }
$report['platformPublisherSource'] = $platformPublisherSource
$report['agentClassification'] = [ordered]@{
    status = $classificationEvidence.status; sourceFile = $classificationEvidence.file
    schemaVersion = $classificationEvidence.schemaVersion; rulesVersion = $classificationEvidence.rulesVersion
    sha256 = $classificationEvidence.sha256
    approvalStatus = $classificationApproval.status
    validationErrors = if ($script:IncludeIds) { @($classification.Errors) } else { @($classification.Errors | ForEach-Object { Protect-ErrorMessage ([string]$_) }) }
}
$activeClassificationRules = @(Get-ActiveClassificationRules -Classification $classification -ClassificationEvidence $classificationEvidence -ClassificationApproval $classificationApproval)

# --------------------------- identity and firmware ---------------------------

Add-Section 'identity' {
    $csp = Get-CimInstance Win32_ComputerSystemProduct
    $sys = Get-CimInstance -Namespace root\wmi -ClassName MS_SystemInformation
    [ordered]@{
        productName  = $sys.SystemProductName
        systemSku    = $sys.SystemSKU
        systemFamily = $sys.SystemFamily
        serialNumber = Protect-Id $csp.IdentifyingNumber
        baseBoard    = (Get-CimInstance Win32_BaseBoard).Product
    }
}

Add-Section 'bios' {
    $b = Get-CimInstance Win32_BIOS
    [ordered]@{ version = $b.SMBIOSBIOSVersion; releaseDate = $b.ReleaseDate; vendor = $b.Manufacturer }
}

# ------------------------------ core hardware --------------------------------

Add-Section 'cpu' {
    $c = Get-CimInstance Win32_Processor
    [ordered]@{
        name = $c.Name; cores = $c.NumberOfCores; logicalProcessors = $c.NumberOfLogicalProcessors
        maxClockMHz = $c.MaxClockSpeed; l2CacheKB = $c.L2CacheSize; l3CacheKB = $c.L3CacheSize
        virtualization = $c.VirtualizationFirmwareEnabled
    }
}

Add-Section 'memory' {
    $ffMap = @{ 8 = 'DIMM'; 12 = 'SODIMM' }
    $dimms = Get-CimInstance Win32_PhysicalMemory | ForEach-Object {
        $ff = [int]$_.FormFactor
        [ordered]@{
            slot = $_.DeviceLocator
            capacityGB = [math]::Round($_.Capacity / 1GB, 0)
            speedMTs = $_.Speed; configuredMTs = $_.ConfiguredClockSpeed
            manufacturer = $_.Manufacturer
            partNumber = "$($_.PartNumber)".Trim()
            formFactor = if ($ffMap.ContainsKey($ff)) { $ffMap[$ff] } else { $ff }
        }
    }
    [ordered]@{
        totalSlots = (Get-CimInstance Win32_PhysicalMemoryArray).MemoryDevices
        populated  = @($dimms).Count
        modules    = @($dimms)
    }
}

Add-Section 'storage' {
    @(Get-PhysicalDisk | ForEach-Object {
        $rel = $null
        try {
            $r = $_ | Get-StorageReliabilityCounter -ErrorAction Stop
            $rel = [ordered]@{
                temperatureC = $r.Temperature; wearPct = $r.Wear
                readErrorsTotal = $r.ReadErrorsTotal; writeErrorsTotal = $r.WriteErrorsTotal
                powerOnHours = $r.PowerOnHours
            }
        } catch {
            $message = Protect-ErrorMessage $_.Exception.Message
            Add-CollectionError -Section 'storage.reliability' -Code 'COUNTERS_UNSUPPORTED' -Message $message -Incomplete $true -ForcesInconclusive $false
            $rel = [ordered]@{ status = 'UNSUPPORTED'; limitation = $message }
        }
        [ordered]@{
            model = $_.FriendlyName; firmware = $_.FirmwareVersion
            busType = "$($_.BusType)"; mediaType = "$($_.MediaType)"
            sizeGB = [math]::Round($_.Size / 1GB, 0); health = "$($_.HealthStatus)"
            serial = Protect-Id ("$($_.SerialNumber)".Trim())
            reliability = $rel
        }
    })
}

Add-Section 'gpu' {
    @(Get-CimInstance Win32_VideoController | ForEach-Object {
        [ordered]@{ name = $_.Name; driverVersion = $_.DriverVersion; driverDate = $_.DriverDate }
    })
}

Add-Section 'npu' {
    $enumerationLimitations = @()
    try { $devs = @(Get-PnpDevice -Class ComputeAccelerator -ErrorAction Stop) }
    catch {
        $message = Protect-ErrorMessage $_.Exception.Message; $devs = @(); $enumerationLimitations += $message
        Add-CollectionError -Section 'npu.primaryEnumeration' -Code 'PNP_CLASS_ENUMERATION_FAILED' -Message $message -Incomplete $true -ForcesInconclusive $false
    }
    if ($devs.Count -eq 0) {
        try { $devs = @(Get-PnpDevice -ErrorAction Stop | Where-Object FriendlyName -match 'NPU') }
        catch { throw "NPU primary and fallback enumeration failed. $(Protect-ErrorMessage $_.Exception.Message)" }
    }
    if ($devs.Count -eq 0) { return [ordered]@{ status = 'NOT_PRESENT'; devices = @(); limitations = @($enumerationLimitations) } }
    $deviceRecords = @($devs | ForEach-Object {
        $id = $_.InstanceId; $propertyLimitations = @(); $driverVersion = $null; $driverDate = $null
        try { $driverVersion = (Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_DriverVersion -ErrorAction Stop).Data }
        catch {
            $propertyLimitations += 'Driver version property unavailable.'
            Add-CollectionError -Section 'npu.driverVersion' -Code 'PNP_PROPERTY_UNKNOWN' -Message 'NPU driver version property unavailable.' -Incomplete $true -ForcesInconclusive $true
        }
        try { $driverDate = (Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_DriverDate -ErrorAction Stop).Data }
        catch {
            $propertyLimitations += 'Driver date property unavailable.'
            Add-CollectionError -Section 'npu.driverDate' -Code 'PNP_PROPERTY_UNKNOWN' -Message 'NPU driver date property unavailable.' -Incomplete $true -ForcesInconclusive $true
        }
        [ordered]@{
            name = if ($script:IncludeIds) { $_.FriendlyName } else { $null }
            namePseudonym = if ($script:IncludeIds) { $null } else { Protect-SensitiveText ([string]$_.FriendlyName) }
            state = "$($_.Status)"; instanceId = Protect-Id ([string]$id)
            driverVersion = $driverVersion; driverDate = $driverDate
            metadataStatus = if ($propertyLimitations.Count -eq 0) { 'OK' } else { 'PARTIAL' }
            limitations = @($propertyLimitations)
        }
    })
    [ordered]@{
        status = if ($enumerationLimitations.Count -gt 0 -or @($deviceRecords | Where-Object metadataStatus -ne 'OK').Count -gt 0) { 'PARTIAL' } else { 'OK' }
        devices = $deviceRecords; limitations = @($enumerationLimitations)
    }
}

Add-Section 'network' {
    $wlanStatus = [ordered]@{ status = 'NOT_COLLECTED'; reason = 'Safe bundles exclude active WLAN details.'; file = $null }
    if ($artifactPlan.activeWlanDetails) {
        $wlan = Invoke-Native -Name 'wlanInterfaces' -Section 'network.wlan' -FailureForcesInconclusive $false -FilePath 'netsh.exe' -ArgumentList 'wlan','show','interfaces' -AllowFailure
        if ($wlan.Success) {
            $wlan.Output | Out-File -LiteralPath (Join-Path $dir 'wlan.txt') -Encoding utf8
            $wlanStatus = [ordered]@{ status = 'OK'; reason = $null; file = 'wlan.txt' }
        } else {
            $wlanStatus = [ordered]@{ status = 'UNKNOWN'; reason = $wlan.Error; file = $null }
        }
    }
    $adapters = @(Get-NetAdapter -ErrorAction Stop | ForEach-Object {
        [ordered]@{
            name = if ($script:IncludeIds) { $_.Name } else { Protect-SensitiveText ([string]$_.Name) }
            description = if ($script:IncludeIds) { $_.InterfaceDescription } else { $null }
            descriptionPseudonym = if ($script:IncludeIds) { $null } else { Protect-SensitiveText ([string]$_.InterfaceDescription) }
            mediaType = "$($_.PhysicalMediaType)"
            driver = $_.DriverVersionString; driverDate = $_.DriverDate
            status = "$($_.Status)"
        }
    })
    [ordered]@{ adapters = $adapters; wlan = $wlanStatus }
}

Add-Section 'displayPanels' {
    @(Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID -ErrorAction Stop | ForEach-Object {
        [ordered]@{
            manufacturer = -join ($_.ManufacturerName | Where-Object { $_ } | ForEach-Object { [char]$_ })
            productCode  = -join ($_.ProductCodeID    | Where-Object { $_ } | ForEach-Object { [char]$_ })
        }
    })
}

Add-Section 'battery' {
    $cim = Get-CimInstance Win32_Battery -ErrorAction Stop
    if (-not $cim) { return [ordered]@{ present = $false } }
    $batteryTempDirectory = $null
    $xmlName = if ($artifactPlan.retainRawBatteryReport) { 'battery-report.xml' } else { 'battery-report-' + [guid]::NewGuid().ToString('N') + '.tmp.xml' }
    if ($artifactPlan.retainRawBatteryReport) { $xmlPath = Join-Path $dir $xmlName }
    else { $batteryTempDirectory = New-TrustedTemporaryDirectory -Purpose 'battery'; $xmlPath = [IO.Path]::Combine($batteryTempDirectory, $xmlName) }
    $structured = $null
    $batteryCommandSucceeded = $false
    try {
        $batteryCommand = Invoke-Native -Name 'batteryReport' -Section 'battery.structured' -FilePath 'powercfg.exe' -ArgumentList '/batteryreport','/xml','/output', $xmlPath -AllowFailure
        $batteryCommandSucceeded = $batteryCommand.Success
        if (-not $batteryCommand.Success) { throw $batteryCommand.Error }
        [xml]$x = Get-Content $xmlPath -Raw
        $design = $x.GetElementsByTagName('DesignCapacity');     $full = $x.GetElementsByTagName('FullChargeCapacity')
        $cycles = $x.GetElementsByTagName('CycleCount')
        $structured = [ordered]@{
            designCapacitymWh     = if ($design.Count -gt 0) { [int]$design.Item(0).InnerText } else { $null }
            fullChargeCapacitymWh = if ($full.Count   -gt 0) { [int]$full.Item(0).InnerText }   else { $null }
            cycleCount            = if ($cycles.Count -gt 0) { [int]$cycles.Item(0).InnerText } else { $null }
        }
        if ($structured.designCapacitymWh -and $structured.fullChargeCapacitymWh) {
            $structured.healthPct = [math]::Round(100.0 * $structured.fullChargeCapacitymWh / $structured.designCapacitymWh, 1)
        }
    } catch {
        $message = Protect-ErrorMessage $_.Exception.Message
        Add-CollectionError -Section 'battery' -Code 'BATTERY_REPORT_FAILED' -Message $message
        $structured = [ordered]@{ status = 'UNKNOWN'; error = $message }
    } finally {
        if ($batteryTempDirectory) {
            try { if ([IO.Directory]::Exists($batteryTempDirectory)) { [IO.Directory]::Delete($batteryTempDirectory, $true) } }
            catch { Add-CollectionError -Section 'battery' -Code 'TEMPFILE_DELETE_FAILED' -Message 'Private temporary battery directory could not be deleted.' -Incomplete $true -ForcesInconclusive $true }
        }
    }
    [ordered]@{
        present = $true
        name = if ($script:IncludeIds) { $cim.Name } else { $null }
        namePseudonym = if ($script:IncludeIds) { $null } else { Protect-SensitiveText ([string]$cim.Name) }
        chemistry = $cim.Chemistry; structured = $structured
        rawReportCommandSucceeded = $batteryCommandSucceeded
        rawReport = if ($artifactPlan.retainRawBatteryReport -and (Test-Path -LiteralPath $xmlPath)) { 'battery-report.xml' } else { $null }
    }
}

# ---------------------------- platform security ------------------------------

Add-Section 'tpm' {
    $t = Get-Tpm  # elevation required
    [ordered]@{ present = $t.TpmPresent; ready = $t.TpmReady; manufacturer = $t.ManufacturerIdTxt; manufacturerVer = $t.ManufacturerVersion }
}

Add-Section 'secureBoot' { [ordered]@{ enabled = (Confirm-SecureBootUEFI) } }  # elevation required

Add-Section 'bitlocker' {
    @(Get-BitLockerVolume -ErrorAction Stop | ForEach-Object {  # elevation required
        $mount = Get-SensitiveLocationRecord -Location ([string]$_.MountPoint)
        [ordered]@{
            mountPoint = $mount.location; mountPointPseudonym = $mount.locationPseudonym
            protection = "$($_.ProtectionStatus)"; encryptionMethod = "$($_.EncryptionMethod)"; encryptedPct = $_.EncryptionPercentage
        }
    })
}

Add-Section 'vbs' {
    $dg = Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -ClassName Win32_DeviceGuard
    [ordered]@{
        vbsStatus = $dg.VirtualizationBasedSecurityStatus   # 0 off, 1 enabled, 2 running
        securityServicesRunning = @($dg.SecurityServicesRunning)
    }
}

# ------------------------------ OS and baseline ------------------------------

Add-Section 'os' {
    $o  = Get-CimInstance Win32_OperatingSystem
    $cv = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    [ordered]@{
        caption = $o.Caption; displayVersion = $cv.DisplayVersion
        build = "$($cv.CurrentBuild).$($cv.UBR)"
        installDate = $o.InstallDate; lastBoot = $o.LastBootUpTime
    }
}

Add-Section 'baselineLoad' {
    $o = Get-CimInstance Win32_OperatingSystem
    [ordered]@{
        uptimeHours  = [math]::Round(((Get-Date) - $o.LastBootUpTime).TotalHours, 1)
        processCount = (Get-Process).Count
        memInUseGB   = [math]::Round(($o.TotalVisibleMemorySize - $o.FreePhysicalMemory) / 1MB, 1)
        memTotalGB   = [math]::Round($o.TotalVisibleMemorySize / 1MB, 1)
        note         = 'Point-in-time only. The corporate floor is a Phase 3 settled-state measurement (45-60 min stabilization, fixed window).'
        topProcessesByWS = @(Get-Process -ErrorAction Stop | Sort-Object WorkingSet64 -Descending | Select-Object -First 15 | ForEach-Object {
            [ordered]@{
                name = if ($script:IncludeIds) { $_.Name } else { $null }
                processPseudonym = if ($script:IncludeIds) { $null } else { Protect-SensitiveText ([string]$_.Name) }
                id = if ($script:IncludeIds) { $_.Id } else { $null }
                wsMB = [math]::Round($_.WorkingSet64 / 1MB, 0)
            }
        })
    }
}

Add-Section 'problemDevices' {
    $pnp = Invoke-SubCapture -Name 'problemDevices.pnp' -Body {
        @(Get-PnpDevice -ErrorAction Stop | Where-Object { $_.Status -ne 'OK' -and $_.Present } | Select-Object -First 25 | ForEach-Object {
            [ordered]@{
                friendlyName = if ($script:IncludeIds) { $_.FriendlyName } else { $null }
                friendlyNamePseudonym = if ($script:IncludeIds) { $null } else { Protect-SensitiveText ([string]$_.FriendlyName) }
                class = $_.Class; status = [string]$_.Status; instanceId = Protect-Id ([string]$_.InstanceId)
            }
        })
    }
    $whea = Get-WheaEventEvidence -Query {
        @(Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-WHEA-Logger'; StartTime = (Get-Date).AddDays(-7) } -MaxEvents 100 -ErrorAction Stop)
    }
    [ordered]@{
        problemDevices = @($pnp.data); problemDevicesStatus = $pnp.status
        wheaEventsLast7Days = $whea.count
        eventStatus = $whea.status; errors = @($pnp.error, $whea.error | Where-Object { $_ })
    }
}

# ------------------------------ agent inventory ------------------------------

Add-Section 'agentInventory' {
    $servicesCapture = Invoke-SubCapture -Name 'agentInventory.services' -Body {
        @(Get-CimInstance Win32_Service -ErrorAction Stop | Where-Object State -eq 'Running' | ForEach-Object {
            $record = New-AgentObservation -Kind 'service' -Name $_.Name -DisplayName $_.DisplayName -State ([string]$_.State) -CommandLine $_.PathName -Rules $activeClassificationRules
            $record['startMode'] = [string]$_.StartMode
            $record
        })
    }
    $tasksCapture = Invoke-SubCapture -Name 'agentInventory.scheduledTasks' -Body {
        @(Get-ScheduledTask -ErrorAction Stop | Where-Object State -ne 'Disabled' | ForEach-Object {
            $task = $_
            $actions = @($task.Actions)
            if ($actions.Count -eq 0) { $actions = @([pscustomobject]@{ Execute = $null; Arguments = $null }) }
            $index = 0
            foreach ($action in $actions) {
                $commandLine = (([string]$action.Execute) + ' ' + ([string]$action.Arguments)).Trim()
                $record = New-AgentObservation -Kind 'scheduledTask' -Name $task.TaskName -DisplayName $task.TaskName -State ([string]$task.State) -CommandLine $commandLine -Rules $activeClassificationRules
                $taskIdentity = ([string]$task.TaskPath) + ([string]$task.TaskName)
                $record['name'] = if ($script:IncludeIds) { $task.TaskName } else { $null }
                $record['displayName'] = $null
                $record['taskPseudonym'] = Protect-SensitiveText $taskIdentity
                $record['taskPath'] = if ($script:IncludeIds) { $task.TaskPath } else { $null }
                $record['author'] = Protect-SensitiveText ([string]$task.Author)
                $record['actionIndex'] = $index
                $index++
                $record
            }
        })
    }
    $driversCapture = Invoke-SubCapture -Name 'agentInventory.kernelDrivers' -Body {
        @(Get-CimInstance Win32_SystemDriver -ErrorAction Stop | Where-Object State -eq 'Running' | ForEach-Object {
            $record = New-AgentObservation -Kind 'kernelDriver' -Name $_.Name -DisplayName $_.DisplayName -State ([string]$_.State) -CommandLine $_.PathName -Rules $activeClassificationRules
            $record['startMode'] = [string]$_.StartMode
            $record['serviceType'] = [string]$_.ServiceType
            $record
        })
    }
    $minifiltersCapture = Invoke-SubCapture -Name 'agentInventory.minifilters' -Body {
        $filterCommand = Invoke-Native -Name 'minifilterInventory' -Section 'agentInventory.minifilters' -FilePath 'fltmc.exe' -ArgumentList 'filters' -AllowFailure
        if (-not $filterCommand.Success) { throw $filterCommand.Error }
        @($filterCommand.Output | ForEach-Object {
            $line = [string]$_
            if ($line -match '^\s*-+' -or $line -match '(?i)Filter\s+Name') { return }
            $columns = @($line -split '\s+' | Where-Object { $_ })
            if ($columns.Count -lt 2) { return }
            $filterName = $columns[0]
            $imagePath = $null; $startMode = $null; $registryStatus = 'OK'; $registryLimitation = $null
            try {
                $serviceKey = Get-ItemProperty -LiteralPath (Join-Path 'HKLM:\SYSTEM\CurrentControlSet\Services' $filterName) -ErrorAction Stop
                $imagePath = [string]$serviceKey.ImagePath; $startMode = [string]$serviceKey.Start
            } catch {
                $registryStatus = 'UNKNOWN'; $registryLimitation = 'Registry metadata for the loaded minifilter was unavailable.'
                Add-CollectionError -Section 'agentInventory.minifilters.metadata' -Code 'REGISTRY_METADATA_UNKNOWN' -Message $registryLimitation -Incomplete $true -ForcesInconclusive $true
            }
            $record = New-AgentObservation -Kind 'minifilter' -Name $filterName -DisplayName $filterName -State 'Loaded' -CommandLine $imagePath -Rules $activeClassificationRules
            $record['instances'] = $columns[1]
            $record['altitude'] = if ($columns.Count -gt 2) { $columns[2] } else { $null }
            $record['startMode'] = $startMode
            $record['registryMetadataStatus'] = $registryStatus
            $record['registryLimitation'] = $registryLimitation
            $record
        })
    }
    $subcaptures = @($servicesCapture, $tasksCapture, $driversCapture, $minifiltersCapture)
    $allAgentRecords = @()
    $allAgentRecords += @($servicesCapture.data)
    $allAgentRecords += @($tasksCapture.data)
    $allAgentRecords += @($driversCapture.data)
    $allAgentRecords += @($minifiltersCapture.data)
    $recordPartials = @($allAgentRecords | Where-Object {
        $_.metadataStatus -ne 'OK' -or ($null -ne $_.registryMetadataStatus -and $_.registryMetadataStatus -ne 'OK')
    })
    [ordered]@{
        status = if (@($subcaptures | Where-Object status -ne 'OK').Count -gt 0 -or $recordPartials.Count -gt 0) { 'PARTIAL' } else { 'OK' }
        classification = $report.agentClassification
        collectionTime = (Get-Date).ToString('o')
        services = @($servicesCapture.data)
        scheduledTasks = @($tasksCapture.data)
        kernelDrivers = @($driversCapture.data)
        minifilters = @($minifiltersCapture.data)
        subcollectionStatus = [ordered]@{
            services = $servicesCapture.status; scheduledTasks = $tasksCapture.status
            kernelDrivers = $driversCapture.status; minifilters = $minifiltersCapture.status
        }
        errors = @($subcaptures.error | Where-Object { $_ })
    }
}

# ------------------------------ HP CMSL (raw) --------------------------------

Add-Section 'hpCmsl' {
    $cmslBinding = Test-ApprovedCmslModuleBinding -ModulePath $ApprovedCmslModulePath -ExpectedTreeSha256 $ApprovedCmslTreeSha256
    if ($cmslBinding.status -eq 'NOT_PROVIDED') {
        $discoveredCmsl = @(Microsoft.PowerShell.Core\Get-Module -ListAvailable -Name HP.ClientManagement -ErrorAction Stop)
        $status = if ($discoveredCmsl.Count -gt 0) { 'APPROVAL_REQUIRED' } else { 'NOT_AVAILABLE' }
        $code = if ($discoveredCmsl.Count -gt 0) { 'CMSL_BINDING_REQUIRED' } else { 'CMSL_NOT_AVAILABLE' }
        $note = if ($discoveredCmsl.Count -gt 0) { 'CMSL was present but was not executed because an approved exact path and module-tree SHA-256 were not supplied.' } else { 'CMSL module was not installed at collection time.' }
        Add-CollectionError -Section 'hpCmsl' -Code $code -Message $note -Incomplete $true -ForcesInconclusive $true
        return [ordered]@{ status = $status; note = $note; binding = [ordered]@{ provided = $false; treeSha256 = $null } }
    }
    if ($cmslBinding.status -ne 'VALID') {
        Add-CollectionError -Section 'hpCmsl' -Code 'CMSL_BINDING_INVALID' -Message $cmslBinding.reason -Incomplete $true -ForcesInconclusive $true
        return [ordered]@{ status = 'NOT_TRUSTED'; note = $cmslBinding.reason; binding = [ordered]@{ provided = $true; treeSha256 = $null } }
    }
    $cmslSnapshot = New-PrivateModuleSnapshot -Binding $cmslBinding
    $approvedCmsl = $null
    try {
        Microsoft.PowerShell.Core\Import-Module -Name $cmslSnapshot.entryPath -Force -ErrorAction Stop
        foreach ($moduleCandidate in @(Microsoft.PowerShell.Core\Get-Module -Name HP.ClientManagement)) {
            if (-not [string]::IsNullOrWhiteSpace([string]$moduleCandidate.ModuleBase) -and [IO.Path]::GetFullPath($moduleCandidate.ModuleBase).TrimEnd([IO.Path]::DirectorySeparatorChar) -eq $cmslSnapshot.root) {
                $approvedCmsl = $moduleCandidate
                break
            }
        }
        if ($null -eq $approvedCmsl) { throw 'The approved CMSL module was not loaded from the private verified snapshot.' }
        $out = [ordered]@{
            status = 'OK'
            moduleVersion = [string]$approvedCmsl.Version
            binding = [ordered]@{ entryFile = [IO.Path]::GetFileName($cmslBinding.entryPath); treeSha256 = $cmslSnapshot.treeSha256; privateSnapshot = $true }
            sysId = & $approvedCmsl { Get-HPDeviceProductID }
        }
        try { $out.installedBios = & $approvedCmsl { Get-HPBIOSVersion } } catch {
            $message = Protect-ErrorMessage $_.Exception.Message; Add-CollectionError -Section 'hpCmsl.installedBios' -Code 'CMSL_COMMAND_FAILED' -Message $message
            $out.installedBios = [ordered]@{ status = 'UNKNOWN'; error = $message }
        }
        try {
            $latest = & $approvedCmsl { Get-HPBIOSUpdates -Latest -ErrorAction Stop }
            [IO.File]::WriteAllText((Join-Path $dir 'cmsl-bios-latest.clixml'), [Management.Automation.PSSerializer]::Serialize($latest, 100), [Text.UTF8Encoding]::new($false))
            $latestJson = Microsoft.PowerShell.Utility\ConvertTo-Json -InputObject $latest -Depth 20
            [IO.File]::WriteAllText((Join-Path $dir 'cmsl-bios-latest.json'), $latestJson, [Text.UTF8Encoding]::new($false))
            $out.latestBios = [ordered]@{ status = 'OK'; rawCliXml = 'cmsl-bios-latest.clixml'; jsonView = 'cmsl-bios-latest.json' }
        } catch {
            $message = Protect-ErrorMessage $_.Exception.Message; Add-CollectionError -Section 'hpCmsl.latestBios' -Code 'CMSL_COMMAND_FAILED' -Message $message
            $out.latestBios = [ordered]@{ status = 'UNKNOWN'; error = $message }
        }
        try {
            $sp = & $approvedCmsl { Get-SoftpaqList -ErrorAction Stop }
            [IO.File]::WriteAllText((Join-Path $dir 'cmsl-softpaq-list.clixml'), [Management.Automation.PSSerializer]::Serialize($sp, 100), [Text.UTF8Encoding]::new($false))
            $spJson = Microsoft.PowerShell.Utility\ConvertTo-Json -InputObject $sp -Depth 20
            [IO.File]::WriteAllText((Join-Path $dir 'cmsl-softpaq-list.json'), $spJson, [Text.UTF8Encoding]::new($false))
            $out.softpaqList = [ordered]@{ status = 'OK'; rawCliXml = 'cmsl-softpaq-list.clixml'; jsonView = 'cmsl-softpaq-list.json'; count = @($sp).Count }
        } catch {
            $message = Protect-ErrorMessage $_.Exception.Message; Add-CollectionError -Section 'hpCmsl.softpaqList' -Code 'CMSL_COMMAND_FAILED' -Message $message
            $out.softpaqList = [ordered]@{ status = 'UNKNOWN'; error = $message }
        }
        $out
    }
    finally {
        if ($approvedCmsl) {
            try { Microsoft.PowerShell.Core\Remove-Module -ModuleInfo $approvedCmsl -Force -ErrorAction Stop }
            catch { Add-CollectionError -Section 'hpCmsl.cleanup' -Code 'CMSL_UNLOAD_FAILED' -Message $_.Exception.Message -Incomplete $true -ForcesInconclusive $true }
        }
        try { if ([IO.Directory]::Exists($cmslSnapshot.root)) { [IO.Directory]::Delete($cmslSnapshot.root, $true) } }
        catch { Add-CollectionError -Section 'hpCmsl.cleanup' -Code 'CMSL_SNAPSHOT_DELETE_FAILED' -Message $_.Exception.Message -Incomplete $true -ForcesInconclusive $true }
    }
}

# -------------------------------- exports ------------------------------------

Write-Host 'Exporting full driver list (slow)...'
$exportStatus = [ordered]@{}
try {
    Get-CimInstance Win32_PnPSignedDriver -ErrorAction Stop | ForEach-Object {
        $publisherOrigin = Resolve-PublisherOrigin -Provider ([string]$_.DriverProviderName) -Signer ([string]$_.Signer) -SignatureTrusted ([bool]$_.IsSigned)
        [pscustomobject][ordered]@{
            DeviceName = if ($script:IncludeIds) { $_.DeviceName } else { $null }
            DevicePseudonym = if ($script:IncludeIds) { $null } else { Protect-SensitiveText ([string]$_.DeviceName) }
            DeviceClass = $_.DeviceClass; DriverVersion = $_.DriverVersion; DriverDate = $_.DriverDate
            Manufacturer = if ($script:IncludeIds) { $_.Manufacturer } else { $null }
            ManufacturerPseudonym = if ($script:IncludeIds) { $null } else { Protect-SensitiveText ([string]$_.Manufacturer) }
            DriverProviderName = if ($script:IncludeIds) { $_.DriverProviderName } else { $null }
            ProviderPseudonym = if ($script:IncludeIds) { $null } else { Protect-SensitiveText ([string]$_.DriverProviderName) }
            IsSigned = $_.IsSigned
            Signer = if ($script:IncludeIds) { $_.Signer } else { $null }
            SignerPseudonym = if ($script:IncludeIds) { $null } else { Protect-SensitiveText ([string]$_.Signer) }
            PublisherOrigin = $publisherOrigin
        }
    } |
        Export-Csv -LiteralPath (Join-Path $dir 'full-drivers.csv') -NoTypeInformation -Encoding UTF8
    $exportStatus.fullDrivers = [ordered]@{ status = 'OK'; file = 'full-drivers.csv' }
} catch {
    $message = Protect-ErrorMessage $_.Exception.Message; Add-CollectionError -Section 'exports.fullDrivers' -Code 'DRIVER_EXPORT_FAILED' -Message $message
    $exportStatus.fullDrivers = [ordered]@{ status = 'UNKNOWN'; error = $message }
}

$standby = Invoke-Native -Name 'standbyCapability' -Section 'exports.standbyCapability' -FilePath 'powercfg.exe' -ArgumentList '/a' -AllowFailure
if ($standby.Success) {
    $standby.Output | Out-File -LiteralPath (Join-Path $dir 'standby-capability.txt') -Encoding utf8
    $exportStatus.standbyCapability = [ordered]@{ status = 'OK'; file = 'standby-capability.txt' }
} else {
    $exportStatus.standbyCapability = [ordered]@{ status = 'UNKNOWN'; error = $standby.Error }
}

if ($artifactPlan.sleepStudy) {
    $sleep = Invoke-Native -Name 'sleepStudy' -Section 'exports.sleepStudy' -FailureForcesInconclusive $false -FilePath 'powercfg.exe' -ArgumentList '/sleepstudy','/output',(Join-Path $dir 'sleepstudy.html') -AllowFailure
    if ($sleep.Success) { $exportStatus.sleepStudy = [ordered]@{ status = 'OK'; file = 'sleepstudy.html' } }
    else {
        $exportStatus.sleepStudy = [ordered]@{ status = 'UNKNOWN'; error = $sleep.Error }
    }
} else {
    $exportStatus.sleepStudy = [ordered]@{ status = 'NOT_COLLECTED'; reason = 'Safe bundles exclude sleepstudy user/activity history.' }
}

$report['exportStatus'] = $exportStatus
$collectorScriptHashAtManifest = if ($script:CollectorScriptPath -and [IO.File]::Exists($script:CollectorScriptPath)) { Get-Sha256File -Path $script:CollectorScriptPath } else { $null }
if ($collectorScriptHashAtStart -ne $collectorScriptHashAtManifest) {
    Add-CollectionError -Section 'provenance.collector' -Code 'COLLECTOR_CHANGED_DURING_RUN' -Message 'Collector script hash changed between startup and manifest generation.' -Incomplete $true -ForcesInconclusive $true
}
$report['nativeStatuses'] = @($script:NativeStatuses)
$report['collectionErrors'] = @($script:CollectionErrors)
try { $summaryLines = Write-CollectorSummary -Report $report -Path (Join-Path $dir 'summary.txt') }
catch { Add-CollectionError -Section 'exports.summary' -Code 'SUMMARY_FAILED' -Message $_.Exception.Message }
$report['collectionErrors'] = @($script:CollectionErrors)
$captureJson = Microsoft.PowerShell.Utility\ConvertTo-Json -InputObject $report -Depth 14
[IO.File]::WriteAllText([IO.Path]::Combine($dir, 'capture.json'), $captureJson, [Text.UTF8Encoding]::new($false))

$observedArtifactOptions = Get-ObservedArtifactOptions -Directory $dir -Report $report -RestrictedRequested $script:IncludeIds
$manifestMetadata = @{
    collectorScriptSha256 = $collectorScriptHashAtStart
    collectorScriptSha256AtManifest = $collectorScriptHashAtManifest
    bundleId = $bundleId
    bundleMode = $script:BundleMode
    authorizationReference = $resolvedMode.AuthorizationReference
    powershellVersion = $PSVersionTable.PSVersion.ToString()
    osBuild = Get-ReportValue $report 'os.build' ([Environment]::OSVersion.Version.ToString())
    elevated = $elevated
    classification = $report.agentClassification
    commandOptions = [ordered]@{
        bundleMode = $script:BundleMode; includeIdentifiersAliasUsed = [bool]$IncludeIdentifiers
        agentClassificationFile = $classificationEvidence.file
        approvedAgentClassificationSha256 = $classificationApproval.approvedSha256
        platformPublisherSource = $platformPublisherSource
        approvedCmslBindingProvided = (-not [string]::IsNullOrWhiteSpace($ApprovedCmslModulePath) -and -not [string]::IsNullOrWhiteSpace($ApprovedCmslTreeSha256))
        approvedCmslTreeSha256 = if ($ApprovedCmslTreeSha256 -match '^[0-9A-Fa-f]{64}$') { $ApprovedCmslTreeSha256.ToUpperInvariant() } else { $null }
        restrictedArtifactsRequested = $observedArtifactOptions.restrictedArtifactsRequested
        activeWlanFilePresent = $observedArtifactOptions.activeWlanFilePresent
        activeWlanCommandSucceeded = $observedArtifactOptions.activeWlanCommandSucceeded
        activeWlanCollected = $observedArtifactOptions.activeWlanCollected
        rawBatteryReportFilePresent = $observedArtifactOptions.rawBatteryReportFilePresent
        rawBatteryReportCommandSucceeded = $observedArtifactOptions.rawBatteryReportCommandSucceeded
        rawBatteryReportRetained = $observedArtifactOptions.rawBatteryReportRetained
        sleepStudyFilePresent = $observedArtifactOptions.sleepStudyFilePresent
        sleepStudyCommandSucceeded = $observedArtifactOptions.sleepStudyCommandSucceeded
        sleepStudyCollected = $observedArtifactOptions.sleepStudyCollected
    }
    collectionErrors = @($script:CollectionErrors)
    nativeStatuses = @($script:NativeStatuses)
}
$null = Write-EvidenceManifest -Directory $dir -Metadata $manifestMetadata
Write-Host "Evidence manifest written with SHA-256 hashes."
