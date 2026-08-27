# HP ZBook 8 G2a 16 inch: Observed Configuration Sheet

**Status:** Derived, non-normative summary of a sanitized capture set. This sheet is not an evidence record and does not establish support, compatibility, qualification, persona fit, a procurement envelope, or a verdict.

| Required provenance | Reference |
|---|---|
| Candidate manifest | [manifest ID/version] |
| T0 evidence release | [Phase 1 release ID/version required before decision use] |
| Source artifact hashes | [artifact/hash references] |
| Verdict record | [Phase 5 record ID or NOT ISSUED] |
| Capture date | 2026-08-26 |
| Capture sources | Windows Settings, Task Manager Performance views, and HP System Information |

Device-identifying and active-network values are omitted. Values marked **observed** are point-in-time readings from the captured unit, not supported maxima, steady-state measurements, benchmarks, or fleet distributions.

## Evidence baseline

| Field | Captured value | Evidence record |
|---|---|---|
| System BIOS | Y82 family, 01.01.05, dated 2026-05-04 | [T0 ID] |
| Windows edition / build | Windows 11 Enterprise 25H2, build 26200.8893 | [T0 ID] |
| Driver baseline | GPU 32.0.22042.9001; NPU 32.0.203.329 | [T0 IDs] |
| Corporate image release | [not established in supplied captures] | [T0 ID required] |
| Agent baseline release | [not established in supplied captures] | [T0 ID required] |
| Test-pack version | [not applicable to screen captures / insert for later collection] | [test-plan ref] |

Do not join these observations to evidence from another BIOS, driver, Windows, image, agent, or test-pack baseline without an explicit comparability decision.

## Identity

| Field | Captured value | Evidence record |
|---|---|---|
| Product name | HP ZBook 8 G2a 16 inch Mobile Workstation PC | [T0 ID] |
| Product number / SKU | DZ6Q7UC#ABA | [T0 ID] |
| HP software build string | 26WWLAAZ602#SABA#DABA | [T0 ID] |

## Firmware

| Field | Captured value | Evidence record |
|---|---|---|
| System BIOS | Y82 family, 01.01.05, dated 2026-05-04 | [T0 ID] |
| Keyboard controller | 09.57.00 | [T0 ID] |

## CPU

| Field | Captured value | Evidence record |
|---|---|---|
| Processor | AMD Ryzen AI 7 PRO 450 with Radeon 860M | [T0 ID] |
| Reported topology | 1 socket, 8 cores / 16 logical processors, x64 | [T0 ID] |
| Reported base clock | 2.00 GHz | [T0 ID] |
| Reported cache | L1 640 KB, L2 8.0 MB, L3 16.0 MB | [T0 ID] |
| Virtualization | Enabled | [T0 ID] |
| Point-in-time clock/activity | 2.05 GHz at 34%, 2.24 GHz at 37%, 2.42 GHz at 51% **observed** | [T0 ID] |

The clock/activity samples are capture context only. They do not establish idle behavior, a power limit, or sustained performance.

## Integrated GPU

| Field | Captured value | Evidence record |
|---|---|---|
| Adapter | AMD Radeon(TM) 860M Graphics | [T0 ID] |
| Dedicated allocation | 512 MB; 453 MB in use **observed** | [T0 ID] |
| Task Manager memory display | 32.1 GB total; 31.6 GB shown as shared limit | [T0 ID] |
| Driver | 32.0.22042.9001, dated 2026-01-28 | [T0 ID] |
| DirectX display | 12, feature level 12.2 | [T0 ID] |
| PCI location | Bus 196, device 0, function 0 | [T0 ID] |
| Temperature during capture | 41–42 °C **observed** | [T0 ID] |

The temperature was not collected under a preregistered idle protocol and must not be labeled an idle temperature.

## NPU

| Field | Captured value | Evidence record |
|---|---|---|
| Presence | Enumerated in Task Manager as NPU 0 / NPU Compute Accelerator | [T0 ID] |
| Driver | 32.0.203.329, dated 2025-12-17 | [T0 ID] |
| Task Manager memory display | 31.6 GB shown as shared limit | [T0 ID] |
| PCI location | Bus 197, device 0, function 1 | [T0 ID] |

Presence does not establish application support, security approval, usable model size, or measured throughput.

## Memory

| Field | Captured value | Evidence record |
|---|---|---|
| Installed / usable | 64.0 GB installed; 63.3 GB usable; 740 MB hardware reserved **observed** | [T0 ID] |
| Task Manager configuration display | 2 of 2 slots used; 2 × 32 GB reported **observed, provisional** | [T0 ID] |
| Reported speed | 5600 MT/s **observed** | [T0 ID] |
| Activity during capture | 18.8–19.2 GB in use; commit 21.5/72.8 GB; 7.9 GB cached **observed** | [T0 ID] |

The 2 × 32 GB statement remains provisional until per-DIMM enumeration identifies both modules. The observed 64 GB installation is not evidence of the platform's maximum supported, orderable, upgradeable, or qualified memory.

## Storage

| Field | Captured value | Evidence record |
|---|---|---|
| System volume | NVMe SSD; 477 GB displayed capacity; system disk and page file present | [T0 ID] |
| Used at capture | 106 GB of 477 GB **observed** | [T0 ID] |
| Activity during capture | 1–2% active; 20.3 ms response; approximately 2.4 MB/s background writes **observed** | [T0 ID] |
| SSD model / firmware / reliability | [not established in supplied captures] | [T0 ID required] |

The 106 GB reading is not a frozen corporate-image floor until measured under the Phase 3 settled protocol.

## Network and active connection data

No SSID, BSSID, IP address, IPv6 address, DNS suffix, gateway, active network name, or connection inference is included. The supplied captures did not establish the WLAN module identity. An authorized Phase 1 collection may record adapter hardware and driver identity without disclosing the active network.

## Operating system

| Field | Captured value | Evidence record |
|---|---|---|
| Edition / version | Windows 11 Enterprise 25H2 | [T0 ID] |
| OS build | 26200.8893 | [T0 ID] |
| Experience pack | 1000.26100.334.0 | [T0 ID] |
| Installation date | 2026-08-10 | [T0 ID] |
| Pen / touch | Settings reported no pen or touch input for the captured display | [T0 ID] |

## Point-in-time activity during capture

These readings were collected at approximately 9.5 hours uptime. They are neither an idle baseline nor a benchmark.

| Metric | Captured value | Evidence record |
|---|---|---|
| Processes / threads / handles | 351–366 / approximately 7,500–7,900 / approximately 238,000–246,000 **observed** | [T0 ID] |
| CPU | 34–51% at 2.05–2.42 GHz **observed** | [T0 ID] |
| Memory | Approximately 30% **observed** | [T0 ID] |
| Disk | 1–2% active **observed** | [T0 ID] |
| GPU / NPU | 0% displayed **observed** | [T0 ID] |

## Open evidence items

- Per-DIMM manufacturer, part number, serial-safe identity, and validated configuration.
- SSD model, firmware, reliability counters, and approved class.
- WLAN/Bluetooth module and driver identity.
- Panel and battery identity.
- Supported and orderable memory configurations; no maximum is established here.
- Physical storage-slot inventory and qualified expansion options.
- Corporate image and agent baseline releases.
- BitLocker, VBS, Secure Boot, TPM, problem-device, event, battery-health, and raw vendor-management records.

Each open item needs a T0 or applicable T1 evidence-record reference before it can support a gate or verdict. Unknown critical component identity produces HOLD.

## Privacy omissions

Serial number, asset/device name, operating-system device and product IDs, feature byte, and all active Wi-Fi/network identifiers are omitted. Their absence from this view does not remove the requirement for authorized identity mapping in the protected evidence store.
