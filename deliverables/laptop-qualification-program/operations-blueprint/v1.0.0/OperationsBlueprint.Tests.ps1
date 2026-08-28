$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Test-OperationsBlueprint.ps1') -LoadFunctionsOnly
$evaluationTime = [DateTimeOffset]::Parse('2026-08-27T12:30:00Z')

function Copy-TestObject {
    param([Parameter(Mandatory = $true)]$InputObject)
    # PSSerializer preserves ISO date-time fixture values as strings on both PowerShell 5.1 and Core.
    # ConvertFrom-Json coerces them to local DateTime values on newer Core hosts, which changes chronology.
    [System.Management.Automation.PSSerializer]::Deserialize(
        [System.Management.Automation.PSSerializer]::Serialize($InputObject, 50)
    )
}

function Test-ScriptBlockThrows {
    param([Parameter(Mandatory = $true)][scriptblock]$ScriptBlock)

    try {
        & $ScriptBlock | Out-Null
        return $false
    }
    catch { return $true }
}

function New-TestDigest {
    param([ValidatePattern('^[0-9a-f]$')][string]$Nibble = 'a')
    'sha256:' + (($Nibble * 64) -join '')
}

function New-TestCanonicalPrincipalId {
    param([Parameter(Mandatory = $true)][string]$Seed)
    'private://canonical-principals/sha256/' + (Get-Sha256TokenFromText -Text $Seed).Substring(7)
}

$script:PortableValidationRecordFixtures = [System.Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
$script:PortableSourceDocumentFixtures = [System.Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
$script:SerializedFixtureCache = [System.Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)

function Restore-TestPortableFixtureRegistries {
    param([Parameter(Mandatory = $true)][object[]]$RecordIndex)

    foreach ($validationRecord in @($RecordIndex | Where-Object recordType -CEQ 'portable-contract-validation-record')) {
        $script:PortableValidationRecordFixtures[[string]$validationRecord.recordId] = $validationRecord
    }
    foreach ($projectionRecord in @($RecordIndex | Where-Object recordType -CEQ 'portable-contract-projection-record')) {
        $metadata = Get-PortableContractMetadata -PortableRecordType ([string]$projectionRecord.payload.portableRecordType)
        $sourceErrors = New-Object System.Collections.ArrayList
        $boundSource = New-PortableProjectionSourcePayload -Bindings @($projectionRecord.payload.projection.bindings) `
            -Errors $sourceErrors -Context "cached portable fixture $($projectionRecord.recordId)"
        if ($sourceErrors.Count -ne 0) {
            throw "Cached portable fixture source reconstruction failed: $(@($sourceErrors.code) -join ', ')."
        }
        $sourceFields = [ordered]@{
            (([string]$metadata.IdPointer).Substring(1)) = [string]$projectionRecord.payload.sourceCanonicalIdValue
        }
        foreach ($property in $boundSource.PSObject.Properties) {
            $sourceFields[[string]$property.Name] = $property.Value
        }
        $script:PortableSourceDocumentFixtures[[string]$projectionRecord.payload.sourceRecordRef] =
            Copy-TestObject -InputObject ([pscustomobject]$sourceFields)
    }
}

function Convert-TestFixtureAutomationNullsToExplicitNull {
    param([AllowNull()]$Value)

    if ($null -eq $Value -or $Value -is [string]) { return }
    if ($Value -is [System.Collections.IDictionary]) {
        foreach ($key in @($Value.Keys)) {
            $child = $Value[$key]
            if ($null -eq $child) { $Value[$key] = $null }
            else { Convert-TestFixtureAutomationNullsToExplicitNull -Value $child }
        }
        return
    }
    if ($Value.GetType().FullName -ceq 'System.Management.Automation.PSCustomObject') {
        foreach ($property in @($Value.PSObject.Properties)) {
            $child = $property.Value
            if ($null -eq $child) { $property.Value = $null }
            else { Convert-TestFixtureAutomationNullsToExplicitNull -Value $child }
        }
        return
    }
    if ($Value -is [System.Collections.IList]) {
        for ($index = 0; $index -lt $Value.Count; $index++) {
            $child = $Value[$index]
            if ($null -eq $child) { $Value[$index] = $null }
            else { Convert-TestFixtureAutomationNullsToExplicitNull -Value $child }
        }
    }
}

function Get-SerializedTestFixtureClone {
    param(
        [Parameter(Mandatory = $true)][string]$CacheKey,
        [Parameter(Mandatory = $true)][scriptblock]$Factory
    )

    if (-not $script:SerializedFixtureCache.ContainsKey($CacheKey)) {
        $pristine = & $Factory
        # PSSerializer otherwise turns PowerShell's no-output sentinel, when it
        # is stored in a property, into an empty PSCustomObject.  Make every
        # null-like fixture property an explicit null before taking the snapshot.
        Convert-TestFixtureAutomationNullsToExplicitNull -Value $pristine
        $script:SerializedFixtureCache.Add(
            $CacheKey,
            [System.Management.Automation.PSSerializer]::Serialize($pristine, 100)
        )
    }
    $clone = [System.Management.Automation.PSSerializer]::Deserialize(
        $script:SerializedFixtureCache[$CacheKey]
    )
    Restore-TestPortableFixtureRegistries -RecordIndex @($clone.RecordIndex)
    return $clone
}

function Test-IsLegacyPortableRecordType {
    param([AllowNull()]$RecordType)
    return [string]$RecordType -cin @(
        'candidate-manifest', 'test-plan', 'evidence-record', 'threshold-policy', 'verdict-record'
    )
}

function Get-TestPortableProjectionFields {
    param([Parameter(Mandatory = $true)][string]$PortableRecordType)
    switch ($PortableRecordType) {
        'CANDIDATE_MANIFEST' {
            @(
                'schemaVersion','status','frozenAt','qualificationAuthority','testPlanRef','thresholdPolicyRef',
                'tenantBoundaryRef','targetEnvironmentRef','hardwareEnvelope','platformBaseline','personas',
                'candidateDevices','controls','docksAndPeripherals','pilotPopulationPlan','procurementDeadline',
                'evaluationOwner','programCost','openItems','evidencePath','approvedBy','tier'
            )
        }
        'TEST_PLAN' {
            @(
                'schemaVersion','status','qualificationTier','manifestRef','thresholdPolicyRef','dependencyReviewRef',
                'omittedClasses','frozenAt','approvedBy','samplingFloors','evidenceReusePolicy','tests'
            )
        }
        'EVIDENCE_RECORD' {
            @(
                'schemaVersion','provenance','testRef','conditionRef','testPackVersion','tool','result','distribution','coverage','artifacts',
                'recordKind','evidenceUse','corroborationRef','subject','baseline','timestamp','admission','dataQuality',
                'knownLimitations','stale','claimId','subjectRef','personaId','capacityWaterfallPointer','evidenceReleaseRef',
                'coverageStatus','cohortRef','observationWindow','baselineFingerprint','distributionRef','attributionClass',
                'issueStatement','businessEffectRef','testPlanRef','controlRole','metricId','unit','statisticDirection',
                'freshnessBinding'
            )
        }
        'THRESHOLD_POLICY' {
            @(
                'schemaVersion','version','status','frozenAt','approvedBy','thresholds','reserves','revisionPolicy',
                'nonComparableAfterRevision','extensions'
            )
        }
        'VERDICT_RECORD' {
            @(
                'schemaVersion','recordStage','status','immutableAt','manifestRef','qualificationAuthority','approvers',
                'evidenceReleases','qualificationAuthorityApprovalRef','qualificationAuthorityApprovalDigest',
                'pilotPopulationPlanRef','privacyOwner','pilotAuthorizationRecordRef','pilotAuthorizationRecordDigest',
                'pilotNotRequiredApprovalRef','pilotNotRequiredApprovalDigest','provisionalLabVerdict','pilotAuthorization',
                'pilotCompletion','fleetVerdict','fleetDeploymentDisposition','personaVerdicts','conditions','exceptions',
                'arbitration','arbitrationAuthorityApprovalRef','arbitrationAuthorityApprovalDigest','deadlineDecision',
                'deadlineAuthorityApprovalRef','deadlineAuthorityApprovalDigest','procurementEnvelope',
                'procurementDisposition','residualRisks','requalificationTriggers'
            )
        }
        default { throw "Unsupported portable fixture type $PortableRecordType." }
    }
}

function Get-TestPortableDefaultFields {
    param(
        [Parameter(Mandatory = $true)][string]$RecordId,
        [Parameter(Mandatory = $true)][string]$PortableRecordType
    )
    $activation = $RecordId -match 'activation|phase[23]|monitoring'
    switch ($PortableRecordType) {
        'CANDIDATE_MANIFEST' {
            [ordered]@{
                schemaVersion = '2.0.1'
                status = 'frozen'
                frozenAt = '2026-08-27T08:00:00Z'
                qualificationAuthority = 'ROLE_QUALIFICATION_AUTHORITY'
                testPlanRef = $(if ($activation) { 'test-plan-activation-synthetic-1' } else { 'test-plan-synthetic-1' })
                thresholdPolicyRef = $(if ($activation) { 'monitoring-threshold-policy-synthetic-1' } else { 'freshness-policy-synthetic-1' })
                tenantBoundaryRef = 'private://tenants/synthetic'
                targetEnvironmentRef = 'private://environments/synthetic'
            }
        }
        'TEST_PLAN' {
            [ordered]@{
                schemaVersion = '2.0.1'
                status = 'frozen'
                qualificationTier = 'full'
                manifestRef = $(if ($activation) { 'manifest-activation-synthetic-1' } else { 'manifest-synthetic-1' })
                thresholdPolicyRef = $(if ($activation) { 'monitoring-threshold-policy-synthetic-1' } else { 'freshness-policy-synthetic-1' })
                dependencyReviewRef = 'private://reviews/dependency-review-synthetic-1'
                omittedClasses = @()
                frozenAt = '2026-08-27T08:00:00Z'
                approvedBy = 'ROLE_QUALIFICATION_AUTHORITY'
                samplingFloors = [pscustomobject]@{}
                evidenceReusePolicy = [pscustomobject]@{ policyVersion = '1.0.0'; status = 'frozen' }
                tests = @()
            }
        }
        'EVIDENCE_RECORD' {
            [ordered]@{
                schemaVersion = '2.0.1'
                recordKind = 'measurement-summary'
                provenance = 'T0'
                evidenceUse = 'gate-or-verdict'
                testRef = 'test-controlled-benchmark-synthetic-1'
                conditionRef = 'controlled-condition-synthetic-1'
                testPackVersion = 'test-pack-synthetic-1'
                tool = [pscustomobject]@{ name = 'synthetic-evidence-tool'; version = '1.0.0' }
                subjectRef = 'manifest-synthetic-1'
                controlRole = 'candidate'
                subject = [pscustomobject][ordered]@{
                    kind = 'device'
                    role = 'candidate'
                    deviceId = "device-$RecordId"
                    configurationIdentity = 'configuration-synthetic-1'
                    manifestRef = 'manifest-synthetic-1'
                }
                baselineFingerprint = New-TestDigest 'b'
                baseline = [pscustomobject][ordered]@{
                    biosVersion = 'BIOS-SYNTHETIC-1'
                    windowsBuild = '26100.9999'
                    driverVersions = [pscustomobject]@{ chipset = 'DRIVER-SYNTHETIC-1' }
                    agentVersions = [pscustomobject]@{ management = 'AGENT-SYNTHETIC-1' }
                    image = 'IMAGE-SYNTHETIC-1'
                    baselineFingerprintSha256 = New-TestDigest 'b'
                }
                timestamp = '2026-08-27T10:00:00Z'
                admission = [pscustomobject][ordered]@{ mode = 'fresh'; admittedAt = '2026-08-27T11:00:00Z' }
                result = [pscustomobject][ordered]@{ status = 'PASS'; state = 'PASS' }
                distribution = [pscustomobject][ordered]@{
                    unitCount = 1
                    runCount = 1
                    runs = @([pscustomobject][ordered]@{ runId = "run-$RecordId-1"; deviceId = "device-$RecordId" })
                    summary = [pscustomobject][ordered]@{
                        kind = 'numeric'
                        median = 100
                        spread = [pscustomobject][ordered]@{ kind = 'range'; min = 95; max = 105 }
                    }
                    runVariationPct = 0.03
                    betweenUnitVariationPct = 0
                    missingResults = [pscustomobject][ordered]@{ count = 0; reasons = @() }
                    excludedOutliers = @()
                }
                coverage = [pscustomobject]@{
                    scope = 'Synthetic admitted fixture scope.'
                    plannedUnits = 1
                    observedUnits = 1
                    plannedRuns = 1
                    observedRuns = 1
                    percent = 100
                    gaps = @()
                }
                dataQuality = 'controlled-delta'
                artifacts = @([pscustomobject]@{
                    path = "synthetic/$RecordId.json"
                    sha256 = Get-Sha256TokenFromText -Text "portable-evidence-artifact:$RecordId"
                    bytes = 1
                })
                knownLimitations = @()
                distributionRef = "distribution-$RecordId"
            }
        }
        'THRESHOLD_POLICY' {
            [ordered]@{
                schemaVersion = '2.0.1'
                version = '1.0.0'
                status = 'frozen'
                frozenAt = '2026-08-27T08:00:00Z'
                approvedBy = 'ROLE_QUALIFICATION_AUTHORITY'
                thresholds = [pscustomobject]@{}
            }
        }
        'VERDICT_RECORD' {
            [ordered]@{
                schemaVersion = '2.0.1'
                recordStage = 'phase5-final'
                status = 'approved-and-immutable'
                immutableAt = '2026-08-27T12:00:00Z'
                manifestRef = $(if ($activation -or $RecordId -match 'activation|phase3') { 'manifest-activation-synthetic-1' } else { 'manifest-synthetic-1' })
                qualificationAuthority = 'ROLE_QUALIFICATION_AUTHORITY'
                approvers = @('ROLE_QUALIFICATION_AUTHORITY','ROLE_SECURITY_APPROVER')
                evidenceReleases = @('candidate-release-synthetic-1')
                qualificationAuthorityApprovalRef = "qualification-authority-approval-$RecordId"
                qualificationAuthorityApprovalDigest = New-TestDigest '6'
            }
        }
    }
}

function ConvertTo-TestJsonPointerToken {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Token)
    return $Token.Replace('~', '~0').Replace('/', '~1')
}

function New-TestPortableProjectionRecord {
    param(
        [Parameter(Mandatory = $true)][string]$RecordId,
        [Parameter(Mandatory = $true)][string]$LegacyRecordType,
        [string]$ValidUntil,
        [hashtable]$Fields
    )
    $metadata = switch ($LegacyRecordType) {
        'candidate-manifest' { Get-PortableContractMetadata -PortableRecordType 'CANDIDATE_MANIFEST' }
        'test-plan' { Get-PortableContractMetadata -PortableRecordType 'TEST_PLAN' }
        'evidence-record' { Get-PortableContractMetadata -PortableRecordType 'EVIDENCE_RECORD' }
        'threshold-policy' { Get-PortableContractMetadata -PortableRecordType 'THRESHOLD_POLICY' }
        'verdict-record' { Get-PortableContractMetadata -PortableRecordType 'VERDICT_RECORD' }
    }
    $portableRecordType = switch ($LegacyRecordType) {
        'candidate-manifest' { 'CANDIDATE_MANIFEST' }
        'test-plan' { 'TEST_PLAN' }
        'evidence-record' { 'EVIDENCE_RECORD' }
        'threshold-policy' { 'THRESHOLD_POLICY' }
        'verdict-record' { 'VERDICT_RECORD' }
    }
    $sourceFields = Get-TestPortableDefaultFields -RecordId $RecordId -PortableRecordType $portableRecordType
    foreach ($key in $Fields.Keys) { $sourceFields[$key] = $Fields[$key] }
    if ($portableRecordType -ceq 'EVIDENCE_RECORD') {
        if ($sourceFields.Contains('freshnessBinding') -and $sourceFields.freshnessBinding -is [pscustomobject]) {
            $sourceFields.timestamp = [string]$sourceFields.freshnessBinding.observedAt
            $sourceFields.admission = [pscustomobject][ordered]@{
                mode = 'fresh'
                admittedAt = [string]$sourceFields.freshnessBinding.admittedAt
            }
        }
        if ($sourceFields.result -isnot [pscustomobject]) {
            $sourceFields.result = [pscustomobject][ordered]@{ status = 'PASS'; state = $sourceFields.result }
        }
        if ([string]$sourceFields.provenance -cne 'T0') {
            $sourceFields.recordKind = 'documentary-claim'
            $sourceFields.evidenceUse = 'context'
            $sourceFields.subject = [pscustomobject][ordered]@{
                kind = 'configuration'
                configurationIdentity = "configuration-$RecordId"
                sourceDocumentRef = "source-$RecordId"
            }
            $sourceFields.baseline = [pscustomobject][ordered]@{
                configurationEnvelopeRef = "envelope-$RecordId"
                platformApplicability = @('platform-synthetic-1')
                baselineFingerprintSha256 = New-TestDigest 'b'
            }
            $sourceFields.dataQuality = 'document'
            $sourceFields.Remove('distribution')
            $sourceFields.Remove('distributionRef')
            $sourceFields.Remove('subjectRef')
            $sourceFields.Remove('controlRole')
        }
        $normalizedArtifacts = New-Object System.Collections.ArrayList
        $artifactIndex = 0
        foreach ($artifact in @($sourceFields.artifacts)) {
            $artifactIndex++
            [void]$normalizedArtifacts.Add([pscustomobject][ordered]@{
                path = if ($null -ne $artifact.PSObject.Properties['path']) { [string]$artifact.path } else { "synthetic/$RecordId-$artifactIndex.json" }
                sha256 = [string]$artifact.sha256
                bytes = if ($null -ne $artifact.PSObject.Properties['bytes']) { [int64]$artifact.bytes } else { [int64]1 }
            })
        }
        $sourceFields.artifacts = @($normalizedArtifacts)
    }
    $fieldContract = Get-PortableProjectionFieldContract -PortableRecordType $portableRecordType
    if ($fieldContract.PSObject.Properties['NestedRootFieldPointers']) {
        foreach ($nestedField in $fieldContract.NestedRootFieldPointers.PSObject.Properties) {
            if (-not $sourceFields.Contains([string]$nestedField.Name)) { continue }
            $tokens = @(([string]$nestedField.Value).TrimStart('/').Split('/'))
            if ($tokens.Count -ne 2) { throw "Portable fixture nested pointer $($nestedField.Value) is not a frozen two-token mapping." }
            $rootField = [string]$tokens[0]
            $leafField = [string]$tokens[1]
            $rootValue = [ordered]@{}
            if ($sourceFields.Contains($rootField) -and $null -ne $sourceFields[$rootField]) {
                foreach ($property in $sourceFields[$rootField].PSObject.Properties) {
                    $rootValue[[string]$property.Name] = $property.Value
                }
            }
            $rootValue[$leafField] = $sourceFields[[string]$nestedField.Name]
            $sourceFields[$rootField] = [pscustomobject]$rootValue
        }
    }
    $idField = ([string]$metadata.IdPointer).Substring(1)
    $sourceDocument = [ordered]@{ $idField = $RecordId }
    foreach ($fieldName in Get-TestPortableProjectionFields -PortableRecordType $portableRecordType) {
        if (-not $sourceFields.Contains($fieldName)) { continue }
        if (@($fieldContract.RootFields) -ccontains $fieldName) {
            $sourceDocument[$fieldName] = $sourceFields[$fieldName]
            continue
        }
        if (@($fieldContract.OperationsExtensionFields) -ccontains $fieldName) {
            if (-not $sourceDocument.Contains('extensions')) {
                $sourceDocument.extensions = [ordered]@{}
            }
            if (-not $sourceDocument.extensions.Contains('operationsBlueprintV1')) {
                $sourceDocument.extensions.operationsBlueprintV1 = [ordered]@{}
            }
            $sourceDocument.extensions.operationsBlueprintV1[$fieldName] = $sourceFields[$fieldName]
        }
    }
    $sourceDocument = Copy-TestObject -InputObject ([pscustomobject]$sourceDocument)
    $sourceKey = (Get-Sha256TokenFromText -Text "portable-source:$RecordId").Substring(7)
    $sourceRecordRef = "private://portable-sources/$sourceKey"
    $sourceRecordDigest = Get-CanonicalPayloadDigest -Payload $sourceDocument
    $script:PortableSourceDocumentFixtures[$sourceRecordRef] = $sourceDocument
    $freshnessBinding = [pscustomobject][ordered]@{
        observedAt = '2026-08-27T10:00:00Z'
        admittedAt = '2026-08-27T11:00:00Z'
        policyRef = 'private://policies/portable-contract-admission-synthetic-1'
        maxAgeDays = 1
        dependencySnapshotRef = "private://portable-source-snapshots/$sourceKey"
        dependencySnapshotDigest = $sourceRecordDigest
        dependencyStatus = 'MATCH'
    }
    if ($portableRecordType -ceq 'VERDICT_RECORD' -and
        $sourceFields.Contains('freshnessBinding') -and
        $sourceFields.freshnessBinding -is [pscustomobject]) {
        $freshnessBinding = Copy-TestObject -InputObject $sourceFields.freshnessBinding
    }
    $validationId = 'portable-validation-' + $sourceKey.Substring(0, 24)
    $validationFields = @{
        schemaVersion = '1.0.0'
        recordStage = 'PORTABLE_CONTRACT_VALIDATION'
        status = 'VERIFIED'
        portableRecordType = $portableRecordType
        sourceRecordRef = $sourceRecordRef
        sourceRecordDigest = $sourceRecordDigest
        schemaUri = [string]$metadata.SchemaUri
        schemaDigest = [string]$metadata.SchemaDigest
        validatorReleaseRef = 'private://validator-releases/portable-contract-validator-synthetic-1'
        validatorReleaseDigest = Get-Sha256TokenFromText -Text 'portable-contract-validator-synthetic-1'
        validationInputDigest = $null
        validationIssueCount = 0
        validationIssueSetDigest = Get-CanonicalPayloadDigest -Payload ([object[]]@())
        validationResultDigest = $null
        protectedAttestationRef = "private://portable-attestations/$sourceKey"
        protectedAttestationDigest = Get-Sha256TokenFromText -Text "portable-attestation:$RecordId"
        protectedAttestationSubjectDigest = $null
        protectedAttestationStatus = 'SYNTHETIC'
        validatedAt = '2026-08-27T11:00:00Z'
        freshnessBinding = Copy-TestObject $freshnessBinding
        validationMode = 'TEST'
        resolverStatus = 'SYNTHETIC'
        authorizationEffect = 'NONE'
    }
    $validationProjection = [pscustomobject]$validationFields
    $validationFields.validationInputDigest = Get-PortableContractValidationInputDigest -ValidationRecord $validationProjection
    $validationFields.validationResultDigest = Get-PortableContractValidationResultDigest -ValidationRecord ([pscustomobject]$validationFields)
    $validationFields.protectedAttestationSubjectDigest = $validationFields.validationResultDigest
    $validationRecord = New-CanonicalRecord -RecordId $validationId -RecordType 'portable-contract-validation-record' `
        -ValidUntil $ValidUntil -Fields $validationFields
    $script:PortableValidationRecordFixtures[$validationId] = $validationRecord

    $bindings = New-Object System.Collections.ArrayList
    foreach ($fieldName in Get-TestPortableProjectionFields -PortableRecordType $portableRecordType) {
        if (-not $sourceFields.Contains($fieldName)) { continue }
        $pointer = Get-PortableProjectionFieldPointer -FieldContract $fieldContract -ProjectionField $fieldName
        if ([string]::IsNullOrEmpty([string]$pointer)) { throw "Portable fixture field $fieldName has no frozen projection pointer." }
        [void]$bindings.Add([pscustomobject][ordered]@{
            projectionField = $fieldName
            pointer = $pointer
            value = $sourceFields[$fieldName]
            valueDigest = Get-CanonicalPayloadDigest -Payload $sourceFields[$fieldName]
        })
    }
    $projectionFields = @{
        schemaVersion = '1.0.0'
        recordStage = 'PORTABLE_CONTRACT_PROJECTION'
        status = 'VERIFIED'
        portableRecordType = $portableRecordType
        sourceRecordRef = $sourceRecordRef
        sourceRecordDigest = $sourceRecordDigest
        sourceCanonicalIdPointer = [string]$metadata.IdPointer
        sourceCanonicalIdValue = $RecordId
        projectionPointers = @($bindings | ForEach-Object { [string]$_.pointer })
        projection = [pscustomobject][ordered]@{ projectionType = $portableRecordType; bindings = @($bindings) }
        projectionDigest = Get-PortableContractProjectionDigest -Bindings @($bindings)
        validationRecordRef = $validationId
        validationRecordDigest = [string]$validationRecord.contentDigest
        projectedAt = '2026-08-27T11:01:00Z'
        freshnessBinding = Copy-TestObject $freshnessBinding
        validationMode = 'TEST'
        resolverStatus = 'SYNTHETIC'
        authorizationEffect = 'NONE'
    }
    if ($portableRecordType -ceq 'VERDICT_RECORD' -and
        $sourceFields.Contains('freshnessBinding') -and
        $sourceFields.freshnessBinding -is [pscustomobject]) {
        $projectionFields.freshnessBinding = Copy-TestObject -InputObject $sourceFields.freshnessBinding
    }
    if ($portableRecordType -ceq 'EVIDENCE_RECORD') {
        $projectionFields.provenance = [string]$sourceFields.provenance
        if ([string]$sourceFields.provenance -ceq 'T2') {
            $projectionFields.corroborationRef = $sourceFields.corroborationRef
        }
    }
    return New-CanonicalRecord -RecordId $RecordId -RecordType 'portable-contract-projection-record' `
        -Pointers @('/projection') -ValidUntil $ValidUntil -Fields $projectionFields
}

function Get-TestRecordPayloadValue {
    param([Parameter(Mandatory = $true)]$Record, [Parameter(Mandatory = $true)][string]$FieldName)
    if ([string]$Record.recordType -ceq 'portable-contract-projection-record') {
        $matches = @($Record.payload.projection.bindings | Where-Object { [string]$_.projectionField -ceq $FieldName })
        if ($matches.Count -eq 1) { return $matches[0].value }
        return $null
    }
    return $Record.payload.PSObject.Properties[$FieldName].Value
}

function Set-TestRecordPayloadValue {
    param(
        [Parameter(Mandatory = $true)]$Record,
        [Parameter(Mandatory = $true)][string]$FieldName,
        [AllowNull()]$Value
    )
    if ([string]$Record.recordType -ceq 'portable-contract-projection-record') {
        $binding = @($Record.payload.projection.bindings | Where-Object { [string]$_.projectionField -ceq $FieldName })[0]
        if ($null -eq $binding) { throw "Portable fixture $($Record.recordId) has no $FieldName projection binding." }
        $binding.value = $Value
        return
    }
    $payloadProperty = $Record.payload.PSObject.Properties[$FieldName]
    if ($null -eq $payloadProperty) {
        $Record.payload | Add-Member -NotePropertyName $FieldName -NotePropertyValue $Value
    }
    else {
        $payloadProperty.Value = $Value
    }
}

function Remove-TestRecordPayloadValue {
    param(
        [Parameter(Mandatory = $true)]$Record,
        [Parameter(Mandatory = $true)][string]$FieldName
    )
    if ([string]$Record.recordType -ceq 'portable-contract-projection-record') {
        $Record.payload.projection.bindings = @($Record.payload.projection.bindings | Where-Object {
            [string]$_.projectionField -cne $FieldName
        })
        return
    }
    if ($null -ne $Record.payload.PSObject.Properties[$FieldName]) {
        $Record.payload.PSObject.Properties.Remove($FieldName)
    }
}

function Get-TestPortableValidationRecords {
    param([Parameter(Mandatory = $true)][object[]]$RecordIndex)
    $result = New-Object System.Collections.ArrayList
    $seen = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($record in @($RecordIndex | Where-Object { [string]$_.recordType -ceq 'portable-contract-projection-record' })) {
        $validationId = [string]$record.payload.validationRecordRef
        if ($seen.Add($validationId) -and $script:PortableValidationRecordFixtures.ContainsKey($validationId)) {
            [void]$result.Add($script:PortableValidationRecordFixtures[$validationId])
        }
    }
    return @($result)
}

function Update-TestPortableSourceAttestation {
    param([Parameter(Mandatory = $true)]$ProjectionRecord)

    $metadata = Get-PortableContractMetadata -PortableRecordType ([string]$ProjectionRecord.payload.portableRecordType)
    $sourceErrors = New-Object System.Collections.ArrayList
    $boundSource = New-PortableProjectionSourcePayload -Bindings @($ProjectionRecord.payload.projection.bindings) `
        -Errors $sourceErrors -Context "portable fixture $($ProjectionRecord.recordId)"
    if ($sourceErrors.Count -ne 0) {
        throw "Portable fixture source reconstruction failed: $(@($sourceErrors.code) -join ', ')."
    }
    $sourceDocumentFields = [ordered]@{
        (([string]$metadata.IdPointer).Substring(1)) = [string]$ProjectionRecord.payload.sourceCanonicalIdValue
    }
    foreach ($property in $boundSource.PSObject.Properties) {
        $sourceDocumentFields[[string]$property.Name] = $property.Value
    }
    $sourceDocument = Copy-TestObject -InputObject ([pscustomobject]$sourceDocumentFields)
    $sourceDigest = Get-CanonicalPayloadDigest -Payload $sourceDocument
    if (-not (Test-Sha256Token $sourceDigest)) { throw "Portable fixture $($ProjectionRecord.recordId) source cannot be canonically hashed." }
    $script:PortableSourceDocumentFixtures[[string]$ProjectionRecord.payload.sourceRecordRef] = $sourceDocument
    $ProjectionRecord.payload.sourceRecordDigest = $sourceDigest
    if ([string]$ProjectionRecord.payload.portableRecordType -cne 'VERDICT_RECORD') {
        $ProjectionRecord.payload.freshnessBinding.dependencySnapshotDigest = $sourceDigest
    }

    $validationId = [string]$ProjectionRecord.payload.validationRecordRef
    if (-not $script:PortableValidationRecordFixtures.ContainsKey($validationId)) {
        throw "Portable fixture $($ProjectionRecord.recordId) has no retained validation record $validationId."
    }
    $validationRecord = $script:PortableValidationRecordFixtures[$validationId]
    $validationRecord.payload.sourceRecordDigest = $sourceDigest
    if ([string]$ProjectionRecord.payload.portableRecordType -cne 'VERDICT_RECORD') {
        $validationRecord.payload.freshnessBinding.dependencySnapshotDigest = $sourceDigest
    }
    $validationRecord.payload.validationInputDigest = Get-PortableContractValidationInputDigest -ValidationRecord $validationRecord.payload
    $validationRecord.payload.validationResultDigest = Get-PortableContractValidationResultDigest -ValidationRecord $validationRecord.payload
    $validationRecord.payload.protectedAttestationSubjectDigest = $validationRecord.payload.validationResultDigest
    $validationRecord.payload.protectedAttestationDigest = Get-Sha256TokenFromText `
        -Text "portable-attestation:$($ProjectionRecord.recordId):$($validationRecord.payload.validationResultDigest)"
    Update-CanonicalRecordBinding $validationRecord
    $ProjectionRecord.payload.validationRecordDigest = [string]$validationRecord.contentDigest
}

function New-CanonicalRecord {
    param(
        [Parameter(Mandatory = $true)][string]$RecordId,
        [Parameter(Mandatory = $true)][string]$RecordType,
        [string[]]$Pointers = @('/record'),
        [string]$ValidUntil = '2026-08-28T00:00:00Z',
        [hashtable]$Fields = @{}
    )
    if (Test-IsLegacyPortableRecordType -RecordType $RecordType) {
        return New-TestPortableProjectionRecord -RecordId $RecordId -LegacyRecordType $RecordType `
            -ValidUntil $ValidUntil -Fields $Fields
    }
    $validFrom = '2026-08-27T00:00:00Z'
    $payloadFields = [ordered]@{
        record = $RecordId
        validFrom = $validFrom
        validUntil = $ValidUntil
    }
    foreach ($key in $Fields.Keys) { $payloadFields[$key] = $Fields[$key] }
    # Each canonical fixture owns its payload graph. Deep-copying here prevents a
    # mutation of one evidence source from silently changing a release or sibling
    # record that was initialized from the same freshness/target object instance.
    $payload = Copy-TestObject -InputObject ([pscustomobject]$payloadFields)
    $digest = Get-CanonicalPayloadDigest -Payload $payload
    $recordKey = (Get-Sha256TokenFromText -Text "fixture-record:$RecordId").Substring(7)
    $record = [pscustomobject][ordered]@{
        recordId = $RecordId
        recordType = $RecordType
        contentDigest = $digest
        validated = $true
        freshness = 'CURRENT'
        validFrom = $validFrom
        validUntil = $ValidUntil
        pointers = @($Pointers)
        payload = $payload
        immutableArtifactRef = "private://test-fixtures/artifacts/$recordKey"
        envelopeProfile = 'operations-canonical-envelope/1.0.0'
        envelopeCoreDigest = $null
        attestationRef = "private://test-fixtures/attestations/$recordKey"
        attestationDigest = $null
        attestationSubjectDigest = $null
        attestationStatus = 'VERIFIED'
    }
    $record.envelopeCoreDigest = Get-CanonicalEnvelopeCoreDigest -Record $record
    $record.attestationSubjectDigest = $record.envelopeCoreDigest
    $record.attestationDigest = Get-Sha256TokenFromText -Text "fixture-attestation:${RecordId}:$($record.envelopeCoreDigest)"
    $record
}

function Initialize-TestEvidenceReleaseSubject {
    param([Parameter(Mandatory = $true)]$ReleaseRecord)

    if ([string]$ReleaseRecord.recordType -cne 'evidence-release') {
        throw "Fixture $($ReleaseRecord.recordId) is not an evidence release."
    }
    Set-TestRecordPayloadValue -Record $ReleaseRecord -FieldName memberRecordBindings -Value @()
    Set-TestRecordPayloadValue -Record $ReleaseRecord -FieldName releaseSubjectDigest -Value (New-TestDigest '0')
    Set-TestRecordPayloadValue -Record $ReleaseRecord -FieldName releaseSubjectDigest `
        -Value (Get-EvidenceReleaseSubjectDigest -ReleaseRecord $ReleaseRecord)
    Update-CanonicalRecordBinding $ReleaseRecord
    return $ReleaseRecord
}

function Complete-TestEvidenceReleaseMembership {
    param(
        [Parameter(Mandatory = $true)]$ReleaseRecord,
        [Parameter(Mandatory = $true)][object[]]$RecordIndex
    )

    $recordMap = [System.Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
    foreach ($record in @($RecordIndex)) {
        if ($null -ne $record -and -not $recordMap.ContainsKey([string]$record.recordId)) {
            $recordMap.Add([string]$record.recordId, $record)
        }
    }
    $bindings = New-Object System.Collections.ArrayList
    foreach ($memberId in @($ReleaseRecord.payload.memberRecordIds)) {
        $wholeMemberId = [string]$memberId
        if ([string]::IsNullOrWhiteSpace($wholeMemberId) -or $wholeMemberId.Contains('#') -or
            -not $recordMap.ContainsKey($wholeMemberId)) {
            throw "Evidence release $($ReleaseRecord.recordId) has an unresolved non-whole member '$wholeMemberId'."
        }
        $memberRecord = $recordMap[$wholeMemberId]
        [void]$bindings.Add([pscustomobject][ordered]@{
            recordRef = $wholeMemberId
            contentDigest = [string]$memberRecord.contentDigest
        })
    }
    Set-TestRecordPayloadValue -Record $ReleaseRecord -FieldName memberRecordBindings -Value @($bindings)
    Update-CanonicalRecordBinding $ReleaseRecord
    return $ReleaseRecord
}

function Update-CanonicalRecordBinding {
    param([Parameter(Mandatory = $true)]$Record)
    if ([string]$Record.recordType -ceq 'portable-contract-projection-record') {
        foreach ($binding in @($Record.payload.projection.bindings)) {
            $binding.valueDigest = Get-CanonicalPayloadDigest -Payload $binding.value
        }
        $Record.payload.projectionPointers = @($Record.payload.projection.bindings | ForEach-Object { [string]$_.pointer })
        $Record.payload.projectionDigest = Get-PortableContractProjectionDigest -Bindings @($Record.payload.projection.bindings)
        if ([string]$Record.payload.portableRecordType -ceq 'EVIDENCE_RECORD') {
            $Record.payload.provenance = [string](Get-TestRecordPayloadValue -Record $Record -FieldName 'provenance')
            $corroborationBinding = @($Record.payload.projection.bindings | Where-Object projectionField -CEQ 'corroborationRef')
            if ([string]$Record.payload.provenance -ceq 'T2' -and $corroborationBinding.Count -eq 1) {
                if ($null -eq $Record.payload.PSObject.Properties['corroborationRef']) {
                    $Record.payload | Add-Member -NotePropertyName corroborationRef -NotePropertyValue $corroborationBinding[0].value
                }
                else { $Record.payload.corroborationRef = $corroborationBinding[0].value }
            }
            elseif ($null -ne $Record.payload.PSObject.Properties['corroborationRef']) {
                $Record.payload.PSObject.Properties.Remove('corroborationRef')
            }
        }
        Update-TestPortableSourceAttestation -ProjectionRecord $Record
    }
    $Record.contentDigest = Get-CanonicalPayloadDigest -Payload $Record.payload
    $Record.envelopeCoreDigest = Get-CanonicalEnvelopeCoreDigest -Record $Record
    $Record.attestationSubjectDigest = $Record.envelopeCoreDigest
    $Record.attestationDigest = Get-Sha256TokenFromText -Text "fixture-attestation:$($Record.recordId):$($Record.envelopeCoreDigest)"
}

function New-EvidenceRecord {
    param(
        [Parameter(Mandatory = $true)][string]$RecordId,
        [Parameter(Mandatory = $true)][string]$ClaimId,
        [ValidateSet('T0', 'T1', 'T2')][string]$Provenance = 'T0',
        [string]$CorroborationRef,
        [hashtable]$Fields = @{}
    )
    $recordFields = @{ claimId = $ClaimId; provenance = $Provenance }
    if (-not [string]::IsNullOrWhiteSpace($CorroborationRef)) {
        $recordFields.corroborationRef = [pscustomobject][ordered]@{
            recordRef = $CorroborationRef
            expectedProvenance = 'T0'
            claimScope = $ClaimId
        }
    }
    foreach ($key in $Fields.Keys) { $recordFields[$key] = $Fields[$key] }
    if (-not $recordFields.ContainsKey('result')) {
        $recordFields.result = [pscustomobject][ordered]@{ status = 'PASS'; state = 'PASS' }
    }
    $pointers = @('/result/status')
    if ($recordFields.ContainsKey('issueStatement')) { $pointers += '/issueStatement' }
    New-CanonicalRecord -RecordId $RecordId -RecordType 'evidence-record' -Pointers $pointers -Fields $recordFields
}

function New-DistributionRecord {
    param(
        [Parameter(Mandatory = $true)][string]$RecordId,
        [Parameter(Mandatory = $true)][string]$SourceEvidenceRef,
        [Parameter(Mandatory = $true)]$Phase0TestPlanRecord,
        [string]$TestClass = 'controlled-benchmark',
        [string]$TestRef,
        [string]$ConditionRef,
        [string]$BaselineFingerprint = (New-TestDigest 'b'),
        [int]$UnitCount = 0,
        [int]$RunCount = 0,
        [string]$SourceEvidenceDigest = (New-TestDigest 'd'),
        [string]$SourceEvidenceReleaseRef = 'evidence-release-synthetic-placeholder',
        [string]$SourceEvidenceReleaseSubjectDigest = (New-TestDigest 'e')
    )
    $testPlanSamplingFloors = Get-TestRecordPayloadValue -Record $Phase0TestPlanRecord -FieldName 'samplingFloors'
    $testPlanDefinitions = @(Get-TestRecordPayloadValue -Record $Phase0TestPlanRecord -FieldName 'tests')
    $floorProperty = $testPlanSamplingFloors.PSObject.Properties[$TestClass]
    if ($null -eq $floorProperty -or $floorProperty.Value -isnot [pscustomobject]) {
        throw "The Phase 0 test plan does not define the $TestClass sampling floor."
    }
    $floor = $floorProperty.Value
    $matchingTests = @(if ([string]::IsNullOrWhiteSpace($TestRef)) {
        $testPlanDefinitions | Where-Object { [string]$_.class -ceq $TestClass }
    }
    else {
        $testPlanDefinitions | Where-Object { [string]$_.testId -ceq $TestRef }
    })
    if ($matchingTests.Count -ne 1 -or [string]$matchingTests[0].class -cne $TestClass) {
        throw "The Phase 0 test plan does not define exactly one $TestClass test matching '$TestRef'."
    }
    $testDefinition = $matchingTests[0]
    if ([string]::IsNullOrWhiteSpace($ConditionRef)) {
        $conditions = @($testDefinition.conditions)
        if ($conditions.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$conditions[0].conditionId)) {
            throw "The Phase 0 test definition $($testDefinition.testId) does not define exactly one fixture condition."
        }
        $ConditionRef = [string]$conditions[0].conditionId
    }
    $requiredUnits = [int]$floor.minUnits
    $requiredRuns = [int]$floor.minRepetitionsPerUnit
    if ($UnitCount -le 0) { $UnitCount = $requiredUnits }
    if ($RunCount -le 0) { $RunCount = $requiredUnits * $requiredRuns }
    $baseRuns = [Math]::Floor($RunCount / $UnitCount)
    $extraRuns = $RunCount % $UnitCount
    $perUnitRunCounts = New-Object System.Collections.ArrayList
    for ($unitIndex = 0; $unitIndex -lt $UnitCount; $unitIndex++) {
        $acceptedRunCount = [int]$baseRuns + $(if ($unitIndex -lt $extraRuns) { 1 } else { 0 })
        [void]$perUnitRunCounts.Add([pscustomobject][ordered]@{
            unitRef = 'private://fleet-units/sha256/' + (Get-Sha256TokenFromText -Text "${RecordId}:unit:$unitIndex").Substring(7)
            acceptedRunCount = $acceptedRunCount
        })
    }
    $distributionRecord = New-CanonicalRecord $RecordId 'distribution-record' @('/median', '/coverage') -Fields @{
        sourceEvidenceRef = $SourceEvidenceRef
        sourceEvidenceDigest = $SourceEvidenceDigest
        sourceEvidenceReleaseRef = $SourceEvidenceReleaseRef
        sourceEvidenceReleaseSubjectDigest = $SourceEvidenceReleaseSubjectDigest
        testRef = [string]$testDefinition.testId
        testDefinitionDigest = Get-CanonicalPayloadDigest -Payload $testDefinition
        conditionRef = $ConditionRef
        baselineFingerprint = $BaselineFingerprint
        testClass = $TestClass
        metricId = 'synthetic-normalized-score'
        unit = 'normalized-points'
        statisticDirection = 'DESCRIPTIVE_ONLY'
        unitCount = $UnitCount
        runCount = $RunCount
        perUnitRunCounts = @($perUnitRunCounts)
        requiredUnits = $RequiredUnits
        requiredRuns = $RequiredRuns
        phase0TestPlanRef = [string]$Phase0TestPlanRecord.recordId
        phase0TestPlanDigest = [string]$Phase0TestPlanRecord.contentDigest
        samplingFloorPointer = "#/samplingFloors/$TestClass"
        samplingFloorDigest = Get-CanonicalPayloadDigest -Payload $floor
        median = 100
        spread = [pscustomobject]@{ minimum = 95; maximum = 105 }
        runVariation = [pscustomobject]@{ minimum = 95; maximum = 105; coefficientOfVariation = 0.03 }
        coverage = [pscustomobject]@{ expected = $UnitCount; observed = $UnitCount; percent = 100 }
        missingResults = @([pscustomobject]@{ count = 0 })
        outliers = @([pscustomobject]@{ count = 0 })
        exclusions = @([pscustomobject]@{ count = 0 })
        samplingFloorStatus = 'PASS'
        distributionStatus = 'PASS'
    }
    # A derived distribution is created only after its source evidence has been
    # admitted and before the immutable release is issued.  The fixture's latest
    # admitted source is 10:30Z and every leadership release is issued at 11:30Z.
    $distributionRecord.validFrom = '2026-08-27T10:31:00Z'
    $distributionRecord.payload.validFrom = '2026-08-27T10:31:00Z'
    Update-CanonicalRecordBinding $distributionRecord
    return $distributionRecord
}

function New-TestPortableDistributionValue {
    param([Parameter(Mandatory = $true)]$DistributionRecord)

    $payload = $DistributionRecord.payload
    $runs = New-Object System.Collections.ArrayList
    foreach ($unit in @($payload.perUnitRunCounts)) {
        for ($runIndex = 1; $runIndex -le [int]$unit.acceptedRunCount; $runIndex++) {
            [void]$runs.Add([pscustomobject][ordered]@{
                runId = "$($DistributionRecord.recordId):$($unit.unitRef):$runIndex"
                deviceId = [string]$unit.unitRef
            })
        }
    }
    $missingCount = ([int]$payload.coverage.expected * [int]$payload.requiredRuns) - [int]$payload.runCount
    $missingReasons = @($payload.missingResults | Where-Object { [int]$_.count -gt 0 } | ForEach-Object { [string]$_.reason })
    $excludedOutliers = New-Object System.Collections.ArrayList
    foreach ($finding in @($payload.outliers | Where-Object { [int]$_.count -gt 0 })) {
        for ($index = 0; $index -lt [int]$finding.count; $index++) {
            [void]$excludedOutliers.Add([pscustomobject][ordered]@{ value = $null; reason = [string]$finding.reason })
        }
    }
    [pscustomobject][ordered]@{
        unitCount = [int]$payload.unitCount
        runCount = [int]$payload.runCount
        runs = @($runs)
        summary = [pscustomobject][ordered]@{
            kind = 'numeric'
            median = $payload.median
            spread = [pscustomobject][ordered]@{
                kind = 'range'
                min = $payload.spread.minimum
                max = $payload.spread.maximum
            }
        }
        runVariationPct = $payload.runVariation.coefficientOfVariation
        betweenUnitVariationPct = 0
        missingResults = [pscustomobject][ordered]@{ count = $missingCount; reasons = @($missingReasons) }
        excludedOutliers = @($excludedOutliers)
    }
}

function Set-TestPortableDistributionCrosswalk {
    param(
        [Parameter(Mandatory = $true)]$EvidenceRecord,
        [Parameter(Mandatory = $true)]$DistributionRecord
    )
    $distribution = $DistributionRecord.payload
    $plannedRuns = [int]$distribution.coverage.expected * [int]$distribution.requiredRuns
    $missingRuns = $plannedRuns - [int]$distribution.runCount
    Set-TestRecordPayloadValue -Record $EvidenceRecord -FieldName 'distribution' `
        -Value (New-TestPortableDistributionValue -DistributionRecord $DistributionRecord)
    Set-TestRecordPayloadValue -Record $EvidenceRecord -FieldName 'coverage' -Value ([pscustomobject][ordered]@{
        scope = 'Exact portable-to-operations distribution cohort.'
        plannedUnits = [int]$distribution.coverage.expected
        observedUnits = [int]$distribution.coverage.observed
        plannedRuns = $plannedRuns
        observedRuns = [int]$distribution.runCount
        percent = if ([int]$distribution.coverage.expected -gt 0) {
            [Math]::Round((100.0 * [int]$distribution.coverage.observed / [int]$distribution.coverage.expected), 13)
        }
        else { 0 }
        gaps = if ($missingRuns -gt 0) { @('Governed missing accepted runs remain.') } else { @() }
    })
    Update-CanonicalRecordBinding $EvidenceRecord
}

function New-LeadershipDependencySnapshotFixture {
    [pscustomobject][ordered]@{
        windowsBuild = '26100.9999'
        biosVersion = 'BIOS-SYNTHETIC-1'
        driverPackVersion = 'DRIVER-PACK-SYNTHETIC-1'
        corporateImageVersion = 'IMAGE-SYNTHETIC-1'
        securityAgentSetDigest = (New-TestDigest '6')
        conditionSetDigest = (New-TestDigest '7')
        testPackVersion = 'test-pack-synthetic-1'
    }
}

function New-LeadershipFreshnessFixture {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet('personaNeed', 'currentFleetIssue', 'candidateComparison', 'businessEffect', 'recommendation')]
        [string]$LinkName,
        [string]$ObservedAt,
        [string]$AdmittedAt,
        [int]$MaxAgeDays
    )
    if ([string]::IsNullOrWhiteSpace($ObservedAt)) {
        $ObservedAt = switch ($LinkName) {
            'personaNeed' { '2026-08-25T09:00:00Z' }
            'currentFleetIssue' { '2026-03-31T00:00:00Z' }
            'candidateComparison' { '2026-08-26T08:00:00Z' }
            'businessEffect' { '2026-03-31T00:00:00Z' }
            'recommendation' { '2026-08-27T11:30:00Z' }
        }
    }
    if ([string]::IsNullOrWhiteSpace($AdmittedAt)) {
        $AdmittedAt = switch ($LinkName) {
            'personaNeed' { '2026-08-27T10:00:00Z' }
            'currentFleetIssue' { '2026-08-27T09:00:00Z' }
            'candidateComparison' { '2026-08-27T10:30:00Z' }
            'businessEffect' { '2026-08-27T11:00:00Z' }
            'recommendation' { '2026-08-27T11:55:00Z' }
        }
    }
    if (-not $PSBoundParameters.ContainsKey('MaxAgeDays')) {
        $MaxAgeDays = if ($LinkName -in @('currentFleetIssue', 'businessEffect')) { 365 } else { 30 }
    }
    $snapshot = New-LeadershipDependencySnapshotFixture
    $policyPointer = "/extensions/leadershipFreshness/$LinkName"
    [pscustomobject][ordered]@{
        status = 'CURRENT'
        observedAt = $ObservedAt
        admittedAt = $AdmittedAt
        evaluatedAt = '2026-08-27T12:29:00Z'
        maxAgeDays = $MaxAgeDays
        policyRef = "freshness-policy-synthetic-1#$policyPointer"
        dependencySnapshotRef = 'platform-baseline-synthetic-1#/dependencySnapshot'
        dependencySnapshot = $snapshot
        dependencySnapshotDigest = Get-CanonicalPayloadDigest -Payload $snapshot
        dependencyStatus = 'MATCH'
    }
}

function New-SourceFreshnessBinding {
    param(
        [Parameter(Mandatory = $true)]$Freshness,
        [string]$ObservedAt,
        [string]$AdmittedAt
    )
    if ([string]::IsNullOrWhiteSpace($ObservedAt)) { $ObservedAt = [string]$Freshness.observedAt }
    if ([string]::IsNullOrWhiteSpace($AdmittedAt)) { $AdmittedAt = [string]$Freshness.admittedAt }
    [pscustomobject][ordered]@{
        observedAt = $ObservedAt
        admittedAt = $AdmittedAt
        policyRef = [string]$Freshness.policyRef
        maxAgeDays = [int]$Freshness.maxAgeDays
        dependencySnapshotRef = [string]$Freshness.dependencySnapshotRef
        dependencySnapshotDigest = [string]$Freshness.dependencySnapshotDigest
        dependencyStatus = 'MATCH'
    }
}

function New-FleetPortfolioFreshnessBinding {
    param(
        [Parameter(Mandatory = $true)]$SourceFreshness,
        [Parameter(Mandatory = $true)]$ThresholdPolicyRecord,
        [Parameter(Mandatory = $true)]$PlatformBaselineRecord
    )
    $policyExtensions = Get-TestRecordPayloadValue -Record $ThresholdPolicyRecord -FieldName 'extensions'
    $policyObject = $policyExtensions.leadershipFreshness.currentFleetIssue
    $baselineSnapshot = Get-TestRecordPayloadValue -Record $PlatformBaselineRecord -FieldName 'dependencySnapshot'
    [pscustomobject][ordered]@{
        observedAt = [string]$SourceFreshness.observedAt
        admittedAt = [string]$SourceFreshness.admittedAt
        policyRef = [string]$ThresholdPolicyRecord.recordId
        policyDigest = [string]$ThresholdPolicyRecord.contentDigest
        policyObjectPointer = '/extensions/leadershipFreshness/currentFleetIssue'
        policyObjectDigest = Get-CanonicalPayloadDigest -Payload $policyObject
        maximumAgePointer = '/extensions/leadershipFreshness/currentFleetIssue/maxAgeDays'
        maximumAgeDays = [int]$policyObject.maxAgeDays
        platformBaselineRef = [string]$PlatformBaselineRecord.recordId
        platformBaselineDigest = [string]$PlatformBaselineRecord.contentDigest
        platformBaselinePointer = '/dependencySnapshot'
        dependencySnapshotRef = "$($PlatformBaselineRecord.recordId)#/dependencySnapshot"
        dependencySnapshotPointer = '/dependencySnapshot'
        dependencySnapshotDigest = Get-CanonicalPayloadDigest -Payload $baselineSnapshot
        dependencyStatus = 'MATCH'
    }
}

function New-FleetPopulationProofMetadata {
    param(
        [Parameter(Mandatory = $true)][string]$Seed,
        [Parameter(Mandatory = $true)]
        [ValidateSet('PORTFOLIO_COVERAGE', 'CLAIM_COVERAGE', 'CONFIGURATION_COHORT', 'PERSONA_ALLOCATION')]
        [string]$Purpose
    )

    [pscustomobject][ordered]@{
        proofScheme = 'HMAC_SHA256_SORTED_SET_COMMITMENT'
        proofVersion = '1.0.0'
        populationCommitmentKeyRef = 'private://fleet-population-commitment-keys/synthetic-1'
        populationCommitmentKeyVersion = 'synthetic-1.0.0'
        populationCanonicalization = 'UTF8_NFC_LENGTH_PREFIXED_SORTED'
        populationCanonicalizationVersion = '1.0.0'
        populationCommitmentPurpose = $Purpose
        populationCommitmentDomainDigest = Get-Sha256TokenFromText -Text "fleet-population-domain-placeholder:$Seed"
    }
}

function New-FleetCoverageCommitment {
    param(
        [Parameter(Mandatory = $true)][string]$Seed,
        [Parameter(Mandatory = $true)]
        [ValidateSet('PORTFOLIO_COVERAGE', 'CLAIM_COVERAGE')]
        [string]$Purpose,
        [string]$PlannedPopulationDigest,
        [int]$Planned = 40,
        [int]$Eligible = 35,
        [int]$Observed = 30,
        [int]$Missing = 5,
        [int]$Excluded = 5,
        [double]$Percent = 85.7142857142857,
        [ValidateSet('PASS', 'HOLD', 'FAIL', 'INCONCLUSIVE')][string]$Status = 'PASS'
    )

    if ([string]::IsNullOrWhiteSpace($PlannedPopulationDigest)) {
        $PlannedPopulationDigest = Get-Sha256TokenFromText -Text "fleet-population-set:${Seed}:planned"
    }
    $metadata = New-FleetPopulationProofMetadata -Seed $Seed -Purpose $Purpose
    [pscustomobject][ordered]@{
        planned = $Planned
        eligible = $Eligible
        observed = $Observed
        missing = $Missing
        excluded = $Excluded
        percent = $Percent
        plannedPopulationDigest = $PlannedPopulationDigest
        eligiblePopulationDigest = Get-Sha256TokenFromText -Text "fleet-population-set:${Seed}:eligible"
        observedPopulationDigest = Get-Sha256TokenFromText -Text "fleet-population-set:${Seed}:observed"
        missingPopulationDigest = Get-Sha256TokenFromText -Text "fleet-population-set:${Seed}:missing"
        excludedPopulationDigest = Get-Sha256TokenFromText -Text "fleet-population-set:${Seed}:excluded"
        populationPartitionProofRef = "private://fleet-population-proofs/$Seed/partition"
        populationPartitionProofDigest = Get-Sha256TokenFromText -Text "fleet-population-proof:${Seed}:partition"
        proofScheme = $metadata.proofScheme
        proofVersion = $metadata.proofVersion
        populationCommitmentKeyRef = $metadata.populationCommitmentKeyRef
        populationCommitmentKeyVersion = $metadata.populationCommitmentKeyVersion
        populationCanonicalization = $metadata.populationCanonicalization
        populationCanonicalizationVersion = $metadata.populationCanonicalizationVersion
        populationCommitmentPurpose = $metadata.populationCommitmentPurpose
        populationCommitmentDomainDigest = $metadata.populationCommitmentDomainDigest
        status = $Status
    }
}

function Set-FleetPopulationMetadata {
    param(
        [Parameter(Mandatory = $true)]$Target,
        [Parameter(Mandatory = $true)][string]$Seed,
        [Parameter(Mandatory = $true)]
        [ValidateSet('CONFIGURATION_COHORT', 'PERSONA_ALLOCATION')]
        [string]$Purpose
    )

    $metadata = New-FleetPopulationProofMetadata -Seed $Seed -Purpose $Purpose
    foreach ($property in $metadata.PSObject.Properties) {
        $Target | Add-Member -NotePropertyName ([string]$property.Name) -NotePropertyValue $property.Value
    }
    return $Target
}

function New-FrozenTestPlanFields {
    param(
        [Parameter(Mandatory = $true)][string]$ManifestRef,
        [Parameter(Mandatory = $true)][string]$ThresholdPolicyRef,
        [string]$ConditionId = 'controlled-condition-synthetic-1'
    )

    $definitions = [ordered]@{
        'component-identification' = @{ Units = 5; Runs = 1; PerRole = $true; Phase = 1 }
        'controlled-benchmark' = @{ Units = 3; Runs = 5; PerRole = $true; Phase = 3 }
        'sustained-performance' = @{ Units = 3; Runs = 3; PerRole = $true; Phase = 3 }
        'battery-standby' = @{ Units = 3; Runs = 3; PerRole = $true; Phase = 3 }
        'dock-reliability' = @{ Units = 3; Runs = 20; PerRole = $true; Phase = 3 }
        'application-compatibility' = @{ Units = 2; Runs = 2; PerRole = $false; Phase = 2 }
        'production-pilot' = @{ Units = 30; Runs = 10; PerRole = $false; Phase = 4 }
        'sentiment' = @{ Units = 24; Runs = 1; PerRole = $false; Phase = 4 }
        'corporate-floor' = @{ Units = 3; Runs = 3; PerRole = $true; Phase = 3 }
        'agent-state' = @{ Units = 3; Runs = 3; PerRole = $true; Phase = 3 }
    }
    $samplingFloors = [ordered]@{}
    $tests = New-Object System.Collections.ArrayList
    foreach ($className in $definitions.Keys) {
        $definition = $definitions[$className]
        $floor = [ordered]@{
            minUnits = [int]$definition.Units
            minRepetitionsPerUnit = [int]$definition.Runs
            perRole = [bool]$definition.PerRole
            samplingConcern = "Frozen $className sampling concern."
            selectionMethod = 'Predeclared representative deterministic fixture selection.'
            repetitionUnit = 'Completed protocol run.'
        }
        switch ($className) {
            'component-identification' { $floor.requiredStrata = @('known-lot', 'supplier') }
            'sustained-performance' { $floor.stabilizationRule = 'Run only after thermal stabilization.' }
            'battery-standby' { $floor.sessionDefinition = 'A complete charge-discharge or overnight session.' }
            'dock-reliability' { $floor.matrixCoverageRef = 'private://matrices/dock-synthetic-1' }
            'application-compatibility' { $floor.matrixCoverageRef = 'private://matrices/application-agent-synthetic-1' }
            'production-pilot' {
                $floor.minEvidenceDays = 10
                $floor.representative = $true
                $floor.volunteerOnly = $false
                $floor.stratumQuotas = [pscustomobject]@{ persona = [pscustomobject]@{ engineering = 30 }; region = [pscustomobject]@{ east = 15; west = 15 }; workPattern = [pscustomobject]@{ hybrid = 15; office = 15 } }
            }
            'sentiment' {
                $floor.minResponseRatePct = 80
                $floor.representative = $true
                $floor.volunteerOnly = $false
                $floor.stratumQuotas = [pscustomobject]@{ persona = [pscustomobject]@{ engineering = 24 }; region = [pscustomobject]@{ east = 12; west = 12 }; workPattern = [pscustomobject]@{ hybrid = 12; office = 12 } }
            }
            'corporate-floor' { $floor.imageBaselinesRef = 'private://baselines/corporate-image-synthetic-1' }
            'agent-state' { $floor.agentStateMatrixRef = 'private://matrices/agent-state-synthetic-1' }
        }
        $samplingFloors[$className] = [pscustomobject]$floor
        $testConditionId = if ($className -ceq 'controlled-benchmark') {
            $ConditionId
        }
        else {
            "controlled-condition-$className-synthetic-1"
        }
        $appliesTo = if ([int]$definition.Phase -eq 3) {
            @('candidate', 'incumbent', 'sibling-or-alternative')
        }
        else {
            @('candidate')
        }
        [void]$tests.Add([pscustomobject]@{
            testId = "test-$className-synthetic-1"
            testVersion = '1.0.0'
            testPackVersion = 'test-pack-synthetic-1'
            phase = [int]$definition.Phase
            class = $className
            samplingFloorRef = "#/samplingFloors/$className"
            purpose = "Exercise the frozen $className class."
            dependencies = @('baseline-synthetic-1')
            conditions = @([pscustomobject]@{ conditionId = $testConditionId; description = "Frozen $className test-local condition." })
            appliesTo = @($appliesTo)
            expectedEvidence = @('canonical evidence record and distribution')
            rules = [pscustomobject]@{ pass = 'Meets the frozen threshold.'; hold = 'Evidence is incomplete.'; fail = 'Violates the frozen threshold.'; inconclusive = 'Data quality prevents a verdict.' }
            stalenessDependencies = @('bios', 'windows-build', 'agent-versions', 'threshold-policy', 'test-pack')
        })
    }

    @{
        planId = 'test-plan-synthetic-1'
        schemaVersion = '2.0.1'
        status = 'frozen'
        qualificationTier = 'full'
        manifestRef = $ManifestRef
        thresholdPolicyRef = $ThresholdPolicyRef
        dependencyReviewRef = 'private://reviews/dependency-review-synthetic-1'
        omittedClasses = @()
        frozenAt = '2026-08-27T08:00:00Z'
        approvedBy = 'ROLE_QUALIFICATION_AUTHORITY'
        samplingFloors = [pscustomobject]$samplingFloors
        evidenceReusePolicy = [pscustomobject]@{
            policyVersion = '1.0.0'
            status = 'frozen'
            frozenAt = '2026-08-27T08:00:00Z'
            approvedBy = 'ROLE_QUALIFICATION_AUTHORITY'
            documentaryContext = [pscustomobject]@{
                countsTowardSamplingFloor = $false
                replacesFreshPhase1 = $false
                exactConfigurationRequired = $true
                artifactHashVerificationRequired = $true
                currencyWindowRequired = $true
                unchangedDependenciesRequired = $true
            }
            compatibilityCache = [pscustomobject]@{
                eligibleClass = 'application-compatibility'
                maximumAgeDays = 30
                requiredDependencyDimensions = @('hardware','firmware','operating-system','agents','applications','peripherals','conditions','test-and-pack','support-currency','threshold-policy','staleness')
                exactSubjectRequired = $true
                artifactHashVerificationRequired = $true
                completeEvidenceRequired = $true
                separateStrataOnMismatch = $true
                bridge = [pscustomobject]@{
                    minimumCandidateUnits = 1
                    minimumRepetitionsPerCriticalCombination = 1
                    criticalMatrixRef = 'private://matrices/compatibility-critical-synthetic-1'
                    functionalRuleRef = 'private://rules/compatibility-functional-synthetic-1'
                    repeatabilityRuleRef = 'private://rules/compatibility-repeatability-synthetic-1'
                    driftRuleRef = 'private://rules/compatibility-drift-synthetic-1'
                    cachePlusBridgeMustMeetFullFloor = $true
                }
            }
            dynamicEvidence = [pscustomobject]@{
                classes = @('controlled-benchmark','sustained-performance','battery-standby','dock-reliability','corporate-floor','agent-state','production-pilot','sentiment')
                cachedRecordsCountTowardFloors = $false
                freshConcurrentEvidenceRequired = $true
            }
            bootstrap = [pscustomobject]@{
                compatibilityFullFreshFloorRequired = $true
                controlFullFreshClassFloorRequired = $true
                productionTelemetryCountsTowardFloor = $false
                singleAnchorRunSufficient = $false
            }
        }
        tests = @($tests)
    }
}

function New-Phase3CandidateComparisonFixture {
    param(
        [Parameter(Mandatory = $true)]$Chain,
        [Parameter(Mandatory = $true)]$TestPlanRecord,
        [Parameter(Mandatory = $true)]$SourceFreshnessBinding
    )

    $phase3Tests = @((Get-TestRecordPayloadValue -Record $TestPlanRecord -FieldName 'tests') | Where-Object { [int]$_.phase -eq 3 })
    if ($phase3Tests.Count -eq 0) {
        throw 'The frozen Phase 0 plan defines no Phase 3 candidate-comparison tests.'
    }

    $evidenceRecords = New-Object System.Collections.ArrayList
    $distributionRecords = New-Object System.Collections.ArrayList
    $conditionRefs = New-Object System.Collections.ArrayList
    foreach ($testDefinition in $phase3Tests) {
        $conditions = @($testDefinition.conditions)
        if ($conditions.Count -ne 1) {
            throw "Phase 3 fixture test $($testDefinition.testId) must define exactly one test-local condition."
        }
        $conditionRef = [string]$conditions[0].conditionId
        if (@($conditionRefs) -cnotcontains $conditionRef) { [void]$conditionRefs.Add($conditionRef) }

        foreach ($role in @($testDefinition.appliesTo)) {
            $roleName = [string]$role
            $subjectRef = switch ($roleName) {
                'candidate' { [string]$Chain.candidateComparison.candidateRef }
                'incumbent' { [string]$Chain.candidateComparison.incumbentControlRef }
                'sibling-or-alternative' { [string]$Chain.candidateComparison.siblingControlRef }
                default { throw "Phase 3 fixture test $($testDefinition.testId) has unsupported appliesTo role $roleName." }
            }
            $roleSlug = if ($roleName -ceq 'sibling-or-alternative') { 'sibling' } else { $roleName }
            $isLegacyControlledBenchmark = [string]$testDefinition.class -ceq 'controlled-benchmark'
            $evidenceId = if ($isLegacyControlledBenchmark) {
                switch ($roleName) {
                    'candidate' { 'candidate-t0' }
                    'incumbent' { 'incumbent-t0' }
                    'sibling-or-alternative' { 'sibling-t0' }
                }
            }
            else { "$roleSlug-$($testDefinition.class)-t0" }
            $distributionId = if ($isLegacyControlledBenchmark) {
                switch ($roleName) {
                    'candidate' { 'distribution-candidate-synthetic-1' }
                    'incumbent' { 'distribution-incumbent-synthetic-1' }
                    'sibling-or-alternative' { 'distribution-sibling-synthetic-1' }
                }
            }
            else { "distribution-$roleSlug-$($testDefinition.class)-synthetic-1" }

            $evidence = New-EvidenceRecord $evidenceId 'candidate-comparison' -Fields @{
                subjectRef = $subjectRef
                controlRole = $roleName
                testPlanRef = [string]$TestPlanRecord.recordId
                testRef = [string]$testDefinition.testId
                conditionRef = $conditionRef
                baselineFingerprint = [string]$Chain.candidateComparison.baselineFingerprint
                testPackVersion = [string]$testDefinition.testPackVersion
                evidenceReleaseRef = 'candidate-release-synthetic-1'
                distributionRef = $distributionId
                coverageStatus = 'PASS'
                freshnessBinding = Copy-TestObject -InputObject $SourceFreshnessBinding
            }
            $distribution = New-DistributionRecord `
                -RecordId $distributionId `
                -SourceEvidenceRef $evidenceId `
                -Phase0TestPlanRecord $TestPlanRecord `
                -TestClass ([string]$testDefinition.class) `
                -TestRef ([string]$testDefinition.testId) `
                -ConditionRef $conditionRef `
                -BaselineFingerprint ([string]$Chain.candidateComparison.baselineFingerprint)
            Set-TestPortableDistributionCrosswalk -EvidenceRecord $evidence -DistributionRecord $distribution
            [void]$evidenceRecords.Add($evidence)
            [void]$distributionRecords.Add($distribution)
        }
    }

    [pscustomobject]@{
        EvidenceRecords = @($evidenceRecords)
        DistributionRecords = @($distributionRecords)
        EvidenceRefs = @($evidenceRecords | ForEach-Object { [string]$_.recordId })
        MemberRecordIds = @(
            @($evidenceRecords | ForEach-Object { [string]$_.recordId }) +
            @($distributionRecords | ForEach-Object { [string]$_.recordId })
        )
        ConditionRefs = @($conditionRefs)
    }
}

function New-IssuedClaimChainFixture {
    $template = Get-Content (Join-Path $here 'leadership-claim-chain.json') -Raw | ConvertFrom-Json
    [pscustomobject]@{
        chainVersion = '1.0.0'
        documentType = 'leadership-claim-chain'
        status = 'ISSUED'
        portableContractRefs = @(
            '../../v2.0.1/NEW_LAPTOP_EVALUATION_PLAYBOOK_v2.md',
            '../../v2.0.1/schemas/candidate-manifest.schema.json',
            '../../v2.0.1/schemas/test-plan.schema.json',
            '../../v2.0.1/schemas/evidence-record.schema.json',
            '../../v2.0.1/schemas/threshold-policy.schema.json',
            '../../v2.0.1/schemas/verdict-record.schema.json'
        )
        personaNeed = [pscustomobject]@{
            personaId = 'persona-engineering-synthetic'
            manifestRef = 'manifest-synthetic-1'
            personaVerdictPointer = 'verdict-synthetic-1#/personaVerdicts/0'
            capacityWaterfallPointer = 'verdict-synthetic-1#/personaVerdicts/0/capacityWaterfall'
            evidenceReleaseRef = 'persona-release-synthetic-1'
            evidenceRefs = @('evidence-persona-t0')
            provenance = @('T0')
            freshness = New-LeadershipFreshnessFixture 'personaNeed' `
                -ObservedAt '2026-08-27T09:00:00Z' -AdmittedAt '2026-08-27T09:30:00Z'
        }
        currentFleetIssue = [pscustomobject]@{
            incumbentControlRef = 'manifest-synthetic-1#/controls/incumbent'
            cohortRef = 'cohort-synthetic-1'
            statement = 'Synthetic incumbent incident rate exceeded the fixture threshold during the observation window.'
            issueStatementPointer = 'evidence-incumbent-t0#/extensions/operationsBlueprintV1/issueStatement'
            attributionClass = 'ASSOCIATION'
            observationWindow = '2026-08-27/2026-08-27'
            baselineFingerprint = (New-TestDigest 'b')
            fleetPortfolioRef = 'fleet-portfolio-synthetic-1'
            fleetPortfolioCohortPointer = 'fleet-portfolio-synthetic-1#/configurationCohorts/0'
            evidenceReleaseRef = 'fleet-release-synthetic-1'
            evidenceRefs = @('evidence-incumbent-t0', 'incident-release-t0')
            provenance = @('T0')
            freshness = New-LeadershipFreshnessFixture 'currentFleetIssue' `
                -ObservedAt '2026-08-27T09:00:00Z' -AdmittedAt '2026-08-27T10:00:00Z'
        }
        candidateComparison = [pscustomobject]@{
            candidateRef = 'manifest-synthetic-1#/candidateDevices/0'
            incumbentControlRef = 'manifest-synthetic-1#/controls/incumbent'
            siblingControlRef = 'manifest-synthetic-1#/controls/sibling-or-alternative'
            testPlanRef = 'test-plan-synthetic-1'
            conditionRefs = @('controlled-condition-synthetic-1')
            evidenceReleaseRef = 'candidate-release-synthetic-1'
            evidenceRefs = @('candidate-t0', 'incumbent-t0', 'sibling-t0')
            provenance = @('T0')
            baselineFingerprint = (New-TestDigest 'b')
            testPackVersion = 'test-pack-synthetic-1'
            freshness = New-LeadershipFreshnessFixture 'candidateComparison' `
                -ObservedAt '2026-08-27T09:15:00Z' -AdmittedAt '2026-08-27T10:15:00Z'
        }
        businessEffect = [pscustomobject]@{
            status = 'MEASURED'
            effectType = 'COST_DELTA'
            statement = 'Synthetic measured business effect used only by the unit test.'
            assumptions = @('Synthetic prices and time values are fixture data, not a portfolio claim.')
            decisionImpact = 'The synthetic effect is one bounded input to the fixture recommendation.'
            freshness = New-LeadershipFreshnessFixture 'businessEffect' `
                -ObservedAt '2026-08-27T09:30:00Z' -AdmittedAt '2026-08-27T10:30:00Z'
            businessEffectRef = 'business-impact-synthetic-1'
            businessEffectPointer = 'business-impact-synthetic-1#/businessEffectStatement'
            observationWindow = '2026-08-27/2026-08-27'
            evidenceReleaseRef = 'business-release-synthetic-1'
            evidenceRefs = @('business-impact-t0')
            provenance = @('T0')
            currency = 'USD'
            quantity = 1000
            candidateQuoteRef = 'candidate-quote-synthetic-1'
            controlQuoteRef = 'control-quote-synthetic-1'
            quoteValidUntil = '2026-09-30T00:00:00Z'
            calculationPointer = 'business-impact-synthetic-1#/calculation'
            calculationMethod = 'candidate-total-minus-control-total'
            calculationResult = 300000
            resultUnit = 'USD'
            uncertainty = 'Synthetic fixture uncertainty; no real financial claim.'
        }
        recommendation = [pscustomobject]@{
            verdictRef = 'verdict-synthetic-1'
            fleetVerdictPointer = 'verdict-synthetic-1#/fleetVerdict'
            personaVerdictPointer = 'verdict-synthetic-1#/personaVerdicts/0'
            procurementEnvelopePointer = 'verdict-synthetic-1#/procurementEnvelope'
            claimRecordRef = 'decision-claim-synthetic-1'
            statementPointer = 'decision-claim-synthetic-1#/renderedStatement'
            action = 'DO_NOT_BUY'
            statement = 'DO_NOT_BUY: The issued fleet, persona, or procurement disposition blocks purchase for persona persona-engineering-synthetic.'
            freshness = New-LeadershipFreshnessFixture 'recommendation' `
                -ObservedAt '2026-08-27T12:20:00Z' -AdmittedAt '2026-08-27T12:25:00Z'
        }
        lineage = [pscustomobject]@{
            generatedAt = '2026-08-27T12:29:00Z'
            validatorReleaseRef = 'private://validator-releases/operations-blueprint-v1.0.0'
            semanticValidationRef = 'semantic-validation-synthetic-1'
            semanticValidationDigest = (New-TestDigest 'e')
            semanticInputDigest = (New-TestDigest '0')
            derivedDocumentsAreEvidence = $false
        }
        requiredLeadershipLinks = $template.requiredLeadershipLinks
        currentFleetRequiredDimensions = $template.currentFleetRequiredDimensions
        readinessRules = $template.readinessRules
    }
}

function New-UnmeasuredBusinessEffectFixture {
    [pscustomobject]@{
        status = 'NOT_MEASURED'
        statement = 'NOT_MEASURED: No non-price business effect is claimed for this decision.'
        assumptions = @('No non-price business-effect estimate is available.')
        decisionImpact = 'No non-price benefit may support this recommendation; only current commercial quotes and the issued verdict remain decision inputs.'
        freshness = New-LeadershipFreshnessFixture 'businessEffect' -ObservedAt '2026-08-20T00:00:00Z' -AdmittedAt '2026-08-27T11:00:00Z'
        notMeasuredReason = 'No approved business-impact release exists for this fixture.'
        currency = 'USD'
        quantity = 1000
        candidateQuoteRef = 'candidate-quote-synthetic-1'
        controlQuoteRef = 'control-quote-synthetic-1'
        quoteValidUntil = '2026-09-30T00:00:00Z'
    }
}

function Update-ClaimSemanticBinding {
    param([Parameter(Mandatory = $true)]$Chain, [Parameter(Mandatory = $true)][object[]]$RecordIndex)
    if (@($RecordIndex | Where-Object recordType -CEQ 'portable-contract-projection-record').Count -gt 0) {
        $mapErrors = New-Object System.Collections.ArrayList
        $map = Get-CanonicalRecordMap -RecordIndex $RecordIndex -Errors $mapErrors -Context 'semantic fixture rebinding' `
            -EvaluationTime $evaluationTime -ValidationProfile TEST
    }
    else {
        $map = [System.Collections.Generic.Dictionary[string,object]]::new([System.StringComparer]::Ordinal)
        foreach ($record in @($RecordIndex)) { if (-not $map.ContainsKey([string]$record.recordId)) { $map.Add([string]$record.recordId, $record) } }
    }
    $digest = Get-LeadershipSemanticInputDigest -Chain $Chain -RecordMap $map
    [string[]]$semanticSourceRefs = @(Get-LeadershipSemanticInputDigest -Chain $Chain -RecordMap $map -ReturnSourceRecordRefs)
    $Chain.lineage.semanticInputDigest = $digest
    $semanticRecord = $RecordIndex | Where-Object recordId -eq 'semantic-validation-synthetic-1'
    $semanticRecord.payload.inputDigest = $digest
    $semanticRecord.payload.validatorReleaseDigest = 'sha256:b4fdd5765b3d850a296a2948e50d17c6f5b457316adbe903dc13894a9bf66466'
    $semanticRecord.payload.sourceRecordRefs = @($semanticSourceRefs)
    $semanticRecord.payload.sourceRecordSetDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject]@{
        sourceRecordRefs = @($semanticSourceRefs)
    })
    $semanticRecord.payload.validationResultDigest = Get-SemanticValidationResultDigest -SemanticRecord $semanticRecord.payload
    Update-CanonicalRecordBinding $semanticRecord
    $Chain.lineage.semanticValidationDigest = $semanticRecord.contentDigest
    $decisionRecord = @($RecordIndex | Where-Object recordId -eq 'decision-claim-synthetic-1')[0]
    if ($null -ne $decisionRecord) {
        $verdictRecord = @($RecordIndex | Where-Object recordId -eq 'verdict-synthetic-1')[0]
        $manifestRecord = @($RecordIndex | Where-Object recordId -eq 'manifest-synthetic-1')[0]
        $decisionRecord.payload.sourceVerdictDigest = $verdictRecord.contentDigest
        $decisionRecord.payload.sourceManifestDigest = $manifestRecord.contentDigest
        $decisionRecord.payload.semanticValidationDigest = $semanticRecord.contentDigest
        $decisionRecord.payload.semanticInputDigest = $digest
        $decisionRecord.payload.procurementEnvelopeDigest = Get-CanonicalPayloadDigest -Payload `
            (Get-TestRecordPayloadValue -Record $verdictRecord -FieldName 'procurementEnvelope')
        $decisionRecord.payload.renderedStatement = [string]$Chain.recommendation.statement
        $decisionRecord.payload.renderedStatementDigest = Get-CanonicalPayloadDigest -Payload ([string]$Chain.recommendation.statement)
        Update-CanonicalRecordBinding $decisionRecord
    }
}

$script:QualificationAuthorityClosureFixtureXml = $null

function New-TestQualificationAuthorityClosureFixture {
    if ([string]::IsNullOrEmpty([string]$script:QualificationAuthorityClosureFixtureXml)) {
        $activation = New-ActivationScenarioFixture -Stage PILOT
        $closureTypes = @(
            'identity-governance-root-authority-record',
            'security-freshness-policy-record',
            'role-binding-approval-record',
            'role-binding-record',
            'role-binding-readback-record'
        )
        $closure = @($activation.RecordIndex | Where-Object {
            [string]$_.recordType -cin $closureTypes -and
            ([string]$_.recordType -cne 'security-freshness-policy-record' -or
             [string]$_.recordId -ceq 'private://policies/identity-role-binding-readback-synthetic-1')
        })
        $script:QualificationAuthorityClosureFixtureXml =
            [System.Management.Automation.PSSerializer]::Serialize($closure, 100)
    }
    return @([System.Management.Automation.PSSerializer]::Deserialize(
        $script:QualificationAuthorityClosureFixtureXml
    ))
}

function Get-TestPortableVerdictView {
    param([Parameter(Mandatory = $true)]$VerdictRecord)

    $view = [ordered]@{
        recordId = [string]$VerdictRecord.recordId
        recordType = 'verdict-record'
        contentDigest = [string]$VerdictRecord.contentDigest
        portableProjectionRecord = $VerdictRecord.payload
    }
    foreach ($binding in @($VerdictRecord.payload.projection.bindings)) {
        $view[[string]$binding.projectionField] = $binding.value
    }
    return [pscustomobject]$view
}

function New-TestQualificationAuthorityApprovalRecord {
    param(
        [Parameter(Mandatory = $true)][string]$RecordId,
        [Parameter(Mandatory = $true)]$VerdictRecord,
        [Parameter(Mandatory = $true)]$ManifestRecord,
        [Parameter(Mandatory = $true)][object[]]$AuthorityClosureRecords,
        [Parameter(Mandatory = $true)][ValidateSet('VERDICT_ISSUANCE','PILOT_NOT_REQUIRED')][string]$DecisionScope,
        [Parameter(Mandatory = $true)][string]$IssuedAt,
        [Parameter(Mandatory = $true)][string]$ApprovedAt,
        [Parameter(Mandatory = $true)][string]$RevocationCheckedAt
    )

    $roleBinding = @($AuthorityClosureRecords | Where-Object recordType -CEQ 'role-binding-record')[0]
    $roleBindingReadback = @($AuthorityClosureRecords | Where-Object recordType -CEQ 'role-binding-readback-record')[0]
    $readbackPolicy = @($AuthorityClosureRecords | Where-Object {
        [string]$_.recordId -ceq [string]$roleBindingReadback.payload.readbackPolicyRef
    })[0]
    $qualificationBindings = @($roleBinding.payload.bindings | Where-Object roleId -CEQ 'ROLE_QUALIFICATION_AUTHORITY')
    $securityBindings = @($roleBinding.payload.bindings | Where-Object roleId -CEQ 'ROLE_SECURITY_APPROVER')
    if ($qualificationBindings.Count -lt 2 -or $securityBindings.Count -lt 1) {
        throw 'The qualification-authority fixture requires two qualification principals and one security approver.'
    }

    $verdictView = Get-TestPortableVerdictView -VerdictRecord $VerdictRecord
    $approverBindings = @(
        [pscustomobject][ordered]@{
            roleId = 'ROLE_QUALIFICATION_AUTHORITY'
            canonicalPrincipalId = [string]$qualificationBindings[1].canonicalPrincipalId
        },
        [pscustomobject][ordered]@{
            roleId = 'ROLE_SECURITY_APPROVER'
            canonicalPrincipalId = [string]$securityBindings[0].canonicalPrincipalId
        }
    )
    $revocationEvidenceRef = "private://qualification-authority/revocation/$RecordId"
    $revocationEvidenceDigest = Get-Sha256TokenFromText -Text "qualification-authority-revocation:$RecordId"
    $approvalFields = [ordered]@{
        schemaVersion = '1.0.0'
        recordStage = 'QUALIFICATION_AUTHORITY_APPROVAL'
        status = 'APPROVED'
        tenantBoundaryRef = [string](Get-TestRecordPayloadValue -Record $ManifestRecord -FieldName 'tenantBoundaryRef')
        targetEnvironmentRef = [string](Get-TestRecordPayloadValue -Record $ManifestRecord -FieldName 'targetEnvironmentRef')
        manifestRef = [string]$ManifestRecord.recordId
        manifestDigest = [string]$ManifestRecord.contentDigest
        verdictRef = [string]$VerdictRecord.recordId
        qualificationAuthority = [string](Get-TestRecordPayloadValue -Record $VerdictRecord -FieldName 'qualificationAuthority')
        authorityRole = 'ROLE_QUALIFICATION_AUTHORITY'
        authorityPrincipalId = [string]$qualificationBindings[0].canonicalPrincipalId
        recordProducerPrincipalId = New-TestCanonicalPrincipalId -Seed "qualification-authority-producer:$RecordId"
        affectedRequesterPrincipalId = New-TestCanonicalPrincipalId -Seed "qualification-authority-requester:$RecordId"
        approverBindings = @($approverBindings)
        approverSetRef = "private://qualification-authority/approver-sets/$RecordId"
        approverSetDigest = Get-QualificationAuthorityApproverSetDigest -ApproverBindings $approverBindings
        roleBindingRef = [string]$roleBinding.recordId
        roleBindingDigest = [string]$roleBinding.contentDigest
        roleBindingReadbackRef = [string]$roleBindingReadback.recordId
        roleBindingReadbackDigest = [string]$roleBindingReadback.contentDigest
        roleBindingReadbackPolicyRef = [string]$readbackPolicy.recordId
        roleBindingReadbackPolicyDigest = [string]$readbackPolicy.contentDigest
        roleBindingReadbackMaxAgeMinutes = [int]$roleBindingReadback.payload.maxAgeMinutes
        decisionScope = $DecisionScope
        decisionRef = Get-QualificationAuthorityDecisionRef -VerdictRef ([string]$VerdictRecord.recordId) -DecisionScope $DecisionScope
        decisionSubjectDigest = Get-QualificationAuthorityDecisionSubjectDigest -Verdict $verdictView -DecisionScope $DecisionScope
        approvalSubjectDigest = New-TestDigest '0'
        signedSubjectRef = "private://qualification-authority/subjects/$RecordId"
        signedSubjectDigest = New-TestDigest '0'
        approvalArtifactRef = "private://qualification-authority/approvals/$RecordId"
        approvalArtifactDigest = New-TestDigest '0'
        signatureRef = "private://qualification-authority/signatures/$RecordId"
        signatureDigest = Get-Sha256TokenFromText -Text "qualification-authority-signature:$RecordId"
        signatureStatus = 'VERIFIED'
        issuedAt = $IssuedAt
        approvedAt = $ApprovedAt
        expiresAt = '2026-08-28T00:00:00Z'
        freshnessBinding = [pscustomobject][ordered]@{
            observedAt = $RevocationCheckedAt
            admittedAt = $RevocationCheckedAt
            policyRef = [string]$readbackPolicy.recordId
            maxAgeDays = 1
            dependencySnapshotRef = $revocationEvidenceRef
            dependencySnapshotDigest = $revocationEvidenceDigest
            dependencyStatus = 'MATCH'
        }
        revocationStatus = 'NOT_REVOKED'
        revocationEvidenceRef = $revocationEvidenceRef
        revocationEvidenceDigest = $revocationEvidenceDigest
        revocationCheckedAt = $RevocationCheckedAt
        authorizationEffect = 'NONE'
    }
    # The signed subject includes the canonical record payload's common
    # record/validity fields.  Construct the envelope first, then hash the actual
    # payload projection rather than the pre-envelope field dictionary.
    $approvalRecord = New-CanonicalRecord -RecordId $RecordId `
        -RecordType 'qualification-authority-approval-record' -Fields $approvalFields
    $approvalSubjectDigest = Get-QualificationAuthorityApprovalSubjectDigest -Approval $approvalRecord
    $approvalRecord.payload.approvalSubjectDigest = $approvalSubjectDigest
    $approvalRecord.payload.signedSubjectDigest = $approvalSubjectDigest
    $approvalRecord.payload.approvalArtifactDigest = $approvalSubjectDigest
    Update-CanonicalRecordBinding $approvalRecord
    return $approvalRecord
}

function Update-FleetPortfolioDimensionDigests {
    param(
        [Parameter(Mandatory = $true)]$Fixture,
        [switch]$UpdateSemanticBinding
    )

    $portfolio = @($Fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
    $descriptors = @(Get-FleetDimensionClaimDescriptors -Chain $Fixture.Chain)
    $dimensionDigestBindings = New-Object System.Collections.ArrayList
    foreach ($dimensionPolicy in @($Fixture.Chain.currentFleetRequiredDimensions)) {
        $dimensionId = [string]$dimensionPolicy.dimensionId
        $propertyName = [string]@($descriptors | Where-Object DimensionId -CEQ $dimensionId)[0].PropertyName
        $dimension = $portfolio.payload.dimensionCoverage.$propertyName
        $dimension.dimensionEvidenceDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject][ordered]@{
            dimensionId = [string]$dimension.dimensionId
            status = [string]$dimension.status
            claimBindings = @($dimension.claimBindings)
        })
        [void]$dimensionDigestBindings.Add([pscustomobject][ordered]@{
            dimensionId = $dimensionId
            dimensionEvidenceDigest = [string]$dimension.dimensionEvidenceDigest
        })
    }
    $coverage = $portfolio.payload.dimensionCoverage
    $coverage.bindingsDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject][ordered]@{
        dimensionPolicyRef = [string]$coverage.dimensionPolicyRef
        dimensionPolicyDigest = [string]$coverage.dimensionPolicyDigest
        dimensions = @($dimensionDigestBindings)
    })
    $coverage.policyExecutionDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject][ordered]@{
        dimensionPolicyRef = [string]$coverage.dimensionPolicyRef
        dimensionPolicyDigest = [string]$coverage.dimensionPolicyDigest
        policyExecutionToolRef = [string]$coverage.policyExecutionToolRef
        policyExecutionToolVersion = [string]$coverage.policyExecutionToolVersion
        policyExecutedAt = [string]$coverage.policyExecutedAt
        bindingsDigest = [string]$coverage.bindingsDigest
    })
    Update-CanonicalRecordBinding $portfolio
    if ($UpdateSemanticBinding) { Update-ClaimSemanticBinding -Chain $Fixture.Chain -RecordIndex $Fixture.RecordIndex }
}

function New-FleetDimensionSemanticTestContext {
    $fixture = New-IssuedClaimFixture
    $errors = New-Object System.Collections.ArrayList
    $recordMap = Get-CanonicalRecordMap -RecordIndex $fixture.RecordIndex -Errors $errors `
        -Context 'fleet dimension direct test fixture' -EvaluationTime $evaluationTime -ValidationProfile TEST
    if ($errors.Count -ne 0) { throw "The base fleet dimension fixture is invalid: $(@($errors.code) -join ', ')" }
    $portfolio = $recordMap['fleet-portfolio-synthetic-1']
    $governance = Get-FleetPortfolioGovernanceBinding -FleetPortfolio $portfolio -Chain $fixture.Chain `
        -RecordMap $recordMap -ValidationProfile TEST -Errors $errors
    if ($errors.Count -ne 0) { throw "The base fleet governance fixture is invalid: $(@($errors.code) -join ', ')" }
    [pscustomobject]@{
        Fixture = $fixture
        RecordMap = $recordMap
        Portfolio = $portfolio
        Governance = $governance
    }
}

function Get-FleetDimensionSemanticReasonCodes {
    param(
        [Parameter(Mandatory = $true)]$Context,
        [Parameter(Mandatory = $true)]$Portfolio
    )
    $errors = New-Object System.Collections.ArrayList
    Test-FleetPortfolioDimensionSemantics -FleetPortfolio $Portfolio -Chain $Context.Fixture.Chain `
        -RecordMap $Context.RecordMap -Governance $Context.Governance -EvaluationTime $evaluationTime `
        -LineageGeneratedAt ([DateTimeOffset]::Parse('2026-08-27T12:00:00Z')) -Errors $errors
    @($errors | ForEach-Object { [string]$_.code })
}

function Update-DecisionClaimVerdictBinding {
    param([Parameter(Mandatory = $true)][object[]]$RecordIndex)
    $verdict = @($RecordIndex | Where-Object recordId -eq 'verdict-synthetic-1')[0]
    Update-CanonicalRecordBinding $verdict
    $decision = @($RecordIndex | Where-Object recordId -eq 'decision-claim-synthetic-1')[0]
    $decision.payload.sourceVerdictDigest = $verdict.contentDigest
    $decision.payload.procurementEnvelopeDigest = Get-CanonicalPayloadDigest -Payload `
        (Get-TestRecordPayloadValue -Record $verdict -FieldName 'procurementEnvelope')
    Update-CanonicalRecordBinding $decision
}

function Get-FreshnessSourceRecordIds {
    param(
        [Parameter(Mandatory = $true)]$Chain,
        [Parameter(Mandatory = $true)]
        [ValidateSet('personaNeed', 'currentFleetIssue', 'candidateComparison', 'businessEffect', 'recommendation')]
        [string]$LinkName
    )
    switch ($LinkName) {
        'personaNeed' { @('persona-release-synthetic-1', 'evidence-persona-t0') }
        'currentFleetIssue' {
            @('fleet-portfolio-synthetic-1', 'fleet-release-synthetic-1', 'evidence-incumbent-t0', 'incident-release-t0') + @(
                Get-FleetDimensionClaimDescriptors -Chain $Chain | ForEach-Object { "evidence-$($_.ClaimBindingId)" }
            )
        }
        'candidateComparison' { @('candidate-release-synthetic-1', 'candidate-t0', 'incumbent-t0', 'sibling-t0') }
        'businessEffect' {
            if ([string]$Chain.businessEffect.status -ceq 'MEASURED') {
                @('business-impact-synthetic-1', 'business-release-synthetic-1', 'business-impact-t0')
            }
            else { @('candidate-quote-synthetic-1', 'control-quote-synthetic-1') }
        }
        'recommendation' { @('verdict-synthetic-1', 'decision-claim-synthetic-1') }
    }
}

function Set-LinkAndSourceFreshnessTimes {
    param(
        [Parameter(Mandatory = $true)]$Chain,
        [Parameter(Mandatory = $true)][object[]]$RecordIndex,
        [Parameter(Mandatory = $true)]
        [ValidateSet('personaNeed', 'currentFleetIssue', 'candidateComparison', 'businessEffect', 'recommendation')]
        [string]$LinkName,
        [Parameter(Mandatory = $true)][string]$ObservedAt,
        [Parameter(Mandatory = $true)][string]$AdmittedAt,
        [string]$EvaluatedAt = '2026-08-27T12:00:00Z'
    )
    $Chain.$LinkName.freshness.observedAt = $ObservedAt
    $Chain.$LinkName.freshness.admittedAt = $AdmittedAt
    $Chain.$LinkName.freshness.evaluatedAt = $EvaluatedAt
    foreach ($recordId in @(Get-FreshnessSourceRecordIds -Chain $Chain -LinkName $LinkName)) {
        $record = @($RecordIndex | Where-Object recordId -eq $recordId)[0]
        $record.payload.freshnessBinding.observedAt = $ObservedAt
        $record.payload.freshnessBinding.admittedAt = $AdmittedAt
        Update-CanonicalRecordBinding $record
    }
    if ($LinkName -eq 'recommendation') { Update-DecisionClaimVerdictBinding $RecordIndex }
}

function Get-FleetDimensionClaimDescriptors {
    param([Parameter(Mandatory = $true)]$Chain)

    $propertyByDimension = [ordered]@{
        CONFIGURATION_PERSONA_POPULATION = 'configurationPersonaPopulation'
        PLATFORM_SUPPORT_BASELINE = 'platformSupportBaseline'
        CAPACITY_HEADROOM = 'capacityHeadroom'
        WORKLOAD_RESOURCE_PRESSURE = 'workloadResourcePressure'
        APPLICATION_STATE = 'applicationState'
        BATTERY_STANDBY = 'batteryStandby'
        DOCK_RELIABILITY = 'dockReliability'
        PROVISIONING_UPDATE_COMPLIANCE_MANAGEMENT = 'provisioningUpdateComplianceManagement'
        INCIDENT_REPAIR_SUPPORT = 'incidentRepairSupport'
        REGION_WORK_PATTERN_REPRESENTATION = 'regionWorkPatternRepresentation'
        PROVENANCE_INTEGRITY = 'provenanceIntegrity'
        LIMITATIONS_OUTLIERS_FRESHNESS_REQUALIFICATION = 'limitationsOutliersFreshnessRequalification'
    }
    $distributionTypes = @(
        'PHYSICAL_CAPACITY_CORPORATE_FLOOR_RESERVE_HEADROOM','RESOURCE_PRESSURE','WORKLOAD_TIMING',
        'BATTERY_RUNTIME','STANDBY_DRAIN','DOCK_ATTACH_DETACH_SLEEP_RESUME_RELIABILITY',
        'INCIDENT_PREVALENCE','REPAIR_PREVALENCE','SUPPORT_CONTACT_PREVALENCE','SUPPORT_EFFORT'
    )
    $denominatedTypes = @(
        'PERSONA_COHORT_POPULATION','APPLICATION_FAILURE_COMPATIBILITY','PROVISIONING_STATE',
        'UPDATE_STATE','COMPLIANCE_STATE','MANAGEMENT_STATE','REGION_REPRESENTATION','WORK_PATTERN_REPRESENTATION'
    )
    $testClassByMetric = @{
        PHYSICAL_CAPACITY_CORPORATE_FLOOR_RESERVE_HEADROOM = 'corporate-floor'
        RESOURCE_PRESSURE = 'production-pilot'
        WORKLOAD_TIMING = 'production-pilot'
        BATTERY_RUNTIME = 'battery-standby'
        STANDBY_DRAIN = 'battery-standby'
        DOCK_ATTACH_DETACH_SLEEP_RESUME_RELIABILITY = 'dock-reliability'
        INCIDENT_PREVALENCE = 'production-pilot'
        REPAIR_PREVALENCE = 'production-pilot'
        SUPPORT_CONTACT_PREVALENCE = 'production-pilot'
        SUPPORT_EFFORT = 'production-pilot'
    }
    $descriptors = New-Object System.Collections.ArrayList
    foreach ($dimension in @($Chain.currentFleetRequiredDimensions)) {
        $dimensionId = [string]$dimension.dimensionId
        foreach ($claimMetricType in @($dimension.requiredClaimMetricTypes)) {
            $metricType = [string]$claimMetricType
            $slug = $metricType.ToLowerInvariant().Replace('_', '-')
            $shape = if ($distributionTypes -ccontains $metricType) { 'DISTRIBUTION' }
                elseif ($denominatedTypes -ccontains $metricType) { 'DENOMINATED_COUNT' }
                else { 'STRUCTURED_STATE' }
            [void]$descriptors.Add([pscustomobject][ordered]@{
                DimensionId = $dimensionId
                PropertyName = [string]$propertyByDimension[$dimensionId]
                ClaimMetricType = $metricType
                ClaimBindingId = "fleet-$slug-synthetic-1"
                MetricId = "fleet-$slug"
                EvidenceShape = $shape
                TestClass = if ($shape -ceq 'DISTRIBUTION') { [string]$testClassByMetric[$metricType] } else { $null }
            })
        }
    }
    @($descriptors)
}

function New-FleetDimensionContractFixture {
    param(
        [Parameter(Mandatory = $true)]$Chain,
        [Parameter(Mandatory = $true)]$FleetPortfolioDomainContext,
        [Parameter(Mandatory = $true)]$Phase0TestPlanRecord,
        [Parameter(Mandatory = $true)]$QueryPackRecord,
        [Parameter(Mandatory = $true)]$SourceFreshnessBinding,
        [Parameter(Mandatory = $true)]$ClaimFreshnessBinding,
        [Parameter(Mandatory = $true)][object[]]$AdditionalMemberRecords,
        [Parameter(Mandatory = $true)][string]$RequalificationPlanRef
    )

    $eligibleCount = 35
    $descriptors = @(Get-FleetDimensionClaimDescriptors -Chain $Chain)
    $evidenceRecords = New-Object System.Collections.ArrayList
    $distributionRecords = New-Object System.Collections.ArrayList
    $sourceByClaimId = [System.Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
    $distributionByClaimId = [System.Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
    foreach ($descriptor in $descriptors) {
        $artifactHash = Get-Sha256TokenFromText -Text "fleet-artifact:$($descriptor.ClaimBindingId)"
        $evidenceId = "evidence-$($descriptor.ClaimBindingId)"
        $testDefinition = if ($descriptor.EvidenceShape -ceq 'DISTRIBUTION') {
            @((Get-TestRecordPayloadValue -Record $Phase0TestPlanRecord -FieldName 'tests') |
                Where-Object { [string]$_.class -ceq [string]$descriptor.TestClass })[0]
        }
        else { $null }
        $fields = @{
            subjectRef = [string]$Chain.currentFleetIssue.incumbentControlRef
            cohortRef = [string]$Chain.currentFleetIssue.cohortRef
            observationWindow = [string]$Chain.currentFleetIssue.observationWindow
            baselineFingerprint = [string]$Chain.currentFleetIssue.baselineFingerprint
            evidenceReleaseRef = 'fleet-release-synthetic-1'
            coverageStatus = 'PASS'
            coverage = [pscustomobject]@{
                scope = 'Eligible current-fleet devices after governed exclusions.'
                plannedUnits = 35
                observedUnits = 30
                plannedRuns = 350
                observedRuns = 300
                percent = 85.7142857142857
                gaps = @('Five eligible units have no admitted result.')
            }
            metricId = [string]$descriptor.MetricId
            unit = if ($descriptor.EvidenceShape -ceq 'STRUCTURED_STATE') { 'state' } else { 'devices' }
            statisticDirection = 'DESCRIPTIVE_ONLY'
            tool = [pscustomobject]@{ name = 'systrack'; version = 'synthetic-1.0.0' }
            artifacts = @([pscustomobject]@{ sha256 = $artifactHash })
            freshnessBinding = Copy-TestObject -InputObject $SourceFreshnessBinding
            result = if ($descriptor.EvidenceShape -ceq 'DENOMINATED_COUNT') {
                [pscustomobject][ordered]@{ status = 'PASS'; numeratorValue = 30 }
            }
            elseif ($descriptor.EvidenceShape -ceq 'STRUCTURED_STATE') {
                [pscustomobject][ordered]@{ status = 'PASS'; state = 'PASS' }
            }
            else {
                [pscustomobject][ordered]@{ status = 'PASS'; metricValue = 100 }
            }
        }
        if ($descriptor.EvidenceShape -ceq 'DISTRIBUTION') {
            $fields.distributionRef = "distribution-$($descriptor.ClaimBindingId)"
            $fields.testPlanRef = [string]$Phase0TestPlanRecord.recordId
            $fields.testRef = [string]$testDefinition.testId
            $fields.conditionRef = [string]$testDefinition.conditions[0].conditionId
            $fields.testPackVersion = [string]$testDefinition.testPackVersion
        }
        $evidence = New-EvidenceRecord $evidenceId $descriptor.ClaimBindingId -Fields $fields
        [void]$evidenceRecords.Add($evidence)
        $sourceByClaimId.Add([string]$descriptor.ClaimBindingId, $evidence)
        if ($descriptor.EvidenceShape -ceq 'DISTRIBUTION') {
            $floor = (Get-TestRecordPayloadValue -Record $Phase0TestPlanRecord -FieldName 'samplingFloors').PSObject.Properties[[string]$descriptor.TestClass].Value
            $distribution = New-DistributionRecord `
                -RecordId "distribution-$($descriptor.ClaimBindingId)" `
                -SourceEvidenceRef $evidence.recordId `
                -Phase0TestPlanRecord $Phase0TestPlanRecord `
                -TestClass ([string]$descriptor.TestClass) `
                -TestRef ([string]$testDefinition.testId) `
                -ConditionRef ([string]$testDefinition.conditions[0].conditionId) `
                -BaselineFingerprint ([string]$Chain.currentFleetIssue.baselineFingerprint) `
                -UnitCount 30 `
                -RunCount (30 * [int]$floor.minRepetitionsPerUnit)
            $distribution.payload.metricId = [string]$descriptor.MetricId
            $distribution.payload.unit = 'devices'
            $distribution.payload.statisticDirection = 'DESCRIPTIVE_ONLY'
            $distribution.payload.coverage = [pscustomobject]@{ expected = $eligibleCount; observed = 30; percent = 85.7142857142857 }
            $distribution.payload.missingResults = @([pscustomobject]@{
                count = (($eligibleCount - 30) * [int]$distribution.payload.requiredRuns)
                reason = 'NO_ADMITTED_RESULT'
            })
            $distribution.payload.exclusions = @([pscustomobject]@{ count = 5 })
            Update-CanonicalRecordBinding $distribution
            Set-TestPortableDistributionCrosswalk -EvidenceRecord $evidence -DistributionRecord $distribution
            [void]$distributionRecords.Add($distribution)
            $distributionByClaimId.Add([string]$descriptor.ClaimBindingId, $distribution)
        }
    }

    $memberRecords = @($AdditionalMemberRecords) + @($evidenceRecords) + @($distributionRecords)
    $release = Initialize-TestEvidenceReleaseSubject (New-CanonicalRecord 'fleet-release-synthetic-1' 'evidence-release' @('/memberRecordIds') -Fields @{
        memberRecordIds = @($memberRecords | ForEach-Object { [string]$_.recordId })
        semanticGateStatus = 'PASS'
        samplingFloorStatus = 'PASS'
        distributionStatus = 'PASS'
        coverageStatus = 'PASS'
        releasedAt = '2026-08-27T11:30:00Z'
        freshnessBinding = Copy-TestObject -InputObject $SourceFreshnessBinding
    })

    foreach ($distribution in @($distributionRecords)) {
        $sourceEvidence = @($evidenceRecords | Where-Object recordId -CEQ ([string]$distribution.payload.sourceEvidenceRef))[0]
        $distribution.payload.sourceEvidenceDigest = [string]$sourceEvidence.contentDigest
        $distribution.payload.sourceEvidenceReleaseRef = [string]$release.recordId
        $distribution.payload.sourceEvidenceReleaseSubjectDigest = [string]$release.payload.releaseSubjectDigest
        Update-CanonicalRecordBinding $distribution
    }
    [void](Complete-TestEvidenceReleaseMembership -ReleaseRecord $release -RecordIndex $memberRecords)

    $dimensions = [ordered]@{}
    foreach ($dimensionPolicy in @($Chain.currentFleetRequiredDimensions)) {
        $dimensionId = [string]$dimensionPolicy.dimensionId
        $claims = New-Object System.Collections.ArrayList
        foreach ($descriptor in @($descriptors | Where-Object DimensionId -CEQ $dimensionId)) {
            $evidence = $sourceByClaimId[[string]$descriptor.ClaimBindingId]
            $artifactHash = [string]@(Get-TestRecordPayloadValue -Record $evidence -FieldName 'artifacts')[0].sha256
            $claim = [ordered]@{
                claimBindingId = [string]$descriptor.ClaimBindingId
                claimMetricType = [string]$descriptor.ClaimMetricType
                evidenceShape = [string]$descriptor.EvidenceShape
                metricId = [string]$descriptor.MetricId
                unit = if ($descriptor.EvidenceShape -ceq 'STRUCTURED_STATE') { 'state' } else { 'devices' }
                statisticDirection = 'DESCRIPTIVE_ONLY'
                evidenceReleaseBindings = @([pscustomobject]@{ recordRef = $release.recordId; contentDigest = $release.contentDigest })
                sourceRecordBindings = @([pscustomobject]@{ recordRef = $evidence.recordId; contentDigest = $evidence.contentDigest })
                sourcePointers = @([pscustomobject]@{
                    recordRef = $evidence.recordId
                    contentDigest = $evidence.contentDigest
                    jsonPointer = if ($descriptor.EvidenceShape -ceq 'DENOMINATED_COUNT') { '/result/numeratorValue' }
                        elseif ($descriptor.EvidenceShape -ceq 'STRUCTURED_STATE') { '/result/state' }
                        else { '/result/status' }
                })
                coverage = New-FleetCoverageCommitment `
                    -Seed ([string]$descriptor.ClaimBindingId) `
                    -Purpose CLAIM_COVERAGE
                missingnessReasonCodes = @('SOURCE_RECORD_MISSING')
                exclusionRefs = @('private://fleet-exclusions/synthetic-1')
                baselineFingerprint = [string]$Chain.currentFleetIssue.baselineFingerprint
                observationWindow = [string]$Chain.currentFleetIssue.observationWindow
                provenanceTier = 'T0'
                corroborationRefs = @()
                sourceToolRef = 'systrack'
                sourceToolVersion = 'synthetic-1.0.0'
                queryPackRef = $QueryPackRecord.recordId
                queryPackDigest = $QueryPackRecord.contentDigest
                queryPackVersion = [string]$QueryPackRecord.payload.version
                artifactHashes = @($artifactHash)
                freshnessBinding = Copy-TestObject -InputObject $ClaimFreshnessBinding
                limitations = @('Synthetic fixture data only.')
                requalificationTriggerRefs = [object[]]@()
            }
            if ($descriptor.ClaimMetricType -ceq 'REQUALIFICATION_TRIGGER') {
                $claim.requalificationTriggerRefs = [object[]]@($RequalificationPlanRef)
            }
            if ($descriptor.EvidenceShape -ceq 'DISTRIBUTION') {
                $distribution = $distributionByClaimId[[string]$descriptor.ClaimBindingId]
                $claim.distributionRef = $distribution.recordId
                $claim.distributionDigest = $distribution.contentDigest
                $claim.denominator = [pscustomobject]@{ definition = 'Eligible current-fleet devices after governed exclusions.'; unit = 'devices'; value = $eligibleCount }
            }
            elseif ($descriptor.EvidenceShape -ceq 'DENOMINATED_COUNT') {
                $claim.structuredSummaryRef = $evidence.recordId
                $claim.structuredSummaryDigest = $evidence.contentDigest
                $claim.denominator = [pscustomobject]@{ definition = 'Eligible current-fleet devices after governed exclusions.'; unit = 'devices'; value = $eligibleCount }
                $claim.resultPointer = '/result/numeratorValue'
                $evidenceResult = (Get-TestRecordPayloadValue -Record $evidence -FieldName 'result').numeratorValue
                $claim.resultDigest = Get-CanonicalPayloadDigest -Payload $evidenceResult
                $claim.numeratorValue = [int]$evidenceResult
                $claim.rateValue = [Math]::Round((([double]$evidenceResult / [double]$eligibleCount) * 100), 9)
                $claim.rateScale = 'PERCENT'
            }
            else {
                $claim.structuredSummaryRef = $evidence.recordId
                $claim.structuredSummaryDigest = $evidence.contentDigest
                $claim.resultPointer = '/result/state'
                $claim.resultDigest = Get-CanonicalPayloadDigest -Payload (Get-TestRecordPayloadValue -Record $evidence -FieldName 'result').state
                $claim.resultValueType = 'STRING'
            }
            $claim.coverage.populationCommitmentDomainDigest = Get-FleetClaimCoverageDomainDigest `
                -FleetPortfolio $FleetPortfolioDomainContext -Claim ([pscustomobject]$claim)
            [void]$claims.Add([pscustomobject]$claim)
        }
        $dimension = [pscustomobject][ordered]@{
            dimensionId = $dimensionId
            status = 'PASS'
            claimBindings = @($claims)
            dimensionEvidenceDigest = $null
        }
        $dimension.dimensionEvidenceDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject][ordered]@{
            dimensionId = $dimension.dimensionId
            status = $dimension.status
            claimBindings = @($dimension.claimBindings)
        })
        $propertyName = [string]@($descriptors | Where-Object DimensionId -CEQ $dimensionId)[0].PropertyName
        $dimensions[$propertyName] = $dimension
    }

    $policyRef = 'leadership-claim-chain-v1.0.0#/currentFleetRequiredDimensions'
    $policyDigest = Get-CanonicalPayloadDigest -Payload ([object[]]@($Chain.currentFleetRequiredDimensions))
    $dimensionDigestBindings = @($Chain.currentFleetRequiredDimensions | ForEach-Object {
        $propertyName = [string]@($descriptors | Where-Object DimensionId -CEQ ([string]$_.dimensionId))[0].PropertyName
        [pscustomobject][ordered]@{
            dimensionId = [string]$_.dimensionId
            dimensionEvidenceDigest = [string]$dimensions[$propertyName].dimensionEvidenceDigest
        }
    })
    $bindingsDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject][ordered]@{
        dimensionPolicyRef = $policyRef
        dimensionPolicyDigest = $policyDigest
        dimensions = @($dimensionDigestBindings)
    })
    $policyExecutedAt = '2026-08-27T12:00:00Z'
    $dimensionCoverage = [ordered]@{
        dimensionPolicyId = 'CURRENT_FLEET_LEADERSHIP_DIMENSIONS_V1'
        dimensionPolicyVersion = '1.0.0'
        dimensionPolicyRef = $policyRef
        dimensionPolicyDigest = $policyDigest
        policyExecutionRef = 'private://policy-executions/fleet-dimensions-synthetic-1'
        policyExecutionDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject][ordered]@{
            dimensionPolicyRef = $policyRef
            dimensionPolicyDigest = $policyDigest
            policyExecutionToolRef = 'policy-as-code'
            policyExecutionToolVersion = 'synthetic-1.0.0'
            policyExecutedAt = $policyExecutedAt
            bindingsDigest = $bindingsDigest
        })
        policyExecutionToolRef = 'policy-as-code'
        policyExecutionToolVersion = 'synthetic-1.0.0'
        policyExecutedAt = $policyExecutedAt
        bindingsDigest = $bindingsDigest
    }
    foreach ($propertyName in $dimensions.Keys) { $dimensionCoverage[$propertyName] = $dimensions[$propertyName] }

    [pscustomobject]@{
        DimensionCoverage = [pscustomobject]$dimensionCoverage
        EvidenceRecords = @($evidenceRecords)
        DistributionRecords = @($distributionRecords)
        ReleaseRecord = $release
    }
}

function New-IssuedRecordIndexFixture {
    param($Chain)
    if ($null -eq $Chain) { $Chain = New-IssuedClaimChainFixture }
    $pilotNotRequiredReason = 'The synthetic fixture uses an explicitly governed no-pilot disposition.'
    $pilotVerdictRecordId = 'pilot-verdict-synthetic-1'
    $finalIssuanceApprovalRef = 'qualification-authority-approval-final-synthetic-1'
    $finalPilotWaiverApprovalRef = 'qualification-authority-approval-final-pilot-waiver-synthetic-1'
    $pilotIssuanceApprovalRef = 'qualification-authority-approval-pilot-synthetic-1'
    $pilotWaiverApprovalRef = 'qualification-authority-approval-pilot-waiver-synthetic-1'
    $personaVerdict = [pscustomobject]@{
        persona = 'persona-engineering-synthetic'
        verdict = 'HOLD'
        assignmentDisposition = 'BLOCKED'
        conflictsWithFleetConditions = $false
        conditionRefs = @('COND-SYNTHETIC-1')
        capacityWaterfall = [pscustomobject]@{
            thresholdPolicyRef = 'freshness-policy-synthetic-1'
            calculationEvidenceRef = 'evidence-persona-t0'
            memory = [pscustomobject]@{
                physicalMemoryGB = 64; corporateFloorGB = 12; memoryReserveGB = 8
                remainingWorkloadHeadroomGB = 44; personaRequirementGB = 32; outcome = 'PASS'
            }
            storage = [pscustomobject]@{
                formattedCapacityGB = 1000; corporateImageGB = 100; storageReserveGB = 100
                personaWorkingSetGB = 500; remainingWorkloadHeadroomGB = 300; outcome = 'PASS'
            }
        }
    }
    $procurementEnvelope = [pscustomobject]@{
        approvedSkus = @('SKU-SYNTHETIC-1')
        quantityScope = '1000 units'
        substitutionPolicy = [pscustomobject]@{
            silentSubstitutionAllowed = $false
            observableEquivalenceEvidenceRequired = $true
            materialDifferenceAction = 'DELTA_QUALIFICATION_REQUIRED'
            unknownIdentityDisposition = 'HOLD'
        }
        substitutionAssessments = @([pscustomobject]@{ identityStatus = 'KNOWN'; disposition = 'OBSERVABLY_EQUIVALENT' })
    }
    $verdictFields = @{
        schemaVersion = '2.0.1'
        recordStage = 'phase5-final'
        status = 'approved-and-immutable'
        immutableAt = '2026-08-27T12:20:00Z'
        manifestRef = 'manifest-synthetic-1'
        qualificationAuthority = 'ROLE_QUALIFICATION_AUTHORITY'
        approvers = @('ROLE_QUALIFICATION_AUTHORITY','ROLE_SECURITY_APPROVER')
        evidenceReleases = @(
            'persona-release-synthetic-1','fleet-release-synthetic-1',
            'candidate-release-synthetic-1','business-release-synthetic-1'
        )
        qualificationAuthorityApprovalRef = $finalIssuanceApprovalRef
        qualificationAuthorityApprovalDigest = New-TestDigest '6'
        pilotAuthorizationRecordRef = $pilotVerdictRecordId
        pilotAuthorizationRecordDigest = New-TestDigest '7'
        pilotNotRequiredApprovalRef = $finalPilotWaiverApprovalRef
        pilotNotRequiredApprovalDigest = New-TestDigest '8'
        provisionalLabVerdict = 'HOLD'
        pilotAuthorization = [pscustomobject]@{
            status = 'NOT_REQUIRED'
            reason = $pilotNotRequiredReason
        }
        pilotCompletion = [pscustomobject]@{
            status = 'NOT_REQUIRED'
            reason = $pilotNotRequiredReason
            authorityApprovalRef = $finalPilotWaiverApprovalRef
        }
        fleetVerdict = 'HOLD'
        fleetDeploymentDisposition = 'BLOCKED'
        personaVerdicts = @($personaVerdict)
        conditions = @([pscustomobject]@{ conditionId = 'COND-SYNTHETIC-1'; description = 'Synthetic retained condition metadata.'; owner = 'ROLE_QUALIFICATION_AUTHORITY'; expiration = '2026-08-28'; closureEvidence = @('fixture://closure') })
        exceptions = @()
        arbitration = [pscustomobject]@{ required = $false; triggers = @() }
        deadlineDecision = [pscustomobject]@{
            deadlineStatus = 'before-deadline'
            evidenceState = 'conclusive'
            decision = 'no-purchase'
        }
        procurementEnvelope = $procurementEnvelope
        procurementDisposition = 'BLOCKED'
        residualRisks = @('none identified in synthetic fixture')
        requalificationTriggers = @('baseline-change')
        recommendationStatement = $Chain.recommendation.statement
    }
    $manifestFields = @{
        schemaVersion = '2.0.1'
        status = 'frozen'
        frozenAt = '2026-08-27T08:00:00Z'
        qualificationAuthority = 'ROLE_QUALIFICATION_AUTHORITY'
        hardwareEnvelope = [pscustomobject][ordered]@{
            productFamily = 'Synthetic Qualification Laptop'
            orderableSkus = @('SKU-SYNTHETIC-1')
            cpu = 'Synthetic x64 processor'
            memory = [pscustomobject][ordered]@{ totalGB = 64; configuration = '2x32GB' }
            storage = [pscustomobject][ordered]@{ minCapacityGB = 1000; approvedSsdClasses = @('synthetic-nvme') }
            approvedWlanModules = @('synthetic-wlan-1')
            approvedPanels = @('synthetic-panel-1')
            batteryClass = 'synthetic-battery-1'
        }
        personas = @([pscustomobject][ordered]@{
            name = 'persona-engineering-synthetic'
            workloadRequirement = 'Synthetic engineering workload capacity requirement.'
            extensions = [pscustomobject][ordered]@{
                operationsBlueprintV1 = [pscustomobject][ordered]@{
                    personaRequirementGB = 32
                    personaWorkingSetGB = 500
                }
            }
        })
        evidenceReleases = @(
            'persona-release-synthetic-1','fleet-release-synthetic-1',
            'candidate-release-synthetic-1','business-release-synthetic-1'
        )
        candidateDevices = @([pscustomobject]@{ candidateId = 'candidate-synthetic-1' })
        controls = [pscustomobject]@{
            incumbent = [pscustomobject]@{ controlId = 'incumbent-synthetic-1' }
            'sibling-or-alternative' = [pscustomobject]@{ controlId = 'sibling-synthetic-1' }
        }
        pilotPopulationPlan = [pscustomobject]@{
            targetCount = 30
            privacyOwner = 'ROLE_PRIVACY_APPROVER'
            volunteerOnly = $true
            selectionDimensions = @('persona','region','work-pattern')
            dimensions = @(
                [pscustomobject]@{ dimension = 'persona'; categories = @([pscustomobject]@{ category = 'persona-engineering-synthetic'; plannedCount = 30 }) },
                [pscustomobject]@{ dimension = 'region'; categories = @([pscustomobject]@{ category = 'region-synthetic-1'; plannedCount = 30 }) },
                [pscustomobject]@{ dimension = 'work-pattern'; categories = @([pscustomobject]@{ category = 'hybrid'; plannedCount = 30 }) }
            )
        }
        testPlanRef = 'test-plan-synthetic-1'
        thresholdPolicyRef = 'freshness-policy-synthetic-1'
    }
    $requiredDependencyFields = @(
        'windowsBuild',
        'biosVersion',
        'driverPackVersion',
        'corporateImageVersion',
        'securityAgentSetDigest',
        'conditionSetDigest',
        'testPackVersion'
    )
    $freshnessPolicyFields = @{
        leadershipFreshness = [pscustomobject][ordered]@{
            personaNeed = [pscustomobject]@{ maxAgeDays = 30; requiredDependencyFields = @($requiredDependencyFields) }
            currentFleetIssue = [pscustomobject]@{ maxAgeDays = 365; requiredDependencyFields = @($requiredDependencyFields) }
            candidateComparison = [pscustomobject]@{ maxAgeDays = 30; requiredDependencyFields = @($requiredDependencyFields) }
            businessEffect = [pscustomobject]@{ maxAgeDays = 365; requiredDependencyFields = @($requiredDependencyFields) }
            recommendation = [pscustomobject]@{ maxAgeDays = 30; requiredDependencyFields = @($requiredDependencyFields) }
        }
    }
    $freshnessPolicyFields.extensions = [pscustomobject][ordered]@{
        leadershipFreshness = Copy-TestObject -InputObject $freshnessPolicyFields.leadershipFreshness
        operationsBlueprintV1 = [pscustomobject][ordered]@{
            phase3ContemporaneityWindowHours = 24
            phase3ContemporaneityRationale = 'Synthetic frozen comparison window for same-run candidate and controls.'
            phase3ContemporaneityApprovedBy = 'ROLE_QUALIFICATION_AUTHORITY'
            capacityArithmeticToleranceGB = 0.000001
            capacityArithmeticToleranceRationale = 'Synthetic exact-decimal capacity reconciliation tolerance.'
            capacityArithmeticToleranceApprovedBy = 'ROLE_QUALIFICATION_AUTHORITY'
            capacityCorporateFloorMetricId = 'corporate-floor-memory-gb'
            capacityCorporateImageMetricId = 'corporate-image-storage-gb'
        }
    }
    $freshnessPolicyFields.thresholds = [pscustomobject][ordered]@{
        minTelemetryCoveragePct = [pscustomobject][ordered]@{ value = 80 }
    }
    $freshnessPolicyFields.reserves = [pscustomobject][ordered]@{
        memoryReserveGB = [pscustomobject][ordered]@{ value = 8 }
        storageReserveGB = [pscustomobject][ordered]@{ value = 100 }
    }
    $baselineSnapshot = New-LeadershipDependencySnapshotFixture
    $baselineFields = @{
        dependencySnapshot = $baselineSnapshot
        dependencySnapshotDigest = Get-CanonicalPayloadDigest -Payload $baselineSnapshot
        dependencyStatus = 'CURRENT'
    }
    $personaSourceFreshness = New-SourceFreshnessBinding $Chain.personaNeed.freshness
    $fleetSourceFreshness = New-SourceFreshnessBinding $Chain.currentFleetIssue.freshness
    $candidateSourceFreshness = New-SourceFreshnessBinding $Chain.candidateComparison.freshness
    $businessSourceFreshness = New-SourceFreshnessBinding $Chain.businessEffect.freshness
    $recommendationSourceFreshness = New-SourceFreshnessBinding $Chain.recommendation.freshness
    $verdictFields.freshnessBinding = $recommendationSourceFreshness
    $testPlanRecord = New-CanonicalRecord 'test-plan-synthetic-1' 'test-plan' @('/samplingFloors','/tests') -Fields (
        New-FrozenTestPlanFields -ManifestRef 'manifest-synthetic-1' -ThresholdPolicyRef 'freshness-policy-synthetic-1'
    )
    $testPlanDefinitions = @(Get-TestRecordPayloadValue -Record $testPlanRecord -FieldName 'tests')
    $applicationCompatibilityTest = @($testPlanDefinitions | Where-Object { [string]$_.class -ceq 'application-compatibility' })[0]
    $productionPilotTest = @($testPlanDefinitions | Where-Object { [string]$_.class -ceq 'production-pilot' })[0]
    $candidateComparisonContract = New-Phase3CandidateComparisonFixture `
        -Chain $Chain -TestPlanRecord $testPlanRecord -SourceFreshnessBinding $candidateSourceFreshness
    $Chain.candidateComparison.conditionRefs = @($candidateComparisonContract.ConditionRefs)
    $Chain.candidateComparison.evidenceRefs = @($candidateComparisonContract.EvidenceRefs)
    $freshnessPolicyRecord = New-CanonicalRecord 'freshness-policy-synthetic-1' 'threshold-policy' @(
        '/leadershipFreshness/personaNeed','/leadershipFreshness/currentFleetIssue',
        '/leadershipFreshness/candidateComparison','/leadershipFreshness/businessEffect',
        '/leadershipFreshness/recommendation','/extensions/leadershipFreshness/currentFleetIssue',
        '/extensions/leadershipFreshness/currentFleetIssue/maxAgeDays',
        '/thresholds/minTelemetryCoveragePct/value'
    ) -Fields $freshnessPolicyFields
    $platformBaselineRecord = New-CanonicalRecord 'platform-baseline-synthetic-1' 'platform-baseline-record' @('/dependencySnapshot') -Fields $baselineFields
    $fleetContractFreshness = New-FleetPortfolioFreshnessBinding `
        -SourceFreshness $fleetSourceFreshness `
        -ThresholdPolicyRecord $freshnessPolicyRecord `
        -PlatformBaselineRecord $platformBaselineRecord
    $manifestRecord = New-CanonicalRecord 'manifest-synthetic-1' 'candidate-manifest' @(
        '/candidateDevices/0','/controls/incumbent','/controls/sibling-or-alternative'
    ) -Fields $manifestFields
    $verdictRecord = New-CanonicalRecord 'verdict-synthetic-1' 'verdict-record' @(
        '/fleetVerdict','/personaVerdicts/0','/personaVerdicts/0/capacityWaterfall',
        '/procurementEnvelope','/requalificationTriggers/0'
    ) -Fields $verdictFields
    $pilotVerdictRecord = New-CanonicalRecord $pilotVerdictRecordId 'verdict-record' -Fields @{
        schemaVersion = '2.0.1'
        recordStage = 'pilot-authorization'
        status = 'approved-and-immutable'
        immutableAt = '2026-08-27T12:12:00Z'
        manifestRef = 'manifest-synthetic-1'
        qualificationAuthority = 'ROLE_QUALIFICATION_AUTHORITY'
        approvers = @('ROLE_QUALIFICATION_AUTHORITY','ROLE_SECURITY_APPROVER')
        evidenceReleases = @('candidate-release-synthetic-1')
        qualificationAuthorityApprovalRef = $pilotIssuanceApprovalRef
        qualificationAuthorityApprovalDigest = New-TestDigest '6'
        pilotNotRequiredApprovalRef = $pilotWaiverApprovalRef
        pilotNotRequiredApprovalDigest = New-TestDigest '8'
        provisionalLabVerdict = 'QUALIFY'
        pilotAuthorization = [pscustomobject]@{
            status = 'NOT_REQUIRED'
            reason = $pilotNotRequiredReason
        }
        pilotPopulationPlanRef = 'manifest-synthetic-1#/pilotPopulationPlan'
        privacyOwner = 'ROLE_PRIVACY_APPROVER'
        freshnessBinding = New-SourceFreshnessBinding -Freshness $Chain.recommendation.freshness `
            -ObservedAt '2026-08-27T12:12:00Z' -AdmittedAt '2026-08-27T12:12:00Z'
    }
    $fleetDimensionDescriptors = @(Get-FleetDimensionClaimDescriptors -Chain $Chain)
    $fleetQueryPack = New-CanonicalRecord 'fleet-query-pack-synthetic-1' 'query-pack-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'TELEMETRY_QUERY_PACK'
        status = 'APPROVED'
        artifactRef = 'private://fleet-query-packs/synthetic-1'
        digest = New-TestDigest '8'
        version = '1.0.0'
        sourceToolRefs = @('systrack','microsoft-graph-readback')
        metricIds = @('fleet-device-inventory','fleet-issue-prevalence') + @($fleetDimensionDescriptors | ForEach-Object MetricId)
        ownerRole = 'ROLE_MONITORING_OWNER'
        approvedAt = '2026-03-31T00:00:00Z'
        expiresAt = '2026-09-30T00:00:00Z'
    }
    $fleetIssueEvidenceRecord = New-EvidenceRecord 'evidence-incumbent-t0' 'current-fleet-issue' -Fields @{
        subjectRef = 'manifest-synthetic-1#/controls/incumbent'
        controlRole = 'incumbent'
        cohortRef = 'cohort-synthetic-1'
        issueStatement = 'Synthetic incumbent incident rate exceeded the fixture threshold during the observation window.'
        attributionClass = 'ASSOCIATION'
        observationWindow = [string]$Chain.currentFleetIssue.observationWindow
        baselineFingerprint = [string]$Chain.currentFleetIssue.baselineFingerprint
        testPlanRef = [string]$testPlanRecord.recordId
        testRef = [string]$productionPilotTest.testId
        conditionRef = [string]$productionPilotTest.conditions[0].conditionId
        testPackVersion = [string]$productionPilotTest.testPackVersion
        evidenceReleaseRef = 'fleet-release-synthetic-1'
        distributionRef = 'distribution-fleet-synthetic-1'
        coverageStatus = 'PASS'
        freshnessBinding = $fleetSourceFreshness
    }
    $incidentEvidenceRecord = New-EvidenceRecord 'incident-release-t0' 'current-fleet-issue' -Fields @{
        subjectRef = 'manifest-synthetic-1#/controls/incumbent'
        controlRole = 'incumbent'
        cohortRef = 'cohort-synthetic-1'
        observationWindow = [string]$Chain.currentFleetIssue.observationWindow
        baselineFingerprint = [string]$Chain.currentFleetIssue.baselineFingerprint
        testPlanRef = [string]$testPlanRecord.recordId
        testRef = [string]$productionPilotTest.testId
        conditionRef = [string]$productionPilotTest.conditions[0].conditionId
        testPackVersion = [string]$productionPilotTest.testPackVersion
        evidenceReleaseRef = 'fleet-release-synthetic-1'
        distributionRef = 'distribution-incident-synthetic-1'
        coverageStatus = 'PASS'
        freshnessBinding = $fleetSourceFreshness
    }
    $fleetIssueDistributionRecord = New-DistributionRecord 'distribution-fleet-synthetic-1' 'evidence-incumbent-t0' $testPlanRecord `
        -TestClass 'production-pilot' -TestRef ([string]$productionPilotTest.testId) `
        -ConditionRef ([string]$productionPilotTest.conditions[0].conditionId) `
        -BaselineFingerprint ([string]$Chain.currentFleetIssue.baselineFingerprint) -UnitCount 30 -RunCount 300
    $incidentDistributionRecord = New-DistributionRecord 'distribution-incident-synthetic-1' 'incident-release-t0' $testPlanRecord `
        -TestClass 'production-pilot' -TestRef ([string]$productionPilotTest.testId) `
        -ConditionRef ([string]$productionPilotTest.conditions[0].conditionId) `
        -BaselineFingerprint ([string]$Chain.currentFleetIssue.baselineFingerprint) -UnitCount 30 -RunCount 300
    Set-TestPortableDistributionCrosswalk -EvidenceRecord $fleetIssueEvidenceRecord -DistributionRecord $fleetIssueDistributionRecord
    Set-TestPortableDistributionCrosswalk -EvidenceRecord $incidentEvidenceRecord -DistributionRecord $incidentDistributionRecord
    $requalificationPlanRecord = New-CanonicalRecord 'fleet-requalification-plan-synthetic-1' 'requalification-plan-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'REQUALIFICATION_PLAN'
        status = 'APPROVED'
        verdictRef = $verdictRecord.recordId
        verdictDigest = $verdictRecord.contentDigest
        requalificationTriggersPointer = 'verdict-synthetic-1#/requalificationTriggers/0'
        thresholdPolicyRef = $freshnessPolicyRecord.recordId
        thresholdPolicyDigest = $freshnessPolicyRecord.contentDigest
        stopConditionsRef = 'stop-conditions-synthetic-placeholder'
        stopConditionsDigest = New-TestDigest '4'
        rollbackRef = 'rollback-synthetic-placeholder'
        rollbackDigest = New-TestDigest '5'
        triggerActions = @([pscustomobject]@{
            triggerId = 'baseline-change'
            triggerPointer = 'verdict-synthetic-1#/requalificationTriggers/0'
            action = 'FULL_REQUALIFICATION'
            ownerRole = 'ROLE_QUALIFICATION_AUTHORITY'
            alertRouteRef = 'private://alert-routes/requalification-synthetic-1'
        })
        ownerRole = 'ROLE_QUALIFICATION_AUTHORITY'
        alertRouteRef = 'private://alert-routes/requalification-synthetic-1'
        approvedAt = '2026-08-27T11:30:00Z'
        expiresAt = '2026-09-30T00:00:00Z'
    }
    $fleetPortfolioDomainContext = [pscustomobject][ordered]@{
        recordId = 'fleet-portfolio-synthetic-1'
        privacyReleaseRef = 'private://privacy-releases/fleet-portfolio-synthetic-1'
        privacyReleaseDigest = New-TestDigest '2'
        snapshotAt = [string]$Chain.currentFleetIssue.freshness.observedAt
        observationWindow = [string]$Chain.currentFleetIssue.observationWindow
        populationCohortRef = [string]$Chain.currentFleetIssue.cohortRef
    }
    $fleetDimensionContract = New-FleetDimensionContractFixture `
        -Chain $Chain `
        -FleetPortfolioDomainContext $fleetPortfolioDomainContext `
        -Phase0TestPlanRecord $testPlanRecord `
        -QueryPackRecord $fleetQueryPack `
        -SourceFreshnessBinding $fleetSourceFreshness `
        -ClaimFreshnessBinding $fleetContractFreshness `
        -AdditionalMemberRecords @(
            $fleetIssueEvidenceRecord,
            $incidentEvidenceRecord,
            $fleetIssueDistributionRecord,
            $incidentDistributionRecord
        ) `
        -RequalificationPlanRef $requalificationPlanRecord.recordId
    $fleetPlannedPopulationDigest = Get-Sha256TokenFromText -Text 'fleet-population-set:planned-synthetic-1'
    $fleetPortfolioCoverage = New-FleetCoverageCommitment `
        -Seed 'portfolio-synthetic-1' `
        -Purpose PORTFOLIO_COVERAGE `
        -PlannedPopulationDigest $fleetPlannedPopulationDigest
    $fleetPersonaAllocation = [pscustomobject][ordered]@{
        personaId = [string]$Chain.personaNeed.personaId
        cohortRef = [string]$Chain.currentFleetIssue.cohortRef
        observedDeviceCount = 25
        observedPopulationDigest = Get-Sha256TokenFromText -Text 'fleet-population-set:persona-engineering-synthetic-1:observed'
        populationSubsetProofRef = 'private://fleet-population-proofs/persona-engineering-synthetic-1/subset'
        populationSubsetProofDigest = Get-Sha256TokenFromText -Text 'fleet-population-proof:persona-engineering-synthetic-1:subset'
    }
    $fleetPersonaAllocation = Set-FleetPopulationMetadata `
        -Target $fleetPersonaAllocation -Seed 'persona-engineering-synthetic-1' -Purpose PERSONA_ALLOCATION
    $fleetConfigurationCohort = [pscustomobject][ordered]@{
        configurationRef = [string]$Chain.currentFleetIssue.incumbentControlRef
        cohortRef = [string]$Chain.currentFleetIssue.cohortRef
        observedDeviceCount = 30
        observedPopulationDigest = Get-Sha256TokenFromText -Text 'fleet-population-set:configuration-synthetic-1:observed'
        unknownComponentIdentityCount = 2
        personaAllocations = @($fleetPersonaAllocation)
        unassignedPersonaCount = 5
        unassignedPopulationDigest = Get-Sha256TokenFromText -Text 'fleet-population-set:configuration-synthetic-1:unassigned'
        populationSubsetProofRef = 'private://fleet-population-proofs/configuration-synthetic-1/subset'
        populationSubsetProofDigest = Get-Sha256TokenFromText -Text 'fleet-population-proof:configuration-synthetic-1:subset'
        personaPartitionProofRef = 'private://fleet-population-proofs/configuration-synthetic-1/persona-partition'
        personaPartitionProofDigest = Get-Sha256TokenFromText -Text 'fleet-population-proof:configuration-synthetic-1:persona-partition'
        lifecycleEvidenceRefs = @('incident-release-t0')
        platformEvidenceRefs = @('evidence-incumbent-t0')
        issueEvidenceRefs = @('evidence-incumbent-t0')
    }
    $fleetConfigurationCohort = Set-FleetPopulationMetadata `
        -Target $fleetConfigurationCohort -Seed 'configuration-synthetic-1' -Purpose CONFIGURATION_COHORT
    $fleetPortfolioFields = @{
        schemaVersion = '1.0.0'
        recordStage = 'CURRENT_FLEET_PORTFOLIO'
        status = 'ISSUED'
        snapshotAt = [string]$Chain.currentFleetIssue.freshness.observedAt
        observationWindow = [string]$Chain.currentFleetIssue.observationWindow
        populationCohortRef = [string]$Chain.currentFleetIssue.cohortRef
        joinPolicyRef = 'private://fleet-join-policies/mutually-exclusive-precedence-v1'
        joinPolicyDigest = New-TestDigest '7'
        queryPackRef = $fleetQueryPack.recordId
        queryPackDigest = $fleetQueryPack.contentDigest
        privacyPolicyRef = 'private://privacy-policies/fleet-portfolio-synthetic-1'
        privacyPolicyDigest = New-TestDigest '1'
        privacyReleaseRef = 'private://privacy-releases/fleet-portfolio-synthetic-1'
        privacyReleaseDigest = New-TestDigest '2'
        privacyAggregationFloorPointer = '/aggregationFloor'
        privacyAggregationFloorDigest = Get-CanonicalPayloadDigest -Payload 10
        aggregationFloor = 10
        minimumCoveragePointer = '/thresholds/minTelemetryCoveragePct/value'
        minimumCoverageValueDigest = Get-CanonicalPayloadDigest -Payload 80
        minimumCoveragePct = 80
        coverage = $fleetPortfolioCoverage
        dimensionCoverage = $fleetDimensionContract.DimensionCoverage
        configurationCohorts = @($fleetConfigurationCohort)
        configurationPartitionProofRef = 'private://fleet-population-proofs/portfolio-synthetic-1/configuration-partition'
        configurationPartitionProofDigest = Get-Sha256TokenFromText -Text 'fleet-population-proof:portfolio-synthetic-1:configuration-partition'
        sourceRecordCount = 42
        uniqueDeviceCount = 40
        duplicateRecordCount = 2
        staleDeviceCount = 2
        retiredDeviceCount = 2
        offlineDeviceCount = 2
        unhealthyDeviceCount = 2
        joinEligibleDeviceCount = 32
        joinedDeviceCount = 30
        unjoinableDeviceCount = 2
        matchedDeviceCount = 30
        unmatchedDeviceCount = 0
        reconciliationMethod = 'MUTUALLY_EXCLUSIVE_PRECEDENCE_V1'
        reconciliationStatus = 'PASS'
        reconciliationEvidenceRef = 'private://fleet-reconciliation/synthetic-1'
        reconciliationEvidenceDigest = New-TestDigest '9'
        sourceEvidenceReleaseBindings = @([pscustomobject]@{
            recordRef = $fleetDimensionContract.ReleaseRecord.recordId
            contentDigest = $fleetDimensionContract.ReleaseRecord.contentDigest
        })
        freshnessBinding = $fleetContractFreshness
    }
    $fleetPortfolioDomainContext | Add-Member -NotePropertyName coverage -NotePropertyValue $fleetPortfolioCoverage
    $fleetPortfolioCoverage.populationCommitmentDomainDigest = Get-FleetPortfolioCoverageDomainDigest `
        -FleetPortfolio $fleetPortfolioDomainContext
    $fleetConfigurationCohort.populationCommitmentDomainDigest = Get-FleetConfigurationPopulationDomainDigest `
        -FleetPortfolio $fleetPortfolioDomainContext -ConfigurationCohort $fleetConfigurationCohort
    $fleetPersonaAllocation.populationCommitmentDomainDigest = Get-FleetPersonaPopulationDomainDigest `
        -FleetPortfolio $fleetPortfolioDomainContext `
        -ConfigurationCohort $fleetConfigurationCohort `
        -PersonaAllocation $fleetPersonaAllocation
    $candidateReleaseRecord = Initialize-TestEvidenceReleaseSubject (New-CanonicalRecord 'candidate-release-synthetic-1' 'evidence-release' @('/memberRecordIds') -Fields @{
        memberRecordIds = @($candidateComparisonContract.MemberRecordIds)
        semanticGateStatus = 'PASS'
        samplingFloorStatus = 'PASS'
        distributionStatus = 'PASS'
        coverageStatus = 'PASS'
        testPlanRef = [string]$testPlanRecord.recordId
        conditionRefs = @($candidateComparisonContract.ConditionRefs)
        baselineFingerprint = [string]$Chain.candidateComparison.baselineFingerprint
        testPackVersion = 'test-pack-synthetic-1'
        releasedAt = '2026-08-27T11:30:00Z'
        freshnessBinding = $candidateSourceFreshness
    })
    $corporateFloorTest = @($testPlanDefinitions | Where-Object { [string]$_.class -ceq 'corporate-floor' })[0]
    $capacityCorporateFloorEvidence = New-EvidenceRecord 'evidence-capacity-corporate-floor-t0' 'capacity-corporate-floor' -Fields @{
        subjectRef = 'manifest-synthetic-1'
        controlRole = 'candidate'
        testPlanRef = [string]$testPlanRecord.recordId
        testRef = [string]$corporateFloorTest.testId
        conditionRef = [string]$corporateFloorTest.conditions[0].conditionId
        baselineFingerprint = [string]$Chain.candidateComparison.baselineFingerprint
        testPackVersion = [string]$corporateFloorTest.testPackVersion
        evidenceReleaseRef = 'persona-release-synthetic-1'
        distributionRef = 'distribution-capacity-corporate-floor-synthetic-1'
        coverageStatus = 'PASS'
        freshnessBinding = $candidateSourceFreshness
    }
    $capacityCorporateFloorDistribution = New-DistributionRecord `
        'distribution-capacity-corporate-floor-synthetic-1' 'evidence-capacity-corporate-floor-t0' $testPlanRecord `
        -TestClass 'corporate-floor' -TestRef ([string]$corporateFloorTest.testId) `
        -ConditionRef ([string]$corporateFloorTest.conditions[0].conditionId) `
        -BaselineFingerprint ([string]$Chain.candidateComparison.baselineFingerprint)
    $capacityCorporateFloorDistribution.payload.metricId = 'corporate-floor-memory-gb'
    $capacityCorporateFloorDistribution.payload.unit = 'GB'
    $capacityCorporateFloorDistribution.payload.median = 12
    $capacityCorporateFloorDistribution.payload.spread = [pscustomobject]@{ minimum = 12; maximum = 12 }
    $capacityCorporateFloorDistribution.payload.runVariation = [pscustomobject]@{
        minimum = 12; maximum = 12; coefficientOfVariation = 0
    }
    Update-CanonicalRecordBinding $capacityCorporateFloorDistribution
    Set-TestPortableDistributionCrosswalk `
        -EvidenceRecord $capacityCorporateFloorEvidence -DistributionRecord $capacityCorporateFloorDistribution

    $capacityCorporateImageEvidence = New-EvidenceRecord 'evidence-capacity-corporate-image-t0' 'capacity-corporate-image' -Fields @{
        subjectRef = 'manifest-synthetic-1'
        controlRole = 'candidate'
        testPlanRef = [string]$testPlanRecord.recordId
        testRef = [string]$corporateFloorTest.testId
        conditionRef = [string]$corporateFloorTest.conditions[0].conditionId
        baselineFingerprint = [string]$Chain.candidateComparison.baselineFingerprint
        testPackVersion = [string]$corporateFloorTest.testPackVersion
        evidenceReleaseRef = 'persona-release-synthetic-1'
        distributionRef = 'distribution-capacity-corporate-image-synthetic-1'
        coverageStatus = 'PASS'
        freshnessBinding = $candidateSourceFreshness
    }
    $capacityCorporateImageDistribution = New-DistributionRecord `
        'distribution-capacity-corporate-image-synthetic-1' 'evidence-capacity-corporate-image-t0' $testPlanRecord `
        -TestClass 'corporate-floor' -TestRef ([string]$corporateFloorTest.testId) `
        -ConditionRef ([string]$corporateFloorTest.conditions[0].conditionId) `
        -BaselineFingerprint ([string]$Chain.candidateComparison.baselineFingerprint)
    $capacityCorporateImageDistribution.payload.metricId = 'corporate-image-storage-gb'
    $capacityCorporateImageDistribution.payload.unit = 'GB'
    $capacityCorporateImageDistribution.payload.median = 100
    $capacityCorporateImageDistribution.payload.spread = [pscustomobject]@{ minimum = 100; maximum = 100 }
    $capacityCorporateImageDistribution.payload.runVariation = [pscustomobject]@{
        minimum = 100; maximum = 100; coefficientOfVariation = 0
    }
    Update-CanonicalRecordBinding $capacityCorporateImageDistribution
    Set-TestPortableDistributionCrosswalk `
        -EvidenceRecord $capacityCorporateImageEvidence -DistributionRecord $capacityCorporateImageDistribution

    $personaEvidenceRecord = New-EvidenceRecord 'evidence-persona-t0' 'persona-fit' -Fields @{
        subjectRef = 'manifest-synthetic-1'
        controlRole = 'candidate'
        personaId = 'persona-engineering-synthetic'
        capacityWaterfallPointer = 'verdict-synthetic-1#/personaVerdicts/0/capacityWaterfall'
        testPlanRef = [string]$testPlanRecord.recordId
        testRef = [string]$applicationCompatibilityTest.testId
        conditionRef = [string]$applicationCompatibilityTest.conditions[0].conditionId
        baselineFingerprint = New-TestDigest 'b'
        testPackVersion = [string]$applicationCompatibilityTest.testPackVersion
        evidenceReleaseRef = 'persona-release-synthetic-1'
        distributionRef = 'distribution-persona-synthetic-1'
        coverageStatus = 'PASS'
        freshnessBinding = $personaSourceFreshness
        result = [pscustomobject][ordered]@{
            status = 'PASS'
            capacityWaterfall = Copy-TestObject -InputObject $personaVerdict.capacityWaterfall
        }
    }
    $personaDistributionRecord = New-DistributionRecord 'distribution-persona-synthetic-1' 'evidence-persona-t0' $testPlanRecord `
        -TestClass 'application-compatibility' -TestRef ([string]$applicationCompatibilityTest.testId) `
        -ConditionRef ([string]$applicationCompatibilityTest.conditions[0].conditionId) `
        -BaselineFingerprint (New-TestDigest 'b') -UnitCount 2 -RunCount 4
    Set-TestPortableDistributionCrosswalk -EvidenceRecord $personaEvidenceRecord -DistributionRecord $personaDistributionRecord
    $personaReleaseRecord = Initialize-TestEvidenceReleaseSubject (New-CanonicalRecord 'persona-release-synthetic-1' 'evidence-release' @('/memberRecordIds') -Fields @{
        memberRecordIds = @(
            'evidence-persona-t0','distribution-persona-synthetic-1',
            'evidence-capacity-corporate-floor-t0','distribution-capacity-corporate-floor-synthetic-1',
            'evidence-capacity-corporate-image-t0','distribution-capacity-corporate-image-synthetic-1'
        )
        semanticGateStatus = 'PASS'; samplingFloorStatus = 'PASS'; distributionStatus = 'PASS'; coverageStatus = 'PASS'
        testPlanRef = [string]$testPlanRecord.recordId
        testPlanDigest = [string]$testPlanRecord.contentDigest
        thresholdPolicyRef = [string]$freshnessPolicyRecord.recordId
        thresholdPolicyDigest = [string]$freshnessPolicyRecord.contentDigest
        releasedAt = '2026-08-27T11:30:00Z'
        freshnessBinding = $personaSourceFreshness
    })
    $businessEvidenceRecord = New-EvidenceRecord 'business-impact-t0' 'business-impact' -Fields @{
        businessEffectRef = 'business-impact-synthetic-1'
        subjectRef = 'manifest-synthetic-1#/candidateDevices/0'
        controlRole = 'candidate'
        observationWindow = [string]$Chain.businessEffect.observationWindow
        testPlanRef = [string]$testPlanRecord.recordId
        testRef = [string]$productionPilotTest.testId
        conditionRef = [string]$productionPilotTest.conditions[0].conditionId
        baselineFingerprint = New-TestDigest 'b'
        testPackVersion = [string]$productionPilotTest.testPackVersion
        evidenceReleaseRef = 'business-release-synthetic-1'
        distributionRef = 'distribution-business-synthetic-1'
        coverageStatus = 'PASS'
        freshnessBinding = $businessSourceFreshness
    }
    $businessDistributionRecord = New-DistributionRecord 'distribution-business-synthetic-1' 'business-impact-t0' $testPlanRecord `
        -TestClass 'production-pilot' -TestRef ([string]$productionPilotTest.testId) `
        -ConditionRef ([string]$productionPilotTest.conditions[0].conditionId) `
        -BaselineFingerprint (New-TestDigest 'b') -UnitCount 30 -RunCount 300
    Set-TestPortableDistributionCrosswalk -EvidenceRecord $businessEvidenceRecord -DistributionRecord $businessDistributionRecord
    $businessReleaseRecord = Initialize-TestEvidenceReleaseSubject (New-CanonicalRecord 'business-release-synthetic-1' 'evidence-release' @('/memberRecordIds') -Fields @{
        memberRecordIds = @('business-impact-t0','distribution-business-synthetic-1')
        semanticGateStatus = 'PASS'; samplingFloorStatus = 'PASS'; distributionStatus = 'PASS'; coverageStatus = 'PASS'
        releasedAt = '2026-08-27T11:30:00Z'
        freshnessBinding = $businessSourceFreshness
    })
    $records = @(
        $freshnessPolicyRecord,
        $platformBaselineRecord,
        $fleetQueryPack,
        $manifestRecord,
        $verdictRecord,
        $pilotVerdictRecord,
        $personaEvidenceRecord,
        $personaDistributionRecord,
        $capacityCorporateFloorEvidence,
        $capacityCorporateFloorDistribution,
        $capacityCorporateImageEvidence,
        $capacityCorporateImageDistribution,
        $personaReleaseRecord,
        (New-CanonicalRecord 'cohort-synthetic-1' 'cohort-record' -Fields @{
            cohortId = 'cohort-synthetic-1'
            asOf = [string]$Chain.currentFleetIssue.freshness.observedAt
            personaIds = @('persona-engineering-synthetic')
            deviceConfigurationRefs = @('manifest-synthetic-1#/controls/incumbent')
            population = [pscustomobject]@{ eligibleUnits = 35; observedUnits = 30; missingUnits = 5; coveragePercent = 85.7142857142857 }
            evidenceReleaseRefs = @('fleet-release-synthetic-1')
            freshnessBinding = $fleetSourceFreshness
        }),
        (New-CanonicalRecord 'fleet-portfolio-synthetic-1' 'fleet-portfolio-record' @('/configurationCohorts/0') -Fields $fleetPortfolioFields),
        $fleetIssueEvidenceRecord,
        $incidentEvidenceRecord,
        $fleetIssueDistributionRecord,
        $incidentDistributionRecord,
        @($fleetDimensionContract.EvidenceRecords),
        @($fleetDimensionContract.DistributionRecords),
        $fleetDimensionContract.ReleaseRecord,
        $requalificationPlanRecord,
        $testPlanRecord,
        @($candidateComparisonContract.EvidenceRecords),
        @($candidateComparisonContract.DistributionRecords),
        $candidateReleaseRecord,
        (New-CanonicalRecord 'candidate-quote-synthetic-1' 'commercial-quote-record' -ValidUntil '2026-09-30T00:00:00Z' -Fields @{ subjectRef = 'manifest-synthetic-1#/candidateDevices/0'; configurationEnvelopePointer = 'verdict-synthetic-1#/procurementEnvelope'; currency = 'USD'; quantity = 1000; unitPrice = 1500; totalPrice = 1500000; quotedAt = '2026-08-20T00:00:00Z'; freshnessBinding = $businessSourceFreshness }),
        (New-CanonicalRecord 'control-quote-synthetic-1' 'commercial-quote-record' -ValidUntil '2026-09-30T00:00:00Z' -Fields @{ subjectRef = 'manifest-synthetic-1#/controls/incumbent'; configurationEnvelopePointer = 'manifest-synthetic-1#/controls/incumbent'; currency = 'USD'; quantity = 1000; unitPrice = 1200; totalPrice = 1200000; quotedAt = '2026-08-20T00:00:00Z'; freshnessBinding = $businessSourceFreshness }),
        (New-CanonicalRecord 'business-impact-synthetic-1' 'business-impact-record' @('/businessEffectStatement','/observationWindow','/assumptions','/calculation') -Fields @{
            effectType = 'COST_DELTA'; businessEffectStatement = 'Synthetic measured business effect used only by the unit test.'; observationWindow = [string]$Chain.businessEffect.observationWindow; assumptions = @('Synthetic prices and time values are fixture data, not a portfolio claim.'); currency = 'USD'; quantity = 1000; candidateQuoteRef = 'candidate-quote-synthetic-1'; controlQuoteRef = 'control-quote-synthetic-1'; quoteValidUntil = '2026-09-30T00:00:00Z'; calculation = [pscustomobject]@{ method = 'candidate-total-minus-control-total'; result = 300000 }; calculationMethod = 'candidate-total-minus-control-total'; calculationResult = 300000; resultUnit = 'USD'; uncertainty = 'Synthetic fixture uncertainty; no real financial claim.'; freshnessBinding = $businessSourceFreshness
        }),
        $businessEvidenceRecord,
        $businessDistributionRecord,
        $businessReleaseRecord
    )
    # Array-valued expressions in an array literal are retained as nested arrays
    # on Windows PowerShell 5.1. Flatten only the two generated top-level record
    # collections; canonical record payload arrays must remain untouched.
    $flattenedRecords = New-Object System.Collections.ArrayList
    foreach ($recordEntry in $records) {
        if ($recordEntry -is [System.Array]) {
            foreach ($generatedRecord in $recordEntry) { [void]$flattenedRecords.Add($generatedRecord) }
        }
        else { [void]$flattenedRecords.Add($recordEntry) }
    }
    $records = @($flattenedRecords)
    $recordMapForDistributionBinding = [System.Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
    foreach ($recordForBinding in $records) {
        if (-not $recordMapForDistributionBinding.ContainsKey([string]$recordForBinding.recordId)) {
            $recordMapForDistributionBinding.Add([string]$recordForBinding.recordId, $recordForBinding)
        }
    }
    # The portfolio consumes the immutable fleet release.  Its canonical
    # envelope therefore begins after that release, rather than at the generic
    # fixture epoch used by New-CanonicalRecord.
    $fleetPortfolioConsumer = $recordMapForDistributionBinding['fleet-portfolio-synthetic-1']
    $fleetPortfolioConsumer.validFrom = '2026-08-27T11:45:00Z'
    $fleetPortfolioConsumer.payload.validFrom = '2026-08-27T11:45:00Z'
    Update-CanonicalRecordBinding $fleetPortfolioConsumer
    foreach ($distributionForBinding in @($records | Where-Object recordType -CEQ 'distribution-record')) {
        $sourceEvidenceForBinding = $recordMapForDistributionBinding[[string]$distributionForBinding.payload.sourceEvidenceRef]
        $sourceEvidenceReleaseRef = Get-TestRecordPayloadValue -Record $sourceEvidenceForBinding -FieldName 'evidenceReleaseRef'
        $releaseForBinding = $recordMapForDistributionBinding[[string]$sourceEvidenceReleaseRef]
        $distributionForBinding.payload.sourceEvidenceDigest = [string]$sourceEvidenceForBinding.contentDigest
        $distributionForBinding.payload.sourceEvidenceReleaseRef = [string]$releaseForBinding.recordId
        $distributionForBinding.payload.sourceEvidenceReleaseSubjectDigest = [string]$releaseForBinding.payload.releaseSubjectDigest
        Update-CanonicalRecordBinding $distributionForBinding
    }
    $capacityResult = Get-TestRecordPayloadValue -Record $personaEvidenceRecord -FieldName 'result'
    $capacityResult | Add-Member -NotePropertyName capacityInputBindings -NotePropertyValue @(
        [pscustomobject][ordered]@{
            inputName = 'physicalMemoryGB'; recordRef = [string]$manifestRecord.recordId
            contentDigest = [string]$manifestRecord.contentDigest; pointer = '/hardwareEnvelope/memory/totalGB'
            valueDigest = Get-CanonicalPayloadDigest -Payload 64
        },
        [pscustomobject][ordered]@{
            inputName = 'corporateFloorGB'; recordRef = [string]$capacityCorporateFloorDistribution.recordId
            contentDigest = [string]$capacityCorporateFloorDistribution.contentDigest; pointer = '/median'
            valueDigest = Get-CanonicalPayloadDigest -Payload 12
        },
        [pscustomobject][ordered]@{
            inputName = 'personaRequirementGB'; recordRef = [string]$manifestRecord.recordId
            contentDigest = [string]$manifestRecord.contentDigest
            pointer = '/personas/0/extensions/operationsBlueprintV1/personaRequirementGB'
            valueDigest = Get-CanonicalPayloadDigest -Payload 32
        },
        [pscustomobject][ordered]@{
            inputName = 'formattedCapacityGB'; recordRef = [string]$manifestRecord.recordId
            contentDigest = [string]$manifestRecord.contentDigest; pointer = '/hardwareEnvelope/storage/minCapacityGB'
            valueDigest = Get-CanonicalPayloadDigest -Payload 1000
        },
        [pscustomobject][ordered]@{
            inputName = 'corporateImageGB'; recordRef = [string]$capacityCorporateImageDistribution.recordId
            contentDigest = [string]$capacityCorporateImageDistribution.contentDigest; pointer = '/median'
            valueDigest = Get-CanonicalPayloadDigest -Payload 100
        },
        [pscustomobject][ordered]@{
            inputName = 'personaWorkingSetGB'; recordRef = [string]$manifestRecord.recordId
            contentDigest = [string]$manifestRecord.contentDigest
            pointer = '/personas/0/extensions/operationsBlueprintV1/personaWorkingSetGB'
            valueDigest = Get-CanonicalPayloadDigest -Payload 500
        }
    )
    Set-TestRecordPayloadValue -Record $personaEvidenceRecord -FieldName 'result' -Value $capacityResult
    Update-CanonicalRecordBinding $personaEvidenceRecord
    $personaDistributionRecord.payload.sourceEvidenceDigest = [string]$personaEvidenceRecord.contentDigest
    Update-CanonicalRecordBinding $personaDistributionRecord
    foreach ($releaseForMembership in @($records | Where-Object recordType -CEQ 'evidence-release')) {
        [void](Complete-TestEvidenceReleaseMembership -ReleaseRecord $releaseForMembership -RecordIndex $records)
    }
    # Release envelope digests are intentionally computed last, after every
    # member distribution has its final source/release-subject binding.  Refresh
    # the fleet claim and portfolio bindings from that immutable envelope and
    # then recompute the dependent dimension-policy digests.
    $fleetReleaseForBinding = $recordMapForDistributionBinding['fleet-release-synthetic-1']
    $fleetPortfolioForBinding = $recordMapForDistributionBinding['fleet-portfolio-synthetic-1']
    $fleetPortfolioForBinding.payload.sourceEvidenceReleaseBindings[0].contentDigest = `
        [string]$fleetReleaseForBinding.contentDigest
    foreach ($dimensionProperty in $fleetPortfolioForBinding.payload.dimensionCoverage.PSObject.Properties) {
        if ($dimensionProperty.Value -isnot [pscustomobject] -or
            $null -eq $dimensionProperty.Value.PSObject.Properties['claimBindings']) { continue }
        foreach ($claimForBinding in @($dimensionProperty.Value.claimBindings)) {
            $claimForBinding.evidenceReleaseBindings[0].contentDigest = [string]$fleetReleaseForBinding.contentDigest
            if ([string]$claimForBinding.evidenceShape -ceq 'DISTRIBUTION') {
                $claimDistributionForBinding = $recordMapForDistributionBinding[[string]$claimForBinding.distributionRef]
                $claimForBinding.distributionDigest = [string]$claimDistributionForBinding.contentDigest
            }
        }
    }
    Update-FleetPortfolioDimensionDigests -Fixture ([pscustomobject]@{
        Chain = $Chain
        RecordIndex = $records
    })
    $verdictRecord = $records | Where-Object recordId -eq 'verdict-synthetic-1'
    $decisionFields = @{
        sourceVerdictRef = 'verdict-synthetic-1'
        sourceVerdictDigest = $verdictRecord.contentDigest
        sourceManifestRef = 'manifest-synthetic-1'
        sourceManifestDigest = @($records | Where-Object recordId -eq 'manifest-synthetic-1')[0].contentDigest
        sourcePointers = @('verdict-synthetic-1#/fleetVerdict','verdict-synthetic-1#/personaVerdicts/0','verdict-synthetic-1#/procurementEnvelope')
        semanticValidationRef = 'semantic-validation-synthetic-1'
        semanticValidationDigest = New-TestDigest 'e'
        semanticInputDigest = New-TestDigest '0'
        personaId = 'persona-engineering-synthetic'
        fleetDisposition = 'HOLD'
        personaDisposition = 'HOLD'
        decisionAction = 'DO_NOT_BUY'
        procurementEnvelopeDigest = Get-CanonicalPayloadDigest -Payload (Get-TestRecordPayloadValue -Record $verdictRecord -FieldName 'procurementEnvelope')
        arbitrationRequired = $false
        conditionRefs = @()
        renderedStatement = $Chain.recommendation.statement
        renderedStatementDigest = Get-CanonicalPayloadDigest -Payload ([string]$Chain.recommendation.statement)
        rendererToolRef = 'decision-packet-renderer'
        rendererVersion = 'synthetic-renderer-1.0.0'
        rendererReleaseRef = 'private://renderers/releases/synthetic-1'
        rendererReleaseDigest = New-TestDigest '2'
        templateRef = 'private://templates/leadership-decision-packet-synthetic-1'
        templateDigest = New-TestDigest '3'
        renderMode = 'DETERMINISTIC_FROM_CANONICAL_RECORDS'
        manualOverrideAllowed = $false
        unmeasuredClaimPolicy = 'CONTROLLED_HYPOTHESIS_ONLY'
        renderedAt = '2026-08-27T12:29:45Z'
        freshnessBinding = $recommendationSourceFreshness
    }
    [string[]]$semanticSourceRefs = @('manifest-synthetic-1','verdict-synthetic-1')
    [Array]::Sort($semanticSourceRefs, [StringComparer]::Ordinal)
    $records += New-CanonicalRecord 'semantic-validation-synthetic-1' 'semantic-validation-record' @('/validationResult') -Fields @{
        inputDigest = New-TestDigest '0'
        validatorReleaseRef = 'private://validator-releases/operations-blueprint-v1.0.0'
        validatorReleaseDigest = New-TestDigest '8'
        validationResultDigest = New-TestDigest '9'
        sourceRecordSetDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject]@{ sourceRecordRefs = @($semanticSourceRefs) })
        sourceRecordRefs = @($semanticSourceRefs)
        validationResult = 'PASS'
        evaluationTime = '2026-08-27T12:29:00Z'
        validatedAt = '2026-08-27T12:29:30Z'
        expiresAt = '2026-08-28T00:00:00Z'
    }
    $records += New-CanonicalRecord 'decision-claim-synthetic-1' 'decision-claim-record' @('/renderedStatement') -Fields $decisionFields
    $records += @(Get-TestPortableValidationRecords -RecordIndex $records)

    $authorityClosureRecords = @(New-TestQualificationAuthorityClosureFixture)
    $records += @($authorityClosureRecords)

    $pilotIssuanceApproval = New-TestQualificationAuthorityApprovalRecord `
        -RecordId $pilotIssuanceApprovalRef -VerdictRecord $pilotVerdictRecord -ManifestRecord $manifestRecord `
        -AuthorityClosureRecords $authorityClosureRecords -DecisionScope VERDICT_ISSUANCE `
        -IssuedAt '2026-08-27T12:06:00Z' -ApprovedAt '2026-08-27T12:07:00Z' `
        -RevocationCheckedAt '2026-08-27T12:08:00Z'
    $pilotWaiverApproval = New-TestQualificationAuthorityApprovalRecord `
        -RecordId $pilotWaiverApprovalRef -VerdictRecord $pilotVerdictRecord -ManifestRecord $manifestRecord `
        -AuthorityClosureRecords $authorityClosureRecords -DecisionScope PILOT_NOT_REQUIRED `
        -IssuedAt '2026-08-27T12:06:30Z' -ApprovedAt '2026-08-27T12:07:30Z' `
        -RevocationCheckedAt '2026-08-27T12:08:30Z'
    Set-TestRecordPayloadValue -Record $pilotVerdictRecord -FieldName qualificationAuthorityApprovalDigest `
        -Value ([string]$pilotIssuanceApproval.contentDigest)
    Set-TestRecordPayloadValue -Record $pilotVerdictRecord -FieldName pilotNotRequiredApprovalDigest `
        -Value ([string]$pilotWaiverApproval.contentDigest)
    Update-CanonicalRecordBinding $pilotVerdictRecord

    Set-TestRecordPayloadValue -Record $verdictRecord -FieldName pilotAuthorizationRecordDigest `
        -Value ([string]$pilotVerdictRecord.contentDigest)
    Update-CanonicalRecordBinding $verdictRecord
    $finalIssuanceApproval = New-TestQualificationAuthorityApprovalRecord `
        -RecordId $finalIssuanceApprovalRef -VerdictRecord $verdictRecord -ManifestRecord $manifestRecord `
        -AuthorityClosureRecords $authorityClosureRecords -DecisionScope VERDICT_ISSUANCE `
        -IssuedAt '2026-08-27T12:13:00Z' -ApprovedAt '2026-08-27T12:14:00Z' `
        -RevocationCheckedAt '2026-08-27T12:15:00Z'
    $finalPilotWaiverApproval = New-TestQualificationAuthorityApprovalRecord `
        -RecordId $finalPilotWaiverApprovalRef -VerdictRecord $verdictRecord -ManifestRecord $manifestRecord `
        -AuthorityClosureRecords $authorityClosureRecords -DecisionScope PILOT_NOT_REQUIRED `
        -IssuedAt '2026-08-27T12:13:30Z' -ApprovedAt '2026-08-27T12:14:30Z' `
        -RevocationCheckedAt '2026-08-27T12:15:30Z'
    Set-TestRecordPayloadValue -Record $verdictRecord -FieldName qualificationAuthorityApprovalDigest `
        -Value ([string]$finalIssuanceApproval.contentDigest)
    Set-TestRecordPayloadValue -Record $verdictRecord -FieldName pilotNotRequiredApprovalDigest `
        -Value ([string]$finalPilotWaiverApproval.contentDigest)
    Update-CanonicalRecordBinding $verdictRecord
    $records += @(
        $pilotIssuanceApproval,
        $pilotWaiverApproval,
        $finalIssuanceApproval,
        $finalPilotWaiverApproval
    )

    Update-ClaimSemanticBinding -Chain $Chain -RecordIndex $records
    $records
}

function New-IssuedClaimFixtureUncached {
    $chain = New-IssuedClaimChainFixture
    $index = @(New-IssuedRecordIndexFixture -Chain $chain)
    [pscustomobject]@{ Chain = $chain; RecordIndex = $index }
}

function New-IssuedClaimFixture {
    Get-SerializedTestFixtureClone -CacheKey 'issued-claim-v1' -Factory {
        New-IssuedClaimFixtureUncached
    }
}

function New-TestPilotAcceptedWindowBinding {
    param(
        [Parameter(Mandatory = $true)]$DistributionRecord,
        [Parameter(Mandatory = $true)][string[]]$AcceptedDates
    )

    $rows = New-Object System.Collections.ArrayList
    foreach ($unit in @($DistributionRecord.payload.perUnitRunCounts | Sort-Object -Property unitRef -CaseSensitive)) {
        if ([int]$unit.acceptedRunCount -ne $AcceptedDates.Count) {
            throw "Pilot window date count does not match $($unit.unitRef) acceptedRunCount."
        }
        $rowSubject = [pscustomobject][ordered]@{
            unitRef = [string]$unit.unitRef
            acceptedDates = @($AcceptedDates)
        }
        [void]$rows.Add([pscustomobject][ordered]@{
            unitRef = [string]$unit.unitRef
            acceptedDates = @($AcceptedDates)
            acceptedWindowDigest = Get-CanonicalPayloadDigest -Payload $rowSubject
        })
    }
    $rowProjection = @($rows | ForEach-Object {
        [pscustomobject][ordered]@{
            unitRef = [string]$_.unitRef
            acceptedDates = @($_.acceptedDates)
            acceptedWindowDigest = [string]$_.acceptedWindowDigest
        }
    })
    [pscustomobject][ordered]@{
        distributionRef = [string]$DistributionRecord.recordId
        testClass = [string]$DistributionRecord.payload.testClass
        unitSetDigest = Get-PilotDistributionUnitSetDigest -Distribution $DistributionRecord.payload
        acceptedWindowSetDigest = Get-CanonicalPayloadDigest -Payload $rowProjection
        perUnitAcceptedWindows = @($rows)
    }
}

function New-TestPilotRepresentationDimensions {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('production','sentiment')][string]$Mode
    )

    $observedCount = if ($Mode -ceq 'production') { 30 } else { 24 }
    $categoryDefinitions = @(
        [pscustomobject]@{
            Dimension = 'persona'
            Categories = @([pscustomobject]@{ Name = 'engineering'; Planned = 30; Observed = $observedCount })
        },
        [pscustomobject]@{
            Dimension = 'region'
            Categories = @(
                [pscustomobject]@{ Name = 'east'; Planned = 15; Observed = $(if ($Mode -ceq 'production') { 15 } else { 12 }) },
                [pscustomobject]@{ Name = 'west'; Planned = 15; Observed = $(if ($Mode -ceq 'production') { 15 } else { 12 }) }
            )
        },
        [pscustomobject]@{
            Dimension = 'work-pattern'
            Categories = @(
                [pscustomobject]@{ Name = 'hybrid'; Planned = 15; Observed = $(if ($Mode -ceq 'production') { 15 } else { 12 }) },
                [pscustomobject]@{ Name = 'office'; Planned = 15; Observed = $(if ($Mode -ceq 'production') { 15 } else { 12 }) }
            )
        }
    )
    @($categoryDefinitions | ForEach-Object {
        $dimensionName = [string]$_.Dimension
        [pscustomobject][ordered]@{
            dimension = $dimensionName
            plannedCount = 30
            observedCount = $observedCount
            nonmissingCount = $observedCount
            categories = @($_.Categories | ForEach-Object {
                [pscustomobject][ordered]@{
                    category = [string]$_.Name
                    plannedCount = [int]$_.Planned
                    observedCount = [int]$_.Observed
                    nonmissingCount = [int]$_.Observed
                    categoryPopulationDigest = Get-Sha256TokenFromText `
                        -Text "pilot-category:${Mode}:${dimensionName}:$($_.Name)"
                }
            })
        }
    })
}

function New-CompletedPilotIssuedClaimFixture {
    param([AllowNull()]$BaseFixture)

    $fixture = if ($null -eq $BaseFixture) { New-IssuedClaimFixture } else { Copy-TestObject $BaseFixture }
    $chain = $fixture.Chain
    $records = @($fixture.RecordIndex)
    foreach ($validationRecord in @($records | Where-Object recordType -CEQ 'portable-contract-validation-record')) {
        $script:PortableValidationRecordFixtures[[string]$validationRecord.recordId] = $validationRecord
    }
    if ($null -ne $BaseFixture) {
        foreach ($projectionRecord in @($records | Where-Object recordType -CEQ 'portable-contract-projection-record')) {
            $metadata = Get-PortableContractMetadata -PortableRecordType ([string]$projectionRecord.payload.portableRecordType)
            $sourceErrors = New-Object System.Collections.ArrayList
            $boundSource = New-PortableProjectionSourcePayload -Bindings @($projectionRecord.payload.projection.bindings) `
                -Errors $sourceErrors -Context "cached portable fixture $($projectionRecord.recordId)"
            if ($sourceErrors.Count -ne 0) {
                throw "Cached portable fixture source reconstruction failed: $(@($sourceErrors.code) -join ', ')."
            }
            $sourceFields = [ordered]@{
                (([string]$metadata.IdPointer).Substring(1)) = [string]$projectionRecord.payload.sourceCanonicalIdValue
            }
            foreach ($property in $boundSource.PSObject.Properties) {
                $sourceFields[[string]$property.Name] = $property.Value
            }
            $script:PortableSourceDocumentFixtures[[string]$projectionRecord.payload.sourceRecordRef] =
                Copy-TestObject -InputObject ([pscustomobject]$sourceFields)
        }
    }
    $manifest = @($records | Where-Object recordId -CEQ 'manifest-synthetic-1')[0]
    $testPlan = @($records | Where-Object recordId -CEQ 'test-plan-synthetic-1')[0]
    $thresholdPolicy = @($records | Where-Object recordId -CEQ 'freshness-policy-synthetic-1')[0]
    $pilotVerdict = @($records | Where-Object recordId -CEQ 'pilot-verdict-synthetic-1')[0]
    $finalVerdict = @($records | Where-Object recordId -CEQ 'verdict-synthetic-1')[0]
    $personaEvidence = @($records | Where-Object recordId -CEQ 'evidence-persona-t0')[0]
    $personaDistribution = @($records | Where-Object recordId -CEQ 'distribution-persona-synthetic-1')[0]
    $personaRelease = @($records | Where-Object recordId -CEQ 'persona-release-synthetic-1')[0]
    $decisionRecord = @($records | Where-Object recordId -CEQ 'decision-claim-synthetic-1')[0]
    $authorityClosure = @($records | Where-Object {
        [string]$_.recordType -cin @(
            'identity-governance-root-authority-record','security-freshness-policy-record',
            'role-binding-approval-record','role-binding-record','role-binding-readback-record'
        ) -and ([string]$_.recordType -cne 'security-freshness-policy-record' -or
            [string]$_.recordId -ceq 'private://policies/identity-role-binding-readback-synthetic-1')
    })

    $pilotPopulationPlan = [pscustomobject][ordered]@{
        targetCount = 30
        privacyOwner = 'ROLE_PRIVACY_APPROVER'
        volunteerOnly = $false
        selectionDimensions = @('persona','region','work-pattern')
        dimensions = @(
            [pscustomobject][ordered]@{
                dimension = 'persona'
                categories = @([pscustomobject][ordered]@{ category = 'engineering'; plannedCount = 30 })
            },
            [pscustomobject][ordered]@{
                dimension = 'region'
                categories = @(
                    [pscustomobject][ordered]@{ category = 'east'; plannedCount = 15 },
                    [pscustomobject][ordered]@{ category = 'west'; plannedCount = 15 }
                )
            },
            [pscustomobject][ordered]@{
                dimension = 'work-pattern'
                categories = @(
                    [pscustomobject][ordered]@{ category = 'hybrid'; plannedCount = 15 },
                    [pscustomobject][ordered]@{ category = 'office'; plannedCount = 15 }
                )
            }
        )
    }
    Set-TestRecordPayloadValue -Record $manifest -FieldName 'pilotPopulationPlan' -Value $pilotPopulationPlan
    Update-CanonicalRecordBinding $manifest

    $capacityResult = Get-TestRecordPayloadValue -Record $personaEvidence -FieldName 'result'
    foreach ($capacityBinding in @($capacityResult.capacityInputBindings | Where-Object {
        [string]$_.recordRef -ceq [string]$manifest.recordId
    })) {
        $capacityBinding.contentDigest = [string]$manifest.contentDigest
    }
    Set-TestRecordPayloadValue -Record $personaEvidence -FieldName 'result' -Value $capacityResult
    Update-CanonicalRecordBinding $personaEvidence
    $personaDistribution.payload.sourceEvidenceDigest = [string]$personaEvidence.contentDigest
    Update-CanonicalRecordBinding $personaDistribution
    [void](Complete-TestEvidenceReleaseMembership -ReleaseRecord $personaRelease -RecordIndex $records)

    $pilotAuthorization = [pscustomobject][ordered]@{
        status = 'AUTHORIZED'
        phase2ApprovalRef = 'private://phase2-approvals/pilot-synthetic-1'
        phase2ApprovalCurrent = $true
        provisionalVerdictRef = 'private://provisional-verdicts/pilot-synthetic-1'
        stopConditionsRef = 'private://pilot/stop-conditions/synthetic-1'
        rollbackPlanRef = 'private://pilot/rollback-plans/synthetic-1'
        operationalReadiness = [pscustomobject][ordered]@{
            severityModelRef = 'private://pilot/severity-models/synthetic-1'
            maxIncidentRateThresholdRef = 'private://pilot/thresholds/max-incident-rate-synthetic-1'
            deviceSwapProcessRef = 'private://pilot/device-swap-processes/synthetic-1'
            sparePoolPlanRef = 'private://pilot/spare-pool-plans/synthetic-1'
            serviceDeskBriefingRef = 'private://pilot/service-desk-briefings/synthetic-1'
            durationDays = 10
            minEvidenceCoverageThresholdRef = 'private://pilot/thresholds/min-coverage-synthetic-1'
        }
        approvedBy = 'ROLE_QUALIFICATION_AUTHORITY'
        approvedAt = '2026-08-17T08:00:00Z'
    }
    Set-TestRecordPayloadValue -Record $pilotVerdict -FieldName 'pilotAuthorization' -Value $pilotAuthorization
    Remove-TestRecordPayloadValue -Record $pilotVerdict -FieldName 'pilotNotRequiredApprovalRef'
    Remove-TestRecordPayloadValue -Record $pilotVerdict -FieldName 'pilotNotRequiredApprovalDigest'
    Update-CanonicalRecordBinding $pilotVerdict

    $records = @($records | Where-Object {
        [string]$_.recordId -cnotin @(
            'qualification-authority-approval-pilot-synthetic-1',
            'qualification-authority-approval-pilot-waiver-synthetic-1',
            'qualification-authority-approval-final-synthetic-1',
            'qualification-authority-approval-final-pilot-waiver-synthetic-1'
        )
    })
    $pilotIssuanceApproval = New-TestQualificationAuthorityApprovalRecord `
        -RecordId 'qualification-authority-approval-pilot-synthetic-1' `
        -VerdictRecord $pilotVerdict -ManifestRecord $manifest -AuthorityClosureRecords $authorityClosure `
        -DecisionScope VERDICT_ISSUANCE -IssuedAt '2026-08-27T12:06:00Z' `
        -ApprovedAt '2026-08-27T12:07:00Z' -RevocationCheckedAt '2026-08-27T12:08:00Z'
    Set-TestRecordPayloadValue -Record $pilotVerdict -FieldName 'qualificationAuthorityApprovalDigest' `
        -Value ([string]$pilotIssuanceApproval.contentDigest)
    Update-CanonicalRecordBinding $pilotVerdict

    $pilotReleaseId = 'pilot-completion-release-synthetic-1'
    $productionEvidenceId = 'pilot-production-evidence-synthetic-1'
    $productionDistributionId = 'pilot-production-distribution-synthetic-1'
    $sentimentEvidenceId = 'pilot-sentiment-evidence-synthetic-1'
    $sentimentDistributionId = 'pilot-sentiment-distribution-synthetic-1'
    $testDefinitions = @(Get-TestRecordPayloadValue -Record $testPlan -FieldName 'tests')
    $productionDefinition = @($testDefinitions | Where-Object class -CEQ 'production-pilot')[0]
    $sentimentDefinition = @($testDefinitions | Where-Object class -CEQ 'sentiment')[0]
    $pilotFreshness = New-SourceFreshnessBinding -Freshness $chain.candidateComparison.freshness `
        -ObservedAt '2026-08-27T09:00:00Z' -AdmittedAt '2026-08-27T10:45:00Z'
    $pilotRelease = Initialize-TestEvidenceReleaseSubject (New-CanonicalRecord $pilotReleaseId 'evidence-release' `
        @('/memberRecordIds') -Fields @{
            memberRecordIds = @($productionEvidenceId,$productionDistributionId,$sentimentEvidenceId,$sentimentDistributionId)
            semanticGateStatus = 'PASS'
            samplingFloorStatus = 'PASS'
            distributionStatus = 'PASS'
            coverageStatus = 'PASS'
            testPlanRef = [string]$testPlan.recordId
            testPlanDigest = [string]$testPlan.contentDigest
            thresholdPolicyRef = [string]$thresholdPolicy.recordId
            thresholdPolicyDigest = [string]$thresholdPolicy.contentDigest
            conditionRefs = @(
                [string]$productionDefinition.conditions[0].conditionId,
                [string]$sentimentDefinition.conditions[0].conditionId
            )
            baselineFingerprint = [string]$chain.candidateComparison.baselineFingerprint
            testPackVersion = 'test-pack-synthetic-1'
            releasedAt = '2026-08-27T11:30:00Z'
            freshnessBinding = $pilotFreshness
        })

    $productionEvidence = New-EvidenceRecord $productionEvidenceId 'pilot-production-completion' -Fields @{
        subjectRef = 'manifest-synthetic-1#/candidateDevices/0'
        controlRole = 'candidate'
        testPlanRef = [string]$testPlan.recordId
        testRef = [string]$productionDefinition.testId
        conditionRef = [string]$productionDefinition.conditions[0].conditionId
        baselineFingerprint = [string]$chain.candidateComparison.baselineFingerprint
        testPackVersion = [string]$productionDefinition.testPackVersion
        evidenceReleaseRef = $pilotReleaseId
        distributionRef = $productionDistributionId
        coverageStatus = 'PASS'
        freshnessBinding = $pilotFreshness
        result = [pscustomobject][ordered]@{
            status = 'PASS'
            state = 'PASS'
            stopConditionOutcome = 'NO_UNRESOLVED_STOP_CONDITION'
        }
    }
    $sentimentEvidence = New-EvidenceRecord $sentimentEvidenceId 'pilot-sentiment-completion' -Fields @{
        subjectRef = 'manifest-synthetic-1#/candidateDevices/0'
        controlRole = 'candidate'
        testPlanRef = [string]$testPlan.recordId
        testRef = [string]$sentimentDefinition.testId
        conditionRef = [string]$sentimentDefinition.conditions[0].conditionId
        baselineFingerprint = [string]$chain.candidateComparison.baselineFingerprint
        testPackVersion = [string]$sentimentDefinition.testPackVersion
        evidenceReleaseRef = $pilotReleaseId
        distributionRef = $sentimentDistributionId
        coverageStatus = 'PASS'
        freshnessBinding = $pilotFreshness
        result = [pscustomobject][ordered]@{ status = 'PASS'; state = 'PASS' }
    }
    $productionDistribution = New-DistributionRecord $productionDistributionId $productionEvidenceId $testPlan `
        -TestClass 'production-pilot' -TestRef ([string]$productionDefinition.testId) `
        -ConditionRef ([string]$productionDefinition.conditions[0].conditionId) `
        -BaselineFingerprint ([string]$chain.candidateComparison.baselineFingerprint) -UnitCount 30 -RunCount 300 `
        -SourceEvidenceReleaseRef $pilotReleaseId `
        -SourceEvidenceReleaseSubjectDigest ([string]$pilotRelease.payload.releaseSubjectDigest)
    $sentimentDistribution = New-DistributionRecord $sentimentDistributionId $sentimentEvidenceId $testPlan `
        -TestClass 'sentiment' -TestRef ([string]$sentimentDefinition.testId) `
        -ConditionRef ([string]$sentimentDefinition.conditions[0].conditionId) `
        -BaselineFingerprint ([string]$chain.candidateComparison.baselineFingerprint) -UnitCount 24 -RunCount 24 `
        -SourceEvidenceReleaseRef $pilotReleaseId `
        -SourceEvidenceReleaseSubjectDigest ([string]$pilotRelease.payload.releaseSubjectDigest)
    # The sentiment distribution observes the 24 governed respondents from the
    # complete 30-person planned pilot cohort.  Missing-response evidence is
    # explicit so the portable and operations projections reconcile exactly.
    $sentimentDistribution.payload.coverage = [pscustomobject][ordered]@{
        expected = 30
        observed = 24
        percent = 80
    }
    $sentimentDistribution.payload.missingResults = @(
        [pscustomobject][ordered]@{ reason = 'NO_RESPONSE'; count = 6 }
    )
    foreach ($pilotDistribution in @($productionDistribution,$sentimentDistribution)) {
        $pilotDistribution.validFrom = '2026-08-27T10:46:00Z'
        $pilotDistribution.payload.validFrom = '2026-08-27T10:46:00Z'
        Update-CanonicalRecordBinding $pilotDistribution
    }
    Set-TestPortableDistributionCrosswalk -EvidenceRecord $productionEvidence -DistributionRecord $productionDistribution
    Set-TestPortableDistributionCrosswalk -EvidenceRecord $sentimentEvidence -DistributionRecord $sentimentDistribution
    foreach ($pilotEvidence in @($productionEvidence,$sentimentEvidence)) {
        $portableCoverage = Get-TestRecordPayloadValue -Record $pilotEvidence -FieldName 'coverage'
        $coverageGaps = New-Object System.Collections.ArrayList
        if ([string]$pilotEvidence.recordId -ceq $sentimentEvidenceId) {
            [void]$coverageGaps.Add('Governed missing accepted runs remain.')
        }
        $portableCoverage.gaps = $coverageGaps
        Set-TestRecordPayloadValue -Record $pilotEvidence -FieldName 'coverage' -Value $portableCoverage
        Update-CanonicalRecordBinding $pilotEvidence
    }

    $pilotPopulationPlanRef = 'manifest-synthetic-1#/pilotPopulationPlan'
    $productionRepresentation = [pscustomobject][ordered]@{
        pilotPopulationPlanRef = $pilotPopulationPlanRef
        targetCount = 30
        selectionDimensions = @('persona','region','work-pattern')
        volunteerOnly = $false
        dimensions = @(New-TestPilotRepresentationDimensions -Mode production)
    }
    $sentimentRepresentationBase = [pscustomobject][ordered]@{
        pilotPopulationPlanRef = $pilotPopulationPlanRef
        targetCount = 30
        selectionDimensions = @('persona','region','work-pattern')
        volunteerOnly = $false
        dimensions = @(New-TestPilotRepresentationDimensions -Mode sentiment)
    }
    $productionWindow = New-TestPilotAcceptedWindowBinding -DistributionRecord $productionDistribution `
        -AcceptedDates @(
            '2026-08-18','2026-08-19','2026-08-20','2026-08-21','2026-08-22',
            '2026-08-23','2026-08-24','2026-08-25','2026-08-26','2026-08-27'
        )
    $sentimentWindow = New-TestPilotAcceptedWindowBinding -DistributionRecord $sentimentDistribution `
        -AcceptedDates @('2026-08-27')
    $proof = [pscustomobject][ordered]@{
        proofScheme = 'HMAC_SHA256_SORTED_SET_COMMITMENT'
        proofVersion = '1.0.0'
        populationCanonicalization = 'UTF8_NFC_LENGTH_PREFIXED_SORTED'
        populationCanonicalizationVersion = '1.0.0'
        populationCommitmentKeyRef = 'private://pilot-population-keys/synthetic-1'
        populationCommitmentKeyVersion = 'synthetic-1.0.0'
        populationCommitmentPurpose = 'PILOT_PARTICIPANT_CLOSURE'
        populationCommitmentDomainDigest = New-TestDigest '0'
        plannedPopulationSourceRef = 'private://pilot-populations/planned/synthetic-1'
        plannedPopulationSourceDigest = Get-CanonicalPayloadDigest -Payload $pilotPopulationPlan
        attributeSnapshotRef = 'private://pilot-populations/attribute-snapshots/synthetic-1'
        attributeSnapshotDigest = Get-Sha256TokenFromText -Text 'pilot-attribute-snapshot-synthetic-1'
        attributeSnapshotAt = '2026-08-17T08:30:00Z'
        plannedCount = 30
        enrolledCount = 30
        completedCount = 30
        respondentCount = 24
        plannedPopulationDigest = Get-Sha256TokenFromText -Text 'pilot-population-planned-synthetic-1'
        enrolledPopulationDigest = Get-Sha256TokenFromText -Text 'pilot-population-planned-synthetic-1'
        completedPopulationDigest = Get-Sha256TokenFromText -Text 'pilot-population-planned-synthetic-1'
        respondentPopulationDigest = Get-Sha256TokenFromText -Text 'pilot-population-respondents-synthetic-1'
        completedUnitSetDigest = Get-PilotDistributionUnitSetDigest -Distribution $productionDistribution.payload
        respondentUnitSetDigest = Get-PilotDistributionUnitSetDigest -Distribution $sentimentDistribution.payload
        productionRepresentationDigest = Get-CanonicalPayloadDigest -Payload $productionRepresentation
        sentimentRepresentationDigest = Get-CanonicalPayloadDigest -Payload $sentimentRepresentationBase
        selectionProofRef = 'private://pilot-proofs/selection/synthetic-1'
        selectionProofDigest = Get-Sha256TokenFromText -Text 'pilot-proof-selection-synthetic-1'
        enrollmentSubsetProofRef = 'private://pilot-proofs/enrollment/synthetic-1'
        enrollmentSubsetProofDigest = Get-Sha256TokenFromText -Text 'pilot-proof-enrollment-synthetic-1'
        completionSubsetProofRef = 'private://pilot-proofs/completion/synthetic-1'
        completionSubsetProofDigest = Get-Sha256TokenFromText -Text 'pilot-proof-completion-synthetic-1'
        respondentSubsetProofRef = 'private://pilot-proofs/respondent/synthetic-1'
        respondentSubsetProofDigest = Get-Sha256TokenFromText -Text 'pilot-proof-respondent-synthetic-1'
        attributePartitionProofRef = 'private://pilot-proofs/attribute-partition/synthetic-1'
        attributePartitionProofDigest = Get-Sha256TokenFromText -Text 'pilot-proof-attribute-partition-synthetic-1'
        distributionWindowBindings = @($productionWindow,$sentimentWindow)
        proofIssuerPrincipalId = New-TestCanonicalPrincipalId -Seed 'pilot-participant-proof-issuer-synthetic-1'
        proofIssuedAt = '2026-08-27T10:30:00Z'
        proofExpiresAt = '2026-08-28T00:00:00Z'
        proofRevocationStatus = 'NOT_REVOKED'
        proofRevocationEvidenceRef = 'private://pilot-proofs/revocation/synthetic-1'
        proofRevocationEvidenceDigest = Get-Sha256TokenFromText -Text 'pilot-proof-revocation-synthetic-1'
        proofRevocationCheckedAt = '2026-08-27T12:00:00Z'
        proofSubjectDigest = New-TestDigest '0'
        protectedProofRef = 'private://pilot-proofs/protected/synthetic-1'
        protectedProofDigest = Get-Sha256TokenFromText -Text 'pilot-proof-protected-synthetic-1'
        protectedProofStatus = 'VERIFIED'
    }
    $proof.populationCommitmentDomainDigest = Get-PilotParticipantCommitmentDomainDigest `
        -Proof $proof `
        -PilotEvidenceRelease ([pscustomobject]@{
            recordId = [string]$pilotRelease.recordId
            releaseSubjectDigest = [string]$pilotRelease.payload.releaseSubjectDigest
        }) `
        -Manifest ([pscustomobject]@{ recordId = [string]$manifest.recordId; contentDigest = [string]$manifest.contentDigest }) `
        -Phase0TestPlan ([pscustomobject]@{ recordId = [string]$testPlan.recordId; contentDigest = [string]$testPlan.contentDigest }) `
        -FrozenThresholdPolicy ([pscustomobject]@{ recordId = [string]$thresholdPolicy.recordId; contentDigest = [string]$thresholdPolicy.contentDigest }) `
        -PilotPopulationPlanRef $pilotPopulationPlanRef `
        -PilotPopulationPlanDigest (Get-CanonicalPayloadDigest -Payload $pilotPopulationPlan) `
        -PilotVerdict ([pscustomobject]@{ recordId = [string]$pilotVerdict.recordId; contentDigest = [string]$pilotVerdict.contentDigest }) `
        -AuthorizedAt ([string]$pilotAuthorization.approvedAt) -StartedAt '2026-08-17T09:00:00Z' `
        -CompletedAt '2026-08-27T10:00:00Z'
    $proof.proofSubjectDigest = Get-PilotParticipantProofSubjectDigest -Proof $proof
    $productionRepresentation | Add-Member -NotePropertyName populationProof -NotePropertyValue (Copy-TestObject $proof)

    $productionResult = Get-TestRecordPayloadValue -Record $productionEvidence -FieldName 'result'
    $productionResult | Add-Member -NotePropertyName representation -NotePropertyValue $productionRepresentation
    Set-TestRecordPayloadValue -Record $productionEvidence -FieldName 'result' -Value $productionResult
    Update-CanonicalRecordBinding $productionEvidence
    $sentimentRepresentation = [pscustomobject][ordered]@{
        pilotPopulationPlanRef = [string]$sentimentRepresentationBase.pilotPopulationPlanRef
        targetCount = [int]$sentimentRepresentationBase.targetCount
        selectionDimensions = @($sentimentRepresentationBase.selectionDimensions)
        volunteerOnly = $false
        dimensions = @($sentimentRepresentationBase.dimensions)
        parentProductionEvidenceRef = [string]$productionEvidence.recordId
        parentProductionEvidenceDigest = [string]$productionEvidence.contentDigest
        populationProof = Copy-TestObject $proof
    }
    $sentimentResult = Get-TestRecordPayloadValue -Record $sentimentEvidence -FieldName 'result'
    $sentimentResult | Add-Member -NotePropertyName representation -NotePropertyValue $sentimentRepresentation
    Set-TestRecordPayloadValue -Record $sentimentEvidence -FieldName 'result' -Value $sentimentResult
    Update-CanonicalRecordBinding $sentimentEvidence
    $productionDistribution.payload.sourceEvidenceDigest = [string]$productionEvidence.contentDigest
    $sentimentDistribution.payload.sourceEvidenceDigest = [string]$sentimentEvidence.contentDigest
    Update-CanonicalRecordBinding $productionDistribution
    Update-CanonicalRecordBinding $sentimentDistribution
    $pilotMembers = @($productionEvidence,$productionDistribution,$sentimentEvidence,$sentimentDistribution)
    [void](Complete-TestEvidenceReleaseMembership -ReleaseRecord $pilotRelease -RecordIndex $pilotMembers)

    Set-TestRecordPayloadValue -Record $finalVerdict -FieldName 'evidenceReleases' -Value @(
        'persona-release-synthetic-1','fleet-release-synthetic-1','candidate-release-synthetic-1',
        'business-release-synthetic-1',$pilotReleaseId
    )
    Set-TestRecordPayloadValue -Record $finalVerdict -FieldName 'pilotAuthorizationRecordDigest' `
        -Value ([string]$pilotVerdict.contentDigest)
    Set-TestRecordPayloadValue -Record $finalVerdict -FieldName 'pilotAuthorization' `
        -Value (Copy-TestObject $pilotAuthorization)
    Set-TestRecordPayloadValue -Record $finalVerdict -FieldName 'pilotCompletion' -Value ([pscustomobject][ordered]@{
        status = 'COMPLETED'
        pilotEvidenceReleaseRef = $pilotReleaseId
        coverageEvidenceRef = $productionEvidenceId
        stopConditionOutcome = 'NO_UNRESOLVED_STOP_CONDITION'
        startedAt = '2026-08-17T09:00:00Z'
        completedAt = '2026-08-27T10:00:00Z'
        approvedBy = 'ROLE_QUALIFICATION_AUTHORITY'
    })
    Set-TestRecordPayloadValue -Record $finalVerdict -FieldName 'provisionalLabVerdict' -Value 'QUALIFY'
    Set-TestRecordPayloadValue -Record $finalVerdict -FieldName 'fleetVerdict' -Value 'QUALIFY'
    Set-TestRecordPayloadValue -Record $finalVerdict -FieldName 'fleetDeploymentDisposition' -Value 'APPROVED'
    $personaVerdicts = @(Get-TestRecordPayloadValue -Record $finalVerdict -FieldName 'personaVerdicts')
    $personaVerdicts[0].verdict = 'QUALIFY'
    $personaVerdicts[0].assignmentDisposition = 'APPROVED'
    $personaVerdicts[0].conditionRefs = @()
    Set-TestRecordPayloadValue -Record $finalVerdict -FieldName 'personaVerdicts' -Value @($personaVerdicts)
    Set-TestRecordPayloadValue -Record $finalVerdict -FieldName 'conditions' -Value @()
    Set-TestRecordPayloadValue -Record $finalVerdict -FieldName 'deadlineDecision' -Value ([pscustomobject][ordered]@{
        deadlineStatus = 'before-deadline'
        evidenceState = 'conclusive'
        decision = 'purchase-within-approved-envelope'
    })
    Set-TestRecordPayloadValue -Record $finalVerdict -FieldName 'procurementDisposition' -Value 'APPROVED'
    Remove-TestRecordPayloadValue -Record $finalVerdict -FieldName 'pilotNotRequiredApprovalRef'
    Remove-TestRecordPayloadValue -Record $finalVerdict -FieldName 'pilotNotRequiredApprovalDigest'
    Update-CanonicalRecordBinding $finalVerdict

    $finalIssuanceApproval = New-TestQualificationAuthorityApprovalRecord `
        -RecordId 'qualification-authority-approval-final-synthetic-1' `
        -VerdictRecord $finalVerdict -ManifestRecord $manifest -AuthorityClosureRecords $authorityClosure `
        -DecisionScope VERDICT_ISSUANCE -IssuedAt '2026-08-27T12:13:00Z' `
        -ApprovedAt '2026-08-27T12:14:00Z' -RevocationCheckedAt '2026-08-27T12:15:00Z'
    Set-TestRecordPayloadValue -Record $finalVerdict -FieldName 'qualificationAuthorityApprovalDigest' `
        -Value ([string]$finalIssuanceApproval.contentDigest)
    Update-CanonicalRecordBinding $finalVerdict

    $chain.recommendation.action = 'BUY'
    $chain.recommendation.statement = 'BUY: Approve 1000 units within verdict-synthetic-1#/procurementEnvelope for persona persona-engineering-synthetic.'
    $decisionRecord.payload.fleetDisposition = 'QUALIFY'
    $decisionRecord.payload.personaDisposition = 'QUALIFY'
    $decisionRecord.payload.decisionAction = 'BUY'
    $decisionRecord.payload.conditionRefs = @()
    $records = @($records | Where-Object recordType -CNE 'portable-contract-validation-record')
    $records += @(
        $pilotRelease,$productionEvidence,$productionDistribution,$sentimentEvidence,$sentimentDistribution,
        $pilotIssuanceApproval,$finalIssuanceApproval
    )
    $records += @(Get-TestPortableValidationRecords -RecordIndex $records)
    $fixture.RecordIndex = @($records)
    Update-ClaimSemanticBinding -Chain $chain -RecordIndex $fixture.RecordIndex
    return $fixture
}

function New-NonPriceIssuedClaimFixture {
    $fixture = New-IssuedClaimFixture
    $effect = $fixture.Chain.businessEffect
    foreach ($costField in @(
        'assumptions','currency','quantity','candidateQuoteRef','controlQuoteRef','quoteValidUntil',
        'calculationPointer','calculationMethod','calculationResult','resultUnit','uncertainty'
    )) { $effect.PSObject.Properties.Remove($costField) }

    $evidence = @($fixture.RecordIndex | Where-Object recordId -eq 'business-impact-t0')[0]
    $distribution = @($fixture.RecordIndex | Where-Object recordId -eq 'distribution-business-synthetic-1')[0]
    $sourceBindings = @(
        [pscustomobject]@{ recordRef = $evidence.recordId; contentDigest = $evidence.contentDigest },
        [pscustomobject]@{ recordRef = $distribution.recordId; contentDigest = $distribution.contentDigest }
    )
    $denominator = [pscustomobject]@{ definition = 'Observed managed devices'; unit = 'devices'; value = 30 }
    $coverage = Copy-TestObject $distribution.payload.coverage
    $limitations = @('Synthetic fixture only; not a production benefit statement.')
    $nonPriceRecord = New-CanonicalRecord 'business-impact-synthetic-1' 'business-impact-record' `
        @('/businessEffectStatement','/observationWindow','/distributionRef','/coverage') -Fields @{
            effectType = 'NON_PRICE_EFFECT'
            businessEffectStatement = [string]$effect.statement
            metricId = [string]$distribution.payload.metricId
            metricUnit = [string]$distribution.payload.unit
            metricDirection = [string]$distribution.payload.statisticDirection
            denominator = $denominator
            observationWindow = [string]$effect.observationWindow
            distributionRef = $distribution.recordId
            distributionDigest = $distribution.contentDigest
            coverage = $coverage
            limitations = $limitations
            sourceRecordBindings = $sourceBindings
            freshnessBinding = New-SourceFreshnessBinding $effect.freshness
        }
    for ($recordIndex = 0; $recordIndex -lt $fixture.RecordIndex.Count; $recordIndex++) {
        if ([string]$fixture.RecordIndex[$recordIndex].recordId -ceq 'business-impact-synthetic-1') {
            $fixture.RecordIndex[$recordIndex] = $nonPriceRecord
            break
        }
    }
    $effect | Add-Member -NotePropertyName effectType -NotePropertyValue 'NON_PRICE_EFFECT'
    $effect | Add-Member -NotePropertyName metricId -NotePropertyValue $nonPriceRecord.payload.metricId
    $effect | Add-Member -NotePropertyName metricUnit -NotePropertyValue $nonPriceRecord.payload.metricUnit
    $effect | Add-Member -NotePropertyName metricDirection -NotePropertyValue $nonPriceRecord.payload.metricDirection
    $effect | Add-Member -NotePropertyName denominator -NotePropertyValue (Copy-TestObject $denominator)
    $effect | Add-Member -NotePropertyName distributionRef -NotePropertyValue $distribution.recordId
    $effect | Add-Member -NotePropertyName distributionDigest -NotePropertyValue $distribution.contentDigest
    $effect | Add-Member -NotePropertyName coverage -NotePropertyValue (Copy-TestObject $coverage)
    $effect | Add-Member -NotePropertyName limitations -NotePropertyValue @($limitations)
    $effect | Add-Member -NotePropertyName sourceRecordBindings -NotePropertyValue (Copy-TestObject $sourceBindings)
    $effect.decisionImpact = 'This measured non-price effect may support the recommendation only within its stated metric, denominator, observation window, coverage, and limitations; no monetary effect is claimed.'
    Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
    $fixture
}

function New-ActivationFreshnessBinding {
    param(
        [string]$ObservedAt = '2026-08-27T10:00:00Z',
        [string]$AdmittedAt = '2026-08-27T10:05:00Z'
    )
    $dependencySnapshot = [pscustomobject]@{
        windowsBuild = '26100.9999'
        corporateImageVersion = 'IMAGE-SYNTHETIC-1'
    }
    [pscustomobject][ordered]@{
        observedAt = $ObservedAt
        admittedAt = $AdmittedAt
        policyRef = 'monitoring-threshold-policy-synthetic-1#/activationFreshness/defaultMaxAgeDays'
        maxAgeDays = 30
        dependencySnapshotRef = 'manifest-activation-synthetic-1#/platformBaseline'
        dependencySnapshotDigest = Get-CanonicalPayloadDigest -Payload $dependencySnapshot
        dependencyStatus = 'MATCH'
    }
}

function New-SecurityFreshnessPolicyRecord {
    param(
        [Parameter(Mandatory = $true)][string]$RecordId,
        [Parameter(Mandatory = $true)][ValidateSet('AUTHORIZATION_TTL','AUTHORIZATION_REVOCATION','PACKAGE_REVOCATION','READBACK_FRESHNESS')][string]$PolicyKind,
        [Parameter(Mandatory = $true)][int]$MaximumAgeMinutes,
        [Parameter(Mandatory = $true)][string]$TenantBoundaryRef,
        [Parameter(Mandatory = $true)][string]$TargetEnvironmentRef,
        [Parameter(Mandatory = $true)][ValidateSet('ROOT_BOOTSTRAP','ROLE_BOUND')][string]$AuthorityMode,
        [Parameter(Mandatory = $true)][string]$ApprovedByPrincipalRef,
        [string]$RootAuthorityRef,
        [string]$RootAuthorityDigest,
        [string]$RootAuthorityReadbackRef,
        [string]$RootAuthorityReadbackDigest,
        [string]$SignatureAuthorityKeyRef,
        [string]$SignatureAuthorityPublicKeySpkiDigest,
        [string]$RoleBindingRef,
        [string]$RoleBindingDigest,
        [string]$RoleBindingReadbackRef,
        [string]$RoleBindingReadbackDigest,
        [string]$ApprovedAt = '2026-08-27T12:06:00Z'
    )

    $isBootstrap = $AuthorityMode -ceq 'ROOT_BOOTSTRAP'
    $fields = [ordered]@{
        schemaVersion = '1.0.0'
        recordStage = 'SECURITY_FRESHNESS_POLICY'
        status = 'APPROVED'
        authorityMode = $AuthorityMode
        policyScope = if ($isBootstrap) { 'IDENTITY_ROLE_BINDING_READBACK' } else { 'OPERATIONAL_CONTROL_PLANE' }
        policyKind = $PolicyKind
        maximumAgeMinutes = $MaximumAgeMinutes
        tenantBoundaryRef = $TenantBoundaryRef
        targetEnvironmentRef = $TargetEnvironmentRef
        approvedByRole = if ($isBootstrap) { 'ROLE_IDENTITY_SECURITY_APPROVER' } else { 'ROLE_SECURITY_APPROVER' }
        approvedByPrincipalRef = $ApprovedByPrincipalRef
        approvalSubjectDigest = New-TestDigest '0'
        signedSubjectDigest = New-TestDigest '0'
        approvalArtifactRef = "private://security-freshness-policies/approvals/$RecordId"
        approvalArtifactDigest = New-TestDigest '0'
        signatureRef = "private://security-freshness-policies/signatures/$RecordId"
        signatureDigest = Get-Sha256TokenFromText -Text "synthetic-security-policy-signature:$RecordId"
        signatureStatus = 'VERIFIED'
        approvedAt = $ApprovedAt
        expiresAt = '2026-08-28T00:00:00Z'
        revocationStatus = 'NOT_REVOKED'
        revocationEvidenceRef = "private://security-freshness-policies/revocation/$RecordId"
        revocationEvidenceDigest = Get-Sha256TokenFromText -Text "synthetic-security-policy-revocation:$RecordId"
        revocationCheckedAt = '2026-08-27T12:25:00Z'
    }
    if ($isBootstrap) {
        $fields.rootAuthorityRef = $RootAuthorityRef
        $fields.rootAuthorityDigest = $RootAuthorityDigest
        $fields.rootAuthorityReadbackRef = $RootAuthorityReadbackRef
        $fields.rootAuthorityReadbackDigest = $RootAuthorityReadbackDigest
        $fields.signatureAuthorityKeyRef = $SignatureAuthorityKeyRef
        $fields.signatureAuthorityPublicKeySpkiDigest = $SignatureAuthorityPublicKeySpkiDigest
    }
    else {
        $fields.roleBindingRef = $RoleBindingRef
        $fields.roleBindingDigest = $RoleBindingDigest
        $fields.roleBindingReadbackRef = $RoleBindingReadbackRef
        $fields.roleBindingReadbackDigest = $RoleBindingReadbackDigest
    }
    $subjectDigest = Get-SecurityFreshnessPolicyApprovalSubjectDigest -Policy ([pscustomobject]$fields)
    $fields.approvalSubjectDigest = $subjectDigest
    $fields.signedSubjectDigest = $subjectDigest
    $fields.approvalArtifactDigest = $subjectDigest
    New-CanonicalRecord $RecordId 'security-freshness-policy-record' -Fields $fields
}

function New-ActivationScenarioFixtureUncached {
    param([ValidateSet('PILOT', 'PRODUCTION')][string]$Stage = 'PILOT')

    $desiredRevision = New-TestDigest 'a'
    $packageDigest = New-TestDigest 'c'
    $membershipDigest = New-TestDigest 'd'
    $priorRevision = New-TestDigest 'e'
    $priorPackageDigest = New-TestDigest 'f'
    $priorMembershipDigest = New-TestDigest '1'
    $scope = 'private://rings/ring-synthetic-1'
    $tenantBoundaryRef = 'private://tenants/synthetic'
    $targetEnvironmentRef = 'private://environments/synthetic'
    $objectType = 'deviceManagementConfigurationPolicy'
    $writer = 'msgraph-terraform-provider'
    $applyOperatorIdentityRef = 'private://identities/terraform-apply-operator-synthetic-1'
    $authorizationIssuerPrincipalRef = 'private://principals/authorization-issuer-synthetic-1'
    $personaId = 'persona-engineering-synthetic'
    $managedObjectRefs = @('private://intune/objects/policy-synthetic-1')
    $managedObjectSetDigest = Get-ManagedObjectSetDigest -ManagedObjectRefs $managedObjectRefs
    $consumptionLedgerRef = 'private://ledgers/write-authorization-synthetic-1'
    $consumptionLedgerPolicyRef = 'private://policies/write-consumption-synthetic-1'
    $consumptionLedgerPolicyDigest = New-TestDigest '9'
    $independentReadbackPolicyRef = 'private://policies/intune-readback-synthetic-1'
    $readbackMaxAgeMinutes = 30
    $authorizationTtlPolicyRef = 'private://policies/authorization-ttl-synthetic-1'
    $authorizationMaxTtlMinutes = 60
    $authorizationRevocationPolicyRef = 'private://policies/authorization-revocation-freshness-synthetic-1'
    $authorizationRevocationMaxAgeMinutes = 30
    $packageRevocationPolicyRef = 'private://policies/package-revocation-freshness-synthetic-1'
    $packageRevocationMaxAgeMinutes = 60
    $roleBindingBootstrapPolicyRef = 'private://policies/identity-role-binding-readback-synthetic-1'
    $manifestRef = 'manifest-activation-synthetic-1'
    $testPlanRef = 'test-plan-activation-synthetic-1'
    $thresholdPolicyRef = 'monitoring-threshold-policy-synthetic-1'
    $targetRing = if ($Stage -eq 'PRODUCTION') { 'PERSONA_QUALIFIED' } else { 'AUTHORIZED_PILOT' }
    $sourceCommit = '0123456789abcdef0123456789abcdef01234567'
    $approvalRoles = @(
        'ROLE_PROTECTED_ENVIRONMENT_APPROVER',
        'ROLE_INTUNE_CHANGE_APPROVER',
        'ROLE_QUALIFICATION_AUTHORITY',
        'ROLE_PRIVACY_APPROVER'
    )
    if ($Stage -eq 'PRODUCTION') { $approvalRoles += 'ROLE_PROCUREMENT_APPROVER' }

    $manifest = New-CanonicalRecord $manifestRef 'candidate-manifest' @('/platformBaseline') -Fields @{
        platformBaseline = [pscustomobject]@{ windowsBuild = '26100.9999'; corporateImageVersion = 'IMAGE-SYNTHETIC-1' }
    }
    $testPlan = New-CanonicalRecord $testPlanRef 'test-plan' @('/samplingFloors','/tests') -Fields (New-FrozenTestPlanFields -ManifestRef $manifestRef -ThresholdPolicyRef $thresholdPolicyRef)
    $thresholdPolicy = New-CanonicalRecord $thresholdPolicyRef 'threshold-policy' @(
        '/monitoring/coverage/systrack',
        '/monitoring/coverage/microsoftGraphReadback',
        '/monitoring/signals/fleetHealthThreshold',
        '/monitoring/signals/graphAssignmentThreshold',
        '/activationFreshness/defaultMaxAgeDays'
    ) -Fields @{
        monitoring = [pscustomobject]@{
            coverage = [pscustomobject]@{ systrack = 90; microsoftGraphReadback = 95 }
            signals = [pscustomobject]@{ fleetHealthThreshold = 10; graphAssignmentThreshold = 1 }
        }
        activationFreshness = [pscustomobject]@{ defaultMaxAgeDays = 30 }
    }
    $baselineSnapshot = New-LeadershipDependencySnapshotFixture
    $platformBaseline = New-CanonicalRecord 'platform-baseline-activation-synthetic-1' 'platform-baseline-record' @('/dependencySnapshot') -Fields @{
        dependencySnapshot = $baselineSnapshot
        dependencySnapshotDigest = Get-CanonicalPayloadDigest -Payload $baselineSnapshot
        dependencyStatus = 'CURRENT'
        capturedAt = '2026-08-27T10:00:00Z'
    }

    $phase2Evidence = New-EvidenceRecord 'phase2-evidence-synthetic-1' 'phase2-compatibility-security' -Fields @{
        freshnessBinding = New-ActivationFreshnessBinding
    }
    $phase3Evidence = New-EvidenceRecord 'phase3-evidence-synthetic-1' 'phase3-provisional-verdict' -Fields @{
        freshnessBinding = New-ActivationFreshnessBinding
    }
    $phase2Release = Initialize-TestEvidenceReleaseSubject (New-CanonicalRecord 'phase2-release-synthetic-1' 'evidence-release' -Fields @{
        memberRecordIds = @('phase2-evidence-synthetic-1')
        semanticGateStatus = 'PASS'
        samplingFloorStatus = 'PASS'
        distributionStatus = 'PASS'
        coverageStatus = 'PASS'
        freshnessBinding = New-ActivationFreshnessBinding
        testPlanRef = $testPlanRef
        testPlanDigest = $testPlan.contentDigest
        thresholdPolicyRef = $thresholdPolicyRef
        thresholdPolicyDigest = $thresholdPolicy.contentDigest
        testPackVersion = 'test-pack-synthetic-1'
    })
    [void](Complete-TestEvidenceReleaseMembership -ReleaseRecord $phase2Release -RecordIndex @($phase2Evidence))
    $phase3Release = Initialize-TestEvidenceReleaseSubject (New-CanonicalRecord 'phase3-release-synthetic-1' 'evidence-release' -Fields @{
        memberRecordIds = @('phase3-evidence-synthetic-1')
        semanticGateStatus = 'PASS'
        samplingFloorStatus = 'PASS'
        distributionStatus = 'PASS'
        coverageStatus = 'PASS'
        freshnessBinding = New-ActivationFreshnessBinding
        testPlanRef = $testPlanRef
        testPlanDigest = $testPlan.contentDigest
        thresholdPolicyRef = $thresholdPolicyRef
        thresholdPolicyDigest = $thresholdPolicy.contentDigest
    })
    [void](Complete-TestEvidenceReleaseMembership -ReleaseRecord $phase3Release -RecordIndex @($phase3Evidence))
    $phase2ApprovalEntryBase = [ordered]@{
        decision = 'APPROVED'
        roleId = 'ROLE_QUALIFICATION_AUTHORITY'
        principalRef = 'private://principals/phase2-compatibility-approver-synthetic-1'
        approvalArtifactRef = 'private://approvals/phase2-compatibility-synthetic-1'
        approvalArtifactDigest = New-TestDigest '6'
        signatureRef = 'private://signatures/phase2-compatibility-synthetic-1'
        signatureDigest = New-TestDigest '7'
        approvedAt = '2026-08-27T11:40:00Z'
    }
    $securityApprovalEntry = Copy-TestObject ([pscustomobject]$phase2ApprovalEntryBase)
    $securityApprovalEntry.roleId = 'ROLE_SECURITY_APPROVER'
    $securityApprovalEntry.principalRef = 'private://principals/phase2-security-approver-synthetic-1'
    $securityApprovalEntry.approvalArtifactRef = 'private://approvals/phase2-security-synthetic-1'
    $securityApprovalEntry.approvalArtifactDigest = New-TestDigest '8'
    $securityApprovalEntry.signatureRef = 'private://signatures/phase2-security-synthetic-1'
    $securityApprovalEntry.signatureDigest = New-TestDigest '9'
    $securityApprovalEntry.approvedAt = '2026-08-27T11:40:00Z'
    $phase2Approval = New-CanonicalRecord 'phase2-approval-synthetic-1' 'phase2-approval-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'PHASE2_COMPATIBILITY_SECURITY_APPROVAL'
        status = 'APPROVED'
        manifestRef = $manifestRef
        manifestDigest = $manifest.contentDigest
        phase0TestPlanRef = $testPlanRef
        phase0TestPlanDigest = $testPlan.contentDigest
        phase0ThresholdPolicyRef = $thresholdPolicyRef
        phase0ThresholdPolicyDigest = $thresholdPolicy.contentDigest
        phase2EvidenceReleaseRef = $phase2Release.recordId
        phase2EvidenceReleaseDigest = $phase2Release.contentDigest
        compatibilityMatrixRef = 'private://matrices/phase2-compatibility-synthetic-1'
        compatibilityMatrixDigest = New-TestDigest 'a'
        testPackRef = 'private://test-packs/phase2-synthetic-1'
        testPackDigest = New-TestDigest 'b'
        testPackVersion = 'test-pack-synthetic-1'
        platformBaselineRef = $platformBaseline.recordId
        platformBaselineDigest = $platformBaseline.contentDigest
        compatibilityApproval = [pscustomobject]$phase2ApprovalEntryBase
        securityApproval = $securityApprovalEntry
        exceptionRefs = @()
        exceptionSetDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject]@{ exceptionRefs = @() })
        exceptionStatus = 'NONE'
        approvedAt = '2026-08-27T11:40:00Z'
        expiresAt = '2026-08-28T00:00:00Z'
    }
    $phase3Verdict = New-CanonicalRecord 'phase3-verdict-synthetic-1' 'verdict-record' @('/provisionalLabVerdict') -Fields @{
        schemaVersion = '2.0.1'
        recordStage = 'pilot-authorization'
        status = 'approved-and-immutable'
        immutableAt = '2026-08-27T11:50:00Z'
        manifestRef = $manifestRef
        manifestDigest = $manifest.contentDigest
        testPlanRef = $testPlanRef
        testPlanDigest = $testPlan.contentDigest
        thresholdPolicyRef = $thresholdPolicyRef
        thresholdPolicyDigest = $thresholdPolicy.contentDigest
        evidenceReleaseRef = $phase3Release.recordId
        evidenceReleaseDigest = $phase3Release.contentDigest
        provisionalLabVerdict = 'QUALIFY_WITH_CONDITIONS'
        pilotAuthorization = [pscustomobject]@{ status = 'AUTHORIZED' }
        evidenceReleases = @($phase3Release.recordId)
        issuedAt = '2026-08-27T11:50:00Z'
    }

    $targetPopulationSeed = [pscustomobject][ordered]@{
        populationCeiling = 30
        targetPopulationCount = 10
        exclusionRefs = @('private://directory/exclusions/break-glass-synthetic-1')
        targetCompositionDigest = New-TestDigest '0'
        groupMembershipRuleRef = 'private://directory/rules/persona-engineering-synthetic-1'
        groupMembershipRuleDigest = New-TestDigest '4'
        assignmentFilterRef = 'private://directory/filters/enterprise-windows-synthetic-1'
        assignmentFilterDigest = New-TestDigest '5'
        assignmentFilterMode = 'INCLUDE'
        dynamicMembershipPolicy = 'DYNAMIC_WITH_CEILING_AND_PREWRITE_READBACK'
        directoryReadbackRef = 'directory-readback-synthetic-1'
        directoryReadbackDigest = New-TestDigest '0'
        directoryReadbackAt = '2026-08-27T12:05:00Z'
    }
    $targetPopulationSeed.targetCompositionDigest = Get-TargetCompositionDigest -TargetPopulation $targetPopulationSeed -TargetScopeRef $scope -TargetRing $targetRing -PersonaId $personaId
    $directoryReadback = New-CanonicalRecord 'directory-readback-synthetic-1' 'readback-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'DIRECTORY_MEMBERSHIP_READBACK'
        status = 'VERIFIED'
        readbackKind = 'DIRECTORY_TARGET_POPULATION'
        readerToolRef = 'microsoft-graph-directory-readback'
        readIdentityRef = 'private://identities/directory-reader-synthetic-1'
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        targetScopeRef = $scope
        groupMembershipRuleRef = $targetPopulationSeed.groupMembershipRuleRef
        groupMembershipRuleDigest = $targetPopulationSeed.groupMembershipRuleDigest
        assignmentFilterRef = $targetPopulationSeed.assignmentFilterRef
        assignmentFilterDigest = $targetPopulationSeed.assignmentFilterDigest
        assignmentFilterMode = $targetPopulationSeed.assignmentFilterMode
        dynamicMembershipPolicy = $targetPopulationSeed.dynamicMembershipPolicy
        populationCeiling = $targetPopulationSeed.populationCeiling
        targetPopulationCount = $targetPopulationSeed.targetPopulationCount
        exclusionRefs = @($targetPopulationSeed.exclusionRefs)
        targetCompositionDigest = $targetPopulationSeed.targetCompositionDigest
        targetMembershipDigest = $membershipDigest
        responseArtifactRef = 'private://readbacks/directory-membership-synthetic-1'
        responseArtifactDigest = New-TestDigest '5'
        paginationComplete = $true
        collectedAt = $targetPopulationSeed.directoryReadbackAt
        freshnessBinding = [pscustomobject][ordered]@{
            observedAt = $targetPopulationSeed.directoryReadbackAt
            admittedAt = $targetPopulationSeed.directoryReadbackAt
            policyRef = $independentReadbackPolicyRef
            maxAgeDays = [int][Math]::Ceiling($readbackMaxAgeMinutes / 1440.0)
            dependencySnapshotRef = $targetPopulationSeed.groupMembershipRuleRef
            dependencySnapshotDigest = $targetPopulationSeed.groupMembershipRuleDigest
            dependencyStatus = 'MATCH'
        }
    }
    $targetPopulationSeed.directoryReadbackDigest = $directoryReadback.contentDigest
    $targetPopulation = Copy-TestObject $targetPopulationSeed

    # Identity governance is deliberately acyclic: the root signs one bootstrap
    # readback policy; that policy governs the role-binding observation; only
    # then may role-bound operational freshness policies be issued.
    $authorizationTtlPolicyApproverAlias = 'private://principals/authorization-ttl-policy-approver-synthetic-1'
    $authorizationRevocationPolicyApproverAlias = 'private://principals/authorization-revocation-policy-approver-synthetic-1'
    $packageRevocationPolicyApproverAlias = 'private://principals/package-revocation-policy-approver-synthetic-1'
    $readbackPolicyApproverAlias = 'private://principals/readback-policy-approver-synthetic-1'
    $roleAliasSeeds = @(
        [pscustomobject]@{ roleId = 'ROLE_EVALUATION_OWNER'; principalAliasRef = 'private://principals/requester-synthetic-1' },
        [pscustomobject]@{ roleId = 'ROLE_GRAPH_AUTOMATION_OWNER'; principalAliasRef = 'private://identities/graph-writer' },
        [pscustomobject]@{ roleId = 'ROLE_IAC_APPLY_OPERATOR'; principalAliasRef = $applyOperatorIdentityRef },
        [pscustomobject]@{ roleId = 'ROLE_DIRECTORY_READBACK_OWNER'; principalAliasRef = $directoryReadback.payload.readIdentityRef },
        [pscustomobject]@{ roleId = 'ROLE_ENDPOINT_TELEMETRY_OWNER'; principalAliasRef = 'private://identities/graph-reader' },
        [pscustomobject]@{ roleId = 'ROLE_AUTHORIZATION_LEDGER_OWNER'; principalAliasRef = 'private://identities/authorization-ledger-synthetic-1' },
        [pscustomobject]@{ roleId = 'ROLE_AUTHORIZATION_LEDGER_VERIFIER'; principalAliasRef = 'private://identities/authorization-ledger-observer-synthetic-1' },
        [pscustomobject]@{ roleId = 'ROLE_IAC_PLATFORM_OWNER'; principalAliasRef = 'private://identities/terraform-role-binding-source-synthetic-1' },
        [pscustomobject]@{ roleId = 'ROLE_IAC_PLATFORM_OWNER'; principalAliasRef = 'private://identities/azure-terraform-writer-synthetic-1' },
        [pscustomobject]@{ roleId = 'ROLE_CLOUD_RESOURCE_READBACK_OWNER'; principalAliasRef = 'private://identities/azure-resource-reader-synthetic-1' },
        [pscustomobject]@{ roleId = 'ROLE_DIRECTORY_READBACK_OWNER'; principalAliasRef = 'private://identities/role-binding-directory-reader-synthetic-1' },
        [pscustomobject]@{ roleId = 'ROLE_SUPPLY_CHAIN_OWNER'; principalAliasRef = 'private://identities/package-signer-synthetic-1' },
        [pscustomobject]@{ roleId = 'ROLE_SECURITY_APPROVER'; principalAliasRef = 'private://identities/package-verifier-synthetic-1' },
        [pscustomobject]@{ roleId = 'ROLE_SECURITY_APPROVER'; principalAliasRef = $authorizationTtlPolicyApproverAlias },
        [pscustomobject]@{ roleId = 'ROLE_SECURITY_APPROVER'; principalAliasRef = $authorizationRevocationPolicyApproverAlias },
        [pscustomobject]@{ roleId = 'ROLE_SECURITY_APPROVER'; principalAliasRef = $packageRevocationPolicyApproverAlias },
        [pscustomobject]@{ roleId = 'ROLE_SECURITY_APPROVER'; principalAliasRef = $readbackPolicyApproverAlias },
        [pscustomobject]@{ roleId = 'ROLE_PROTECTED_ENVIRONMENT_APPROVER'; principalAliasRef = $authorizationIssuerPrincipalRef }
    )
    for ($approvalIndex = 0; $approvalIndex -lt $approvalRoles.Count; $approvalIndex++) {
        $roleAliasSeeds += [pscustomobject]@{
            roleId = $approvalRoles[$approvalIndex]
            principalAliasRef = "private://principals/approver-$approvalIndex"
        }
    }
    foreach ($phase2ApprovalEntry in @($phase2Approval.payload.compatibilityApproval, $phase2Approval.payload.securityApproval)) {
        $roleAliasSeeds += [pscustomobject]@{
            roleId = $phase2ApprovalEntry.roleId
            principalAliasRef = $phase2ApprovalEntry.principalRef
        }
    }
    $roleBindings = @(
        for ($roleIndex = 0; $roleIndex -lt $roleAliasSeeds.Count; $roleIndex++) {
            [pscustomobject][ordered]@{
                roleId = [string]$roleAliasSeeds[$roleIndex].roleId
                principalAliasRef = [string]$roleAliasSeeds[$roleIndex].principalAliasRef
                canonicalPrincipalId = New-TestCanonicalPrincipalId -Seed "synthetic-canonical-principal:$roleIndex"
            }
        }
    )
    $roleBindingSetDigest = Get-RoleBindingSetDigest -Bindings $roleBindings

    $rootAuthorityKeyBindings = @(
        [pscustomobject][ordered]@{
            authorityKeyRef = 'private://identity-governance/keys/root-synthetic-a'
            publicKeySpkiDigest = New-TestDigest '1'
            keyCustodianPrincipalId = New-TestCanonicalPrincipalId -Seed 'root-key-custodian-synthetic-a'
        },
        [pscustomobject][ordered]@{
            authorityKeyRef = 'private://identity-governance/keys/root-synthetic-b'
            publicKeySpkiDigest = New-TestDigest '2'
            keyCustodianPrincipalId = New-TestCanonicalPrincipalId -Seed 'root-key-custodian-synthetic-b'
        }
    )
    $rootAuthorityFields = [ordered]@{
        schemaVersion = '1.0.0'
        recordStage = 'IDENTITY_GOVERNANCE_ROOT_AUTHORITY'
        status = 'ACTIVE'
        authorityVersion = 'synthetic-root-1.0.0'
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        ceremonyOwnerRole = 'ROLE_IDENTITY_SECURITY_APPROVER'
        ceremonyOperatorIdentityRef = New-TestCanonicalPrincipalId -Seed 'root-ceremony-operator-synthetic-1'
        quorumThreshold = 2
        authorityKeyBindings = $rootAuthorityKeyBindings
        authorityKeySetDigest = Get-IdentityGovernanceAuthorityKeySetDigest -AuthorityKeyBindings $rootAuthorityKeyBindings
        ceremonySubjectDigest = New-TestDigest '0'
        ceremonyEvidenceRef = 'private://identity-governance/ceremonies/root-synthetic-1'
        ceremonyEvidenceDigest = New-TestDigest '3'
        ceremonySignatureBindings = @()
        ceremonyAttestationRef = 'private://identity-governance/attestations/root-synthetic-1'
        ceremonyAttestationDigest = New-TestDigest '4'
        ceremonyAttestationStatus = 'VERIFIED'
        independentReadbackRef = 'private://identity-governance/readbacks/root-synthetic-1'
        independentReadbackDigest = New-TestDigest '5'
        independentReaderToolRef = 'microsoft-graph-directory-readback'
        independentReadIdentityRef = New-TestCanonicalPrincipalId -Seed 'root-authority-reader-synthetic-1'
        independentReadbackStatus = 'PASS'
        independentReadbackAt = '2026-08-27T12:00:00Z'
        independentReadbackMaxAgeMinutes = $readbackMaxAgeMinutes
        independentReadbackSubjectDigest = New-TestDigest '0'
        independentReadbackAttestationRef = 'private://identity-governance/attestations/root-readback-synthetic-1'
        independentReadbackAttestationDigest = New-TestDigest '5'
        independentReadbackAttestationStatus = 'VERIFIED'
        issuedAt = '2026-08-27T11:40:00Z'
        expiresAt = '2026-08-28T00:00:00Z'
        revocationStatus = 'NOT_REVOKED'
        revocationEvidenceRef = 'private://identity-governance/revocation/root-synthetic-1'
        revocationEvidenceDigest = New-TestDigest '6'
        revocationCheckedAt = '2026-08-27T11:55:00Z'
    }
    $rootAuthoritySubjectDigest = Get-IdentityGovernanceRootCeremonySubjectDigest -Authority ([pscustomobject]$rootAuthorityFields)
    $rootAuthorityFields.ceremonySubjectDigest = $rootAuthoritySubjectDigest
    $rootAuthorityFields.independentReadbackSubjectDigest = $rootAuthoritySubjectDigest
    $rootAuthorityFields.ceremonySignatureBindings = @(
        for ($rootSignatureIndex = 0; $rootSignatureIndex -lt $rootAuthorityKeyBindings.Count; $rootSignatureIndex++) {
            [pscustomobject][ordered]@{
                authorityKeyRef = $rootAuthorityKeyBindings[$rootSignatureIndex].authorityKeyRef
                publicKeySpkiDigest = $rootAuthorityKeyBindings[$rootSignatureIndex].publicKeySpkiDigest
                signerPrincipalId = $rootAuthorityKeyBindings[$rootSignatureIndex].keyCustodianPrincipalId
                signedSubjectDigest = $rootAuthoritySubjectDigest
                signatureRef = "private://identity-governance/signatures/root-synthetic-$rootSignatureIndex"
                signatureDigest = Get-Sha256TokenFromText -Text "synthetic-root-signature:$rootSignatureIndex"
                signatureStatus = 'VERIFIED'
            }
        }
    )
    $rootAuthority = New-CanonicalRecord 'identity-governance-root-synthetic-1' 'identity-governance-root-authority-record' -Fields $rootAuthorityFields

    $bootstrapPolicyPrincipal = $rootAuthority.payload.ceremonyOperatorIdentityRef
    $roleBindingBootstrapPolicy = New-SecurityFreshnessPolicyRecord `
        -RecordId $roleBindingBootstrapPolicyRef -PolicyKind READBACK_FRESHNESS `
        -MaximumAgeMinutes $readbackMaxAgeMinutes -TenantBoundaryRef $tenantBoundaryRef `
        -TargetEnvironmentRef $targetEnvironmentRef -AuthorityMode ROOT_BOOTSTRAP `
        -ApprovedByPrincipalRef $bootstrapPolicyPrincipal -RootAuthorityRef $rootAuthority.recordId `
        -RootAuthorityDigest $rootAuthority.contentDigest `
        -RootAuthorityReadbackRef $rootAuthority.payload.independentReadbackRef `
        -RootAuthorityReadbackDigest $rootAuthority.payload.independentReadbackDigest `
        -SignatureAuthorityKeyRef $rootAuthorityKeyBindings[0].authorityKeyRef `
        -SignatureAuthorityPublicKeySpkiDigest $rootAuthorityKeyBindings[0].publicKeySpkiDigest `
        -ApprovedAt '2026-08-27T12:01:00Z'

    [string[]]$approvedRoleCatalog = @(Get-FrozenRoleCatalog)
    $roleBindingApprovalFields = [ordered]@{
        schemaVersion = '1.0.0'
        recordStage = 'ROLE_BINDING_APPROVAL'
        status = 'APPROVED'
        bindingVersion = 'synthetic-1.0.0'
        bindingSetDigest = $roleBindingSetDigest
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        approvedRoleCatalog = @($approvedRoleCatalog)
        approvedRoleCatalogDigest = Get-ApprovedRoleCatalogDigest -ApprovedRoleCatalog $approvedRoleCatalog
        approverRole = 'ROLE_IDENTITY_SECURITY_APPROVER'
        approverPrincipalRef = New-TestCanonicalPrincipalId -Seed 'role-binding-approval-synthetic-1'
        approvalAuthorityRef = $rootAuthority.recordId
        approvalAuthorityDigest = $rootAuthority.contentDigest
        approvalAuthorityReadbackRef = $rootAuthority.payload.independentReadbackRef
        approvalAuthorityReadbackDigest = $rootAuthority.payload.independentReadbackDigest
        approvalSubjectDigest = New-TestDigest '0'
        approvalArtifactRef = 'private://identity-governance/approvals/role-binding-synthetic-1'
        approvalArtifactDigest = New-TestDigest '0'
        approvalArtifactAttestationRef = 'private://identity-governance/attestations/role-binding-synthetic-1'
        approvalArtifactAttestationDigest = New-TestDigest '7'
        approvalArtifactAttestationStatus = 'VERIFIED'
        signatureRef = 'private://identity-governance/signatures/role-binding-synthetic-1'
        signatureDigest = New-TestDigest '8'
        signatureAuthorityKeyRef = $rootAuthorityKeyBindings[1].authorityKeyRef
        signatureAuthorityPublicKeySpkiDigest = $rootAuthorityKeyBindings[1].publicKeySpkiDigest
        signedSubjectDigest = New-TestDigest '0'
        signatureStatus = 'VERIFIED'
        approvedAt = '2026-08-27T12:02:00Z'
        expiresAt = '2026-08-28T00:00:00Z'
        revocationStatus = 'NOT_REVOKED'
        revocationEvidenceRef = 'private://identity-governance/revocation/role-binding-synthetic-1'
        revocationEvidenceDigest = New-TestDigest '9'
        revocationCheckedAt = '2026-08-27T12:02:30Z'
    }
    $roleBindingApprovalSubjectDigest = Get-RoleBindingApprovalSubjectDigest -Approval ([pscustomobject]$roleBindingApprovalFields)
    $roleBindingApprovalFields.approvalSubjectDigest = $roleBindingApprovalSubjectDigest
    $roleBindingApprovalFields.approvalArtifactDigest = $roleBindingApprovalSubjectDigest
    $roleBindingApprovalFields.signedSubjectDigest = $roleBindingApprovalSubjectDigest
    $roleBindingApproval = New-CanonicalRecord 'role-binding-approval-synthetic-1' 'role-binding-approval-record' -Fields $roleBindingApprovalFields
    $roleBinding = New-CanonicalRecord 'private://roles/binding-synthetic-1' 'role-binding-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'ROLE_BINDING'
        status = 'VERIFIED'
        bindingVersion = 'synthetic-1.0.0'
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        sourceToolRef = 'terraform'
        sourceIdentityRef = 'private://identities/terraform-role-binding-source-synthetic-1'
        bindings = $roleBindings
        bindingSetDigest = $roleBindingSetDigest
        approvalRef = $roleBindingApproval.recordId
        approvalDigest = $roleBindingApproval.contentDigest
        approvedAt = '2026-08-27T12:03:00Z'
        revocationStatus = 'NOT_REVOKED'
        revocationEvidenceRef = 'private://revocation/role-binding-synthetic-1'
        revocationEvidenceDigest = New-TestDigest '9'
        revocationCheckedAt = '2026-08-27T12:04:00Z'
        expiresAt = '2026-08-28T00:00:00Z'
    }
    $roleBindingReadback = New-CanonicalRecord 'private://roles/binding-readback-synthetic-1' 'role-binding-readback-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'ROLE_BINDING_READBACK'
        status = 'VERIFIED'
        roleBindingRef = $roleBinding.recordId
        roleBindingDigest = $roleBinding.contentDigest
        bindingSetDigest = $roleBindingSetDigest
        readerToolRef = 'microsoft-graph-directory-readback'
        readIdentityRef = 'private://identities/role-binding-directory-reader-synthetic-1'
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        observedBindingSetDigest = $roleBindingSetDigest
        responseArtifactRef = 'private://readbacks/role-binding-synthetic-1'
        responseArtifactDigest = New-TestDigest 'a'
        observedAt = '2026-08-27T12:05:00Z'
        maxAgeMinutes = $readbackMaxAgeMinutes
        readbackPolicyRef = $roleBindingBootstrapPolicy.recordId
        readbackPolicyDigest = $roleBindingBootstrapPolicy.contentDigest
        revocationStatus = 'NOT_REVOKED'
        revocationEvidenceRef = $roleBinding.payload.revocationEvidenceRef
        revocationEvidenceDigest = $roleBinding.payload.revocationEvidenceDigest
        revocationCheckedAt = '2026-08-27T12:04:00Z'
        consistencyStatus = 'PASS'
    }

    $authorizationTtlPolicyPrincipal = @($roleBindings | Where-Object principalAliasRef -ceq $authorizationTtlPolicyApproverAlias)[0].canonicalPrincipalId
    $authorizationRevocationPolicyPrincipal = @($roleBindings | Where-Object principalAliasRef -ceq $authorizationRevocationPolicyApproverAlias)[0].canonicalPrincipalId
    $packageRevocationPolicyPrincipal = @($roleBindings | Where-Object principalAliasRef -ceq $packageRevocationPolicyApproverAlias)[0].canonicalPrincipalId
    $readbackPolicyPrincipal = @($roleBindings | Where-Object principalAliasRef -ceq $readbackPolicyApproverAlias)[0].canonicalPrincipalId
    $rolePolicyArguments = @{
        TenantBoundaryRef = $tenantBoundaryRef
        TargetEnvironmentRef = $targetEnvironmentRef
        AuthorityMode = 'ROLE_BOUND'
        RoleBindingRef = $roleBinding.recordId
        RoleBindingDigest = $roleBinding.contentDigest
        RoleBindingReadbackRef = $roleBindingReadback.recordId
        RoleBindingReadbackDigest = $roleBindingReadback.contentDigest
    }
    $authorizationTtlPolicy = New-SecurityFreshnessPolicyRecord @rolePolicyArguments `
        -RecordId $authorizationTtlPolicyRef -PolicyKind AUTHORIZATION_TTL `
        -MaximumAgeMinutes $authorizationMaxTtlMinutes -ApprovedByPrincipalRef $authorizationTtlPolicyPrincipal
    $authorizationRevocationPolicy = New-SecurityFreshnessPolicyRecord @rolePolicyArguments `
        -RecordId $authorizationRevocationPolicyRef -PolicyKind AUTHORIZATION_REVOCATION `
        -MaximumAgeMinutes $authorizationRevocationMaxAgeMinutes -ApprovedByPrincipalRef $authorizationRevocationPolicyPrincipal
    $packageRevocationPolicy = New-SecurityFreshnessPolicyRecord @rolePolicyArguments `
        -RecordId $packageRevocationPolicyRef -PolicyKind PACKAGE_REVOCATION `
        -MaximumAgeMinutes $packageRevocationMaxAgeMinutes -ApprovedByPrincipalRef $packageRevocationPolicyPrincipal
    $readbackFreshnessPolicy = New-SecurityFreshnessPolicyRecord @rolePolicyArguments `
        -RecordId $independentReadbackPolicyRef -PolicyKind READBACK_FRESHNESS `
        -MaximumAgeMinutes $readbackMaxAgeMinutes -ApprovedByPrincipalRef $readbackPolicyPrincipal
    $independentReadbackPolicyDigest = $readbackFreshnessPolicy.contentDigest

    $packageVerification = New-CanonicalRecord 'package-verification-synthetic-1' 'package-verification-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'PACKAGE_VERIFICATION'
        status = 'VERIFIED'
        packageDigest = $packageDigest
        packageArtifactRef = 'private://packages/intune-synthetic-1'
        sourceCommit = $sourceCommit
        signatureRef = 'private://signatures/package-synthetic-1'
        signatureDigest = New-TestDigest '2'
        signatureStatus = 'VALID'
        signerIdentityRef = 'private://identities/package-signer-synthetic-1'
        timestampEvidenceRef = 'private://timestamps/package-synthetic-1'
        timestampEvidenceDigest = New-TestDigest '3'
        timestampAuthorityRef = 'private://authorities/timestamp-synthetic-1'
        timestampStatus = 'VALID'
        timestampedAt = '2026-08-27T12:07:00Z'
        revocationEvidenceRef = 'private://revocation/package-synthetic-1'
        revocationEvidenceDigest = New-TestDigest '4'
        certificateRevocationStatus = 'GOOD'
        revocationCheckedAt = '2026-08-27T12:08:00Z'
        packageRevocationFreshnessPolicyRef = $packageRevocationPolicy.recordId
        packageRevocationFreshnessPolicyDigest = $packageRevocationPolicy.contentDigest
        packageRevocationCheckMaxAgeMinutes = $packageRevocationMaxAgeMinutes
        verificationToolRef = 'artifact-signing'
        verificationPolicyRef = 'private://policies/package-verification-synthetic-1'
        verificationPolicyDigest = New-TestDigest '5'
        verifierIdentityRef = 'private://identities/package-verifier-synthetic-1'
        verifierRole = 'ROLE_SECURITY_APPROVER'
        sbomRef = 'private://sbom/package-synthetic-1'
        sbomDigest = New-TestDigest '6'
        malwareScanRef = 'private://scans/malware-package-synthetic-1'
        malwareScanDigest = New-TestDigest '7'
        malwareScanStatus = 'PASS'
        diagnosticRedactionPolicyRef = 'private://policies/diagnostic-redaction-synthetic-1'
        diagnosticRedactionPolicyDigest = New-TestDigest '8'
        diagnosticRedactionStatus = 'PASS'
        diagnosticDataClassification = 'SAFE_SHAREABLE'
        verifiedAt = '2026-08-27T12:09:00Z'
        expiresAt = '2026-08-28T00:00:00Z'
    }

    $activationPersonaVerdict = [pscustomobject]@{
        persona = $personaId
        verdict = 'QUALIFY_WITH_CONDITIONS'
        assignmentDisposition = 'APPROVED_WITH_CONDITIONS'
        conflictsWithFleetConditions = $false
        conditionRefs = @('COND-SYNTHETIC-1')
        capacityWaterfall = [pscustomobject]@{
            memory = [pscustomobject]@{ outcome = 'PASS' }
            storage = [pscustomobject]@{ outcome = 'PASS' }
        }
    }
    $activationVerdict = New-CanonicalRecord 'activation-verdict-synthetic-1' 'verdict-record' @('/fleetVerdict','/personaVerdicts/0','/procurementEnvelope','/requalificationTriggers') -Fields @{
        schemaVersion = '2.0.1'
        recordStage = 'phase5-final'
        status = 'approved-and-immutable'
        manifestRef = $manifestRef
        pilotCompletion = [pscustomobject]@{ status = 'COMPLETED' }
        fleetVerdict = 'QUALIFY_WITH_CONDITIONS'
        fleetDeploymentDisposition = 'APPROVED_WITH_CONDITIONS'
        personaVerdicts = @($activationPersonaVerdict)
        conditions = @([pscustomobject]@{
            conditionId = 'COND-SYNTHETIC-1'
            description = 'Synthetic bounded condition.'
            owner = 'ROLE_QUALIFICATION_AUTHORITY'
            expiration = '2026-08-28'
            closureEvidence = @('private://evidence/condition-closure-synthetic-1')
        })
        arbitration = [pscustomobject]@{
            required = $false
            status = 'NOT_REQUIRED'
            triggers = @()
            authorityRole = 'ROLE_QUALIFICATION_AUTHORITY'
            outcome = 'NO_CONFLICT'
        }
        procurementEnvelope = [pscustomobject]@{
            approvedSkus = @('SKU-SYNTHETIC-1')
            quantityScope = '1000 units'
            substitutionPolicy = [pscustomobject]@{
                silentSubstitutionAllowed = $false
                observableEquivalenceEvidenceRequired = $true
                materialDifferenceAction = 'DELTA_QUALIFICATION_REQUIRED'
                unknownIdentityDisposition = 'HOLD'
            }
            substitutionAssessments = @()
        }
        procurementDisposition = 'APPROVED_WITH_CONDITIONS'
        residualRisks = @()
        requalificationTriggers = @('baseline-change')
    }

    $priorAuthorizationRef = 'private://authorizations/prior-known-good-synthetic-1'
    $priorAuthorizationDigest = New-TestDigest '2'
    $priorOperationRef = 'private://operations/prior-known-good-synthetic-1'
    $priorOperationId = 'prior-known-good-operation-synthetic-1'
    $priorConsumptionLedgerRef = 'private://ledgers/prior-known-good-synthetic-1'
    $priorConsumptionLedgerDigest = New-TestDigest '3'
    $priorConsumedAt = '2026-08-27T10:50:00Z'
    $priorConsumption = New-CanonicalRecord 'prior-known-good-consumption-synthetic-1' 'authorization-consumption-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'AUTHORIZATION_CONSUMPTION'
        status = 'COMMITTED'
        consumptionLedgerRef = $priorConsumptionLedgerRef
        consumptionLedgerPolicyRef = $consumptionLedgerPolicyRef
        consumptionLedgerPolicyDigest = $consumptionLedgerPolicyDigest
        ledgerAuthorityIdentityRef = 'private://identities/prior-ledger-authority-synthetic-1'
        ledgerAuthorityRole = 'ROLE_AUTHORIZATION_LEDGER_OWNER'
        authorizationRef = $priorAuthorizationRef
        authorizationDigest = $priorAuthorizationDigest
        authorizationId = 'prior-known-good-authorization-synthetic-1'
        authorizationNonce = 'prior-known-good-nonce-synthetic-1'
        authorizedOperationId = $priorOperationId
        managedObjectSetDigest = $managedObjectSetDigest
        maxUses = 1
        authorizationUseCount = 1
        consumptionLedgerSequence = 1
        previousLedgerEntryDigest = New-TestDigest '0'
        consumptionLedgerDigest = $priorConsumptionLedgerDigest
        replayCheckStatus = 'NOT_REUSED'
        atomicCommitEvidenceRef = 'private://ledgers/commits/prior-known-good-synthetic-1'
        atomicCommitEvidenceDigest = New-TestDigest '1'
        consumedAt = $priorConsumedAt
        independentReadbackPolicyRef = $independentReadbackPolicyRef
        independentReadbackPolicyDigest = $independentReadbackPolicyDigest
    }
    $priorWriteOperation = New-CanonicalRecord $priorOperationRef 'write-operation-record' -Fields @{
        operationId = $priorOperationId
        status = 'COMPLETED'
        writeAuthorizationRef = $priorAuthorizationRef
        writeAuthorizationDigest = $priorAuthorizationDigest
        authorizationId = 'prior-known-good-authorization-synthetic-1'
        authorizationNonce = 'prior-known-good-nonce-synthetic-1'
        maxUses = 1
        authorizationConsumptionRef = $priorConsumption.recordId
        authorizationConsumptionDigest = $priorConsumption.contentDigest
        consumptionLedgerRef = $priorConsumptionLedgerRef
        consumptionLedgerDigest = $priorConsumptionLedgerDigest
        consumptionLedgerSequence = 1
        replayCheckStatus = 'NOT_REUSED'
        reviewedPlanRef = 'private://plans/prior-known-good-synthetic-1'
        reviewedPlanDigest = New-TestDigest '4'
        roleBindingRef = 'private://roles/prior-binding-synthetic-1'
        roleBindingDigest = New-TestDigest '4'
        roleBindingReadbackRef = 'private://roles/prior-binding-readback-synthetic-1'
        roleBindingReadbackDigest = New-TestDigest '5'
        transportOwnershipRef = 'private://transport/prior-known-good-synthetic-1'
        transportOwnershipDigest = New-TestDigest '5'
        packageVerificationRef = $packageVerification.recordId
        packageVerificationDigest = $packageVerification.contentDigest
        writerToolRef = $writer
        writeIdentityRef = 'private://identities/prior-graph-writer-synthetic-1'
        applyOperatorIdentityRef = 'private://identities/prior-terraform-apply-operator-synthetic-1'
        managedObjectType = $objectType
        managedObjectRefs = @($managedObjectRefs)
        managedObjectSetDigest = $managedObjectSetDigest
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        targetScopeRef = $scope
        desiredStateRevision = $priorRevision
        packageDigest = $priorPackageDigest
        targetMembershipDigest = $priorMembershipDigest
        targetPopulation = Copy-TestObject $targetPopulation
        startedAt = '2026-08-27T10:49:00Z'
        consumedAt = $priorConsumedAt
        mutationStartedAt = '2026-08-27T10:51:00Z'
        preNetworkAtomicCommitEvidenceRef = 'private://ledgers/pre-network-commits/prior-known-good-synthetic-1'
        preNetworkAtomicCommitEvidenceDigest = New-TestDigest '2'
        authorizationUseCount = 1
        independentReadbackPolicyRef = $independentReadbackPolicyRef
        independentReadbackPolicyDigest = $independentReadbackPolicyDigest
        readbackMaxAgeMinutes = $readbackMaxAgeMinutes
        expectedReadbackKind = 'INTUNE_POST_WRITE'
        completedAt = '2026-08-27T10:55:00Z'
    }
    $priorConsumptionReadback = New-CanonicalRecord 'prior-known-good-consumption-readback-synthetic-1' 'authorization-consumption-ledger-readback-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'AUTHORIZATION_CONSUMPTION_LEDGER_READBACK'
        status = 'VERIFIED'
        consumptionRecordRef = $priorConsumption.recordId
        consumptionRecordDigest = $priorConsumption.contentDigest
        consumptionLedgerRef = $priorConsumptionLedgerRef
        ledgerAuthorityIdentityRef = $priorConsumption.payload.ledgerAuthorityIdentityRef
        authorizationRef = $priorAuthorizationRef
        authorizationDigest = $priorAuthorizationDigest
        authorizationId = $priorConsumption.payload.authorizationId
        authorizationNonce = $priorConsumption.payload.authorizationNonce
        authorizedOperationId = $priorOperationId
        writeOperationRef = $priorWriteOperation.recordId
        writeOperationDigest = $priorWriteOperation.contentDigest
        writeOperationId = $priorOperationId
        consumptionLedgerSequence = 1
        previousLedgerEntryDigest = $priorConsumption.payload.previousLedgerEntryDigest
        resultingLedgerDigest = $priorConsumptionLedgerDigest
        atomicCommitEvidenceRef = $priorConsumption.payload.atomicCommitEvidenceRef
        atomicCommitEvidenceDigest = $priorConsumption.payload.atomicCommitEvidenceDigest
        readerToolRef = 'authorization-consumption-ledger-readback'
        readIdentityRef = 'private://identities/prior-authorization-ledger-observer-synthetic-1'
        observationArtifactRef = 'private://readbacks/prior-authorization-ledger-synthetic-1'
        observationArtifactDigest = New-TestDigest '2'
        observationArtifactAttestationRef = 'private://attestations/prior-authorization-ledger-readback-synthetic-1'
        observationArtifactAttestationDigest = New-TestDigest '3'
        observationArtifactAttestationStatus = 'VERIFIED'
        observedAt = '2026-08-27T10:57:00Z'
        maxAgeMinutes = 120
        readbackPolicyRef = $independentReadbackPolicyRef
        readbackPolicyDigest = $independentReadbackPolicyDigest
        chainStatus = 'PASS'
        replayStatus = 'PASS'
        consistencyStatus = 'PASS'
    }
    $priorReadback = New-CanonicalRecord 'prior-known-good-readback-synthetic-1' 'readback-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'INTUNE_POST_WRITE_READBACK'
        status = 'VERIFIED'
        readbackKind = 'INTUNE_POST_WRITE'
        readerToolRef = 'microsoft-graph-readback'
        readIdentityRef = 'private://identities/prior-graph-reader-synthetic-1'
        writeAuthorizationRef = $priorAuthorizationRef
        writeAuthorizationDigest = $priorAuthorizationDigest
        authorizationId = 'prior-known-good-authorization-synthetic-1'
        authorizationNonce = 'prior-known-good-nonce-synthetic-1'
        authorizationConsumptionRef = $priorConsumption.recordId
        authorizationConsumptionDigest = $priorConsumption.contentDigest
        authorizationConsumptionReadbackRef = $priorConsumptionReadback.recordId
        authorizationConsumptionReadbackDigest = $priorConsumptionReadback.contentDigest
        consumptionLedgerDigest = $priorConsumptionLedgerDigest
        consumptionLedgerSequence = 1
        replayCheckStatus = 'NOT_REUSED'
        consumedAt = $priorConsumedAt
        writeOperationRef = $priorWriteOperation.recordId
        writeOperationDigest = $priorWriteOperation.contentDigest
        writeOperationId = $priorOperationId
        reviewedPlanRef = 'private://plans/prior-known-good-synthetic-1'
        reviewedPlanDigest = New-TestDigest '4'
        roleBindingRef = 'private://roles/prior-binding-synthetic-1'
        roleBindingDigest = New-TestDigest '4'
        roleBindingReadbackRef = 'private://roles/prior-binding-readback-synthetic-1'
        roleBindingReadbackDigest = New-TestDigest '5'
        packageVerificationRef = 'package-verification-synthetic-1'
        packageVerificationDigest = $packageVerification.contentDigest
        independentReadbackPolicyRef = $independentReadbackPolicyRef
        independentReadbackPolicyDigest = $independentReadbackPolicyDigest
        readbackMaxAgeMinutes = $readbackMaxAgeMinutes
        writerToolRef = $writer
        writeIdentityRef = 'private://identities/prior-graph-writer-synthetic-1'
        applyOperatorIdentityRef = 'private://identities/prior-terraform-apply-operator-synthetic-1'
        managedObjectType = $objectType
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        httpStatus = 200
        responseBodyPresent = $true
        observedStateRevision = $priorRevision
        observedPackageDigest = $priorPackageDigest
        targetMembershipDigest = $priorMembershipDigest
        targetScopeRef = $scope
        targetPopulation = Copy-TestObject $targetPopulation
        assignmentMatched = $true
        deviceStateMatched = $true
        collectedAt = '2026-08-27T11:00:00Z'
    }
    $rollback = New-CanonicalRecord 'rollback-synthetic-1' 'rollback-record' -Fields @{
        status = 'APPROVED'
        targetScopeRef = $scope
        managedObjectType = $objectType
        desiredStateRevision = $desiredRevision
        packageDigest = $packageDigest
        priorKnownGoodReadbackRef = $priorReadback.recordId
        priorKnownGoodReadbackDigest = $priorReadback.contentDigest
        priorKnownGoodDesiredStateRevision = $priorRevision
        priorKnownGoodPackageDigest = $priorPackageDigest
        priorKnownGoodTargetMembershipDigest = $priorMembershipDigest
        rollbackArtifactRef = 'private://rollback/artifacts/prior-known-good-synthetic-1'
        rollbackArtifactDigest = New-TestDigest '6'
        rollbackArtifactAttestationRef = 'private://rollback/attestations/prior-known-good-synthetic-1'
        rollbackArtifactAttestationDigest = New-TestDigest '7'
        postRollbackReadbackPolicyRef = 'private://policies/post-rollback-readback-synthetic-1'
        postRollbackReadbackPolicyDigest = New-TestDigest '8'
        postRollbackReadbackMaxAgeMinutes = 30
        ownerRole = 'ROLE_INTUNE_CHANGE_APPROVER'
        approvedAt = '2026-08-27T11:45:00Z'
        expiresAt = '2026-08-28T00:00:00Z'
    }

    $queryArtifactDigest = New-TestDigest '8'
    $queryPack = New-CanonicalRecord 'query-pack-synthetic-1' 'query-pack-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'TELEMETRY_QUERY_PACK'
        status = 'APPROVED'
        artifactRef = 'private://telemetry-query-packs/synthetic-1'
        digest = $queryArtifactDigest
        version = '1.0.0'
        sourceToolRefs = @('systrack','microsoft-graph-readback')
        metricIds = @('fleet-health-synthetic','graph-assignment-synthetic')
        ownerRole = 'ROLE_MONITORING_OWNER'
        approvedAt = '2026-08-27T11:30:00Z'
        expiresAt = '2026-08-28T00:00:00Z'
    }
    $telemetryCohort = New-CanonicalRecord 'telemetry-cohort-synthetic-1' 'cohort-record' -Fields @{
        cohortId = 'telemetry-cohort-synthetic-1'
        asOf = '2026-08-27T11:30:00Z'
        personaIds = @($personaId)
        deviceConfigurationRefs = @($manifestRef)
        population = [pscustomobject]@{ eligibleUnits = 10; observedUnits = 10; missingUnits = 0; coveragePercent = 100 }
        scopeRef = $scope
        evidenceReleaseRefs = @('telemetry-evidence-release-synthetic-1')
        freshnessBinding = New-ActivationFreshnessBinding -ObservedAt '2026-08-27T11:30:00Z' -AdmittedAt '2026-08-27T11:31:00Z'
    }
    $telemetryEvidence = New-EvidenceRecord 'telemetry-evidence-synthetic-1' 'telemetry-baseline' -Fields @{
        freshnessBinding = New-ActivationFreshnessBinding -ObservedAt '2026-08-27T11:30:00Z' -AdmittedAt '2026-08-27T11:31:00Z'
    }
    $telemetryEvidenceRelease = Initialize-TestEvidenceReleaseSubject (New-CanonicalRecord 'telemetry-evidence-release-synthetic-1' 'evidence-release' -Fields @{
        memberRecordIds = @('telemetry-evidence-synthetic-1')
        semanticGateStatus = 'PASS'
        samplingFloorStatus = 'PASS'
        distributionStatus = 'PASS'
        coverageStatus = 'PASS'
        freshnessBinding = New-ActivationFreshnessBinding -ObservedAt '2026-08-27T11:30:00Z' -AdmittedAt '2026-08-27T11:31:00Z'
    })
    [void](Complete-TestEvidenceReleaseMembership -ReleaseRecord $telemetryEvidenceRelease -RecordIndex @($telemetryEvidence))
    $telemetryBaseline = New-CanonicalRecord 'telemetry-baseline-synthetic-1' 'telemetry-baseline-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'TELEMETRY_BASELINE'
        status = 'ISSUED'
        cohortRef = $telemetryCohort.recordId
        cohortDigest = $telemetryCohort.contentDigest
        queryPackRef = $queryPack.recordId
        queryPackDigest = $queryPack.contentDigest
        thresholdPolicyRef = $thresholdPolicyRef
        thresholdPolicyDigest = $thresholdPolicy.contentDigest
        evidenceReleaseRef = $telemetryEvidenceRelease.recordId
        evidenceReleaseDigest = $telemetryEvidenceRelease.contentDigest
        coverageStatus = 'PASS'
        observedAt = '2026-08-27T11:35:00Z'
        freshnessBinding = New-ActivationFreshnessBinding -ObservedAt '2026-08-27T11:35:00Z' -AdmittedAt '2026-08-27T11:36:00Z'
    }
    $coverageFloors = @(
        [pscustomobject]@{ sourceToolRef = 'systrack'; minimumCoveragePercent = 90; thresholdPolicyRef = $thresholdPolicyRef; thresholdPointer = '#/monitoring/coverage/systrack' },
        [pscustomobject]@{ sourceToolRef = 'microsoft-graph-readback'; minimumCoveragePercent = 95; thresholdPolicyRef = $thresholdPolicyRef; thresholdPointer = '#/monitoring/coverage/microsoftGraphReadback' }
    )
    $coveragePolicy = New-CanonicalRecord 'coverage-policy-synthetic-1' 'coverage-policy-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'COVERAGE_POLICY'
        status = 'APPROVED'
        thresholdPolicyRef = $thresholdPolicyRef
        thresholdPolicyDigest = $thresholdPolicy.contentDigest
        sourceFloors = Copy-TestObject $coverageFloors
        ownerRole = 'ROLE_MONITORING_OWNER'
        approvedAt = '2026-08-27T11:32:00Z'
        expiresAt = '2026-08-28T00:00:00Z'
    }
    $stopConditionRefs = @('stop-condition-synthetic-1')
    [string[]]$sortedStopRefs = [string[]]$stopConditionRefs
    [Array]::Sort($sortedStopRefs, [StringComparer]::Ordinal)
    $conditionSetDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject]@{ conditionRefs = @($sortedStopRefs) })
    $stopConditions = New-CanonicalRecord 'stop-plan-synthetic-1' 'stop-conditions-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'STOP_CONDITION_SET'
        status = 'APPROVED'
        manifestRef = $manifestRef
        personaId = $personaId
        targetScopeRef = $scope
        managedObjectType = $objectType
        conditionSetDigest = $conditionSetDigest
        conditionRefs = @($stopConditionRefs)
        conditionCount = 1
        monitoringQueryPackRef = $queryPack.recordId
        monitoringQueryPackDigest = $queryPack.contentDigest
        telemetryBaselineRef = $telemetryBaseline.recordId
        telemetryBaselineDigest = $telemetryBaseline.contentDigest
        coveragePolicyRef = $coveragePolicy.recordId
        coveragePolicyDigest = $coveragePolicy.contentDigest
        thresholdPolicyRef = $thresholdPolicyRef
        thresholdPolicyDigest = $thresholdPolicy.contentDigest
        cadenceMinutes = 60
        alertOwnerRole = 'ROLE_MONITORING_OWNER'
        alertRouteRef = 'private://alert-routes/stop-synthetic-1'
        approvedAt = '2026-08-27T11:45:00Z'
        expiresAt = '2026-08-28T00:00:00Z'
    }
    $requalificationPlan = New-CanonicalRecord 'requalification-plan-synthetic-1' 'requalification-plan-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'REQUALIFICATION_PLAN'
        status = 'APPROVED'
        verdictRef = $activationVerdict.recordId
        verdictDigest = $activationVerdict.contentDigest
        requalificationTriggersPointer = 'activation-verdict-synthetic-1#/requalificationTriggers'
        thresholdPolicyRef = $thresholdPolicyRef
        thresholdPolicyDigest = $thresholdPolicy.contentDigest
        stopConditionsRef = $stopConditions.recordId
        stopConditionsDigest = $stopConditions.contentDigest
        rollbackRef = $rollback.recordId
        rollbackDigest = $rollback.contentDigest
        triggerActions = @([pscustomobject]@{
            triggerId = 'baseline-change'
            triggerPointer = 'activation-verdict-synthetic-1#/requalificationTriggers/0'
            action = 'FULL_REQUALIFICATION'
            ownerRole = 'ROLE_MONITORING_OWNER'
            alertRouteRef = 'private://alert-routes/requalification-synthetic-1'
        })
        ownerRole = 'ROLE_MONITORING_OWNER'
        alertRouteRef = 'private://alert-routes/requalification-synthetic-1'
        approvedAt = '2026-08-27T11:46:00Z'
        expiresAt = '2026-08-28T00:00:00Z'
    }
    $stopCondition = New-CanonicalRecord 'stop-condition-synthetic-1' 'stop-condition-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'STOP_CONDITION'
        status = 'APPROVED'
        stopConditionsRef = $stopConditions.recordId
        stopConditionsDigest = $stopConditions.contentDigest
        conditionSetDigest = $conditionSetDigest
        conditionId = 'STOP-SYNTHETIC-1'
        signalId = 'fleet-health-synthetic'
        sourceToolRef = 'systrack'
        metricId = 'fleet-health-synthetic'
        thresholdPolicyRef = $thresholdPolicyRef
        thresholdPolicyDigest = $thresholdPolicy.contentDigest
        thresholdPointer = '#/monitoring/signals/fleetHealthThreshold'
        comparison = 'GT'
        evaluationWindowMinutes = 1440
        cadenceMinutes = 60
        missingDisposition = 'INCONCLUSIVE'
        breachDisposition = 'REQUALIFY'
        rollbackRef = $rollback.recordId
        rollbackDigest = $rollback.contentDigest
        requalificationPlanRef = $requalificationPlan.recordId
        requalificationPlanDigest = $requalificationPlan.contentDigest
        ownerRole = 'ROLE_MONITORING_OWNER'
        alertRouteRef = 'private://alert-routes/stop-synthetic-1'
        approvedAt = '2026-08-27T11:47:00Z'
        expiresAt = '2026-08-28T00:00:00Z'
    }
    $pilotAuthorization = New-CanonicalRecord 'pilot-authorization-synthetic-1' 'pilot-authorization-record' -Fields @{
        status = 'AUTHORIZED'
        manifestRef = $manifestRef
        manifestDigest = $manifest.contentDigest
        personaId = $personaId
        phase2Status = 'PASS'
        phase2ApprovalRef = $phase2Approval.recordId
        phase2ApprovalDigest = $phase2Approval.contentDigest
        phase3Verdict = 'QUALIFY_WITH_CONDITIONS'
        phase3VerdictRef = $phase3Verdict.recordId
        phase3VerdictDigest = $phase3Verdict.contentDigest
        testPlanRef = $testPlanRef
        testPlanDigest = $testPlan.contentDigest
        thresholdPolicyRef = $thresholdPolicyRef
        thresholdPolicyDigest = $thresholdPolicy.contentDigest
        evidenceReleaseBindings = @(
            [pscustomobject]@{ recordRef = $phase2Release.recordId; contentDigest = $phase2Release.contentDigest },
            [pscustomobject]@{ recordRef = $phase3Release.recordId; contentDigest = $phase3Release.contentDigest }
        )
        stopConditionsRef = $stopConditions.recordId
        stopConditionsDigest = $stopConditions.contentDigest
        rollbackRef = $rollback.recordId
        rollbackDigest = $rollback.contentDigest
        targetScopeRef = $scope
        authorizedAt = '2026-08-27T11:55:00Z'
        expiresAt = '2026-08-28T00:00:00Z'
    }

    $compensatingControl = New-CanonicalRecord 'compensating-control-synthetic-1' 'compensating-control-record' -Fields @{
        status = 'ACTIVE'
        targetScopeRef = $scope
        personaId = $personaId
        managedObjectType = $objectType
        controlDescription = 'Synthetic active control for the bounded verdict condition.'
        evidenceRefs = @($phase3Evidence.recordId)
        expiresAt = '2026-08-28T00:00:00Z'
    }
    $conditionDecisionRecord = if ($Stage -eq 'PRODUCTION') { $activationVerdict } else { $pilotAuthorization }
    $condition = New-CanonicalRecord 'condition-synthetic-1' 'condition-record' -Fields @{
        ownerRole = 'ROLE_QUALIFICATION_AUTHORITY'
        ownerPrincipalRef = 'private://principals/condition-owner-synthetic-1'
        sourceDecisionRef = $conditionDecisionRecord.recordId
        sourceDecisionDigest = $conditionDecisionRecord.contentDigest
        sourceConditionId = 'COND-SYNTHETIC-1'
        reason = 'Synthetic bounded condition retained for validator testing.'
        targetScopeRef = $scope
        personaId = $personaId
        managedObjectType = $objectType
        conditionState = 'ACTIVE'
        compensatingControlRefs = @($compensatingControl.recordId)
        compensatingControlSetDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject]@{ compensatingControlRefs = @($compensatingControl.recordId) })
        evidenceReleaseRef = $phase3Release.recordId
        evidenceReleaseDigest = $phase3Release.contentDigest
        issuedAt = '2026-08-27T11:56:00Z'
        expiresAt = '2026-08-28T00:00:00Z'
    }

    $transport = New-CanonicalRecord 'private://transport/ownership-synthetic-1' 'transport-ownership-record' -Fields @{
        managedObjectType = $objectType
        targetScopeRef = $scope
        writerToolRef = $writer
        selectionStatus = 'APPROVED_OBJECT_TYPE_OWNER'
        governancePolicyDigest = Get-CanonicalPayloadDigest -Payload (Get-CheckedRegistry).intuneTransportOwnership
    }
    $atmosSourceBindings = @(
        [pscustomobject][ordered]@{ order = 1; sourceKind = 'DEFAULTS'; sourceRef = 'private://atmos/sources/defaults-synthetic-1'; sourceDigest = New-TestDigest '1' },
        [pscustomobject][ordered]@{ order = 2; sourceKind = 'STACK'; sourceRef = 'private://atmos/sources/stack-synthetic-1'; sourceDigest = New-TestDigest '2' },
        [pscustomobject][ordered]@{ order = 3; sourceKind = 'OVERRIDE'; sourceRef = 'private://atmos/sources/override-synthetic-1'; sourceDigest = New-TestDigest '3' }
    )
    $atmosRenderedOutputDigest = New-TestDigest '1'
    $atmosStackRender = New-CanonicalRecord 'atmos-stack-render-synthetic-1' 'atmos-stack-render-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'ATMOS_STACK_RENDER'
        status = 'VERIFIED'
        sourceCommit = $sourceCommit
        stackId = 'enterprise-windows-synthetic-1'
        environmentId = 'protected-synthetic-1'
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        orderedSourceBindings = $atmosSourceBindings
        orderedSourceSetDigest = Get-AtmosOrderedSourceSetDigest -OrderedSourceBindings $atmosSourceBindings
        declaredOverrideKeys = @('region','target-ring')
        usedOverrideKeys = @('region','target-ring')
        resolvedNonSecretValuesDigest = New-TestDigest '4'
        renderedOutputRef = 'private://atmos/rendered/intune-synthetic-1'
        renderedOutputDigest = $atmosRenderedOutputDigest
        affectedComponents = @('intune-enterprise-windows')
        secretScanPolicyRef = 'private://policies/atmos-secret-scan-synthetic-1'
        secretScanPolicyDigest = New-TestDigest '5'
        secretScanEvidenceRef = 'private://evidence/atmos-secret-scan-synthetic-1'
        secretScanEvidenceDigest = New-TestDigest '6'
        secretScanStatus = 'PASS'
        policyBundleRef = 'private://policies/atmos-bundle-synthetic-1'
        policyBundleDigest = New-TestDigest '7'
        policyResultsRef = 'private://evidence/atmos-policy-results-synthetic-1'
        policyResultsDigest = New-TestDigest '8'
        policyStatus = 'PASS'
        rendererToolRef = 'atmos'
        rendererVersion = 'synthetic-atmos-1.0.0'
        rendererReleaseRef = 'private://atmos/releases/synthetic-1'
        rendererReleaseDigest = New-TestDigest '9'
        renderedAt = '2026-08-27T12:01:00Z'
    }
    $plan = New-CanonicalRecord 'private://plans/reviewed-plan-synthetic-1' 'reviewed-plan-record' -Fields @{
        status = 'APPROVED'
        sourceCommit = $sourceCommit
        desiredStateRevision = $desiredRevision
        graphWriteRevision = $desiredRevision
        atmosRenderDigest = $atmosRenderedOutputDigest
        atmosStackRenderRef = $atmosStackRender.recordId
        atmosStackRenderDigest = $atmosStackRender.contentDigest
        providerLockDigest = New-TestDigest '2'
        moduleLockDigest = New-TestDigest '3'
        variableSetDigest = New-TestDigest '4'
        observedStateSnapshotDigest = New-TestDigest '5'
        policyResultsDigest = New-TestDigest '7'
        packageDigest = $packageDigest
        packageVerificationRef = $packageVerification.recordId
        packageVerificationDigest = $packageVerification.contentDigest
        targetMembershipDigest = $membershipDigest
        targetPopulation = Copy-TestObject $targetPopulation
        targetRing = $targetRing
        targetScopeRef = $scope
        managedObjectType = $objectType
        writerToolRef = $writer
        rollbackRef = $rollback.recordId
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        planExpiresAt = '2026-08-28T00:00:00Z'
    }
    $approvalEntries = @(
        for ($i = 0; $i -lt $approvalRoles.Count; $i++) {
            [pscustomobject]@{
                roleId = $approvalRoles[$i]
                principalRef = "private://principals/approver-$i"
                decision = 'APPROVED'
                approvedAt = '2026-08-27T12:10:00Z'
                expiresAt = '2026-08-28T00:00:00Z'
            }
        }
    )
    $approval = New-CanonicalRecord 'private://approvals/approval-synthetic-1' 'approval-record' -Fields @{
        status = 'APPROVED'
        requestedStage = $Stage
        planDigest = $plan.contentDigest
        targetScopeRef = $scope
        managedObjectType = $objectType
        requesterPrincipalRef = 'private://principals/requester-synthetic-1'
        approvalEntries = $approvalEntries
    }
    $activation = New-CanonicalRecord 'private://activation/activation-record-synthetic-1' 'activation-record' -Fields @{
        state = 'ACTIVE'
        registryVersion = (Get-CheckedRegistry).registryVersion
        roleBindingRef = $roleBinding.recordId
        roleBindingDigest = $roleBinding.contentDigest
        roleBindingReadbackRef = $roleBindingReadback.recordId
        roleBindingReadbackDigest = $roleBindingReadback.contentDigest
        transportOwnershipRef = $transport.recordId
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        expiresAt = '2026-08-28T00:00:00Z'
    }

    $semanticValidation = $null
    $decisionClaim = $null
    $renderManifest = $null
    $rolloutMonitoring = $null
    if ($Stage -eq 'PRODUCTION') {
        [string[]]$semanticSourceRefs = @($manifestRef, $activationVerdict.recordId)
        [Array]::Sort($semanticSourceRefs, [StringComparer]::Ordinal)
        $semanticInputDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject]@{
            manifestDigest = $manifest.contentDigest
            verdictDigest = $activationVerdict.contentDigest
        })
        $semanticValidation = New-CanonicalRecord 'activation-semantic-validation-synthetic-1' 'semantic-validation-record' @('/validationResult') -Fields @{
            inputDigest = $semanticInputDigest
            validatorReleaseRef = 'private://validator-releases/operations-blueprint-v1.0.0'
            validatorReleaseDigest = New-TestDigest '8'
            validationResultDigest = New-TestDigest '9'
            sourceRecordSetDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject]@{ sourceRecordRefs = @($semanticSourceRefs) })
            sourceRecordRefs = @($semanticSourceRefs)
            validationResult = 'PASS'
            evaluationTime = '2026-08-27T12:07:00Z'
            validatedAt = '2026-08-27T12:08:00Z'
            expiresAt = '2026-08-28T00:00:00Z'
        }
        $activationVerdictPayload = [pscustomobject][ordered]@{}
        foreach ($binding in @($activationVerdict.payload.projection.bindings)) {
            $activationVerdictPayload | Add-Member -NotePropertyName ([string]$binding.projectionField) -NotePropertyValue $binding.value
        }
        $expectedRecommendation = Get-ExpectedRecommendation -VerdictPayload $activationVerdictPayload -PersonaVerdict $activationPersonaVerdict -VerdictRef $activationVerdict.recordId
        $decisionClaim = New-CanonicalRecord 'activation-decision-claim-synthetic-1' 'decision-claim-record' @('/renderedStatement') -Fields @{
            sourceVerdictRef = $activationVerdict.recordId
            sourceVerdictDigest = $activationVerdict.contentDigest
            sourceManifestRef = $manifestRef
            sourceManifestDigest = $manifest.contentDigest
            sourcePointers = @('activation-verdict-synthetic-1#/fleetVerdict','activation-verdict-synthetic-1#/personaVerdicts/0','activation-verdict-synthetic-1#/procurementEnvelope')
            semanticValidationRef = $semanticValidation.recordId
            semanticValidationDigest = $semanticValidation.contentDigest
            semanticInputDigest = $semanticInputDigest
            personaId = $personaId
            fleetDisposition = 'QUALIFY_WITH_CONDITIONS'
            personaDisposition = 'QUALIFY_WITH_CONDITIONS'
            decisionAction = $expectedRecommendation.Action
            procurementEnvelopeDigest = Get-CanonicalPayloadDigest -Payload (Get-TestRecordPayloadValue -Record $activationVerdict -FieldName 'procurementEnvelope')
            arbitrationRequired = $false
            conditionRefs = @('COND-SYNTHETIC-1')
            renderedStatement = $expectedRecommendation.Statement
            renderedStatementDigest = Get-CanonicalPayloadDigest -Payload ([string]$expectedRecommendation.Statement)
            rendererToolRef = 'decision-packet-renderer'
            rendererVersion = 'synthetic-renderer-1.0.0'
            rendererReleaseRef = 'private://renderers/releases/synthetic-1'
            rendererReleaseDigest = New-TestDigest '2'
            templateRef = 'private://templates/leadership-decision-packet-synthetic-1'
            templateDigest = New-TestDigest '3'
            renderMode = 'DETERMINISTIC_FROM_CANONICAL_RECORDS'
            manualOverrideAllowed = $false
            unmeasuredClaimPolicy = 'CONTROLLED_HYPOTHESIS_ONLY'
            renderedAt = '2026-08-27T12:08:30Z'
            freshnessBinding = New-ActivationFreshnessBinding -ObservedAt '2026-08-27T12:08:00Z' -AdmittedAt '2026-08-27T12:08:30Z'
        }
        $renderSourceBindings = @(
            [pscustomobject]@{ recordRef = $manifest.recordId; contentDigest = $manifest.contentDigest },
            [pscustomobject]@{ recordRef = $activationVerdict.recordId; contentDigest = $activationVerdict.contentDigest }
        )
        $renderManifest = New-CanonicalRecord 'render-manifest-synthetic-1' 'render-manifest-record' -Fields @{
            schemaVersion = '1.0.0'
            recordStage = 'LEADERSHIP_RENDER_MANIFEST'
            status = 'ISSUED'
            semanticValidationRef = $semanticValidation.recordId
            semanticValidationDigest = $semanticValidation.contentDigest
            semanticInputDigest = $semanticInputDigest
            claimChainRef = 'private://claims/leadership-chain-synthetic-1'
            claimChainDigest = New-TestDigest '4'
            decisionClaimRef = $decisionClaim.recordId
            decisionClaimDigest = $decisionClaim.contentDigest
            sourceRecordBindings = $renderSourceBindings
            sourceRecordSetDigest = Get-CanonicalPayloadDigest -Payload ([pscustomobject]@{
                sourceRecordBindings = @($renderSourceBindings | Sort-Object -Property recordRef -CaseSensitive)
            })
            rendererToolRef = 'decision-packet-renderer'
            rendererVersion = $decisionClaim.payload.rendererVersion
            rendererReleaseRef = $decisionClaim.payload.rendererReleaseRef
            rendererReleaseDigest = $decisionClaim.payload.rendererReleaseDigest
            templateRef = $decisionClaim.payload.templateRef
            templateVersion = '1.0.0'
            templateDigest = $decisionClaim.payload.templateDigest
            renderMode = 'DETERMINISTIC_FROM_CANONICAL_RECORDS'
            manualOverrideAllowed = $false
            outputArtifactRef = 'private://leadership-packets/decision-synthetic-1'
            outputArtifactDigest = New-TestDigest '5'
            outputArtifactAttestationRef = 'private://attestations/leadership-packet-synthetic-1'
            outputArtifactAttestationDigest = New-TestDigest '6'
            outputFormat = 'PDF'
            encoding = 'UTF-8'
            safeLinkPolicyRef = 'private://policies/safe-links-synthetic-1'
            safeLinkPolicyDigest = New-TestDigest '6'
            privacyReleaseRef = 'private://releases/privacy-synthetic-1'
            privacyReleaseDigest = New-TestDigest '7'
            securityTestRef = 'private://tests/render-security-synthetic-1'
            securityTestDigest = New-TestDigest '8'
            securityTestStatus = 'PASS'
            generatedByIdentityRef = 'private://identities/decision-renderer-synthetic-1'
            generatedAt = '2026-08-27T12:08:45Z'
        }
        $primaryAlertRef = 'private://alert-routes/rollout-primary-synthetic-1'
        $deadmanAlertRef = 'private://alert-routes/rollout-deadman-synthetic-1'
        $signalClasses = @(
            'REVIEW_RESPONSE', 'MONITOR_HEALTH_DEADMAN', 'INTUNE_DRIFT', 'TARGET_MEMBERSHIP',
            'SYSTRACK_FLEET_HEALTH', 'SERVICENOW_INCIDENT_REPAIR', 'EVIDENCE_FRESHNESS',
            'EXCEPTION_EXPIRATION', 'VENDOR_PRODUCT_CHANGE', 'IAC_DRIFT'
        )
        $signals = @(
            for ($signalIndex = 0; $signalIndex -lt $signalClasses.Count; $signalIndex++) {
                $usesGraph = ($signalIndex % 2) -eq 1
                $isDeadman = $signalClasses[$signalIndex] -ceq 'MONITOR_HEALTH_DEADMAN'
                $isReview = $signalClasses[$signalIndex] -ceq 'REVIEW_RESPONSE'
                [pscustomobject][ordered]@{
                    signalClass = $signalClasses[$signalIndex]
                    applicabilityStatus = 'ACTIVE'
                    signalId = "governed-signal-$signalIndex"
                    sourceToolRef = if ($usesGraph) { 'microsoft-graph-readback' } else { 'systrack' }
                    metricId = if ($usesGraph) { 'graph-assignment-synthetic' } else { 'fleet-health-synthetic' }
                    thresholdPolicyRef = $thresholdPolicyRef
                    thresholdPointer = if ($usesGraph) { '#/monitoring/signals/graphAssignmentThreshold' } else { '#/monitoring/signals/fleetHealthThreshold' }
                    comparison = if ($usesGraph) { 'LT' } else { 'GT' }
                    evaluationWindowMinutes = 60
                    cadenceMinutes = 60
                    missingDisposition = 'INCONCLUSIVE'
                    breachDisposition = if ($usesGraph) { 'HOLD' } else { 'REQUALIFY' }
                    ownerRole = if ($isDeadman) { 'ROLE_ENDPOINT_TELEMETRY_OWNER' } else { 'ROLE_MONITORING_OWNER' }
                    alertRouteRef = if ($isDeadman) { $deadmanAlertRef } elseif ($isReview) { $primaryAlertRef } else { $primaryAlertRef }
                }
            }
        )
        $rolloutMonitoring = New-CanonicalRecord 'rollout-monitoring-synthetic-1' 'rollout-monitoring-record' -Fields @{
            schemaVersion = '1.0.0'
            recordStage = 'PRODUCTION_ROLLOUT_MONITORING'
            status = 'APPROVED'
            manifestRef = $manifestRef
            manifestDigest = $manifest.contentDigest
            personaId = $personaId
            semanticValidationRef = $semanticValidation.recordId
            semanticValidationDigest = $semanticValidation.contentDigest
            semanticInputDigest = $semanticInputDigest
            validatorReleaseRef = $semanticValidation.payload.validatorReleaseRef
            validatorReleaseDigest = $semanticValidation.payload.validatorReleaseDigest
            semanticValidatedAt = $semanticValidation.payload.validatedAt
            decisionClaimRef = $decisionClaim.recordId
            decisionClaimDigest = $decisionClaim.contentDigest
            renderManifestRef = $renderManifest.recordId
            renderManifestDigest = $renderManifest.contentDigest
            decisionAction = $decisionClaim.payload.decisionAction
            finalVerdictRef = $activationVerdict.recordId
            finalVerdictDigest = $activationVerdict.contentDigest
            fleetVerdictPointer = 'activation-verdict-synthetic-1#/fleetVerdict'
            personaVerdictPointer = 'activation-verdict-synthetic-1#/personaVerdicts/0'
            procurementEnvelopePointer = 'activation-verdict-synthetic-1#/procurementEnvelope'
            sourceCommit = $sourceCommit
            atmosRenderDigest = $plan.payload.atmosRenderDigest
            atmosStackRenderRef = $atmosStackRender.recordId
            atmosStackRenderDigest = $atmosStackRender.contentDigest
            reviewedPlanRef = $plan.recordId
            reviewedPlanDigest = $plan.contentDigest
            desiredStateRevision = $desiredRevision
            packageDigest = $packageDigest
            packageVerificationRef = $packageVerification.recordId
            packageVerificationDigest = $packageVerification.contentDigest
            targetRing = $targetRing
            targetScopeRef = $scope
            targetMembershipDigest = $membershipDigest
            targetPopulation = Copy-TestObject $targetPopulation
            queryPackRef = $queryPack.recordId
            queryPackDigest = $queryPack.contentDigest
            queryPack = [pscustomobject]@{
                artifactRef = $queryPack.payload.artifactRef
                digest = $queryPack.payload.digest
                version = $queryPack.payload.version
                sourceToolRefs = @($queryPack.payload.sourceToolRefs)
                metricIds = @($queryPack.payload.metricIds)
            }
            telemetryCohortRef = $telemetryCohort.recordId
            telemetryCohortDigest = $telemetryCohort.contentDigest
            telemetryBaselineRef = $telemetryBaseline.recordId
            telemetryBaselineDigest = $telemetryBaseline.contentDigest
            coveragePolicyRef = $coveragePolicy.recordId
            coveragePolicyDigest = $coveragePolicy.contentDigest
            thresholdPolicyRef = $thresholdPolicyRef
            thresholdPolicyDigest = $thresholdPolicy.contentDigest
            coverageFloors = Copy-TestObject $coverageFloors
            signals = $signals
            primaryAlertRef = $primaryAlertRef
            primaryAlertDigest = New-TestDigest 'a'
            independentDeadmanRef = $deadmanAlertRef
            independentDeadmanDigest = New-TestDigest 'b'
            independentDeadmanOwnerRole = 'ROLE_ENDPOINT_TELEMETRY_OWNER'
            independentDeadmanCadenceMinutes = 60
            stopConditionsRef = $stopConditions.recordId
            stopConditionsDigest = $stopConditions.contentDigest
            rollbackRef = $rollback.recordId
            rollbackDigest = $rollback.contentDigest
            requalificationPlanRef = $requalificationPlan.recordId
            requalificationPlanDigest = $requalificationPlan.contentDigest
            requalificationTriggersPointer = 'activation-verdict-synthetic-1#/requalificationTriggers'
            ownerRole = 'ROLE_MONITORING_OWNER'
            approvedAt = '2026-08-27T12:09:00Z'
            expiresAt = '2026-08-28T00:00:00Z'
        }
    }

    $request = [pscustomobject][ordered]@{
        requestedStage = $Stage
        desiredStateRevision = $desiredRevision
        graphWriteRevision = $desiredRevision
        reviewedPlanRef = $plan.recordId
        reviewedPlanDigest = $plan.contentDigest
        packageDigest = $packageDigest
        packageVerificationRef = $packageVerification.recordId
        packageVerificationDigest = $packageVerification.contentDigest
        packageRevocationFreshnessPolicyRef = $packageRevocationPolicy.recordId
        packageRevocationFreshnessPolicyDigest = $packageRevocationPolicy.contentDigest
        packageRevocationCheckMaxAgeMinutes = $packageRevocationMaxAgeMinutes
        consumptionLedgerRef = $consumptionLedgerRef
        consumptionLedgerPolicyRef = $consumptionLedgerPolicyRef
        consumptionLedgerPolicyDigest = $consumptionLedgerPolicyDigest
        independentReadbackPolicyRef = $independentReadbackPolicyRef
        independentReadbackPolicyDigest = $independentReadbackPolicyDigest
        authorizationTtlPolicyRef = $authorizationTtlPolicy.recordId
        authorizationTtlPolicyDigest = $authorizationTtlPolicy.contentDigest
        authorizationMaxTtlMinutes = $authorizationMaxTtlMinutes
        authorizationRevocationFreshnessPolicyRef = $authorizationRevocationPolicy.recordId
        authorizationRevocationFreshnessPolicyDigest = $authorizationRevocationPolicy.contentDigest
        authorizationRevocationCheckMaxAgeMinutes = $authorizationRevocationMaxAgeMinutes
        targetMembershipDigest = $membershipDigest
        targetPopulation = Copy-TestObject $targetPopulation
        targetRing = $targetRing
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        targetScopeRef = $scope
        managedObjectType = $objectType
        managedObjectRefs = @($managedObjectRefs)
        managedObjectSetDigest = $managedObjectSetDigest
        writerToolRef = $writer
        writeIdentityRef = 'private://identities/graph-writer'
        applyOperatorIdentityRef = $applyOperatorIdentityRef
        manifestRef = $manifestRef
        personaId = $personaId
        requesterPrincipalRef = 'private://principals/requester-synthetic-1'
        transportOwnershipRecordRef = $transport.recordId
        transportOwnershipRecordDigest = $transport.contentDigest
        transportSelectionStatus = 'APPROVED_OBJECT_TYPE_OWNER'
        roleBindingRef = $roleBinding.recordId
        roleBindingDigest = $roleBinding.contentDigest
        roleBindingReadbackRef = $roleBindingReadback.recordId
        roleBindingReadbackDigest = $roleBindingReadback.contentDigest
        writeAuthorizationRef = 'private://authorizations/write-authorization-synthetic-1'
        writeAuthorizationDigest = New-TestDigest '0'
        writeOperationId = 'write-operation-synthetic-1'
        writeOperationRef = 'private://operations/write-operation-synthetic-1'
        writeCompletedAt = '2026-08-27T12:20:00Z'
        readbackMaxAgeMinutes = $readbackMaxAgeMinutes
        protectedApprovalRef = $approval.recordId
        approvalRecordDigest = $approval.contentDigest
        approvalExpiresAt = '2026-08-28T00:00:00Z'
        approvalSetStatus = 'APPROVED'
        approvalRoleIds = @($approvalRoles)
        approvalSetScopeRef = $scope
        approvalSetPlanDigest = $plan.contentDigest
        privateActivationRecordRef = $activation.recordId
        privateActivationRecordDigest = $activation.contentDigest
        authorization = [pscustomobject][ordered]@{
            phase2Status = 'PASS'
            phase3Verdict = 'QUALIFY_WITH_CONDITIONS'
            pilotAuthorizationRef = $pilotAuthorization.recordId
            pilotAuthorizationDigest = $pilotAuthorization.contentDigest
            stopConditionsRef = $stopConditions.recordId
            stopConditionsDigest = $stopConditions.contentDigest
            rollbackRef = $rollback.recordId
            rollbackDigest = $rollback.contentDigest
            componentIdentityStatus = 'KNOWN'
            pilotCompletionStatus = if ($Stage -eq 'PRODUCTION') { 'COMPLETE' } else { 'NOT_STARTED' }
            finalVerdictRef = if ($Stage -eq 'PRODUCTION') { $activationVerdict.recordId } else { $null }
            fleetVerdict = if ($Stage -eq 'PRODUCTION') { 'QUALIFY_WITH_CONDITIONS' } else { $null }
            personaVerdict = if ($Stage -eq 'PRODUCTION') { 'QUALIFY_WITH_CONDITIONS' } else { $null }
            procurementEnvelopeRef = if ($Stage -eq 'PRODUCTION') { 'activation-verdict-synthetic-1#/procurementEnvelope' } else { $null }
            deltaQualificationStatus = 'NOT_REQUIRED'
            conditionsStatus = 'CURRENT_WITH_ACTIVE_CONTROLS'
            conditionRecordRefs = @($condition.recordId)
        }
    }
    if ($Stage -eq 'PRODUCTION') {
        $request | Add-Member -NotePropertyName rolloutMonitoringRef -NotePropertyValue $rolloutMonitoring.recordId
        $request | Add-Member -NotePropertyName rolloutMonitoringRecordDigest -NotePropertyValue $rolloutMonitoring.contentDigest
    }

    $writeAuthorizationFields = @{
        schemaVersion = '1.0.0'
        recordStage = 'PRE_WRITE_AUTHORIZATION'
        status = 'ISSUED'
        authorizationId = 'authorization-nonce-synthetic-1'
        authorizationNonce = 'nonce-synthetic-1'
        maxUses = 1
        authorizedOperationId = $request.writeOperationId
        consumptionLedgerRef = $consumptionLedgerRef
        consumptionLedgerPolicyRef = $consumptionLedgerPolicyRef
        consumptionLedgerPolicyDigest = $consumptionLedgerPolicyDigest
        requestedStage = $Stage
        requestDigest = Get-WriteAuthorizationRequestDigest -Request $request
        approvalRef = $approval.recordId
        approvalDigest = $approval.contentDigest
        activationRef = $activation.recordId
        activationDigest = $activation.contentDigest
        roleBindingRef = $roleBinding.recordId
        roleBindingDigest = $roleBinding.contentDigest
        roleBindingReadbackRef = $roleBindingReadback.recordId
        roleBindingReadbackDigest = $roleBindingReadback.contentDigest
        pilotAuthorizationRef = $pilotAuthorization.recordId
        pilotAuthorizationDigest = $pilotAuthorization.contentDigest
        stopConditionsRef = $stopConditions.recordId
        stopConditionsDigest = $stopConditions.contentDigest
        rollbackRef = $rollback.recordId
        rollbackDigest = $rollback.contentDigest
        reviewedPlanRef = $plan.recordId
        reviewedPlanDigest = $plan.contentDigest
        transportOwnershipRef = $transport.recordId
        transportOwnershipDigest = $transport.contentDigest
        packageVerificationRef = $packageVerification.recordId
        packageVerificationDigest = $packageVerification.contentDigest
        independentReadbackPolicyRef = $independentReadbackPolicyRef
        independentReadbackPolicyDigest = $independentReadbackPolicyDigest
        readbackMaxAgeMinutes = $readbackMaxAgeMinutes
        writerToolRef = $writer
        writeIdentityRef = $request.writeIdentityRef
        applyOperatorIdentityRef = $request.applyOperatorIdentityRef
        managedObjectType = $objectType
        managedObjectRefs = @($managedObjectRefs)
        managedObjectSetDigest = $managedObjectSetDigest
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        targetScopeRef = $scope
        desiredStateRevision = $desiredRevision
        packageDigest = $packageDigest
        targetMembershipDigest = $membershipDigest
        targetPopulation = Copy-TestObject $targetPopulation
        issuedByRole = 'ROLE_PROTECTED_ENVIRONMENT_APPROVER'
        issuedByPrincipalRef = $authorizationIssuerPrincipalRef
        authorizationSubjectDigest = New-TestDigest '0'
        authorizationArtifactRef = 'private://authorizations/artifacts/write-authorization-synthetic-1'
        authorizationArtifactDigest = New-TestDigest '0'
        issuerSignatureRef = 'private://authorizations/signatures/write-authorization-synthetic-1'
        issuerSignatureDigest = New-TestDigest 'a'
        issuerSignatureStatus = 'VERIFIED'
        revocationStatus = 'NOT_REVOKED'
        revocationEvidenceRef = 'private://revocation/write-authorization-synthetic-1'
        revocationEvidenceDigest = New-TestDigest 'b'
        revocationCheckedAt = '2026-08-27T12:11:30Z'
        authorizationTtlPolicyRef = $authorizationTtlPolicy.recordId
        authorizationTtlPolicyDigest = $authorizationTtlPolicy.contentDigest
        authorizationMaxTtlMinutes = $authorizationMaxTtlMinutes
        authorizationRevocationFreshnessPolicyRef = $authorizationRevocationPolicy.recordId
        authorizationRevocationFreshnessPolicyDigest = $authorizationRevocationPolicy.contentDigest
        authorizationRevocationCheckMaxAgeMinutes = $authorizationRevocationMaxAgeMinutes
        issuedAt = '2026-08-27T12:12:00Z'
        notBefore = '2026-08-27T12:13:00Z'
        expiresAt = '2026-08-27T13:00:00Z'
        singleUse = $true
    }
    if ($Stage -eq 'PRODUCTION') {
        $writeAuthorizationFields.rolloutMonitoringRef = $rolloutMonitoring.recordId
        $writeAuthorizationFields.rolloutMonitoringDigest = $rolloutMonitoring.contentDigest
        $writeAuthorizationFields.semanticValidationRef = $semanticValidation.recordId
        $writeAuthorizationFields.semanticValidationDigest = $semanticValidation.contentDigest
        $writeAuthorizationFields.decisionClaimRef = $decisionClaim.recordId
        $writeAuthorizationFields.decisionClaimDigest = $decisionClaim.contentDigest
    }
    $writeAuthorizationSubject = [ordered]@{
        record = $request.writeAuthorizationRef
        validFrom = '2026-08-27T00:00:00Z'
        validUntil = '2026-08-28T00:00:00Z'
    }
    foreach ($writeAuthorizationFieldName in $writeAuthorizationFields.Keys) {
        $writeAuthorizationSubject[$writeAuthorizationFieldName] = $writeAuthorizationFields[$writeAuthorizationFieldName]
    }
    $authorizationSubjectDigest = Get-WriteAuthorizationSubjectDigest -Authorization ([pscustomobject]$writeAuthorizationSubject)
    $writeAuthorizationFields.authorizationSubjectDigest = $authorizationSubjectDigest
    $writeAuthorizationFields.authorizationArtifactDigest = $authorizationSubjectDigest
    $writeAuthorization = New-CanonicalRecord $request.writeAuthorizationRef 'write-authorization-record' -Fields $writeAuthorizationFields
    $request.writeAuthorizationDigest = $writeAuthorization.contentDigest

    $consumptionLedgerDigest = New-TestDigest 'c'
    $authorizationConsumption = New-CanonicalRecord 'authorization-consumption-synthetic-1' 'authorization-consumption-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'AUTHORIZATION_CONSUMPTION'
        status = 'COMMITTED'
        consumptionLedgerRef = $consumptionLedgerRef
        consumptionLedgerPolicyRef = $consumptionLedgerPolicyRef
        consumptionLedgerPolicyDigest = $consumptionLedgerPolicyDigest
        ledgerAuthorityIdentityRef = 'private://identities/authorization-ledger-synthetic-1'
        ledgerAuthorityRole = 'ROLE_AUTHORIZATION_LEDGER_OWNER'
        authorizationRef = $writeAuthorization.recordId
        authorizationDigest = $writeAuthorization.contentDigest
        authorizationId = $writeAuthorization.payload.authorizationId
        authorizationNonce = $writeAuthorization.payload.authorizationNonce
        authorizedOperationId = $request.writeOperationId
        managedObjectSetDigest = $managedObjectSetDigest
        maxUses = 1
        authorizationUseCount = 1
        consumptionLedgerSequence = 1
        previousLedgerEntryDigest = New-TestDigest '0'
        consumptionLedgerDigest = $consumptionLedgerDigest
        replayCheckStatus = 'NOT_REUSED'
        atomicCommitEvidenceRef = 'private://ledgers/commits/write-authorization-synthetic-1'
        atomicCommitEvidenceDigest = New-TestDigest 'd'
        consumedAt = '2026-08-27T12:15:00Z'
        independentReadbackPolicyRef = $independentReadbackPolicyRef
        independentReadbackPolicyDigest = $independentReadbackPolicyDigest
    }

    $writeOperation = New-CanonicalRecord $request.writeOperationRef 'write-operation-record' -Fields @{
        operationId = $request.writeOperationId
        status = 'COMPLETED'
        writeAuthorizationRef = $writeAuthorization.recordId
        writeAuthorizationDigest = $writeAuthorization.contentDigest
        authorizationId = $writeAuthorization.payload.authorizationId
        authorizationNonce = $writeAuthorization.payload.authorizationNonce
        maxUses = 1
        consumptionLedgerRef = $consumptionLedgerRef
        consumptionLedgerDigest = $consumptionLedgerDigest
        consumptionLedgerSequence = 1
        replayCheckStatus = 'NOT_REUSED'
        authorizationConsumptionRef = $authorizationConsumption.recordId
        authorizationConsumptionDigest = $authorizationConsumption.contentDigest
        reviewedPlanRef = $plan.recordId
        reviewedPlanDigest = $plan.contentDigest
        roleBindingRef = $roleBinding.recordId
        roleBindingDigest = $roleBinding.contentDigest
        roleBindingReadbackRef = $roleBindingReadback.recordId
        roleBindingReadbackDigest = $roleBindingReadback.contentDigest
        transportOwnershipRef = $transport.recordId
        transportOwnershipDigest = $transport.contentDigest
        packageVerificationRef = $packageVerification.recordId
        packageVerificationDigest = $packageVerification.contentDigest
        writerToolRef = $writer
        writeIdentityRef = $request.writeIdentityRef
        applyOperatorIdentityRef = $request.applyOperatorIdentityRef
        managedObjectType = $objectType
        managedObjectRefs = @($managedObjectRefs)
        managedObjectSetDigest = $managedObjectSetDigest
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        targetScopeRef = $scope
        desiredStateRevision = $desiredRevision
        packageDigest = $packageDigest
        targetMembershipDigest = $membershipDigest
        targetPopulation = Copy-TestObject $targetPopulation
        startedAt = '2026-08-27T12:14:00Z'
        consumedAt = '2026-08-27T12:15:00Z'
        mutationStartedAt = '2026-08-27T12:16:00Z'
        preNetworkAtomicCommitEvidenceRef = $authorizationConsumption.payload.atomicCommitEvidenceRef
        preNetworkAtomicCommitEvidenceDigest = $authorizationConsumption.payload.atomicCommitEvidenceDigest
        authorizationUseCount = 1
        independentReadbackPolicyRef = $independentReadbackPolicyRef
        independentReadbackPolicyDigest = $independentReadbackPolicyDigest
        readbackMaxAgeMinutes = $readbackMaxAgeMinutes
        expectedReadbackKind = 'INTUNE_POST_WRITE'
        completedAt = '2026-08-27T12:20:00Z'
    }
    $authorizationConsumptionReadback = New-CanonicalRecord 'authorization-consumption-readback-synthetic-1' 'authorization-consumption-ledger-readback-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'AUTHORIZATION_CONSUMPTION_LEDGER_READBACK'
        status = 'VERIFIED'
        consumptionRecordRef = $authorizationConsumption.recordId
        consumptionRecordDigest = $authorizationConsumption.contentDigest
        consumptionLedgerRef = $consumptionLedgerRef
        ledgerAuthorityIdentityRef = $authorizationConsumption.payload.ledgerAuthorityIdentityRef
        authorizationRef = $writeAuthorization.recordId
        authorizationDigest = $writeAuthorization.contentDigest
        authorizationId = $writeAuthorization.payload.authorizationId
        authorizationNonce = $writeAuthorization.payload.authorizationNonce
        authorizedOperationId = $request.writeOperationId
        writeOperationRef = $writeOperation.recordId
        writeOperationDigest = $writeOperation.contentDigest
        writeOperationId = $writeOperation.payload.operationId
        consumptionLedgerSequence = $authorizationConsumption.payload.consumptionLedgerSequence
        previousLedgerEntryDigest = $authorizationConsumption.payload.previousLedgerEntryDigest
        resultingLedgerDigest = $authorizationConsumption.payload.consumptionLedgerDigest
        atomicCommitEvidenceRef = $authorizationConsumption.payload.atomicCommitEvidenceRef
        atomicCommitEvidenceDigest = $authorizationConsumption.payload.atomicCommitEvidenceDigest
        readerToolRef = 'authorization-consumption-ledger-readback'
        readIdentityRef = 'private://identities/authorization-ledger-observer-synthetic-1'
        observationArtifactRef = 'private://readbacks/authorization-ledger-synthetic-1'
        observationArtifactDigest = New-TestDigest 'e'
        observationArtifactAttestationRef = 'private://attestations/authorization-ledger-readback-synthetic-1'
        observationArtifactAttestationDigest = New-TestDigest 'f'
        observationArtifactAttestationStatus = 'VERIFIED'
        observedAt = '2026-08-27T12:22:00Z'
        maxAgeMinutes = 30
        readbackPolicyRef = $independentReadbackPolicyRef
        readbackPolicyDigest = $independentReadbackPolicyDigest
        chainStatus = 'PASS'
        replayStatus = 'PASS'
        consistencyStatus = 'PASS'
    }
    $readbackRecord = New-CanonicalRecord 'readback-synthetic-1' 'readback-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'INTUNE_POST_WRITE_READBACK'
        status = 'VERIFIED'
        readbackKind = 'INTUNE_POST_WRITE'
        readerToolRef = 'microsoft-graph-readback'
        readIdentityRef = 'private://identities/graph-reader'
        writeAuthorizationRef = $writeAuthorization.recordId
        writeAuthorizationDigest = $writeAuthorization.contentDigest
        authorizationId = $writeAuthorization.payload.authorizationId
        authorizationNonce = $writeAuthorization.payload.authorizationNonce
        authorizationConsumptionRef = $authorizationConsumption.recordId
        authorizationConsumptionDigest = $authorizationConsumption.contentDigest
        authorizationConsumptionReadbackRef = $authorizationConsumptionReadback.recordId
        authorizationConsumptionReadbackDigest = $authorizationConsumptionReadback.contentDigest
        consumptionLedgerDigest = $consumptionLedgerDigest
        consumptionLedgerSequence = 1
        replayCheckStatus = 'NOT_REUSED'
        consumedAt = '2026-08-27T12:15:00Z'
        writeOperationRef = $writeOperation.recordId
        writeOperationDigest = $writeOperation.contentDigest
        writeOperationId = $writeOperation.payload.operationId
        reviewedPlanRef = $plan.recordId
        reviewedPlanDigest = $plan.contentDigest
        roleBindingRef = $roleBinding.recordId
        roleBindingDigest = $roleBinding.contentDigest
        roleBindingReadbackRef = $roleBindingReadback.recordId
        roleBindingReadbackDigest = $roleBindingReadback.contentDigest
        packageVerificationRef = $packageVerification.recordId
        packageVerificationDigest = $packageVerification.contentDigest
        independentReadbackPolicyRef = $independentReadbackPolicyRef
        independentReadbackPolicyDigest = $independentReadbackPolicyDigest
        readbackMaxAgeMinutes = $readbackMaxAgeMinutes
        writerToolRef = $writer
        writeIdentityRef = $request.writeIdentityRef
        applyOperatorIdentityRef = $request.applyOperatorIdentityRef
        managedObjectType = $objectType
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        httpStatus = 200
        responseBodyPresent = $true
        observedStateRevision = $desiredRevision
        observedPackageDigest = $packageDigest
        targetMembershipDigest = $membershipDigest
        targetScopeRef = $scope
        targetPopulation = Copy-TestObject $targetPopulation
        assignmentMatched = $true
        deviceStateMatched = $true
        collectedAt = '2026-08-27T12:25:00Z'
    }
    $readback = [pscustomobject][ordered]@{
        schemaVersion = '1.0.0'
        recordStage = 'INTUNE_POST_WRITE_READBACK'
        status = 'VERIFIED'
        readbackKind = 'INTUNE_POST_WRITE'
        readerToolRef = $readbackRecord.payload.readerToolRef
        readIdentityRef = $readbackRecord.payload.readIdentityRef
        readbackRecordRef = $readbackRecord.recordId
        readbackRecordDigest = $readbackRecord.contentDigest
        writeAuthorizationRef = $writeAuthorization.recordId
        writeAuthorizationDigest = $writeAuthorization.contentDigest
        authorizationId = $writeAuthorization.payload.authorizationId
        authorizationNonce = $writeAuthorization.payload.authorizationNonce
        authorizationConsumptionRef = $authorizationConsumption.recordId
        authorizationConsumptionDigest = $authorizationConsumption.contentDigest
        authorizationConsumptionReadbackRef = $authorizationConsumptionReadback.recordId
        authorizationConsumptionReadbackDigest = $authorizationConsumptionReadback.contentDigest
        consumptionLedgerDigest = $consumptionLedgerDigest
        consumptionLedgerSequence = 1
        replayCheckStatus = 'NOT_REUSED'
        consumedAt = '2026-08-27T12:15:00Z'
        writeOperationRef = $writeOperation.recordId
        writeOperationDigest = $writeOperation.contentDigest
        writeOperationId = $writeOperation.payload.operationId
        reviewedPlanRef = $plan.recordId
        reviewedPlanDigest = $plan.contentDigest
        roleBindingRef = $roleBinding.recordId
        roleBindingDigest = $roleBinding.contentDigest
        roleBindingReadbackRef = $roleBindingReadback.recordId
        roleBindingReadbackDigest = $roleBindingReadback.contentDigest
        packageVerificationRef = $packageVerification.recordId
        packageVerificationDigest = $packageVerification.contentDigest
        independentReadbackPolicyRef = $independentReadbackPolicyRef
        independentReadbackPolicyDigest = $independentReadbackPolicyDigest
        readbackMaxAgeMinutes = $readbackMaxAgeMinutes
        writerToolRef = $writer
        writeIdentityRef = $request.writeIdentityRef
        applyOperatorIdentityRef = $request.applyOperatorIdentityRef
        managedObjectType = $objectType
        httpStatus = 200
        responseBodyPresent = $true
        observedStateRevision = $desiredRevision
        observedPackageDigest = $packageDigest
        targetMembershipDigest = $membershipDigest
        tenantBoundaryRef = $tenantBoundaryRef
        targetEnvironmentRef = $targetEnvironmentRef
        targetScopeRef = $scope
        targetPopulation = Copy-TestObject $targetPopulation
        assignmentMatched = $true
        deviceStateMatched = $true
        collectedAt = '2026-08-27T12:25:00Z'
    }

    $records = @(
        $manifest, $testPlan, $thresholdPolicy, $platformBaseline,
        $phase2Evidence, $phase3Evidence, $phase2Release, $phase3Release,
        $phase2Approval, $phase3Verdict,
        $directoryReadback, $roleBindingBootstrapPolicy, $authorizationTtlPolicy,
        $authorizationRevocationPolicy, $packageRevocationPolicy, $readbackFreshnessPolicy,
        $packageVerification, $activationVerdict,
        $priorConsumption, $priorWriteOperation, $priorConsumptionReadback, $priorReadback, $rollback, $queryPack, $telemetryCohort,
        $telemetryEvidence, $telemetryEvidenceRelease, $telemetryBaseline,
        $coveragePolicy, $stopConditions, $requalificationPlan, $stopCondition,
        $pilotAuthorization, $compensatingControl, $condition, $transport,
        $atmosStackRender, $plan, $approval, $rootAuthority, $roleBindingApproval, $roleBinding, $roleBindingReadback, $activation,
        $writeAuthorization, $authorizationConsumption, $writeOperation,
        $authorizationConsumptionReadback,
        $readbackRecord
    )
    if ($Stage -eq 'PRODUCTION') { $records += @($semanticValidation, $decisionClaim, $renderManifest, $rolloutMonitoring) }
    $records += @(Get-TestPortableValidationRecords -RecordIndex $records)
    [pscustomobject]@{
        Request = $request
        RecordIndex = @($records)
        Readback = $readback
        RolloutMonitoringRecord = $rolloutMonitoring
    }
}

function New-ActivationScenarioFixture {
    param([ValidateSet('PILOT', 'PRODUCTION')][string]$Stage = 'PILOT')

    Get-SerializedTestFixtureClone -CacheKey "activation-scenario-$Stage-v1" -Factory {
        New-ActivationScenarioFixtureUncached -Stage $Stage
    }
}

function New-ActivationRequestFixture {
    param([ValidateSet('PILOT', 'PRODUCTION')][string]$Stage = 'PILOT')
    (New-ActivationScenarioFixture -Stage $Stage).Request
}

function New-ActivationRecordIndexFixture {
    param([ValidateSet('PILOT', 'PRODUCTION')][string]$Stage = 'PILOT')
    @((New-ActivationScenarioFixture -Stage $Stage).RecordIndex)
}

function New-ReadbackFixture {
    param([ValidateSet('PILOT', 'PRODUCTION')][string]$Stage = 'PILOT')
    (New-ActivationScenarioFixture -Stage $Stage).Readback
}

function New-ActivationReadbackMutation {
    param(
        [Parameter(Mandatory = $true)][string]$Field,
        [AllowNull()]$Value,
        [ValidateSet('PILOT', 'PRODUCTION')][string]$Stage = 'PILOT'
    )
    $index = @(New-ActivationRecordIndexFixture -Stage $Stage)
    $readback = New-ReadbackFixture -Stage $Stage
    $record = @($index | Where-Object recordId -eq 'readback-synthetic-1')[0]
    $record.payload.$Field = $Value
    Update-CanonicalRecordBinding $record
    $readback.$Field = $Value
    $readback.readbackRecordDigest = $record.contentDigest
    [pscustomobject]@{ RecordIndex = $index; Readback = $readback }
}

function Get-CheckedRegistry { Get-Content (Join-Path $here 'tool-registry.json') -Raw | ConvertFrom-Json }
function Get-CheckedMatrix { Get-Content (Join-Path $here 'control-matrix.json') -Raw | ConvertFrom-Json }

function New-TransportRegistryFixture {
    param([object[]]$ObjectTypeOwnership = @())
    $registry = Get-CheckedRegistry
    $registry.intuneTransportOwnership.objectTypeOwnership = @($ObjectTypeOwnership)
    $registry
}

function New-DirectGraphExceptionScenario {
    $request = New-ActivationRequestFixture
    $request.writerToolRef = 'microsoft-graph-write'
    $request | Add-Member -NotePropertyName transportExceptionRef -NotePropertyValue 'private://exceptions/graph-synthetic-1'
    $request | Add-Member -NotePropertyName transportExceptionExpiresAt -NotePropertyValue '2026-08-28T00:00:00Z'
    $index = @(New-ActivationRecordIndexFixture)
    $exception = New-CanonicalRecord 'private://exceptions/graph-synthetic-1' 'exception-record' -Fields @{
        status = 'APPROVED'
        managedObjectType = 'deviceManagementConfigurationPolicy'
        targetScopeRef = 'private://rings/ring-synthetic-1'
        writerToolRef = 'microsoft-graph-write'
        providerGapRef = 'private://provider-gaps/gap-synthetic-1'
        reason = 'Synthetic provider gap for validator testing only.'
        ownerRole = 'ROLE_GRAPH_AUTOMATION_OWNER'
        ownerPrincipalRef = 'private://principals/graph-owner-synthetic-1'
        compensatingControlRefs = @('graph-compensating-control-synthetic-1')
        closureEvidenceRef = 'private://evidence/graph-closure-synthetic-1'
        expiresAt = '2026-08-28T00:00:00Z'
    }
    $index += $exception
    $request | Add-Member -NotePropertyName transportExceptionDigest -NotePropertyValue $exception.contentDigest
    $index += New-CanonicalRecord 'graph-compensating-control-synthetic-1' 'compensating-control-record' -Fields @{
        status = 'ACTIVE'
        sourceExceptionRef = 'private://exceptions/graph-synthetic-1'
        ownerRole = 'ROLE_GRAPH_AUTOMATION_OWNER'
        targetScopeRef = 'private://rings/ring-synthetic-1'
        managedObjectType = 'deviceManagementConfigurationPolicy'
        expiresAt = '2026-08-28T00:00:00Z'
    }
    [pscustomobject]@{ Request = $request; RecordIndex = $index; ExceptionRecord = $exception }
}

function Invoke-TestActivation {
    param([ValidateSet('PILOT', 'PRODUCTION')][string]$Stage = 'PILOT', $Request, $Readback, [object[]]$RecordIndex, $Registry)
    if ($null -eq $Request) { $Request = New-ActivationRequestFixture $Stage }
    $effectiveStage = if ($Request.requestedStage -in @('PILOT', 'PRODUCTION')) { [string]$Request.requestedStage } else { $Stage }
    if ($null -eq $RecordIndex) { $RecordIndex = New-ActivationRecordIndexFixture -Stage $effectiveStage }
    if ($null -eq $Registry) { $Registry = Get-CheckedRegistry }
    Get-ActivationDecision -Request $Request -Registry $Registry -RecordIndex $RecordIndex -Readback $Readback -EvaluationTime $evaluationTime -ValidationProfile TEST
}

function Get-TestRecordIndexReasonCodes {
    param([Parameter(Mandatory = $true)][object[]]$RecordIndex)
    $errors = New-Object System.Collections.ArrayList
    [void](Get-CanonicalRecordMap -RecordIndex $RecordIndex -Errors $errors -Context 'operations regression fixture' `
        -EvaluationTime $evaluationTime -ValidationProfile TEST)
    @($errors | ForEach-Object { [string]$_.code })
}

function New-ProductionActivationScenario {
    $scenario = New-ActivationScenarioFixture -Stage 'PRODUCTION'
    [pscustomobject]@{
        Request = $scenario.Request
        RecordIndex = @($scenario.RecordIndex)
        RolloutMonitoringRecord = $scenario.RolloutMonitoringRecord
    }
}

function New-AzureResourceStateScenarioFixture {
    $scenario = New-ActivationScenarioFixture -Stage PRODUCTION
    $records = @($scenario.RecordIndex)
    $plan = @($records | Where-Object recordType -ceq 'reviewed-plan-record')[0]
    $authorization = @($records | Where-Object recordType -ceq 'write-authorization-record')[0]
    $writeOperation = @($records | Where-Object recordId -ceq $scenario.Request.writeOperationRef)[0]
    $consumption = @($records | Where-Object recordId -ceq 'authorization-consumption-synthetic-1')[0]
    $consumptionReadback = @($records | Where-Object recordId -ceq 'authorization-consumption-readback-synthetic-1')[0]
    $roleBinding = @($records | Where-Object recordType -ceq 'role-binding-record')[0]
    $roleReadback = @($records | Where-Object recordType -ceq 'role-binding-readback-record')[0]
    $package = @($records | Where-Object recordType -ceq 'package-verification-record')[0]
    $transport = @($records | Where-Object recordId -ceq $scenario.Request.transportOwnershipRecordRef)[0]

    $operationId = 'azure-deployment-operation-synthetic-1'
    $tenant = 'private://tenants/synthetic'
    $subscription = 'private://subscriptions/synthetic'
    $environment = 'private://environments/synthetic'
    $scope = 'private://azure/resource-groups/synthetic'
    $resourceType = 'Microsoft.Intune/diagnosticSettings'
    $resourceId = 'private://azure/resources/diagnostic-settings-synthetic-1'
    $apiVersion = '2026-01-01'
    $writerIdentity = 'private://identities/azure-terraform-writer-synthetic-1'
    $applyIdentity = 'private://identities/terraform-apply-operator-synthetic-1'
    $projectionRef = 'private://azure/projections/diagnostic-settings-synthetic-1'
    $projectionDigest = New-TestDigest '1'
    $stateDigest = New-TestDigest '2'
    $objectRefs = @($resourceId)
    $objectSetDigest = Get-ManagedObjectSetDigest -ManagedObjectRefs $objectRefs

    $plan.payload.writerToolRef = 'terraform'
    $plan.payload.targetScopeRef = $scope
    $plan.payload.managedObjectType = $resourceType
    foreach ($field in ([ordered]@{
        azureSubscriptionBoundaryRef = $subscription
        azureResourceType = $resourceType
        azureResourceIdRef = $resourceId
        azureApiVersion = $apiVersion
        expectedStateProjectionRef = $projectionRef
        expectedStateProjectionDigest = $projectionDigest
        expectedStateDigest = $stateDigest
    }).GetEnumerator()) {
        $plan.payload | Add-Member -NotePropertyName $field.Key -NotePropertyValue $field.Value
    }
    Update-CanonicalRecordBinding $plan

    $transport.payload.managedObjectType = $resourceType
    $transport.payload.targetScopeRef = $scope
    $transport.payload.writerToolRef = 'terraform'
    Update-CanonicalRecordBinding $transport

    $scenario.Request.writerToolRef = 'terraform'
    $scenario.Request.writeIdentityRef = $writerIdentity
    $scenario.Request.applyOperatorIdentityRef = $applyIdentity
    $scenario.Request.targetScopeRef = $scope
    $scenario.Request.managedObjectType = $resourceType
    $scenario.Request.managedObjectRefs = @($objectRefs)
    $scenario.Request.managedObjectSetDigest = $objectSetDigest
    $scenario.Request.reviewedPlanDigest = $plan.contentDigest
    $scenario.Request.transportOwnershipRecordDigest = $transport.contentDigest
    $scenario.Request.writeOperationId = $operationId
    $scenario.Request.writeCompletedAt = '2026-08-27T12:20:00Z'

    $authorization.payload.authorizedOperationId = $operationId
    $authorization.payload.requestDigest = Get-WriteAuthorizationRequestDigest -Request $scenario.Request
    $authorization.payload.reviewedPlanDigest = $plan.contentDigest
    $authorization.payload.transportOwnershipDigest = $transport.contentDigest
    $authorization.payload.writerToolRef = 'terraform'
    $authorization.payload.writeIdentityRef = $writerIdentity
    $authorization.payload.applyOperatorIdentityRef = $applyIdentity
    $authorization.payload.managedObjectType = $resourceType
    $authorization.payload.managedObjectRefs = @($objectRefs)
    $authorization.payload.managedObjectSetDigest = $objectSetDigest
    $authorization.payload.tenantBoundaryRef = $tenant
    $authorization.payload.targetEnvironmentRef = $environment
    $authorization.payload.targetScopeRef = $scope
    $authorization.payload.authorizationSubjectDigest = Get-WriteAuthorizationSubjectDigest -Authorization $authorization.payload
    $authorization.payload.authorizationArtifactDigest = $authorization.payload.authorizationSubjectDigest
    Update-CanonicalRecordBinding $authorization
    $scenario.Request.writeAuthorizationDigest = $authorization.contentDigest

    $consumption.payload.authorizationDigest = $authorization.contentDigest
    $consumption.payload.authorizedOperationId = $operationId
    $consumption.payload.managedObjectSetDigest = $objectSetDigest
    Update-CanonicalRecordBinding $consumption

    $writeOperation.payload.operationId = $operationId
    $writeOperation.payload.writeAuthorizationDigest = $authorization.contentDigest
    $writeOperation.payload.authorizationConsumptionDigest = $consumption.contentDigest
    $writeOperation.payload.reviewedPlanDigest = $plan.contentDigest
    $writeOperation.payload.transportOwnershipDigest = $transport.contentDigest
    $writeOperation.payload.writerToolRef = 'terraform'
    $writeOperation.payload.writeIdentityRef = $writerIdentity
    $writeOperation.payload.applyOperatorIdentityRef = $applyIdentity
    $writeOperation.payload.managedObjectType = $resourceType
    $writeOperation.payload.managedObjectRefs = @($objectRefs)
    $writeOperation.payload.managedObjectSetDigest = $objectSetDigest
    $writeOperation.payload.tenantBoundaryRef = $tenant
    $writeOperation.payload.targetEnvironmentRef = $environment
    $writeOperation.payload.targetScopeRef = $scope
    $writeOperation.payload.expectedReadbackKind = 'AZURE_RESOURCE_STATE'
    Update-CanonicalRecordBinding $writeOperation

    $consumptionReadback.payload.consumptionRecordDigest = $consumption.contentDigest
    $consumptionReadback.payload.authorizationDigest = $authorization.contentDigest
    $consumptionReadback.payload.authorizedOperationId = $operationId
    $consumptionReadback.payload.writeOperationDigest = $writeOperation.contentDigest
    $consumptionReadback.payload.writeOperationId = $operationId
    Update-CanonicalRecordBinding $consumptionReadback

    $azureOperation = New-CanonicalRecord $operationId 'azure-deployment-operation-record' -Fields @{
        schemaVersion = '1.0.0'; recordStage = 'AZURE_RESOURCE_DEPLOYMENT_OPERATION'; status = 'COMPLETED'
        operationId = $operationId; writerToolRef = 'terraform'; writeIdentityRef = $writerIdentity
        applyOperatorIdentityRef = $applyIdentity; tenantBoundaryRef = $tenant
        subscriptionBoundaryRef = $subscription; targetEnvironmentRef = $environment; targetScopeRef = $scope
        resourceType = $resourceType; resourceIdRef = $resourceId; apiVersion = $apiVersion
        sourceCommit = $plan.payload.sourceCommit; desiredStateRevision = $plan.payload.desiredStateRevision
        reviewedPlanRef = $plan.recordId; reviewedPlanDigest = $plan.contentDigest
        expectedStateProjectionRef = $projectionRef; expectedStateProjectionDigest = $projectionDigest
        expectedStateDigest = $stateDigest; writeAuthorizationRef = $authorization.recordId
        writeAuthorizationDigest = $authorization.contentDigest; writeOperationRef = $writeOperation.recordId
        writeOperationDigest = $writeOperation.contentDigest; authorizationConsumptionRef = $consumption.recordId
        authorizationConsumptionDigest = $consumption.contentDigest
        authorizationConsumptionReadbackRef = $consumptionReadback.recordId
        authorizationConsumptionReadbackDigest = $consumptionReadback.contentDigest
        roleBindingRef = $roleBinding.recordId; roleBindingDigest = $roleBinding.contentDigest
        roleBindingReadbackRef = $roleReadback.recordId; roleBindingReadbackDigest = $roleReadback.contentDigest
        packageVerificationRef = $package.recordId; packageVerificationDigest = $package.contentDigest
        operationArtifactRef = 'private://azure/operations/deployment-synthetic-1'
        operationArtifactDigest = New-TestDigest '3'
        startedAt = $writeOperation.payload.mutationStartedAt; completedAt = $writeOperation.payload.completedAt
    }
    $azureReadback = New-CanonicalRecord 'azure-resource-state-readback-synthetic-1' 'readback-record' -Fields @{
        schemaVersion = '1.0.0'; recordStage = 'AZURE_RESOURCE_STATE_READBACK'; status = 'VERIFIED'
        readbackKind = 'AZURE_RESOURCE_STATE'; readerToolRef = 'azure-resource-manager-readback'
        readIdentityRef = 'private://identities/azure-resource-reader-synthetic-1'
        tenantBoundaryRef = $tenant; subscriptionBoundaryRef = $subscription; targetEnvironmentRef = $environment
        targetScopeRef = $scope; resourceType = $resourceType; resourceIdRef = $resourceId; apiVersion = $apiVersion
        sourceCommit = $plan.payload.sourceCommit; desiredStateRevision = $plan.payload.desiredStateRevision
        deploymentOperationRef = $azureOperation.recordId; deploymentOperationDigest = $azureOperation.contentDigest
        deploymentOperationId = $operationId; readbackProjectionRef = $projectionRef
        readbackProjectionDigest = $projectionDigest; expectedStateDigest = $stateDigest; observedStateDigest = $stateDigest
        httpStatus = 200; responseBodyPresent = $true; stateMatched = $true
        collectedAt = '2026-08-27T12:25:00Z'; freshnessPolicyRef = $authorization.payload.independentReadbackPolicyRef
        freshnessPolicyDigest = $authorization.payload.independentReadbackPolicyDigest
        freshnessMaxAgeMinutes = $authorization.payload.readbackMaxAgeMinutes
        freshnessBinding = [pscustomobject][ordered]@{
            observedAt = '2026-08-27T12:25:00Z'; admittedAt = '2026-08-27T12:25:00Z'
            policyRef = $authorization.payload.independentReadbackPolicyRef; maxAgeDays = 1
            dependencySnapshotRef = $azureOperation.recordId; dependencySnapshotDigest = $azureOperation.contentDigest
            dependencyStatus = 'MATCH'
        }
    }
    $records += @($azureOperation, $azureReadback)
    [pscustomobject]@{ RecordIndex = @($records); AzureOperation = $azureOperation; AzureReadback = $azureReadback }
}

function New-OperationsFullRecordIndexFixture {
    $issued = New-IssuedClaimFixture
    $production = New-ProductionActivationScenario
    $schema = Get-Content (Join-Path $here 'operations-record-contracts.schema.json') -Raw | ConvertFrom-Json
    # Prefer the production closure records where both chains provide the same operations type.
    $allRecords = @($production.RecordIndex) + @($issued.RecordIndex)
    $allRecords += New-CanonicalRecord 'procurement-envelope-synthetic-1' 'procurement-envelope-record' -Fields @{
        status = 'APPROVED'
        manifestRef = 'manifest-activation-synthetic-1'
        verdictRef = 'activation-verdict-synthetic-1'
        procurementEnvelope = Copy-TestObject (@($production.RecordIndex | Where-Object recordId -eq 'activation-verdict-synthetic-1')[0].payload.procurementEnvelope)
        approvedAt = '2026-08-27T12:09:00Z'
        approverRole = 'ROLE_PROCUREMENT_APPROVER'
    }
    $allRecords += New-CanonicalRecord 'exception-synthetic-1' 'exception-record' -Fields @{
        status = 'APPROVED'
        managedObjectType = 'deviceManagementConfigurationPolicy'
        targetScopeRef = 'private://rings/ring-synthetic-1'
        writerToolRef = 'microsoft-graph-write'
        providerGapRef = 'private://provider-gaps/synthetic-1'
        reason = 'Synthetic bounded provider-gap fixture.'
        ownerRole = 'ROLE_GRAPH_AUTOMATION_OWNER'
        ownerPrincipalRef = 'private://principals/graph-exception-owner-synthetic-1'
        compensatingControlRefs = @('graph-compensating-control-synthetic-1')
        closureEvidenceRef = 'private://evidence/graph-exception-closure-synthetic-1'
        expiresAt = '2026-08-28T00:00:00Z'
    }
    $azurePlan = @($production.RecordIndex | Where-Object recordType -ceq 'reviewed-plan-record')[0]
    $azureAuthorization = @($production.RecordIndex | Where-Object recordType -ceq 'write-authorization-record')[0]
    $azureWriteOperation = @($production.RecordIndex | Where-Object recordType -ceq 'write-operation-record')[0]
    $azureConsumption = @($production.RecordIndex | Where-Object recordType -ceq 'authorization-consumption-record')[0]
    $azureConsumptionReadback = @($production.RecordIndex | Where-Object recordType -ceq 'authorization-consumption-ledger-readback-record')[0]
    $azureRoleBinding = @($production.RecordIndex | Where-Object recordType -ceq 'role-binding-record')[0]
    $azureRoleReadback = @($production.RecordIndex | Where-Object recordType -ceq 'role-binding-readback-record')[0]
    $azurePackage = @($production.RecordIndex | Where-Object recordType -ceq 'package-verification-record')[0]
    $allRecords += New-CanonicalRecord 'azure-deployment-operation-synthetic-1' 'azure-deployment-operation-record' -Fields @{
        schemaVersion = '1.0.0'
        recordStage = 'AZURE_RESOURCE_DEPLOYMENT_OPERATION'
        status = 'COMPLETED'
        operationId = 'azure-deployment-operation-synthetic-1'
        writerToolRef = 'terraform'
        writeIdentityRef = 'private://identities/azure-terraform-writer-synthetic-1'
        applyOperatorIdentityRef = 'private://identities/azure-terraform-apply-synthetic-1'
        tenantBoundaryRef = 'private://tenants/synthetic'
        subscriptionBoundaryRef = 'private://subscriptions/synthetic'
        targetEnvironmentRef = 'private://environments/synthetic'
        targetScopeRef = 'private://azure/resource-groups/synthetic'
        resourceType = 'Microsoft.Intune/diagnosticSettings'
        resourceIdRef = 'private://azure/resources/diagnostic-settings-synthetic-1'
        apiVersion = '2026-01-01'
        sourceCommit = $azurePlan.payload.sourceCommit
        desiredStateRevision = $azurePlan.payload.desiredStateRevision
        reviewedPlanRef = $azurePlan.recordId
        reviewedPlanDigest = $azurePlan.contentDigest
        expectedStateProjectionRef = 'private://azure/projections/diagnostic-settings-synthetic-1'
        expectedStateProjectionDigest = New-TestDigest '1'
        expectedStateDigest = New-TestDigest '2'
        writeAuthorizationRef = $azureAuthorization.recordId
        writeAuthorizationDigest = $azureAuthorization.contentDigest
        writeOperationRef = $azureWriteOperation.recordId
        writeOperationDigest = $azureWriteOperation.contentDigest
        authorizationConsumptionRef = $azureConsumption.recordId
        authorizationConsumptionDigest = $azureConsumption.contentDigest
        authorizationConsumptionReadbackRef = $azureConsumptionReadback.recordId
        authorizationConsumptionReadbackDigest = $azureConsumptionReadback.contentDigest
        roleBindingRef = $azureRoleBinding.recordId
        roleBindingDigest = $azureRoleBinding.contentDigest
        roleBindingReadbackRef = $azureRoleReadback.recordId
        roleBindingReadbackDigest = $azureRoleReadback.contentDigest
        packageVerificationRef = $azurePackage.recordId
        packageVerificationDigest = $azurePackage.contentDigest
        operationArtifactRef = 'private://azure/operations/diagnostic-settings-synthetic-1'
        operationArtifactDigest = New-TestDigest '3'
        startedAt = '2026-08-27T12:15:00Z'
        completedAt = '2026-08-27T12:20:00Z'
    }
    $records = New-Object System.Collections.ArrayList
    foreach ($variant in @($schema.'$defs'.operationsCanonicalRecord.oneOf)) {
        $definitionName = [string]$variant.'$ref'.Split('/')[-1]
        $recordType = [string]$schema.'$defs'.PSObject.Properties[$definitionName].Value.allOf[1].properties.recordType.const
        $record = @($allRecords | Where-Object { [string]$_.recordType -ceq $recordType })[0]
        if ($null -eq $record) { throw "No canonical fixture exists for operations recordType $recordType." }
        [void]$records.Add($record)
    }
    @($records)
}

function Update-RolloutMonitoringRequestBinding {
    param([Parameter(Mandatory = $true)]$Scenario)
    Update-CanonicalRecordBinding $Scenario.RolloutMonitoringRecord
    $Scenario.Request.rolloutMonitoringRecordDigest = $Scenario.RolloutMonitoringRecord.contentDigest
}

function New-TemporaryBlueprintDirectory {
    param([string]$Parent)
    if ([string]::IsNullOrWhiteSpace($Parent)) { $Parent = [IO.Path]::GetTempPath() }
    $path = Join-Path $Parent ('operations-blueprint-test-' + [Guid]::NewGuid().ToString('N'))
    [void](New-Item -ItemType Directory -Path $path)
    $path
}

function New-BlueprintManifestTestDirectory {
    $path = New-TemporaryBlueprintDirectory
    foreach ($name in @(
        '.gitattributes',
        'control-matrix.json',
        'GOVERNANCE_AND_IAC_OPERATING_MODEL.md',
        'LEADERSHIP_DECISION_PACKET_TEMPLATE.md',
        'leadership-claim-chain.json',
        'operations-record-contracts.schema.json',
        'OperationsBlueprint.Tests.ps1',
        'private-activation-checklist.md',
        'README.md',
        'Test-OperationsBlueprint.ps1',
        'tool-registry.json',
        'BLUEPRINT_MANIFEST.sha256'
    )) {
        Copy-Item -LiteralPath (Join-Path $here $name) -Destination $path
    }
    $path
}

function Test-TestPathWithinRoot {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Root
    )
    $fullPath = [IO.Path]::GetFullPath($Path)
    $fullRoot = [IO.Path]::GetFullPath($Root).TrimEnd([char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar))
    $prefix = $fullRoot + [IO.Path]::DirectorySeparatorChar
    $comparison = if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
    $fullPath.Equals($fullRoot, $comparison) -or $fullPath.StartsWith($prefix, $comparison)
}

function Get-TestEnvironmentVariableState {
    param([Parameter(Mandatory = $true)][string]$Name)

    $path = "Env:$Name"
    $present = Test-Path -LiteralPath $path
    [pscustomobject][ordered]@{
        Name = $Name
        Present = $present
        Value = if ($present) { [string](Get-Item -LiteralPath $path -ErrorAction Stop).Value } else { $null }
    }
}

function Remove-TestEnvironmentVariable {
    param([Parameter(Mandatory = $true)][string]$Name)

    Remove-Item -LiteralPath "Env:$Name" -ErrorAction SilentlyContinue
}

function Restore-TestEnvironmentVariableState {
    param([Parameter(Mandatory = $true)]$State)

    if ($State.Present -eq $true) {
        if (Test-Path -LiteralPath "Env:$($State.Name)") {
            Set-Item -LiteralPath "Env:$($State.Name)" -Value ([string]$State.Value)
        }
        else {
            New-Item -Path Env: -Name ([string]$State.Name) -Value ([string]$State.Value) | Out-Null
        }
    }
    else {
        Remove-TestEnvironmentVariable -Name ([string]$State.Name)
    }
}

function Initialize-TestDirectoryCaseSensitivityInterop {
    if ('OperationsBlueprintTests.NativeDirectoryCaseSensitivity' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace OperationsBlueprintTests
{
    public static class NativeDirectoryCaseSensitivity
    {
        [StructLayout(LayoutKind.Sequential)]
        private struct FILE_CASE_SENSITIVE_INFO
        {
            public UInt32 Flags;
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern SafeFileHandle CreateFileW(
            string fileName,
            UInt32 desiredAccess,
            UInt32 shareMode,
            IntPtr securityAttributes,
            UInt32 creationDisposition,
            UInt32 flagsAndAttributes,
            IntPtr templateFile);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool GetFileInformationByHandleEx(
            SafeFileHandle fileHandle,
            Int32 fileInformationClass,
            out FILE_CASE_SENSITIVE_INFO fileInformation,
            UInt32 bufferSize);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern UInt32 QueryDosDeviceW(
            string deviceName,
            StringBuilder targetPath,
            UInt32 maximumLength);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern UInt32 GetFinalPathNameByHandleW(
            SafeFileHandle fileHandle,
            StringBuilder filePath,
            UInt32 filePathLength,
            UInt32 flags);

        private static SafeFileHandle OpenExistingPath(string path)
        {
            const UInt32 FILE_SHARE_READ = 0x00000001;
            const UInt32 FILE_SHARE_WRITE = 0x00000002;
            const UInt32 FILE_SHARE_DELETE = 0x00000004;
            const UInt32 OPEN_EXISTING = 3;
            const UInt32 FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;
            SafeFileHandle handle = CreateFileW(
                path,
                0,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                IntPtr.Zero,
                OPEN_EXISTING,
                FILE_FLAG_BACKUP_SEMANTICS,
                IntPtr.Zero);
            if (handle.IsInvalid)
            {
                int error = Marshal.GetLastWin32Error();
                handle.Dispose();
                throw new Win32Exception(error);
            }
            return handle;
        }

        public static bool IsCaseSensitive(string directoryPath)
        {
            const Int32 FileCaseSensitiveInfo = 23;
            const UInt32 FILE_CS_FLAG_CASE_SENSITIVE_DIR = 0x00000001;

            using (SafeFileHandle handle = OpenExistingPath(directoryPath))
            {
                FILE_CASE_SENSITIVE_INFO information;
                if (!GetFileInformationByHandleEx(
                    handle,
                    FileCaseSensitiveInfo,
                    out information,
                    (UInt32)Marshal.SizeOf(typeof(FILE_CASE_SENSITIVE_INFO))))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                }
                return (information.Flags & FILE_CS_FLAG_CASE_SENSITIVE_DIR) != 0;
            }
        }

        public static string[] GetDosDeviceTargets(string driveName)
        {
            StringBuilder buffer = new StringBuilder(32768);
            UInt32 length = QueryDosDeviceW(driveName, buffer, (UInt32)buffer.Capacity);
            if (length == 0)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }
            return buffer.ToString().Split(new char[] { '\0' }, StringSplitOptions.RemoveEmptyEntries);
        }

        public static string GetFinalPath(string existingPath)
        {
            const UInt32 FILE_NAME_NORMALIZED = 0;
            const UInt32 VOLUME_NAME_DOS = 0;
            using (SafeFileHandle handle = OpenExistingPath(existingPath))
            {
                StringBuilder buffer = new StringBuilder(32768);
                UInt32 length = GetFinalPathNameByHandleW(
                    handle,
                    buffer,
                    (UInt32)buffer.Capacity,
                    FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
                if (length == 0 || length >= buffer.Capacity)
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                }
                return buffer.ToString();
            }
        }
    }
}
'@
}

function Get-TestDirectoryCaseSensitivityState {
    param([Parameter(Mandatory = $true)][string]$DirectoryPath)

    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        return [pscustomobject]@{ QuerySucceeded = $false; CaseSensitive = $null }
    }
    try {
        Initialize-TestDirectoryCaseSensitivityInterop
        [pscustomobject]@{
            QuerySucceeded = $true
            CaseSensitive = [OperationsBlueprintTests.NativeDirectoryCaseSensitivity]::IsCaseSensitive($DirectoryPath)
        }
    }
    catch {
        [pscustomobject]@{ QuerySucceeded = $false; CaseSensitive = $null }
    }
}

function Get-TestWindowsVolumeDeviceTargets {
    param([Parameter(Mandatory = $true)][string]$DriveName)
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { return @() }
    Initialize-TestDirectoryCaseSensitivityInterop
    @([OperationsBlueprintTests.NativeDirectoryCaseSensitivity]::GetDosDeviceTargets($DriveName))
}

function Get-TestWindowsFinalHandlePath {
    param([Parameter(Mandatory = $true)][string]$ExistingPath)
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { return $null }
    Initialize-TestDirectoryCaseSensitivityInterop
    [OperationsBlueprintTests.NativeDirectoryCaseSensitivity]::GetFinalPath($ExistingPath)
}

function Assert-TestProductionWindowsToolchainBoundary {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [string[]]$CandidatePaths = @(),
        [scriptblock]$CaseSensitivityQuery = { param($DirectoryPath) Get-TestDirectoryCaseSensitivityState -DirectoryPath $DirectoryPath },
        [scriptblock]$VolumeDeviceQuery = { param($DriveName) @(Get-TestWindowsVolumeDeviceTargets -DriveName $DriveName) },
        [scriptblock]$FinalPathQuery = { param($ExistingPath) Get-TestWindowsFinalHandlePath -ExistingPath $ExistingPath }
    )

    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'Production schema validation requires a Windows trusted runner.'
    }
    if (-not [IO.Path]::IsPathRooted($Root) -or -not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw 'The production toolchain root must be an existing absolute directory.'
    }
    $resolvedRoot = (Resolve-Path -LiteralPath $Root -ErrorAction Stop).ProviderPath.TrimEnd(
        [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    )
    $volumeRoot = [IO.Path]::GetPathRoot($resolvedRoot)
    if ([string]::IsNullOrWhiteSpace($volumeRoot) -or $volumeRoot.StartsWith('\\', [StringComparison]::Ordinal)) {
        throw 'The production toolchain root must be on a local fixed volume.'
    }
    try { $drive = [IO.DriveInfo]::new($volumeRoot) }
    catch { throw 'The production toolchain volume could not be authenticated.' }
    if (-not $drive.IsReady -or $drive.DriveType -ne [IO.DriveType]::Fixed -or
        @('NTFS', 'ReFS') -notcontains [string]$drive.DriveFormat) {
        throw 'The production toolchain root requires a ready fixed NTFS or ReFS volume.'
    }
    $driveName = $volumeRoot.TrimEnd([char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar))
    $deviceTargets = @(& $VolumeDeviceQuery $driveName)
    if ($deviceTargets.Count -ne 1 -or [string]$deviceTargets[0] -cnotmatch '^\\Device\\HarddiskVolume[0-9]+$') {
        throw 'The production toolchain root may not use SUBST, DOS-device, redirected, or ambiguous volume mapping.'
    }

    Assert-TestPathChainWithoutReparsePoint -Path $resolvedRoot -Root $resolvedRoot -IncludeRootAncestors
    $directories = [System.Collections.Generic.Dictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
    $rootCursor = [IO.DirectoryInfo]::new($resolvedRoot)
    while ($null -ne $rootCursor) {
        if (-not $directories.ContainsKey($rootCursor.FullName)) { $directories.Add($rootCursor.FullName, $rootCursor.FullName) }
        $rootCursor = $rootCursor.Parent
    }

    $canonicalPaths = [System.Collections.Generic.Dictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
    $canonicalPaths.Add($resolvedRoot, $resolvedRoot)
    foreach ($candidatePath in @($CandidatePaths)) {
        if ([string]::IsNullOrWhiteSpace($candidatePath) -or -not (Test-Path -LiteralPath $candidatePath)) {
            throw 'Every production toolchain candidate path must exist.'
        }
        $resolvedCandidate = (Resolve-Path -LiteralPath $candidatePath -ErrorAction Stop).ProviderPath
        if (-not $canonicalPaths.ContainsKey($resolvedCandidate)) { $canonicalPaths.Add($resolvedCandidate, $resolvedCandidate) }
        $candidateItem = Get-Item -LiteralPath $resolvedCandidate -Force -ErrorAction Stop
        $candidateDirectory = if ($candidateItem.PSIsContainer) { $candidateItem.FullName } else { $candidateItem.Directory.FullName }
        if (-not (Test-TestPathWithinRoot -Path $candidateDirectory -Root $resolvedRoot)) {
            throw 'Every production toolchain candidate parent must remain beneath the trusted root.'
        }
        Assert-TestPathChainWithoutReparsePoint -Path $resolvedCandidate -Root $resolvedRoot
        $cursor = [IO.DirectoryInfo]::new($candidateDirectory)
        $reachedRoot = $false
        while ($null -ne $cursor) {
            if (-not $directories.ContainsKey($cursor.FullName)) { $directories.Add($cursor.FullName, $cursor.FullName) }
            if ($cursor.FullName.Equals($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
                $reachedRoot = $true
                break
            }
            $cursor = $cursor.Parent
        }
        if (-not $reachedRoot) { throw 'A production toolchain candidate parent escaped the trusted root.' }
    }

    foreach ($directory in @($directories.Values)) {
        $state = & $CaseSensitivityQuery $directory
        if ($null -eq $state -or $state.QuerySucceeded -ne $true -or $state.CaseSensitive -ne $false) {
            throw 'Production schema validation requires authenticated case-insensitive directory semantics.'
        }
    }
    foreach ($canonicalPath in @($canonicalPaths.Values)) {
        $expectedFinalPath = ('\\?\' + [IO.Path]::GetFullPath($canonicalPath)).TrimEnd([char[]]@('\'))
        $observedFinalPath = [string](& $FinalPathQuery $canonicalPath)
        if ([string]::IsNullOrWhiteSpace($observedFinalPath) -or
            -not $observedFinalPath.TrimEnd([char[]]@('\')).Equals($expectedFinalPath, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'A production toolchain handle did not resolve to the exact checked canonical path.'
        }
    }
    $deviceTargetsAfterValidation = @(& $VolumeDeviceQuery $driveName)
    if ($deviceTargetsAfterValidation.Count -ne 1 -or
        [string]$deviceTargetsAfterValidation[0] -cne [string]$deviceTargets[0]) {
        throw 'The production toolchain volume mapping changed during validation.'
    }
}

function Assert-TestPathChainWithoutReparsePoint {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Root,
        [switch]$IncludeRootAncestors
    )

    $fullRoot = [IO.Path]::GetFullPath($Root).TrimEnd(
        [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    )
    $fullPath = [IO.Path]::GetFullPath($Path)
    if (-not (Test-TestPathWithinRoot -Path $fullPath -Root $fullRoot)) {
        throw 'Trusted path does not remain beneath its designated root.'
    }
    $relative = $fullPath.Substring($fullRoot.Length).TrimStart(
        [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    )
    $paths = New-Object System.Collections.Generic.List[string]
    if ($IncludeRootAncestors) {
        $ancestors = New-Object System.Collections.Generic.List[string]
        $ancestor = [IO.DirectoryInfo]::new($fullRoot)
        while ($null -ne $ancestor) {
            [void]$ancestors.Add($ancestor.FullName)
            $ancestor = $ancestor.Parent
        }
        for ($ancestorIndex = $ancestors.Count - 1; $ancestorIndex -ge 1; $ancestorIndex--) {
            [void]$paths.Add($ancestors[$ancestorIndex])
        }
    }
    [void]$paths.Add($fullRoot)
    $cursor = $fullRoot
    if (-not [string]::IsNullOrEmpty($relative)) {
        foreach ($segment in $relative.Split([char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar), [StringSplitOptions]::RemoveEmptyEntries)) {
            $cursor = Join-Path $cursor $segment
            [void]$paths.Add($cursor)
        }
    }
    foreach ($candidate in $paths) {
        $attributes = [IO.File]::GetAttributes($candidate)
        if (([IO.FileAttributes]$attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Trusted toolchain paths may not contain a reparse point or symbolic link.'
        }
    }
}

function Get-PinnedDirectoryTreeSha256 {
    param([Parameter(Mandatory = $true)][string]$Root)

    if (-not [IO.Path]::IsPathRooted($Root) -or -not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw 'Pinned package tree root must be an existing absolute directory.'
    }
    $resolvedRoot = (Resolve-Path -LiteralPath $Root -ErrorAction Stop).ProviderPath.TrimEnd(
        [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    )
    Assert-TestPathChainWithoutReparsePoint -Path $resolvedRoot -Root $resolvedRoot -IncludeRootAncestors
    if (([IO.File]::GetAttributes($resolvedRoot) -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Pinned package tree root may not be a reparse point or symbolic link.'
    }
    $filesByRelativePath = [System.Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    foreach ($entry in @(Get-ChildItem -LiteralPath $resolvedRoot -Force -Recurse -ErrorAction Stop)) {
        if (([IO.File]::GetAttributes($entry.FullName) -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Pinned package tree contains a reparse point or symbolic link: $($entry.FullName)"
        }
        if ($entry.PSIsContainer) { continue }
        $relativePath = $entry.FullName.Substring($resolvedRoot.Length).TrimStart(
            [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
        ).Replace('\', '/')
        if ([string]::IsNullOrWhiteSpace($relativePath) -or
            [regex]::IsMatch($relativePath, '[\x00-\x1f\x7f]') -or
            $filesByRelativePath.ContainsKey($relativePath)) {
            throw 'Pinned package tree contains an empty or duplicate ordinal relative path.'
        }
        $filesByRelativePath.Add($relativePath, $entry.FullName)
    }
    if ($filesByRelativePath.Count -eq 0) { throw 'Pinned package tree may not be empty.' }
    [string[]]$relativePaths = @($filesByRelativePath.Keys)
    [Array]::Sort($relativePaths, [StringComparer]::Ordinal)
    $treeText = New-Object Text.StringBuilder
    foreach ($relativePath in $relativePaths) {
        $fileHash = (Get-FileHash -LiteralPath $filesByRelativePath[$relativePath] -Algorithm SHA256).Hash.ToLowerInvariant()
        [void]$treeText.Append($fileHash).Append('  ./').Append($relativePath).Append("`n")
    }
    (Get-Sha256TokenFromText -Text $treeText.ToString()).Substring(7)
}

function Get-TrustedSchemaToolchain {
    param([ValidateSet('TEST','PRODUCTION')][string]$ValidationProfile = 'PRODUCTION')

    $ValidationProfile = ([string]$ValidationProfile).ToUpperInvariant()
    # Trusted runners must inject explicit immutable paths and lowercase SHA-256 values.
    # No PATH, profile, AppData, parent-directory, Firebase, or repository package discovery is permitted.
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'Production schema validation requires a Windows trusted runner.'
    }
    $loaderOverrides = @(Get-ChildItem Env: | Where-Object {
        $_.Name.StartsWith('NODE_', [StringComparison]::OrdinalIgnoreCase) -or
            $_.Name.StartsWith('LD_', [StringComparison]::OrdinalIgnoreCase) -or
            $_.Name.Equals('OPENSSL_CONF', [StringComparison]::OrdinalIgnoreCase) -or
            $_.Name.Equals('OPENSSL_CONF_INCLUDE', [StringComparison]::OrdinalIgnoreCase) -or
            $_.Name.Equals('OPENSSL_MODULES', [StringComparison]::OrdinalIgnoreCase) -or
            $_.Name.Equals('OPENSSL_ENGINES', [StringComparison]::OrdinalIgnoreCase) -or
            $_.Name.StartsWith('DYLD_', [StringComparison]::OrdinalIgnoreCase)
    })
    if ($loaderOverrides.Count -gt 0) {
        throw "Trusted schema validation rejects every present Node or dynamic-loader override: $(@($loaderOverrides.Name) -join ', ')."
    }
    $variables = [ordered]@{
        Root = 'OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT'
        SchemaRuntimeRoot = 'OPERATIONS_BLUEPRINT_NODE_RUNTIME_ROOT'
        SchemaRuntimeContentHash = 'OPERATIONS_BLUEPRINT_NODE_RUNTIME_CONTENT_SHA256'
        SchemaRuntimeTreeHash = 'OPERATIONS_BLUEPRINT_NODE_RUNTIME_TREE_SHA256'
        SchemaWorkingDirectory = 'OPERATIONS_BLUEPRINT_SCHEMA_WORKING_DIRECTORY'
        NodePath = 'OPERATIONS_BLUEPRINT_NODE_PATH'
        NodeHash = 'OPERATIONS_BLUEPRINT_NODE_SHA256'
        NodeModulesRoot = 'OPERATIONS_BLUEPRINT_NODE_MODULES_ROOT'
        NodeModulesTreeHash = 'OPERATIONS_BLUEPRINT_NODE_MODULES_TREE_SHA256'
        AjvRoot = 'OPERATIONS_BLUEPRINT_AJV_ROOT'
        AjvTreeHash = 'OPERATIONS_BLUEPRINT_AJV_TREE_SHA256'
        AjvPath = 'OPERATIONS_BLUEPRINT_AJV_PATH'
        AjvHash = 'OPERATIONS_BLUEPRINT_AJV_SHA256'
        AjvFormatsRoot = 'OPERATIONS_BLUEPRINT_AJV_FORMATS_ROOT'
        AjvFormatsTreeHash = 'OPERATIONS_BLUEPRINT_AJV_FORMATS_TREE_SHA256'
        AjvFormatsPath = 'OPERATIONS_BLUEPRINT_AJV_FORMATS_PATH'
        AjvFormatsHash = 'OPERATIONS_BLUEPRINT_AJV_FORMATS_SHA256'
    }
    $values = @{}
    foreach ($entry in $variables.GetEnumerator()) {
        $value = [Environment]::GetEnvironmentVariable($entry.Value)
        if ([string]::IsNullOrWhiteSpace($value)) {
            throw "Trusted schema toolchain variable $($entry.Value) is required."
        }
        $values[$entry.Key] = $value
    }
    if (-not [IO.Path]::IsPathRooted([string]$values.Root) -or
        -not (Test-Path -LiteralPath $values.Root -PathType Container)) {
        throw 'OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT must be an existing absolute directory.'
    }
    $resolvedRoot = (Resolve-Path -LiteralPath $values.Root -ErrorAction Stop).ProviderPath
    Assert-TestPathChainWithoutReparsePoint -Path $resolvedRoot -Root $resolvedRoot -IncludeRootAncestors
    Assert-TestProductionWindowsToolchainBoundary -Root $resolvedRoot
    $repoRoot = [IO.Path]::GetFullPath((Join-Path $here '..\..\..\..'))
    if (Test-TestPathWithinRoot -Path $resolvedRoot -Root $repoRoot) {
        throw 'The trusted schema toolchain root may not be inside the pull-request checkout.'
    }
    if (-not [IO.Path]::IsPathRooted([string]$values.SchemaRuntimeRoot) -or
        -not (Test-Path -LiteralPath $values.SchemaRuntimeRoot -PathType Container)) {
        throw 'OPERATIONS_BLUEPRINT_NODE_RUNTIME_ROOT must be an existing absolute directory.'
    }
    if ([string]$values.SchemaRuntimeContentHash -cnotmatch '^[a-f0-9]{64}$' -or
        [string]$values.SchemaRuntimeTreeHash -cnotmatch '^[a-f0-9]{64}$') {
        throw 'Both Node runtime content and guarded-tree SHA-256 pins must be lowercase 64-character digests.'
    }
    if (-not [IO.Path]::IsPathRooted([string]$values.SchemaWorkingDirectory) -or
        -not (Test-Path -LiteralPath $values.SchemaWorkingDirectory -PathType Container)) {
        throw 'OPERATIONS_BLUEPRINT_SCHEMA_WORKING_DIRECTORY must be an existing absolute directory.'
    }
    $resolvedSchemaRuntimeRoot = (Resolve-Path -LiteralPath $values.SchemaRuntimeRoot -ErrorAction Stop).ProviderPath
    $resolvedSchemaWorkingDirectory = (Resolve-Path -LiteralPath $values.SchemaWorkingDirectory -ErrorAction Stop).ProviderPath
    if (-not (Test-TestPathWithinRoot -Path $resolvedSchemaRuntimeRoot -Root $resolvedRoot) -or
        -not (Test-TestPathWithinRoot -Path $resolvedSchemaWorkingDirectory -Root $resolvedSchemaRuntimeRoot) -or
        (Test-TestPathWithinRoot -Path $resolvedSchemaRuntimeRoot -Root $repoRoot) -or
        (Test-TestPathWithinRoot -Path $repoRoot -Root $resolvedSchemaRuntimeRoot) -or
        (Test-TestPathWithinRoot -Path $resolvedSchemaWorkingDirectory -Root $repoRoot)) {
        throw 'The schema runtime and fixed working directory must resolve beneath the designated external toolchain root and outside the checkout.'
    }
    Assert-TestPathChainWithoutReparsePoint -Path $resolvedSchemaRuntimeRoot -Root $resolvedRoot
    Assert-TestPathChainWithoutReparsePoint -Path $resolvedSchemaWorkingDirectory -Root $resolvedSchemaRuntimeRoot
    if ((Get-PinnedDirectoryTreeSha256 -Root $resolvedSchemaRuntimeRoot) -cne
        [string]$values.SchemaRuntimeContentHash) {
        throw 'Trusted Node runtime full-content SHA-256 does not match its runner pin.'
    }
    $values.SchemaRuntimeRoot = $resolvedSchemaRuntimeRoot
    $values.SchemaWorkingDirectory = $resolvedSchemaWorkingDirectory
    if (-not [IO.Path]::IsPathRooted([string]$values.NodeModulesRoot) -or
        -not (Test-Path -LiteralPath $values.NodeModulesRoot -PathType Container)) {
        throw 'OPERATIONS_BLUEPRINT_NODE_MODULES_ROOT must be an existing absolute directory.'
    }
    if ([string]$values.NodeModulesTreeHash -cnotmatch '^[a-f0-9]{64}$') {
        throw 'OPERATIONS_BLUEPRINT_NODE_MODULES_TREE_SHA256 must be a lowercase 64-character digest.'
    }
    $resolvedNodeModulesRoot = (Resolve-Path -LiteralPath $values.NodeModulesRoot -ErrorAction Stop).ProviderPath
    if (-not (Test-TestPathWithinRoot -Path $resolvedNodeModulesRoot -Root $resolvedSchemaRuntimeRoot) -or
        (Test-TestPathWithinRoot -Path $resolvedNodeModulesRoot -Root $repoRoot)) {
        throw 'The pinned node_modules root must resolve beneath the designated external toolchain root.'
    }
    Assert-TestPathChainWithoutReparsePoint -Path $resolvedNodeModulesRoot -Root $resolvedRoot
    if ((Get-PinnedDirectoryTreeSha256 -Root $resolvedNodeModulesRoot) -cne [string]$values.NodeModulesTreeHash) {
        throw 'Trusted node_modules package-tree SHA-256 does not match its runner pin.'
    }
    $values.NodeModulesRoot = $resolvedNodeModulesRoot
    foreach ($package in @(
        @{ Name = 'Ajv'; RootKey = 'AjvRoot'; TreeHashKey = 'AjvTreeHash' },
        @{ Name = 'AjvFormats'; RootKey = 'AjvFormatsRoot'; TreeHashKey = 'AjvFormatsTreeHash' }
    )) {
        $packageRoot = [string]$values[$package.RootKey]
        $expectedTreeHash = [string]$values[$package.TreeHashKey]
        if (-not [IO.Path]::IsPathRooted($packageRoot) -or
            -not (Test-Path -LiteralPath $packageRoot -PathType Container)) {
            throw "Trusted $($package.Name) package root must be an existing absolute directory."
        }
        if ($expectedTreeHash -cnotmatch '^[a-f0-9]{64}$') {
            throw "Trusted $($package.Name) package-tree SHA-256 must be a lowercase 64-character digest."
        }
        $resolvedPackageRoot = (Resolve-Path -LiteralPath $packageRoot -ErrorAction Stop).ProviderPath
        if (-not (Test-TestPathWithinRoot -Path $resolvedPackageRoot -Root $resolvedNodeModulesRoot) -or
            (Test-TestPathWithinRoot -Path $resolvedPackageRoot -Root $repoRoot)) {
            throw "Trusted $($package.Name) package root must resolve beneath the exact pinned node_modules root."
        }
        Assert-TestPathChainWithoutReparsePoint -Path $resolvedPackageRoot -Root $resolvedRoot
        $actualTreeHash = Get-PinnedDirectoryTreeSha256 -Root $resolvedPackageRoot
        if ($actualTreeHash -cne $expectedTreeHash) {
            throw "Trusted $($package.Name) package-tree SHA-256 does not match its runner pin."
        }
        $values[$package.RootKey] = $resolvedPackageRoot
    }
    if ([string]$values.AjvRoot -ceq [string]$values.AjvFormatsRoot) {
        throw 'Ajv and ajv-formats require distinct exact package roots.'
    }
    foreach ($tool in @(
        @{ Name = 'Node'; PathKey = 'NodePath'; HashKey = 'NodeHash'; RootKey = 'SchemaRuntimeRoot' },
        @{ Name = 'Ajv'; PathKey = 'AjvPath'; HashKey = 'AjvHash'; RootKey = 'AjvRoot' },
        @{ Name = 'AjvFormats'; PathKey = 'AjvFormatsPath'; HashKey = 'AjvFormatsHash'; RootKey = 'AjvFormatsRoot' }
    )) {
        $pathValue = [string]$values[$tool.PathKey]
        $expectedHash = [string]$values[$tool.HashKey]
        if (-not [IO.Path]::IsPathRooted($pathValue)) {
            throw "Trusted $($tool.Name) path must be absolute."
        }
        if ($expectedHash -cnotmatch '^[a-f0-9]{64}$') {
            throw "Trusted $($tool.Name) SHA-256 must be a lowercase 64-character digest."
        }
        if (-not (Test-Path -LiteralPath $pathValue -PathType Leaf)) {
            throw "Trusted $($tool.Name) entry file is unavailable."
        }
        $resolvedPath = (Resolve-Path -LiteralPath $pathValue -ErrorAction Stop).ProviderPath
        if (-not (Test-TestPathWithinRoot -Path $resolvedPath -Root ([string]$values[$tool.RootKey])) -or
            (Test-TestPathWithinRoot -Path $resolvedPath -Root $repoRoot)) {
            throw "Trusted $($tool.Name) entry must resolve beneath its exact designated external root."
        }
        Assert-TestPathChainWithoutReparsePoint -Path $resolvedPath -Root $resolvedRoot
        $actualHash = (Get-FileHash -LiteralPath $resolvedPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -cne $expectedHash) {
            throw "Trusted $($tool.Name) entry SHA-256 does not match its runner pin."
        }
        $values[$tool.PathKey] = $resolvedPath
    }
    Assert-TestProductionWindowsToolchainBoundary -Root $resolvedRoot -CandidatePaths @(
        [string]$values.SchemaRuntimeRoot,
        [string]$values.SchemaWorkingDirectory,
        [string]$values.NodeModulesRoot,
        [string]$values.AjvRoot,
        [string]$values.AjvFormatsRoot,
        [string]$values.NodePath,
        [string]$values.AjvPath,
        [string]$values.AjvFormatsPath
    )
    [pscustomobject]@{
        Root = $resolvedRoot
        ValidationProfile = $ValidationProfile
        SchemaRuntimeRoot = $values.SchemaRuntimeRoot
        SchemaRuntimeContentHash = $values.SchemaRuntimeContentHash
        SchemaRuntimeTreeHash = $values.SchemaRuntimeTreeHash
        SchemaWorkingDirectory = $values.SchemaWorkingDirectory
        NodePath = $values.NodePath
        NodeHash = $values.NodeHash
        NodeModulesRoot = $values.NodeModulesRoot
        NodeModulesTreeHash = $values.NodeModulesTreeHash
        AjvRoot = $values.AjvRoot
        AjvTreeHash = $values.AjvTreeHash
        AjvPath = $values.AjvPath
        AjvHash = $values.AjvHash
        AjvFormatsRoot = $values.AjvFormatsRoot
        AjvFormatsTreeHash = $values.AjvFormatsTreeHash
        AjvFormatsPath = $values.AjvFormatsPath
        AjvFormatsHash = $values.AjvFormatsHash
    }
}

function Assert-TrustedSchemaToolchainExecutionBoundary {
    param([Parameter(Mandatory = $true)]$Toolchain)

    Assert-TestProductionWindowsToolchainBoundary -Root ([string]$Toolchain.Root) -CandidatePaths @(
        [string]$Toolchain.SchemaRuntimeRoot,
        [string]$Toolchain.SchemaWorkingDirectory,
        [string]$Toolchain.NodeModulesRoot,
        [string]$Toolchain.AjvRoot,
        [string]$Toolchain.AjvFormatsRoot,
        [string]$Toolchain.NodePath,
        [string]$Toolchain.AjvPath,
        [string]$Toolchain.AjvFormatsPath
    )
    Assert-TestPathChainWithoutReparsePoint -Path ([string]$Toolchain.Root) -Root ([string]$Toolchain.Root) -IncludeRootAncestors
    foreach ($path in @(
        [string]$Toolchain.Root, [string]$Toolchain.SchemaRuntimeRoot,
        [string]$Toolchain.SchemaWorkingDirectory, [string]$Toolchain.NodeModulesRoot,
        [string]$Toolchain.AjvRoot, [string]$Toolchain.AjvFormatsRoot,
        [string]$Toolchain.NodePath, [string]$Toolchain.AjvPath, [string]$Toolchain.AjvFormatsPath
    )) {
        Assert-TestPathChainWithoutReparsePoint -Path $path -Root ([string]$Toolchain.Root)
    }
    $loaderOverrides = @(Get-ChildItem Env: | Where-Object {
        $_.Name.StartsWith('NODE_', [StringComparison]::OrdinalIgnoreCase) -or
            $_.Name.StartsWith('LD_', [StringComparison]::OrdinalIgnoreCase) -or
            $_.Name.Equals('OPENSSL_CONF', [StringComparison]::OrdinalIgnoreCase) -or
            $_.Name.Equals('OPENSSL_CONF_INCLUDE', [StringComparison]::OrdinalIgnoreCase) -or
            $_.Name.Equals('OPENSSL_MODULES', [StringComparison]::OrdinalIgnoreCase) -or
            $_.Name.Equals('OPENSSL_ENGINES', [StringComparison]::OrdinalIgnoreCase) -or
            $_.Name.StartsWith('DYLD_', [StringComparison]::OrdinalIgnoreCase)
    })
    if ($loaderOverrides.Count -gt 0) {
        throw 'Trusted schema execution rejects every present Node or dynamic-loader override.'
    }
    foreach ($tree in @(
        @{ Path = [string]$Toolchain.SchemaRuntimeRoot; Digest = [string]$Toolchain.SchemaRuntimeContentHash },
        @{ Path = [string]$Toolchain.NodeModulesRoot; Digest = [string]$Toolchain.NodeModulesTreeHash },
        @{ Path = [string]$Toolchain.AjvRoot; Digest = [string]$Toolchain.AjvTreeHash },
        @{ Path = [string]$Toolchain.AjvFormatsRoot; Digest = [string]$Toolchain.AjvFormatsTreeHash }
    )) {
        if ((Get-PinnedDirectoryTreeSha256 -Root $tree.Path) -cne $tree.Digest) {
            throw 'Trusted schema package tree changed before execution.'
        }
    }
    foreach ($entry in @(
        @{ Path = [string]$Toolchain.NodePath; Digest = [string]$Toolchain.NodeHash },
        @{ Path = [string]$Toolchain.AjvPath; Digest = [string]$Toolchain.AjvHash },
        @{ Path = [string]$Toolchain.AjvFormatsPath; Digest = [string]$Toolchain.AjvFormatsHash }
    )) {
        if ((Get-FileHash -LiteralPath $entry.Path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry.Digest) {
            throw 'Trusted schema entry changed before execution.'
        }
    }
}

function ConvertTo-WindowsProcessArgument {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value)

    $builder = New-Object Text.StringBuilder
    [void]$builder.Append('"')
    $backslashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') {
            $backslashes++
            continue
        }
        if ($character -eq '"') {
            if ($backslashes -gt 0) { [void]$builder.Append((('\' * ($backslashes * 2)) -join '')) }
            [void]$builder.Append('\"')
            $backslashes = 0
            continue
        }
        if ($backslashes -gt 0) { [void]$builder.Append((('\' * $backslashes) -join '')) }
        [void]$builder.Append($character)
        $backslashes = 0
    }
    if ($backslashes -gt 0) { [void]$builder.Append((('\' * ($backslashes * 2)) -join '')) }
    [void]$builder.Append('"')
    $builder.ToString()
}

function Invoke-OperationsRecordSchemaValidation {
    param(
        [Parameter(Mandatory = $true)][object[]]$Records,
        [ValidateSet('TEST','PRODUCTION')][string]$ValidationProfile = 'PRODUCTION'
    )
    $ValidationProfile = ([string]$ValidationProfile).ToUpperInvariant()
    $toolchain = Get-TrustedSchemaToolchain -ValidationProfile $ValidationProfile
    $schemaPath = Join-Path $here 'operations-record-contracts.schema.json'
    $temp = New-TemporaryBlueprintDirectory
    try {
        $instancePath = Join-Path $temp 'operations-records.json'
        ConvertTo-Json -InputObject @($Records) -Depth 100 | Set-Content -LiteralPath $instancePath -Encoding UTF8
        $script = @'
const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
try {
  const exact = value => fs.realpathSync.native(path.resolve(value));
  const sameWindowsPath = (left, right) => exact(left).toLowerCase() === exact(right).toLowerCase();
  const expectedNodePath = process.argv[1];
  const expectedWorkingDirectory = process.argv[2];
  const pinnedAjvEntry = exact(process.argv[3]);
  const pinnedFormatsEntry = exact(process.argv[4]);
  const pinnedAjvRoot = exact(process.argv[5]);
  const pinnedFormatsRoot = exact(process.argv[6]);
  if (!sameWindowsPath(process.execPath, expectedNodePath) ||
      !sameWindowsPath(process.cwd(), expectedWorkingDirectory)) {
    throw new Error('Node executable or working-directory identity does not match the trusted runner binding.');
  }
  const dependencyRequire = createRequire(path.join(pinnedFormatsRoot, 'package.json'));
  const resolvedAjvEntry = exact(dependencyRequire.resolve('ajv'));
  const resolvedFormatsEntry = exact(dependencyRequire.resolve('ajv-formats'));
  if (!sameWindowsPath(resolvedAjvEntry, path.join(pinnedAjvRoot, 'dist', 'ajv.js')) ||
      !sameWindowsPath(resolvedFormatsEntry, pinnedFormatsEntry) ||
      !sameWindowsPath(path.dirname(path.dirname(resolvedAjvEntry)), pinnedAjvRoot) ||
      !sameWindowsPath(path.dirname(path.dirname(resolvedFormatsEntry)), pinnedFormatsRoot)) {
    throw new Error('Pinned package dependency resolution does not match the exact trusted entries.');
  }
  const Ajv2020 = require(pinnedAjvEntry).default;
  const addFormats = require(resolvedFormatsEntry);
  const schema = readJson(process.argv[7]);
  const instance = readJson(process.argv[8]);
  const ajv = new Ajv2020({ strict: true, allErrors: true, validateFormats: true });
  addFormats(ajv);
  const validate = ajv.compile(schema);
  const valid = validate(instance);
  process.stdout.write(JSON.stringify({ compiled: true, valid, errors: validate.errors || [] }));
} catch (error) {
  process.stdout.write(JSON.stringify({ compiled: false, valid: false, errors: [{ message: String(error && error.stack || error) }] }));
}
'@
        $parentWorkingDirectory = (Get-Location).ProviderPath
        $parentPath = [Environment]::GetEnvironmentVariable('PATH')
        $runtimeGuard = $null
        $process = $null
        try {
            Assert-TrustedSchemaToolchainExecutionBoundary -Toolchain $toolchain
            if ($ValidationProfile -ceq 'PRODUCTION') {
                if (-not (Initialize-BlueprintWindowsFileSystemInterop)) {
                    throw 'Production schema validation cannot initialize the native runtime-tree guard.'
                }
                $runtimeGuard = [OperationsBlueprint.NativeFileSystemSecurity]::OpenRuntimeTreeGuard(
                    [string]$toolchain.SchemaRuntimeRoot
                )
                if ($null -eq $runtimeGuard -or
                    [string]$runtimeGuard.Digest -cne [string]$toolchain.SchemaRuntimeTreeHash) {
                    throw 'Production schema runtime is not an immutable, digest-matched guarded namespace.'
                }
            }

            $arguments = @(
                '-e', $script,
                [string]$toolchain.NodePath,
                [string]$toolchain.SchemaWorkingDirectory,
                [string]$toolchain.AjvPath,
                [string]$toolchain.AjvFormatsPath,
                [string]$toolchain.AjvRoot,
                [string]$toolchain.AjvFormatsRoot,
                [string]$schemaPath,
                [string]$instancePath
            )
            $startInfo = New-Object Diagnostics.ProcessStartInfo
            $startInfo.FileName = [string]$toolchain.NodePath
            $startInfo.Arguments = (@($arguments | ForEach-Object {
                ConvertTo-WindowsProcessArgument -Value ([string]$_)
            }) -join ' ')
            $startInfo.WorkingDirectory = [string]$toolchain.SchemaWorkingDirectory
            $startInfo.UseShellExecute = $false
            $startInfo.CreateNoWindow = $true
            $startInfo.RedirectStandardOutput = $true
            $startInfo.RedirectStandardError = $true
            foreach ($name in @($startInfo.EnvironmentVariables.Keys)) {
                if ($name.StartsWith('NODE_', [StringComparison]::OrdinalIgnoreCase) -or
                    $name.StartsWith('LD_', [StringComparison]::OrdinalIgnoreCase) -or
                    $name.Equals('OPENSSL_CONF', [StringComparison]::OrdinalIgnoreCase) -or
                    $name.Equals('OPENSSL_CONF_INCLUDE', [StringComparison]::OrdinalIgnoreCase) -or
                    $name.Equals('OPENSSL_MODULES', [StringComparison]::OrdinalIgnoreCase) -or
                    $name.Equals('OPENSSL_ENGINES', [StringComparison]::OrdinalIgnoreCase) -or
                    $name.StartsWith('DYLD_', [StringComparison]::OrdinalIgnoreCase)) {
                    $startInfo.EnvironmentVariables.Remove($name)
                }
            }
            $closedPath = @(
                [IO.Path]::GetDirectoryName([string]$toolchain.NodePath),
                [Environment]::SystemDirectory
            ) -join [IO.Path]::PathSeparator
            $startInfo.EnvironmentVariables['PATH'] = $closedPath
            foreach ($profileName in @('HOME','USERPROFILE','APPDATA','LOCALAPPDATA')) {
                $startInfo.EnvironmentVariables[$profileName] = [string]$toolchain.SchemaWorkingDirectory
            }

            $process = New-Object Diagnostics.Process
            $process.StartInfo = $startInfo
            if (-not $process.Start()) { throw 'Trusted Node schema subprocess did not start.' }
            $stdoutTask = $process.StandardOutput.ReadToEndAsync()
            $stderrTask = $process.StandardError.ReadToEndAsync()
            if (-not $process.WaitForExit(120000)) {
                try { $process.Kill() } catch { }
                throw 'Trusted Node schema subprocess exceeded its bounded execution time.'
            }
            $process.WaitForExit()
            $stdout = $stdoutTask.GetAwaiter().GetResult()
            $stderr = $stderrTask.GetAwaiter().GetResult()
            $exitCode = $process.ExitCode

            if ($ValidationProfile -ceq 'PRODUCTION' -and
                ($null -eq $runtimeGuard -or
                    -not $runtimeGuard.Validate([string]$toolchain.SchemaRuntimeTreeHash))) {
                throw 'Production schema runtime changed while the guarded child was executing.'
            }
            Assert-TrustedSchemaToolchainExecutionBoundary -Toolchain $toolchain
            if ((Get-Location).ProviderPath -cne $parentWorkingDirectory -or
                [Environment]::GetEnvironmentVariable('PATH') -cne $parentPath) {
                throw 'Schema validation altered its parent working directory or PATH.'
            }
            if ($exitCode -ne 0 -or -not [string]::IsNullOrEmpty([string]$stderr) -or
                [string]::IsNullOrEmpty([string]$stdout) -or $stdout.Length -gt 1048576 -or
                $stdout -match '[\r\n]' -or -not $stdout.StartsWith('{') -or -not $stdout.EndsWith('}')) {
                throw 'Node/Ajv schema validation did not return exactly one bounded structured result.'
            }
            $parsed = ConvertFrom-Json -InputObject $stdout
            $resultProperties = @($parsed.PSObject.Properties.Name)
            if ($resultProperties.Count -ne 3 -or
                $resultProperties -cnotcontains 'compiled' -or
                $resultProperties -cnotcontains 'valid' -or
                $resultProperties -cnotcontains 'errors') {
                throw 'Node/Ajv schema validation returned an unexpected result contract.'
            }
            [pscustomobject][ordered]@{
                validationProfile = $ValidationProfile
                authoritative = $false
                promotionEffect = 'NONE'
                state = if ($ValidationProfile -ceq 'TEST') {
                    'TEST_SCHEMA_VALIDATED_NON_PROMOTABLE'
                }
                else { 'PRODUCTION_SCHEMA_VALIDATED_STRUCTURAL_ONLY' }
                compiled = [bool]$parsed.compiled
                valid = [bool]$parsed.valid
                errors = @($parsed.errors)
            }
        }
        finally {
            if ($null -ne $process) { $process.Dispose() }
            if ($null -ne $runtimeGuard) { $runtimeGuard.Dispose() }
        }
    }
    finally { Remove-Item -LiteralPath $temp -Recurse -Force }
}

Describe 'Operations blueprint v1.0.0' {
    $registryPath = Join-Path $here 'tool-registry.json'
    $matrixPath = Join-Path $here 'control-matrix.json'
    $chainPath = Join-Path $here 'leadership-claim-chain.json'

    Context 'Tool registry' {
        It 'validates the public binding blueprint without authorizing it' {
            $result = Test-ToolRegistry (Get-CheckedRegistry) -EvaluationTime $evaluationTime
            $result.Valid | Should Be $true
            $result.Allowed | Should Be $false
            $result.State | Should Be 'VALIDATED_BINDING_BLUEPRINT'
        }

        It 'pins the full 53-tool inventory and classification map' {
            $registry = Get-CheckedRegistry
            $required = @('git','github-review','enterprise-ci','terraform','atmos','msgraph-terraform-provider','entra-workload-identity','azure-key-vault','terraform-state','evidence-store','intune','microsoft-graph-write','microsoft-graph-readback','azure-resource-manager-readback','microsoft-graph-directory-readback','windows-autopilot','windows-update-service','systrack','servicenow','fabric-onelake','power-bi','ansible','collector','agent-classification','hp-cmsl','hp-hpia','windows-native-telemetry','windows-powershell','powershell-core','pester','nodejs','ajv','ajv-formats','semantic-validator','test-harness-catalog','survey-platform','procurement-system','vendor-change-feed','policy-as-code','iac-quality-security','artifact-signing','decision-packet-renderer','alert-channel','claude-code-review','group-policy','configuration-manager','defender-security-settings-management','oem-endpoint-management','emergency-endpoint-automation','conditional-access','organization-security-stack','authorization-consumption-ledger','authorization-consumption-ledger-readback')
            @($registry.bindings).Count | Should Be 53
            @($registry.endpointWriteOwnership.toolClassifications.PSObject.Properties).Count | Should Be 53
            foreach ($id in $required) {
                (@($registry.bindings.toolId) -ccontains $id) | Should Be $true
                (@($registry.endpointWriteOwnership.toolClassifications.PSObject.Properties.Name) -ccontains $id) | Should Be $true
            }
        }

        It 'rejects a missing frozen tool' {
            $registry = Get-CheckedRegistry
            $registry.bindings = @($registry.bindings | Where-Object toolId -ne 'organization-security-stack')
            (@((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes) -contains 'REQUIRED_TOOL_MISSING') | Should Be $true
        }

        It 'rejects an alternate production Windows writer' {
            $registry = Get-CheckedRegistry
            $alternate = Copy-TestObject $registry.bindings[0]
            $alternate.toolId = 'alternate-windows-writer'
            $alternate.writeScope = 'production Windows endpoint and Intune settings'
            $registry.bindings += $alternate
            $registry.endpointWriteOwnership.toolClassifications | Add-Member 'alternate-windows-writer' 'INTUNE_ENFORCEMENT'
            $codes = @((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes)
            ($codes -contains 'UNAPPROVED_TOOL_BINDING') | Should Be $true
            ($codes -contains 'UNAPPROVED_TOOL_WRITE_CLASSIFICATION') | Should Be $true
            ($codes -contains 'INTUNE_WRITE_CLASSIFICATION_NOT_UNIQUE') | Should Be $true
        }

        It 'rejects duplicate tool identifiers' {
            $registry = Get-CheckedRegistry
            $registry.bindings += Copy-TestObject $registry.bindings[0]
            (@((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes) -contains 'DUPLICATE_TOOL_ID') | Should Be $true
        }

        It 'rejects verdict authority and a second desired-state authority' {
            $registry = Get-CheckedRegistry
            ($registry.bindings | Where-Object toolId -eq 'microsoft-graph-write').authorityClasses += 'verdict-authority'
            ($registry.bindings | Where-Object toolId -eq 'terraform').authorityClasses += 'desired-state'
            $codes = @((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes)
            ($codes -contains 'FORBIDDEN_TOOL_AUTHORITY') | Should Be $true
            ($codes -contains 'GIT_NOT_SOLE_DESIRED_STATE_AUTHORITY') | Should Be $true
        }

        It 'rejects Graph writes without independent readback' {
            $registry = Get-CheckedRegistry
            ($registry.bindings | Where-Object toolId -eq 'microsoft-graph-write').readback.viaToolRef = ''
            (@((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes) -contains 'GRAPH_READBACK_REQUIRED') | Should Be $true
        }

        It 'rejects a Graph reader with write scope or shared identity' {
            $registry = Get-CheckedRegistry
            $writer = $registry.bindings | Where-Object toolId -eq 'microsoft-graph-write'
            $reader = $registry.bindings | Where-Object toolId -eq 'microsoft-graph-readback'
            $reader.writeScope = $writer.writeScope
            $reader.identityBoundary = $writer.identityBoundary
            (@((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes) -contains 'GRAPH_READBACK_IDENTITY_NOT_INDEPENDENT') | Should Be $true
        }

        It 'rejects writable directory and Azure resource readback identities' -TestCases @(
            @{ ToolId = 'microsoft-graph-directory-readback'; Code = 'DIRECTORY_READBACK_IDENTITY_NOT_INDEPENDENT' },
            @{ ToolId = 'azure-resource-manager-readback'; Code = 'ARM_READBACK_IDENTITY_NOT_INDEPENDENT' }
        ) {
            param($ToolId, $Code)
            $registry = Get-CheckedRegistry
            ($registry.bindings | Where-Object toolId -eq $ToolId).writeScope = 'production writes'
            (@((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'requires Terraform readback from all three resource planes' {
            $registry = Get-CheckedRegistry
            ($registry.bindings | Where-Object toolId -eq 'terraform').readback.viaToolRefs = @('microsoft-graph-readback')
            (@((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes) -contains 'TERRAFORM_RESOURCE_PLANE_READBACK_INCOMPLETE') | Should Be $true
        }

        It 'enforces exact resource-plane observers for identity, Key Vault, and Terraform state' -TestCases @(
            @{ ToolId = 'entra-workload-identity'; ReplacementRefs = @('microsoft-graph-directory-readback') },
            @{ ToolId = 'azure-key-vault'; ReplacementRefs = @('microsoft-graph-readback') },
            @{ ToolId = 'terraform-state'; ReplacementRefs = @('microsoft-graph-directory-readback') }
        ) {
            param($ToolId, $ReplacementRefs)
            $registry = Get-CheckedRegistry
            ($registry.bindings | Where-Object toolId -eq $ToolId).readback.viaToolRefs = @($ReplacementRefs)
            $result = Test-ToolRegistry $registry -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'PER_BINDING_READBACK_PLANE_INVALID') | Should Be $true
        }

        It 'rejects CI, Terraform, and Intune readback substitutions' -TestCases @(
            @{ ToolId = 'enterprise-ci'; Field = 'viaToolRef'; Value = 'azure-resource-manager-readback' },
            @{ ToolId = 'terraform'; Field = 'viaToolRefs'; Value = @('microsoft-graph-readback', 'microsoft-graph-directory-readback', 'microsoft-graph-directory-readback') },
            @{ ToolId = 'intune'; Field = 'viaToolRef'; Value = 'azure-resource-manager-readback' }
        ) {
            param($ToolId, $Field, $Value)
            $registry = Get-CheckedRegistry
            $binding = $registry.bindings | Where-Object toolId -eq $ToolId
            $binding.readback.$Field = $Value
            $result = Test-ToolRegistry $registry -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'BINDING_POLICY_DRIFT') | Should Be $true
        }

        It 'rejects a populated public Intune transport ownership inventory' {
            $registry = Get-CheckedRegistry
            $registry.intuneTransportOwnership.objectTypeOwnership = @([pscustomobject]@{ objectType = 'synthetic'; transport = 'microsoft-graph-write' })
            (@((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes) -contains 'PUBLIC_TRANSPORT_OWNERSHIP_NOT_HELD') | Should Be $true
        }

        It 'rejects Ansible as a production Intune writer' {
            $registry = Get-CheckedRegistry
            ($registry.bindings | Where-Object toolId -eq 'ansible').writeScope = 'production-intune-settings'
            (@((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes) -contains 'ANSIBLE_PRODUCTION_WRITE_FORBIDDEN') | Should Be $true
        }

        It 'rejects any frozen Terraform write-scope mutation' {
            $registry = Get-CheckedRegistry
            ($registry.bindings | Where-Object toolId -eq 'terraform').writeScope = 'all Intune objects without bounds'
            (@((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes) -contains 'BINDING_POLICY_DRIFT') | Should Be $true
        }

        It 'binds tool version, failure, replacement, data-class, and replaceability policy into the frozen registry digest' -TestCases @(
            @{ Field = 'versionPolicy'; Value = 'floating latest version' },
            @{ Field = 'failureMode'; Value = 'continue on tool failure' },
            @{ Field = 'replacementRule'; Value = 'silent replacement allowed' },
            @{ Field = 'dataClasses'; Value = @('unbounded private data') },
            @{ Field = 'replaceable'; Value = $false }
        ) {
            param($Field, $Value)
            $registry = Get-CheckedRegistry
            $binding = $registry.bindings | Where-Object toolId -eq 'terraform'
            $binding.$Field = $Value
            (@((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes) -contains 'BINDING_POLICY_DRIFT') | Should Be $true
        }

        It 'rejects a forged ACTIVE public registry' {
            $registry = Get-CheckedRegistry
            $registry.activation.state = 'ACTIVE'
            (@((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes) -contains 'PUBLIC_BLUEPRINT_CANNOT_ACTIVATE') | Should Be $true
        }

        It 'rejects a competing endpoint authority reclassified as Intune enforcement' {
            $registry = Get-CheckedRegistry
            $registry.endpointWriteOwnership.toolClassifications.'group-policy' = 'INTUNE_ENFORCEMENT'
            $codes = @((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes)
            ($codes -contains 'TOOL_WRITE_CLASSIFICATION_MISMATCH') | Should Be $true
            ($codes -contains 'INTUNE_WRITE_CLASSIFICATION_NOT_UNIQUE') | Should Be $true
        }

        It 'rejects free-text tool owner roles' {
            $registry = Get-CheckedRegistry
            ($registry.bindings | Where-Object toolId -eq 'terraform').ownerRole = 'Terraform team'
            (@((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes) -contains 'INVALID_TOOL_OWNER_ROLE') | Should Be $true
        }

        It 'rejects unexpected registry, binding, and readback fields' -TestCases @(
            @{ Target = 'registry' }, @{ Target = 'binding' }, @{ Target = 'readback' }
        ) {
            param($Target)
            $registry = Get-CheckedRegistry
            if ($Target -eq 'registry') { $registry | Add-Member -NotePropertyName inventedAuthority -NotePropertyValue 'ACTIVE' }
            elseif ($Target -eq 'binding') { $registry.bindings[0] | Add-Member -NotePropertyName hiddenWriteScope -NotePropertyValue 'all devices' }
            else { $registry.bindings[0].readback | Add-Member -NotePropertyName trustsWriter -NotePropertyValue $true }
            (@((Test-ToolRegistry $registry -EvaluationTime $evaluationTime).ReasonCodes) -contains 'UNEXPECTED_CONTRACT_FIELD') | Should Be $true
        }
    }

    Context 'Control matrix' {
        It 'validates the matrix without granting authority' {
            $result = Test-ControlMatrix (Get-CheckedMatrix) (Get-CheckedRegistry) -ControlRoot $here
            $result.Valid | Should Be $true
            $result.Allowed | Should Be $false
            $result.State | Should Be 'VALIDATED_CONTROL_MATRIX'
        }

        It 'rejects a mutation to the frozen control policy digest' {
            $matrix = Get-CheckedMatrix
            $matrix.controls[0].objective = [string]$matrix.controls[0].objective + ' mutated'
            (@((Test-ControlMatrix $matrix (Get-CheckedRegistry) -ControlRoot $here).ReasonCodes) -contains 'CONTROL_POLICY_DRIFT') | Should Be $true
        }

        It 'rejects dangling and duplicate references' {
            $matrix = Get-CheckedMatrix
            $matrix.controls[0].toolRefs += 'missing-tool'
            $matrix.controls += Copy-TestObject $matrix.controls[0]
            $codes = @((Test-ControlMatrix $matrix (Get-CheckedRegistry) -ControlRoot $here).ReasonCodes)
            ($codes -contains 'DANGLING_TOOL_REF') | Should Be $true
            ($codes -contains 'DUPLICATE_CONTROL_ID') | Should Be $true
        }

        It 'rejects removal of a required control' {
            $matrix = Get-CheckedMatrix
            $matrix.controls = @($matrix.controls | Where-Object controlId -ne 'PRIV-001')
            (@((Test-ControlMatrix $matrix (Get-CheckedRegistry) -ControlRoot $here).ReasonCodes) -contains 'REQUIRED_CONTROL_MISSING') | Should Be $true
        }

        It 'keeps public role-to-principal bindings on HOLD' {
            $matrix = Get-CheckedMatrix
            $matrix.roleCatalog.privatePrincipalBindingRef = 'private://identities/forged-binding'
            (@((Test-ControlMatrix $matrix (Get-CheckedRegistry) -ControlRoot $here).ReasonCodes) -contains 'PUBLIC_ROLE_BINDING_NOT_HELD') | Should Be $true
        }

        It 'rejects control roles absent from the canonical catalog' {
            $matrix = Get-CheckedMatrix
            $matrix.controls[0].ownerRole = 'ROLE_INVENTED_OWNER'
            (@((Test-ControlMatrix $matrix (Get-CheckedRegistry) -ControlRoot $here).ReasonCodes) -contains 'UNRESOLVED_CANONICAL_ROLE') | Should Be $true
        }

        It 'rejects nonblocking top-level and nested failure states' {
            $matrix = Get-CheckedMatrix
            $matrix.controls[0].failureState = 'PASS'
            $matrix.controls[0].failClosed.missing = 'PASS'
            (@((Test-ControlMatrix $matrix (Get-CheckedRegistry) -ControlRoot $here).ReasonCodes) -contains 'NON_BLOCKING_FAILURE_STATE') | Should Be $true
        }

        It 'rejects relabeling any declared Intune write control' -TestCases @(
            @{ ControlId = 'IAC-002' }, @{ ControlId = 'INTUNE-004' }
        ) {
            param($ControlId)
            $matrix = Get-CheckedMatrix
            ($matrix.controls | Where-Object controlId -eq $ControlId).writesIntune = $false
            (@((Test-ControlMatrix $matrix (Get-CheckedRegistry) -ControlRoot $here).ReasonCodes) -contains 'INTUNE_WRITE_CLASSIFICATION_MISMATCH') | Should Be $true
        }

        It 'requires readback and rollback for each Intune write' {
            $matrix = Get-CheckedMatrix
            $control = $matrix.controls | Where-Object controlId -eq 'INTUNE-004'
            $control.readbackRef = ''
            $control.rollbackRef = ''
            $codes = @((Test-ControlMatrix $matrix (Get-CheckedRegistry) -ControlRoot $here).ReasonCodes)
            ($codes -contains 'INTUNE_READBACK_REQUIRED') | Should Be $true
            ($codes -contains 'ROLLBACK_REQUIRED') | Should Be $true
        }

        It 'requires the full reviewed multi-plane IaC apply path' {
            $matrix = Get-CheckedMatrix
            $control = $matrix.controls | Where-Object controlId -eq 'IAC-002'
            $control.toolRefs = @($control.toolRefs | Where-Object { $_ -ne 'azure-resource-manager-readback' })
            (@((Test-ControlMatrix $matrix (Get-CheckedRegistry) -ControlRoot $here).ReasonCodes) -contains 'IAC_APPLY_PATH_INVALID') | Should Be $true
        }

        It 'rejects unresolved Markdown anchors and JSON pointers' {
            $matrix = Get-CheckedMatrix
            ($matrix.controls | Where-Object controlId -eq 'DATA-001').readbackRef = 'GOVERNANCE_AND_IAC_OPERATING_MODEL.md#not-real'
            ($matrix.controls | Where-Object controlId -eq 'GOV-002').readbackRef = 'tool-registry.json#/not/real'
            (@((Test-ControlMatrix $matrix (Get-CheckedRegistry) -ControlRoot $here).ReasonCodes) -contains 'UNRESOLVED_CONTROL_REFERENCE') | Should Be $true
        }

        It 'rejects a canonical-looking tool owner role absent from the role catalog' {
            $registry = Get-CheckedRegistry
            ($registry.bindings | Where-Object toolId -eq 'terraform').ownerRole = 'ROLE_INVENTED_TOOL_OWNER'
            (@((Test-ControlMatrix (Get-CheckedMatrix) $registry -ControlRoot $here).ReasonCodes) -contains 'UNRESOLVED_TOOL_OWNER_ROLE') | Should Be $true
        }

        It 'rejects unexpected matrix, role, control, and fail-closed fields' -TestCases @(
            @{ Target = 'matrix' }, @{ Target = 'role' }, @{ Target = 'control' }, @{ Target = 'failClosed' }
        ) {
            param($Target)
            $matrix = Get-CheckedMatrix
            if ($Target -eq 'matrix') { $matrix | Add-Member -NotePropertyName shadowControls -NotePropertyValue @() }
            elseif ($Target -eq 'role') { $matrix.roleCatalog.roles[0] | Add-Member -NotePropertyName principalRef -NotePropertyValue 'private://forged' }
            elseif ($Target -eq 'control') { $matrix.controls[0] | Add-Member -NotePropertyName allowOnFailure -NotePropertyValue $true }
            else { $matrix.controls[0].failClosed | Add-Member -NotePropertyName timeout -NotePropertyValue 'PASS' }
            (@((Test-ControlMatrix $matrix (Get-CheckedRegistry) -ControlRoot $here).ReasonCodes) -contains 'UNEXPECTED_CONTRACT_FIELD') | Should Be $true
        }
    }

    Context 'Private diagnostic redaction' {
        It 'renders only the stable reason code and never echoes private diagnostic inputs' {
            $privateA = 'private://tenants/contoso/rings/pilot-a'
            $privateB = 'private://tenants/contoso/rings/pilot-b'
            $urn = 'urn:tenant:contoso:production'
            $principal = '11111111-2222-4333-8444-555555555555'
            $errors = New-Object System.Collections.ArrayList
            Add-BlueprintError -Errors $errors -Code 'SYNTHETIC_PRIVATE_DIAGNOSTIC' -Message "A=$privateA repeated=$privateA B=$privateB tenant=$urn principal=$principal"

            $message = [string]$errors[0].message
            $message | Should Not Match ([regex]::Escape($privateA))
            $message | Should Not Match ([regex]::Escape($privateB))
            $message | Should Not Match ([regex]::Escape($urn))
            $message | Should Not Match ([regex]::Escape($principal))
            $message | Should Be 'Validation failed: SYNTHETIC_PRIVATE_DIAGNOSTIC.'
        }

        It 'bounds hostile diagnostic text to one safe line while retaining the stable reason code' -TestCases @(
            @{ Name = 'line-feed'; Payload = "before`nafter" },
            @{ Name = 'carriage-return'; Payload = "before`rafter" },
            @{ Name = 'ansi-escape'; Payload = ("before" + [char]0x1b + '[31mafter') },
            @{ Name = 'bidi-override'; Payload = ("before" + [char]0x202e + 'after') },
            @{ Name = 'zero-width-format'; Payload = ("before" + [char]0x200b + 'after') },
            @{ Name = 'line-separator'; Payload = ("before" + [char]0x2028 + 'after') },
            @{ Name = 'paragraph-separator'; Payload = ("before" + [char]0x2029 + 'after') },
            @{ Name = 'private-use'; Payload = ("before" + [char]0xe000 + 'after') },
            @{ Name = 'unpaired-high-surrogate'; Payload = ("before" + [char]0xd800 + 'after') },
            @{ Name = 'overlong'; Payload = ('x' * 10000) }
        ) {
            param($Name, $Payload)
            $privateRef = 'private://diagnostics/hostile-private-identifier'
            $principal = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
            $errors = New-Object System.Collections.ArrayList
            Add-BlueprintError -Errors $errors -Code 'SYNTHETIC_DIAGNOSTIC_INJECTION' `
                -Message "$Name payload=$Payload private=$privateRef principal=$principal"

            $errors.Count | Should Be 1
            [string]$errors[0].code | Should Be 'SYNTHETIC_DIAGNOSTIC_INJECTION'
            $message = [string]$errors[0].message
            $message.Length -le 512 | Should Be $true
            $message.Contains("`r") | Should Be $false
            $message.Contains("`n") | Should Be $false
            $message.Contains($privateRef) | Should Be $false
            $message.Contains($principal) | Should Be $false
            $forbiddenCategories = @(
                [Globalization.UnicodeCategory]::Control,
                [Globalization.UnicodeCategory]::Format,
                [Globalization.UnicodeCategory]::LineSeparator,
                [Globalization.UnicodeCategory]::ParagraphSeparator,
                [Globalization.UnicodeCategory]::PrivateUse,
                [Globalization.UnicodeCategory]::Surrogate
            )
            $unsafeCategories = @(
                for ($index = 0; $index -lt $message.Length; $index++) {
                    $category = [Globalization.CharUnicodeInfo]::GetUnicodeCategory($message, $index)
                    if ($forbiddenCategories -contains $category) { $category }
                }
            )
            $unsafeCategories.Count | Should Be 0
        }

        It 'returns a fixed directory error without exposing the requested filesystem path' {
            $missing = Join-Path ([IO.Path]::GetTempPath()) ('private-directory-' + [Guid]::NewGuid().ToString('N'))
            $result = Test-BlueprintFileManifest -BlueprintRoot $missing
            $errorRecord = @($result.Errors | Where-Object code -ceq 'BLUEPRINT_DIRECTORY_UNREADABLE')[0]
            [string]$errorRecord.message | Should Be 'Validation failed: BLUEPRINT_DIRECTORY_UNREADABLE.'
            [string]$errorRecord.message | Should Not Match ([regex]::Escape($missing))
        }

        It 'returns a fixed JSON error naming only the contract file' {
            $temp = New-BlueprintManifestTestDirectory
            try {
                Set-Content -LiteralPath (Join-Path $temp 'tool-registry.json') -Value '{ private://exception/raw-path-sentinel' -Encoding UTF8
                $result = Test-OperationsBlueprintBundle -BlueprintRoot $temp
                $errorRecord = @($result.Errors | Where-Object code -ceq 'BLUEPRINT_FILE_INVALID')[0]
                [string]$errorRecord.message | Should Be 'Validation failed: BLUEPRINT_FILE_INVALID.'
                [string]$errorRecord.message | Should Not Match ([regex]::Escape($temp))
                [string]$errorRecord.message | Should Not Match 'private://exception/raw-path-sentinel'
            }
            finally { Remove-Item -LiteralPath $temp -Recurse -Force }
        }
    }

    Context 'Canonical cross-host serialization' {
        It 'round-trips paired Unicode and special characters to one frozen canonical digest' {
            $value = [pscustomobject][ordered]@{
                apostrophe = "O'Brien"
                controls = "line`nquote`"slash\\"
                emoji = [char]::ConvertFromUtf32(0x1F600)
                separators = ([string][char]0x2028) + ([string][char]0x2029)
            }
            $canonicalText = ConvertTo-DeterministicJsonText (ConvertTo-CanonicalJsonValue $value)
            $expectedText = '{"apostrophe":"O''Brien","controls":"line\nquote\"slash\\\\","emoji":"' +
                $value.emoji + '","separators":"\u2028\u2029"}'
            $canonicalText | Should Be $expectedText
            (Get-CanonicalPayloadDigest $value) | Should Be 'sha256:60a01d4f45bfed8ce6192c82875630d2780f41a1cc4ca9f1b2b05bdfbbcabab8'
        }

        It 'rejects unpaired UTF-16 surrogate code units' -TestCases @(
            @{ Value = [string][char]0xD800 },
            @{ Value = [string][char]0xDC00 }
        ) {
            param($Value)
            $payload = [pscustomobject]@{ value = $Value }
            Test-ScriptBlockThrows { ConvertTo-DeterministicJsonText (ConvertTo-CanonicalJsonValue $payload) } | Should Be $true
            (Get-CanonicalPayloadDigest $payload) | Should Be 'INVALID_CANONICAL_JSON_RUNTIME_DOMAIN'
        }

        It 'rejects every non-finite numeric value' -TestCases @(
            @{ Value = [double]::NaN },
            @{ Value = [double]::PositiveInfinity },
            @{ Value = [double]::NegativeInfinity }
        ) {
            param($Value)
            $payload = [pscustomobject]@{ value = $Value }
            Test-ScriptBlockThrows { ConvertTo-DeterministicJsonText (ConvertTo-CanonicalJsonValue $payload) } | Should Be $true
            (Get-CanonicalPayloadDigest $payload) | Should Be 'INVALID_CANONICAL_JSON_RUNTIME_DOMAIN'
        }

        It 'rejects runtime objects instead of hashing their string representation' -TestCases @(
            @{ Value = [DateTime]::Parse('2026-08-27T12:30:00Z') },
            @{ Value = [Guid]::Parse('11111111-2222-4333-8444-555555555555') },
            @{ Value = [Text.StringBuilder]::new('literal-collision') }
        ) {
            param($Value)
            $payload = [pscustomobject]@{ value = $Value }
            Test-ScriptBlockThrows { ConvertTo-DeterministicJsonText (ConvertTo-CanonicalJsonValue $payload) } | Should Be $true
            (Get-CanonicalPayloadDigest $payload) | Should Be 'INVALID_CANONICAL_JSON_RUNTIME_DOMAIN'
        }

        It 'rejects non-string dictionary keys before integer and string keys can collide' {
            $dictionary = [ordered]@{}
            $dictionary.Add(1, 'integer-key')
            $dictionary.Add('1', 'string-key')
            Test-ScriptBlockThrows { ConvertTo-CanonicalJsonValue $dictionary } | Should Be $true
            (Get-CanonicalPayloadDigest $dictionary) | Should Be 'INVALID_CANONICAL_JSON_RUNTIME_DOMAIN'
        }

        It 'rejects ordinal-case-colliding dictionary keys at the top level and recursively' -TestCases @(
            @{ Nested = $false }, @{ Nested = $true }
        ) {
            param($Nested)
            $collision = [System.Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
            $collision.Add('A', 1)
            $collision.Add('a', 2)
            $value = if ($Nested) { [pscustomobject]@{ safe = $collision } } else { $collision }
            Test-ScriptBlockThrows { ConvertTo-CanonicalJsonValue $value } | Should Be $true
            (Get-CanonicalPayloadDigest $value) | Should Be 'INVALID_CANONICAL_JSON_RUNTIME_DOMAIN'
        }

        It 'matches independent hard-coded numeric text and SHA-256 vectors under non-invariant cultures' {
            $vectors = @(
                @{ Name = 'Int32 minimum'; Value = [int]::MinValue; Text = '-2147483648'; Digest = 'sha256:56bb3b3a6aa1747def7c225256374c5e73f2fc46555adc47ea16e2d782159387' },
                @{ Name = 'Int32 maximum'; Value = [int]::MaxValue; Text = '2147483647'; Digest = 'sha256:972dcafa6fb4c2c88bce752fca4ab18c6bd88599330a4ad9813915b05bfbe76d' },
                @{ Name = 'Int64 minimum'; Value = [long]::MinValue; Text = '-9223372036854775808'; Digest = 'sha256:85386477f3af47e4a0b308ee3b3a688df16e8b2228105dd7d4dcd42a9807cb78' },
                @{ Name = 'Int64 maximum'; Value = [long]::MaxValue; Text = '9223372036854775807'; Digest = 'sha256:b34a1c30a715f6bf8b7243afa7fab883ce3612b7231716bdcbbdc1982e1aed29' },
                @{ Name = 'Decimal whole'; Value = [decimal]'42.0000'; Text = '42.0'; Digest = 'sha256:53519e43db90bd08ff4459fd23fc944324ffb7d8f542ccc0b44257afea2ef525' },
                @{ Name = 'Decimal fraction'; Value = [decimal]'1.25'; Text = '1.25'; Digest = 'sha256:004a9e0878ff83e6b91f50d50dad439d2065c6cbb0d20f1f328b2fd75e085d6a' },
                @{ Name = 'Decimal trailing-zero normalization'; Value = [decimal]'1.2500'; Text = '1.25'; Digest = 'sha256:004a9e0878ff83e6b91f50d50dad439d2065c6cbb0d20f1f328b2fd75e085d6a' },
                @{ Name = 'Double positive zero'; Value = [double]0.0; Text = '0.0'; Digest = 'sha256:8aed642bf5118b9d3c859bd4be35ecac75b6e873cce34e7b6f554b06f75550d7' },
                @{ Name = 'Double negative zero'; Value = [BitConverter]::Int64BitsToDouble([long]::MinValue); Text = '0.0'; Digest = 'sha256:8aed642bf5118b9d3c859bd4be35ecac75b6e873cce34e7b6f554b06f75550d7' },
                @{ Name = 'Double exact integer'; Value = [double]42; Text = '42.0'; Digest = 'sha256:53519e43db90bd08ff4459fd23fc944324ffb7d8f542ccc0b44257afea2ef525' },
                @{ Name = 'Double exact fraction'; Value = [double]0.125; Text = '0.125'; Digest = 'sha256:52c003e77e74cbacd60930b997433027175ca60b20b7fbb4ec6073b2c4932bb9' },
                @{ Name = 'Double lower fixed threshold'; Value = [double]0.0001; Text = '0.0001'; Digest = 'sha256:e539aebac7fd2ed8aba8854fedeaa65436962f8ee1c82341b394698f085b6496' },
                @{ Name = 'Double lower exponent threshold'; Value = [double]0.00001; Text = '1E-5'; Digest = 'sha256:932e73d87adfb4843b7b0a07b60f15bfd89f776d98783f954af9a33ace369202' },
                @{ Name = 'Double upper fixed threshold'; Value = [double]100000000000000; Text = '100000000000000.0'; Digest = 'sha256:009bafccf9fffe667e1c0b1ec801b62aeae4e648e0c0da55a584e3031954e28b' },
                @{ Name = 'Double upper exponent threshold'; Value = [double]1000000000000000; Text = '1E+15'; Digest = 'sha256:d980faf90b20a967bfb27e02e74c7cdda0966dd5d7ae849a64c56c1c1394b8e6' },
                @{ Name = 'Double smallest accepted magnitude'; Value = [double]0.00000000000001; Text = '1E-14'; Digest = 'sha256:d1bba707f50aa8d3c70f234d038c89812ec871d2a9f71a9c243694bbefc2e6f6' },
                @{ Name = 'Double largest accepted magnitude'; Value = [double]999999999999999; Text = '999999999999999.0'; Digest = 'sha256:b046b94952c242765d3c39803240c1f7c72fbf52493d420b6c5b0ed82c051c9a' }
            )
            $originalCulture = [Globalization.CultureInfo]::CurrentCulture
            $originalUiCulture = [Globalization.CultureInfo]::CurrentUICulture
            try {
                foreach ($cultureName in @('en-US', 'th-TH', 'fa-IR')) {
                    $culture = [Globalization.CultureInfo]::GetCultureInfo($cultureName)
                    [Globalization.CultureInfo]::CurrentCulture = $culture
                    [Globalization.CultureInfo]::CurrentUICulture = $culture
                    foreach ($vector in $vectors) {
                        $canonicalText = ConvertTo-DeterministicJsonText (ConvertTo-CanonicalJsonValue $vector.Value)
                        $canonicalText | Should Be $vector.Text
                        (Get-CanonicalPayloadDigest $vector.Value) | Should Be $vector.Digest
                    }
                }
            }
            finally {
                [Globalization.CultureInfo]::CurrentCulture = $originalCulture
                [Globalization.CultureInfo]::CurrentUICulture = $originalUiCulture
            }
        }

        It 'rejects finite doubles outside the exact cross-host scalar domain without hash collisions' -TestCases @(
            @{ Value = [double]::Epsilon },
            @{ Value = [double]::MaxValue },
            @{ Value = [double]::MinValue }
        ) {
            param($Value)
            Test-ScriptBlockThrows { ConvertTo-DeterministicJsonText (ConvertTo-CanonicalJsonValue $Value) } | Should Be $true
            (Get-CanonicalPayloadDigest $Value) | Should Be 'INVALID_CANONICAL_JSON_RUNTIME_DOMAIN'
        }

        It 'serializes noncolliding ordinal dictionary keys independently of insertion order' {
            $nestedA = [System.Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
            $nestedA.Add('delta', 4)
            $nestedA.Add('Gamma', 3)
            $first = [System.Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
            $first.Add('beta', $nestedA)
            $first.Add('Alpha', 1)

            $nestedB = [System.Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
            $nestedB.Add('Gamma', 3)
            $nestedB.Add('delta', 4)
            $second = [System.Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
            $second.Add('Alpha', 1)
            $second.Add('beta', $nestedB)

            (Get-CanonicalPayloadDigest $first) | Should Be (Get-CanonicalPayloadDigest $second)
            (ConvertTo-DeterministicJsonText (ConvertTo-CanonicalJsonValue $first)) | Should Be '{"Alpha":1,"beta":{"Gamma":3,"delta":4}}'
        }

        It 'decodes valid escaped JSON Pointer tokens exactly' {
            $document = [pscustomobject]@{
                'a/b' = 'slash-value'
                'm~n' = 'tilde-value'
                array = @('zero', 'one')
            }
            (ConvertFrom-StrictJsonPointerToken -EncodedToken 'm~0n').Valid | Should Be $true
            (ConvertFrom-StrictJsonPointerToken -EncodedToken 'm~0n').Value | Should Be 'm~n'
            (ConvertFrom-StrictJsonPointerToken -EncodedToken 'a~1b').Value | Should Be 'a/b'
            (Test-JsonPointerExists -Document $document -Pointer '/a~1b') | Should Be $true
            (Test-JsonPointerExists -Document $document -Pointer '/m~0n') | Should Be $true
            $found = $false
            (Get-JsonPointerValue -Document $document -Pointer '/a~1b' -Found ([ref]$found)) | Should Be 'slash-value'
            $found | Should Be $true
            $found = $false
            (Get-JsonPointerValue -Document $document -Pointer '/m~0n' -Found ([ref]$found)) | Should Be 'tilde-value'
            $found | Should Be $true
        }

        It 'rejects invalid JSON Pointer escapes consistently across syntax and resolution helpers' -TestCases @(
            @{ Pointer = '/a~2b' },
            @{ Pointer = '/a~' }
        ) {
            param($Pointer)
            $document = [pscustomobject]@{ 'a~2b' = 'must-not-resolve'; 'a~' = 'must-not-resolve' }
            (Test-StrictJsonPointerSyntax -Pointer $Pointer) | Should Be $false
            (Test-JsonPointerExists -Document $document -Pointer $Pointer) | Should Be $false
            $found = $true
            (Get-JsonPointerValue -Document $document -Pointer $Pointer -Found ([ref]$found)) | Should BeNullOrEmpty
            $found | Should Be $false
        }

        It 'rejects noncanonical or overflowing JSON Pointer array indices consistently' -TestCases @(
            @{ Pointer = '/array/01' },
            @{ Pointer = '/array/+1' },
            @{ Pointer = '/array/-1' },
            @{ Pointer = '/array/ 1' },
            @{ Pointer = '/array/1 ' },
            @{ Pointer = '/array/999999999999999999999999999999' }
        ) {
            param($Pointer)
            $document = [pscustomobject]@{ array = @('zero', 'one') }
            (Test-JsonPointerExists -Document $document -Pointer $Pointer) | Should Be $false
            $found = $true
            (Get-JsonPointerValue -Document $document -Pointer $Pointer -Found ([ref]$found)) | Should BeNullOrEmpty
            $found | Should Be $false
        }
    }

    Context 'Leadership claim chain' {
        It 'accepts the checked-in NOT_ISSUED template without a recommendation' {
            $chain = Get-Content $chainPath -Raw | ConvertFrom-Json
            $result = Test-LeadershipClaimChain $chain -EvaluationTime $evaluationTime
            $result.Valid | Should Be $true
            $result.Allowed | Should Be $false
            $result.State | Should Be 'NOT_READY'
            $chain.recommendation | Should BeNullOrEmpty
        }

        It 'validates a typed five-link measured chain only as derived input' {
            $fixture = New-IssuedClaimFixture
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST
            $result.Valid | Should Be $true
            $result.Allowed | Should Be $false
            $result.State | Should Be 'TEST_FIXTURE_VALIDATED'
        }

        It 'validates a completed representative Phase 4 pilot as nonauthorizing purchase-ready input' {
            $fixture = New-CompletedPilotIssuedClaimFixture
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST
            $finalVerdict = @($fixture.RecordIndex | Where-Object recordId -CEQ 'verdict-synthetic-1')[0]

            $result.Valid | Should Be $true
            $result.Allowed | Should Be $false
            $result.State | Should Be 'TEST_FIXTURE_VALIDATED'
            $fixture.Chain.recommendation.action | Should Be 'BUY'
            (Get-TestRecordPayloadValue -Record $finalVerdict -FieldName 'pilotAuthorization').status | Should Be 'AUTHORIZED'
            (Get-TestRecordPayloadValue -Record $finalVerdict -FieldName 'pilotCompletion').status | Should Be 'COMPLETED'
            (Get-TestRecordPayloadValue -Record $finalVerdict -FieldName 'fleetVerdict') | Should Be 'QUALIFY'
            (Get-TestRecordPayloadValue -Record $finalVerdict -FieldName 'procurementDisposition') | Should Be 'APPROVED'
        }

        It 'validates NON_PRICE_EFFECT leadership inputs and rejects a metric binding mismatch' {
            $fixture = New-NonPriceIssuedClaimFixture
            $positive = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST
            $positive.Valid | Should Be $true
            $positive.Allowed | Should Be $false
            $fixture.Chain.businessEffect.metricId = 'invented-benefit-metric'
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $negative = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST
            $negative.Valid | Should Be $false
            $negative.Allowed | Should Be $false
            (@($negative.ReasonCodes) -contains 'BUSINESS_EFFECT_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects fixture-scheme artifacts and attestations in the production validation profile' {
            $fixture = New-IssuedClaimFixture
            $record = @($fixture.RecordIndex | Where-Object recordId -eq 'evidence-persona-t0')[0]
            $record.immutableArtifactRef = 'fixture://artifacts/evidence-persona-t0'
            $record.attestationRef = 'fixture://attestations/evidence-persona-t0'
            Update-CanonicalRecordBinding $record
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile PRODUCTION
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FIXTURE_RECORD_FORBIDDEN_IN_PRODUCTION') | Should Be $true
        }

        It 'rejects an envelope-core field changed after attestation' {
            $fixture = New-IssuedClaimFixture
            $record = @($fixture.RecordIndex | Where-Object recordId -eq 'evidence-persona-t0')[0]
            $record.pointers = @('/result', '/invented-after-attestation')
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'CANONICAL_ENVELOPE_CORE_DIGEST_MISMATCH') | Should Be $true
        }

        It 'keeps declared leadership policy fields aligned with validator requirements' -TestCases @(
            @{ Link = 'businessEffect'; Field = 'currency' },
            @{ Link = 'businessEffect'; Field = 'quantity' },
            @{ Link = 'businessEffect'; Field = 'candidateQuoteRef' },
            @{ Link = 'businessEffect'; Field = 'controlQuoteRef' },
            @{ Link = 'businessEffect'; Field = 'quoteValidUntil' },
            @{ Link = 'recommendation'; Field = 'action' }
        ) {
            param($Link, $Field)
            $template = Get-Content $chainPath -Raw | ConvertFrom-Json
            $declaration = @($template.requiredLeadershipLinks | Where-Object link -eq $Link)[0]
            (@($declaration.requiredFields) -ccontains $Field) | Should Be $true
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.$Link.PSObject.Properties.Remove($Field)
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'MISSING_REQUIRED_FIELD') | Should Be $true
        }

        It 'rejects portable-contract ordering drift from the frozen leadership template' {
            $fixture = New-IssuedClaimFixture
            $refs = @($fixture.Chain.portableContractRefs)
            $fixture.Chain.portableContractRefs = @($refs[1], $refs[0], $refs[2], $refs[3], $refs[4], $refs[5])
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes)
            ($codes -contains 'PORTABLE_CONTRACT_SET_MISMATCH') | Should Be $false
            ($codes -contains 'LEADERSHIP_TEMPLATE_POLICY_DRIFT') | Should Be $true
        }

        It 'rejects a substituted portable contract even with a recomputed semantic digest' {
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.portableContractRefs[1] = '../../v2.0.1/schemas/forged-manifest.schema.json'
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'PORTABLE_CONTRACT_SET_MISMATCH') | Should Be $true
        }

        It 'validates an explicit NOT_MEASURED business effect without invented evidence' {
            $chain = New-IssuedClaimChainFixture
            $chain.businessEffect = New-UnmeasuredBusinessEffectFixture
            $index = New-IssuedRecordIndexFixture -Chain $chain
            $result = Test-LeadershipClaimChain $chain $index -EvaluationTime $evaluationTime
            $result.Valid | Should Be $true
            $result.Allowed | Should Be $false
            $result.State | Should Be 'VALIDATED_DERIVED_INPUT'
        }

        It 'rejects NOT_MEASURED business effect carrying invented evidence' {
            $chain = New-IssuedClaimChainFixture
            $chain.businessEffect.status = 'NOT_MEASURED'
            $chain.businessEffect.statement = 'NOT_MEASURED but trust this estimate.'
            $chain.businessEffect | Add-Member -NotePropertyName notMeasuredReason -NotePropertyValue 'No approved release.'
            (@((Test-LeadershipClaimChain $chain (New-IssuedRecordIndexFixture -Chain $chain) -EvaluationTime $evaluationTime).ReasonCodes) -contains 'UNMEASURED_BUSINESS_EFFECT_MISREPRESENTED') | Should Be $true
        }

        It 'rejects smuggled NOT_MEASURED decision impact or calculation fields' -TestCases @(
            @{ Target = 'decisionImpact' }, @{ Target = 'calculation' }
        ) {
            param($Target)
            $chain = New-IssuedClaimChainFixture
            $chain.businessEffect = New-UnmeasuredBusinessEffectFixture
            if ($Target -eq 'decisionImpact') {
                $chain.businessEffect.decisionImpact = 'An unmeasured benefit still supports BUY.'
            }
            else {
                $chain.businessEffect | Add-Member -NotePropertyName calculationResult -NotePropertyValue 999999
            }
            (@((Test-LeadershipClaimChain $chain (New-IssuedRecordIndexFixture -Chain $chain) -EvaluationTime $evaluationTime).ReasonCodes) -contains 'UNMEASURED_BUSINESS_EFFECT_MISREPRESENTED') | Should Be $true
        }

        It 'rejects a measured business-effect statement not copied from its typed record' {
            $chain = New-IssuedClaimChainFixture
            $chain.businessEffect.statement = 'Invented financial upside.'
            (@((Test-LeadershipClaimChain $chain (New-IssuedRecordIndexFixture -Chain $chain) -EvaluationTime $evaluationTime).ReasonCodes) -contains 'BUSINESS_EFFECT_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects evidence omitted from its declared release' {
            $fixture = New-IssuedClaimFixture
            ($fixture.RecordIndex | Where-Object recordId -eq 'candidate-release-synthetic-1').payload.memberRecordIds = @('incumbent-t0','sibling-t0')
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'EVIDENCE_NOT_IN_RELEASE') | Should Be $true
        }

        It 'rejects a release whose semantic or sampling gate is not PASS' {
            $fixture = New-IssuedClaimFixture
            ($fixture.RecordIndex | Where-Object recordId -eq 'persona-release-synthetic-1').payload.semanticGateStatus = 'HOLD'
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'EVIDENCE_RELEASE_GATE_NOT_PASSED') | Should Be $true
        }

        It 'rejects a canonical payload changed after its digest was issued' {
            $fixture = New-IssuedClaimFixture
            ($fixture.RecordIndex | Where-Object recordId -eq 'manifest-synthetic-1').payload.testPlanRef = 'forged-plan'
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'CANONICAL_PAYLOAD_DIGEST_MISMATCH') | Should Be $true
        }

        It 'rejects a forged content digest and attestation subject' {
            $fixture = New-IssuedClaimFixture
            $record = $fixture.RecordIndex | Where-Object recordId -eq 'manifest-synthetic-1'
            $record.contentDigest = New-TestDigest '9'
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes)
            ($codes -contains 'CANONICAL_PAYLOAD_DIGEST_MISMATCH') | Should Be $true
            ($codes -contains 'RELEASE_ATTESTATION_BINDING_INVALID') | Should Be $true
        }

        It 'rejects an attestation bound to another subject digest' {
            $fixture = New-IssuedClaimFixture
            ($fixture.RecordIndex | Where-Object recordId -eq 'manifest-synthetic-1').attestationSubjectDigest = New-TestDigest '8'
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'RELEASE_ATTESTATION_BINDING_INVALID') | Should Be $true
        }

        It 'rejects canonical payload validity that conflicts with its envelope' {
            $fixture = New-IssuedClaimFixture
            $record = $fixture.RecordIndex | Where-Object recordId -eq 'manifest-synthetic-1'
            $record.payload.validUntil = '2026-08-29T00:00:00Z'
            Update-CanonicalRecordBinding $record
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'CANONICAL_ENVELOPE_PAYLOAD_CONFLICT') | Should Be $true
        }

        It 'requires immutable fixture artifacts and verified attestations' -TestCases @(
            @{ Field = 'immutableArtifactRef'; Value = 'https://example.invalid/artifact'; Code = 'IMMUTABLE_ARTIFACT_REF_REQUIRED' },
            @{ Field = 'attestationStatus'; Value = 'PENDING'; Code = 'RELEASE_ATTESTATION_BINDING_INVALID' }
        ) {
            param($Field, $Value, $Code)
            $fixture = New-IssuedClaimFixture
            ($fixture.RecordIndex | Where-Object recordId -eq 'manifest-synthetic-1').$Field = $Value
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects fake canonical pointer inventory entries' {
            $fixture = New-IssuedClaimFixture
            ($fixture.RecordIndex | Where-Object recordId -eq 'manifest-synthetic-1').pointers += '/candidateDevices/99'
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'UNRESOLVED_RECORD_POINTER') | Should Be $true
        }

        It 'rejects semantic fields smuggled into the canonical envelope' {
            $fixture = New-IssuedClaimFixture
            ($fixture.RecordIndex | Where-Object recordId -eq 'manifest-synthetic-1') | Add-Member -NotePropertyName qualificationAuthority -NotePropertyValue 'forged'
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'UNEXPECTED_CONTRACT_FIELD') | Should Be $true
        }

        It 'rejects a missing distribution record' {
            $fixture = New-IssuedClaimFixture
            $fixture.RecordIndex = @($fixture.RecordIndex | Where-Object recordId -ne 'distribution-candidate-synthetic-1')
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'UNRESOLVED_RECORD_REF') | Should Be $true
        }

        It 'rejects a distribution bound to different evidence' {
            $fixture = New-IssuedClaimFixture
            $distribution = $fixture.RecordIndex | Where-Object recordId -eq 'distribution-candidate-synthetic-1'
            $distribution.payload.sourceEvidenceRef = 'incumbent-t0'
            Update-CanonicalRecordBinding $distribution
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'DISTRIBUTION_SEMANTICS_INVALID') | Should Be $true
        }

        It 'rejects a distribution omitted from its immutable evidence release' {
            $fixture = New-IssuedClaimFixture
            $release = $fixture.RecordIndex | Where-Object recordId -eq 'candidate-release-synthetic-1'
            $release.payload.memberRecordIds = @($release.payload.memberRecordIds | Where-Object { $_ -ne 'distribution-candidate-synthetic-1' })
            Update-CanonicalRecordBinding $release
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'DISTRIBUTION_NOT_IN_RELEASE') | Should Be $true
        }

        It 'rejects a declared sampling floor below the Playbook floor' {
            $fixture = New-IssuedClaimFixture
            $distribution = $fixture.RecordIndex | Where-Object recordId -eq 'distribution-candidate-synthetic-1'
            $distribution.payload.requiredUnits = 2
            Update-CanonicalRecordBinding $distribution
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'DISTRIBUTION_SEMANTICS_INVALID') | Should Be $true
        }

        It 'rejects wrong-case and unknown sampling classes' -TestCases @(
            @{ TestClass = 'Controlled-Benchmark' }, @{ TestClass = 'business-impact' }
        ) {
            param($TestClass)
            $fixture = New-IssuedClaimFixture
            $distribution = $fixture.RecordIndex | Where-Object recordId -eq 'distribution-candidate-synthetic-1'
            $distribution.payload.testClass = $TestClass
            Update-CanonicalRecordBinding $distribution
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'DISTRIBUTION_SEMANTICS_INVALID') | Should Be $true
        }

        It 'rejects aggregate run counts below units times required repetitions' {
            $fixture = New-IssuedClaimFixture
            $distribution = $fixture.RecordIndex | Where-Object recordId -eq 'distribution-candidate-synthetic-1'
            $distribution.payload.runCount = 14
            Update-CanonicalRecordBinding $distribution
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'DISTRIBUTION_SEMANTICS_INVALID') | Should Be $true
        }

        It 'accepts exact and higher per-unit run proofs against the frozen floor' -TestCases @(
            @{ UnitCount = 3; RunCount = 15 }, @{ UnitCount = 4; RunCount = 24 }
        ) {
            param($UnitCount, $RunCount)
            $fixture = New-IssuedClaimFixture
            $testPlan = @($fixture.RecordIndex | Where-Object recordId -ceq 'test-plan-synthetic-1')[0]
            $distribution = New-DistributionRecord 'distribution-per-unit-positive' 'candidate-t0' $testPlan `
                -TestClass 'controlled-benchmark' -UnitCount $UnitCount -RunCount $RunCount
            $errors = New-Object System.Collections.ArrayList
            Test-DistributionPerUnitRunProof -Distribution $distribution.payload -Context 'positive per-unit fixture' -Errors $errors
            $errors.Count | Should Be 0
        }

        It 'rejects aggregate-only, duplicate, incomplete, below-floor, and mismatched per-unit proofs' -TestCases @(
            @{ Target = 'aggregate-only' },
            @{ Target = 'below-floor-unit' },
            @{ Target = 'duplicate-unit' },
            @{ Target = 'list-count' },
            @{ Target = 'sum-mismatch' }
        ) {
            param($Target)
            $fixture = New-IssuedClaimFixture
            $distribution = @($fixture.RecordIndex | Where-Object recordId -ceq 'distribution-candidate-synthetic-1')[0]
            switch ($Target) {
                'aggregate-only' {
                    $distribution.payload.unitCount = 1
                    $distribution.payload.runCount = 150
                    $distribution.payload.perUnitRunCounts = @([pscustomobject]@{
                        unitRef = $distribution.payload.perUnitRunCounts[0].unitRef
                        acceptedRunCount = 150
                    })
                }
                'below-floor-unit' {
                    $distribution.payload.perUnitRunCounts[0].acceptedRunCount = 4
                    $distribution.payload.perUnitRunCounts[2].acceptedRunCount = 6
                }
                'duplicate-unit' { $distribution.payload.perUnitRunCounts[1].unitRef = $distribution.payload.perUnitRunCounts[0].unitRef }
                'list-count' { $distribution.payload.perUnitRunCounts = @($distribution.payload.perUnitRunCounts | Select-Object -First 2) }
                'sum-mismatch' { $distribution.payload.runCount = 16 }
            }
            Update-CanonicalRecordBinding $distribution
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'DISTRIBUTION_PER_UNIT_RUN_PROOF_INVALID') | Should Be $true
        }

        It 'rejects public distribution counts below a raised exact Phase 0 class floor' {
            $fixture = New-IssuedClaimFixture
            $testPlan = @($fixture.RecordIndex | Where-Object recordId -ceq 'test-plan-synthetic-1')[0]
            $distribution = @($fixture.RecordIndex | Where-Object recordId -ceq 'distribution-candidate-synthetic-1')[0]
            $testPlan.payload.samplingFloors.'controlled-benchmark'.minUnits = 10
            $testPlan.payload.samplingFloors.'controlled-benchmark'.minRepetitionsPerUnit = 10
            Update-CanonicalRecordBinding $testPlan
            $distribution.payload.phase0TestPlanDigest = $testPlan.contentDigest
            $distribution.payload.samplingFloorDigest = Get-CanonicalPayloadDigest -Payload $testPlan.payload.samplingFloors.'controlled-benchmark'
            Update-CanonicalRecordBinding $distribution
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'DISTRIBUTION_PHASE0_FLOOR_BINDING_INVALID') | Should Be $true
        }

        It 'requires metric identity and a bounded statistic direction on distributions' -TestCases @(
            @{ Target = 'missingMetric'; Code = 'MISSING_REQUIRED_FIELD' },
            @{ Target = 'invalidDirection'; Code = 'DISTRIBUTION_SEMANTICS_INVALID' }
        ) {
            param($Target, $Code)
            $fixture = New-IssuedClaimFixture
            $distribution = $fixture.RecordIndex | Where-Object recordId -eq 'distribution-candidate-synthetic-1'
            if ($Target -eq 'missingMetric') { $distribution.payload.PSObject.Properties.Remove('metricId') }
            else { $distribution.payload.statisticDirection = 'BEST_WINS' }
            Update-CanonicalRecordBinding $distribution
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects forged distribution coverage observations and percentages' -TestCases @(
            @{ Field = 'observed'; Value = 2 }, @{ Field = 'percent'; Value = 12.5 }
        ) {
            param($Field, $Value)
            $fixture = New-IssuedClaimFixture
            $distribution = $fixture.RecordIndex | Where-Object recordId -eq 'distribution-candidate-synthetic-1'
            $distribution.payload.coverage.$Field = $Value
            Update-CanonicalRecordBinding $distribution
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'DISTRIBUTION_COVERAGE_INVALID') | Should Be $true
        }

        It 'rejects evidence bound to the wrong persona manifest' {
            $fixture = New-IssuedClaimFixture
            ($fixture.RecordIndex | Where-Object recordId -eq 'evidence-persona-t0').payload.subjectRef = 'candidate-synthetic-1'
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'PERSONA_EVIDENCE_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects current-fleet issue pointer, text, and attribution mismatches' -TestCases @(
            @{ Target = 'pointer' }, @{ Target = 'text' }, @{ Target = 'attribution' }
        ) {
            param($Target)
            $fixture = New-IssuedClaimFixture
            if ($Target -eq 'pointer') { $fixture.Chain.currentFleetIssue.issueStatementPointer = 'evidence-incumbent-t0#/result' }
            elseif ($Target -eq 'text') { $fixture.Chain.currentFleetIssue.statement = 'A stronger issue statement was invented after release.' }
            else { $fixture.Chain.currentFleetIssue.attributionClass = 'DIRECT' }
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'CURRENT_FLEET_STATEMENT_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects a fleet portfolio whose counts do not reconcile' {
            $fixture = New-IssuedClaimFixture
            $portfolio = $fixture.RecordIndex | Where-Object recordId -eq 'fleet-portfolio-synthetic-1'
            $portfolio.payload.coverage.planned = 41
            Update-CanonicalRecordBinding $portfolio
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FLEET_PORTFOLIO_COUNT_RECONCILIATION_FAILED') | Should Be $true
        }

        It 'rejects duplicate, stale, retired, offline, unhealthy, and unjoinable fleet arithmetic drift' -TestCases @(
            @{ Field = 'duplicateRecordCount' }, @{ Field = 'staleDeviceCount' },
            @{ Field = 'retiredDeviceCount' }, @{ Field = 'offlineDeviceCount' },
            @{ Field = 'unhealthyDeviceCount' }, @{ Field = 'unjoinableDeviceCount' }
        ) {
            param($Field)
            $fixture = New-IssuedClaimFixture
            $portfolio = $fixture.RecordIndex | Where-Object recordId -eq 'fleet-portfolio-synthetic-1'
            $portfolio.payload.$Field = [int]$portfolio.payload.$Field + 1
            Update-CanonicalRecordBinding $portfolio
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FLEET_PORTFOLIO_COUNT_RECONCILIATION_FAILED') | Should Be $true
        }

        It 'rejects an unbound or malformed fleet join policy' -TestCases @(
            @{ Field = 'joinPolicyRef'; Value = 'unscoped-policy' },
            @{ Field = 'joinPolicyDigest'; Value = 'not-a-digest' }
        ) {
            param($Field, $Value)
            $fixture = New-IssuedClaimFixture
            $portfolio = $fixture.RecordIndex | Where-Object recordId -eq 'fleet-portfolio-synthetic-1'
            $portfolio.payload.$Field = $Value
            Update-CanonicalRecordBinding $portfolio
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes) -contains 'FLEET_PORTFOLIO_RECORD_MISMATCH') | Should Be $true
        }

        It 'rejects an unresolved fleet-portfolio cohort pointer' {
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.currentFleetIssue.fleetPortfolioCohortPointer = 'fleet-portfolio-synthetic-1#/configurationCohorts/9'
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FLEET_PORTFOLIO_COHORT_POINTER_INVALID') | Should Be $true
        }

        It 'rejects a fleet portfolio without the selected persona allocation' {
            $fixture = New-IssuedClaimFixture
            $portfolio = $fixture.RecordIndex | Where-Object recordId -eq 'fleet-portfolio-synthetic-1'
            $portfolio.payload.configurationCohorts[0].personaAllocations[0].personaId = 'persona-finance-synthetic'
            Update-CanonicalRecordBinding $portfolio
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FLEET_PORTFOLIO_PERSONA_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects fleet-portfolio evidence absent from every declared release' {
            $fixture = New-IssuedClaimFixture
            $portfolio = $fixture.RecordIndex | Where-Object recordId -eq 'fleet-portfolio-synthetic-1'
            $portfolio.payload.configurationCohorts[0].lifecycleEvidenceRefs += 'candidate-t0'
            Update-CanonicalRecordBinding $portfolio
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FLEET_PORTFOLIO_EVIDENCE_UNRELEASED') | Should Be $true
        }

        It 'rejects a selected persona cohort below the fleet privacy aggregation floor' {
            $fixture = New-IssuedClaimFixture
            $portfolio = $fixture.RecordIndex | Where-Object recordId -eq 'fleet-portfolio-synthetic-1'
            $portfolio.payload.aggregationFloor = 26
            $portfolio.payload.privacyAggregationFloorDigest = Get-CanonicalPayloadDigest -Payload 26
            Update-CanonicalRecordBinding $portfolio
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FLEET_PORTFOLIO_PRIVACY_FLOOR_INVALID') | Should Be $true
        }

        It 'accepts synthetic private privacy commitments only in TEST and never authorizes them' {
            $fixture = New-IssuedClaimFixture
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST
            $result.Valid | Should Be $true
            $result.Allowed | Should Be $false
            $result.State | Should Be 'TEST_FIXTURE_VALIDATED'
        }

        It 'uses distinct release-scoped commitments and proof artifacts for every fleet domain' {
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            $claims = @(
                foreach ($descriptor in @(Get-FleetDimensionClaimDescriptors -Chain $fixture.Chain)) {
                    $dimension = $portfolio.payload.dimensionCoverage.PSObject.Properties[[string]$descriptor.PropertyName].Value
                    @($dimension.claimBindings | Where-Object claimBindingId -CEQ ([string]$descriptor.ClaimBindingId))[0]
                }
            )
            $configuration = $portfolio.payload.configurationCohorts[0]
            $persona = $configuration.personaAllocations[0]
            $plannedCommitments = @($portfolio.payload.coverage.plannedPopulationDigest) + @($claims.coverage.plannedPopulationDigest)
            $proofRefs = @(
                $portfolio.payload.coverage.populationPartitionProofRef,
                $portfolio.payload.configurationPartitionProofRef,
                $configuration.populationSubsetProofRef,
                $configuration.personaPartitionProofRef,
                $persona.populationSubsetProofRef
            ) + @($claims.coverage.populationPartitionProofRef)
            $proofDigests = @(
                $portfolio.payload.coverage.populationPartitionProofDigest,
                $portfolio.payload.configurationPartitionProofDigest,
                $configuration.populationSubsetProofDigest,
                $configuration.personaPartitionProofDigest,
                $persona.populationSubsetProofDigest
            ) + @($claims.coverage.populationPartitionProofDigest)

            @($plannedCommitments | Sort-Object -Unique).Count | Should Be $plannedCommitments.Count
            @($proofRefs | Sort-Object -Unique).Count | Should Be $proofRefs.Count
            @($proofDigests | Sort-Object -Unique).Count | Should Be $proofDigests.Count
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST
            $result.Valid | Should Be $true
            $result.Allowed | Should Be $false
            $result.State | Should Be 'TEST_FIXTURE_VALIDATED'
        }

        It 'rejects malformed, cross-domain, or replayed fleet population proof bindings' -TestCases @(
            @{ Target = 'missing-planned-digest' },
            @{ Target = 'wrong-domain' },
            @{ Target = 'wrong-scheme' },
            @{ Target = 'wrong-version' },
            @{ Target = 'wrong-key-ref' },
            @{ Target = 'wrong-key-version' },
            @{ Target = 'wrong-canonicalization' },
            @{ Target = 'wrong-canonicalization-version' },
            @{ Target = 'wrong-purpose' },
            @{ Target = 'reused-proof-ref' },
            @{ Target = 'reused-proof-digest' },
            @{ Target = 'reused-cross-domain-commitment' },
            @{ Target = 'configuration-subset-proof' },
            @{ Target = 'persona-subset-proof' }
        ) {
            param($Target)
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            $claims = @($portfolio.payload.dimensionCoverage.configurationPersonaPopulation.claimBindings)
            $claim = $claims[0]
            $configuration = $portfolio.payload.configurationCohorts[0]
            $persona = $configuration.personaAllocations[0]
            switch ($Target) {
                'missing-planned-digest' { $claim.coverage.PSObject.Properties.Remove('plannedPopulationDigest') }
                'wrong-domain' { $claim.coverage.populationCommitmentDomainDigest = New-TestDigest 'f' }
                'wrong-scheme' { $claim.coverage.proofScheme = 'CALLER_DEFINED_SET_HASH' }
                'wrong-version' { $claim.coverage.proofVersion = '2.0.0' }
                'wrong-key-ref' { $claim.coverage.populationCommitmentKeyRef = 'private://fleet-population-commitment-keys/other' }
                'wrong-key-version' { $claim.coverage.populationCommitmentKeyVersion = 'other-1.0.0' }
                'wrong-canonicalization' { $claim.coverage.populationCanonicalization = 'CALLER_DEFINED_SORT' }
                'wrong-canonicalization-version' { $claim.coverage.populationCanonicalizationVersion = '2.0.0' }
                'wrong-purpose' { $claim.coverage.populationCommitmentPurpose = 'PORTFOLIO_COVERAGE' }
                'reused-proof-ref' { $claim.coverage.populationPartitionProofRef = $claims[1].coverage.populationPartitionProofRef }
                'reused-proof-digest' { $claim.coverage.populationPartitionProofDigest = $claims[1].coverage.populationPartitionProofDigest }
                'reused-cross-domain-commitment' { $claim.coverage.plannedPopulationDigest = $portfolio.payload.coverage.plannedPopulationDigest }
                'configuration-subset-proof' { $configuration.populationSubsetProofRef = $portfolio.payload.coverage.populationPartitionProofRef }
                'persona-subset-proof' { $persona.populationSubsetProofDigest = $configuration.populationSubsetProofDigest }
            }
            Update-FleetPortfolioDimensionDigests -Fixture $fixture -UpdateSemanticBinding
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FLEET_PORTFOLIO_POPULATION_COMMITMENT_INVALID') | Should Be $true
        }

        It 'never authorizes same-count opaque membership substitutions or exposes their private proof material' {
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            $claim = $portfolio.payload.dimensionCoverage.configurationPersonaPopulation.claimBindings[0]
            $privateProofRef = 'private://fleet-population-proofs/same-count-different-membership-sensitive'
            $privateProofBytes = 'synthetic-private-proof-bytes-must-never-be-diagnosed'
            $privateMemberId = 'synthetic-private-device-id-must-never-be-diagnosed'
            $privateProofDigest = Get-Sha256TokenFromText -Text $privateProofBytes
            $claim.coverage.observedPopulationDigest = Get-Sha256TokenFromText -Text $privateMemberId
            $claim.coverage.populationPartitionProofRef = $privateProofRef
            $claim.coverage.populationPartitionProofDigest = $privateProofDigest
            Update-FleetPortfolioDimensionDigests -Fixture $fixture -UpdateSemanticBinding

            $testResult = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST
            $testResult.Valid | Should Be $true
            $testResult.Allowed | Should Be $false
            $testResult.State | Should Be 'TEST_FIXTURE_VALIDATED'

            $productionResult = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile PRODUCTION
            $productionResult.Valid | Should Be $false
            $productionResult.Allowed | Should Be $false
            (@($productionResult.ReasonCodes) -contains 'FLEET_PORTFOLIO_PRIVATE_PRIVACY_BINDING_UNVERIFIED') | Should Be $true
            $diagnosticText = $productionResult.Errors | ConvertTo-Json -Depth 8 -Compress
            $diagnosticText.Contains($privateProofRef) | Should Be $false
            $diagnosticText.Contains($privateProofDigest) | Should Be $false
            $diagnosticText.Contains($privateProofBytes) | Should Be $false
            $diagnosticText.Contains($privateMemberId) | Should Be $false
        }

        It 'keeps an otherwise-valid opaque private privacy binding on production HOLD' {
            $fixture = New-IssuedClaimFixture
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile PRODUCTION
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FLEET_PORTFOLIO_PRIVATE_PRIVACY_BINDING_UNVERIFIED') | Should Be $true
        }

        It 'does not let changed opaque privacy commitments become production evidence or authorization' -TestCases @(
            @{ Field = 'privacyPolicyDigest'; Value = (New-TestDigest 'e') },
            @{ Field = 'privacyReleaseDigest'; Value = (New-TestDigest 'f') }
        ) {
            param($Field, $Value)
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            $portfolio.payload.$Field = $Value
            Update-CanonicalRecordBinding $portfolio
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile PRODUCTION
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FLEET_PORTFOLIO_PRIVATE_PRIVACY_BINDING_UNVERIFIED') | Should Be $true
        }

        It 'rejects missing privacy commitment digests' -TestCases @(
            @{ Field = 'privacyPolicyDigest' }, @{ Field = 'privacyReleaseDigest' }
        ) {
            param($Field)
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            $portfolio.payload.PSObject.Properties.Remove($Field)
            Update-CanonicalRecordBinding $portfolio
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'MISSING_REQUIRED_FIELD') | Should Be $true
        }

        It 'rejects changed privacy-floor and minimum-coverage governance bindings' -TestCases @(
            @{ Target = 'privacy-floor-pointer' },
            @{ Target = 'privacy-floor-digest' },
            @{ Target = 'minimum-pointer' },
            @{ Target = 'minimum-digest' },
            @{ Target = 'minimum-value' }
        ) {
            param($Target)
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            switch ($Target) {
                'privacy-floor-pointer' { $portfolio.payload.privacyAggregationFloorPointer = '/inventedFloor' }
                'privacy-floor-digest' { $portfolio.payload.privacyAggregationFloorDigest = New-TestDigest 'f' }
                'minimum-pointer' { $portfolio.payload.minimumCoveragePointer = '/thresholds/other/value' }
                'minimum-digest' { $portfolio.payload.minimumCoverageValueDigest = New-TestDigest 'f' }
                'minimum-value' { $portfolio.payload.minimumCoveragePct = 79 }
            }
            Update-CanonicalRecordBinding $portfolio
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'FLEET_PORTFOLIO_GOVERNANCE_BINDING_INVALID') | Should Be $true
        }

        It 'rejects fail-open portfolio coverage arithmetic and governed-floor claims' -TestCases @(
            @{ Target = 'zero-eligible' },
            @{ Target = 'equation' },
            @{ Target = 'percent' },
            @{ Target = 'one-of-one-hundred' },
            @{ Target = 'exact-boundary-below-floor' }
        ) {
            param($Target)
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            switch ($Target) {
                'zero-eligible' {
                    $portfolio.payload.coverage = [pscustomobject]@{ planned = 5; eligible = 0; observed = 0; missing = 0; excluded = 5; percent = 0; status = 'PASS' }
                }
                'equation' { $portfolio.payload.coverage.missing = 4 }
                'percent' { $portfolio.payload.coverage.percent = 80 }
                'one-of-one-hundred' {
                    $portfolio.payload.coverage = [pscustomobject]@{ planned = 100; eligible = 100; observed = 1; missing = 99; excluded = 0; percent = 1; status = 'PASS' }
                }
                'exact-boundary-below-floor' {
                    # Displayed 80.00 is within projection tolerance of 79.999, but exact cross-products remain below 80%.
                    $portfolio.payload.coverage = [pscustomobject]@{ planned = 100000; eligible = 100000; observed = 79999; missing = 20001; excluded = 0; percent = 80.00; status = 'PASS' }
                }
            }
            Update-CanonicalRecordBinding $portfolio
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'FLEET_PORTFOLIO_COVERAGE_INVALID') | Should Be $true
        }

        It 'accepts an exact fractional governed coverage floor' {
            $errors = New-Object System.Collections.ArrayList
            $coverage = New-FleetCoverageCommitment -Seed 'fractional-positive' -Purpose PORTFOLIO_COVERAGE `
                -Planned 200 -Eligible 200 -Observed 191 -Missing 9 -Excluded 0 -Percent 95.5
            (Test-FleetPortfolioCoverageValue -Coverage $coverage -MinimumCoveragePct 95.5 -AggregationFloor 10 `
                -Context 'fractional positive fixture' -ErrorCode 'FRACTIONAL_COVERAGE_INVALID' -Errors $errors) | Should Be $true
            $errors.Count | Should Be 0
        }

        It 'rejects a count ratio just below a fractional floor despite a tolerated display projection' {
            $errors = New-Object System.Collections.ArrayList
            $coverage = New-FleetCoverageCommitment -Seed 'fractional-boundary' -Purpose PORTFOLIO_COVERAGE `
                -Planned 100000 -Eligible 100000 -Observed 95499 -Missing 4501 -Excluded 0 -Percent 95.5
            (Test-FleetPortfolioCoverageValue -Coverage $coverage -MinimumCoveragePct 95.5 -AggregationFloor 10 `
                -Context 'fractional boundary fixture' -ErrorCode 'FRACTIONAL_COVERAGE_INVALID' -Errors $errors) | Should Be $false
            (@($errors.code) -contains 'FRACTIONAL_COVERAGE_INVALID') | Should Be $true
        }

        It 'rejects a claim coverage projection that diverges from the governed portfolio cohort' {
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            $claim = $portfolio.payload.dimensionCoverage.configurationPersonaPopulation.claimBindings[0]
            $claim.coverage.planned = 41
            $claim.coverage.eligible = 36
            $claim.coverage.observed = 30
            $claim.coverage.missing = 6
            $claim.coverage.percent = 83.3333333333333
            Update-FleetPortfolioDimensionDigests -Fixture $fixture -UpdateSemanticBinding
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'FLEET_PORTFOLIO_CLAIM_COVERAGE_INVALID') | Should Be $true
        }

        It 'accepts honest claim-specific missingness below the parent observation count' {
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            $claim = $portfolio.payload.dimensionCoverage.configurationPersonaPopulation.claimBindings[0]
            $evidence = @($fixture.RecordIndex | Where-Object recordId -ceq $claim.structuredSummaryRef)[0]
            $claim.coverage.observed = 29
            $claim.coverage.missing = 6
            $claim.coverage.percent = 82.8571428571429
            $evidence.payload.coverage.observedUnits = 29
            $evidence.payload.coverage.observedRuns = 290
            $evidence.payload.coverage.percent = 82.8571428571429
            Update-CanonicalRecordBinding $evidence
            $claim.sourceRecordBindings[0].contentDigest = $evidence.contentDigest
            $claim.sourcePointers[0].contentDigest = $evidence.contentDigest
            $claim.structuredSummaryDigest = $evidence.contentDigest
            Update-FleetPortfolioDimensionDigests -Fixture $fixture -UpdateSemanticBinding
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST
            $result.Valid | Should Be $true
            $result.Allowed | Should Be $false
        }

        It 'rejects omission of each frozen current-fleet leadership dimension' {
            $context = New-FleetDimensionSemanticTestContext
            $properties = @(
                'configurationPersonaPopulation','platformSupportBaseline','capacityHeadroom',
                'workloadResourcePressure','applicationState','batteryStandby','dockReliability',
                'provisioningUpdateComplianceManagement','incidentRepairSupport',
                'regionWorkPatternRepresentation','provenanceIntegrity',
                'limitationsOutliersFreshnessRequalification'
            )
            foreach ($propertyName in $properties) {
                $portfolio = Copy-TestObject -InputObject $context.Portfolio
                $portfolio.dimensionCoverage.PSObject.Properties.Remove($propertyName)
                $codes = @(Get-FleetDimensionSemanticReasonCodes -Context $context -Portfolio $portfolio)
                ($codes -contains 'FLEET_PORTFOLIO_DIMENSION_SET_INCOMPLETE') | Should Be $true
            }
        }

        It 'rejects mislabeling every frozen current-fleet claim type' {
            $context = New-FleetDimensionSemanticTestContext
            $descriptors = @(Get-FleetDimensionClaimDescriptors -Chain $context.Fixture.Chain)
            foreach ($descriptor in $descriptors) {
                $portfolio = Copy-TestObject -InputObject $context.Portfolio
                $dimension = $portfolio.dimensionCoverage.PSObject.Properties[[string]$descriptor.PropertyName].Value
                $claim = @($dimension.claimBindings | Where-Object claimBindingId -CEQ ([string]$descriptor.ClaimBindingId))[0]
                $claim.claimMetricType = 'INVENTED_OR_WRONG_CLAIM_TYPE'
                $codes = @(Get-FleetDimensionSemanticReasonCodes -Context $context -Portfolio $portfolio)
                ($codes -contains 'FLEET_PORTFOLIO_CLAIM_POLICY_MISMATCH') | Should Be $true
            }
        }

        It 'rejects duplicate claim identity and exact evidence-closure substitutions' -TestCases @(
            @{ Target = 'duplicate-claim'; Code = 'FLEET_PORTFOLIO_CLAIM_POLICY_MISMATCH' },
            @{ Target = 'release-digest'; Code = 'FLEET_PORTFOLIO_CLAIM_RELEASE_INVALID' },
            @{ Target = 'source-digest'; Code = 'FLEET_PORTFOLIO_CLAIM_SOURCE_BINDING_INVALID' },
            @{ Target = 'pointer'; Code = 'FLEET_PORTFOLIO_CLAIM_POINTER_INVALID' },
            @{ Target = 'baseline'; Code = 'FLEET_PORTFOLIO_CLAIM_BASELINE_WINDOW_MISMATCH' },
            @{ Target = 'query'; Code = 'FLEET_PORTFOLIO_CLAIM_QUERY_PROVENANCE_INVALID' },
            @{ Target = 'provenance'; Code = 'FLEET_PORTFOLIO_CLAIM_PROVENANCE_INVALID' },
            @{ Target = 'artifact'; Code = 'FLEET_PORTFOLIO_CLAIM_ARTIFACT_INVALID' },
            @{ Target = 'freshness-age'; Code = 'FLEET_PORTFOLIO_CLAIM_FRESHNESS_INVALID' }
        ) {
            param($Target, $Code)
            $context = New-FleetDimensionSemanticTestContext
            $portfolio = Copy-TestObject -InputObject $context.Portfolio
            $claims = @($portfolio.dimensionCoverage.configurationPersonaPopulation.claimBindings)
            $claim = $claims[0]
            switch ($Target) {
                'duplicate-claim' { $claims[1].claimBindingId = $claim.claimBindingId }
                'release-digest' { $claim.evidenceReleaseBindings[0].contentDigest = New-TestDigest 'f' }
                'source-digest' { $claim.sourceRecordBindings[0].contentDigest = New-TestDigest 'f' }
                'pointer' { $claim.sourcePointers[0].jsonPointer = '/invented' }
                'baseline' { $claim.baselineFingerprint = New-TestDigest 'f' }
                'query' { $claim.queryPackDigest = New-TestDigest 'f' }
                'provenance' { $claim.provenanceTier = 'T1' }
                'artifact' { $claim.artifactHashes = @(New-TestDigest 'f') }
                'freshness-age' { $claim.freshnessBinding.maximumAgeDays = 366 }
            }
            $codes = @(Get-FleetDimensionSemanticReasonCodes -Context $context -Portfolio $portfolio)
            ($codes -contains $Code) | Should Be $true
        }

        It 'rejects a portfolio source release with the same ID but a substituted digest' {
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            $portfolio.payload.sourceEvidenceReleaseBindings[0].contentDigest = New-TestDigest 'f'
            Update-CanonicalRecordBinding $portfolio
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'FLEET_PORTFOLIO_RELEASE_SET_INVALID') | Should Be $true
        }

        It 'rejects an unrelated current platform baseline even when the caller recomputes its digest' {
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            $claim = $portfolio.payload.dimensionCoverage.configurationPersonaPopulation.claimBindings[0]
            $baseline = @($fixture.RecordIndex | Where-Object recordId -ceq 'platform-baseline-synthetic-1')[0]
            $alternate = New-CanonicalRecord 'platform-baseline-unrelated-synthetic-1' 'platform-baseline-record' @('/dependencySnapshot') -Fields @{
                dependencySnapshot = Copy-TestObject -InputObject $baseline.payload.dependencySnapshot
                dependencySnapshotDigest = [string]$baseline.payload.dependencySnapshotDigest
                dependencyStatus = 'CURRENT'
            }
            $fixture.RecordIndex += $alternate
            $claim.freshnessBinding.platformBaselineRef = $alternate.recordId
            $claim.freshnessBinding.platformBaselineDigest = $alternate.contentDigest
            $claim.freshnessBinding.dependencySnapshotRef = "$($alternate.recordId)#/dependencySnapshot"
            $claim.freshnessBinding.dependencySnapshotDigest = Get-CanonicalPayloadDigest -Payload $alternate.payload.dependencySnapshot
            Update-FleetPortfolioDimensionDigests -Fixture $fixture -UpdateSemanticBinding
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'FLEET_PORTFOLIO_CLAIM_FRESHNESS_INVALID') | Should Be $true
        }

        It 'rejects a tiny structured summary that cannot support the declared fleet claim' {
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            $claim = $portfolio.payload.dimensionCoverage.configurationPersonaPopulation.claimBindings[0]
            $evidence = @($fixture.RecordIndex | Where-Object recordId -ceq $claim.structuredSummaryRef)[0]
            $evidence.payload.coverage.observedUnits = 1
            $evidence.payload.coverage.observedRuns = 1
            $evidence.payload.coverage.percent = 2.85714285714286
            Update-CanonicalRecordBinding $evidence
            $claim.sourceRecordBindings[0].contentDigest = $evidence.contentDigest
            $claim.sourcePointers[0].contentDigest = $evidence.contentDigest
            $claim.structuredSummaryDigest = $evidence.contentDigest
            Update-FleetPortfolioDimensionDigests -Fixture $fixture -UpdateSemanticBinding
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'FLEET_PORTFOLIO_STRUCTURED_SUMMARY_INVALID') | Should Be $true
        }

        It 'rejects a distribution derived from another released claim source' {
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            $claim = $portfolio.payload.dimensionCoverage.capacityHeadroom.claimBindings[0]
            $distribution = @($fixture.RecordIndex | Where-Object recordId -ceq $claim.distributionRef)[0]
            $unrelated = @($fixture.RecordIndex | Where-Object recordId -ceq 'evidence-fleet-resource-pressure-synthetic-1')[0]
            $distribution.payload.sourceEvidenceRef = $unrelated.recordId
            $distribution.payload.sourceEvidenceDigest = $unrelated.contentDigest
            Update-CanonicalRecordBinding $distribution
            $claim.distributionDigest = $distribution.contentDigest
            Update-FleetPortfolioDimensionDigests -Fixture $fixture -UpdateSemanticBinding
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'FLEET_PORTFOLIO_DISTRIBUTION_BINDING_INVALID') | Should Be $true
        }

        It 'enforces the aggregation floor on non-selected configuration and persona rows' -TestCases @(
            @{ Target = 'configuration' }, @{ Target = 'persona' }
        ) {
            param($Target)
            $fixture = New-IssuedClaimFixture
            $portfolio = @($fixture.RecordIndex | Where-Object recordId -ceq 'fleet-portfolio-synthetic-1')[0]
            $population = @($fixture.RecordIndex | Where-Object recordId -ceq 'cohort-synthetic-1')[0]
            if ($Target -eq 'configuration') {
                $portfolio.payload.configurationCohorts[0].observedDeviceCount = 21
                $portfolio.payload.configurationCohorts[0].personaAllocations[0].observedDeviceCount = 16
                $portfolio.payload.configurationCohorts += [pscustomobject]@{
                    configurationRef = 'manifest-synthetic-1#/candidateDevices/0'
                    cohortRef = 'cohort-nonselected-synthetic-2'
                    observedDeviceCount = 9
                    unknownComponentIdentityCount = 0
                    personaAllocations = @([pscustomobject]@{ personaId = 'persona-other-synthetic'; cohortRef = 'cohort-nonselected-synthetic-2'; observedDeviceCount = 9 })
                    unassignedPersonaCount = 0
                    lifecycleEvidenceRefs = @('incident-release-t0')
                    platformEvidenceRefs = @('evidence-incumbent-t0')
                    issueEvidenceRefs = @('evidence-incumbent-t0')
                }
                $population.payload.deviceConfigurationRefs += 'manifest-synthetic-1#/candidateDevices/0'
                $population.payload.personaIds += 'persona-other-synthetic'
                Update-CanonicalRecordBinding $population
            }
            else {
                $portfolio.payload.configurationCohorts[0].personaAllocations[0].observedDeviceCount = 16
                $portfolio.payload.configurationCohorts[0].personaAllocations += [pscustomobject]@{
                    personaId = 'persona-other-synthetic'
                    cohortRef = [string]$fixture.Chain.currentFleetIssue.cohortRef
                    observedDeviceCount = 9
                }
                $population.payload.personaIds += 'persona-other-synthetic'
                Update-CanonicalRecordBinding $population
            }
            Update-CanonicalRecordBinding $portfolio
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'FLEET_PORTFOLIO_PRIVACY_FLOOR_INVALID') | Should Be $true
        }

        It 'rejects a distribution that substitutes the frozen test ID, class, or definition digest' -TestCases @(
            @{ Target = 'test-ref' },
            @{ Target = 'test-class' },
            @{ Target = 'definition-digest' }
        ) {
            param($Target)
            $fixture = New-IssuedClaimFixture
            $distribution = @($fixture.RecordIndex | Where-Object recordId -ceq 'distribution-candidate-synthetic-1')[0]
            if ($Target -ceq 'test-ref') { $distribution.payload.testRef = 'test-sustained-performance-synthetic-1' }
            elseif ($Target -ceq 'test-class') { $distribution.payload.testClass = 'sustained-performance' }
            else { $distribution.payload.testDefinitionDigest = New-TestDigest 'f' }
            Update-CanonicalRecordBinding $distribution
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'DISTRIBUTION_TEST_DEFINITION_BINDING_INVALID') | Should Be $true
        }

        It 'rejects an evidence tuple that does not match its exact Phase 3 test definition' {
            $fixture = New-IssuedClaimFixture
            $evidence = @($fixture.RecordIndex | Where-Object recordId -ceq 'sibling-t0')[0]
            $evidence.payload.controlRole = 'candidate'
            Update-CanonicalRecordBinding $evidence
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'COMPARISON_TEST_TUPLE_INVALID') | Should Be $true
        }

        It 'rejects omission of one exact Phase 3 test and role tuple' {
            $fixture = New-IssuedClaimFixture
            $evidenceId = 'candidate-agent-state-t0'
            $distributionId = 'distribution-candidate-agent-state-synthetic-1'
            $fixture.RecordIndex = @($fixture.RecordIndex | Where-Object { [string]$_.recordId -cnotin @($evidenceId, $distributionId) })
            $fixture.Chain.candidateComparison.evidenceRefs = @($fixture.Chain.candidateComparison.evidenceRefs | Where-Object { [string]$_ -cne $evidenceId })
            $release = @($fixture.RecordIndex | Where-Object recordId -ceq 'candidate-release-synthetic-1')[0]
            $release.payload.memberRecordIds = @($release.payload.memberRecordIds | Where-Object { [string]$_ -cnotin @($evidenceId, $distributionId) })
            Update-CanonicalRecordBinding $release
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'COMPARISON_TEST_TUPLE_MISSING') | Should Be $true
        }

        It 'requires only Phase 3 test-local conditions of all comparison roles' {
            $fixture = New-IssuedClaimFixture
            $testPlan = @($fixture.RecordIndex | Where-Object recordId -ceq 'test-plan-synthetic-1')[0]
            $phase3Conditions = @($testPlan.payload.tests | Where-Object { [int]$_.phase -eq 3 } | ForEach-Object { $_.conditions[0].conditionId })
            $otherPhaseConditions = @($testPlan.payload.tests | Where-Object { [int]$_.phase -ne 3 } | ForEach-Object { $_.conditions[0].conditionId })
            @($fixture.Chain.candidateComparison.conditionRefs).Count | Should Be $phase3Conditions.Count
            foreach ($conditionRef in $phase3Conditions) { (@($fixture.Chain.candidateComparison.conditionRefs) -ccontains $conditionRef) | Should Be $true }
            foreach ($conditionRef in $otherPhaseConditions) { (@($fixture.Chain.candidateComparison.conditionRefs) -ccontains $conditionRef) | Should Be $false }
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST
            $result.Valid | Should Be $true
            $result.Allowed | Should Be $false
        }

        It 'rejects a capacity waterfall from a different persona verdict index' {
            $fixture = New-IssuedClaimFixture
            $wrongPointer = 'verdict-synthetic-1#/personaVerdicts/1/capacityWaterfall'
            $fixture.Chain.personaNeed.capacityWaterfallPointer = $wrongPointer
            ($fixture.RecordIndex | Where-Object recordId -eq 'verdict-synthetic-1').pointers += '/personaVerdicts/1/capacityWaterfall'
            ($fixture.RecordIndex | Where-Object recordId -eq 'evidence-persona-t0').payload.capacityWaterfallPointer = $wrongPointer
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'CAPACITY_WATERFALL_POINTER_MISMATCH') | Should Be $true
        }

        It 'rejects a candidate projected from a different manifest' {
            $fixture = New-IssuedClaimFixture
            $otherManifest = New-CanonicalRecord 'manifest-synthetic-2' 'candidate-manifest' @('/candidateDevices/0') -Fields @{ candidateDevices = @([pscustomobject]@{ candidateId = 'candidate-synthetic-2' }); testPlanRef = 'test-plan-synthetic-1' }
            $fixture.RecordIndex += $otherManifest
            $fixture.Chain.candidateComparison.candidateRef = 'manifest-synthetic-2#/candidateDevices/0'
            ($fixture.RecordIndex | Where-Object recordId -eq 'candidate-t0').payload.subjectRef = 'manifest-synthetic-2#/candidateDevices/0'
            ($fixture.RecordIndex | Where-Object recordId -eq 'candidate-quote-synthetic-1').payload.subjectRef = 'manifest-synthetic-2#/candidateDevices/0'
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'MANIFEST_SUBJECT_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects a verdict bound to a different manifest' {
            $fixture = New-IssuedClaimFixture
            ($fixture.RecordIndex | Where-Object recordId -eq 'verdict-synthetic-1').payload.manifestRef = 'manifest-synthetic-2'
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'VERDICT_MANIFEST_MISMATCH') | Should Be $true
        }

        It 'rejects a BUY recommendation when the fleet verdict is FAIL' {
            $fixture = New-IssuedClaimFixture
            $verdict = $fixture.RecordIndex | Where-Object recordId -eq 'verdict-synthetic-1'
            $verdict.payload.fleetVerdict = 'FAIL'
            $verdict.payload.fleetDeploymentDisposition = 'BLOCKED'
            $verdict.payload.procurementDisposition = 'BLOCKED'
            Update-DecisionClaimVerdictBinding $fixture.RecordIndex
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'RECOMMENDATION_STRENGTHENS_VERDICT') | Should Be $true
        }

        It 'rejects a persona verdict issued for another persona' {
            $fixture = New-IssuedClaimFixture
            $verdict = $fixture.RecordIndex | Where-Object recordId -eq 'verdict-synthetic-1'
            $verdict.payload.personaVerdicts[0].persona = 'persona-finance-synthetic'
            Update-DecisionClaimVerdictBinding $fixture.RecordIndex
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'SELECTED_PERSONA_ID_MISMATCH') | Should Be $true
        }

        It 'rejects a persona and fleet conflict without complete conditional arbitration' {
            $fixture = New-IssuedClaimFixture
            $verdict = $fixture.RecordIndex | Where-Object recordId -eq 'verdict-synthetic-1'
            $verdict.payload.personaVerdicts[0].conflictsWithFleetConditions = $true
            Update-DecisionClaimVerdictBinding $fixture.RecordIndex
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'PERSONA_FLEET_CONFLICT_ARBITRATION_REQUIRED') | Should Be $true
            (@($result.ReasonCodes) -contains 'PERSONA_FLEET_CONFLICT_NOT_CONDITIONAL') | Should Be $true
        }

        It 'rejects an expired retained verdict condition' {
            $fixture = New-IssuedClaimFixture
            $verdict = $fixture.RecordIndex | Where-Object recordId -eq 'verdict-synthetic-1'
            $verdict.payload.conditions[0].expiration = '2026-08-26'
            Update-DecisionClaimVerdictBinding $fixture.RecordIndex
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'VERDICT_CONDITION_EXPIRED') | Should Be $true
        }

        It 'treats a verdict condition expiring later on the evaluation date as expired' {
            $fixture = New-IssuedClaimFixture
            $verdict = $fixture.RecordIndex | Where-Object recordId -eq 'verdict-synthetic-1'
            $verdict.payload.conditions[0].expiration = '2026-08-27T23:59:59Z'
            Update-DecisionClaimVerdictBinding $fixture.RecordIndex
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'VERDICT_CONDITION_EXPIRED') | Should Be $true
        }

        It 'rejects expired commercial quotes' {
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.businessEffect.quoteValidUntil = '2026-08-27T12:29:00Z'
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'COMMERCIAL_QUOTE_EXPIRED_OR_INVALID') | Should Be $true
        }

        It 'rejects a missing measured commercial quote record' {
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.businessEffect.candidateQuoteRef = 'candidate-quote-invented'
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'UNRESOLVED_RECORD_REF') | Should Be $true
        }

        It 'rejects missing and expired quote inputs on NOT_MEASURED decisions' -TestCases @(
            @{ Target = 'missing'; Code = 'MISSING_REQUIRED_FIELD' },
            @{ Target = 'expired'; Code = 'COMMERCIAL_QUOTE_EXPIRED_OR_INVALID' }
        ) {
            param($Target, $Code)
            $chain = New-IssuedClaimChainFixture
            $chain.businessEffect = New-UnmeasuredBusinessEffectFixture
            if ($Target -eq 'missing') { $chain.businessEffect.PSObject.Properties.Remove('candidateQuoteRef') }
            else { $chain.businessEffect.quoteValidUntil = '2026-08-27T12:29:00Z' }
            $index = New-IssuedRecordIndexFixture -Chain $chain
            (@((Test-LeadershipClaimChain $chain $index -EvaluationTime $evaluationTime).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects commercial quote arithmetic that does not equal unit price times quantity' {
            $fixture = New-IssuedClaimFixture
            ($fixture.RecordIndex | Where-Object recordId -eq 'candidate-quote-synthetic-1').payload.totalPrice = 1
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'COMMERCIAL_QUOTE_ARITHMETIC_INVALID') | Should Be $true
        }

        It 'rejects a quote for a different candidate or incumbent subject' -TestCases @(
            @{ RecordId = 'candidate-quote-synthetic-1' }, @{ RecordId = 'control-quote-synthetic-1' }
        ) {
            param($RecordId)
            $fixture = New-IssuedClaimFixture
            $quote = $fixture.RecordIndex | Where-Object recordId -eq $RecordId
            $quote.payload.subjectRef = 'manifest-synthetic-1#/controls/sibling-or-alternative'
            Update-CanonicalRecordBinding $quote
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'COMMERCIAL_QUOTE_SUBJECT_MISMATCH') | Should Be $true
        }

        It 'rejects a quote bound to the wrong configuration envelope' -TestCases @(
            @{ RecordId = 'candidate-quote-synthetic-1' }, @{ RecordId = 'control-quote-synthetic-1' }
        ) {
            param($RecordId)
            $fixture = New-IssuedClaimFixture
            $quote = $fixture.RecordIndex | Where-Object recordId -eq $RecordId
            $quote.payload.configurationEnvelopePointer = 'manifest-synthetic-1#/controls/sibling-or-alternative'
            Update-CanonicalRecordBinding $quote
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'COMMERCIAL_QUOTE_SUBJECT_MISMATCH') | Should Be $true
        }

        It 'rejects a measured result that does not equal candidate minus control total' {
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.businessEffect.calculationResult = 1
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'BUSINESS_CALCULATION_RESULT_MISMATCH') | Should Be $true
        }

        It 'rejects a rendered decision claim missing a verdict source pointer' {
            $fixture = New-IssuedClaimFixture
            ($fixture.RecordIndex | Where-Object recordId -eq 'decision-claim-synthetic-1').payload.sourcePointers = @('verdict-synthetic-1#/fleetVerdict')
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'DECISION_CLAIM_SOURCE_POINTER_MISSING') | Should Be $true
        }

        It 'rejects semantic validation retained for different decision inputs' {
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.currentFleetIssue.observationWindow = '2026-02-01/2026-03-31'
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'SEMANTIC_VALIDATION_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects a re-digested transitive distribution mutation under stale semantic validation' {
            $fixture = New-IssuedClaimFixture
            $distribution = $fixture.RecordIndex | Where-Object recordId -eq 'distribution-candidate-synthetic-1'
            $distribution.payload.median = 101
            Update-CanonicalRecordBinding $distribution
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'CANONICAL_PAYLOAD_DIGEST_MISMATCH') | Should Be $false
            (@($result.ReasonCodes) -contains 'SEMANTIC_VALIDATION_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects future and malformed observation windows' -TestCases @(
            @{ Field = 'currentFleetIssue'; Value = '2026-09-01/2026-09-30' },
            @{ Field = 'businessEffect'; Value = 'last-quarter' }
        ) {
            param($Field, $Value)
            $chain = New-IssuedClaimChainFixture
            $chain.$Field.observationWindow = $Value
            (@((Test-LeadershipClaimChain $chain (New-IssuedRecordIndexFixture -Chain $chain) -EvaluationTime $evaluationTime).ReasonCodes) -contains 'INVALID_OBSERVATION_WINDOW') | Should Be $true
        }

        It 'rejects an issued chain without a canonical record index' {
            $result = Test-LeadershipClaimChain (New-IssuedClaimChainFixture) -EvaluationTime $evaluationTime
            (@($result.ReasonCodes) -contains 'RECORD_INDEX_REQUIRED') | Should Be $true
            $result.Allowed | Should Be $false
        }

        It 'rejects bare record identifiers' {
            $fixture = New-IssuedClaimFixture
            $bare = @($fixture.RecordIndex | ForEach-Object recordId)
            $result = Test-LeadershipClaimChain $fixture.Chain $bare -EvaluationTime $evaluationTime
            (@($result.ReasonCodes) -contains 'UNTYPED_RECORD_INDEX_ENTRY') | Should Be $true
            $result.Allowed | Should Be $false
        }

        It 'rejects invented canonical record identifiers' {
            $chain = New-IssuedClaimChainFixture
            $chain.candidateComparison.evidenceRefs = @('invented-evidence-id')
            (@((Test-LeadershipClaimChain $chain (New-IssuedRecordIndexFixture -Chain $chain) -EvaluationTime $evaluationTime).ReasonCodes) -contains 'UNRESOLVED_RECORD_REF') | Should Be $true
        }

        It 'rejects null-only evidence references' {
            $chain = New-IssuedClaimChainFixture
            $chain.personaNeed.evidenceRefs = @($null)
            (@((Test-LeadershipClaimChain $chain (New-IssuedRecordIndexFixture -Chain $chain) -EvaluationTime $evaluationTime).ReasonCodes) -contains 'MISSING_REQUIRED_FIELD') | Should Be $true
        }

        It 'rejects nonexistent and case-mismatched pointers' -TestCases @(
            @{ Pointer = 'verdict-synthetic-1#/personaVerdicts/9' },
            @{ Pointer = 'verdict-synthetic-1#/PersonaVerdicts/0' }
        ) {
            param($Pointer)
            $chain = New-IssuedClaimChainFixture
            $chain.personaNeed.personaVerdictPointer = $Pointer
            $chain.recommendation.personaVerdictPointer = $Pointer
            (@((Test-LeadershipClaimChain $chain (New-IssuedRecordIndexFixture -Chain $chain) -EvaluationTime $evaluationTime).ReasonCodes) -contains 'UNRESOLVED_RECORD_POINTER') | Should Be $true
        }

        It 'rejects a semantic-validation digest mismatch' {
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.lineage.semanticValidationDigest = New-TestDigest 'f'
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'SEMANTIC_VALIDATION_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects recommendation text not copied from the rendered decision claim' {
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.recommendation.statement = 'BUY EVERYTHING'
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'DECISION_CLAIM_BINDING_MISMATCH') | Should Be $true
        }

        It 'accepts T2 only with indexed same-claim T0 corroboration' {
            $chain = New-IssuedClaimChainFixture
            $chain.personaNeed.evidenceRefs = @('evidence-persona-t0','evidence-persona-t2')
            $chain.personaNeed.provenance = @('T0','T2')
            $index = @(New-IssuedRecordIndexFixture -Chain $chain)
            $index += New-EvidenceRecord 'evidence-persona-t2' 'persona-fit' 'T2' 'evidence-persona-t0' -Fields @{ subjectRef = 'manifest-synthetic-1'; personaId = 'persona-engineering-synthetic'; capacityWaterfallPointer = 'verdict-synthetic-1#/personaVerdicts/0/capacityWaterfall'; evidenceReleaseRef = 'persona-release-synthetic-1'; coverageStatus = 'PASS'; freshnessBinding = New-SourceFreshnessBinding $chain.personaNeed.freshness }
            $release = $index | Where-Object recordId -eq 'persona-release-synthetic-1'
            $release.payload.memberRecordIds += 'evidence-persona-t2'
            Update-CanonicalRecordBinding $release
            Update-ClaimSemanticBinding $chain $index
            (Test-LeadershipClaimChain $chain $index -EvaluationTime $evaluationTime).Valid | Should Be $true
        }

        It 'rejects different-claim T2 corroboration' {
            $chain = New-IssuedClaimChainFixture
            $chain.personaNeed.evidenceRefs = @('evidence-persona-t0','evidence-persona-t2')
            $chain.personaNeed.provenance = @('T0','T2')
            $index = @(New-IssuedRecordIndexFixture -Chain $chain)
            $index += New-EvidenceRecord 'evidence-persona-t2' 'persona-fit' 'T2' 'candidate-t0' -Fields @{ subjectRef = 'manifest-synthetic-1'; personaId = 'persona-engineering-synthetic'; capacityWaterfallPointer = 'verdict-synthetic-1#/personaVerdicts/0/capacityWaterfall'; evidenceReleaseRef = 'persona-release-synthetic-1'; coverageStatus = 'PASS'; freshnessBinding = New-SourceFreshnessBinding $chain.personaNeed.freshness }
            ($index | Where-Object recordId -eq 'persona-release-synthetic-1').payload.memberRecordIds += 'evidence-persona-t2'
            Update-ClaimSemanticBinding $chain $index
            (@((Test-LeadershipClaimChain $chain $index -EvaluationTime $evaluationTime).ReasonCodes) -contains 'T2_CORROBORATION_MISMATCH') | Should Be $true
        }

        It 'rejects T2 corroboration absent from the same evidence release' {
            $chain = New-IssuedClaimChainFixture
            $chain.personaNeed.evidenceRefs = @('evidence-persona-t0','evidence-persona-t2')
            $chain.personaNeed.provenance = @('T0','T2')
            $index = @(New-IssuedRecordIndexFixture -Chain $chain)
            $index += New-EvidenceRecord 'evidence-persona-t2' 'persona-fit' 'T2' 'evidence-persona-t0' -Fields @{ subjectRef = 'manifest-synthetic-1'; personaId = 'persona-engineering-synthetic'; capacityWaterfallPointer = 'verdict-synthetic-1#/personaVerdicts/0/capacityWaterfall'; evidenceReleaseRef = 'persona-release-synthetic-1'; coverageStatus = 'PASS'; freshnessBinding = New-SourceFreshnessBinding $chain.personaNeed.freshness }
            $release = $index | Where-Object recordId -eq 'persona-release-synthetic-1'
            $release.payload.memberRecordIds = @('evidence-persona-t2','distribution-persona-synthetic-1')
            Update-CanonicalRecordBinding $release
            Update-ClaimSemanticBinding $chain $index
            (@((Test-LeadershipClaimChain $chain $index -EvaluationTime $evaluationTime).ReasonCodes) -contains 'T2_CORROBORATION_NOT_IN_RELEASE') | Should Be $true
        }

        It 'rejects any missing leadership link' -TestCases @(
            @{ Field = 'personaNeed'; Code = 'MISSING_PERSONA_NEED' },
            @{ Field = 'currentFleetIssue'; Code = 'MISSING_CURRENT_FLEET_ISSUE' },
            @{ Field = 'candidateComparison'; Code = 'MISSING_CANDIDATE_COMPARISON' },
            @{ Field = 'businessEffect'; Code = 'MISSING_BUSINESS_EFFECT' },
            @{ Field = 'recommendation'; Code = 'MISSING_RECOMMENDATION' }
        ) {
            param($Field, $Code)
            $chain = New-IssuedClaimChainFixture
            $chain.$Field = $null
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.$Field = $null
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects a derived document used as evidence' {
            $chain = New-IssuedClaimChainFixture
            $chain.currentFleetIssue.evidenceRefs = @('g2a-leadership-brief.md')
            (@((Test-LeadershipClaimChain $chain (New-IssuedRecordIndexFixture -Chain $chain) -EvaluationTime $evaluationTime).ReasonCodes) -contains 'DERIVED_DOCUMENT_AS_EVIDENCE') | Should Be $true
        }

        It 'rejects T2-only support for a decision link' {
            $chain = New-IssuedClaimChainFixture
            $chain.personaNeed.evidenceRefs = @('evidence-persona-t2')
            $chain.personaNeed.provenance = @('T2')
            $index = @(New-IssuedRecordIndexFixture -Chain $chain)
            $index += New-EvidenceRecord 'evidence-persona-t2' 'persona-fit' 'T2' 'evidence-persona-t0' -Fields @{ subjectRef = 'manifest-synthetic-1'; personaId = 'persona-engineering-synthetic'; capacityWaterfallPointer = 'verdict-synthetic-1#/personaVerdicts/0/capacityWaterfall'; evidenceReleaseRef = 'persona-release-synthetic-1'; coverageStatus = 'PASS'; freshnessBinding = New-SourceFreshnessBinding $chain.personaNeed.freshness }
            ($index | Where-Object recordId -eq 'persona-release-synthetic-1').payload.memberRecordIds = @('evidence-persona-t2')
            Update-ClaimSemanticBinding $chain $index
            (@((Test-LeadershipClaimChain $chain $index -EvaluationTime $evaluationTime).ReasonCodes) -contains 'T2_ONLY_DECISION_SUPPORT') | Should Be $true
        }

        It 'rejects a caller-supplied CURRENT freshness label' {
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.currentFleetIssue.freshness = 'CURRENT'
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'LEADERSHIP_FRESHNESS_BINDING_REQUIRED') | Should Be $true
        }

        It 'rejects ancient evidence even after its payload, attestation, and observation window are reissued' {
            $fixture = New-IssuedClaimFixture
            Set-LinkAndSourceFreshnessTimes $fixture.Chain $fixture.RecordIndex 'currentFleetIssue' '2020-01-01T00:00:00Z' '2026-08-27T09:00:00Z'
            $fixture.Chain.currentFleetIssue.observationWindow = '2019-01-01/2020-01-01'
            foreach ($recordId in @('evidence-incumbent-t0', 'incident-release-t0')) {
                $record = @($fixture.RecordIndex | Where-Object recordId -eq $recordId)[0]
                $record.payload.observationWindow = '2019-01-01/2020-01-01'
                Update-CanonicalRecordBinding $record
            }
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'STALE_LEADERSHIP_LINK') | Should Be $true
        }

        It 'rejects invalid admission and evaluation chronology' -TestCases @(
            @{ AdmittedAt = '2026-08-27T12:01:00Z'; EvaluatedAt = '2026-08-27T12:00:00Z' },
            @{ AdmittedAt = '2026-08-27T10:00:00Z'; EvaluatedAt = '2026-08-27T12:01:00Z' }
        ) {
            param($AdmittedAt, $EvaluatedAt)
            $fixture = New-IssuedClaimFixture
            Set-LinkAndSourceFreshnessTimes $fixture.Chain $fixture.RecordIndex 'personaNeed' '2026-08-25T09:00:00Z' $AdmittedAt $EvaluatedAt
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FRESHNESS_CHRONOLOGY_INVALID') | Should Be $true
        }

        It 'rejects freshness timestamps from the future' {
            $fixture = New-IssuedClaimFixture
            Set-LinkAndSourceFreshnessTimes $fixture.Chain $fixture.RecordIndex 'personaNeed' '2026-08-27T12:31:00Z' '2026-08-27T12:31:00Z'
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FRESHNESS_CHRONOLOGY_INVALID') | Should Be $true
        }

        It 'accepts the exact freshness-age boundary and rejects one second beyond it' -TestCases @(
            @{ ObservedAt = '2026-07-28T12:30:00Z'; ExpectedValid = $true },
            @{ ObservedAt = '2026-07-28T12:29:59Z'; ExpectedValid = $false }
        ) {
            param($ObservedAt, $ExpectedValid)
            $fixture = New-IssuedClaimFixture
            Set-LinkAndSourceFreshnessTimes $fixture.Chain $fixture.RecordIndex 'personaNeed' $ObservedAt '2026-08-27T10:00:00Z'
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $ExpectedValid
            $result.Allowed | Should Be $false
            if (-not $ExpectedValid) { (@($result.ReasonCodes) -contains 'STALE_LEADERSHIP_LINK') | Should Be $true }
        }

        It 'rejects a max-age value that differs from its canonical policy pointer' {
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.personaNeed.freshness.maxAgeDays = 31
            foreach ($recordId in @(Get-FreshnessSourceRecordIds $fixture.Chain 'personaNeed')) {
                $record = @($fixture.RecordIndex | Where-Object recordId -eq $recordId)[0]
                $record.payload.freshnessBinding.maxAgeDays = 31
                Update-CanonicalRecordBinding $record
            }
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FRESHNESS_POLICY_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects a link redirected to another canonical max-age policy' {
            $fixture = New-IssuedClaimFixture
            $wrongPolicyRef = 'freshness-policy-synthetic-1#/leadershipFreshness/businessEffect'
            $fixture.Chain.personaNeed.freshness.policyRef = $wrongPolicyRef
            foreach ($recordId in @(Get-FreshnessSourceRecordIds $fixture.Chain 'personaNeed')) {
                $record = @($fixture.RecordIndex | Where-Object recordId -eq $recordId)[0]
                $record.payload.freshnessBinding.policyRef = $wrongPolicyRef
                Update-CanonicalRecordBinding $record
            }
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FRESHNESS_POLICY_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects an alternate wider threshold-policy record even when sources bind its recomputed digest' {
            $fixture = New-IssuedClaimFixture
            $original = @($fixture.RecordIndex | Where-Object recordId -ceq 'freshness-policy-synthetic-1')[0]
            $alternateFields = @{
                leadershipFreshness = Copy-TestObject -InputObject $original.payload.leadershipFreshness
                extensions = Copy-TestObject -InputObject $original.payload.extensions
                thresholds = Copy-TestObject -InputObject $original.payload.thresholds
            }
            $alternateFields.leadershipFreshness.personaNeed.maxAgeDays = 3650
            $alternate = New-CanonicalRecord 'freshness-policy-alternate-synthetic-1' 'threshold-policy' @(
                '/leadershipFreshness/personaNeed','/leadershipFreshness/currentFleetIssue',
                '/leadershipFreshness/candidateComparison','/leadershipFreshness/businessEffect',
                '/leadershipFreshness/recommendation','/extensions/leadershipFreshness/currentFleetIssue',
                '/extensions/leadershipFreshness/currentFleetIssue/maxAgeDays','/thresholds/minTelemetryCoveragePct/value'
            ) -Fields $alternateFields
            $fixture.RecordIndex += $alternate
            $alternateRef = "$($alternate.recordId)#/leadershipFreshness/personaNeed"
            $fixture.Chain.personaNeed.freshness.policyRef = $alternateRef
            $fixture.Chain.personaNeed.freshness.maxAgeDays = 3650
            foreach ($recordId in @(Get-FreshnessSourceRecordIds $fixture.Chain 'personaNeed')) {
                $record = @($fixture.RecordIndex | Where-Object recordId -ceq $recordId)[0]
                $record.payload.freshnessBinding.policyRef = $alternateRef
                $record.payload.freshnessBinding.maxAgeDays = 3650
                Update-CanonicalRecordBinding $record
            }
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $codes = @((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime -ValidationProfile TEST).ReasonCodes)
            ($codes -contains 'FRESHNESS_POLICY_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects link timestamps that do not summarize the oldest observation and latest admission' -TestCases @(
            @{ Field = 'observedAt'; Value = '2026-08-26T09:00:00Z' },
            @{ Field = 'admittedAt'; Value = '2026-08-27T09:59:59Z' }
        ) {
            param($Field, $Value)
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.personaNeed.freshness.$Field = $Value
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FRESHNESS_SOURCE_SUMMARY_MISMATCH') | Should Be $true
        }

        It 'rejects a measured business source without its freshness binding' {
            $fixture = New-IssuedClaimFixture
            $record = @($fixture.RecordIndex | Where-Object recordId -eq 'business-impact-synthetic-1')[0]
            $record.payload.PSObject.Properties.Remove('freshnessBinding')
            Update-CanonicalRecordBinding $record
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'SOURCE_FRESHNESS_BINDING_REQUIRED') | Should Be $true
        }

        It 'rejects every changed platform dependency dimension even after the snapshot is re-digested' -TestCases @(
            @{ Field = 'windowsBuild'; Value = '26100.10000' },
            @{ Field = 'biosVersion'; Value = 'BIOS-SYNTHETIC-2' },
            @{ Field = 'driverPackVersion'; Value = 'DRIVER-PACK-SYNTHETIC-2' },
            @{ Field = 'corporateImageVersion'; Value = 'IMAGE-SYNTHETIC-2' },
            @{ Field = 'securityAgentSetDigest'; Value = (New-TestDigest '8') },
            @{ Field = 'conditionSetDigest'; Value = (New-TestDigest '9') },
            @{ Field = 'testPackVersion'; Value = 'test-pack-synthetic-2' }
        ) {
            param($Field, $Value)
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.personaNeed.freshness.dependencySnapshot.$Field = $Value
            $changedDigest = Get-CanonicalPayloadDigest -Payload $fixture.Chain.personaNeed.freshness.dependencySnapshot
            $fixture.Chain.personaNeed.freshness.dependencySnapshotDigest = $changedDigest
            foreach ($recordId in @(Get-FreshnessSourceRecordIds $fixture.Chain 'personaNeed')) {
                $record = @($fixture.RecordIndex | Where-Object recordId -eq $recordId)[0]
                $record.payload.freshnessBinding.dependencySnapshotDigest = $changedDigest
                Update-CanonicalRecordBinding $record
            }
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FRESHNESS_DEPENDENCY_MISMATCH') | Should Be $true
        }

        It 'rejects a dependency snapshot digest that does not match the structured snapshot' {
            $fixture = New-IssuedClaimFixture
            $fixture.Chain.personaNeed.freshness.dependencySnapshotDigest = New-TestDigest '9'
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'FRESHNESS_DEPENDENCY_DIGEST_MISMATCH') | Should Be $true
        }

        It 'rejects dependency drift in either an evidence source or its evidence release' -TestCases @(
            @{ RecordId = 'evidence-persona-t0' },
            @{ RecordId = 'persona-release-synthetic-1' }
        ) {
            param($RecordId)
            $fixture = New-IssuedClaimFixture
            $record = @($fixture.RecordIndex | Where-Object recordId -eq $RecordId)[0]
            $record.payload.freshnessBinding.dependencyStatus = 'MISMATCH'
            Update-CanonicalRecordBinding $record
            Update-ClaimSemanticBinding $fixture.Chain $fixture.RecordIndex
            $result = Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'SOURCE_FRESHNESS_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects decision links smuggled into the frozen NOT_ISSUED template' {
            $chain = Get-Content $chainPath -Raw | ConvertFrom-Json
            $chain.personaNeed = [pscustomobject]@{ personaId = 'forged' }
            (@((Test-LeadershipClaimChain $chain -EvaluationTime $evaluationTime).ReasonCodes) -contains 'UNISSUED_DECISION_LINK_PRESENT') | Should Be $true
        }

        It 'rejects unexpected claim-chain fields' {
            $fixture = New-IssuedClaimFixture
            $fixture.Chain | Add-Member -NotePropertyName hiddenRecommendation -NotePropertyValue 'BUY'
            (@((Test-LeadershipClaimChain $fixture.Chain $fixture.RecordIndex -EvaluationTime $evaluationTime).ReasonCodes) -contains 'UNEXPECTED_CONTRACT_FIELD') | Should Be $true
        }
    }

    Context 'Public Intune activation policy evaluation' {
        It 'keeps complete pilot and production requests behind the private implementation' -TestCases @(
            @{ Stage = 'PILOT' }, @{ Stage = 'PRODUCTION' }
        ) {
            param($Stage)
            $result = Invoke-TestActivation -Stage $Stage -Readback (New-ReadbackFixture -Stage $Stage)
            $result.State | Should Be 'TEST_FIXTURE_BLOCKED_NON_PROMOTABLE'
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'CONTROL_PLANE_NOT_ACTIVE') | Should Be $true
            (@($result.ReasonCodes) -contains 'PRIVATE_ACTIVATION_IMPLEMENTATION_REQUIRED') | Should Be $true
            if ($Stage -eq 'PRODUCTION') {
                @($result.ReasonCodes | Where-Object { $_ -like 'ROLLOUT_MONITORING_*' }).Count | Should Be 0
                (@($result.ReasonCodes) -contains 'MISSING_REQUIRED_FIELD') | Should Be $false
            }
        }

        It 'never promotes TEST fixtures and rejects fixture references in the PRODUCTION profile' {
            $scenario = New-ActivationScenarioFixture 'PRODUCTION'
            $testResult = Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback
            $testResult.State | Should Be 'TEST_FIXTURE_BLOCKED_NON_PROMOTABLE'
            $testResult.Allowed | Should Be $false

            $record = $scenario.RecordIndex | Where-Object recordId -eq 'package-verification-synthetic-1'
            $record.immutableArtifactRef = 'fixture://package/verification-synthetic-1'
            $record.attestationRef = 'fixture://package/attestation-synthetic-1'
            Update-CanonicalRecordBinding $record
            $productionResult = Get-ActivationDecision -Request $scenario.Request -Registry (Get-CheckedRegistry) -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback -EvaluationTime $evaluationTime -ValidationProfile PRODUCTION
            $productionResult.Allowed | Should Be $false
            (@($productionResult.ReasonCodes) -contains 'FIXTURE_RECORD_FORBIDDEN_IN_PRODUCTION') | Should Be $true
        }

        It 'never treats missing readback as write authorization' {
            $result = Invoke-TestActivation
            $result.State | Should Be 'TEST_FIXTURE_BLOCKED_NON_PROMOTABLE'
            (@($result.ReasonCodes) -contains 'PRIVATE_ACTIVATION_IMPLEMENTATION_REQUIRED') | Should Be $true
        }

        It 'rejects a promotion ring that is invalid for the requested stage' -TestCases @(
            @{ Stage = 'PILOT'; TargetRing = 'PERSONA_QUALIFIED' },
            @{ Stage = 'PRODUCTION'; TargetRing = 'AUTHORIZED_PILOT' }
        ) {
            param($Stage, $TargetRing)
            $request = New-ActivationRequestFixture $Stage
            $request.targetRing = $TargetRing
            $result = Invoke-TestActivation -Request $request
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'TARGET_RING_INVALID') | Should Be $true
        }

        It 'blocks a pilot without Phase 2 approval' {
            $request = New-ActivationRequestFixture
            $request.authorization.phase2Status = 'HOLD'
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'PHASE2_NOT_APPROVED') | Should Be $true
        }

        It 'rejects Phase 2 approval-role collapse and stale gate evidence' -TestCases @(
            @{ Target = 'role-collapse'; Code = 'PHASE2_APPROVAL_SEPARATION_INVALID' },
            @{ Target = 'test-pack'; Code = 'PILOT_GATE_EVIDENCE_BINDING_MISMATCH' }
        ) {
            param($Target, $Code)
            $index = @(New-ActivationRecordIndexFixture)
            if ($Target -eq 'role-collapse') {
                $record = $index | Where-Object recordId -eq 'phase2-approval-synthetic-1'
                $record.payload.securityApproval.principalRef = $record.payload.compatibilityApproval.principalRef
            }
            else {
                $record = $index | Where-Object recordId -eq 'phase2-release-synthetic-1'
                $record.payload.testPackVersion = 'test-pack-stale-synthetic-1'
            }
            Update-CanonicalRecordBinding $record
            $result = Invoke-TestActivation -RecordIndex $index -Readback (New-ReadbackFixture)
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects Phase 3, stop-set, and rollback approvals outside the gated pilot chronology' -TestCases @(
            @{ Target = 'phase3'; Code = 'PHASE3_VERDICT_RECORD_MISMATCH' },
            @{ Target = 'stop'; Code = 'STOP_CONDITIONS_RECORD_MISMATCH' },
            @{ Target = 'rollback'; Code = 'ROLLBACK_RECORD_MISMATCH' }
        ) {
            param($Target, $Code)
            $scenario = New-ActivationScenarioFixture -Stage PILOT
            if ($Target -eq 'phase3') {
                $record = @($scenario.RecordIndex | Where-Object recordId -eq 'phase3-verdict-synthetic-1')[0]
                $record.payload.immutableAt = '2026-08-27T11:39:00Z'
                $record.payload.issuedAt = '2026-08-27T11:39:00Z'
            }
            elseif ($Target -eq 'stop') {
                $record = @($scenario.RecordIndex | Where-Object recordId -eq 'stop-plan-synthetic-1')[0]
                $record.payload.approvedAt = '2026-08-27T11:56:00Z'
            }
            else {
                $record = @($scenario.RecordIndex | Where-Object recordId -eq 'rollback-synthetic-1')[0]
                $record.payload.approvedAt = '2026-08-27T11:56:00Z'
            }
            Update-CanonicalRecordBinding $record
            $result = Invoke-TestActivation -Stage PILOT -Request $scenario.Request -RecordIndex $scenario.RecordIndex
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects a Phase 3 verdict that is not an immutable qualifying provisional verdict' {
            $index = @(New-ActivationRecordIndexFixture)
            $record = $index | Where-Object recordId -eq 'phase3-verdict-synthetic-1'
            $record.payload.provisionalLabVerdict = 'HOLD'
            Update-CanonicalRecordBinding $record
            (@((Invoke-TestActivation -RecordIndex $index -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'PHASE3_VERDICT_RECORD_MISMATCH') | Should Be $true
        }

        It 'rejects target ceilings, composition, group rules, and assignment filters that diverge from directory readback' -TestCases @(
            @{ Target = 'ceiling'; Code = 'TARGET_POPULATION_LIMIT_OR_COMPOSITION_INVALID' },
            @{ Target = 'group'; Code = 'DIRECTORY_TARGET_POPULATION_READBACK_MISMATCH' },
            @{ Target = 'filter'; Code = 'DIRECTORY_TARGET_POPULATION_READBACK_MISMATCH' }
        ) {
            param($Target, $Code)
            $scenario = New-ActivationScenarioFixture
            if ($Target -eq 'ceiling') { $scenario.Request.targetPopulation.targetPopulationCount = 31 }
            else {
                $directory = $scenario.RecordIndex | Where-Object recordId -eq 'directory-readback-synthetic-1'
                if ($Target -eq 'group') { $directory.payload.groupMembershipRuleDigest = New-TestDigest 'e' }
                else { $directory.payload.assignmentFilterDigest = New-TestDigest 'e' }
                Update-CanonicalRecordBinding $directory
            }
            $result = Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects empty stop sets and non-executable member conditions' -TestCases @(
            @{ Target = 'empty'; Code = 'STOP_CONDITIONS_RECORD_MISMATCH' },
            @{ Target = 'unsafe'; Code = 'STOP_CONDITION_NOT_EXECUTABLE' }
        ) {
            param($Target, $Code)
            $index = @(New-ActivationRecordIndexFixture)
            if ($Target -eq 'empty') {
                $record = $index | Where-Object recordId -eq 'stop-plan-synthetic-1'
                $record.payload.conditionRefs = @()
                $record.payload.conditionCount = 0
            }
            else {
                $record = $index | Where-Object recordId -eq 'stop-condition-synthetic-1'
                $record.payload.missingDisposition = 'PASS'
            }
            Update-CanonicalRecordBinding $record
            (@((Invoke-TestActivation -RecordIndex $index -Readback (New-ReadbackFixture)).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects rollback that points at the current package instead of a prior known-good state' {
            $scenario = New-ActivationScenarioFixture
            $rollback = $scenario.RecordIndex | Where-Object recordId -eq 'rollback-synthetic-1'
            $rollback.payload.priorKnownGoodPackageDigest = $scenario.Request.packageDigest
            Update-CanonicalRecordBinding $rollback
            $codes = @((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes)
            (($codes -contains 'ROLLBACK_RECORD_MISMATCH') -or ($codes -contains 'ROLLBACK_PRIOR_KNOWN_GOOD_INVALID')) | Should Be $true
        }

        It 'rejects invalid package signature, timestamp, revocation, and verifier independence' -TestCases @(
            @{ Field = 'signatureStatus'; Value = 'INVALID' },
            @{ Field = 'timestampStatus'; Value = 'INVALID' },
            @{ Field = 'certificateRevocationStatus'; Value = 'REVOKED' },
            @{ Field = 'verifierIdentityRef'; Value = 'private://identities/package-signer-synthetic-1' }
        ) {
            param($Field, $Value)
            $index = @(New-ActivationRecordIndexFixture)
            $record = $index | Where-Object recordId -eq 'package-verification-synthetic-1'
            $record.payload.$Field = $Value
            Update-CanonicalRecordBinding $record
            (@((Invoke-TestActivation -RecordIndex $index -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'PACKAGE_VERIFICATION_BINDING_INVALID') | Should Be $true
        }

        It 'blocks an object type without an approved transport owner' {
            $request = New-ActivationRequestFixture
            $request.transportSelectionStatus = 'UNKNOWN'
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'TRANSPORT_OWNERSHIP_NOT_APPROVED') | Should Be $true
        }

        It 'treats the checked-in empty ownership registry as an activation blocker' {
            (@((Invoke-TestActivation -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'TRANSPORT_OWNERSHIP_MAP_EMPTY') | Should Be $true
        }

        It 'rejects an unbounded or unauthorized transport ownership entry' {
            $entry = [pscustomobject]@{
                managedObjectType = 'deviceManagementConfigurationPolicy'
                targetScopeRef = 'all-devices'
                writerToolRef = 'ansible'
                selectionStatus = 'APPROVED_OBJECT_TYPE_OWNER'
            }
            $registry = New-TransportRegistryFixture @($entry)
            (@((Invoke-TestActivation -Registry $registry -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'TRANSPORT_OWNERSHIP_ENTRY_INVALID') | Should Be $true
        }

        It 'rejects overlapping transport owners for the same object type and scope' {
            $entry = [pscustomobject]@{
                managedObjectType = 'deviceManagementConfigurationPolicy'
                targetScopeRef = 'private://rings/ring-synthetic-1'
                writerToolRef = 'msgraph-terraform-provider'
                selectionStatus = 'APPROVED_OBJECT_TYPE_OWNER'
            }
            $registry = New-TransportRegistryFixture @($entry, (Copy-TestObject $entry))
            (@((Invoke-TestActivation -Registry $registry -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'TRANSPORT_OWNERSHIP_OVERLAP') | Should Be $true
        }

        It 'rejects an ownership map that does not own the requested object and scope' {
            $entry = [pscustomobject]@{
                managedObjectType = 'deviceCompliancePolicy'
                targetScopeRef = 'private://rings/ring-other'
                writerToolRef = 'msgraph-terraform-provider'
                selectionStatus = 'APPROVED_OBJECT_TYPE_OWNER'
            }
            $registry = New-TransportRegistryFixture @($entry)
            (@((Invoke-TestActivation -Registry $registry -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'TRANSPORT_OWNERSHIP_RECORD_MISMATCH') | Should Be $true
        }

        It 'requires a private unexpired exception for direct Graph writes' {
            $request = New-ActivationRequestFixture
            $request.writerToolRef = 'microsoft-graph-write'
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'DIRECT_GRAPH_EXCEPTION_INVALID') | Should Be $true
        }

        It 'rejects direct Graph exceptions missing owner, closure, or compensating controls' -TestCases @(
            @{ Field = 'ownerPrincipalRef' }, @{ Field = 'closureEvidenceRef' }, @{ Field = 'compensatingControlRefs' }
        ) {
            param($Field)
            $scenario = New-DirectGraphExceptionScenario
            $exception = $scenario.RecordIndex | Where-Object recordId -eq 'private://exceptions/graph-synthetic-1'
            $exception.payload.PSObject.Properties.Remove($Field)
            $codes = @((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex).ReasonCodes)
            ($codes -contains 'MISSING_REQUIRED_FIELD') | Should Be $true
            (($codes -contains 'DIRECT_GRAPH_EXCEPTION_RECORD_MISMATCH') -or
                ($codes -contains 'DIRECT_GRAPH_EXCEPTION_BINDING_MISMATCH')) | Should Be $true
        }

        It 'rejects a direct Graph compensating control bound to another exception' {
            $scenario = New-DirectGraphExceptionScenario
            $control = $scenario.RecordIndex | Where-Object recordId -eq 'graph-compensating-control-synthetic-1'
            $control.payload.sourceExceptionRef = 'private://exceptions/another-exception'
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex).ReasonCodes) -contains 'DIRECT_GRAPH_COMPENSATING_CONTROL_INVALID') | Should Be $true
        }

        It 'rejects a re-digested direct Graph exception whose content no longer matches the issued digest' {
            $scenario = New-DirectGraphExceptionScenario
            $scenario.ExceptionRecord.payload.reason = 'Adversarial content swap after the exception was bound.'
            Update-CanonicalRecordBinding $scenario.ExceptionRecord
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex).ReasonCodes) -contains 'DIRECT_GRAPH_EXCEPTION_BINDING_MISMATCH') | Should Be $true
        }

        It 'forbids direct Graph exception fields on the Terraform-provider path' {
            $scenario = New-ActivationScenarioFixture
            $scenario.Request | Add-Member -NotePropertyName transportExceptionRef -NotePropertyValue 'private://exceptions/forbidden-on-provider'
            $scenario.Request | Add-Member -NotePropertyName transportExceptionDigest -NotePropertyValue (New-TestDigest 'f')
            $scenario.Request | Add-Member -NotePropertyName transportExceptionExpiresAt -NotePropertyValue '2026-08-28T00:00:00Z'
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains 'DIRECT_GRAPH_EXCEPTION_FORBIDDEN') | Should Be $true
        }

        It 'binds the approval set to the exact scope and reviewed plan' {
            $request = New-ActivationRequestFixture
            $request.approvalSetScopeRef = 'ring-other'
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'APPROVAL_SET_BINDING_MISMATCH') | Should Be $true
        }

        It 'requires source commit and policy-result digest in every reviewed plan' -TestCases @(
            @{ Field = 'sourceCommit' }, @{ Field = 'policyResultsDigest' }
        ) {
            param($Field)
            $index = @(New-ActivationRecordIndexFixture)
            ($index | Where-Object recordId -eq 'private://plans/reviewed-plan-synthetic-1').payload.PSObject.Properties.Remove($Field)
            (@((Invoke-TestActivation -RecordIndex $index -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'MISSING_REQUIRED_FIELD') | Should Be $true
        }

        It 'requires every governed monitoring binding in stop conditions' -TestCases @(
            @{ Field = 'monitoringQueryPackRef' },
            @{ Field = 'monitoringQueryPackDigest' },
            @{ Field = 'telemetryBaselineRef' },
            @{ Field = 'coveragePolicyRef' },
            @{ Field = 'thresholdPolicyRef' },
            @{ Field = 'cadenceMinutes' },
            @{ Field = 'alertOwnerRole' }
        ) {
            param($Field)
            $index = @(New-ActivationRecordIndexFixture)
            $stop = $index | Where-Object recordId -eq 'stop-plan-synthetic-1'
            $stop.payload.PSObject.Properties.Remove($Field)
            Update-CanonicalRecordBinding $stop
            $result = Invoke-TestActivation -RecordIndex $index
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'MISSING_REQUIRED_FIELD') | Should Be $true
        }

        It 'rejects typed activation records that diverge from the request' -TestCases @(
            @{ RecordId = 'private://transport/ownership-synthetic-1'; Field = 'targetScopeRef'; Value = 'private://rings/other'; Code = 'TRANSPORT_OWNERSHIP_RECORD_MISMATCH' },
            @{ RecordId = 'private://plans/reviewed-plan-synthetic-1'; Field = 'managedObjectType'; Value = 'deviceCompliancePolicy'; Code = 'REVIEWED_PLAN_RECORD_MISMATCH' },
            @{ RecordId = 'private://plans/reviewed-plan-synthetic-1'; Field = 'targetRing'; Value = 'BROAD'; Code = 'REVIEWED_PLAN_RECORD_MISMATCH' },
            @{ RecordId = 'private://approvals/approval-synthetic-1'; Field = 'planDigest'; Value = 'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'; Code = 'APPROVAL_RECORD_BINDING_MISMATCH' },
            @{ RecordId = 'private://operations/write-operation-synthetic-1'; Field = 'writerToolRef'; Value = 'microsoft-graph-write'; Code = 'WRITE_OPERATION_RECORD_MISMATCH' },
            @{ RecordId = 'readback-synthetic-1'; Field = 'managedObjectType'; Value = 'deviceCompliancePolicy'; Code = 'READBACK_RECORD_BINDING_MISMATCH' }
        ) {
            param($RecordId, $Field, $Value, $Code)
            $index = @(New-ActivationRecordIndexFixture)
            ($index | Where-Object recordId -eq $RecordId).payload.$Field = $Value
            (@((Invoke-TestActivation -RecordIndex $index -Readback (New-ReadbackFixture)).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects request digests that do not bind the retained transport, plan, or approval' -TestCases @(
            @{ Field = 'transportOwnershipRecordDigest'; Code = 'TRANSPORT_OWNERSHIP_RECORD_MISMATCH' },
            @{ Field = 'reviewedPlanDigest'; Code = 'REVIEWED_PLAN_RECORD_MISMATCH' },
            @{ Field = 'approvalRecordDigest'; Code = 'APPROVAL_RECORD_BINDING_MISMATCH' }
        ) {
            param($Field, $Code)
            $request = New-ActivationRequestFixture
            $request.$Field = New-TestDigest 'b'
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'requires every stage-specific approval role' -TestCases @(
            @{ Stage = 'PILOT'; Role = 'ROLE_PRIVACY_APPROVER' },
            @{ Stage = 'PRODUCTION'; Role = 'ROLE_PROCUREMENT_APPROVER' }
        ) {
            param($Stage, $Role)
            $request = New-ActivationRequestFixture $Stage
            $request.approvalRoleIds = @($request.approvalRoleIds | Where-Object { $_ -ne $Role })
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'APPROVAL_ROLE_MISSING') | Should Be $true
        }

        It 'rejects duplicate approval roles' {
            $request = New-ActivationRequestFixture
            $request.approvalRoleIds += 'ROLE_PRIVACY_APPROVER'
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'DUPLICATE_APPROVAL_ROLE') | Should Be $true
        }

        It 'blocks fleet HOLD and persona FAIL verdicts' -TestCases @(
            @{ Field = 'fleetVerdict'; Value = 'HOLD'; Code = 'FLEET_VERDICT_BLOCKS' },
            @{ Field = 'personaVerdict'; Value = 'FAIL'; Code = 'PERSONA_VERDICT_BLOCKS' }
        ) {
            param($Field, $Value, $Code)
            $request = New-ActivationRequestFixture 'PRODUCTION'
            $request.authorization.$Field = $Value
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'blocks unknown identity at pilot and production' -TestCases @(
            @{ Stage = 'PILOT' }, @{ Stage = 'PRODUCTION' }
        ) {
            param($Stage)
            $request = New-ActivationRequestFixture $Stage
            $request.authorization.componentIdentityStatus = 'UNKNOWN'
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'UNKNOWN_COMPONENT_IDENTITY') | Should Be $true
        }

        It 'blocks incomplete delta qualification' {
            $request = New-ActivationRequestFixture 'PRODUCTION'
            $request.authorization.deltaQualificationStatus = 'UNKNOWN'
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'DELTA_QUALIFICATION_NOT_COMPLETE') | Should Be $true
        }

        It 'blocks a conditional verdict without current bindings' {
            $request = New-ActivationRequestFixture
            $request.authorization.conditionsStatus = 'MISSING'
            $request.authorization.conditionRecordRefs = @()
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'CONDITIONAL_VERDICT_BINDING_MISSING') | Should Be $true
        }

        It 'blocks an expired condition record' {
            $index = New-ActivationRecordIndexFixture
            ($index | Where-Object recordId -eq 'condition-synthetic-1').payload.expiresAt = '2026-08-27T12:29:00Z'
            (@((Invoke-TestActivation -RecordIndex $index -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'CONDITIONAL_VERDICT_BINDING_INVALID') | Should Be $true
        }

        It 'rejects a conditional verdict retained for another ring or persona' -TestCases @(
            @{ Field = 'targetScopeRef'; Value = 'private://rings/other' },
            @{ Field = 'personaId'; Value = 'persona-finance-synthetic' }
        ) {
            param($Field, $Value)
            $index = @(New-ActivationRecordIndexFixture)
            ($index | Where-Object recordId -eq 'condition-synthetic-1').payload.$Field = $Value
            (@((Invoke-TestActivation -RecordIndex $index -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'CONDITIONAL_VERDICT_BINDING_INVALID') | Should Be $true
        }

        It 'rejects a production procurement pointer outside its final verdict envelope' {
            $request = New-ActivationRequestFixture 'PRODUCTION'
            $request.authorization.procurementEnvelopeRef = 'activation-verdict-synthetic-1#/personaVerdicts/0'
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'PROCUREMENT_ENVELOPE_VERDICT_MISMATCH') | Should Be $true
        }

        It 'rejects a production rollout-monitoring reference without its canonical record' {
            $scenario = New-ProductionActivationScenario
            $scenario.RecordIndex = @($scenario.RecordIndex | Where-Object recordId -ne 'rollout-monitoring-synthetic-1')
            $result = Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'UNRESOLVED_RECORD_REF') | Should Be $true
        }

        It 'requires rollout monitoring fields on every production request' {
            $request = New-ActivationRequestFixture 'PRODUCTION'
            $request.PSObject.Properties.Remove('rolloutMonitoringRef')
            $request.PSObject.Properties.Remove('rolloutMonitoringRecordDigest')
            $result = Invoke-TestActivation -Request $request
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'ROLLOUT_MONITORING_REQUIRED') | Should Be $true
        }

        It 'rejects rollout monitoring retained for different decision inputs' {
            $scenario = New-ProductionActivationScenario
            $scenario.RolloutMonitoringRecord.payload.semanticInputDigest = New-TestDigest 'b'
            Update-RolloutMonitoringRequestBinding $scenario
            $result = Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'ROLLOUT_MONITORING_DECISION_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects rollout monitoring retained for a different reviewed plan' {
            $scenario = New-ProductionActivationScenario
            $scenario.RolloutMonitoringRecord.payload.atmosRenderDigest = New-TestDigest 'f'
            Update-RolloutMonitoringRequestBinding $scenario
            $result = Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'ROLLOUT_MONITORING_PLAN_BINDING_MISMATCH') | Should Be $true
        }

        It 'rejects a rollout query pack missing an independent required source' {
            $scenario = New-ProductionActivationScenario
            $scenario.RolloutMonitoringRecord.payload.queryPack.sourceToolRefs = @('microsoft-graph-readback')
            Update-RolloutMonitoringRequestBinding $scenario
            $result = Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'ROLLOUT_MONITORING_SOURCE_SET_INCOMPLETE') | Should Be $true
        }

        It 'rejects a rollout telemetry baseline outside its frozen freshness policy' {
            $scenario = New-ProductionActivationScenario
            $baseline = @($scenario.RecordIndex | Where-Object recordId -eq 'telemetry-baseline-synthetic-1')[0]
            $baseline.payload.observedAt = '2026-01-01T00:00:00Z'
            $baseline.payload.freshnessBinding.observedAt = '2026-01-01T00:00:00Z'
            $baseline.payload.freshnessBinding.admittedAt = '2026-01-01T00:05:00Z'
            Update-CanonicalRecordBinding $baseline
            $scenario.RolloutMonitoringRecord.payload.telemetryBaselineDigest = $baseline.contentDigest
            Update-RolloutMonitoringRequestBinding $scenario
            $result = Invoke-TestActivation -Stage PRODUCTION -Request $scenario.Request -RecordIndex $scenario.RecordIndex
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'ROLLOUT_MONITORING_BASELINE_FRESHNESS_INVALID') | Should Be $true
        }

        It 'rejects rollout coverage floors that differ from their frozen value or pointer' -TestCases @(
            @{ Target = 'value'; Code = 'ROLLOUT_MONITORING_THRESHOLD_BINDING_MISMATCH' },
            @{ Target = 'pointer'; Code = 'ROLLOUT_MONITORING_THRESHOLD_BINDING_MISMATCH' },
            @{ Target = 'invalid'; Code = 'ROLLOUT_MONITORING_COVERAGE_FLOOR_INVALID' }
        ) {
            param($Target, $Code)
            $scenario = New-ProductionActivationScenario
            $floor = $scenario.RolloutMonitoringRecord.payload.coverageFloors[0]
            if ($Target -eq 'value') { $floor.minimumCoveragePercent = 91 }
            elseif ($Target -eq 'pointer') { $floor.thresholdPointer = '#/monitoring/signals/fleetHealthThreshold' }
            else { $floor.minimumCoveragePercent = 0 }
            Update-RolloutMonitoringRequestBinding $scenario
            $result = Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects a rollout signal whose cadence exceeds its evaluation window' {
            $scenario = New-ProductionActivationScenario
            $scenario.RolloutMonitoringRecord.payload.signals[0].cadenceMinutes = 1441
            Update-RolloutMonitoringRequestBinding $scenario
            $result = Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'ROLLOUT_MONITORING_SIGNAL_INVALID') | Should Be $true
        }

        It 'requires all ten signal classes plus distinct primary and dead-man alert paths' -TestCases @(
            @{ Target = 'class'; Code = 'ROLLOUT_MONITORING_SIGNAL_CLASS_SET_INCOMPLETE' },
            @{ Target = 'deadman'; Code = 'ROLLOUT_ALERT_AND_DEADMAN_BINDING_INVALID' }
        ) {
            param($Target, $Code)
            $scenario = New-ProductionActivationScenario
            if ($Target -eq 'class') { $scenario.RolloutMonitoringRecord.payload.signals[9].signalClass = 'REVIEW_RESPONSE' }
            else { $scenario.RolloutMonitoringRecord.payload.independentDeadmanRef = $scenario.RolloutMonitoringRecord.payload.primaryAlertRef }
            Update-RolloutMonitoringRequestBinding $scenario
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects a NOT_APPLICABLE rollout signal without an exact scoped approval' {
            $scenario = New-ProductionActivationScenario
            $approval = @($scenario.RecordIndex | Where-Object recordId -eq 'private://approvals/approval-synthetic-1')[0]
            $scenario.RolloutMonitoringRecord.payload.signals[9] = [pscustomobject][ordered]@{
                signalClass = 'IAC_DRIFT'
                applicabilityStatus = 'NOT_APPLICABLE'
                ownerRole = 'ROLE_MONITORING_OWNER'
                approverRole = 'ROLE_QUALIFICATION_AUTHORITY'
                approvalRef = $approval.recordId
                approvalDigest = $approval.contentDigest
                rationale = 'Synthetic negative: approval retains the ordinary managed-object scope.'
                approvedAt = '2026-08-27T12:10:00Z'
                expiresAt = '2026-08-28T00:00:00Z'
            }
            Update-RolloutMonitoringRequestBinding $scenario
            $result = Invoke-TestActivation -Stage PRODUCTION -Request $scenario.Request -RecordIndex $scenario.RecordIndex
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'ROLLOUT_SIGNAL_NOT_APPLICABLE_INVALID') | Should Be $true
        }

        It 'rejects DO_NOT_BUY rollout activation and render-manifest output-attestation drift' -TestCases @(
            @{ Target = 'decision'; Code = 'ROLLOUT_MONITORING_DECISION_NOT_DETERMINISTIC' },
            @{ Target = 'render'; Code = 'RENDER_MANIFEST_BINDING_INVALID' }
        ) {
            param($Target, $Code)
            $scenario = New-ProductionActivationScenario
            if ($Target -eq 'decision') { $scenario.RolloutMonitoringRecord.payload.decisionAction = 'DO_NOT_BUY' }
            else {
                $render = $scenario.RecordIndex | Where-Object recordId -eq 'render-manifest-synthetic-1'
                $render.payload.outputArtifactAttestationDigest = New-TestDigest 'f'
                Update-CanonicalRecordBinding $render
            }
            Update-RolloutMonitoringRequestBinding $scenario
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects Atmos source-order, output, and plan bindings that are not exact' -TestCases @(
            @{ Target = 'source'; Code = 'ATMOS_STACK_RENDER_INVALID' },
            @{ Target = 'output'; Code = 'ROLLOUT_ATMOS_STACK_RENDER_MISMATCH' },
            @{ Target = 'plan'; Code = 'REVIEWED_PLAN_RECORD_MISMATCH' }
        ) {
            param($Target, $Code)
            $scenario = New-ProductionActivationScenario
            $atmos = $scenario.RecordIndex | Where-Object recordId -eq 'atmos-stack-render-synthetic-1'
            if ($Target -eq 'source') {
                $atmos.payload.orderedSourceBindings[1].order = 9
                Update-CanonicalRecordBinding $atmos
            }
            elseif ($Target -eq 'output') {
                $atmos.payload.renderedOutputDigest = New-TestDigest 'f'
                Update-CanonicalRecordBinding $atmos
            }
            else {
                $plan = $scenario.RecordIndex | Where-Object recordId -eq 'private://plans/reviewed-plan-synthetic-1'
                $plan.payload.atmosStackRenderDigest = New-TestDigest 'f'
                Update-CanonicalRecordBinding $plan
            }
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects a rollout plan that diverges from the approved stop-condition response plan' {
            $scenario = New-ProductionActivationScenario
            $stop = $scenario.RecordIndex | Where-Object recordId -eq 'stop-plan-synthetic-1'
            $stop.payload.monitoringQueryPackDigest = New-TestDigest 'f'
            Update-CanonicalRecordBinding $stop
            $result = Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex
            $result.Valid | Should Be $false
            $result.Allowed | Should Be $false
            (@($result.ReasonCodes) -contains 'ROLLOUT_MONITORING_RESPONSE_BINDING_MISMATCH') | Should Be $true
        }

        It 'requires one authoritative atomic authorization-consumption record' {
            $scenario = New-ActivationScenarioFixture
            $scenario.RecordIndex = @($scenario.RecordIndex | Where-Object recordId -ne 'authorization-consumption-synthetic-1')
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains 'AUTHORIZATION_CONSUMPTION_RECORD_REQUIRED') | Should Be $true
        }

        It 'rejects nonce replay, multiple use, revocation, object-set drift, and invalid consumption chronology' -TestCases @(
            @{ Target = 'duplicate'; Code = 'WRITE_AUTHORIZATION_REPLAY_OR_REUSE' },
            @{ Target = 'maxUses'; Code = 'PREWRITE_AUTHORIZATION_BINDING_INVALID' },
            @{ Target = 'revoked'; Code = 'PREWRITE_AUTHORIZATION_BINDING_INVALID' },
            @{ Target = 'objects'; Code = 'PREWRITE_AUTHORIZATION_BINDING_INVALID' },
            @{ Target = 'chronology'; Code = 'AUTHORIZATION_CONSUMPTION_RECORD_INVALID' }
        ) {
            param($Target, $Code)
            $scenario = New-ActivationScenarioFixture
            $authorization = $scenario.RecordIndex | Where-Object recordId -eq 'private://authorizations/write-authorization-synthetic-1'
            $consumption = $scenario.RecordIndex | Where-Object recordId -eq 'authorization-consumption-synthetic-1'
            if ($Target -eq 'duplicate') {
                $duplicate = Copy-TestObject $consumption
                $duplicate.recordId = 'authorization-consumption-replay-synthetic-2'
                $duplicate.payload.record = $duplicate.recordId
                Update-CanonicalRecordBinding $duplicate
                $scenario.RecordIndex += $duplicate
            }
            elseif ($Target -eq 'maxUses') { $authorization.payload.maxUses = 2; Update-CanonicalRecordBinding $authorization }
            elseif ($Target -eq 'revoked') { $authorization.payload.revocationStatus = 'REVOKED'; Update-CanonicalRecordBinding $authorization }
            elseif ($Target -eq 'objects') { $authorization.payload.managedObjectSetDigest = New-TestDigest 'f'; Update-CanonicalRecordBinding $authorization }
            else { $consumption.payload.consumedAt = '2026-08-27T12:09:00Z'; Update-CanonicalRecordBinding $consumption }
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects readback that does not close the exact consumption ledger and independent policy' -TestCases @(
            @{ Field = 'consumptionLedgerDigest'; Value = 'sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff' },
            @{ Field = 'independentReadbackPolicyDigest'; Value = 'sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff' }
        ) {
            param($Field, $Value)
            $scenario = New-ActivationReadbackMutation -Field $Field -Value $Value
            $codes = @((Invoke-TestActivation -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes)
            (($codes -contains 'READBACK_PROVENANCE_CLOSURE_MISMATCH') -or ($codes -contains 'READBACK_RECORD_BINDING_MISMATCH')) | Should Be $true
        }

        It 'rejects unexpected activation-request and authorization fields' -TestCases @(
            @{ Target = 'request' }, @{ Target = 'authorization' }
        ) {
            param($Target)
            $request = New-ActivationRequestFixture
            if ($Target -eq 'request') { $request | Add-Member -NotePropertyName forceWrite -NotePropertyValue $true }
            else { $request.authorization | Add-Member -NotePropertyName bypassVerdict -NotePropertyValue $true }
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'UNEXPECTED_CONTRACT_FIELD') | Should Be $true
        }

        It 'rejects malformed readback scalar types' -TestCases @(
            @{ Field = 'httpStatus'; Value = '200'; Code = 'GRAPH_READBACK_FAILED' },
            @{ Field = 'responseBodyPresent'; Value = 'true'; Code = 'READBACK_BODY_MISSING' },
            @{ Field = 'assignmentMatched'; Value = 'true'; Code = 'READBACK_STATE_MISMATCH' },
            @{ Field = 'deviceStateMatched'; Value = 'true'; Code = 'READBACK_STATE_MISMATCH' }
        ) {
            param($Field, $Value, $Code)
            $scenario = New-ActivationReadbackMutation -Field $Field -Value $Value
            (@((Invoke-TestActivation -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects readback before the bound write' {
            $scenario = New-ActivationReadbackMutation -Field 'collectedAt' -Value '2026-08-27T12:19:00Z'
            (@((Invoke-TestActivation -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains 'READBACK_TIME_INVALID') | Should Be $true
        }

        It 'rejects stale readback beyond the frozen age' {
            $request = New-ActivationRequestFixture
            $request.readbackMaxAgeMinutes = 5
            $scenario = New-ActivationReadbackMutation -Field 'collectedAt' -Value '2026-08-27T12:24:00Z'
            (@((Invoke-TestActivation -Request $request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains 'READBACK_TIME_INVALID') | Should Be $true
        }

        It 'rejects readback-age boundaries outside one minute through one day' -TestCases @(
            @{ Minutes = 0 }, @{ Minutes = 1441 }, @{ Minutes = 'bogus' }
        ) {
            param($Minutes)
            $request = New-ActivationRequestFixture
            $request.readbackMaxAgeMinutes = $Minutes
            (@((Invoke-TestActivation -Request $request -Readback (New-ReadbackFixture)).ReasonCodes) -contains 'READBACK_MAX_AGE_INVALID') | Should Be $true
        }

        It 'rejects readback bound to a different operation' {
            $readback = New-ReadbackFixture
            $readback.writeOperationId = 'different-operation'
            (@((Invoke-TestActivation -Readback $readback).ReasonCodes) -contains 'READBACK_OPERATION_MISMATCH') | Should Be $true
        }

        It 'rejects missing response bodies' {
            $scenario = New-ActivationReadbackMutation -Field 'responseBodyPresent' -Value $false
            (@((Invoke-TestActivation -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains 'READBACK_BODY_MISSING') | Should Be $true
        }

        It 'rejects different or differently cased revisions' -TestCases @(
            @{ Value = 'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' },
            @{ Value = 'sha256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' }
        ) {
            param($Value)
            $scenario = New-ActivationReadbackMutation -Field 'observedStateRevision' -Value $Value
            (@((Invoke-TestActivation -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains 'READBACK_REVISION_MISMATCH') | Should Be $true
        }

        It 'rejects a mismatched target scope' {
            $scenario = New-ActivationReadbackMutation -Field 'targetScopeRef' -Value 'private://rings/ring-other'
            (@((Invoke-TestActivation -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains 'READBACK_SCOPE_MISMATCH') | Should Be $true
        }

        It 'rejects the wrong readback tool or reused writer identity' -TestCases @(
            @{ Field = 'readerToolRef'; Value = 'microsoft-graph-write'; Code = 'UNAUTHORIZED_READBACK_TOOL' },
            @{ Field = 'readIdentityRef'; Value = 'private://identities/graph-writer'; Code = 'READBACK_IDENTITY_NOT_INDEPENDENT' }
        ) {
            param($Field, $Value, $Code)
            $readback = New-ReadbackFixture
            $readback.$Field = $Value
            (@((Invoke-TestActivation -Readback $readback).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects an unexpected readback field' {
            $readback = New-ReadbackFixture
            $readback | Add-Member -NotePropertyName writerApprovedItself -NotePropertyValue $true
            (@((Invoke-TestActivation -Readback $readback).ReasonCodes) -contains 'UNEXPECTED_CONTRACT_FIELD') | Should Be $true
        }

        It 'rejects a forged caller digest for an otherwise retained readback' {
            $readback = New-ReadbackFixture
            $readback.readbackRecordDigest = New-TestDigest 'b'
            (@((Invoke-TestActivation -Readback $readback).ReasonCodes) -contains 'READBACK_RECORD_BINDING_MISMATCH') | Should Be $true
        }

        It 'binds the caller readback-age limit into the issued authorization request digest' {
            $scenario = New-ActivationScenarioFixture
            $scenario.Request.readbackMaxAgeMinutes = 29
            $codes = @((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes)
            ($codes -contains 'WRITE_AUTHORIZATION_REQUEST_DIGEST_MISMATCH') | Should Be $true
        }

        It 'fails closed on missing, stale, forked, or identity-overlapping ledger observation' -TestCases @(
            @{ Target = 'missing'; Code = 'AUTHORIZATION_CONSUMPTION_READBACK_REQUIRED' },
            @{ Target = 'stale'; Code = 'AUTHORIZATION_CONSUMPTION_READBACK_INVALID' },
            @{ Target = 'fork'; Code = 'AUTHORIZATION_CONSUMPTION_READBACK_INVALID' },
            @{ Target = 'overlap'; Code = 'AUTHORIZATION_CONSUMPTION_READBACK_INVALID' }
        ) {
            param($Target, $Code)
            $scenario = New-ActivationScenarioFixture
            $observer = @($scenario.RecordIndex | Where-Object recordId -ceq 'authorization-consumption-readback-synthetic-1')[0]
            if ($Target -eq 'missing') {
                $scenario.RecordIndex = @($scenario.RecordIndex | Where-Object recordId -cne $observer.recordId)
            }
            elseif ($Target -eq 'stale') { $observer.payload.observedAt = '2026-08-27T11:00:00Z'; Update-CanonicalRecordBinding $observer }
            elseif ($Target -eq 'fork') { $observer.payload.resultingLedgerDigest = New-TestDigest 'f'; Update-CanonicalRecordBinding $observer }
            else {
                $consumption = @($scenario.RecordIndex | Where-Object recordId -ceq 'authorization-consumption-synthetic-1')[0]
                $observer.payload.readIdentityRef = $consumption.payload.ledgerAuthorityIdentityRef
                Update-CanonicalRecordBinding $observer
            }
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'enforces frozen authorization TTL and revocation-freshness policies' -TestCases @(
            @{ Target = 'ttl'; Code = 'AUTHORIZATION_TTL_POLICY_VIOLATION' },
            @{ Target = 'authorization-revocation'; Code = 'AUTHORIZATION_REVOCATION_EVIDENCE_STALE_OR_POLICY_MISMATCH' },
            @{ Target = 'package-revocation'; Code = 'PACKAGE_REVOCATION_EVIDENCE_STALE_OR_POLICY_MISMATCH' }
        ) {
            param($Target, $Code)
            $scenario = New-ActivationScenarioFixture
            if ($Target -eq 'package-revocation') {
                $record = @($scenario.RecordIndex | Where-Object recordType -ceq 'package-verification-record')[0]
                $record.payload.revocationCheckedAt = '2026-08-27T10:00:00Z'
            }
            else {
                $record = @($scenario.RecordIndex | Where-Object recordType -ceq 'write-authorization-record')[0]
                if ($Target -eq 'ttl') { $record.payload.expiresAt = '2026-08-27T14:00:00Z' }
                else { $record.payload.revocationCheckedAt = '2026-08-27T11:00:00Z' }
            }
            Update-CanonicalRecordBinding $record
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects invalid role-binding, bootstrap-root, and security-policy authority closure' -TestCases @(
            @{ Target = 'missing-role-readback'; Code = 'INVALID_RECORD_REF' },
            @{ Target = 'stale-role-readback'; Code = 'ROLE_BINDING_READBACK_INVALID' },
            @{ Target = 'revoked-role-binding'; Code = 'ROLE_BINDING_RECORD_INVALID' },
            @{ Target = 'wrong-policy-scope'; Code = 'SECURITY_FRESHNESS_ROLE_AUTHORITY_INVALID' },
            @{ Target = 'policy-cycle'; Code = 'SECURITY_FRESHNESS_POLICY_AUTHORITY_CYCLE' },
            @{ Target = 'root-quorum'; Code = 'IDENTITY_GOVERNANCE_ROOT_AUTHORITY_INVALID' },
            @{ Target = 'root-custodian-collapse'; Code = 'IDENTITY_GOVERNANCE_ROOT_AUTHORITY_INVALID' },
            @{ Target = 'root-signer-custodian-mismatch'; Code = 'IDENTITY_GOVERNANCE_ROOT_AUTHORITY_INVALID' },
            @{ Target = 'root-duplicate-key-ref'; Code = 'IDENTITY_GOVERNANCE_ROOT_AUTHORITY_INVALID' },
            @{ Target = 'root-duplicate-signature-ref'; Code = 'IDENTITY_GOVERNANCE_ROOT_AUTHORITY_INVALID' },
            @{ Target = 'root-signature'; Code = 'IDENTITY_GOVERNANCE_ROOT_AUTHORITY_INVALID' },
            @{ Target = 'root-readback-attestation'; Code = 'IDENTITY_GOVERNANCE_ROOT_AUTHORITY_INVALID' }
        ) {
            param($Target, $Code)
            $scenario = New-ActivationScenarioFixture
            $role = @($scenario.RecordIndex | Where-Object recordType -ceq 'role-binding-record')[0]
            $roleReadback = @($scenario.RecordIndex | Where-Object recordType -ceq 'role-binding-readback-record')[0]
            $root = @($scenario.RecordIndex | Where-Object recordType -ceq 'identity-governance-root-authority-record')[0]
            $policy = @($scenario.RecordIndex | Where-Object {
                $_.recordType -ceq 'security-freshness-policy-record' -and $_.payload.policyKind -ceq 'AUTHORIZATION_TTL'
            })[0]
            if ($Target -eq 'missing-role-readback') {
                $scenario.RecordIndex = @($scenario.RecordIndex | Where-Object recordId -cne $roleReadback.recordId)
            }
            elseif ($Target -eq 'stale-role-readback') { $roleReadback.payload.observedAt = '2026-08-27T11:00:00Z'; Update-CanonicalRecordBinding $roleReadback }
            elseif ($Target -eq 'revoked-role-binding') { $role.payload.revocationStatus = 'REVOKED'; Update-CanonicalRecordBinding $role }
            elseif ($Target -eq 'wrong-policy-scope') { $policy.payload.policyScope = 'IDENTITY_ROLE_BINDING_READBACK'; Update-CanonicalRecordBinding $policy }
            elseif ($Target -eq 'policy-cycle') { $policy.payload.roleBindingReadbackRef = $policy.recordId; Update-CanonicalRecordBinding $policy }
            elseif ($Target -eq 'root-quorum') { $root.payload.quorumThreshold = 3; Update-CanonicalRecordBinding $root }
            elseif ($Target -eq 'root-custodian-collapse') {
                $root.payload.authorityKeyBindings[1].keyCustodianPrincipalId = $root.payload.authorityKeyBindings[0].keyCustodianPrincipalId
                $root.payload.authorityKeySetDigest = Get-IdentityGovernanceAuthorityKeySetDigest -AuthorityKeyBindings @($root.payload.authorityKeyBindings)
                $root.payload.ceremonySignatureBindings[1].signerPrincipalId = $root.payload.authorityKeyBindings[1].keyCustodianPrincipalId
                Update-CanonicalRecordBinding $root
            }
            elseif ($Target -eq 'root-signer-custodian-mismatch') {
                $root.payload.ceremonySignatureBindings[0].signerPrincipalId = $root.payload.authorityKeyBindings[1].keyCustodianPrincipalId
                Update-CanonicalRecordBinding $root
            }
            elseif ($Target -eq 'root-duplicate-key-ref') {
                $root.payload.authorityKeyBindings[1].authorityKeyRef = $root.payload.authorityKeyBindings[0].authorityKeyRef
                $root.payload.ceremonySignatureBindings[1].authorityKeyRef = $root.payload.authorityKeyBindings[1].authorityKeyRef
                $root.payload.authorityKeySetDigest = Get-IdentityGovernanceAuthorityKeySetDigest -AuthorityKeyBindings @($root.payload.authorityKeyBindings)
                $subject = Get-IdentityGovernanceRootCeremonySubjectDigest -Authority $root.payload
                $root.payload.ceremonySubjectDigest = $subject
                $root.payload.independentReadbackSubjectDigest = $subject
                foreach ($signature in @($root.payload.ceremonySignatureBindings)) { $signature.signedSubjectDigest = $subject }
                Update-CanonicalRecordBinding $root
            }
            elseif ($Target -eq 'root-duplicate-signature-ref') {
                $root.payload.ceremonySignatureBindings[1].signatureRef = $root.payload.ceremonySignatureBindings[0].signatureRef
                Update-CanonicalRecordBinding $root
            }
            elseif ($Target -eq 'root-signature') { $root.payload.ceremonySignatureBindings[0].signatureStatus = 'INVALID'; Update-CanonicalRecordBinding $root }
            else { $root.payload.independentReadbackAttestationStatus = 'INVALID'; Update-CanonicalRecordBinding $root }
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'reuses one canonical root verifier across bootstrap policy and role-binding approval without duplicating authority' {
            $scenario = New-ActivationScenarioFixture
            $root = @($scenario.RecordIndex | Where-Object recordType -ceq 'identity-governance-root-authority-record')[0]
            $approval = @($scenario.RecordIndex | Where-Object recordType -ceq 'role-binding-approval-record')[0]
            $bootstrapPolicies = @($scenario.RecordIndex | Where-Object {
                $_.recordType -ceq 'security-freshness-policy-record' -and $_.payload.authorityMode -ceq 'ROOT_BOOTSTRAP'
            })
            $approval.payload.approvalAuthorityRef | Should Be $root.recordId
            $approval.payload.approvalAuthorityReadbackRef | Should Be $root.payload.independentReadbackRef
            @($bootstrapPolicies | Where-Object { $_.payload.rootAuthorityRef -ceq $root.recordId }).Count | Should Be $bootstrapPolicies.Count
            $codes = @((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes)
            ($codes -contains 'IDENTITY_GOVERNANCE_ROOT_AUTHORITY_INVALID') | Should Be $false
            ($codes -contains 'SECURITY_FRESHNESS_ROOT_AUTHORITY_INVALID') | Should Be $false
        }

        It 'rejects missing, cross-boundary, revoked, expired, self-bootstrapped, or mis-signed role approval' -TestCases @(
            @{ Target = 'missing'; Code = 'INVALID_RECORD_REF' },
            @{ Target = 'environment'; Code = 'ROLE_BINDING_APPROVAL_INVALID' },
            @{ Target = 'revoked'; Code = 'ROLE_BINDING_APPROVAL_INVALID' },
            @{ Target = 'expired'; Code = 'ROLE_BINDING_APPROVAL_INVALID' },
            @{ Target = 'self-bootstrap'; Code = 'ROLE_BINDING_AUTHORITY_SELF_BOOTSTRAP' },
            @{ Target = 'signed-subject'; Code = 'ROLE_BINDING_APPROVAL_INVALID' }
        ) {
            param($Target, $Code)
            $scenario = New-ActivationScenarioFixture
            $approval = @($scenario.RecordIndex | Where-Object recordType -ceq 'role-binding-approval-record')[0]
            if ($Target -eq 'missing') {
                $scenario.RecordIndex = @($scenario.RecordIndex | Where-Object recordId -cne $approval.recordId)
            }
            elseif ($Target -eq 'environment') { $approval.payload.targetEnvironmentRef = 'private://environments/other'; Update-CanonicalRecordBinding $approval }
            elseif ($Target -eq 'revoked') { $approval.payload.status = 'REVOKED'; $approval.payload.revocationStatus = 'REVOKED'; Update-CanonicalRecordBinding $approval }
            elseif ($Target -eq 'expired') { $approval.payload.expiresAt = '2026-08-27T12:30:00Z'; Update-CanonicalRecordBinding $approval }
            elseif ($Target -eq 'self-bootstrap') { $approval.payload.approvalAuthorityRef = $approval.recordId; Update-CanonicalRecordBinding $approval }
            else { $approval.payload.signedSubjectDigest = New-TestDigest 'f'; Update-CanonicalRecordBinding $approval }
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'enforces acyclic authority branches and current signed freshness policy scope' -TestCases @(
            @{ Target = 'role-bound-root-field'; Code = 'SECURITY_FRESHNESS_ROLE_AUTHORITY_INVALID' },
            @{ Target = 'bootstrap-role-field'; Code = 'SECURITY_FRESHNESS_POLICY_AUTHORITY_CYCLE' },
            @{ Target = 'wrong-role'; Code = 'SECURITY_FRESHNESS_ROLE_AUTHORITY_INVALID' },
            @{ Target = 'cross-tenant'; Code = 'SECURITY_FRESHNESS_ROLE_AUTHORITY_INVALID' },
            @{ Target = 'revoked'; Code = 'SECURITY_FRESHNESS_POLICY_INVALID' },
            @{ Target = 'expired'; Code = 'SECURITY_FRESHNESS_POLICY_INVALID' }
        ) {
            param($Target, $Code)
            $scenario = New-ActivationScenarioFixture
            $roleBound = @($scenario.RecordIndex | Where-Object {
                $_.recordType -ceq 'security-freshness-policy-record' -and $_.payload.policyKind -ceq 'AUTHORIZATION_TTL'
            })[0]
            $bootstrap = @($scenario.RecordIndex | Where-Object {
                $_.recordType -ceq 'security-freshness-policy-record' -and $_.payload.authorityMode -ceq 'ROOT_BOOTSTRAP'
            })[0]
            if ($Target -eq 'role-bound-root-field') { $roleBound.payload | Add-Member -NotePropertyName rootAuthorityRef -NotePropertyValue 'identity-governance-root-synthetic-1'; Update-CanonicalRecordBinding $roleBound }
            elseif ($Target -eq 'bootstrap-role-field') { $bootstrap.payload | Add-Member -NotePropertyName roleBindingRef -NotePropertyValue 'role-binding-synthetic-1'; Update-CanonicalRecordBinding $bootstrap }
            elseif ($Target -eq 'wrong-role') { $roleBound.payload.approvedByRole = 'ROLE_IDENTITY_SECURITY_APPROVER'; Update-CanonicalRecordBinding $roleBound }
            elseif ($Target -eq 'cross-tenant') { $roleBound.payload.tenantBoundaryRef = 'private://tenants/other'; Update-CanonicalRecordBinding $roleBound }
            elseif ($Target -eq 'revoked') { $roleBound.payload.status = 'REVOKED'; $roleBound.payload.revocationStatus = 'REVOKED'; Update-CanonicalRecordBinding $roleBound }
            else { $roleBound.payload.expiresAt = '2026-08-27T12:30:00Z'; Update-CanonicalRecordBinding $roleBound }
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'rejects request and directory observations swapped across tenant or environment boundaries' -TestCases @(
            @{ Target = 'request-tenant'; Code = 'ROLE_BINDING_RECORD_INVALID' },
            @{ Target = 'directory-environment'; Code = 'DIRECTORY_TARGET_POPULATION_READBACK_MISMATCH' }
        ) {
            param($Target, $Code)
            $scenario = New-ActivationScenarioFixture
            if ($Target -eq 'request-tenant') { $scenario.Request.tenantBoundaryRef = 'private://tenants/other' }
            else {
                $directory = @($scenario.RecordIndex | Where-Object recordId -ceq $scenario.Request.targetPopulation.directoryReadbackRef)[0]
                $directory.payload.targetEnvironmentRef = 'private://environments/other'
                Update-CanonicalRecordBinding $directory
            }
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains $Code) | Should Be $true
        }

        It 'enforces exact actor roles, issuer attestation, and pre-network authorization consumption' -TestCases @(
            @{ Target = 'apply-missing'; Code = 'MISSING_REQUIRED_FIELD' },
            @{ Target = 'apply-operation-mismatch'; Code = 'WRITE_OPERATION_RECORD_MISMATCH' },
            @{ Target = 'canonical-overlap'; Code = 'OPERATION_PRINCIPAL_SEPARATION_VIOLATION' },
            @{ Target = 'package-signer-role'; Code = 'PACKAGE_VERIFICATION_BINDING_INVALID' },
            @{ Target = 'package-verifier-role'; Code = 'PACKAGE_VERIFICATION_BINDING_INVALID' },
            @{ Target = 'issuer-signature'; Code = 'WRITE_AUTHORIZATION_ISSUER_ATTESTATION_INVALID' },
            @{ Target = 'mutation-before-consumption'; Code = 'WRITE_AUTHORIZATION_NOT_CONSUMED_BEFORE_MUTATION' }
        ) {
            param($Target, $Code)
            $scenario = New-ActivationScenarioFixture
            $operation = @($scenario.RecordIndex | Where-Object recordId -ceq $scenario.Request.writeOperationRef)[0]
            $authorization = @($scenario.RecordIndex | Where-Object recordType -ceq 'write-authorization-record')[0]
            $role = @($scenario.RecordIndex | Where-Object recordType -ceq 'role-binding-record')[0]
            if ($Target -eq 'apply-missing') { $scenario.Request.PSObject.Properties.Remove('applyOperatorIdentityRef') }
            elseif ($Target -eq 'apply-operation-mismatch') { $operation.payload.applyOperatorIdentityRef = 'private://identities/other-apply'; Update-CanonicalRecordBinding $operation }
            elseif ($Target -eq 'canonical-overlap') {
                $writer = @($role.payload.bindings | Where-Object principalAliasRef -ceq $scenario.Request.writeIdentityRef)[0]
                $apply = @($role.payload.bindings | Where-Object principalAliasRef -ceq $scenario.Request.applyOperatorIdentityRef)[0]
                $apply.canonicalPrincipalId = $writer.canonicalPrincipalId
                $role.payload.bindingSetDigest = Get-RoleBindingSetDigest -Bindings @($role.payload.bindings)
                Update-CanonicalRecordBinding $role
            }
            elseif ($Target -eq 'package-signer-role') {
                $signer = @($role.payload.bindings | Where-Object principalAliasRef -ceq 'private://identities/package-signer-synthetic-1')[0]
                $signer.roleId = 'ROLE_IAC_SECURITY_OWNER'
                $role.payload.bindingSetDigest = Get-RoleBindingSetDigest -Bindings @($role.payload.bindings)
                Update-CanonicalRecordBinding $role
            }
            elseif ($Target -eq 'package-verifier-role') {
                $package = @($scenario.RecordIndex | Where-Object recordType -ceq 'package-verification-record')[0]
                $package.payload.verifierRole = 'ROLE_IAC_SECURITY_OWNER'
                Update-CanonicalRecordBinding $package
            }
            elseif ($Target -eq 'issuer-signature') { $authorization.payload.issuerSignatureStatus = 'INVALID'; Update-CanonicalRecordBinding $authorization }
            else { $operation.payload.mutationStartedAt = '2026-08-27T12:14:30Z'; Update-CanonicalRecordBinding $operation }
            (@((Invoke-TestActivation -Request $scenario.Request -RecordIndex $scenario.RecordIndex -Readback $scenario.Readback).ReasonCodes) -contains $Code) | Should Be $true
        }
    }

    Context 'Azure deployment and independent state readback' {
        It 'accepts one complete Terraform authorization, deployment, and independent Azure readback closure' {
            $scenario = New-AzureResourceStateScenarioFixture
            @(Get-TestRecordIndexReasonCodes -RecordIndex $scenario.RecordIndex).Count | Should Be 0
        }

        It 'rejects stale, unknown, or cross-boundary Azure resource observations' -TestCases @(
            @{ Target = 'stale' }, @{ Target = 'unknown-dependency' }, @{ Target = 'dependency-digest' },
            @{ Target = 'tenant' }, @{ Target = 'subscription' }, @{ Target = 'environment' }, @{ Target = 'operation-id' }
        ) {
            param($Target)
            $scenario = New-AzureResourceStateScenarioFixture
            $readback = $scenario.AzureReadback
            if ($Target -eq 'stale') {
                $readback.payload.collectedAt = '2026-08-27T11:00:00Z'
                $readback.payload.freshnessBinding.observedAt = '2026-08-27T11:00:00Z'
                $readback.payload.freshnessBinding.admittedAt = '2026-08-27T11:00:00Z'
            }
            elseif ($Target -eq 'unknown-dependency') { $readback.payload.freshnessBinding.dependencyStatus = 'UNKNOWN' }
            elseif ($Target -eq 'dependency-digest') { $readback.payload.freshnessBinding.dependencySnapshotDigest = New-TestDigest 'f' }
            elseif ($Target -eq 'tenant') { $readback.payload.tenantBoundaryRef = 'private://tenants/other' }
            elseif ($Target -eq 'subscription') { $readback.payload.subscriptionBoundaryRef = 'private://subscriptions/other' }
            elseif ($Target -eq 'environment') { $readback.payload.targetEnvironmentRef = 'private://environments/other' }
            else { $readback.payload.deploymentOperationId = 'different-azure-operation' }
            Update-CanonicalRecordBinding $readback
            (@(Get-TestRecordIndexReasonCodes -RecordIndex $scenario.RecordIndex) -contains 'AZURE_RESOURCE_STATE_READBACK_INVALID') | Should Be $true
        }

        It 'rejects an Azure deployment that diverges from the pre-bound expected-state projection' {
            $scenario = New-AzureResourceStateScenarioFixture
            $scenario.AzureOperation.payload.expectedStateDigest = New-TestDigest 'f'
            Update-CanonicalRecordBinding $scenario.AzureOperation
            (@(Get-TestRecordIndexReasonCodes -RecordIndex $scenario.RecordIndex) -contains 'AZURE_DEPLOYMENT_OPERATION_INVALID') | Should Be $true
        }
    }

    Context 'Operations record contract schema' {
        It 'does not let a spoofed OS environment variable alter the runtime path comparator' {
            $savedOs = [Environment]::GetEnvironmentVariable('OS')
            try {
                foreach ($spoofedOs in @($null, 'Windows_NT', 'Linux')) {
                    [Environment]::SetEnvironmentVariable('OS', $spoofedOs)
                    if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
                        (Test-TestPathWithinRoot -Path 'C:\TRUSTED\child' -Root 'c:\trusted') | Should Be $true
                    }
                    else {
                        (Test-TestPathWithinRoot -Path '/opt/Trusted/child' -Root '/opt/trusted') | Should Be $false
                    }
                }
            }
            finally { [Environment]::SetEnvironmentVariable('OS', $savedOs) }
        }

        It 'attests the actual external toolchain as local fixed NTFS or ReFS with case sensitivity disabled' {
            if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { $true | Should Be $true; return }
            $paths = @(
                $env:OPERATIONS_BLUEPRINT_NODE_RUNTIME_ROOT,
                $env:OPERATIONS_BLUEPRINT_SCHEMA_WORKING_DIRECTORY,
                $env:OPERATIONS_BLUEPRINT_NODE_MODULES_ROOT,
                $env:OPERATIONS_BLUEPRINT_AJV_ROOT,
                $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_ROOT,
                $env:OPERATIONS_BLUEPRINT_NODE_PATH,
                $env:OPERATIONS_BLUEPRINT_AJV_PATH,
                $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_PATH
            )
            { Assert-TestProductionWindowsToolchainBoundary -Root $env:OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT -CandidatePaths $paths } | Should Not Throw
        }

        It 'fails closed when a trusted-root directory is case-sensitive or its state is unqueryable' -TestCases @(
            @{ Target = 'case-sensitive' },
            @{ Target = 'unqueryable' }
        ) {
            param($Target)
            if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { $true | Should Be $true; return }
            $query = if ($Target -eq 'case-sensitive') {
                { param($DirectoryPath) [pscustomobject]@{ QuerySucceeded = $true; CaseSensitive = $true } }
            }
            else {
                { param($DirectoryPath) [pscustomobject]@{ QuerySucceeded = $false; CaseSensitive = $false } }
            }
            Test-ScriptBlockThrows {
                Assert-TestProductionWindowsToolchainBoundary `
                    -Root $env:OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT `
                    -CandidatePaths @($env:OPERATIONS_BLUEPRINT_NODE_PATH) `
                    -CaseSensitivityQuery $query
            } | Should Be $true
        }

        It 'rejects a redirected DOS-device root or a final-handle path that differs from the checked path' -TestCases @(
            @{ Target = 'redirected-volume' },
            @{ Target = 'retargeted-volume' },
            @{ Target = 'final-path-mismatch' }
        ) {
            param($Target)
            if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { $true | Should Be $true; return }
            $parameters = @{
                Root = $env:OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT
                CandidatePaths = @($env:OPERATIONS_BLUEPRINT_NODE_PATH)
            }
            if ($Target -eq 'redirected-volume') {
                $parameters.VolumeDeviceQuery = { param($DriveName) @('\??\C:\redirected-toolchain') }
            }
            elseif ($Target -eq 'retargeted-volume') {
                $counter = [pscustomobject]@{ Value = 0 }
                $parameters.VolumeDeviceQuery = {
                    param($DriveName)
                    $counter.Value++
                    if ($counter.Value -eq 1) { @('\Device\HarddiskVolume3') } else { @('\Device\HarddiskVolume4') }
                }.GetNewClosure()
            }
            else {
                $parameters.FinalPathQuery = { param($ExistingPath) '\\?\C:\different-object' }
            }
            Test-ScriptBlockThrows { Assert-TestProductionWindowsToolchainBoundary @parameters } | Should Be $true
        }

        It 'rechecks the exact DOS-device target after case and final-handle validation' {
            if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { $true | Should Be $true; return }
            $counter = [pscustomobject]@{ Value = 0 }
            $query = {
                param($DriveName)
                $counter.Value++
                @('\Device\HarddiskVolume3')
            }.GetNewClosure()
            {
                Assert-TestProductionWindowsToolchainBoundary `
                    -Root $env:OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT `
                    -CandidatePaths @($env:OPERATIONS_BLUEPRINT_NODE_PATH) `
                    -VolumeDeviceQuery $query
            } | Should Not Throw
            $counter.Value | Should Be 2
        }

        It 'rejects a real reparse or symbolic-link root before hashing or execution' {
            $candidate = if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) { 'C:\Users\All Users' } else { '/proc/self' }
            if (Test-Path -LiteralPath $candidate) {
                Test-ScriptBlockThrows { Assert-TestPathChainWithoutReparsePoint -Path $candidate -Root $candidate } | Should Be $true
            }
            else { $true | Should Be $true }
        }

        It 'rejects an ordinary trusted root reached through a reparse or symbolic-link ancestor' {
            $candidate = if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) { 'C:\Users\All Users\Microsoft' } else { '/proc/self/fd' }
            if (Test-Path -LiteralPath $candidate) {
                Test-ScriptBlockThrows { Assert-TestPathChainWithoutReparsePoint -Path $candidate -Root $candidate -IncludeRootAncestors } | Should Be $true
            }
            else { $true | Should Be $true }
        }

        It 'fails closed when explicit trusted-runner schema-toolchain pins are absent' {
            $names = @(
                'OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT',
                'OPERATIONS_BLUEPRINT_NODE_RUNTIME_ROOT',
                'OPERATIONS_BLUEPRINT_NODE_RUNTIME_CONTENT_SHA256',
                'OPERATIONS_BLUEPRINT_NODE_RUNTIME_TREE_SHA256',
                'OPERATIONS_BLUEPRINT_SCHEMA_WORKING_DIRECTORY',
                'OPERATIONS_BLUEPRINT_NODE_PATH',
                'OPERATIONS_BLUEPRINT_NODE_SHA256',
                'OPERATIONS_BLUEPRINT_NODE_MODULES_ROOT',
                'OPERATIONS_BLUEPRINT_NODE_MODULES_TREE_SHA256',
                'OPERATIONS_BLUEPRINT_AJV_ROOT',
                'OPERATIONS_BLUEPRINT_AJV_TREE_SHA256',
                'OPERATIONS_BLUEPRINT_AJV_PATH',
                'OPERATIONS_BLUEPRINT_AJV_SHA256',
                'OPERATIONS_BLUEPRINT_AJV_FORMATS_ROOT',
                'OPERATIONS_BLUEPRINT_AJV_FORMATS_TREE_SHA256',
                'OPERATIONS_BLUEPRINT_AJV_FORMATS_PATH',
                'OPERATIONS_BLUEPRINT_AJV_FORMATS_SHA256'
            )
            $saved = @{}
            try {
                foreach ($name in $names) {
                    $saved[$name] = [Environment]::GetEnvironmentVariable($name)
                    [Environment]::SetEnvironmentVariable($name, $null)
                }
                $thrown = $null
                try { [void](Get-TrustedSchemaToolchain) } catch { $thrown = $_ }
                ($null -ne $thrown) | Should Be $true
            }
            finally {
                foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $saved[$name]) }
            }
        }

        It 'rejects mismatched, relative, and checkout-controlled schema-toolchain pins' -TestCases @(
            @{ Target = 'node-hash' },
            @{ Target = 'node-relative' },
            @{ Target = 'checkout' },
            @{ Target = 'runtime-content' },
            @{ Target = 'runtime-tree' },
            @{ Target = 'runtime-root-relative' },
            @{ Target = 'working-directory-relative' },
            @{ Target = 'node-modules-tree' },
            @{ Target = 'ajv-tree' },
            @{ Target = 'formats-tree' },
            @{ Target = 'ajv-root-relative' },
            @{ Target = 'formats-root-relative' }
        ) {
            param($Target)
            $names = @(
                'OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT', 'OPERATIONS_BLUEPRINT_NODE_RUNTIME_ROOT',
                'OPERATIONS_BLUEPRINT_NODE_RUNTIME_CONTENT_SHA256',
                'OPERATIONS_BLUEPRINT_NODE_RUNTIME_TREE_SHA256', 'OPERATIONS_BLUEPRINT_SCHEMA_WORKING_DIRECTORY',
                'OPERATIONS_BLUEPRINT_NODE_PATH',
                'OPERATIONS_BLUEPRINT_NODE_SHA256', 'OPERATIONS_BLUEPRINT_NODE_MODULES_ROOT',
                'OPERATIONS_BLUEPRINT_NODE_MODULES_TREE_SHA256', 'OPERATIONS_BLUEPRINT_AJV_ROOT',
                'OPERATIONS_BLUEPRINT_AJV_TREE_SHA256', 'OPERATIONS_BLUEPRINT_AJV_FORMATS_ROOT',
                'OPERATIONS_BLUEPRINT_AJV_FORMATS_TREE_SHA256'
            )
            $saved = @{}
            foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name) }
            try {
                switch ($Target) {
                    'node-hash' { $env:OPERATIONS_BLUEPRINT_NODE_SHA256 = '0' * 64 }
                    'node-relative' { $env:OPERATIONS_BLUEPRINT_NODE_PATH = 'node.exe' }
                    'checkout' { $env:OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT = [IO.Path]::GetFullPath((Join-Path $here '..\..\..\..')) }
                    'runtime-content' { $env:OPERATIONS_BLUEPRINT_NODE_RUNTIME_CONTENT_SHA256 = '0' * 64 }
                    'runtime-tree' { $env:OPERATIONS_BLUEPRINT_NODE_RUNTIME_TREE_SHA256 = 'invalid' }
                    'runtime-root-relative' { $env:OPERATIONS_BLUEPRINT_NODE_RUNTIME_ROOT = 'schema-runtime' }
                    'working-directory-relative' { $env:OPERATIONS_BLUEPRINT_SCHEMA_WORKING_DIRECTORY = 'schema-runtime\work' }
                    'node-modules-tree' { $env:OPERATIONS_BLUEPRINT_NODE_MODULES_TREE_SHA256 = '0' * 64 }
                    'ajv-tree' { $env:OPERATIONS_BLUEPRINT_AJV_TREE_SHA256 = '0' * 64 }
                    'formats-tree' { $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_TREE_SHA256 = '0' * 64 }
                    'ajv-root-relative' { $env:OPERATIONS_BLUEPRINT_AJV_ROOT = 'node_modules/ajv' }
                    'formats-root-relative' { $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_ROOT = 'node_modules/ajv-formats' }
                }
                $thrown = $null
                try { [void](Get-TrustedSchemaToolchain) } catch { $thrown = $_ }
                ($null -ne $thrown) | Should Be $true
            }
            finally {
                foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $saved[$name]) }
            }
        }

        It 'rejects every inherited Node and dynamic-loader override before starting the schema subprocess' -TestCases @(
            @{ VariableName = 'NODE_OPTIONS' },
            @{ VariableName = 'NODE_PATH' },
            @{ VariableName = 'NODE_REPL_EXTERNAL_MODULE' },
            @{ VariableName = 'NODE_SYNTHETIC_CODE_LOADER' },
            @{ VariableName = 'LD_PRELOAD' },
            @{ VariableName = 'LD_LIBRARY_PATH' },
            @{ VariableName = 'LD_AUDIT' },
            @{ VariableName = 'LD_SYNTHETIC_OVERRIDE' },
            @{ VariableName = 'OPENSSL_CONF' },
            @{ VariableName = 'OPENSSL_CONF_INCLUDE' },
            @{ VariableName = 'OPENSSL_MODULES' },
            @{ VariableName = 'OPENSSL_ENGINES' },
            @{ VariableName = 'DYLD_INSERT_LIBRARIES' },
            @{ VariableName = 'DYLD_LIBRARY_PATH' }
        ) {
            param($VariableName)
            $saved = Get-TestEnvironmentVariableState -Name $VariableName
            try {
                if (Test-Path -LiteralPath "Env:$VariableName") {
                    Set-Item -LiteralPath "Env:$VariableName" -Value 'private://preload/sentinel-that-must-never-run'
                }
                else {
                    New-Item -Path Env: -Name $VariableName -Value 'private://preload/sentinel-that-must-never-run' | Out-Null
                }
                $thrown = $null
                try { [void](Get-TrustedSchemaToolchain) } catch { $thrown = $_ }
                ($null -ne $thrown) | Should Be $true
                [string]$thrown.Exception.Message | Should Match 'dynamic-loader override'
            }
            finally { Restore-TestEnvironmentVariableState -State $saved }
        }

        It 'defaults schema execution to production and rejects an unknown profile before tool discovery' {
            $command = Get-Command Invoke-OperationsRecordSchemaValidation -CommandType Function
            $parameterAst = @($command.ScriptBlock.Ast.ParamBlock.Parameters | Where-Object {
                $_.Name.VariablePath.UserPath -ceq 'ValidationProfile'
            })
            $parameterAst.Count | Should Be 1
            [string]$parameterAst[0].DefaultValue.SafeGetValue() | Should Be 'PRODUCTION'
            Test-ScriptBlockThrows { Invoke-OperationsRecordSchemaValidation -Records @() -ValidationProfile 'UNKNOWN' } | Should Be $true
        }

        It 'refuses a mutable runtime namespace instead of downgrading the production guard' {
            if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { $true | Should Be $true; return }
            $temp = New-TemporaryBlueprintDirectory
            try {
                Set-Content -LiteralPath (Join-Path $temp 'mutable-runtime.bin') -Value 'mutable' -Encoding UTF8
                (Initialize-BlueprintWindowsFileSystemInterop) | Should Be $true
                $guard = [OperationsBlueprint.NativeFileSystemSecurity]::OpenRuntimeTreeGuard($temp)
                ($null -eq $guard) | Should Be $true
                if ($null -ne $guard) { $guard.Dispose() }
            }
            finally { Remove-Item -LiteralPath $temp -Recurse -Force }
        }

        It 'restores absent, empty, and valued environment-variable state exactly' {
            $name = 'NODE_OPERATIONS_BLUEPRINT_RESTORE_SENTINEL'
            $original = Get-TestEnvironmentVariableState -Name $name
            try {
                Remove-TestEnvironmentVariable -Name $name
                $absent = Get-TestEnvironmentVariableState -Name $name
                New-Item -Path Env: -Name $name -Value 'temporary' | Out-Null
                Restore-TestEnvironmentVariableState -State $absent
                (Test-Path -LiteralPath "Env:$name") | Should Be $false

                New-Item -Path Env: -Name $name -Value '' | Out-Null
                $empty = Get-TestEnvironmentVariableState -Name $name
                Remove-TestEnvironmentVariable -Name $name
                Restore-TestEnvironmentVariableState -State $empty
                if ($empty.Present) {
                    (Test-Path -LiteralPath "Env:$name") | Should Be $true
                    ([string](Get-Item -LiteralPath "Env:$name").Value) | Should Be ''
                }
                else {
                    # Windows PowerShell 5.1 normalizes an empty process
                    # environment entry to absence; restore that observable state.
                    (Test-Path -LiteralPath "Env:$name") | Should Be $false
                }

                Set-Item -LiteralPath "Env:$name" -Value 'exact-value'
                $valued = Get-TestEnvironmentVariableState -Name $name
                Set-Item -LiteralPath "Env:$name" -Value 'changed-value'
                Restore-TestEnvironmentVariableState -State $valued
                ([string](Get-Item -LiteralPath "Env:$name").Value) | Should Be 'exact-value'
            }
            finally { Restore-TestEnvironmentVariableState -State $original }
        }

        It 'rejects control characters in package-tree relative paths before hashing' {
            $temp = New-TemporaryBlueprintDirectory
            try {
                $unsafePath = Join-Path $temp "line`nbreak.js"
                Set-Content -LiteralPath $unsafePath -Value 'module.exports = true;' -Encoding UTF8
                Test-ScriptBlockThrows { Get-PinnedDirectoryTreeSha256 -Root $temp } | Should Be $true
            }
            finally { Remove-Item -LiteralPath $temp -Recurse -Force }
        }

        It 'rejects a runtime-only byte addition even when all entry and package pins still match' {
            $pinNames = @(
                'OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT', 'OPERATIONS_BLUEPRINT_NODE_RUNTIME_ROOT',
                'OPERATIONS_BLUEPRINT_NODE_RUNTIME_CONTENT_SHA256',
                'OPERATIONS_BLUEPRINT_NODE_RUNTIME_TREE_SHA256', 'OPERATIONS_BLUEPRINT_SCHEMA_WORKING_DIRECTORY',
                'OPERATIONS_BLUEPRINT_NODE_PATH',
                'OPERATIONS_BLUEPRINT_NODE_SHA256', 'OPERATIONS_BLUEPRINT_NODE_MODULES_ROOT',
                'OPERATIONS_BLUEPRINT_NODE_MODULES_TREE_SHA256', 'OPERATIONS_BLUEPRINT_AJV_ROOT',
                'OPERATIONS_BLUEPRINT_AJV_TREE_SHA256', 'OPERATIONS_BLUEPRINT_AJV_PATH',
                'OPERATIONS_BLUEPRINT_AJV_SHA256', 'OPERATIONS_BLUEPRINT_AJV_FORMATS_ROOT',
                'OPERATIONS_BLUEPRINT_AJV_FORMATS_TREE_SHA256', 'OPERATIONS_BLUEPRINT_AJV_FORMATS_PATH',
                'OPERATIONS_BLUEPRINT_AJV_FORMATS_SHA256'
            )
            $saved = @{}
            foreach ($name in $pinNames) { $saved[$name] = [Environment]::GetEnvironmentVariable($name) }
            $temp = New-TemporaryBlueprintDirectory
            try {
                $bin = Join-Path $temp 'bin'
                $modules = Join-Path $temp 'node_modules'
                $work = Join-Path $temp 'work'
                [void](New-Item -ItemType Directory -Path $bin)
                [void](New-Item -ItemType Directory -Path $modules)
                [void](New-Item -ItemType Directory -Path $work)
                $node = Join-Path $bin 'node-test.bin'
                Set-Content -LiteralPath $node -Value 'synthetic pinned node bytes' -Encoding UTF8
                Copy-Item -LiteralPath $saved.OPERATIONS_BLUEPRINT_AJV_ROOT -Destination (Join-Path $modules 'ajv') -Recurse
                Copy-Item -LiteralPath $saved.OPERATIONS_BLUEPRINT_AJV_FORMATS_ROOT -Destination (Join-Path $modules 'ajv-formats') -Recurse
                $ajvRoot = Join-Path $modules 'ajv'
                $formatsRoot = Join-Path $modules 'ajv-formats'
                $env:OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT = $temp
                $env:OPERATIONS_BLUEPRINT_NODE_RUNTIME_ROOT = $temp
                $env:OPERATIONS_BLUEPRINT_NODE_RUNTIME_CONTENT_SHA256 = Get-PinnedDirectoryTreeSha256 $temp
                $env:OPERATIONS_BLUEPRINT_NODE_RUNTIME_TREE_SHA256 = 'a' * 64
                $env:OPERATIONS_BLUEPRINT_SCHEMA_WORKING_DIRECTORY = $work
                $env:OPERATIONS_BLUEPRINT_NODE_PATH = $node
                $env:OPERATIONS_BLUEPRINT_NODE_SHA256 = (Get-FileHash $node -Algorithm SHA256).Hash.ToLowerInvariant()
                $env:OPERATIONS_BLUEPRINT_NODE_MODULES_ROOT = $modules
                $env:OPERATIONS_BLUEPRINT_NODE_MODULES_TREE_SHA256 = Get-PinnedDirectoryTreeSha256 $modules
                $env:OPERATIONS_BLUEPRINT_AJV_ROOT = $ajvRoot
                $env:OPERATIONS_BLUEPRINT_AJV_TREE_SHA256 = Get-PinnedDirectoryTreeSha256 $ajvRoot
                $env:OPERATIONS_BLUEPRINT_AJV_PATH = Join-Path $ajvRoot 'dist\2020.js'
                $env:OPERATIONS_BLUEPRINT_AJV_SHA256 = (Get-FileHash $env:OPERATIONS_BLUEPRINT_AJV_PATH -Algorithm SHA256).Hash.ToLowerInvariant()
                $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_ROOT = $formatsRoot
                $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_TREE_SHA256 = Get-PinnedDirectoryTreeSha256 $formatsRoot
                $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_PATH = Join-Path $formatsRoot 'dist\index.js'
                $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_SHA256 = (Get-FileHash $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_PATH -Algorithm SHA256).Hash.ToLowerInvariant()

                Set-Content -LiteralPath (Join-Path $bin 'unlisted-native-runtime.dll') `
                    -Value 'adversarial runtime-only byte addition' -Encoding UTF8
                $thrown = $null
                try { [void](Get-TrustedSchemaToolchain) } catch { $thrown = $_ }
                ($null -ne $thrown) | Should Be $true
                [string]$thrown.Exception.Message | Should Match 'full-content SHA-256'
            }
            finally {
                foreach ($name in $pinNames) { [Environment]::SetEnvironmentVariable($name, $saved[$name]) }
                Remove-Item -LiteralPath $temp -Recurse -Force
            }
        }

        It 'rejects a nested dependency substitution that changes bare Ajv resolution' {
            $pinNames = @(
                'OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT', 'OPERATIONS_BLUEPRINT_NODE_RUNTIME_ROOT',
                'OPERATIONS_BLUEPRINT_NODE_RUNTIME_CONTENT_SHA256',
                'OPERATIONS_BLUEPRINT_NODE_RUNTIME_TREE_SHA256', 'OPERATIONS_BLUEPRINT_SCHEMA_WORKING_DIRECTORY',
                'OPERATIONS_BLUEPRINT_NODE_PATH',
                'OPERATIONS_BLUEPRINT_NODE_SHA256', 'OPERATIONS_BLUEPRINT_NODE_MODULES_ROOT',
                'OPERATIONS_BLUEPRINT_NODE_MODULES_TREE_SHA256', 'OPERATIONS_BLUEPRINT_AJV_ROOT',
                'OPERATIONS_BLUEPRINT_AJV_TREE_SHA256', 'OPERATIONS_BLUEPRINT_AJV_PATH',
                'OPERATIONS_BLUEPRINT_AJV_SHA256', 'OPERATIONS_BLUEPRINT_AJV_FORMATS_ROOT',
                'OPERATIONS_BLUEPRINT_AJV_FORMATS_TREE_SHA256', 'OPERATIONS_BLUEPRINT_AJV_FORMATS_PATH',
                'OPERATIONS_BLUEPRINT_AJV_FORMATS_SHA256'
            )
            $saved = @{}
            foreach ($name in $pinNames) { $saved[$name] = [Environment]::GetEnvironmentVariable($name) }
            $temp = New-TemporaryBlueprintDirectory
            try {
                $bin = Join-Path $temp 'bin'
                $modules = Join-Path $temp 'node_modules'
                $work = Join-Path $temp 'work'
                [void](New-Item -ItemType Directory -Path $bin)
                [void](New-Item -ItemType Directory -Path $modules)
                [void](New-Item -ItemType Directory -Path $work)
                $node = Join-Path $bin ([IO.Path]::GetFileName($saved.OPERATIONS_BLUEPRINT_NODE_PATH))
                Copy-Item -LiteralPath $saved.OPERATIONS_BLUEPRINT_NODE_PATH -Destination $node
                Copy-Item -LiteralPath $saved.OPERATIONS_BLUEPRINT_AJV_ROOT -Destination (Join-Path $modules 'ajv') -Recurse
                Copy-Item -LiteralPath $saved.OPERATIONS_BLUEPRINT_AJV_FORMATS_ROOT -Destination (Join-Path $modules 'ajv-formats') -Recurse
                $ajvRoot = Join-Path $modules 'ajv'
                $formatsRoot = Join-Path $modules 'ajv-formats'
                $nestedAjv = Join-Path $formatsRoot 'node_modules\ajv'
                [void](New-Item -ItemType Directory -Path (Join-Path $nestedAjv 'dist') -Force)
                Set-Content -LiteralPath (Join-Path $nestedAjv 'package.json') -Value '{"name":"ajv","version":"0.0.0-adversarial","main":"dist/ajv.js"}' -Encoding UTF8
                Set-Content -LiteralPath (Join-Path $nestedAjv 'dist\ajv.js') -Value 'module.exports = function AdversarialAjv() {};' -Encoding UTF8

                $env:OPERATIONS_BLUEPRINT_TOOLCHAIN_ROOT = $temp
                $env:OPERATIONS_BLUEPRINT_NODE_RUNTIME_ROOT = $temp
                $env:OPERATIONS_BLUEPRINT_SCHEMA_WORKING_DIRECTORY = $work
                $env:OPERATIONS_BLUEPRINT_NODE_PATH = $node
                $env:OPERATIONS_BLUEPRINT_NODE_SHA256 = (Get-FileHash $node -Algorithm SHA256).Hash.ToLowerInvariant()
                $env:OPERATIONS_BLUEPRINT_NODE_MODULES_ROOT = $modules
                $env:OPERATIONS_BLUEPRINT_NODE_MODULES_TREE_SHA256 = Get-PinnedDirectoryTreeSha256 $modules
                $env:OPERATIONS_BLUEPRINT_AJV_ROOT = $ajvRoot
                $env:OPERATIONS_BLUEPRINT_AJV_TREE_SHA256 = Get-PinnedDirectoryTreeSha256 $ajvRoot
                $env:OPERATIONS_BLUEPRINT_AJV_PATH = Join-Path $ajvRoot 'dist\2020.js'
                $env:OPERATIONS_BLUEPRINT_AJV_SHA256 = (Get-FileHash $env:OPERATIONS_BLUEPRINT_AJV_PATH -Algorithm SHA256).Hash.ToLowerInvariant()
                $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_ROOT = $formatsRoot
                $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_TREE_SHA256 = Get-PinnedDirectoryTreeSha256 $formatsRoot
                $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_PATH = Join-Path $formatsRoot 'dist\index.js'
                $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_SHA256 = (Get-FileHash $env:OPERATIONS_BLUEPRINT_AJV_FORMATS_PATH -Algorithm SHA256).Hash.ToLowerInvariant()
                $env:OPERATIONS_BLUEPRINT_NODE_RUNTIME_CONTENT_SHA256 = Get-PinnedDirectoryTreeSha256 $temp
                $env:OPERATIONS_BLUEPRINT_NODE_RUNTIME_TREE_SHA256 = 'a' * 64

                $issuedFixture = New-IssuedClaimFixture
                $record = @($issuedFixture.RecordIndex | Where-Object recordType -eq 'evidence-release')[0]
                $result = Invoke-OperationsRecordSchemaValidation -Records @($record) -ValidationProfile TEST
                $result.compiled | Should Be $false
                $result.valid | Should Be $false
                ([string]$result.errors[0].message) | Should Match 'dependency resolution does not match'
            }
            finally {
                foreach ($name in $pinNames) { [Environment]::SetEnvironmentVariable($name, $saved[$name]) }
                Remove-Item -LiteralPath $temp -Recurse -Force
            }
        }

        It 'is parsed and identified by the bundle as the non-normative Draft 2020-12 operations contract' {
            $schemaPath = Join-Path $here 'operations-record-contracts.schema.json'
            $schema = Get-Content -LiteralPath $schemaPath -Raw | ConvertFrom-Json
            $schema.'$schema' | Should Be 'https://json-schema.org/draft/2020-12/schema'
            $schema.'$id' | Should Be 'urn:laptop-qual:operations-record-contracts:1.0.0'
            $schema.type | Should Be 'array'
            $schema.description | Should Match 'not a sixth portable qualification schema'
            $bundle = Test-OperationsBlueprintBundle $here
            (@($bundle.ReasonCodes) -contains 'OPERATIONS_CONTRACT_SCHEMA_PARSE_FAILED') | Should Be $false
            (@($bundle.ReasonCodes) -contains 'OPERATIONS_CONTRACT_SCHEMA_IDENTITY_INVALID') | Should Be $false
        }

        It 'strict-compiles with pinned Ajv and validates one canonical record for every operations type' {
            $schema = Get-Content (Join-Path $here 'operations-record-contracts.schema.json') -Raw | ConvertFrom-Json
            $expectedTypes = @($schema.'$defs'.operationsCanonicalRecord.oneOf | ForEach-Object {
                $definitionName = [string]$_.'$ref'.Split('/')[-1]
                [string]$schema.'$defs'.PSObject.Properties[$definitionName].Value.allOf[1].properties.recordType.const
            })
            $records = @(New-OperationsFullRecordIndexFixture)
            $expectedTypes.Count | Should Be 45
            $records.Count | Should Be $expectedTypes.Count
            @($records.recordType | Sort-Object -Unique).Count | Should Be $expectedTypes.Count
            foreach ($recordType in $expectedTypes) { (@($records.recordType) -ccontains $recordType) | Should Be $true }
            $parentDirectoryBefore = (Get-Location).ProviderPath
            $parentPathBefore = [Environment]::GetEnvironmentVariable('PATH')
            $result = Invoke-OperationsRecordSchemaValidation -Records $records -ValidationProfile TEST
            (Get-Location).ProviderPath | Should Be $parentDirectoryBefore
            [Environment]::GetEnvironmentVariable('PATH') | Should Be $parentPathBefore
            $result.validationProfile | Should Be 'TEST'
            $result.authoritative | Should Be $false
            $result.promotionEffect | Should Be 'NONE'
            $result.state | Should Be 'TEST_SCHEMA_VALIDATED_NON_PROMOTABLE'
            $result.compiled | Should Be $true
            $result.valid | Should Be $true
            @($result.errors).Count | Should Be 0
        }

        It 'strictly validates every operations record emitted by the issued leadership fixture' {
            $schema = Get-Content (Join-Path $here 'operations-record-contracts.schema.json') -Raw | ConvertFrom-Json
            $operationsTypes = @($schema.'$defs'.operationsCanonicalRecord.oneOf | ForEach-Object {
                $definitionName = [string]$_.'$ref'.Split('/')[-1]
                [string]$schema.'$defs'.PSObject.Properties[$definitionName].Value.allOf[1].properties.recordType.const
            })
            $issued = New-IssuedClaimFixture
            $records = @($issued.RecordIndex | Where-Object { $operationsTypes -ccontains [string]$_.recordType })
            (@($records.recordId) -ccontains 'fleet-query-pack-synthetic-1') | Should Be $true
            (@($records.recordId) -ccontains 'decision-claim-synthetic-1') | Should Be $true
            $result = Invoke-OperationsRecordSchemaValidation -Records $records -ValidationProfile TEST
            $result.compiled | Should Be $true
            $result.valid | Should Be $true
            @($result.errors).Count | Should Be 0
        }

        It 'requires custodians, signers, and independently attested root readback fields' -TestCases @(
            @{ Target = 'key-custodian' },
            @{ Target = 'signature-signer' },
            @{ Target = 'readback-subject' },
            @{ Target = 'readback-attestation-ref' },
            @{ Target = 'readback-attestation-digest' },
            @{ Target = 'readback-attestation-status' }
        ) {
            param($Target)
            $root = @(New-OperationsFullRecordIndexFixture | Where-Object recordType -ceq 'identity-governance-root-authority-record')[0]
            if ($Target -eq 'key-custodian') { $root.payload.authorityKeyBindings[0].PSObject.Properties.Remove('keyCustodianPrincipalId') }
            elseif ($Target -eq 'signature-signer') { $root.payload.ceremonySignatureBindings[0].PSObject.Properties.Remove('signerPrincipalId') }
            elseif ($Target -eq 'readback-subject') { $root.payload.PSObject.Properties.Remove('independentReadbackSubjectDigest') }
            elseif ($Target -eq 'readback-attestation-ref') { $root.payload.PSObject.Properties.Remove('independentReadbackAttestationRef') }
            elseif ($Target -eq 'readback-attestation-digest') { $root.payload.PSObject.Properties.Remove('independentReadbackAttestationDigest') }
            else { $root.payload.independentReadbackAttestationStatus = 'INVALID' }
            $result = Invoke-OperationsRecordSchemaValidation -Records @($root) -ValidationProfile TEST
            $result.compiled | Should Be $true
            $result.valid | Should Be $false
            @($result.errors).Count | Should BeGreaterThan 0
        }

        It 'strictly validates COST_DELTA, NON_PRICE_EFFECT, and NOT_MEASURED business-effect branches' -TestCases @(
            @{ DecisionImpact = 'HOLD' },
            @{ DecisionImpact = 'EXCLUDE_FROM_DECISION' },
            @{ DecisionImpact = 'DECISION_MAY_PROCEED_WITHOUT_EFFECT_CLAIM' }
        ) {
            param($DecisionImpact)
            $costDelta = @(New-OperationsFullRecordIndexFixture | Where-Object recordType -eq 'business-impact-record')[0]
            $nonPrice = New-CanonicalRecord 'business-nonprice-synthetic-1' 'business-impact-record' -Fields @{
                effectType = 'NON_PRICE_EFFECT'
                businessEffectStatement = 'Synthetic normalized incident-repair change; no monetary claim.'
                metricId = 'incident-repair-hours'
                metricUnit = 'hours'
                metricDirection = 'LOWER_IS_BETTER'
                denominator = [pscustomobject]@{ definition = 'Observed managed devices'; unit = 'devices'; value = 30 }
                observationWindow = '2026-01-01/2026-03-31'
                distributionRef = 'distribution-business-synthetic-1'
                distributionDigest = New-TestDigest 'a'
                coverage = [pscustomobject]@{ expected = 30; observed = 30; percent = 100 }
                limitations = @('Synthetic fixture only; not a production benefit statement.')
                sourceRecordBindings = @([pscustomobject]@{ recordRef = 'business-impact-t0'; contentDigest = New-TestDigest 'b' })
                freshnessBinding = New-ActivationFreshnessBinding
            }
            $notMeasured = New-CanonicalRecord 'business-not-measured-synthetic-1' 'business-impact-record' -Fields @{
                effectType = 'NOT_MEASURED'
                businessEffectStatement = 'NO_MEASURED_EFFECT_CLAIM'
                reason = 'No production observation window is complete.'
                decisionImpact = $DecisionImpact
                recordedAt = '2026-08-27T12:00:00Z'
            }
            $result = Invoke-OperationsRecordSchemaValidation -Records @($costDelta, $nonPrice, $notMeasured) -ValidationProfile TEST
            $result.compiled | Should Be $true
            $result.valid | Should Be $true
            @($result.errors).Count | Should Be 0
        }

        It 'rejects invented benefit prose and monetary fields in NOT_MEASURED business effects' -TestCases @(
            @{ Target = 'statement' }, @{ Target = 'currency' }, @{ Target = 'decisionImpact' }
        ) {
            param($Target)
            $record = New-CanonicalRecord 'business-not-measured-invalid-synthetic-1' 'business-impact-record' -Fields @{
                effectType = 'NOT_MEASURED'
                businessEffectStatement = 'NO_MEASURED_EFFECT_CLAIM'
                reason = 'No production observation window is complete.'
                decisionImpact = 'DECISION_MAY_PROCEED_WITHOUT_EFFECT_CLAIM'
                recordedAt = '2026-08-27T12:00:00Z'
            }
            if ($Target -eq 'statement') { $record.payload.businessEffectStatement = 'The candidate will save employee time.' }
            elseif ($Target -eq 'currency') { $record.payload | Add-Member -NotePropertyName currency -NotePropertyValue 'USD' }
            else { $record.payload.decisionImpact = 'INVENTED_BENEFIT_SUPPORTS_BUY' }
            Update-CanonicalRecordBinding $record
            $result = Invoke-OperationsRecordSchemaValidation -Records @($record) -ValidationProfile TEST
            $result.compiled | Should Be $true
            $result.valid | Should Be $false
        }

        It 'rejects portable qualification records from the non-normative operations contract' {
            $portableVerdict = New-CanonicalRecord 'portable-verdict-synthetic-1' 'verdict-record'
            $result = Invoke-OperationsRecordSchemaValidation -Records @($portableVerdict) -ValidationProfile TEST
            $result.compiled | Should Be $true
            $result.valid | Should Be $false
            @($result.errors).Count | Should BeGreaterThan 0
        }

        It 'rejects unknown canonical-envelope and payload properties' -TestCases @(
            @{ Target = 'envelope' },
            @{ Target = 'payload' }
        ) {
            param($Target)
            $issued = New-IssuedClaimFixture
            $record = Copy-TestObject -InputObject (@($issued.RecordIndex | Where-Object recordId -eq 'fleet-portfolio-synthetic-1')[0])
            if ($Target -eq 'envelope') { $record | Add-Member -NotePropertyName bypassAttestation -NotePropertyValue $true }
            else { $record.payload | Add-Member -NotePropertyName ungovernedDeviceCount -NotePropertyValue 1 }
            $result = Invoke-OperationsRecordSchemaValidation -Records @($record) -ValidationProfile TEST
            $result.compiled | Should Be $true
            $result.valid | Should Be $false
            @($result.errors).Count | Should BeGreaterThan 0
        }
    }

    Context 'Blueprint file manifest' {
        It 'validates the checked-in self-excluding manifest without granting authority' {
            $result = Test-BlueprintFileManifest -BlueprintRoot $here
            $result.Valid | Should Be $true
            $result.State | Should Be 'VALID'
            $result.Allowed | Should Be $false
            $lines = @(Get-Content -LiteralPath (Join-Path $here 'BLUEPRINT_MANIFEST.sha256'))
            $lines.Count | Should Be 11
            (@($lines | Where-Object { $_ -match 'BLUEPRINT_MANIFEST\.sha256' }).Count) | Should Be 0
        }

        It 'fails closed when the manifest is missing' {
            $temp = New-TemporaryBlueprintDirectory
            try {
                $result = Test-BlueprintFileManifest -BlueprintRoot $temp
                $result.Valid | Should Be $false
                $result.State | Should Be 'BLOCKED'
                (@($result.ReasonCodes) -contains 'BLUEPRINT_MANIFEST_MISSING') | Should Be $true
            }
            finally { Remove-Item -LiteralPath $temp -Recurse -Force }
        }

        It 'fails closed when a manifested file is tampered' {
            $temp = New-BlueprintManifestTestDirectory
            try {
                Add-Content -LiteralPath (Join-Path $temp 'README.md') -Value 'tampered'
                $result = Test-BlueprintFileManifest -BlueprintRoot $temp
                $result.Valid | Should Be $false
                (@($result.ReasonCodes) -contains 'BLUEPRINT_FILE_HASH_MISMATCH') | Should Be $true
            }
            finally { Remove-Item -LiteralPath $temp -Recurse -Force }
        }

        It 'rejects malformed and duplicate manifest lines' -TestCases @(
            @{ Target = 'malformed'; Code = 'BLUEPRINT_MANIFEST_MALFORMED' },
            @{ Target = 'duplicate'; Code = 'BLUEPRINT_MANIFEST_DUPLICATE' }
        ) {
            param($Target, $Code)
            $temp = New-BlueprintManifestTestDirectory
            try {
                $manifestPath = Join-Path $temp 'BLUEPRINT_MANIFEST.sha256'
                $lines = @(Get-Content -LiteralPath $manifestPath)
                if ($Target -eq 'malformed') { $lines += 'NOT-A-LOWERCASE-SHA256  ./forged.txt' }
                else { $lines += $lines[0] }
                Set-Content -LiteralPath $manifestPath -Value $lines -Encoding UTF8
                $result = Test-BlueprintFileManifest -BlueprintRoot $temp
                $result.Valid | Should Be $false
                (@($result.ReasonCodes) -contains $Code) | Should Be $true
            }
            finally { Remove-Item -LiteralPath $temp -Recurse -Force }
        }

        It 'rejects unexpected and missing manifest entries' -TestCases @(
            @{ Target = 'unexpected'; Code = 'BLUEPRINT_MANIFEST_ENTRY_UNEXPECTED' },
            @{ Target = 'missing'; Code = 'BLUEPRINT_MANIFEST_ENTRY_MISSING' }
        ) {
            param($Target, $Code)
            $temp = New-BlueprintManifestTestDirectory
            try {
                $manifestPath = Join-Path $temp 'BLUEPRINT_MANIFEST.sha256'
                $lines = @(Get-Content -LiteralPath $manifestPath)
                if ($Target -eq 'unexpected') { $lines += (('0' * 64) + '  ./unexpected.txt') }
                else { $lines = @($lines | Where-Object { $_ -notmatch '\./README\.md$' }) }
                Set-Content -LiteralPath $manifestPath -Value $lines -Encoding UTF8
                $result = Test-BlueprintFileManifest -BlueprintRoot $temp
                $result.Valid | Should Be $false
                (@($result.ReasonCodes) -contains $Code) | Should Be $true
                (@($result.ReasonCodes) -contains 'BLUEPRINT_MANIFEST_FILE_COUNT_MISMATCH') | Should Be $true
            }
            finally { Remove-Item -LiteralPath $temp -Recurse -Force }
        }

        It 'rejects a missing functional file even when its manifest entry remains' {
            $temp = New-BlueprintManifestTestDirectory
            try {
                Remove-Item -LiteralPath (Join-Path $temp 'README.md') -Force
                $result = Test-BlueprintFileManifest -BlueprintRoot $temp
                $result.Valid | Should Be $false
                (@($result.ReasonCodes) -contains 'BLUEPRINT_FILE_MISSING') | Should Be $true
            }
            finally { Remove-Item -LiteralPath $temp -Recurse -Force }
        }

        It 'rejects every unmanifested file or nested directory' -TestCases @(
            @{ EntryType = 'file' },
            @{ EntryType = 'directory' }
        ) {
            param($EntryType)
            $temp = New-BlueprintManifestTestDirectory
            try {
                $unexpectedPath = Join-Path $temp 'unmanifested-entry'
                if ($EntryType -eq 'file') { Set-Content -LiteralPath $unexpectedPath -Value 'unexpected' -Encoding UTF8 }
                else { [void](New-Item -ItemType Directory -Path $unexpectedPath) }
                $result = Test-BlueprintFileManifest -BlueprintRoot $temp
                $result.Valid | Should Be $false
                $result.Allowed | Should Be $false
                (@($result.ReasonCodes) -contains 'BLUEPRINT_DIRECTORY_ENTRY_UNEXPECTED') | Should Be $true
            }
            finally { Remove-Item -LiteralPath $temp -Recurse -Force }
        }
    }

    Context 'Bundle and Git boundary' {
        It 'accepts only the exact externally pinned Git executable' {
            $resolved = Get-TrustedGitApplication
            [string]::IsNullOrWhiteSpace([string]$resolved) | Should Be $false
            [IO.Path]::GetFullPath([string]$resolved) | Should Be ([IO.Path]::GetFullPath([string]$env:OPERATIONS_BLUEPRINT_GIT_PATH))
        }

        It 'cannot bypass Windows Git signer or checkout containment by unsetting or spoofing the OS environment variable' {
            if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { $true | Should Be $true; return }
            $temp = New-TemporaryBlueprintDirectory
            $savedPath = $env:OPERATIONS_BLUEPRINT_GIT_PATH
            $savedHash = $env:OPERATIONS_BLUEPRINT_GIT_SHA256
            $savedOs = [Environment]::GetEnvironmentVariable('OS')
            try {
                $mutatedGit = Join-Path $temp 'git.exe'
                Copy-Item -LiteralPath $savedPath -Destination $mutatedGit
                $bytes = [IO.File]::ReadAllBytes($mutatedGit)
                $bytes[$bytes.Length - 1] = $bytes[$bytes.Length - 1] -bxor 1
                [IO.File]::WriteAllBytes($mutatedGit, $bytes)
                $env:OPERATIONS_BLUEPRINT_GIT_PATH = $mutatedGit
                $env:OPERATIONS_BLUEPRINT_GIT_SHA256 = (Get-FileHash -LiteralPath $mutatedGit -Algorithm SHA256).Hash.ToLowerInvariant()
                $checkedInTestPath = Join-Path $here 'OperationsBlueprint.Tests.ps1'
                foreach ($spoofedOs in @($null, 'Linux')) {
                    [Environment]::SetEnvironmentVariable('OS', $spoofedOs)
                    [string]::IsNullOrWhiteSpace([string](Get-TrustedGitApplication)) | Should Be $true
                    $env:OPERATIONS_BLUEPRINT_GIT_PATH = $checkedInTestPath
                    $env:OPERATIONS_BLUEPRINT_GIT_SHA256 = (Get-FileHash -LiteralPath $checkedInTestPath -Algorithm SHA256).Hash.ToLowerInvariant()
                    [string]::IsNullOrWhiteSpace([string](Get-TrustedGitApplication)) | Should Be $true
                    $env:OPERATIONS_BLUEPRINT_GIT_PATH = $mutatedGit
                    $env:OPERATIONS_BLUEPRINT_GIT_SHA256 = (Get-FileHash -LiteralPath $mutatedGit -Algorithm SHA256).Hash.ToLowerInvariant()
                }
            }
            finally {
                $env:OPERATIONS_BLUEPRINT_GIT_PATH = $savedPath
                $env:OPERATIONS_BLUEPRINT_GIT_SHA256 = $savedHash
                [Environment]::SetEnvironmentVariable('OS', $savedOs)
                Remove-Item -LiteralPath $temp -Recurse -Force
            }
        }

        It 'supports consecutive trusted Git calls without leaking helper configuration' {
            $names = @('GIT_CONFIG_NOSYSTEM','GIT_CONFIG_GLOBAL','GIT_CONFIG_SYSTEM')
            $saved = @{}
            foreach ($name in $names) {
                $saved[$name] = [pscustomobject]@{
                    Present = Test-Path -LiteralPath "Env:$name"
                    Value = [Environment]::GetEnvironmentVariable($name)
                }
                [Environment]::SetEnvironmentVariable($name, $null)
            }
            $savedOs = [Environment]::GetEnvironmentVariable('OS')
            try {
                foreach ($spoofedOs in @($null, 'Linux', 'Windows_NT')) {
                    [Environment]::SetEnvironmentVariable('OS', $spoofedOs)
                    $first = Get-TrustedGitApplication
                    $second = Get-TrustedGitApplication
                    [IO.Path]::GetFullPath([string]$first) | Should Be ([IO.Path]::GetFullPath([string]$second))
                    foreach ($name in $names) { (Test-Path -LiteralPath "Env:$name") | Should Be $false }
                }
            }
            finally {
                [Environment]::SetEnvironmentVariable('OS', $savedOs)
                foreach ($name in $names) {
                    if ($saved[$name].Present) { [Environment]::SetEnvironmentVariable($name, $saved[$name].Value) }
                    else { [Environment]::SetEnvironmentVariable($name, $null) }
                }
            }
        }

        It 'rejects preexisting Git configuration injection without changing it' {
            $names = @('GIT_CONFIG_NOSYSTEM','GIT_CONFIG_GLOBAL','GIT_CONFIG_SYSTEM')
            $saved = @{}
            try {
                foreach ($name in $names) {
                    $saved[$name] = [Environment]::GetEnvironmentVariable($name)
                    [Environment]::SetEnvironmentVariable($name, "private://git-config-injection/$name")
                }
                [string]::IsNullOrWhiteSpace([string](Get-TrustedGitApplication)) | Should Be $true
                foreach ($name in $names) {
                    [Environment]::GetEnvironmentVariable($name) | Should Be "private://git-config-injection/$name"
                }
            }
            finally {
                foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $saved[$name]) }
            }
        }

        It 'restores helper-created Git configuration after a trusted command failure' {
            $names = @('GIT_CONFIG_NOSYSTEM','GIT_CONFIG_GLOBAL','GIT_CONFIG_SYSTEM')
            $saved = @{}
            foreach ($name in $names) {
                $saved[$name] = [pscustomobject]@{
                    Present = Test-Path -LiteralPath "Env:$name"
                    Value = [Environment]::GetEnvironmentVariable($name)
                }
                [Environment]::SetEnvironmentVariable($name, $null)
            }
            try {
                $result = Invoke-GitRead @('synthetic-command-that-must-fail')
                ($result.ExitCode -ne 0) | Should Be $true
                foreach ($name in $names) { (Test-Path -LiteralPath "Env:$name") | Should Be $false }
            }
            finally {
                foreach ($name in $names) {
                    if ($saved[$name].Present) { [Environment]::SetEnvironmentVariable($name, $saved[$name].Value) }
                    else { [Environment]::SetEnvironmentVariable($name, $null) }
                }
            }
        }

        It 'fails closed for missing, relative, checkout-controlled, and hash-mismatched Git pins' -TestCases @(
            @{ Target = 'missing-path' },
            @{ Target = 'missing-hash' },
            @{ Target = 'relative-path' },
            @{ Target = 'checkout-path' },
            @{ Target = 'hash-mismatch' }
        ) {
            param($Target)
            $savedPath = $env:OPERATIONS_BLUEPRINT_GIT_PATH
            $savedHash = $env:OPERATIONS_BLUEPRINT_GIT_SHA256
            try {
                switch ($Target) {
                    'missing-path' { $env:OPERATIONS_BLUEPRINT_GIT_PATH = $null }
                    'missing-hash' { $env:OPERATIONS_BLUEPRINT_GIT_SHA256 = $null }
                    'relative-path' { $env:OPERATIONS_BLUEPRINT_GIT_PATH = 'git.exe' }
                    'checkout-path' {
                        $checkoutFile = Join-Path $here 'OperationsBlueprint.Tests.ps1'
                        $env:OPERATIONS_BLUEPRINT_GIT_PATH = $checkoutFile
                        $env:OPERATIONS_BLUEPRINT_GIT_SHA256 = (Get-FileHash $checkoutFile -Algorithm SHA256).Hash.ToLowerInvariant()
                    }
                    'hash-mismatch' { $env:OPERATIONS_BLUEPRINT_GIT_SHA256 = '0' * 64 }
                }
                (@((Test-OperationsBlueprintBundle $here).ReasonCodes) -contains 'TRUSTED_GIT_PIN_INVALID') | Should Be $true
            }
            finally {
                $env:OPERATIONS_BLUEPRINT_GIT_PATH = $savedPath
                $env:OPERATIONS_BLUEPRINT_GIT_SHA256 = $savedHash
            }
        }

        It 'does not permit PATH to replace the exact pinned Git executable' {
            $temp = New-TemporaryBlueprintDirectory
            $savedPath = $env:PATH
            try {
                $fakeGit = Join-Path $temp 'git.cmd'
                Set-Content -LiteralPath $fakeGit -Value '@echo adversarial PATH git' -Encoding ASCII
                $env:PATH = $temp + [IO.Path]::PathSeparator + $savedPath
                $resolved = Get-TrustedGitApplication
                [IO.Path]::GetFullPath([string]$resolved) | Should Be ([IO.Path]::GetFullPath([string]$env:OPERATIONS_BLUEPRINT_GIT_PATH))
            }
            finally {
                $env:PATH = $savedPath
                Remove-Item -LiteralPath $temp -Recurse -Force
            }
        }

        It 'rejects repository-selection, object, config, helper, pager, and loader environment injection' -TestCases @(
            @{ VariableName = 'GIT_DIR' },
            @{ VariableName = 'GIT_WORK_TREE' },
            @{ VariableName = 'GIT_OBJECT_DIRECTORY' },
            @{ VariableName = 'GIT_ALTERNATE_OBJECT_DIRECTORIES' },
            @{ VariableName = 'GIT_CONFIG_COUNT' },
            @{ VariableName = 'GIT_CONFIG_GLOBAL' },
            @{ VariableName = 'GIT_CONFIG_SYSTEM' },
            @{ VariableName = 'GIT_CONFIG_KEY_0' },
            @{ VariableName = 'GIT_ASKPASS' },
            @{ VariableName = 'GIT_PAGER' },
            @{ VariableName = 'GIT_TRACE2_EVENT' },
            @{ VariableName = 'GIT_EXEC_PATH' },
            @{ VariableName = 'LD_PRELOAD' },
            @{ VariableName = 'LD_AUDIT' },
            @{ VariableName = 'OPENSSL_MODULES' }
        ) {
            param($VariableName)
            $saved = [Environment]::GetEnvironmentVariable($VariableName)
            try {
                [Environment]::SetEnvironmentVariable($VariableName, 'private://git-injection/synthetic')
                $result = Test-OperationsBlueprintBundle $here
                $result.Valid | Should Be $false
                $result.Allowed | Should Be $false
                (@($result.ReasonCodes) -contains 'UNSAFE_GIT_ENVIRONMENT') | Should Be $true
            }
            finally { [Environment]::SetEnvironmentVariable($VariableName, $saved) }
        }

        It 'rejects whitespace-only path-valued Git object selectors' -TestCases @(
            @{ VariableName = 'GIT_OBJECT_DIRECTORY'; Value = '   ' },
            @{ VariableName = 'GIT_ALTERNATE_OBJECT_DIRECTORIES'; Value = "`t" }
        ) {
            param($VariableName, $Value)
            $saved = [Environment]::GetEnvironmentVariable($VariableName)
            try {
                [Environment]::SetEnvironmentVariable($VariableName, $Value)
                $result = Test-OperationsBlueprintBundle $here
                $result.Valid | Should Be $false
                (@($result.ReasonCodes) -contains 'UNSAFE_GIT_ENVIRONMENT') | Should Be $true
                [Environment]::GetEnvironmentVariable($VariableName) | Should Be $Value
            }
            finally { [Environment]::SetEnvironmentVariable($VariableName, $saved) }
        }

        It 'validates the public bundle while preserving activation HOLD' {
            $result = Test-OperationsBlueprintBundle $here
            $result.Valid | Should Be $true
            $result.Allowed | Should Be $false
            $result.ActivationState | Should Be 'HOLD'
        }

        It 'keeps the effective activation state at HOLD when the public registry declares ACTIVE' {
            $temp = New-BlueprintManifestTestDirectory
            try {
                $target = Join-Path $temp 'tool-registry.json'
                $registry = Get-Content -LiteralPath $target -Raw | ConvertFrom-Json
                $registry.activation.state = 'ACTIVE'
                $registry | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $target -Encoding UTF8

                $result = Test-OperationsBlueprintBundle $temp
                $result.Valid | Should Be $false
                $result.Allowed | Should Be $false
                $result.State | Should Be 'BLOCKED'
                $result.ActivationState | Should Be 'HOLD'
                (@($result.ReasonCodes) -contains 'PUBLIC_BLUEPRINT_CANNOT_ACTIVATE') | Should Be $true
            }
            finally { Remove-Item $temp -Recurse -Force }
        }

        It 'pins the immutable release tree and baseline' {
            $codes = @((Test-OperationsBlueprintBundle $here).ReasonCodes)
            ($codes -contains 'IMMUTABLE_RELEASE_CHANGED') | Should Be $false
            ($codes -contains 'IMMUTABLE_RELEASE_BASELINE_MISMATCH') | Should Be $false
        }

        It 'rejects a changed immutable-release baseline commit declaration' {
            $temp = New-TemporaryBlueprintDirectory $here
            try {
                Copy-Item $matrixPath $temp
                Copy-Item $chainPath $temp
                $registry = Get-CheckedRegistry
                $registry.immutableRelease.baselineCommit = '0000000000000000000000000000000000000000'
                $registry | ConvertTo-Json -Depth 50 | Set-Content (Join-Path $temp 'tool-registry.json') -Encoding UTF8
                (@((Test-OperationsBlueprintBundle $temp).ReasonCodes) -contains 'IMMUTABLE_RELEASE_BASELINE_COMMIT_MISMATCH') | Should Be $true
            }
            finally { Remove-Item $temp -Recurse -Force }
        }

        It 'rejects a changed immutable-release tree declaration' {
            $temp = New-TemporaryBlueprintDirectory $here
            try {
                Copy-Item $matrixPath $temp
                Copy-Item $chainPath $temp
                $registry = Get-CheckedRegistry
                $registry.immutableRelease.gitTreeId = '0000000000000000000000000000000000000000'
                $registry | ConvertTo-Json -Depth 50 | Set-Content (Join-Path $temp 'tool-registry.json') -Encoding UTF8
                (@((Test-OperationsBlueprintBundle $temp).ReasonCodes) -contains 'IMMUTABLE_RELEASE_BASELINE_MISMATCH') | Should Be $true
            }
            finally { Remove-Item $temp -Recurse -Force }
        }

        It 'rejects null and array document shapes without throwing' -TestCases @(
            @{ Json = 'null' }, @{ Json = '[]' }
        ) {
            param($Json)
            $temp = New-TemporaryBlueprintDirectory
            try {
                foreach ($name in @('tool-registry.json','control-matrix.json','leadership-claim-chain.json')) {
                    Set-Content (Join-Path $temp $name) $Json -Encoding UTF8
                }
                $thrown = $null
                try { $result = Test-OperationsBlueprintBundle $temp } catch { $thrown = $_ }
                $thrown | Should BeNullOrEmpty
                (@($result.ReasonCodes) -contains 'BLUEPRINT_FILE_INVALID_SHAPE') | Should Be $true
            }
            finally { Remove-Item $temp -Recurse -Force }
        }

        It 'rejects duplicate and case-colliding JSON properties before evaluation' -TestCases @(
            @{ DuplicateName = 'documentType' }, @{ DuplicateName = 'DocumentType' }
        ) {
            param($DuplicateName)
            $temp = New-TemporaryBlueprintDirectory
            try {
                Copy-Item $registryPath $temp
                Copy-Item $matrixPath $temp
                Copy-Item $chainPath $temp
                $target = Join-Path $temp 'tool-registry.json'
                $raw = Get-Content $target -Raw
                $needle = '  "documentType": "qualification-tool-registry",'
                $replacement = $needle + "`r`n  `"$DuplicateName`": `"qualification-tool-registry`","
                Set-Content $target ($raw.Replace($needle, $replacement)) -Encoding UTF8
                (@((Test-OperationsBlueprintBundle $temp).ReasonCodes) -contains 'DUPLICATE_JSON_PROPERTY') | Should Be $true
            }
            finally { Remove-Item $temp -Recurse -Force }
        }

        It 'returns a structured HOLD outside a Git repository' {
            $temp = New-TemporaryBlueprintDirectory
            try {
                Copy-Item $registryPath $temp
                Copy-Item $matrixPath $temp
                Copy-Item $chainPath $temp
                $thrown = $null
                try { $result = Test-OperationsBlueprintBundle $temp } catch { $thrown = $_ }
                $thrown | Should BeNullOrEmpty
                $result.Valid | Should Be $false
                $result.Allowed | Should Be $false
                (@($result.ReasonCodes) -contains 'IMMUTABLE_RELEASE_UNVERIFIED') | Should Be $true
            }
            finally { Remove-Item $temp -Recurse -Force }
        }

        It 'returns structured failure data for a non-allowlisted Git invocation shape' {
            $missing = Join-Path ([IO.Path]::GetTempPath()) ('missing-repo-' + [Guid]::NewGuid().ToString('N'))
            $thrown = $null
            try { $result = Invoke-GitRead @('-C', $missing, 'status', '--porcelain=v1') } catch { $thrown = $_ }
            $thrown | Should BeNullOrEmpty
            $result.ExitCode | Should Be 124
            @($result.Lines).Count | Should Be 0
            ([string]::IsNullOrWhiteSpace([string]$result.Error)) | Should Be $false
            [string]$result.Error | Should Be 'Trusted Git invocation shape is not allowlisted.'
            [string]$result.Error | Should Not Match ([regex]::Escape($missing))
        }

        It 'rejects an ignored untracked file inside the immutable release filesystem inventory' {
            $repoRoot = [IO.Path]::GetFullPath((Join-Path $here '..\..\..\..'))
            $excludePath = Join-Path $repoRoot '.git\info\exclude'
            $probeRelative = 'deliverables/laptop-qualification-program/v2.0.1/ignored-release-inventory-probe.synthetic'
            $probePath = Join-Path $repoRoot ($probeRelative.Replace('/', [IO.Path]::DirectorySeparatorChar))
            $mutex = [Threading.Mutex]::new($false, 'Local\LaptopQualificationImmutableInventoryTest')
            $lockTaken = $false
            $savedExcludeBytes = $null
            try {
                try { $lockTaken = $mutex.WaitOne([TimeSpan]::FromMinutes(2)) }
                catch [Threading.AbandonedMutexException] { $lockTaken = $true }
                $lockTaken | Should Be $true
                $savedExcludeBytes = [IO.File]::ReadAllBytes($excludePath)
                [IO.File]::AppendAllText($excludePath, "`n/$probeRelative`n", [Text.UTF8Encoding]::new($false))
                [IO.File]::WriteAllText($probePath, 'ignored but still prohibited', [Text.UTF8Encoding]::new($false))
                $result = Test-OperationsBlueprintBundle $here
                $result.Valid | Should Be $false
                (@($result.ReasonCodes) -contains 'IMMUTABLE_RELEASE_FILESYSTEM_INVENTORY_MISMATCH') | Should Be $true
            }
            finally {
                if ($lockTaken) {
                    if ([IO.File]::Exists($probePath)) { [IO.File]::Delete($probePath) }
                    if ($null -ne $savedExcludeBytes) { [IO.File]::WriteAllBytes($excludePath, $savedExcludeBytes) }
                    [void]$mutex.ReleaseMutex()
                }
                $mutex.Dispose()
            }
        }
    }
}
