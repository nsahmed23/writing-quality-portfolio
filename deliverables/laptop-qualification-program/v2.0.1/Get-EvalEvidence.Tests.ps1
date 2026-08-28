#Requires -Version 5.1
<#
    Collector contract tests. Exactly seven active unit scenarios exercise deterministic
    policy and transformation behavior. Exactly seven skipped checks are the real bench
    matrix; their machine states must not be claimed through mocks.
#>

Describe 'Get-EvalEvidence v2 collector contract' {
    BeforeAll {
        $script:ScriptPath = Join-Path $PSScriptRoot 'Get-EvalEvidence.ps1'
        . $script:ScriptPath -LoadFunctionsOnly
        function Assert-True($Actual, [string]$Message = 'Expected true.') { if (-not [bool]$Actual) { throw $Message } }
        function Assert-Equal($Actual, $Expected) { if ($Actual -ne $Expected) { throw "Expected '$Expected' but got '$Actual'." } }
        function Assert-Matches([string]$Actual, [string]$Pattern) { if ($Actual -notmatch $Pattern) { throw "'$Actual' did not match '$Pattern'." } }
        function Assert-NotMatches([string]$Actual, [string]$Pattern) { if ($Actual -match $Pattern) { throw "'$Actual' unexpectedly matched '$Pattern'." } }
        function Assert-NullOrEmpty($Actual) { if ($null -ne $Actual -and @($Actual).Count -gt 0 -and -not [string]::IsNullOrEmpty([string]$Actual)) { throw "Expected null or empty but got '$Actual'." } }
        function Assert-Throws([scriptblock]$Action) { try { & $Action; throw 'Expected action to throw.' } catch { if ($_.Exception.Message -eq 'Expected action to throw.') { throw } } }
        function Assert-NoThrow([scriptblock]$Action) { try { & $Action } catch { throw "Expected no throw, got: $($_.Exception.Message)" } }
    }

    Context 'Active unit scenarios' {
        It '1. requires a recorded authorization reference for every restricted bundle path' {
            Assert-Equal (Resolve-BundleMode -RequestedMode Safe -IdentifiersSwitch $false -Authorization $null).Mode 'Safe'
            Assert-Throws { Resolve-BundleMode -RequestedMode Restricted -IdentifiersSwitch $false -Authorization ' ' }
            Assert-Throws { Resolve-BundleMode -RequestedMode Safe -IdentifiersSwitch $true -Authorization $null }
            $authorized = Resolve-BundleMode -RequestedMode Restricted -IdentifiersSwitch $false -Authorization 'CASE-1234'
            Assert-True $authorized.IncludesIdentifiers
            Assert-Equal $authorized.AuthorizationReference 'CASE-1234'
        }

        It '2. pseudonymizes identifiers with a per-bundle salt and sanitizes paths in Safe mode' {
            $script:IncludeIds = $false
            $script:PseudonymSalt = [byte[]](0..31)
            $first = Protect-Id 'SERIAL-001234'
            Assert-Matches $first '^sha256:[0-9a-f]{64}$'
            Assert-NotMatches $first 'SERIAL|1234$'
            $pnpId = Protect-Id 'PCI\VEN_1234&DEV_5678\TENANT-DEVICE-9876'
            Assert-Matches $pnpId '^sha256:[0-9a-f]{64}$'
            Assert-NotMatches $pnpId 'PCI|TENANT|9876$'
            Assert-Equal (Protect-Id 'SERIAL-001234') $first
            $pathRecord = Get-SafePathRecord 'C:\Users\Alice Example\Agent\agent.exe'
            Assert-NullOrEmpty $pathRecord.path
            Assert-Equal $pathRecord.fileName 'agent.exe'
            Assert-Matches $pathRecord.pathPseudonym '^sha256:'
            Assert-NotMatches (Protect-ErrorMessage 'failed under C:\Users\Alice Example\secret') 'Alice|Example'
            $safeAgent = New-AgentObservation -Kind 'service' -Name 'Tenant Alice Service' -DisplayName 'Tenant Alice Service' -State 'Running' -CommandLine '"C:\Users\Alice Example\Agent\agent.exe" --service' -Rules @()
            Assert-NullOrEmpty $safeAgent.name
            Assert-NullOrEmpty $safeAgent.displayName
            Assert-NullOrEmpty $safeAgent.product
            Assert-NullOrEmpty $safeAgent.provider
            Assert-NullOrEmpty $safeAgent.signer
            Assert-NullOrEmpty $safeAgent.binary.fileName
            Assert-Matches $safeAgent.observationPseudonym '^sha256:'
            Assert-Matches $safeAgent.productPseudonym '^sha256:'
            $safeMount = Get-SensitiveLocationRecord -Location 'C:\Users\Alice Example\MountedVolume'
            Assert-NullOrEmpty $safeMount.location
            Assert-Matches $safeMount.locationPseudonym '^sha256:[0-9a-f]{64}$'
            Assert-NotMatches $safeMount.locationPseudonym 'Alice|MountedVolume'
            $safeEnvelope = New-CaptureEnvelope -BundleId 'random-bundle-id' -Mode Safe -ComputerName 'TENANT-LAPTOP-1234' -Elevated $false
            Assert-True (-not $safeEnvelope.Contains('hostname')) 'Safe capture envelope must omit hostname entirely.'
            Assert-Matches $safeEnvelope.devicePseudonym '^sha256:[0-9a-f]{64}$'
            Assert-NotMatches $safeEnvelope.devicePseudonym '1234$'
            $script:PseudonymSalt = [byte[]](1..32)
            Assert-True ((Protect-Id 'SERIAL-001234') -ne $first) 'A new bundle salt must produce a new pseudonym.'
        }

        It '3. parses spaced executable paths and marks incomplete provider or signature metadata PARTIAL' {
            $quoted = Split-ExecutableCommandLine '"C:\Program Files\Agent Suite\agent.exe" --service'
            Assert-Equal $quoted.Executable 'C:\Program Files\Agent Suite\agent.exe'
            Assert-Equal $quoted.Arguments '--service'
            $unquoted = Split-ExecutableCommandLine 'C:\Program Files\Agent Suite\driver.sys -k'
            Assert-Equal $unquoted.Executable 'C:\Program Files\Agent Suite\driver.sys'
            Assert-Equal $unquoted.Arguments '-k'
            $plainExecutable = Join-Path $TestDrive 'plain.exe'
            'not a signed executable' | Set-Content -LiteralPath $plainExecutable
            $script:CollectionErrors = @()
            function Get-AuthenticodeSignature { [pscustomobject]@{ Status = 'Valid'; SignerCertificate = [pscustomobject]@{ Subject = 'FAKE-SIGNER-MARKER' } } }
            try { $metadata = Get-ExecutableMetadata -Path $plainExecutable }
            finally { Remove-Item Function:\Get-AuthenticodeSignature -ErrorAction SilentlyContinue }
            Assert-Equal $metadata.status 'PARTIAL'
            Assert-NotMatches ([string]$metadata.signer) 'FAKE-SIGNER-MARKER'
            Assert-True ($script:CollectionErrors.Count -gt 0)
            Assert-True $script:CollectionErrors[0].forcesInconclusive
            $unc = Resolve-LocalObservedExecutable -Path '\\attacker.invalid\share\agent.exe'
            Assert-Equal $unc.status 'REJECTED'
            Assert-Matches $unc.reason 'Remote|device|provider'
            $remoteMetadata = Get-ExecutableMetadata -Path '\\attacker.invalid\share\agent.exe'
            Assert-Equal $remoteMetadata.status 'UNAVAILABLE'
            Assert-Matches $remoteMetadata.limitation 'Remote|device|provider'
            $script:ObservedAttributePaths = @()
            $previousLocation = (Get-Location).Path
            try {
                Set-Location -LiteralPath $TestDrive
                $localResolution = Resolve-LocalObservedExecutable -Path $plainExecutable -AttributeProvider {
                    param($ObservedPath)
                    $script:ObservedAttributePaths += $ObservedPath
                    [IO.File]::GetAttributes($ObservedPath)
                }
            } finally { Set-Location -LiteralPath $previousLocation }
            Assert-Equal $localResolution.status 'LOCAL'
            Assert-True ($script:ObservedAttributePaths.Count -gt 0)
            Assert-Matches $script:ObservedAttributePaths[0] '^[A-Za-z]:[\\/]'
            Assert-NotMatches $script:ObservedAttributePaths[0] '^[A-Za-z]:[^\\/]'
        }

        It '4. validates, versions, hashes, and copies the external vendor-neutral classification envelope' {
            $rulesPath = Join-Path $TestDrive 'rules.json'
            '{ "schemaVersion": "1.0", "rulesVersion": "test-rules-1", "rules": [{ "id": "configured-1", "match": "agent-token", "product": "Configured product", "class": "other", "targets": ["service"] }] }' | Set-Content -LiteralPath $rulesPath
            $classification = Get-AgentClassification -Path $rulesPath
            Assert-Equal $classification.Status 'valid'
            Assert-Equal $classification.RulesVersion 'test-rules-1'
            Assert-Equal $classification.Sha256 (Get-FileHash -LiteralPath $rulesPath -Algorithm SHA256).Hash
            $matched = Resolve-AgentClass -Rules $classification.Rules -EvidenceText 'agent-token' -DefaultProduct 'fallback' -TargetType 'service'
            Assert-Equal $matched.product 'Configured product'
            Assert-Equal $matched.ruleId 'configured-1'
            Assert-Equal (Resolve-AgentClass -Rules $classification.Rules -EvidenceText 'agent-token' -DefaultProduct 'fallback' -TargetType 'kernelDriver').class 'unclassified'
            $safeBundle = Join-Path $TestDrive 'classification-safe-bundle'
            New-Item -ItemType Directory -Path $safeBundle | Out-Null
            $reference = Copy-AgentClassificationEvidence -Classification $classification -Directory $safeBundle -RetainRulesFile $false
            Assert-Equal $reference.sha256 $classification.Sha256
            Assert-NullOrEmpty $reference.file
            Assert-True (-not (Test-Path -LiteralPath (Join-Path $safeBundle 'agent-classification.rules.json'))) 'Safe bundles must not retain raw classification rules.'
            $bundle = Join-Path $TestDrive 'classification-restricted-bundle'
            New-Item -ItemType Directory -Path $bundle | Out-Null
            $copy = Copy-AgentClassificationEvidence -Classification $classification -Directory $bundle -RetainRulesFile $true
            Assert-Equal $copy.sha256 $classification.Sha256
            Assert-True (Test-Path -LiteralPath (Join-Path $bundle 'agent-classification.rules.json'))
            $badPath = Join-Path $TestDrive 'bad-rules.json'
            '{"schemaVersion":"9.9","rulesVersion":"bad","rules":[{"id":"bad","match":"agent-token","product":"Must not apply","class":"unsupported"}]}' | Set-Content -LiteralPath $badPath
            $invalid = Get-AgentClassification -Path $badPath
            Assert-Equal $invalid.Status 'invalid'
            Assert-Equal $invalid.Rules.Count 0
            Assert-Equal (Resolve-AgentClass -Rules $invalid.Rules -EvidenceText 'agent-token' -DefaultProduct 'fallback' -TargetType 'service').class 'unclassified'
            Assert-Equal (Resolve-PublisherOrigin -Provider 'Contoso Platform Corp' -Signer $null -SignatureTrusted $false -PlatformPublisher 'Contoso Platform Corp') 'unknown'
            Assert-Equal (Resolve-PublisherOrigin -Provider 'Contoso Platform Corp' -Signer 'CN=Platform Signing, O=Contoso Platform Corp' -SignatureTrusted $true -PlatformPublisher 'Contoso Platform Corp') 'platform-signed'
            $platformSignerAliases = @('CN=Microsoft Windows, O=Microsoft Corporation')
            Assert-Equal (Resolve-PublisherOrigin -Provider 'Microsoft' -Signer 'Microsoft Windows' -SignatureTrusted $true -PlatformPublisher 'Microsoft Corporation' -PlatformPublisherAliases $platformSignerAliases) 'platform-signed'
            Assert-Equal (Resolve-PublisherOrigin -Provider 'Microsoft Corporation' -Signer 'CN=Microsoft Windows, O=Microsoft Corporation' -SignatureTrusted $true -PlatformPublisher 'Microsoft Corporation' -PlatformPublisherAliases $platformSignerAliases) 'platform-signed'
            Assert-Equal (Resolve-PublisherOrigin -Provider 'Microsoft' -Signer 'Microsoft Windows' -SignatureTrusted $false -PlatformPublisher 'Microsoft Corporation') 'unknown'
            Assert-Equal (Resolve-PublisherOrigin -Provider 'Microsoft Malware LLC' -Signer 'CN=Microsoft Malware LLC' -SignatureTrusted $true -PlatformPublisher 'Microsoft Corporation' -PlatformPublisherAliases $platformSignerAliases) 'third-party'
            Assert-Equal (Resolve-PublisherOrigin -Provider 'Contoso Platform Services LLC' -Signer 'CN=Contoso Platform Services LLC' -SignatureTrusted $true -PlatformPublisher 'Contoso Platform Corp') 'third-party'
            Assert-Equal (Resolve-PublisherOrigin -Provider 'Microsoft LLC' -Signer 'CN=Microsoft LLC, O=Microsoft LLC' -SignatureTrusted $true -PlatformPublisher 'Microsoft Corporation' -PlatformPublisherAliases $platformSignerAliases) 'third-party'
            Assert-Equal (Resolve-PublisherOrigin -Provider 'Contoso Platform LLC' -Signer 'CN=Contoso Platform, O=Contoso Platform LLC' -SignatureTrusted $true -PlatformPublisher 'Contoso Platform Corp') 'third-party'
            Assert-Equal (Resolve-PublisherOrigin -Provider 'Microsoft' -Signer 'CN=Microsoft Windows, O=Microsoft Malware LLC' -SignatureTrusted $true -PlatformPublisher 'Microsoft Corporation' -PlatformPublisherAliases $platformSignerAliases) 'unknown'
            Assert-Equal (Resolve-PublisherOrigin -Provider 'Example Security LLC' -Signer $null) 'third-party'
            Assert-Equal (Resolve-PublisherOrigin -Provider 'Example Security LLC' -Signer 'CN=Platform Signing, O=Contoso Platform Corp' -SignatureTrusted $true -PlatformPublisher 'Contoso Platform Corp') 'third-party'
            Assert-Equal (Resolve-PublisherOrigin -Provider $null -Signer $null) 'unknown'
            Assert-Equal (Resolve-AgentClass -Rules @() -EvidenceText 'unmatched' -DefaultProduct 'fallback' -TargetType 'kernelDriver' -PublisherOrigin 'platform-signed').class 'unclassified'
            Assert-Equal (Resolve-AgentClass -Rules @() -EvidenceText 'unmatched' -DefaultProduct 'fallback' -TargetType 'kernelDriver' -PublisherOrigin 'third-party').class 'unclassified-thirdparty'
            Assert-Equal (Resolve-AgentClass -Rules @() -EvidenceText 'unmatched' -DefaultProduct 'fallback' -TargetType 'kernelDriver' -PublisherOrigin 'unknown').class 'unclassified'
            Assert-Equal (Test-AgentClassificationApproval -Classification $classification -ApprovedSha256 $null).status 'APPROVAL_REQUIRED'
            $malformedApproval = Test-AgentClassificationApproval -Classification $classification -ApprovedSha256 'C:\Users\Alice\ticket.txt'
            Assert-Equal $malformedApproval.status 'DIGEST_INVALID'
            Assert-NullOrEmpty $malformedApproval.approvedSha256
            $approval = Test-AgentClassificationApproval -Classification $classification -ApprovedSha256 $classification.Sha256
            Assert-Equal $approval.status 'APPROVED'
            $invalidEvidence = [pscustomobject]@{ status = 'invalid' }
            Assert-Equal @(Get-ActiveClassificationRules -Classification $classification -ClassificationEvidence $invalidEvidence -ClassificationApproval $approval).Count 0
            $failedCopyDir = Join-Path $TestDrive 'classification-failed-copy'
            New-Item -ItemType Directory -Path $failedCopyDir | Out-Null
            $badSnapshot = [pscustomobject]@{ Status = 'valid'; Sha256 = ('0' * 64); SchemaVersion = '1.0'; RulesVersion = 'bad-copy'; RawBytes = [Text.Encoding]::UTF8.GetBytes('{}') }
            Assert-Throws { Copy-AgentClassificationEvidence -Classification $badSnapshot -Directory $failedCopyDir -RetainRulesFile $true }
            Assert-True (-not (Test-Path -LiteralPath (Join-Path $failedCopyDir 'agent-classification.rules.json'))) 'A failed classification copy must not remain in the bundle.'
            $failedHashDir = Join-Path $TestDrive 'classification-failed-hash'
            New-Item -ItemType Directory -Path $failedHashDir | Out-Null
            Assert-Throws { Copy-AgentClassificationEvidence -Classification $classification -Directory $failedHashDir -RetainRulesFile $true -HashProvider { param($EvidencePath) throw 'forced hash read failure' } }
            Assert-True (-not (Test-Path -LiteralPath (Join-Path $failedHashDir 'agent-classification.rules.json'))) 'Every classification write/hash exception must remove partial output.'
            $moduleDir = Join-Path $TestDrive 'approved-cmsl'
            New-Item -ItemType Directory -Path $moduleDir | Out-Null
            $moduleManifest = Join-Path $moduleDir 'HP.ClientManagement.psd1'
            '@{ RootModule = ''HP.ClientManagement.psm1''; ModuleVersion = ''1.0.0'' }' | Set-Content -LiteralPath $moduleManifest
            'function Get-TestValue { 1 }' | Set-Content -LiteralPath (Join-Path $moduleDir 'HP.ClientManagement.psm1')
            $treeHash = Get-ModuleTreeSha256 -ModuleEntryPath $moduleManifest
            $validBinding = Test-ApprovedCmslModuleBinding -ModulePath $moduleManifest -ExpectedTreeSha256 $treeHash
            Assert-Equal $validBinding.status 'VALID'
            $snapshot = New-PrivateModuleSnapshot -Binding $validBinding
            try {
                Assert-True ($snapshot.root -ne $validBinding.moduleRoot)
                Assert-Equal $snapshot.treeSha256 $treeHash
                Assert-True (Test-Path -LiteralPath $snapshot.entryPath)
            } finally { if (Test-Path -LiteralPath $snapshot.root) { [IO.Directory]::Delete($snapshot.root, $true) } }
            $aclProbe = Join-Path $TestDrive 'acl-cross-host-probe'
            $null = [IO.Directory]::CreateDirectory($aclProbe)
            Assert-NoThrow { Set-PrivateDirectoryAcl -Path $aclProbe }
            $aclDirectory = [IO.DirectoryInfo]::new($aclProbe)
            $instanceGetter = [IO.DirectoryInfo].GetMethod('GetAccessControl', [type[]]@())
            $probeAcl = if ($null -ne $instanceGetter) {
                $instanceGetter.Invoke($aclDirectory, $null)
            } else {
                [IO.FileSystemAclExtensions]::GetAccessControl($aclDirectory)
            }
            Assert-True $probeAcl.AreAccessRulesProtected 'The private ACL must disable inheritance on every supported host.'
            $probeRules = @($probeAcl.GetAccessRules($true, $false, [Security.Principal.SecurityIdentifier]))
            $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
            $systemSid = [Security.Principal.SecurityIdentifier]::new([Security.Principal.WellKnownSidType]::LocalSystemSid, $null).Value
            Assert-Equal @($probeRules | Where-Object { $_.IdentityReference.Value -eq $currentSid -and $_.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow }).Count 1
            Assert-Equal @($probeRules | Where-Object { $_.IdentityReference.Value -eq $systemSid -and $_.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow }).Count 1
            $script:TempCreateCalls = 0
            Assert-Throws {
                New-TrustedTemporaryDirectory -Purpose 'probe' -CandidateRoot '\\attacker.invalid\temp' -DirectoryCreator { param($NewDirectory) $script:TempCreateCalls++ }
            }
            Assert-Equal $script:TempCreateCalls 0
            $script:TempCreateCalls = 0
            $script:TempAttributeCalls = 0
            $syntheticTempRoot = [IO.Path]::Combine([IO.Path]::GetPathRoot($TestDrive), 'trusted-base', 'reparse-temp')
            Assert-Throws {
                New-TrustedTemporaryDirectory -Purpose 'probe' -CandidateRoot $syntheticTempRoot -DriveTypeProvider { param($DriveRoot) [IO.DriveType]::Fixed } -AttributeProvider {
                    param($CandidatePath)
                    $script:TempAttributeCalls++
                    if ($script:TempAttributeCalls -eq 2) { return ([IO.FileAttributes]::Directory -bor [IO.FileAttributes]::ReparsePoint) }
                    [IO.FileAttributes]::Directory
                } -DirectoryCreator { param($NewDirectory) $script:TempCreateCalls++ }
            }
            Assert-Equal $script:TempCreateCalls 0
            'function Get-TestValue { 2 }' | Set-Content -LiteralPath (Join-Path $moduleDir 'HP.ClientManagement.psm1')
            Assert-Equal (Test-ApprovedCmslModuleBinding -ModulePath $moduleManifest -ExpectedTreeSha256 $treeHash).status 'INVALID'
            Assert-True (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'agent-classification.json')) 'The vendor-empty production classification file must ship at the collector default path.'
            Assert-True (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'agent-classification.example.json'))) 'No competing example classification source may ship.'
            $collectorSource = Get-Content -LiteralPath $script:ScriptPath -Raw
            Assert-NotMatches $collectorSource '(?i)CrowdStrike|SentinelOne|Zscaler|Tanium|Netskope|Trellix|McAfee|Symantec|Sophos|Carbon\s+Black|Cylance|Qualys'
            Assert-Matches $collectorSource 'New-AgentObservation -Kind ''kernelDriver''[^\r\n]+-Rules \$activeClassificationRules'
        }

        It '5. records native exit status and never treats an allowed nonzero exit as successful evidence' {
            $script:NativeStatuses = @()
            $script:CollectionErrors = @()
            function cmd.exe { 'HIJACK-MARKER'; $global:LASTEXITCODE = 0 }
            try {
                $wrapped = Invoke-SubCapture -Name 'native.stderrProbe' -Body {
                    Invoke-Native -Name 'expectedFailure' -FilePath 'cmd.exe' -ArgumentList '/d','/c','echo diagnostic 1>&2 & exit /b 3' -AllowFailure
                }
            } finally { Remove-Item Function:\cmd.exe -ErrorAction SilentlyContinue }
            Assert-Equal $wrapped.status 'OK'
            $allowed = @($wrapped.data)[0]
            Assert-True (-not $allowed.Success)
            Assert-Equal $allowed.ExitCode 3
            Assert-True (@($allowed.Output).Count -gt 0) 'Native stderr must remain captured as evidence.'
            Assert-NotMatches ((@($allowed.Output) | ForEach-Object { [string]$_ }) -join ' ') 'HIJACK-MARKER'
            Assert-True (-not $script:NativeStatuses[0].success)
            Assert-Equal $script:CollectionErrors[0].command 'expectedFailure'
            Assert-Equal $script:CollectionErrors[0].exitCode 3
            Assert-True $script:CollectionErrors[0].incomplete
            Assert-True $script:CollectionErrors[0].forcesInconclusive
            Assert-Equal $script:NativeStatuses[0].collectionErrorId $script:CollectionErrors[0].errorId
            Assert-Throws { Invoke-Native -Name 'throwingFailure' -FilePath $env:ComSpec -ArgumentList '/c','exit','4' }
            Assert-Equal $script:NativeStatuses.Count 2
        }

        It '6. preserves later sections, records UNKNOWN rather than zero, and writes a safe summary after failure' {
            $script:report = [ordered]@{ bundleId = 'test-bundle'; bundleMode = 'Safe' }
            $script:CollectionErrors = @()
            $zeroWhea = Get-WheaEventEvidence -Query { Write-Error 'no matching events' -ErrorId 'NoMatchingEventsFound' -ErrorAction Stop }
            Assert-Equal $zeroWhea.status 'OK'
            Assert-Equal $zeroWhea.count 0
            $failedWhea = Get-WheaEventEvidence -Query { Write-Error 'WHEA query failed' -ErrorId 'AccessDenied' -ErrorAction Stop }
            Assert-Equal $failedWhea.status 'UNKNOWN'
            Assert-NullOrEmpty $failedWhea.count
            Add-Section -Name 'identity' -Body { Write-Error 'identity unavailable' }
            Add-Section -Name 'os' -Body { [ordered]@{ caption = 'Test OS'; build = '1.2.3' } }
            Assert-Equal $script:report.identity.status 'UNKNOWN'
            Assert-Equal $script:report.os.caption 'Test OS'
            Assert-Equal $script:CollectionErrors.Count 2
            $summaryPath = Join-Path $TestDrive 'summary.txt'
            Assert-NoThrow { Write-CollectorSummary -Report $script:report -Path $summaryPath | Out-Null }
            Assert-Matches (Get-Content -LiteralPath $summaryPath -Raw) 'Model: unknown'
            Assert-Matches (Get-Content -LiteralPath $summaryPath -Raw) 'Collection errors: 2'
        }

        It '7. manifests every bundle file with SHA-256 plus complete provenance and restriction labels' {
            $artifactDir = Join-Path $TestDrive 'observed-artifacts'
            New-Item -ItemType Directory -Path $artifactDir | Out-Null
            $safePlan = Get-CollectionPlan -Mode Safe
            Assert-True (-not $safePlan.activeWlanDetails)
            Assert-True (-not $safePlan.retainRawBatteryReport)
            Assert-True (-not $safePlan.sleepStudy)
            Assert-True (-not $safePlan.retainClassificationRules)
            $artifactReport = [ordered]@{
                network = [ordered]@{ wlan = [ordered]@{ status = 'UNKNOWN' } }
                battery = [ordered]@{ rawReport = 'battery-report.xml'; rawReportCommandSucceeded = $false }
                exportStatus = [ordered]@{ sleepStudy = [ordered]@{ status = 'UNKNOWN' } }
            }
            $observedAbsent = Get-ObservedArtifactOptions -Directory $artifactDir -Report $artifactReport -RestrictedRequested $true
            Assert-True (-not $observedAbsent.activeWlanCollected)
            Assert-True (-not $observedAbsent.rawBatteryReportRetained)
            Assert-True (-not $observedAbsent.sleepStudyCollected)
            'authorized WLAN evidence' | Set-Content -LiteralPath (Join-Path $artifactDir 'wlan.txt')
            $artifactReport.network.wlan.status = 'OK'
            Assert-True (Get-ObservedArtifactOptions -Directory $artifactDir -Report $artifactReport -RestrictedRequested $true).activeWlanCollected
            'partial sleep evidence' | Set-Content -LiteralPath (Join-Path $artifactDir 'sleepstudy.html')
            'partial battery evidence' | Set-Content -LiteralPath (Join-Path $artifactDir 'battery-report.xml')
            $partialArtifacts = Get-ObservedArtifactOptions -Directory $artifactDir -Report $artifactReport -RestrictedRequested $true
            Assert-True $partialArtifacts.sleepStudyFilePresent
            Assert-True (-not $partialArtifacts.sleepStudyCommandSucceeded)
            Assert-True (-not $partialArtifacts.sleepStudyCollected)
            Assert-True $partialArtifacts.rawBatteryReportFilePresent
            Assert-True (-not $partialArtifacts.rawBatteryReportCommandSucceeded)
            Assert-True (-not $partialArtifacts.rawBatteryReportRetained)

            $bundle = Join-Path $TestDrive 'manifest-bundle'
            New-Item -ItemType Directory -Path $bundle | Out-Null
            'alpha' | Set-Content -LiteralPath (Join-Path $bundle 'a.txt')
            'beta' | Set-Content -LiteralPath (Join-Path $bundle 'b.txt')
            '{"schemaVersion":"1.0","rulesVersion":"rules-7","rules":[]}' | Set-Content -LiteralPath (Join-Path $bundle 'agent-classification.rules.json')
            $metadata = @{
                collectorScriptSha256 = ('a' * 64); bundleId = 'bundle-1'; bundleMode = 'Restricted'
                authorizationReference = 'CASE-1234'; powershellVersion = '5.1'; osBuild = '1.2.3'; elevated = $true
                classification = [ordered]@{ schemaVersion = '1.0'; rulesVersion = 'rules-7'; sha256 = ('b' * 64); sourceFile = 'agent-classification.rules.json' }
                commandOptions = [ordered]@{ bundleMode = 'Restricted' }
                collectionErrors = @([ordered]@{ code = 'EXPECTED'; command = 'probe'; exitCode = 0; incomplete = $false; forcesInconclusive = $false })
                nativeStatuses = @([ordered]@{ name = 'probe'; exitCode = 0; success = $true })
            }
            $manifest = Write-EvidenceManifest -Directory $bundle -Metadata $metadata
            Assert-Equal $manifest.files.Count 3
            Assert-Equal ($manifest.files | Where-Object file -eq 'a.txt').sha256 (Get-FileHash -LiteralPath (Join-Path $bundle 'a.txt') -Algorithm SHA256).Hash
            Assert-NullOrEmpty ($manifest.files | Where-Object file -eq 'evidence-manifest.json')
            Assert-Equal $manifest.bundleMode 'Restricted'
            Assert-Equal $manifest.handling 'restricted-internal'
            Assert-Equal $manifest.authorizationReference 'CASE-1234'
            Assert-Equal $manifest.collectorScriptSha256 ('a' * 64)
            Assert-Equal $manifest.classification.rulesVersion 'rules-7'
            Assert-True $manifest.privacyBoundary.classificationRuleFileRetained
            Assert-Equal $manifest.collectionErrors.Count 1
            Assert-Equal $manifest.nativeStatuses.Count 1
            Assert-Equal $manifest.integrityBoundary.authenticity 'not-provided; release through an approved signed channel'

            $safeManifestDir = Join-Path $TestDrive 'safe-manifest-bundle'
            New-Item -ItemType Directory -Path $safeManifestDir | Out-Null
            'safe evidence' | Set-Content -LiteralPath (Join-Path $safeManifestDir 'capture.json')
            $safeMetadata = @{
                collectorScriptSha256 = ('c' * 64); bundleId = 'bundle-safe'; bundleMode = 'Safe'
                powershellVersion = '5.1'; osBuild = '1.2.3'; elevated = $false
                classification = [ordered]@{ schemaVersion = '1.0'; rulesVersion = 'rules-safe'; sha256 = ('d' * 64); sourceFile = $null }
                commandOptions = [ordered]@{ activeWlanCollected = $false; rawBatteryReportRetained = $false; sleepStudyCollected = $false }
                collectionErrors = @(); nativeStatuses = @()
            }
            $safeManifest = Write-EvidenceManifest -Directory $safeManifestDir -Metadata $safeMetadata
            Assert-Equal $safeManifest.handling 'safe-shareable-after-manifest-review'
            Assert-True $safeManifest.privacyBoundary.manifestReviewRequiredBeforeSharing
            Assert-True (-not $safeManifest.privacyBoundary.classificationRuleFileRetained)
            Assert-Matches ($safeManifest.restrictions -join ' ') 'Classification rules.*not included'
        }
    }

    Context 'Bench integration matrix (execute manually and retain the resulting manifest)' {
        # B1: Standard-user shell. Command: .\Get-EvalEvidence.ps1 -OutputRoot <bench>.
        # Accept: bundle completes; privileged sections are UNKNOWN; other sections and manifest remain.
        It 'B1. non-elevated Safe run completes with explicit privileged-section errors' -Skip { }

        # B2: Elevated shell. Same command. Accept: TPM/SecureBoot/BitLocker/minifilter data and native statuses populate.
        It 'B2. elevated Safe run captures all privileged security and driver evidence' -Skip { }

        # B3: Bench image without CMSL. Same command. Accept: hpCmsl=NOT_AVAILABLE; manifest and remaining bundle complete.
        It 'B3. CMSL-absent unit records NOT_AVAILABLE without losing the bundle' -Skip { }

        # B4: Bench image with approved CMSL. First dot-source with -LoadFunctionsOnly and calculate
        # Get-ModuleTreeSha256 for the approved absolute .psd1, then run with
        # -ApprovedCmslModulePath <absolute.psd1> -ApprovedCmslTreeSha256 <approved digest>.
        # Accept: module version plus CLIXML/JSON raw outputs, or explicit UNKNOWN per command; hashes present.
        It 'B4. CMSL-present unit preserves raw command objects and offline failures honestly' -Skip { }

        # B5: Run once on a laptop with a battery and once on a batteryless/removed-pack bench unit.
        # Accept: structured capacities/health when present and present=false when absent; Safe emits no XML.
        It 'B5. battery-present and battery-absent units produce the correct structured states' -Skip { }

        # B6: Run on a device whose storage provider lacks reliability counters.
        # Accept: per-disk limitation/UNKNOWN is explicit; identity and all other evidence survive.
        It 'B6. unsupported storage reliability counters do not abort or fabricate zero values' -Skip { }

        # B7 Safe: .\Get-EvalEvidence.ps1 -OutputRoot <bench>.
        # B7 Restricted: add -BundleMode Restricted -AuthorizationReference CASE-1234.
        # Accept Safe has random folder ID, salted IDs, no hostname/WLAN/battery XML/sleepstudy/profile paths.
        # Accept Restricted manifest is restricted-internal, records CASE-1234, and hashes every sensitive artifact.
        It 'B7. Safe and authorized Restricted bundles enforce their privacy and manifest contracts end to end' -Skip { }
    }
}
