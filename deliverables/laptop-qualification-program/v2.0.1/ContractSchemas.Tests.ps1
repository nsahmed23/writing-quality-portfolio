$script:ContractRoot = Split-Path -Parent $PSCommandPath
$script:SchemaRoot = Join-Path $script:ContractRoot 'schemas'
$script:NodeEvalBase64Bootstrap = 'eval(Buffer.from(process.argv.splice(1,1)[0],Buffer.from([98,97,115,101,54,52]).toString()).toString())'

function Resolve-ContractNodeModule {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$EnvironmentOverride,
        [Parameter(Mandatory = $true)][string]$ModuleRequest,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$KnownHostFallback
    )

    if (-not [string]::IsNullOrWhiteSpace($EnvironmentOverride)) {
        if (-not (Test-Path -LiteralPath $EnvironmentOverride)) {
            throw "Configured module path does not exist: $EnvironmentOverride"
        }
        return (Resolve-Path -LiteralPath $EnvironmentOverride).Path
    }

    $resolveScript = @'
const [request, root] = process.argv.slice(1);
try {
  process.stdout.write(require.resolve(request, { paths: [root] }));
} catch (error) {
  process.stderr.write(error.message);
  process.exit(2);
}
'@
    $resolveScriptBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($resolveScript))
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'SilentlyContinue'
        $resolved = & node -e $script:NodeEvalBase64Bootstrap $resolveScriptBase64 $ModuleRequest $script:ContractRoot 2>$null
        $probeExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($probeExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace(($resolved -join ''))) {
        return ($resolved -join '')
    }

    if (-not [string]::IsNullOrWhiteSpace($KnownHostFallback) -and (Test-Path -LiteralPath $KnownHostFallback)) {
        return (Resolve-Path -LiteralPath $KnownHostFallback).Path
    }

    throw "Unable to resolve $ModuleRequest. Install Ajv 8 and ajv-formats in this program's node_modules, or set AJV_2020_PATH and AJV_FORMATS_PATH to resolvable module files/directories."
}

$knownAjvFallback = if ([string]::IsNullOrWhiteSpace($env:APPDATA)) { '' } else { Join-Path $env:APPDATA 'npm\node_modules\firebase-tools\node_modules\ajv\dist\2020.js' }
$knownFormatsFallback = if ([string]::IsNullOrWhiteSpace($env:APPDATA)) { '' } else { Join-Path $env:APPDATA 'npm\node_modules\firebase-tools\node_modules\ajv-formats' }
$script:Ajv2020Path = Resolve-ContractNodeModule $env:AJV_2020_PATH 'ajv/dist/2020' $knownAjvFallback
$script:AjvFormatsPath = Resolve-ContractNodeModule $env:AJV_FORMATS_PATH 'ajv-formats' $knownFormatsFallback

$script:NodeValidator = @'
const fs = require("fs");
const [schemaPath, payloadBase64, ajvPath, formatsPath] = process.argv.slice(1);
const Ajv2020Module = require(ajvPath);
const addFormatsModule = require(formatsPath);
const Ajv2020 = Ajv2020Module.default || Ajv2020Module;
const addFormats = addFormatsModule.default || addFormatsModule;
const schema = JSON.parse(fs.readFileSync(schemaPath, "utf8"));
const payload = JSON.parse(Buffer.from(payloadBase64, "base64").toString("utf8"));
const ajv = new Ajv2020({ strict: true, allErrors: true });
addFormats(ajv);
const validate = ajv.compile(schema);
const valid = validate(payload);
process.stdout.write(JSON.stringify({ valid, errors: validate.errors || [] }));
'@
$script:NodeValidatorBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($script:NodeValidator))

function Invoke-ContractValidation {
    param(
        [Parameter(Mandatory = $true)][string]$SchemaName,
        [Parameter(Mandatory = $true)]$Instance
    )

    $schemaPath = Join-Path $script:SchemaRoot $SchemaName
    $json = $Instance | ConvertTo-Json -Depth 100 -Compress
    $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & node -e $script:NodeEvalBase64Bootstrap $script:NodeValidatorBase64 $schemaPath $payload $script:Ajv2020Path $script:AjvFormatsPath 2>&1
        $validatorExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($validatorExitCode -ne 0) {
        throw "Ajv validation process failed: $($output -join [Environment]::NewLine)"
    }
    return (($output -join [Environment]::NewLine) | ConvertFrom-Json)
}

function ConvertTo-CanonicalContractValue {
    param($Value)

    if ($null -eq $Value) { return $null }
    if ($Value -is [System.Collections.IDictionary]) {
        $normalized = [ordered]@{}
        foreach ($key in @($Value.Keys | ForEach-Object { [string]$_ } | Sort-Object -CaseSensitive)) {
            $normalized[$key] = ConvertTo-CanonicalContractValue $Value[$key]
        }
        return $normalized
    }
    if ($Value -is [pscustomobject]) {
        $normalized = [ordered]@{}
        foreach ($key in @($Value.PSObject.Properties.Name | Sort-Object -CaseSensitive)) {
            $normalized[$key] = ConvertTo-CanonicalContractValue $Value.$key
        }
        return $normalized
    }
    if ($Value -is [System.Collections.IEnumerable] -and $Value -isnot [string]) {
        $normalized = New-Object System.Collections.ArrayList
        foreach ($item in $Value) { [void]$normalized.Add((ConvertTo-CanonicalContractValue $item)) }
        return ,@($normalized)
    }
    return $Value
}

function ConvertTo-CanonicalContractJson {
    param($Value)
    return ((ConvertTo-CanonicalContractValue $Value) | ConvertTo-Json -Depth 100 -Compress)
}

function Get-ContractEvidenceDeviceIds {
    param($Record)
    if ($Record.subject.kind -ceq 'device') { return @([string]$Record.subject.deviceId) }
    return @($Record.subject.units | ForEach-Object { [string]$_.deviceId })
}

function Test-ContractBundleSemantics {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)]$TestPlan,
        [Parameter(Mandatory = $true)]$ThresholdPolicy,
        [Parameter(Mandatory = $true)]$Verdict,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$EvidenceRecords,
        [AllowEmptyCollection()][object[]]$PilotAuthorizationRecords = @()
    )

    $errors = New-Object 'System.Collections.Generic.List[string]'

    if ($Manifest.testPlanRef -cne $TestPlan.planId) { $errors.Add('manifest.testPlanRef does not resolve to test-plan.planId') }
    if ($TestPlan.manifestRef -cne $Manifest.manifestId) { $errors.Add('test-plan.manifestRef does not resolve to candidate-manifest.manifestId') }
    if ($Manifest.thresholdPolicyRef -cne $ThresholdPolicy.policyId) { $errors.Add('manifest.thresholdPolicyRef does not resolve to threshold-policy.policyId') }
    if ($TestPlan.thresholdPolicyRef -cne $ThresholdPolicy.policyId) { $errors.Add('test-plan.thresholdPolicyRef does not resolve to threshold-policy.policyId') }
    if ($Verdict.manifestRef -cne $Manifest.manifestId) { $errors.Add('verdict.manifestRef does not resolve to candidate-manifest.manifestId') }
    if ($Verdict.qualificationAuthority -cne $Manifest.qualificationAuthority) { $errors.Add('final qualificationAuthority differs from the frozen manifest') }
    if ($Manifest.tier -cne $TestPlan.qualificationTier) { $errors.Add('manifest tier and test-plan qualificationTier differ') }

    $pilotFloor = [int]$TestPlan.samplingFloors['production-pilot'].minUnits
    if ([int]$Manifest.pilotPopulationPlan.targetCount -lt $pilotFloor) { $errors.Add('pilot targetCount is below the frozen production-pilot floor') }

    $testIds = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
    foreach ($test in $TestPlan.tests) {
        if (-not $testIds.Add([string]$test.testId)) { $errors.Add('testId values are not unique') }
    }

    $phase0Freezes = [ordered]@{
        manifest = [DateTimeOffset]::Parse([string]$Manifest.frozenAt)
        'test-plan' = [DateTimeOffset]::Parse([string]$TestPlan.frozenAt)
        'threshold-policy' = [DateTimeOffset]::Parse([string]$ThresholdPolicy.frozenAt)
    }

    $expectedReusePolicyRef = "$($TestPlan.planId)#/evidenceReusePolicy"
    $dependencyPropertyByDimension = @{
        hardware = 'hardware'; firmware = 'firmware'; 'operating-system' = 'operatingSystem'
        agents = 'agents'; applications = 'applications'; peripherals = 'peripherals'
        conditions = 'conditions'; 'test-and-pack' = 'testAndPack'; 'support-currency' = 'supportCurrency'
        'threshold-policy' = 'thresholdPolicy'; staleness = 'staleness'
    }
    foreach ($role in @('incumbent', 'sibling-or-alternative')) {
        $evidencePlan = $Manifest.controls[$role].evidencePlan
        if ($evidencePlan.reusePolicyRef -cne $expectedReusePolicyRef) { $errors.Add("control reusePolicyRef does not resolve to the frozen plan: $role") }
        if ($evidencePlan.mode -ceq 'cache-reuse') {
            $cachePolicy = $TestPlan.evidenceReusePolicy.compatibilityCache
            if ([int]$evidencePlan.cacheAgeDays -gt [int]$cachePolicy.maximumAgeDays) { $errors.Add("control cache exceeds the frozen maximum age: $role") }
            if ([int]$evidencePlan.bridge.candidateUnits -lt [int]$cachePolicy.bridge.minimumCandidateUnits) { $errors.Add("control bridge is below the frozen unit minimum: $role") }
            if ([int]$evidencePlan.bridge.repetitionsPerCriticalCombination -lt [int]$cachePolicy.bridge.minimumRepetitionsPerCriticalCombination) { $errors.Add("control bridge is below the frozen repetition minimum: $role") }
            if ($evidencePlan.bridge.criticalMatrixRef -cne $cachePolicy.bridge.criticalMatrixRef -or $evidencePlan.bridge.functionalRuleRef -cne $cachePolicy.bridge.functionalRuleRef -or $evidencePlan.bridge.repeatabilityRuleRef -cne $cachePolicy.bridge.repeatabilityRuleRef -or $evidencePlan.bridge.driftRuleRef -cne $cachePolicy.bridge.driftRuleRef) { $errors.Add("control bridge references differ from the frozen policy: $role") }
            foreach ($dimension in $cachePolicy.requiredDependencyDimensions) {
                $property = $dependencyPropertyByDimension[[string]$dimension]
                if ([string]::IsNullOrWhiteSpace($property) -or $evidencePlan.dependencyMatch[$property] -ne $true) { $errors.Add("control cache dependency is not an exact match ($dimension): $role") }
            }
        }
        if ($evidencePlan.mode -ceq 'bootstrap' -and $evidencePlan.fullFreshFloorRequired -ne $true) { $errors.Add("control bootstrap does not require the full fresh floor: $role") }
    }

    $evidenceById = New-Object 'System.Collections.Generic.Dictionary[string,object]' ([System.StringComparer]::Ordinal)
    foreach ($record in $EvidenceRecords) {
        if ($evidenceById.ContainsKey([string]$record.recordId)) {
            $errors.Add("duplicate evidence recordId: $($record.recordId)")
        } else {
            $evidenceById[[string]$record.recordId] = $record
        }
    }
    $gateRecordsByTest = New-Object 'System.Collections.Generic.Dictionary[string,object]' ([System.StringComparer]::Ordinal)
    $releaseRunOwnerById = New-Object 'System.Collections.Generic.Dictionary[string,object]' ([System.StringComparer]::Ordinal)
    $releaseDeviceIdentityById = New-Object 'System.Collections.Generic.Dictionary[string,object]' ([System.StringComparer]::Ordinal)
    foreach ($record in $EvidenceRecords) {
        $testMatches = @($TestPlan.tests | Where-Object { $_.testId -ceq $record.testRef })
        $testDefinition = $null
        if ($testMatches.Count -ne 1) {
            $errors.Add("evidence testRef must resolve to exactly one frozen test definition: $($record.recordId)")
        } else {
            $testDefinition = $testMatches[0]
            if (@($testDefinition.conditions | Where-Object { $_.conditionId -ceq $record.conditionRef }).Count -ne 1) { $errors.Add("evidence conditionRef must resolve within its frozen test definition: $($record.recordId)") }
            if ($record.testPackVersion -cne $testDefinition.testPackVersion) { $errors.Add("evidence testPackVersion differs from its frozen test definition: $($record.recordId)") }
        }

        $observedAt = [DateTimeOffset]::Parse([string]$record.timestamp)
        $admittedAt = [DateTimeOffset]::Parse([string]$record.admission.admittedAt)
        foreach ($freezeName in $phase0Freezes.Keys) {
            if (-not ($admittedAt -gt $phase0Freezes[$freezeName])) { $errors.Add("evidence admission is not strictly after the $freezeName freeze: $($record.recordId)") }
            if ($record.admission.mode -ceq 'fresh' -and -not ($observedAt -gt $phase0Freezes[$freezeName])) { $errors.Add("fresh evidence observation is not strictly after the $freezeName freeze: $($record.recordId)") }
        }
        if ($admittedAt -lt $observedAt) { $errors.Add("evidence admittedAt precedes its observation timestamp: $($record.recordId)") }

        if ($record.provenance -ceq 'T2') {
            $corroborationId = [string]$record.corroborationRef.recordRef
            if ($corroborationId -ceq [string]$record.recordId) {
                $errors.Add("T2 record self-corroborates: $($record.recordId)")
            } elseif (-not $evidenceById.ContainsKey($corroborationId)) {
                $errors.Add("T2 corroboration reference does not resolve: $corroborationId")
            } else {
                $corroboration = $evidenceById[$corroborationId]
                if ($corroboration.provenance -notin @('T0', 'T1')) { $errors.Add("T2 corroboration is not T0 or T1: $corroborationId") }
                if ($corroboration.provenance -cne $record.corroborationRef.expectedProvenance) { $errors.Add("T2 corroboration provenance does not match expectedProvenance: $corroborationId") }
            }
        }

        if ($record.provenance -ceq 'T0') {
            $deviceIds = @(Get-ContractEvidenceDeviceIds $record)
            $evidenceUnits = if ($record.subject.kind -ceq 'device') { @($record.subject) } else { @($record.subject.units) }
            if ($deviceIds.Count -ne [int]$record.distribution.unitCount) { $errors.Add("identified units do not equal distribution.unitCount: $($record.recordId)") }
            $recordDeviceIds = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
            foreach ($deviceId in $deviceIds) {
                if (-not $recordDeviceIds.Add([string]$deviceId)) { $errors.Add("duplicate device identity inside evidence record: $($record.recordId)") }
            }
            if ($record.admission.mode -ceq 'fresh' -and $record.subject.manifestRef -cne $Manifest.manifestId) { $errors.Add("fresh T0 evidence subject does not reference the current manifest: $($record.recordId)") }
            foreach ($unit in $evidenceUnits) {
                if ($record.admission.mode -ceq 'fresh' -and $unit.manifestRef -cne $Manifest.manifestId) { $errors.Add("fresh T0 evidence unit does not reference the current manifest: $($record.recordId) / $($unit.deviceId)") }
                $deviceIdentity = ConvertTo-CanonicalContractJson ([ordered]@{
                    role = [string]$unit.role
                    configurationIdentity = [string]$unit.configurationIdentity
                    manifestRef = [string]$unit.manifestRef
                })
                if ($releaseDeviceIdentityById.ContainsKey([string]$unit.deviceId) -and $releaseDeviceIdentityById[[string]$unit.deviceId] -cne $deviceIdentity) {
                    $errors.Add("device identity changes role, configuration, or manifest across the evidence release: $($unit.deviceId)")
                } else {
                    $releaseDeviceIdentityById[[string]$unit.deviceId] = $deviceIdentity
                }
            }
            if (@($record.distribution.runs).Count -ne [int]$record.distribution.runCount) { $errors.Add("run identities do not equal distribution.runCount: $($record.recordId)") }
            $recordRunIds = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
            foreach ($run in $record.distribution.runs) {
                if (-not $recordRunIds.Add([string]$run.runId)) { $errors.Add("duplicate run identity inside evidence record: $($record.recordId)") }
                if ($deviceIds -cnotcontains [string]$run.deviceId) { $errors.Add("run identity references a device outside its evidence subject: $($record.recordId)") }
                if ($releaseRunOwnerById.ContainsKey([string]$run.runId)) {
                    $errors.Add("runId is not unique across the evidence release: $($run.runId)")
                } else {
                    $releaseRunOwnerById[[string]$run.runId] = [string]$record.recordId
                }
            }
            if ($record.subject.kind -ceq 'batch-stratum') {
                foreach ($unit in $record.subject.units) {
                    if ($unit.role -cne $record.subject.role -or $unit.configurationIdentity -cne $record.subject.configurationIdentity -or $unit.manifestRef -cne $record.subject.manifestRef -or $unit.baselineFingerprintSha256 -ne $record.subject.baselineFingerprintSha256) {
                        $errors.Add("batch unit does not match its declared identity/baseline stratum: $($record.recordId)")
                        break
                    }
                }
                if ($record.subject.baselineFingerprintSha256 -ne $record.baseline.baselineFingerprintSha256) { $errors.Add("batch subject and runtime baseline fingerprints differ: $($record.recordId)") }
            }
            if ([int]$record.coverage.observedUnits -gt [int]$record.coverage.plannedUnits -or [int]$record.coverage.observedRuns -gt [int]$record.coverage.plannedRuns) { $errors.Add("coverage observations exceed plan: $($record.recordId)") }
            if ([int]$record.coverage.observedUnits -ne [int]$record.distribution.unitCount -or [int]$record.coverage.observedRuns -ne [int]$record.distribution.runCount) { $errors.Add("coverage counts and distribution counts differ: $($record.recordId)") }
            $expectedCoveragePct = 100.0 * [double]$record.coverage.observedRuns / [double]$record.coverage.plannedRuns
            if ([Math]::Abs($expectedCoveragePct - [double]$record.coverage.percent) -gt 0.000001) { $errors.Add("coverage percentage is inconsistent: $($record.recordId)") }
            if ([int]$record.distribution.missingResults.count -ne ([int]$record.coverage.plannedRuns - [int]$record.coverage.observedRuns)) { $errors.Add("missing-result count is inconsistent: $($record.recordId)") }
            if ($record.distribution.summary.kind -ceq 'numeric') {
                $spread = $record.distribution.summary.spread
                if ($spread.kind -ceq 'range' -and -not ([double]$spread.min -le [double]$record.distribution.summary.median -and [double]$record.distribution.summary.median -le [double]$spread.max)) { $errors.Add("numeric range does not contain the median: $($record.recordId)") }
                if ($spread.kind -ceq 'percentile' -and -not ([double]$spread.p05 -le [double]$record.distribution.summary.median -and [double]$record.distribution.summary.median -le [double]$spread.p95)) { $errors.Add("percentile spread does not contain the median: $($record.recordId)") }
            }

            if ($record.admission.mode -ceq 'compatibility-cache' -and $null -ne $testDefinition) {
                $cachePolicy = $TestPlan.evidenceReusePolicy.compatibilityCache
                if ($testDefinition.class -cne 'application-compatibility') { $errors.Add("only application-compatibility evidence may use compatibility-cache admission: $($record.recordId)") }
                if ($record.admission.reusePolicyRef -cne $expectedReusePolicyRef) { $errors.Add("cached evidence reusePolicyRef does not resolve to the frozen test plan: $($record.recordId)") }
                $cacheAgeDays = ($admittedAt - $observedAt).TotalDays
                if ($cacheAgeDays -lt 0 -or $cacheAgeDays -gt [double]$cachePolicy.maximumAgeDays) { $errors.Add("cached evidence exceeds the frozen maximum age: $($record.recordId)") }
                $bridgeAcceptedAt = [DateTimeOffset]::Parse([string]$record.admission.bridgeAcceptedAt)
                if (-not ($admittedAt -gt $bridgeAcceptedAt)) { $errors.Add("cached evidence admission does not strictly follow bridge acceptance: $($record.recordId)") }
                if ($record.admission.criticalMatrixRef -cne $cachePolicy.bridge.criticalMatrixRef -or $record.admission.functionalRuleRef -cne $cachePolicy.bridge.functionalRuleRef -or $record.admission.repeatabilityRuleRef -cne $cachePolicy.bridge.repeatabilityRuleRef -or $record.admission.driftRuleRef -cne $cachePolicy.bridge.driftRuleRef) { $errors.Add("cached evidence bridge rules differ from the frozen policy: $($record.recordId)") }
                foreach ($dimension in $cachePolicy.requiredDependencyDimensions) {
                    $property = $dependencyPropertyByDimension[[string]$dimension]
                    if ([string]::IsNullOrWhiteSpace($property) -or $record.admission.dependencyMatch[$property] -ne $true) { $errors.Add("cached evidence dependency is not an exact match ($dimension): $($record.recordId)") }
                }
                $bridgeRecords = @()
                foreach ($bridgeRef in $record.admission.bridgeEvidenceRefs) {
                    if (-not $evidenceById.ContainsKey([string]$bridgeRef)) {
                        $errors.Add("cached evidence bridge reference does not resolve: $bridgeRef")
                    } else {
                        $bridgeRecords += $evidenceById[[string]$bridgeRef]
                    }
                }
                $bridgeUnits = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
                $bridgeRunsByDevice = New-Object 'System.Collections.Generic.Dictionary[string,object]' ([System.StringComparer]::Ordinal)
                foreach ($bridgeRecord in $bridgeRecords) {
                    if ($bridgeRecord.provenance -cne 'T0' -or $bridgeRecord.admission.mode -cne 'fresh' -or $bridgeRecord.evidenceUse -cne 'gate-or-verdict' -or $bridgeRecord.testRef -cne $record.testRef -or $bridgeRecord.conditionRef -cne $record.conditionRef -or $bridgeRecord.baseline.baselineFingerprintSha256 -ne $record.baseline.baselineFingerprintSha256 -or $bridgeRecord.subject.role -cne 'candidate') { $errors.Add("cached evidence bridge is not fresh comparable candidate evidence: $($record.recordId)") }
                    $bridgeObservedAt = [DateTimeOffset]::Parse([string]$bridgeRecord.timestamp)
                    $bridgeAdmittedAt = [DateTimeOffset]::Parse([string]$bridgeRecord.admission.admittedAt)
                    if (-not ($admittedAt -gt $bridgeObservedAt) -or -not ($admittedAt -gt $bridgeAdmittedAt)) { $errors.Add("cached evidence admission does not strictly follow every bridge observation and admission: $($record.recordId)") }
                    if ($bridgeAcceptedAt -le $bridgeObservedAt -or $bridgeAcceptedAt -le $bridgeAdmittedAt) { $errors.Add("cached evidence bridge acceptance does not strictly follow its bridge observation and admission: $($record.recordId)") }
                    if ($bridgeRecord.testPackVersion -cne $record.testPackVersion) { $errors.Add("cached evidence and bridge testPackVersion values differ: $($record.recordId)") }
                    foreach ($deviceId in @(Get-ContractEvidenceDeviceIds $bridgeRecord)) { [void]$bridgeUnits.Add($deviceId) }
                    foreach ($run in $bridgeRecord.distribution.runs) {
                        if (-not $bridgeRunsByDevice.ContainsKey([string]$run.deviceId)) { $bridgeRunsByDevice[[string]$run.deviceId] = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal) }
                        [void]$bridgeRunsByDevice[[string]$run.deviceId].Add([string]$run.runId)
                    }
                }
                if ($bridgeUnits.Count -lt [int]$cachePolicy.bridge.minimumCandidateUnits) { $errors.Add("cached evidence bridge is below the frozen unit minimum: $($record.recordId)") }
                foreach ($bridgeUnit in $bridgeUnits) {
                    $bridgeRunCount = if ($bridgeRunsByDevice.ContainsKey($bridgeUnit)) { $bridgeRunsByDevice[$bridgeUnit].Count } else { 0 }
                    if ($bridgeRunCount -lt [int]$cachePolicy.bridge.minimumRepetitionsPerCriticalCombination) { $errors.Add("cached evidence bridge is below the frozen repetition minimum: $($record.recordId)") }
                }
                $cacheAndBridgeUnits = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
                $cacheAndBridgeRunsByDevice = New-Object 'System.Collections.Generic.Dictionary[string,object]' ([System.StringComparer]::Ordinal)
                foreach ($admittedRecord in @($record) + @($bridgeRecords)) {
                    foreach ($deviceId in @(Get-ContractEvidenceDeviceIds $admittedRecord)) { [void]$cacheAndBridgeUnits.Add($deviceId) }
                    foreach ($run in $admittedRecord.distribution.runs) {
                        if (-not $cacheAndBridgeRunsByDevice.ContainsKey([string]$run.deviceId)) { $cacheAndBridgeRunsByDevice[[string]$run.deviceId] = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal) }
                        [void]$cacheAndBridgeRunsByDevice[[string]$run.deviceId].Add([string]$run.runId)
                    }
                }
                $compatibilityFloor = $TestPlan.samplingFloors['application-compatibility']
                if ($cacheAndBridgeUnits.Count -lt [int]$compatibilityFloor.minUnits) { $errors.Add("cached evidence plus its referenced bridge is below the full compatibility unit floor: $($record.recordId)") }
                foreach ($admittedUnit in $cacheAndBridgeUnits) {
                    $admittedRunCount = if ($cacheAndBridgeRunsByDevice.ContainsKey($admittedUnit)) { $cacheAndBridgeRunsByDevice[$admittedUnit].Count } else { 0 }
                    if ($admittedRunCount -lt [int]$compatibilityFloor.minRepetitionsPerUnit) { $errors.Add("cached evidence plus its referenced bridge is below the full compatibility repetition floor: $($record.recordId)") }
                }
            }

            if ($record.evidenceUse -ceq 'gate-or-verdict' -and $null -ne $testDefinition) {
                $testRef = [string]$record.testRef
                if (-not $gateRecordsByTest.ContainsKey($testRef)) { $gateRecordsByTest[$testRef] = New-Object System.Collections.ArrayList }
                [void]$gateRecordsByTest[$testRef].Add($record)
            }
        }
    }

    foreach ($testDefinition in $TestPlan.tests) {
        $testRef = [string]$testDefinition.testId
        if (-not $gateRecordsByTest.ContainsKey($testRef)) {
            $errors.Add("gate evidence is missing for required frozen test: $testRef")
            continue
        }
        $floor = $TestPlan.samplingFloors[[string]$testDefinition.class]
        $roleByDevice = New-Object 'System.Collections.Generic.Dictionary[string,object]' ([System.StringComparer]::Ordinal)
        foreach ($record in $gateRecordsByTest[$testRef]) {
            foreach ($deviceId in @(Get-ContractEvidenceDeviceIds $record)) {
                if ($roleByDevice.ContainsKey($deviceId) -and $roleByDevice[$deviceId] -cne $record.subject.role) {
                    $errors.Add("the same device identity is assigned to multiple roles for ${testRef}: $deviceId")
                } else {
                    $roleByDevice[$deviceId] = [string]$record.subject.role
                }
            }
        }
        foreach ($role in $testDefinition.appliesTo) {
            foreach ($condition in $testDefinition.conditions) {
                $roleConditionRecords = @($gateRecordsByTest[$testRef] | Where-Object { $_.subject.role -ceq $role -and $_.conditionRef -ceq $condition.conditionId })
                if ($roleConditionRecords.Count -eq 0) {
                    $errors.Add("gate evidence is missing required role/condition coverage for ${testRef}: $role / $($condition.conditionId)")
                    continue
                }
                $strata = @{}
                foreach ($record in $roleConditionRecords) {
                    $stratum = [string]$record.baseline.baselineFingerprintSha256
                    if (-not $strata.ContainsKey($stratum)) { $strata[$stratum] = New-Object System.Collections.ArrayList }
                    [void]$strata[$stratum].Add($record)
                }
                foreach ($stratum in $strata.Keys) {
                    $uniqueUnits = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
                    $uniqueRuns = New-Object 'System.Collections.Generic.Dictionary[string,object]' ([System.StringComparer]::Ordinal)
                    $runsByDevice = New-Object 'System.Collections.Generic.Dictionary[string,object]' ([System.StringComparer]::Ordinal)
                    foreach ($record in $strata[$stratum]) {
                        foreach ($deviceId in @(Get-ContractEvidenceDeviceIds $record)) { [void]$uniqueUnits.Add($deviceId) }
                        foreach ($run in $record.distribution.runs) {
                            if ($uniqueRuns.ContainsKey([string]$run.runId)) {
                                $errors.Add("gate evidence reuses run identity within an aggregate stratum: $($run.runId)")
                            } else {
                                $uniqueRuns[[string]$run.runId] = [string]$run.deviceId
                                if (-not $runsByDevice.ContainsKey([string]$run.deviceId)) { $runsByDevice[[string]$run.deviceId] = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal) }
                                [void]$runsByDevice[[string]$run.deviceId].Add([string]$run.runId)
                            }
                        }
                    }
                    if ($uniqueUnits.Count -lt [int]$floor.minUnits) { $errors.Add("aggregate gate unit coverage is below the frozen $($testDefinition.class) floor for $role / $($condition.conditionId) / $stratum") }
                    foreach ($deviceId in $uniqueUnits) {
                        $runCount = if ($runsByDevice.ContainsKey($deviceId)) { $runsByDevice[$deviceId].Count } else { 0 }
                        if ($runCount -lt [int]$floor.minRepetitionsPerUnit) { $errors.Add("aggregate gate repetitions are below the frozen $($testDefinition.class) floor for $deviceId") }
                    }
                }
            }
        }
    }

    $authorizationMatches = @($PilotAuthorizationRecords | Where-Object { $_.verdictId -ceq $Verdict.pilotAuthorizationRecordRef })
    $authorization = $null
    if ($authorizationMatches.Count -ne 1) {
        $errors.Add('pilotAuthorizationRecordRef must resolve to exactly one authorization record')
    } else {
        $authorization = $authorizationMatches[0]
        if ($authorization.recordStage -cne 'pilot-authorization' -or $authorization.manifestRef -cne $Manifest.manifestId) { $errors.Add('referenced pilot authorization has the wrong stage or manifest') }
        if ($authorization.qualificationAuthority -cne $Manifest.qualificationAuthority) { $errors.Add('pilot authorization qualificationAuthority differs from the frozen manifest') }
        if ($authorization.pilotPopulationPlanRef -cne "$($Manifest.manifestId)#/pilotPopulationPlan" -or $authorization.privacyOwner -cne $Manifest.pilotPopulationPlan.privacyOwner) { $errors.Add('pilot authorization population/privacy references do not match the frozen manifest') }
        if ((ConvertTo-CanonicalContractJson $authorization.pilotAuthorization) -cne (ConvertTo-CanonicalContractJson $Verdict.pilotAuthorization)) { $errors.Add('final pilotAuthorization snapshot differs from the immutable authorization record') }
    }

    if ($Manifest.tier -ceq 'full' -and ($Verdict.pilotAuthorization.status -cne 'AUTHORIZED' -or $Verdict.pilotCompletion.status -cne 'COMPLETED')) {
        $errors.Add('full qualification requires an authorized and completed production pilot')
    }

    if ($Verdict.pilotCompletion.status -ceq 'COMPLETED' -and $null -ne $authorization) {
            if ($authorization.pilotAuthorization.status -cne 'AUTHORIZED') { $errors.Add('referenced pilot authorization is not AUTHORIZED') }
            $authorizedAt = [DateTimeOffset]::Parse([string]$authorization.pilotAuthorization.approvedAt)
            $startedAt = [DateTimeOffset]::Parse([string]$Verdict.pilotCompletion.startedAt)
            $completedAt = [DateTimeOffset]::Parse([string]$Verdict.pilotCompletion.completedAt)
            if (-not ($authorizedAt -lt $startedAt -and $startedAt -lt $completedAt)) {
                $errors.Add('pilot chronology must satisfy authorization < start < completion')
            }
    }

    foreach ($personaVerdict in $Verdict.personaVerdicts) {
        $waterfall = $personaVerdict.capacityWaterfall
        if ($waterfall.thresholdPolicyRef -cne $ThresholdPolicy.policyId) { $errors.Add("persona thresholdPolicyRef does not resolve: $($personaVerdict.persona)") }
        if ([double]$waterfall.memory.memoryReserveGB -ne [double]$ThresholdPolicy.reserves.memoryReserveGB.value) { $errors.Add("persona memory reserve differs from frozen policy: $($personaVerdict.persona)") }
        if ([double]$waterfall.storage.storageReserveGB -ne [double]$ThresholdPolicy.reserves.storageReserveGB.value) { $errors.Add("persona storage reserve differs from frozen policy: $($personaVerdict.persona)") }

        $expectedMemory = [double]$waterfall.memory.physicalMemoryGB - [double]$waterfall.memory.corporateFloorGB - [double]$waterfall.memory.memoryReserveGB
        if ([Math]::Abs($expectedMemory - [double]$waterfall.memory.remainingWorkloadHeadroomGB) -gt 0.000001) { $errors.Add("persona memory waterfall arithmetic is invalid: $($personaVerdict.persona)") }
        $expectedMemoryOutcome = if ($expectedMemory -ge [double]$waterfall.memory.personaRequirementGB) { 'PASS' } else { 'SHORTFALL' }
        if ($waterfall.memory.outcome -cne $expectedMemoryOutcome) { $errors.Add("persona memory outcome is inconsistent: $($personaVerdict.persona)") }

        $expectedStorage = [double]$waterfall.storage.formattedCapacityGB - [double]$waterfall.storage.corporateImageGB - [double]$waterfall.storage.storageReserveGB - [double]$waterfall.storage.personaWorkingSetGB
        if ([Math]::Abs($expectedStorage - [double]$waterfall.storage.remainingWorkloadHeadroomGB) -gt 0.000001) { $errors.Add("persona storage waterfall arithmetic is invalid: $($personaVerdict.persona)") }
        $expectedStorageOutcome = if ($expectedStorage -ge 0) { 'PASS' } else { 'SHORTFALL' }
        if ($waterfall.storage.outcome -cne $expectedStorageOutcome) { $errors.Add("persona storage outcome is inconsistent: $($personaVerdict.persona)") }
    }

    return [pscustomobject]@{ valid = ($errors.Count -eq 0); errors = @($errors) }
}

function New-SamplingFloor {
    param(
        [int]$Units,
        [int]$Repetitions,
        [bool]$PerRole,
        [string]$Concern,
        [string]$RepetitionUnit
    )
    return [ordered]@{
        minUnits = $Units
        minRepetitionsPerUnit = $Repetitions
        perRole = $PerRole
        samplingConcern = $Concern
        selectionMethod = 'Preselected from the declared population'
        repetitionUnit = $RepetitionUnit
    }
}

function New-TestDefinition {
    param([string]$Class, [int]$Phase)
    $roles = if ($Phase -eq 3 -or $Class -eq 'component-identification') {
        @('candidate', 'incumbent', 'sibling-or-alternative')
    } else {
        @('candidate')
    }
    return [ordered]@{
        testId = "test-$Class"
        testVersion = 'fixture-v1'
        testPackVersion = 'fixture-pack-v1'
        phase = $Phase
        class = $Class
        samplingFloorRef = "#/samplingFloors/$Class"
        purpose = "Fixture coverage for $Class"
        dependencies = @()
        conditions = @(
            [ordered]@{
                conditionId = 'fixture-condition'
                description = 'Deterministic fixture condition'
            }
        )
        appliesTo = @($roles)
        expectedEvidence = @('fixture-evidence-record')
        rules = [ordered]@{
            pass = 'Meets the frozen policy constant'
            hold = 'Critical identity remains unknown'
            fail = 'Violates the frozen policy constant'
            inconclusive = 'Coverage is below the frozen floor'
        }
        stalenessDependencies = @('test-pack')
    }
}

function New-ValidTestPlan {
    $floors = [ordered]@{}

    $floor = New-SamplingFloor 5 1 $true 'Supplier variation' 'complete enumeration'
    $floor.requiredStrata = @('known-lot', 'supplier')
    $floors['component-identification'] = $floor

    $floors['controlled-benchmark'] = New-SamplingFloor 3 5 $true 'Run and unit variance' 'accepted run per condition'

    $floor = New-SamplingFloor 3 3 $true 'Steady-state variance' 'accepted stabilized run per condition'
    $floor.stabilizationRule = 'Reach the frozen steady-state criterion before each accepted run'
    $floors['sustained-performance'] = $floor

    $floor = New-SamplingFloor 3 3 $true 'Cycle variation' 'full cycle or overnight session per condition'
    $floor.sessionDefinition = 'A complete frozen full-cycle or overnight protocol'
    $floors['battery-standby'] = $floor

    $floor = New-SamplingFloor 3 20 $true 'Intermittent dock faults' 'complete attach-detach-sleep-resume cycle'
    $floor.matrixCoverageRef = 'dock-matrix-fixture'
    $floors['dock-reliability'] = $floor

    $floor = New-SamplingFloor 2 2 $false 'Application and agent combinations' 'accepted critical-matrix run'
    $floor.matrixCoverageRef = 'application-matrix-fixture'
    $floors['application-compatibility'] = $floor

    $quota = [ordered]@{
        persona = [ordered]@{ 'fixture-persona' = 1 }
        region = [ordered]@{ 'fixture-region' = 1 }
        workPattern = [ordered]@{ 'fixture-work-pattern' = 1 }
    }
    $floor = New-SamplingFloor 30 10 $false 'Population representation' 'participant evidence day'
    $floor.minEvidenceDays = 10
    $floor.representative = $true
    $floor.volunteerOnly = $false
    $floor.stratumQuotas = $quota
    $floors['production-pilot'] = $floor

    $floor = New-SamplingFloor 24 1 $false 'Selection and nonresponse bias' 'completed exit survey'
    $floor.minResponseRatePct = 80
    $floor.representative = $true
    $floor.volunteerOnly = $false
    $floor.stratumQuotas = $quota
    $floors['sentiment'] = $floor

    $floor = New-SamplingFloor 3 3 $true 'Measurement-window variance' 'settled measurement window per image'
    $floor.imageBaselinesRef = 'image-baselines-fixture'
    $floors['corporate-floor'] = $floor

    $floor = New-SamplingFloor 3 3 $true 'Scheduled and burst-state variance' 'observation window per agent state'
    $floor.agentStateMatrixRef = 'agent-state-matrix-fixture'
    $floors['agent-state'] = $floor

    $tests = @(
        (New-TestDefinition 'component-identification' 1),
        (New-TestDefinition 'controlled-benchmark' 3),
        (New-TestDefinition 'sustained-performance' 3),
        (New-TestDefinition 'battery-standby' 3),
        (New-TestDefinition 'dock-reliability' 3),
        (New-TestDefinition 'application-compatibility' 2),
        (New-TestDefinition 'production-pilot' 4),
        (New-TestDefinition 'sentiment' 4),
        (New-TestDefinition 'corporate-floor' 3),
        (New-TestDefinition 'agent-state' 3)
    )

    return [ordered]@{
        planId = 'test-plan-fixture'
        schemaVersion = '2.0.1'
        status = 'frozen'
        qualificationTier = 'full'
        manifestRef = 'manifest-fixture'
        thresholdPolicyRef = 'threshold-policy-fixture'
        dependencyReviewRef = 'dependency-review-fixture'
        omittedClasses = @()
        frozenAt = '2026-08-27T12:00:00Z'
        approvedBy = 'Fixture approver'
        samplingFloors = $floors
        evidenceReusePolicy = [ordered]@{
            policyVersion = 'fixture-reuse-v1'
            status = 'frozen'
            frozenAt = '2026-08-27T12:00:00Z'
            approvedBy = 'Fixture approver'
            documentaryContext = [ordered]@{
                countsTowardSamplingFloor = $false
                replacesFreshPhase1 = $false
                exactConfigurationRequired = $true
                artifactHashVerificationRequired = $true
                currencyWindowRequired = $true
                unchangedDependenciesRequired = $true
            }
            compatibilityCache = [ordered]@{
                eligibleClass = 'application-compatibility'
                maximumAgeDays = 30
                requiredDependencyDimensions = @(
                    'hardware', 'firmware', 'operating-system', 'agents', 'applications',
                    'peripherals', 'conditions', 'test-and-pack', 'support-currency',
                    'threshold-policy', 'staleness'
                )
                exactSubjectRequired = $true
                artifactHashVerificationRequired = $true
                completeEvidenceRequired = $true
                separateStrataOnMismatch = $true
                bridge = [ordered]@{
                    minimumCandidateUnits = 1
                    minimumRepetitionsPerCriticalCombination = 2
                    criticalMatrixRef = 'fixture-critical-matrix'
                    functionalRuleRef = 'fixture-functional-rule'
                    repeatabilityRuleRef = 'fixture-repeatability-rule'
                    driftRuleRef = 'fixture-drift-rule'
                    cachePlusBridgeMustMeetFullFloor = $true
                }
            }
            dynamicEvidence = [ordered]@{
                classes = @(
                    'controlled-benchmark', 'sustained-performance', 'battery-standby',
                    'dock-reliability', 'corporate-floor', 'agent-state',
                    'production-pilot', 'sentiment'
                )
                cachedRecordsCountTowardFloors = $false
                freshConcurrentEvidenceRequired = $true
            }
            bootstrap = [ordered]@{
                compatibilityFullFreshFloorRequired = $true
                controlFullFreshClassFloorRequired = $true
                productionTelemetryCountsTowardFloor = $false
                singleAnchorRunSufficient = $false
            }
        }
        tests = $tests
    }
}

function New-ValidT2EvidenceRecord {
    return [ordered]@{
        recordId = 'evidence-t2-fixture'
        schemaVersion = '2.0.1'
        recordKind = 'documentary-claim'
        provenance = 'T2'
        evidenceUse = 'gate-or-verdict'
        corroborationRef = [ordered]@{
            recordRef = 'evidence-t1-fixture'
            expectedProvenance = 'T1'
            claimScope = 'The same fixture claim'
        }
        subject = [ordered]@{
            kind = 'configuration'
            configurationIdentity = 'configuration-fixture'
            sourceDocumentRef = 'document-fixture'
        }
        baseline = [ordered]@{
            configurationEnvelopeRef = 'envelope-fixture'
            platformApplicability = @('platform-fixture')
            baselineFingerprintSha256 = [string]::new('a', 64)
        }
        tool = [ordered]@{ name = 'Fixture retriever'; version = '1.0' }
        testRef = 'test-application-compatibility'
        conditionRef = 'fixture-condition'
        testPackVersion = 'fixture-pack-v1'
        timestamp = '2026-08-27T13:00:00Z'
        admission = [ordered]@{ mode = 'fresh'; admittedAt = '2026-08-27T13:05:00Z' }
        result = [ordered]@{ claim = 'Fixture claim only' }
        coverage = [ordered]@{
            scope = 'Fixture document scope'
            plannedUnits = 1
            observedUnits = 1
            plannedRuns = 1
            observedRuns = 1
            percent = 100
            gaps = @()
        }
        dataQuality = 'document'
        artifacts = @(
            [ordered]@{ path = 'fixture.json'; sha256 = [string]::new('b', 64); bytes = 1 }
        )
        knownLimitations = @('Fixture evidence is not a production claim')
    }
}

function New-ValidT1EvidenceRecord {
    $record = New-ValidT2EvidenceRecord
    $record.recordId = 'evidence-t1-fixture'
    $record.provenance = 'T1'
    $record.evidenceUse = 'context'
    $record.Remove('corroborationRef')
    $record.subject.sourceDocumentRef = 'document-t1-fixture'
    $record.tool.name = 'Fixture primary-source retriever'
    $record.timestamp = '2026-08-27T12:30:00Z'
    $record.admission.admittedAt = '2026-08-27T12:35:00Z'
    return $record
}

function New-ValidT0BatchEvidenceRecord {
    param(
        [string]$TestClass = 'controlled-benchmark',
        [int]$UnitCount = 3,
        [int]$RepetitionsPerUnit = 5,
        [string]$Role = 'candidate',
        [string]$RecordSuffix = 'fixture',
        [string]$EvidenceUse = 'gate-or-verdict',
        [string]$ConditionRef = 'fixture-condition',
        [int]$DeviceStart = 1,
        [string]$AdmissionMode = 'fresh',
        [string]$ObservedAt = '2026-08-27T14:00:00Z',
        [string]$AdmittedAt = '2026-08-27T14:05:00Z',
        [string[]]$BridgeEvidenceRefs = @(),
        [string]$BaselineFingerprint = ''
    )

    $fingerprint = if ([string]::IsNullOrWhiteSpace($BaselineFingerprint)) { [string]::new('d', 64) } else { $BaselineFingerprint }
    $runCount = $UnitCount * $RepetitionsPerUnit
    $units = @(
        for ($offset = 0; $offset -lt $UnitCount; $offset++) {
            $index = $DeviceStart + $offset
            [ordered]@{
                deviceId = "fixture-$Role-device-$index"
                role = $Role
                configurationIdentity = 'configuration-fixture'
                manifestRef = 'manifest-fixture'
                baselineFingerprintSha256 = $fingerprint
            }
        }
    )
    $runs = @(
        foreach ($unit in $units) {
            for ($repetition = 1; $repetition -le $RepetitionsPerUnit; $repetition++) {
                [ordered]@{
                    runId = "run-$RecordSuffix-$($unit.deviceId)-$repetition"
                    deviceId = $unit.deviceId
                }
            }
        }
    )
    $subject = if ($UnitCount -eq 1) {
        [ordered]@{
            kind = 'device'
            role = $Role
            deviceId = $units[0].deviceId
            configurationIdentity = 'configuration-fixture'
            manifestRef = 'manifest-fixture'
        }
    } else {
        [ordered]@{
            kind = 'batch-stratum'
            stratumId = "fixture-stratum-$Role"
            role = $Role
            configurationIdentity = 'configuration-fixture'
            manifestRef = 'manifest-fixture'
            baselineFingerprintSha256 = $fingerprint
            units = $units
        }
    }
    $admission = [ordered]@{ mode = $AdmissionMode; admittedAt = $AdmittedAt }
    if ($AdmissionMode -eq 'compatibility-cache') {
        $admission.reusePolicyRef = 'test-plan-fixture#/evidenceReusePolicy'
        $admission.cachedReleaseRef = "cached-release-$RecordSuffix"
        $admission.dependencySnapshotRef = "cached-dependencies-$RecordSuffix"
        $admission.dependencyMatch = [ordered]@{
            hardware = $true
            firmware = $true
            operatingSystem = $true
            agents = $true
            applications = $true
            peripherals = $true
            conditions = $true
            testAndPack = $true
            supportCurrency = $true
            thresholdPolicy = $true
            staleness = $true
        }
        $admission.artifactHashesVerified = $true
        $admission.completeEvidenceVerified = $true
        $admission.withinMaximumAge = $true
        $admission.bridgeEvidenceRefs = @($BridgeEvidenceRefs)
        $admission.criticalMatrixRef = 'fixture-critical-matrix'
        $admission.functionalRuleRef = 'fixture-functional-rule'
        $admission.repeatabilityRuleRef = 'fixture-repeatability-rule'
        $admission.driftRuleRef = 'fixture-drift-rule'
        $admission.bridgeAccepted = $true
        $admission.bridgeAcceptedAt = '2026-08-27T13:30:00Z'
        $admission.cachePlusBridgeMeetsFloor = $true
    }
    return [ordered]@{
        recordId = "evidence-t0-$TestClass-$Role-$RecordSuffix"
        schemaVersion = '2.0.1'
        recordKind = 'measurement-summary'
        provenance = 'T0'
        evidenceUse = $EvidenceUse
        subject = $subject
        baseline = [ordered]@{
            biosVersion = 'fixture-bios'
            windowsBuild = 'fixture-windows'
            driverVersions = [ordered]@{ chipset = 'fixture-driver' }
            agentVersions = [ordered]@{ management = 'fixture-agent' }
            image = 'corporate'
            baselineFingerprintSha256 = $fingerprint
        }
        tool = [ordered]@{ name = 'Fixture collector'; version = '1.0' }
        testRef = "test-$TestClass"
        conditionRef = $ConditionRef
        testPackVersion = 'fixture-pack-v1'
        timestamp = $ObservedAt
        admission = $admission
        result = [ordered]@{ metric = 'fixture'; value = 1 }
        distribution = [ordered]@{
            unitCount = $UnitCount
            runCount = $runCount
            runs = $runs
            summary = [ordered]@{ kind = 'numeric'; median = 1; spread = [ordered]@{ kind = 'range'; min = 0; max = 2 } }
            runVariationPct = 1
            betweenUnitVariationPct = 1
            missingResults = [ordered]@{ count = 0; reasons = @() }
            excludedOutliers = @()
        }
        coverage = [ordered]@{
            scope = 'fixture batch'
            plannedUnits = $UnitCount
            observedUnits = $UnitCount
            plannedRuns = $runCount
            observedRuns = $runCount
            percent = 100
            gaps = @()
        }
        dataQuality = 'controlled-delta'
        artifacts = @([ordered]@{ path = 'fixture-t0.json'; sha256 = [string]::new('e', 64); bytes = 1 })
        knownLimitations = @()
    }
}

function New-FloorCompleteGateEvidenceRecords {
    param(
        [Parameter(Mandatory = $true)]$Plan,
        [string[]]$ExcludeClasses = @(),
        [string]$RecordPrefix = 'complete'
    )

    $records = New-Object System.Collections.ArrayList
    foreach ($test in $Plan.tests) {
        if ($ExcludeClasses -contains [string]$test.class) { continue }
        $floor = $Plan.samplingFloors[[string]$test.class]
        foreach ($condition in $test.conditions) {
            foreach ($role in $test.appliesTo) {
                [void]$records.Add((New-ValidT0BatchEvidenceRecord `
                    -TestClass $test.class `
                    -UnitCount $floor.minUnits `
                    -RepetitionsPerUnit $floor.minRepetitionsPerUnit `
                    -Role $role `
                    -ConditionRef $condition.conditionId `
                    -RecordSuffix "$RecordPrefix-$($test.class)-$role-$($condition.conditionId)"))
            }
        }
    }
    return @($records)
}

function New-ValidCandidateManifest {
    return [ordered]@{
        manifestId = 'manifest-fixture'
        schemaVersion = '2.0.1'
        status = 'frozen'
        frozenAt = '2026-08-27T12:00:00Z'
        approvedBy = 'Fixture manifest approver'
        tier = 'full'
        hardwareEnvelope = [ordered]@{
            productFamily = 'fixture-family'
            orderableSkus = @('fixture-sku')
            cpu = 'fixture-cpu'
            memory = [ordered]@{ totalGB = 1; configuration = 'fixture-memory' }
            storage = [ordered]@{ minCapacityGB = 1; approvedSsdClasses = @('fixture-ssd') }
            approvedWlanModules = @('fixture-wlan')
            approvedPanels = @('fixture-panel')
            batteryClass = 'fixture-battery'
        }
        platformBaseline = [ordered]@{
            biosVersion = 'fixture-bios'
            windowsBuild = 'fixture-windows'
            driverBaseline = [ordered]@{ chipset = 'fixture-driver' }
            agentBaselineRef = 'fixture-agent-baseline'
        }
        personas = @([ordered]@{ name = 'fixture-persona'; workloadRequirement = 'fixture measured requirement' })
        candidateDevices = @([ordered]@{ deviceId = 'fixture-device' })
        controls = [ordered]@{
            incumbent = [ordered]@{
                model = 'fixture-incumbent'
                evidencePlan = [ordered]@{
                    mode = 'cache-reuse'
                    contemporaneousControlRun = $true
                    reusePolicyRef = 'test-plan-fixture#/evidenceReusePolicy'
                    freshClasses = @(
                        'component-identification', 'controlled-benchmark',
                        'sustained-performance', 'battery-standby', 'dock-reliability',
                        'corporate-floor', 'agent-state'
                    )
                    reusedClasses = @('application-compatibility')
                    cachedReleaseRef = 'fixture-cache'
                    cachedArtifactSha256 = @([string]::new('c', 64))
                    cacheAgeDays = 1
                    dependencySnapshotRef = 'fixture-dependencies'
                    dependencyMatch = [ordered]@{
                        hardware = $true
                        firmware = $true
                        operatingSystem = $true
                        agents = $true
                        applications = $true
                        peripherals = $true
                        conditions = $true
                        testAndPack = $true
                        supportCurrency = $true
                        thresholdPolicy = $true
                        staleness = $true
                    }
                    stalenessCheckedAt = '2026-08-27T12:00:00Z'
                    withinMaximumAge = $true
                    bridge = [ordered]@{
                        candidateUnits = 1
                        repetitionsPerCriticalCombination = 2
                        criticalMatrixRef = 'fixture-critical-matrix'
                        functionalRuleRef = 'fixture-functional-rule'
                        repeatabilityRuleRef = 'fixture-repeatability-rule'
                        driftRuleRef = 'fixture-drift-rule'
                        acceptanceEvidenceRef = 'fixture-bridge-evidence'
                        accepted = $true
                        cachePlusBridgeMeetsFloor = $true
                    }
                }
            }
            'sibling-or-alternative' = [ordered]@{
                model = 'fixture-sibling'
                evidencePlan = [ordered]@{
                    mode = 'fresh'
                    contemporaneousControlRun = $true
                    reusePolicyRef = 'test-plan-fixture#/evidenceReusePolicy'
                    freshClasses = @(
                        'component-identification', 'application-compatibility',
                        'controlled-benchmark', 'sustained-performance', 'battery-standby',
                        'dock-reliability', 'corporate-floor', 'agent-state'
                    )
                    reusedClasses = @()
                    fullFreshFloorRequired = $true
                }
            }
        }
        docksAndPeripherals = @('fixture-dock')
        pilotPopulationPlan = [ordered]@{
            targetCount = 30
            selectionDimensions = @('persona', 'region', 'work-pattern')
            privacyOwner = 'Fixture privacy owner'
            volunteerOnly = $false
        }
        procurementDeadline = '2026-12-31'
        evaluationOwner = 'Fixture evaluation owner'
        qualificationAuthority = 'Fixture qualification authority'
        testPlanRef = 'test-plan-fixture'
        thresholdPolicyRef = 'threshold-policy-fixture'
        programCost = [ordered]@{ engineerDays = 0; labHardwareAmount = 0; currency = 'USD'; elapsedDays = 0 }
        openItems = @()
    }
}

function New-GovernedConstant {
    param($Value, [string]$Unit)
    return [ordered]@{
        value = $Value
        unit = $Unit
        rationale = 'Fixture rationale'
        selectionMethod = 'Fixture selection method'
        selectionEvidenceRefs = @('fixture-evidence')
        appliesTo = @('fixture-scope')
        approvedBy = 'Fixture approver'
    }
}

function New-ValidThresholdPolicy {
    $memory = New-GovernedConstant 0 'GB'
    $memory.revisableWhen = 'New representative evidence is approved'
    $memory.nonComparableComparisonClasses = @('fixture-memory-comparison')
    $storage = New-GovernedConstant 0 'GB'
    $storage.revisableWhen = 'New representative evidence is approved'
    $storage.nonComparableComparisonClasses = @('fixture-storage-comparison')

    return [ordered]@{
        policyId = 'threshold-policy-fixture'
        schemaVersion = '2.0.1'
        version = 'fixture-v1'
        status = 'frozen'
        frozenAt = '2026-08-27T12:00:00Z'
        approvedBy = 'Fixture approver'
        reserves = [ordered]@{ memoryReserveGB = $memory; storageReserveGB = $storage }
        thresholds = [ordered]@{
            idleCpuMedianMaxPct = New-GovernedConstant 0 'percent'
            idleCpuP95MaxPct = New-GovernedConstant 0 'percent'
            idleMemoryMaxGB = New-GovernedConstant 0 'GB'
            sleepDrainMaxPctPer16h = New-GovernedConstant 0 'percent-per-16h'
            dockCyclesRequired = New-GovernedConstant 1 'cycles'
            dockFailuresMax = New-GovernedConstant 0 'failures'
            sustainedPerfDropMaxPct = New-GovernedConstant 0 'percent'
            benchmarkRepeatabilityMaxCvPct = New-GovernedConstant 0 'percent'
            minTelemetryCoveragePct = New-GovernedConstant 0 'percent'
            maxPilotIncidentRate = New-GovernedConstant 0 'fixture-rate-unit'
            appSuccessRateMinPct = New-GovernedConstant 0 'percent'
        }
        revisionPolicy = [ordered]@{
            authority = 'Fixture revision authority'
            allowedWhen = @('New approved evidence')
            requiresNewVersion = $true
            prohibitAfterCandidateResults = $true
            revisionEvidenceRequired = $true
        }
        nonComparableAfterRevision = [ordered]@{
            rule = 'Fixture comparisons using a changed constant remain separate'
            comparisonClasses = @('fixture-comparison')
        }
    }
}

function New-ValidVerdictRecord {
    return [ordered]@{
        verdictId = 'verdict-fixture'
        schemaVersion = '2.0.1'
        recordStage = 'phase5-final'
        status = 'approved-and-immutable'
        immutableAt = '2026-08-27T12:00:00Z'
        manifestRef = 'manifest-fixture'
        qualificationAuthority = 'Fixture qualification authority'
        pilotAuthorizationRecordRef = 'pilot-authorization-fixture'
        provisionalLabVerdict = 'QUALIFY'
        pilotAuthorization = [ordered]@{
            status = 'AUTHORIZED'
            phase2ApprovalRef = 'phase2-approval-fixture'
            phase2ApprovalCurrent = $true
            provisionalVerdictRef = 'provisional-verdict-fixture'
            stopConditionsRef = 'stop-conditions-fixture'
            rollbackPlanRef = 'rollback-plan-fixture'
            operationalReadiness = [ordered]@{
                severityModelRef = 'severity-model-fixture'
                maxIncidentRateThresholdRef = 'incident-threshold-fixture'
                deviceSwapProcessRef = 'swap-process-fixture'
                sparePoolPlanRef = 'spare-pool-fixture'
                serviceDeskBriefingRef = 'briefing-fixture'
                durationDays = 1
                minEvidenceCoverageThresholdRef = 'coverage-threshold-fixture'
            }
            approvedBy = 'Fixture pilot approver'
            approvedAt = '2026-08-27T12:00:00Z'
        }
        pilotCompletion = [ordered]@{
            status = 'COMPLETED'
            pilotEvidenceReleaseRef = 'pilot-evidence-release-fixture'
            coverageEvidenceRef = 'pilot-coverage-fixture'
            stopConditionOutcome = 'NO_UNRESOLVED_STOP_CONDITION'
            startedAt = '2026-08-27T13:00:00Z'
            completedAt = '2026-08-27T14:00:00Z'
            approvedBy = 'Fixture pilot completion approver'
        }
        fleetVerdict = 'QUALIFY'
        fleetDeploymentDisposition = 'APPROVED'
        personaVerdicts = @(
            [ordered]@{
                persona = 'fixture-persona'
                verdict = 'QUALIFY'
                assignmentDisposition = 'APPROVED'
                conflictsWithFleetConditions = $false
                conditionRefs = @()
                capacityWaterfall = [ordered]@{
                    thresholdPolicyRef = 'threshold-policy-fixture'
                    calculationEvidenceRef = 'capacity-evidence-fixture'
                    memory = [ordered]@{
                        physicalMemoryGB = 1
                        corporateFloorGB = 0
                        memoryReserveGB = 0
                        remainingWorkloadHeadroomGB = 1
                        personaRequirementGB = 0
                        outcome = 'PASS'
                    }
                    storage = [ordered]@{
                        formattedCapacityGB = 1
                        corporateImageGB = 0
                        storageReserveGB = 0
                        personaWorkingSetGB = 0
                        remainingWorkloadHeadroomGB = 1
                        outcome = 'PASS'
                    }
                }
            }
        )
        conditions = @()
        exceptions = @()
        arbitration = [ordered]@{ required = $false; triggers = @() }
        deadlineDecision = [ordered]@{
            deadlineStatus = 'before-deadline'
            evidenceState = 'conclusive'
            decision = 'purchase-within-approved-envelope'
        }
        procurementEnvelope = [ordered]@{
            approvedSkus = @('fixture-sku')
            requiredMemory = 'fixture-memory'
            requiredStorage = 'fixture-storage'
            approvedWlanModules = @('fixture-wlan')
            approvedSsdClasses = @('fixture-ssd')
            displayRequirements = 'fixture-display'
            batteryRequirements = 'fixture-battery'
            warrantyRepairTerms = 'fixture-warranty'
            assetRegistrationRequirements = 'fixture-registration'
            substitutionPolicy = [ordered]@{
                silentSubstitutionAllowed = $false
                observableEquivalenceEvidenceRequired = $true
                materialDifferenceAction = 'DELTA_QUALIFICATION_REQUIRED'
                unknownIdentityDisposition = 'HOLD'
            }
            substitutionAssessments = @()
            pcnRequirement = 'fixture-pcn'
            quantityScope = 'fixture-quantity-scope'
            returnRights = 'fixture-return-rights'
        }
        procurementDisposition = 'APPROVED'
        residualRisks = @()
        requalificationTriggers = @('fixture-trigger')
        approvers = @('Fixture approver')
        evidenceReleases = @('fixture-evidence-release')
    }
}

function New-ValidPilotAuthorizationRecord {
    return [ordered]@{
        verdictId = 'pilot-authorization-fixture'
        schemaVersion = '2.0.1'
        recordStage = 'pilot-authorization'
        status = 'approved-and-immutable'
        immutableAt = '2026-08-27T12:00:00Z'
        manifestRef = 'manifest-fixture'
        qualificationAuthority = 'Fixture qualification authority'
        provisionalLabVerdict = 'QUALIFY'
        pilotPopulationPlanRef = 'manifest-fixture#/pilotPopulationPlan'
        privacyOwner = 'Fixture privacy owner'
        pilotAuthorization = [ordered]@{
            status = 'AUTHORIZED'
            phase2ApprovalRef = 'phase2-approval-fixture'
            phase2ApprovalCurrent = $true
            provisionalVerdictRef = 'provisional-verdict-fixture'
            stopConditionsRef = 'stop-conditions-fixture'
            rollbackPlanRef = 'rollback-plan-fixture'
            operationalReadiness = [ordered]@{
                severityModelRef = 'severity-model-fixture'
                maxIncidentRateThresholdRef = 'incident-threshold-fixture'
                deviceSwapProcessRef = 'swap-process-fixture'
                sparePoolPlanRef = 'spare-pool-fixture'
                serviceDeskBriefingRef = 'briefing-fixture'
                durationDays = 1
                minEvidenceCoverageThresholdRef = 'coverage-threshold-fixture'
            }
            approvedBy = 'Fixture pilot approver'
            approvedAt = '2026-08-27T12:00:00Z'
        }
        approvers = @('Fixture pilot approver')
        evidenceReleases = @('phase2-approval-fixture', 'provisional-verdict-fixture')
    }
}

Describe 'Portable qualification contract schemas' {
    It 'reaches a valid fallback after a failed local Node probe under caller EAP Stop' {
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Stop'
            $resolved = Resolve-ContractNodeModule `
                -EnvironmentOverride '' `
                -ModuleRequest '__laptop_qualification_missing_module__' `
                -KnownHostFallback $script:Ajv2020Path
            $resolved | Should Be (Resolve-Path -LiteralPath $script:Ajv2020Path).Path
            $ErrorActionPreference | Should Be 'Stop'
        } finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
    }

    It 'accepts a complete candidate manifest' {
        (Invoke-ContractValidation 'candidate-manifest.schema.json' (New-ValidCandidateManifest)).valid | Should Be $true
    }

    It 'rejects a full-tier manifest below the fixed pilot population floor' {
        $manifest = New-ValidCandidateManifest
        $manifest.pilotPopulationPlan.targetCount = 29
        (Invoke-ContractValidation 'candidate-manifest.schema.json' $manifest).valid | Should Be $false
    }

    It 'rejects cached dynamic-class control evidence' {
        $manifest = New-ValidCandidateManifest
        $manifest.controls.incumbent.evidencePlan.reusedClasses = @('controlled-benchmark')
        (Invoke-ContractValidation 'candidate-manifest.schema.json' $manifest).valid | Should Be $false
    }

    It 'accepts a full-floor control bootstrap without production telemetry' {
        $manifest = New-ValidCandidateManifest
        $bootstrap = $manifest.controls.'sibling-or-alternative'.evidencePlan
        $bootstrap.mode = 'bootstrap'
        $bootstrap.dependencySnapshotRef = 'fixture-bootstrap-dependencies'
        $bootstrap.bootstrapSelectionMethod = 'Preselected representative controls'
        (Invoke-ContractValidation 'candidate-manifest.schema.json' $manifest).valid | Should Be $true
    }

    It 'accepts a complete ten-class frozen full-tier test plan' {
        (Invoke-ContractValidation 'test-plan.schema.json' (New-ValidTestPlan)).valid | Should Be $true
    }

    It 'rejects a per-role Phase 2 application-compatibility floor' {
        $plan = New-ValidTestPlan
        $plan.samplingFloors['application-compatibility'].perRole = $true
        (Invoke-ContractValidation 'test-plan.schema.json' $plan).valid | Should Be $false
    }

    It 'rejects a controlled-benchmark floor below the program minimum' {
        $plan = New-ValidTestPlan
        $plan.samplingFloors['controlled-benchmark'].minUnits = 2
        (Invoke-ContractValidation 'test-plan.schema.json' $plan).valid | Should Be $false
    }

    It 'rejects a Phase 3 test missing the sibling-or-alternative control' {
        $plan = New-ValidTestPlan
        $benchmark = $plan.tests | Where-Object { $_.class -eq 'controlled-benchmark' }
        $benchmark.appliesTo = @('candidate', 'incumbent')
        (Invoke-ContractValidation 'test-plan.schema.json' $plan).valid | Should Be $false
    }

    It 'rejects a Phase 1 component-identification test missing a control role' {
        $plan = New-ValidTestPlan
        $identity = $plan.tests | Where-Object { $_.class -eq 'component-identification' }
        $identity.appliesTo = @('candidate', 'incumbent')
        (Invoke-ContractValidation 'test-plan.schema.json' $plan).valid | Should Be $false
    }

    It 'rejects a delta plan that both tests and omits the same class' {
        $plan = New-ValidTestPlan
        $plan.qualificationTier = 'delta'
        $plan.omittedClasses = @(
            [ordered]@{
                class = 'controlled-benchmark'
                rationale = 'Fixture omission contradiction'
                dependenciesUnaffected = $true
                reviewEvidenceRef = 'fixture-dependency-review'
            }
        )
        (Invoke-ContractValidation 'test-plan.schema.json' $plan).valid | Should Be $false
    }

    It 'accepts a T2 record with a specific T0 or T1 corroboration reference' {
        (Invoke-ContractValidation 'evidence-record.schema.json' (New-ValidT2EvidenceRecord)).valid | Should Be $true
    }

    It 'accepts a multi-unit T0 batch with unit-level identity and baseline provenance' {
        (Invoke-ContractValidation 'evidence-record.schema.json' (New-ValidT0BatchEvidenceRecord)).valid | Should Be $true
    }

    It 'rejects a one-device T0 subject claiming a multi-unit distribution' {
        $evidence = New-ValidT0BatchEvidenceRecord
        $evidence.subject = [ordered]@{
            kind = 'device'
            role = 'candidate'
            deviceId = 'fixture-device-1'
            configurationIdentity = 'configuration-fixture'
            manifestRef = 'manifest-fixture'
        }
        (Invoke-ContractValidation 'evidence-record.schema.json' $evidence).valid | Should Be $false
    }

    It 'rejects T2 evidence without corroboration' {
        $evidence = New-ValidT2EvidenceRecord
        $evidence.Remove('corroborationRef')
        (Invoke-ContractValidation 'evidence-record.schema.json' $evidence).valid | Should Be $false
    }

    It 'rejects hypothesis-only T2 evidence without corroboration' {
        $evidence = New-ValidT2EvidenceRecord
        $evidence.evidenceUse = 'hypothesis-only'
        $evidence.Remove('corroborationRef')
        (Invoke-ContractValidation 'evidence-record.schema.json' $evidence).valid | Should Be $false
    }

    It 'accepts hypothesis-only T2 evidence when it is corroborated' {
        $evidence = New-ValidT2EvidenceRecord
        $evidence.evidenceUse = 'hypothesis-only'
        (Invoke-ContractValidation 'evidence-record.schema.json' $evidence).valid | Should Be $true
    }

    It 'accepts a fully governed threshold and reserve policy fixture' {
        (Invoke-ContractValidation 'threshold-policy.schema.json' (New-ValidThresholdPolicy)).valid | Should Be $true
    }

    It 'accepts an immutable pre-Phase 4 pilot authorization record' {
        (Invoke-ContractValidation 'verdict-record.schema.json' (New-ValidPilotAuthorizationRecord)).valid | Should Be $true
    }

    It 'rejects a pre-Phase 4 authorization without its rollback plan' {
        $authorization = New-ValidPilotAuthorizationRecord
        $authorization.pilotAuthorization.Remove('rollbackPlanRef')
        (Invoke-ContractValidation 'verdict-record.schema.json' $authorization).valid | Should Be $false
    }

    It 'accepts a complete Phase 5 record with authorized pilot gates' {
        (Invoke-ContractValidation 'verdict-record.schema.json' (New-ValidVerdictRecord)).valid | Should Be $true
    }

    It 'rejects incomplete Phase 5 pilot authorization' {
        $verdict = New-ValidVerdictRecord
        $verdict.pilotAuthorization.Remove('rollbackPlanRef')
        (Invoke-ContractValidation 'verdict-record.schema.json' $verdict).valid | Should Be $false
    }

    It 'rejects a final Phase 5 record without pilot completion evidence' {
        $verdict = New-ValidVerdictRecord
        $verdict.Remove('pilotCompletion')
        (Invoke-ContractValidation 'verdict-record.schema.json' $verdict).valid | Should Be $false
    }

    It 'rejects a final Phase 5 record without its pre-pilot authorization reference' {
        $verdict = New-ValidVerdictRecord
        $verdict.Remove('pilotAuthorizationRecordRef')
        (Invoke-ContractValidation 'verdict-record.schema.json' $verdict).valid | Should Be $false
    }

    It 'rejects a normal purchase when the deadline is reached with inconclusive evidence' {
        $verdict = New-ValidVerdictRecord
        $verdict.deadlineDecision.deadlineStatus = 'deadline-reached'
        $verdict.deadlineDecision.evidenceState = 'inconclusive'
        (Invoke-ContractValidation 'verdict-record.schema.json' $verdict).valid | Should Be $false
    }

    It 'accepts the deadline risk-exception path with conditions and arbitration' {
        $verdict = New-ValidVerdictRecord
        $verdict.fleetVerdict = 'INCONCLUSIVE'
        $verdict.fleetDeploymentDisposition = 'APPROVED_WITH_CONDITIONS'
        $verdict.procurementDisposition = 'APPROVED_WITH_CONDITIONS'
        $verdict.deadlineDecision = [ordered]@{
            deadlineStatus = 'deadline-reached'
            evidenceState = 'inconclusive'
            decision = 'risk-accepted-expiring-exception'
            exceptionRef = 'fixture-deadline-exception'
            authorityApprovalRef = 'fixture-deadline-approval'
        }
        $verdict.conditions = @(
            [ordered]@{ conditionId = 'fixture-condition'; description = 'Expiring risk condition'; owner = 'Fixture owner'; expiration = '2026-12-31'; closureEvidence = 'fixture-closure-evidence' }
        )
        $verdict.exceptions = @(
            [ordered]@{ exceptionId = 'fixture-deadline-exception'; owner = 'Fixture owner'; reason = 'Procurement deadline'; compensatingControl = 'Restricted deployment'; scope = 'Fixture scope'; expiration = '2026-12-31'; closureEvidence = 'fixture-closure-evidence'; approvedBy = 'Fixture authority' }
        )
        $verdict.arbitration = [ordered]@{ required = $true; triggers = @('deadline-inconclusive'); authority = 'Fixture authority'; outcome = 'Expiring exception'; date = '2026-08-27'; evidenceRefs = @('fixture-deadline-approval') }
        (Invoke-ContractValidation 'verdict-record.schema.json' $verdict).valid | Should Be $true
    }

    It 'rejects approved procurement while a material substitution awaits delta qualification' {
        $verdict = New-ValidVerdictRecord
        $verdict.procurementEnvelope.substitutionAssessments = @(
            [ordered]@{
                substitutionId = 'fixture-material-substitution'
                identityStatus = 'KNOWN'
                proposedIdentity = 'fixture-substitute-controller'
                qualifiedEnvelopeComparison = 'A known controller differs from the qualified envelope'
                observableEquivalenceEvidenceRefs = @('fixture-equivalence-evidence')
                differences = @('Storage controller revision')
                dependencyMappings = @('storage-controller')
                materialDifference = 'YES'
                disposition = 'DELTA_QUALIFICATION_REQUIRED'
                deltaQualificationRef = 'fixture-pending-delta-qualification'
                arbitrationRequired = $false
            }
        )
        (Invoke-ContractValidation 'verdict-record.schema.json' $verdict).valid | Should Be $false
    }

    It 'accepts a material substitution held for delta qualification with procurement blocked' {
        $verdict = New-ValidVerdictRecord
        $verdict.procurementDisposition = 'BLOCKED'
        $verdict.procurementEnvelope.substitutionAssessments = @(
            [ordered]@{
                substitutionId = 'fixture-material-substitution'
                identityStatus = 'KNOWN'
                proposedIdentity = 'fixture-substitute-controller'
                qualifiedEnvelopeComparison = 'A known controller differs from the qualified envelope'
                observableEquivalenceEvidenceRefs = @('fixture-equivalence-evidence')
                differences = @('Storage controller revision')
                dependencyMappings = @('storage-controller')
                materialDifference = 'YES'
                disposition = 'DELTA_QUALIFICATION_REQUIRED'
                deltaQualificationRef = 'fixture-pending-delta-qualification'
                arbitrationRequired = $false
            }
        )
        (Invoke-ContractValidation 'verdict-record.schema.json' $verdict).valid | Should Be $true
    }

    It 'rejects an approved substitution when component identity is unknown' {
        $verdict = New-ValidVerdictRecord
        $verdict.procurementEnvelope.substitutionAssessments = @(
            [ordered]@{
                substitutionId = 'fixture-substitution'
                identityStatus = 'UNKNOWN'
                qualifiedEnvelopeComparison = 'Identity could not be compared'
                observableEquivalenceEvidenceRefs = @()
                differences = @('Unknown identity')
                dependencyMappings = @('hardware-component')
                materialDifference = 'UNKNOWN'
                disposition = 'APPROVED_EQUIVALENT'
                arbitrationRequired = $false
            }
        )
        (Invoke-ContractValidation 'verdict-record.schema.json' $verdict).valid | Should Be $false
    }

    Context 'mandatory bundle semantic release checks beyond standalone JSON Schema' {
        It 'accepts a referentially consistent bundle with valid chronology and capacity arithmetic' {
            $plan = New-ValidTestPlan
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'referential')
            $records += (New-ValidT1EvidenceRecord)
            $records += (New-ValidT2EvidenceRecord)
            $records += (New-ValidT0BatchEvidenceRecord -EvidenceUse 'context' -RecordSuffix 'referential-context')
            (Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))).valid | Should Be $true
        }

        It 'rejects pilot execution that starts before its authorization' {
            $verdict = New-ValidVerdictRecord
            $verdict.pilotCompletion.startedAt = '2026-08-27T11:00:00Z'
            (Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) $verdict @() @((New-ValidPilotAuthorizationRecord))).valid | Should Be $false
        }

        It 'rejects fabricated persona capacity arithmetic' {
            $verdict = New-ValidVerdictRecord
            $verdict.personaVerdicts[0].capacityWaterfall.memory.remainingWorkloadHeadroomGB = 999
            (Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) $verdict @() @((New-ValidPilotAuthorizationRecord))).valid | Should Be $false
        }

        It 'rejects a dangling T2 corroboration reference' {
            $records = @((New-ValidT2EvidenceRecord))
            (Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))).valid | Should Be $false
        }

        It 'rejects evidence whose testRef does not resolve to a frozen test definition' {
            $evidence = New-ValidT1EvidenceRecord
            $evidence.testRef = 'unknown-test-definition'
            (Invoke-ContractValidation 'evidence-record.schema.json' $evidence).valid | Should Be $true
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @($evidence) @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'testRef must resolve to exactly one frozen test definition'
        }

        It 'rejects a T0 batch whose distribution count exceeds its identified units' {
            $evidence = New-ValidT0BatchEvidenceRecord
            $evidence.distribution.unitCount = 4
            $records = @($evidence)
            (Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))).valid | Should Be $false
        }

        It 'rejects duplicate test identifiers across the frozen plan' {
            $plan = New-ValidTestPlan
            $plan.tests[1].testId = $plan.tests[0].testId
            (Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @() @((New-ValidPilotAuthorizationRecord))).valid | Should Be $false
        }

        It 'rejects a final release with no gate-bearing T0 evidence' {
            $context = New-ValidT0BatchEvidenceRecord -UnitCount 1 -RepetitionsPerUnit 1 -EvidenceUse 'context' -RecordSuffix 'zero-gate-context'
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @($context) @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'gate evidence is missing for required frozen test'
        }

        It 'rejects a frozen test plan that references a different manifest' {
            $plan = New-ValidTestPlan
            $plan.manifestRef = 'foreign-manifest'
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'foreign-plan')
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'test-plan.manifestRef does not resolve'
        }

        It 'rejects a case-only test-plan manifest reference mismatch' {
            $plan = New-ValidTestPlan
            $plan.manifestRef = 'MANIFEST-FIXTURE'
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'case-plan-manifest')
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'test-plan.manifestRef does not resolve'
        }

        It 'rejects fresh T0 evidence bound to a foreign manifest' {
            $plan = New-ValidTestPlan
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'foreign-evidence')
            $record = @($records | Where-Object { $_.testRef -eq 'test-controlled-benchmark' -and $_.subject.role -eq 'candidate' })[0]
            $record.subject.manifestRef = 'foreign-manifest'
            foreach ($unit in $record.subject.units) { $unit.manifestRef = 'foreign-manifest' }
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'fresh T0 evidence subject does not reference the current manifest'
        }

        It 'rejects a case-only evidence testRef mismatch' {
            $plan = New-ValidTestPlan
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'case-test-ref')
            $record = @($records | Where-Object { $_.testRef -ceq 'test-controlled-benchmark' -and $_.subject.role -ceq 'candidate' })[0]
            $record.testRef = 'TEST-CONTROLLED-BENCHMARK'
            (Invoke-ContractValidation 'evidence-record.schema.json' $record).valid | Should Be $true
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'testRef must resolve to exactly one frozen test definition'
        }

        It 'rejects a case-only evidence conditionRef mismatch' {
            $plan = New-ValidTestPlan
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'case-condition-ref')
            $record = @($records | Where-Object { $_.testRef -ceq 'test-controlled-benchmark' -and $_.subject.role -ceq 'candidate' })[0]
            $record.conditionRef = 'FIXTURE-CONDITION'
            (Invoke-ContractValidation 'evidence-record.schema.json' $record).valid | Should Be $true
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'conditionRef must resolve within its frozen test definition'
        }

        It 'rejects a case-only evidence testPackVersion mismatch' {
            $plan = New-ValidTestPlan
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'case-test-pack')
            $record = @($records | Where-Object { $_.testRef -ceq 'test-controlled-benchmark' -and $_.subject.role -ceq 'candidate' })[0]
            $record.testPackVersion = 'FIXTURE-PACK-V1'
            (Invoke-ContractValidation 'evidence-record.schema.json' $record).valid | Should Be $true
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'testPackVersion differs from its frozen test definition'
        }

        It 'rejects a case-only T2 corroboration reference mismatch' {
            $plan = New-ValidTestPlan
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'case-corroboration')
            $t1 = New-ValidT1EvidenceRecord
            $t1.recordId = 'EVIDENCE-T1-FIXTURE'
            $t2 = New-ValidT2EvidenceRecord
            $records += @($t1, $t2)
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'T2 corroboration reference does not resolve'
        }

        It 'treats case-distinct evidence recordIds as distinct ordinal identifiers' {
            $plan = New-ValidTestPlan
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'case-distinct-records')
            $lower = New-ValidT1EvidenceRecord
            $upper = New-ValidT1EvidenceRecord
            $upper.recordId = 'EVIDENCE-T1-FIXTURE'
            $upper.subject.sourceDocumentRef = 'document-case-distinct-fixture'
            $records += @($lower, $upper)
            (Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))).valid | Should Be $true
        }

        It 'rejects case-only verdict manifest and pilot-authorization reference mismatches' {
            $plan = New-ValidTestPlan
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'case-verdict-refs')
            $verdict = New-ValidVerdictRecord
            $verdict.manifestRef = 'MANIFEST-FIXTURE'
            $verdict.pilotAuthorizationRecordRef = 'PILOT-AUTHORIZATION-FIXTURE'
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) $verdict $records @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'verdict.manifestRef does not resolve'
            ($result.errors -join [Environment]::NewLine) | Should Match 'pilotAuthorizationRecordRef must resolve'
        }

        It 'rejects a full-tier pilot waiver with a dangling authorization record' {
            $verdict = New-ValidVerdictRecord
            $verdict.pilotAuthorization.status = 'NOT_REQUIRED'
            $verdict.pilotAuthorization.reason = 'Invalid full-tier waiver fixture'
            $verdict.pilotCompletion.status = 'NOT_REQUIRED'
            $verdict.pilotCompletion.reason = 'Invalid full-tier waiver fixture'
            $verdict.pilotCompletion.authorityApprovalRef = 'fixture-waiver-authority'
            $verdict.pilotAuthorizationRecordRef = 'does-not-resolve'
            (Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) $verdict @() @()).valid | Should Be $false
        }

        It 'rejects a cache bridge below the frozen reuse-policy minima' {
            $plan = New-ValidTestPlan
            $plan.evidenceReusePolicy.compatibilityCache.bridge.minimumCandidateUnits = 5
            $plan.evidenceReusePolicy.compatibilityCache.bridge.minimumRepetitionsPerCriticalCombination = 5
            (Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @() @((New-ValidPilotAuthorizationRecord))).valid | Should Be $false
        }

        It 'rejects qualification-authority drift and a mutated final authorization snapshot' {
            $verdict = New-ValidVerdictRecord
            $verdict.qualificationAuthority = 'Different final authority'
            $verdict.pilotAuthorization.rollbackPlanRef = 'mutated-rollback-plan'
            $authorization = New-ValidPilotAuthorizationRecord
            $authorization.qualificationAuthority = 'Different authorization authority'
            (Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) $verdict @() @($authorization)).valid | Should Be $false
        }

        It 'accepts floor-complete T0 evidence for the entire frozen test plan' {
            $manifest = New-ValidCandidateManifest
            $plan = New-ValidTestPlan
            $policy = New-ValidThresholdPolicy
            $verdict = New-ValidVerdictRecord
            $authorization = New-ValidPilotAuthorizationRecord
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'full')
            (Test-ContractBundleSemantics $manifest $plan $policy $verdict $records @($authorization)).valid | Should Be $true
        }

        It 'accepts one-device one-run engineering evidence when it is context-only' {
            $plan = New-ValidTestPlan
            $evidence = New-ValidT0BatchEvidenceRecord -UnitCount 1 -RepetitionsPerUnit 1 -EvidenceUse 'context' -RecordSuffix 'engineering-context'
            (Invoke-ContractValidation 'evidence-record.schema.json' $evidence).valid | Should Be $true
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'context-positive')
            $records += $evidence
            (Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))).valid | Should Be $true
        }

        It 'aggregates multiple records without losing required Phase 3 role coverage' {
            $plan = New-ValidTestPlan
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -ExcludeClasses @('controlled-benchmark') -RecordPrefix 'aggregate-other')
            $records += @(
                foreach ($role in @('candidate', 'incumbent', 'sibling-or-alternative')) {
                    New-ValidT0BatchEvidenceRecord -UnitCount 2 -RepetitionsPerUnit 5 -Role $role -DeviceStart 1 -RecordSuffix "aggregate-$role-a"
                    New-ValidT0BatchEvidenceRecord -UnitCount 1 -RepetitionsPerUnit 5 -Role $role -DeviceStart 3 -RecordSuffix "aggregate-$role-b"
                }
            )
            (Invoke-ContractValidation 'evidence-record.schema.json' $records[1]).valid | Should Be $true
            (Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))).valid | Should Be $true
        }

        It 'rejects candidate-only Phase 3 gate evidence even when the candidate meets its floor' {
            $evidence = New-ValidT0BatchEvidenceRecord -UnitCount 3 -RepetitionsPerUnit 5 -Role 'candidate' -RecordSuffix 'candidate-only'
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @($evidence) @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'missing required role/condition coverage.*incumbent'
            ($result.errors -join [Environment]::NewLine) | Should Match 'missing required role/condition coverage.*sibling-or-alternative'
        }

        It 'rejects duplicate run identities instead of double-counting them' {
            $candidate = New-ValidT0BatchEvidenceRecord -Role 'candidate' -RecordSuffix 'dedup-candidate'
            $duplicate = New-ValidT0BatchEvidenceRecord -Role 'candidate' -RecordSuffix 'dedup-candidate'
            $duplicate.recordId = 'evidence-t0-controlled-benchmark-candidate-dedup-copy'
            $incumbent = New-ValidT0BatchEvidenceRecord -Role 'incumbent' -RecordSuffix 'dedup-incumbent'
            $sibling = New-ValidT0BatchEvidenceRecord -Role 'sibling-or-alternative' -RecordSuffix 'dedup-sibling'
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @($candidate, $duplicate, $incumbent, $sibling) @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'reuses run identity within an aggregate stratum'
        }

        It 'rejects a runId reused across required comparison roles' {
            $plan = New-ValidTestPlan
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'cross-role-run')
            $candidate = @($records | Where-Object { $_.testRef -eq 'test-controlled-benchmark' -and $_.subject.role -eq 'candidate' })[0]
            $incumbent = @($records | Where-Object { $_.testRef -eq 'test-controlled-benchmark' -and $_.subject.role -eq 'incumbent' })[0]
            $incumbent.distribution.runs[0].runId = $candidate.distribution.runs[0].runId
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'runId is not unique across the evidence release'
        }

        It 'rejects the same device identity assigned to different comparison roles' {
            $candidate = New-ValidT0BatchEvidenceRecord -Role 'candidate' -RecordSuffix 'role-candidate'
            $incumbent = New-ValidT0BatchEvidenceRecord -Role 'incumbent' -RecordSuffix 'role-incumbent'
            for ($index = 0; $index -lt $incumbent.subject.units.Count; $index++) {
                $oldId = $incumbent.subject.units[$index].deviceId
                $newId = $candidate.subject.units[$index].deviceId
                $incumbent.subject.units[$index].deviceId = $newId
                foreach ($run in $incumbent.distribution.runs | Where-Object { $_.deviceId -eq $oldId }) { $run.deviceId = $newId }
            }
            $sibling = New-ValidT0BatchEvidenceRecord -Role 'sibling-or-alternative' -RecordSuffix 'role-sibling'
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @($candidate, $incumbent, $sibling) @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'same device identity is assigned to multiple roles'
        }

        It 'rejects a device whose role changes across different tests' {
            $plan = New-ValidTestPlan
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -RecordPrefix 'cross-test-role-base')
            $candidateContext = New-ValidT0BatchEvidenceRecord -TestClass 'controlled-benchmark' -UnitCount 1 -RepetitionsPerUnit 1 -Role 'candidate' -EvidenceUse 'context' -RecordSuffix 'cross-test-candidate' -DeviceStart 90
            $incumbentContext = New-ValidT0BatchEvidenceRecord -TestClass 'sustained-performance' -UnitCount 1 -RepetitionsPerUnit 1 -Role 'incumbent' -EvidenceUse 'context' -RecordSuffix 'cross-test-incumbent' -DeviceStart 91
            $incumbentContext.subject.deviceId = $candidateContext.subject.deviceId
            $incumbentContext.distribution.runs[0].deviceId = $candidateContext.subject.deviceId
            $records += @($candidateContext, $incumbentContext)
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'device identity changes role, configuration, or manifest across the evidence release'
        }

        It 'enforces the floor independently for every gate-bearing baseline stratum' {
            $candidate = New-ValidT0BatchEvidenceRecord -Role 'candidate' -RecordSuffix 'stratum-candidate'
            $incumbent = New-ValidT0BatchEvidenceRecord -Role 'incumbent' -RecordSuffix 'stratum-incumbent'
            $sibling = New-ValidT0BatchEvidenceRecord -Role 'sibling-or-alternative' -RecordSuffix 'stratum-sibling'
            $alternate = New-ValidT0BatchEvidenceRecord -Role 'candidate' -UnitCount 1 -RepetitionsPerUnit 5 -DeviceStart 10 -RecordSuffix 'alternate-stratum' -BaselineFingerprint ([string]::new('f', 64))
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @($candidate, $incumbent, $sibling, $alternate) @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'aggregate gate unit coverage is below the frozen controlled-benchmark floor.*ffffffff'
        }

        It 'requires every frozen test condition for every applicable role' {
            $plan = New-ValidTestPlan
            $benchmark = $plan.tests | Where-Object { $_.class -eq 'controlled-benchmark' }
            $benchmark.conditions += [ordered]@{ conditionId = 'second-condition'; description = 'Second required condition' }
            $records = @(
                (New-ValidT0BatchEvidenceRecord -Role 'candidate' -RecordSuffix 'condition-candidate'),
                (New-ValidT0BatchEvidenceRecord -Role 'incumbent' -RecordSuffix 'condition-incumbent'),
                (New-ValidT0BatchEvidenceRecord -Role 'sibling-or-alternative' -RecordSuffix 'condition-sibling')
            )
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'missing required role/condition coverage.*second-condition'
        }

        It 'admits pre-freeze compatibility evidence only through the frozen cache and bridge policy' {
            $plan = New-ValidTestPlan
            $bridge = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 2 -RecordSuffix 'compatibility-bridge' -ObservedAt '2026-08-27T13:00:00Z' -AdmittedAt '2026-08-27T13:05:00Z'
            $cache = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 1 -RecordSuffix 'compatibility-cache' -AdmissionMode 'compatibility-cache' -ObservedAt '2026-08-10T12:00:00Z' -AdmittedAt '2026-08-27T14:00:00Z' -BridgeEvidenceRefs @($bridge.recordId)
            (Invoke-ContractValidation 'evidence-record.schema.json' $cache).valid | Should Be $true
            (Invoke-ContractValidation 'evidence-record.schema.json' $bridge).valid | Should Be $true
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -ExcludeClasses @('application-compatibility') -RecordPrefix 'cache-other')
            $records += @($cache, $bridge)
            (Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))).valid | Should Be $true
        }

        It 'rejects bridge acceptance equal to its referenced bridge observation' {
            $plan = New-ValidTestPlan
            $bridge = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 2 -RecordSuffix 'equal-observation-bridge' -ObservedAt '2026-08-27T13:00:00Z' -AdmittedAt '2026-08-27T13:00:00Z'
            $cache = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 1 -RecordSuffix 'equal-observation-cache' -AdmissionMode 'compatibility-cache' -ObservedAt '2026-08-10T12:00:00Z' -AdmittedAt '2026-08-27T14:00:00Z' -BridgeEvidenceRefs @($bridge.recordId)
            $cache.admission.bridgeAcceptedAt = $bridge.timestamp
            (Invoke-ContractValidation 'evidence-record.schema.json' $bridge).valid | Should Be $true
            (Invoke-ContractValidation 'evidence-record.schema.json' $cache).valid | Should Be $true
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -ExcludeClasses @('application-compatibility') -RecordPrefix 'equal-observation-other')
            $records += @($cache, $bridge)
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'bridge acceptance does not strictly follow its bridge observation and admission'
        }

        It 'rejects bridge acceptance equal to its referenced bridge admission' {
            $plan = New-ValidTestPlan
            $bridge = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 2 -RecordSuffix 'equal-admission-bridge' -ObservedAt '2026-08-27T13:00:00Z' -AdmittedAt '2026-08-27T13:05:00Z'
            $cache = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 1 -RecordSuffix 'equal-admission-cache' -AdmissionMode 'compatibility-cache' -ObservedAt '2026-08-10T12:00:00Z' -AdmittedAt '2026-08-27T14:00:00Z' -BridgeEvidenceRefs @($bridge.recordId)
            $cache.admission.bridgeAcceptedAt = $bridge.admission.admittedAt
            (Invoke-ContractValidation 'evidence-record.schema.json' $bridge).valid | Should Be $true
            (Invoke-ContractValidation 'evidence-record.schema.json' $cache).valid | Should Be $true
            $records = @(New-FloorCompleteGateEvidenceRecords -Plan $plan -ExcludeClasses @('application-compatibility') -RecordPrefix 'equal-admission-other')
            $records += @($cache, $bridge)
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) $plan (New-ValidThresholdPolicy) (New-ValidVerdictRecord) $records @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'bridge acceptance does not strictly follow its bridge observation and admission'
        }

        It 'rejects a cache admitted before its referenced fresh bridge exists' {
            $bridge = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 2 -RecordSuffix 'future-bridge' -ObservedAt '2026-08-27T15:00:00Z' -AdmittedAt '2026-08-27T15:05:00Z'
            $cache = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 1 -RecordSuffix 'future-cache' -AdmissionMode 'compatibility-cache' -ObservedAt '2026-08-10T12:00:00Z' -AdmittedAt '2026-08-27T14:00:00Z' -BridgeEvidenceRefs @($bridge.recordId)
            $cache.admission.bridgeAcceptedAt = '2026-08-27T15:10:00Z'
            (Invoke-ContractValidation 'evidence-record.schema.json' $cache).valid | Should Be $true
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @($cache, $bridge) @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'admission does not strictly follow every bridge observation and admission'
        }

        It 'rejects a cache whose test pack differs from its bridge and frozen test' {
            $bridge = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 2 -RecordSuffix 'pack-bridge' -ObservedAt '2026-08-27T13:00:00Z' -AdmittedAt '2026-08-27T13:05:00Z'
            $cache = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 1 -RecordSuffix 'pack-cache' -AdmissionMode 'compatibility-cache' -ObservedAt '2026-08-10T12:00:00Z' -AdmittedAt '2026-08-27T14:00:00Z' -BridgeEvidenceRefs @($bridge.recordId)
            $cache.testPackVersion = 'obsolete-pack-v0'
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @($cache, $bridge) @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'evidence testPackVersion differs from its frozen test definition'
            ($result.errors -join [Environment]::NewLine) | Should Match 'cached evidence and bridge testPackVersion values differ'
        }

        It 'rejects pre-freeze fresh dynamic evidence' {
            $evidence = New-ValidT0BatchEvidenceRecord -UnitCount 1 -RepetitionsPerUnit 1 -EvidenceUse 'context' -RecordSuffix 'prefreeze-dynamic' -ObservedAt '2026-08-26T12:00:00Z' -AdmittedAt '2026-08-27T14:00:00Z'
            (Invoke-ContractValidation 'evidence-record.schema.json' $evidence).valid | Should Be $true
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @($evidence) @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'fresh evidence observation is not strictly after the manifest freeze'
        }

        It 'rejects an incomplete cache admission at the schema boundary' {
            $cache = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -RecordSuffix 'invalid-cache-shape' -AdmissionMode 'compatibility-cache' -ObservedAt '2026-08-10T12:00:00Z' -AdmittedAt '2026-08-27T14:00:00Z' -BridgeEvidenceRefs @('bridge-fixture')
            $cache.admission.Remove('bridgeEvidenceRefs')
            (Invoke-ContractValidation 'evidence-record.schema.json' $cache).valid | Should Be $false
        }

        It 'rejects dynamic-class evidence laundered through compatibility-cache admission' {
            $bridge = New-ValidT0BatchEvidenceRecord -UnitCount 1 -RepetitionsPerUnit 5 -DeviceStart 2 -RecordSuffix 'dynamic-bridge'
            $cache = New-ValidT0BatchEvidenceRecord -UnitCount 2 -RepetitionsPerUnit 5 -DeviceStart 1 -RecordSuffix 'dynamic-cache' -AdmissionMode 'compatibility-cache' -ObservedAt '2026-08-10T12:00:00Z' -AdmittedAt '2026-08-27T14:00:00Z' -BridgeEvidenceRefs @($bridge.recordId)
            (Invoke-ContractValidation 'evidence-record.schema.json' $cache).valid | Should Be $true
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @($cache, $bridge) @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'only application-compatibility evidence may use compatibility-cache admission'
        }

        It 'rejects a compatibility cache older than the frozen maximum age' {
            $bridge = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 2 -RecordSuffix 'stale-bridge'
            $cache = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 1 -RecordSuffix 'stale-cache' -AdmissionMode 'compatibility-cache' -ObservedAt '2026-01-01T12:00:00Z' -AdmittedAt '2026-08-27T14:00:00Z' -BridgeEvidenceRefs @($bridge.recordId)
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @($cache, $bridge) @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'cached evidence exceeds the frozen maximum age'
        }

        It 'rejects a cache whose referenced bridge does not complete the compatibility floor' {
            $bridge = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 1 -RecordSuffix 'same-unit-bridge'
            $cache = New-ValidT0BatchEvidenceRecord -TestClass 'application-compatibility' -UnitCount 1 -RepetitionsPerUnit 2 -DeviceStart 1 -RecordSuffix 'same-unit-cache' -AdmissionMode 'compatibility-cache' -ObservedAt '2026-08-10T12:00:00Z' -AdmittedAt '2026-08-27T14:00:00Z' -BridgeEvidenceRefs @($bridge.recordId)
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @($cache, $bridge) @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'cached evidence plus its referenced bridge is below the full compatibility unit floor'
        }

        It 'rejects one-unit one-run controlled-benchmark evidence below its frozen floor' {
            $evidence = New-ValidT0BatchEvidenceRecord -UnitCount 1 -RepetitionsPerUnit 1 -RecordSuffix 'one-unit-one-run'
            (Invoke-ContractValidation 'evidence-record.schema.json' $evidence).valid | Should Be $true
            $result = Test-ContractBundleSemantics (New-ValidCandidateManifest) (New-ValidTestPlan) (New-ValidThresholdPolicy) (New-ValidVerdictRecord) @($evidence) @((New-ValidPilotAuthorizationRecord))
            $result.valid | Should Be $false
            ($result.errors -join [Environment]::NewLine) | Should Match 'aggregate gate unit coverage is below the frozen controlled-benchmark floor'
        }

        It 'rejects result evidence not strictly after each Phase 0 freeze timestamp' {
            foreach ($freezeName in @('manifest', 'test-plan', 'threshold-policy')) {
                $manifest = New-ValidCandidateManifest
                $plan = New-ValidTestPlan
                $policy = New-ValidThresholdPolicy
                $manifest.frozenAt = '2026-08-27T11:00:00Z'
                $plan.frozenAt = '2026-08-27T11:00:00Z'
                $policy.frozenAt = '2026-08-27T11:00:00Z'
                if ($freezeName -eq 'manifest') { $manifest.frozenAt = '2026-08-27T12:30:00Z' }
                if ($freezeName -eq 'test-plan') { $plan.frozenAt = '2026-08-27T12:30:00Z' }
                if ($freezeName -eq 'threshold-policy') { $policy.frozenAt = '2026-08-27T12:30:00Z' }
                $evidence = New-ValidT1EvidenceRecord
                $evidence.timestamp = '2026-08-27T12:30:00Z'
                (Test-ContractBundleSemantics $manifest $plan $policy (New-ValidVerdictRecord) @($evidence) @((New-ValidPilotAuthorizationRecord))).valid | Should Be $false
            }
        }
    }
}
