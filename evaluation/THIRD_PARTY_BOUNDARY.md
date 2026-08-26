# Third-party source and redistribution boundary

The evaluation studied nine user-requested source surfaces at pinned revisions. Their repository clones are intentionally absent from this public branch. The bundle contains our source registers, hashes, synthesized mechanisms, short evidence references, and evaluator outputs.

| Source | Pinned revision | Boundary note |
|---|---|---|
| [aashaexo/soundshuman](https://github.com/aashaexo/soundshuman/tree/a45cfbba9fde843d670e553a0aa98f6a23d7fb28) | `a45cfbba9fde843d670e553a0aa98f6a23d7fb28` | Self-authoritative for its rules; documents Humanizer lineage. |
| [hardikpandya/stop-slop](https://github.com/hardikpandya/stop-slop/tree/8da1f030185bdfe8471220585162991eaeb970e9) | `8da1f030185bdfe8471220585162991eaeb970e9` | Outcomes require independent evaluation. |
| [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop/tree/d30eddb9e04562234f2070b5ee63ca4649d9a05e) | `d30eddb9e04562234f2070b5ee63ca4649d9a05e` | Native diagnostic surface in this pilot. |
| [blader/humanizer](https://github.com/blader/humanizer/tree/e2e92e7b4b8229253ed5c8e81dc65463fdeddda5) | `e2e92e7b4b8229253ed5c8e81dc65463fdeddda5` | Rule source, not independent performance evidence. |
| [ehmo/slopkit](https://github.com/ehmo/slopkit/tree/b33718bb9283c11b09567dc714f92d90ffb7bd16) | `b33718bb9283c11b09567dc714f92d90ffb7bd16` | Contributed two distinct authored surfaces. |
| [jalaalrd/anti-ai-slop-writing](https://github.com/jalaalrd/anti-ai-slop-writing/tree/63255f9bbb75a265dc5786a04535cd033f487756) | `63255f9bbb75a265dc5786a04535cd033f487756` | No top-level license was found in the pinned snapshot, so expressive source wording was not copied. |
| [conorbronsdon/avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing/tree/40328bd292bc682d46010a6f9ac2cdbf4fb4ceca) | `40328bd292bc682d46010a6f9ac2cdbf4fb4ceca` | Native diagnostic surface; documents upstream lineage. |
| [Kami anti-patterns](https://github.com/tw93/Kami/blob/68c1dfad6e757047357efdcf13269ec6e820f899/references/anti-patterns.md) | `68c1dfad6e757047357efdcf13269ec6e820f899` | Reference-only source adapted through an F2 diagnostic projection. |
| [Kami writing](https://github.com/tw93/Kami/blob/68c1dfad6e757047357efdcf13269ec6e820f899/references/writing.md) | `68c1dfad6e757047357efdcf13269ec6e820f899` | Reference-only source adapted through an F2 diagnostic projection. |

Seven repository snapshots had top-level MIT licenses in the source review. The pinned `anti-ai-slop-writing` snapshot had no top-level license. Repository repetition is not independent confirmation: `soundshuman` and `avoid-ai-writing` disclose lineage connected to `humanizer`.

No third-party code was executed during the investigation or pilot. A reviewer should flag any file that appears to reproduce a source repository rather than record our analysis or generated test evidence.

Some pilot manifests preserve original local source paths and hashes. Those paths are provenance records, not portable dependencies. Reviewers may use the commit-pinned URLs in `source-review/research_run/source_register.csv` and `pilot/research_run/source_register.csv` to inspect source material independently and compare recorded hashes. Fetching those sources elsewhere does not satisfy the frozen jobs' exact original-path requirements and does not make the evaluator's verified evidence replay portable. External source execution is neither required nor authorized by this bundle.
