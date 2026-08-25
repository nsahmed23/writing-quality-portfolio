# Bibliographic and source-access manifest

Research cutoff: **2026-08-19 23:59 America/Chicago**. Retrieval date: **2026-08-25**. “Full” means the complete relevant text was lawfully inspected; a complete TOC with unavailable chapter prose is “partial.” The CSV access and coverage ledgers are controlling.

| ID | Bibliographic record at cutoff | Inspected | Access verdict |
|---|---|---|---|
| WB5 | Joseph M. Williams and Joseph Bizup, *Style: The Basics of Clarity and Grace*, 5th ed., Pearson; print published 2014, ©2015, ISBN 9780321953308 | Official metadata/TOC; selected lawful teaching adaptation; related-edition page-cited commentary | Partial. All ten lessons accounted; no lesson inspected in full. |
| WBL13 | Williams and Bizup, *Style: Lessons in Clarity and Grace*, 13th ed., Pearson, published 2021, ©2022 | Official metadata/TOC | Partial related work. Corroborates continuing architecture; not the same edition line as *Basics*. |
| LAN5 | Richard A. Lanham, *Revising Prose*, 5th ed., Pearson Longman, published 10 July 2006, ©2007, ISBN 9780321441690 | Official TOC; peer-reviewed chapter review; university adaptation | Partial. Chapters/page spans and eight-step method accounted; book not fully read. |
| GOPEN | George D. Gopen, *The Sense of Structure*, 1st ed., Pearson Longman, 2004/©2005, ISBN 9780205296323 | Official/catalog metadata and detailed TOC/subheadings | Partial. Six chapters accounted; chapter prose unavailable. |
| GS90 | George D. Gopen and Judith A. Swan, “The Science of Scientific Writing,” *American Scientist* 78.6 (1990), 550–558 | Complete permission-reprinted article | Full. |
| TUF | Virginia Tufte, *Artful Sentences: Syntax as Style*, Graphics Press, 2006, ISBN 9780961392185 | Publisher/catalog pages and complete 14-chapter TOC | Partial. Chapter text unavailable. Virginia Tufte was Edward Rolf Tufte’s mother, confirmed by his first-person publisher announcement and USC. |
| MIN96 | Barbara Minto, *The Minto Pyramid Principle: Logic in Writing, Thinking, and Problem Solving*, expanded ed., Minto International, 1996 | Author pages, catalog, 12-chapter/3-appendix TOC | Partial. Latest author-designated expanded text visible on her site; chapter text unavailable. |
| MIN26 | Barbara Minto, *The Pyramid Principle*, 3rd ed., Pearson, published 23 February 2026, ©2026, ISBN 9781292763255 | Publisher metadata and 10-chapter/1-appendix TOC | Partial. Latest publisher-numbered edition; its content-level relation to 1996 is unresolved. |
| DIA | Daniele Procida, *Diátaxis*, living site | All 18 English navigation pages as full HTML | Full current site. News dates Aug. 4/6, 2026 precede cutoff; no official exact-cutoff snapshot, so temporal confidence is high, not absolute. |
| GAR5 | Bryan A. Garner, *Garner’s Modern English Usage*, 5th ed., Oxford UP, 17 Nov. 2022, 1,312 pp., ISBN 9780197599020 | OUP/LawProse metadata, first-party LCI, Oxford Reference front/index, scholarly review | Partial. Complete A–Z corpus/headword list and all LCI assignments unavailable behind subscription. |
| STR18 | William Strunk Jr., *The Elements of Style*, privately printed, 1918 | Complete lawful public-domain text/scan | Full. |
| STR20 | Strunk, *The Elements of Style*, Harcourt, Brace and Howe, 1920 | Complete Project Gutenberg text | Full. |
| SW4 | Strunk and E. B. White, *The Elements of Style*, 4th ed., published 1999, ©2000, Pearson/Allyn and Bacon, ISBN 9780205309023 | Official metadata and complete TOC | Partial. Full prose and Chapter IV headword inventory unavailable. 2009 anniversary reuses fourth-edition text. |
| PULLUM | Geoffrey K. Pullum, “The Land of the Free and *The Elements of Style*,” *English Today* 26.2 (2010), 34–44, DOI 10.1017/S0266078410000076 | Complete author manuscript; publisher abstract/metadata | Full author manuscript; published typeset body not inspected. |
| PLAT | OpenAI, “Build skills” and “Skills in ChatGPT,” living official documentation | Full public HTML plus official local skill-creator schema | Full current requirements. Help page was updated before cutoff; undated build page creates a six-day time-travel caveat. |

## Edition resolutions

- The baseline’s “Pearson, 2014” citation is defensible for the *Basics* paperback publication, but the title also carries ©2015 and later digital metadata; the package stores publication and copyright separately.
- *Basics* 5th and *Lessons* 13th are related products, not interchangeable editions.
- Lanham fifth is the current substantiated edition; it integrates business/professional material absent as dedicated chapters in fourth.
- No later edition of *The Sense of Structure* or *Artful Sentences* was substantiated by cutoff.
- Minto requires a dual record: current Pearson third (2026) versus author-designated expanded text (1996). No unsupported equivalence is asserted.
- Garner fifth (2022) is current; no sixth edition was found.
- Strunk/White fourth remains the last substantiated substantive textual revision; illustrated/anniversary packages do not create a fifth textual edition.

## Platform architecture resolution

Official OpenAI documentation requires a skill directory with `SKILL.md` containing `name` and `description`; optional `agents/openai.yaml` stores interface/policy/dependencies. Activation is explicit (`@` in ChatGPT; `$` or `/skills` in Codex) or implicit through the description. Two or more reusable skills should be distributed as a plugin. Therefore the requested tree is adapted by placing all seven skill directories under `skills/`, adding `.codex-plugin/plugin.json`, and keeping routing/research artifacts at plugin root. No eighth router skill is required or created.

Primary links: [OpenAI Build skills](https://learn.chatgpt.com/docs/build-skills), [Skills in ChatGPT](https://help.openai.com/en/articles/20001066-skills-in-chatgpt), [Diátaxis](https://diataxis.fr/), [Pearson Williams](https://www.pearson.com/en-us/subject-catalog/p/style-the-basics-of-clarity-and-grace/P200000002141/9780134109749), [Pearson Lanham](https://www.pearson.com/en-us/subject-catalog/p/revising-prose/P200000002251/9780321441690), [OUP Garner](https://global.oup.com/academic/product/garners-modern-english-usage-9780197599020), [Pearson Strunk/White](https://www.pearson.com/en-au/subject-catalog/p/elements-of-style-the/P200000002160/9780205309023).
