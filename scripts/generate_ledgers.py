#!/usr/bin/env python3
"""Generate normalized portfolio ledgers from auditable, compact source data."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETRIEVED = "2026-08-25"
CUTOFF = "2026-08-19 23:59 America/Chicago"

sources = {
    "WB5": {"author": "Joseph M. Williams; Joseph Bizup", "work": "Style: The Basics of Clarity and Grace", "edition": "5th", "year": "2014/©2015", "publisher": "Pearson", "url": "https://www.pearson.com/en-us/subject-catalog/p/style-the-basics-of-clarity-and-grace/P200000002141/9780134109749"},
    "WBL13": {"author": "Joseph M. Williams; Joseph Bizup", "work": "Style: Lessons in Clarity and Grace", "edition": "13th", "year": "2021/©2022", "publisher": "Pearson", "url": "https://www.pearson.com/en-us/subject-catalog/p/style-lessons-in-clarity-and-grace/P200000002140/9780137536603"},
    "LAN5": {"author": "Richard A. Lanham", "work": "Revising Prose", "edition": "5th", "year": "2006/©2007", "publisher": "Pearson Longman", "url": "https://www.pearson.com/en-us/subject-catalog/p/revising-prose/P200000002251/9780321441690"},
    "GOPEN": {"author": "George D. Gopen", "work": "The Sense of Structure", "edition": "1st", "year": "2004/©2005", "publisher": "Pearson Longman", "url": "https://www.pearson.com/en-au/subject-catalog/p/sense-of-structure-the-writing-from-the-reader-s-perspective/P200000007559"},
    "GS90": {"author": "George D. Gopen; Judith A. Swan", "work": "The Science of Scientific Writing", "edition": "American Scientist 78.6", "year": "1990", "publisher": "Sigma Xi", "url": "https://scholars.duke.edu/display/pub881487"},
    "TUF": {"author": "Virginia Tufte", "work": "Artful Sentences: Syntax as Style", "edition": "1st/only substantiated", "year": "2006", "publisher": "Graphics Press", "url": "https://archive.org/details/artfulsentencess0000tuft"},
    "MIN96": {"author": "Barbara Minto", "work": "The Minto Pyramid Principle: Logic in Writing, Thinking, and Problem Solving", "edition": "new and expanded", "year": "1996", "publisher": "Minto International", "url": "https://www.barbaraminto.com/textbook"},
    "MIN26": {"author": "Barbara Minto", "work": "The Pyramid Principle", "edition": "3rd", "year": "2026", "publisher": "Pearson", "url": "https://www.pearson.com/en-gb/subject-catalog/p/the-pyramid-principle/P200000015259/9781292763255"},
    "DIA": {"author": "Daniele Procida", "work": "Diátaxis", "edition": "living website", "year": "current at cutoff", "publisher": "diataxis.fr", "url": "https://diataxis.fr/"},
    "GAR5": {"author": "Bryan A. Garner", "work": "Garner's Modern English Usage", "edition": "5th", "year": "2022", "publisher": "Oxford University Press", "url": "https://global.oup.com/academic/product/garners-modern-english-usage-9780197599020"},
    "STR18": {"author": "William Strunk Jr.", "work": "The Elements of Style", "edition": "privately printed original", "year": "1918", "publisher": "W. F. Humphrey", "url": "https://www.gutenberg.org/files/37134/37134-h/37134-h.htm"},
    "STR20": {"author": "William Strunk Jr.", "work": "The Elements of Style", "edition": "first trade", "year": "1920", "publisher": "Harcourt, Brace and Howe", "url": "https://www.gutenberg.org/files/37134/37134-h/37134-h.htm"},
    "SW4": {"author": "William Strunk Jr.; E. B. White", "work": "The Elements of Style", "edition": "4th", "year": "1999/©2000", "publisher": "Pearson/Allyn and Bacon", "url": "https://www.pearson.com/en-au/subject-catalog/p/elements-of-style-the/P200000002160/9780205309023"},
    "PULLUM": {"author": "Geoffrey K. Pullum", "work": "The Land of the Free and The Elements of Style", "edition": "English Today 26.2", "year": "2010", "publisher": "Cambridge University Press", "url": "https://pullum.ppls.ed.ac.uk/LandOfTheFree.html"},
    "PLAT": {"author": "OpenAI", "work": "Build skills; Skills in ChatGPT", "edition": "living official documentation", "year": "2026", "publisher": "OpenAI", "url": "https://learn.chatgpt.com/docs/build-skills"},
}

access_rows = [
    ["WB5", "Style: The Basics of Clarity and Grace", "5th", "2014/©2015", "Pearson", "official catalog/TOC; lawful selected teaching adaptation; page-cited related-edition commentary", "partial", "Preface and all 10 lesson titles; selected concepts", "all lesson prose, internal sections, exercises, examples, qualifications, fifth-edition pages", RETRIEVED, "latest Basics edition found by cutoff", "high metadata; medium operational detail"],
    ["WBL13", "Style: Lessons in Clarity and Grace", "13th", "2021/©2022", "Pearson", "official catalog/TOC", "partial-related", "all parts/chapters and edition-update description", "full chapters and pages", RETRIEVED, "current related flagship, not replacement edition of Basics", "high"],
    ["LAN5", "Revising Prose", "5th", "2006/©2007", "Pearson Longman", "official catalog/TOC; peer-reviewed chapter review; university adaptation", "partial", "all chapters/page spans; eight-step method; lard formula", "full chapter prose, examples, exercises, complete terms appendix", RETRIEVED, "latest substantiated edition", "high metadata; medium-high method"],
    ["GOPEN", "The Sense of Structure", "1st", "2004/©2005", "Pearson Longman", "official metadata; publisher-supplied TOC/subheadings; library catalogs", "partial", "all six chapters and visible subheadings", "full chapter prose, qualifications, examples, pages", RETRIEVED, "no later edition; Aug. 2026 announced book was not published by cutoff", "high metadata; low-detail extraction"],
    ["GS90", "The Science of Scientific Writing", "American Scientist 78.6", "1990", "Sigma Xi", "complete permission-reprinted PDF", "full", "pp. 550–558 entire article", "none", RETRIEVED, "stable article", "high"],
    ["TUF", "Artful Sentences: Syntax as Style", "1st/only substantiated", "2006", "Graphics Press", "publisher/catalog metadata and complete top-level TOC", "partial", "14 chapter titles; bibliography/index metadata", "all chapter text, exact subcategories, examples, qualifications, page-level forms", RETRIEVED, "no revised edition found", "high metadata; low-detail extraction"],
    ["MIN96", "The Minto Pyramid Principle", "new and expanded", "1996", "Minto International", "author site; catalog; complete TOC", "partial", "12 chapters, four parts, three appendices; author concept/course pages", "chapter text and pages", RETRIEVED, "author-designated expanded/complete line", "high metadata; medium method"],
    ["MIN26", "The Pyramid Principle", "3rd", "2026", "Pearson", "official catalog/TOC", "partial", "10 chapters, two parts, one appendix", "full text; content-level relation to 1996 edition", RETRIEVED, "latest publisher-numbered edition", "high metadata; relation unresolved"],
    ["DIA", "Diátaxis", "living website", "current at cutoff", "diataxis.fr", "full public HTML for 18 English navigation pages", "full", "all 18 pages", "official time-stamped snapshot at exact cutoff; express mixed-document policy", RETRIEVED, "news dated Aug. 4 and Aug. 6, 2026 before cutoff", "high, not absolute temporal"],
    ["GAR5", "Garner's Modern English Usage", "5th", "2022", "Oxford University Press", "OUP/LawProse metadata; first-party LCI; Oxford Reference front/index only; scholarly review", "partial", "front-matter categories; LCI; selected verified examples", "complete A–Z corpus, headword inventory, all classifications/pages/LCI assignments", RETRIEVED, "latest edition by cutoff", "high meta-method; unsupported exhaustiveness"],
    ["STR18", "The Elements of Style", "1918 original", "1918", "private", "lawful public-domain scan/text", "full", "entire 43-page original", "none", RETRIEVED, "historical", "high"],
    ["STR20", "The Elements of Style", "1920 trade", "1920", "Harcourt, Brace and Howe", "Project Gutenberg full text", "full", "entire trade text", "none", RETRIEVED, "historical", "high"],
    ["SW4", "The Elements of Style", "4th", "1999/©2000", "Pearson", "official metadata and full TOC", "partial", "all rule/reminder headings; edition-change overview", "full prose, Chapter IV headword inventory and qualifications", RETRIEVED, "latest substantiated substantive revision; 2009 reprints same text", "high metadata; incomplete rules"],
    ["PULLUM", "The Land of the Free and The Elements of Style", "English Today 26.2", "2010", "Cambridge UP", "complete author manuscript HTML; publisher abstract/metadata", "full-author-manuscript", "all manuscript sections and references; published abstract", "publisher typeset body", RETRIEVED, "stable article", "high"],
    ["PLAT", "OpenAI Skill format and packaging", "living docs", "2026", "OpenAI", "full official HTML; local official skill-creator schema", "full-current", "SKILL.md schema, activation, metadata, locations, plugin distribution, upload notes", "dated revision snapshot at exact Aug. 19 cutoff", RETRIEVED, "Help Center updated before cutoff; Build page undated; no contrary post-cutoff change found", "high current; temporal caveat"],
]

access_fields = ["source_id", "source", "edition", "publication_year", "publisher", "format_inspected", "access", "pages_or_sections_available", "pages_or_sections_unavailable", "retrieval_date", "cutoff_status", "confidence_matches_edition"]

coverage = []
def cov(source, order, section, location, access, disposition, owner, notes=""):
    coverage.append({"source_id": source, "order": order, "chapter_or_section": section, "page_or_location": location, "access": access, "operational_disposition": disposition, "skill_owner": owner, "notes": notes})

for i, sec in enumerate(["Preface", "Lesson 1 Understanding Style", "Lesson 2 Actions", "Lesson 3 Characters", "Lesson 4 Cohesion and Coherence", "Lesson 5 Emphasis", "Lesson 6 Global Coherence", "Lesson 7 Concision", "Lesson 8 Shape", "Lesson 9 Elegance", "Lesson 10 The Ethics of Style", "Index"], 1):
    owner = {2:"shared-reference",3:"sentence-clarity",4:"sentence-clarity",5:"cohesion-emphasis",6:"cohesion-emphasis",7:"memo-structure/shared-reference",8:"concision",9:"sentence-clarity/sentence-variety",10:"sentence-variety",11:"shared ethics"}.get(i, "reference-only")
    cov("WB5", i, sec, "official TOC", "partial", "Chapter accounted; accessible operational principles registered where supported", owner, "Full lesson unavailable; no fifth-edition page claim")

wbl13_sections = [
    "Preface", "In Memoriam", "Introduction", "Part One: Style as Choice", "Lesson One: Correctness and Style",
    "Part Two: Clarity", "Lesson Two: Actions", "Lesson Three: Characters", "Lesson Four: Cohesion and Coherence", "Lesson Five: Emphasis",
    "Part Three: Clarity of Form", "Lesson Six: Framing Documents", "Lesson Seven: Framing Sections",
    "Part Four: Grace", "Lesson Eight: Concision", "Lesson Nine: Shape", "Lesson Ten: Elegance",
    "Part Five: Ethics", "Lesson Eleven: The Ethics of Clarity", "Lesson Twelve: Beyond Clarity",
    "Appendix I: Punctuation", "Appendix II: Using Sources", "Glossary", "Suggested Answers", "Acknowledgments", "Index",
]
for i, sec in enumerate(wbl13_sections, 1):
    cov("WBL13", i, sec, "official Pearson TOC", "partial-related", "Related-edition location accounted; used only to distinguish the current Lessons line and corroborate architecture", "shared-reference", "Not substituted for Basics fifth; full chapter unavailable")

for i, sec in enumerate(["Preface", "1 Action", "2 Attention", "3 Voice", "4 Skotison! (Intentional Obscurity)", "5 Business Prose", "6 Professional Prose", "7 Electronic Prose", "8 Why Bother?", "Appendix of Terms", "Exercises", "Index"], 1):
    owner = "concision" if 1 < i < 10 else "reference-only"
    cov("LAN5", i, sec, "review page spans/official TOC", "partial", "Chapter-level method/disposition registered", owner, "Full chapter unavailable")

gopen_book = [
    "1 The Complexity of the English Sentence", "1.1 Tools, Not Rules", "1.2 Anatomy of a Sentence’s Meaning from the Reader’s Perspective",
    "2 A Structural Anatomy of the English Sentence", "2.1 Fallacy of Good and Bad Sentences", "2.2 Reader Expectations at Sentence Level",
    "3 Weights and Balances; Motions and Connections", "3.1 Artificial Emphasis and When to Use It", "3.2 Fred and His Dog: Competition for Emphasis", "3.3 Moments of Truth", "3.4 Backwards Link of Topic Position", "3.5 Functions of Stress Position", "3.6 Flow of Thought from Sentence to Sentence",
    "4 Whose Paragraph Is It, Anyway?", "4.1 Procrustean Problems", "4.2 Issue", "4.3 Point", "4.4 Pointless Paragraphs", "4.5 Connections Between Paragraphs", "4.6 Summarizing Paragraph Structures", "4.7 Note on Whole Documents",
    "5 Write the Way You Speak and Other Bad Advice", "5.1 Bad Advice", "5.2 Toll Booth Syndrome",
    "6 Mark My Words: Punctuation", "6.1 Punctuation as power", "6.2 Semicolon/history", "6.3 Colon", "6.4 Dashes-parentheses-commas-brackets", "6.5 Hyphen", "6.6 Question mark", "6.7 Exclamation/artificial emphasis", "6.8 Quotation marks", "6.9 Apostrophe", "6.10 Ellipsis", "6.11 Period", "6.12 Comma"]
for i, sec in enumerate(gopen_book, 1):
    cov("GOPEN", i, sec, "publisher-supplied TOC", "partial", "Mapped to cohesion/emphasis or usage reference where supported by full companion article", "cohesion-emphasis" if not sec.startswith("6") else "usage-adjudicator/reference", "Full book text unavailable")

gs_article = ["Structural locations and reader roles", "Subject–verb proximity", "Stress position", "One unit/one principal stress", "Topic position", "Given/new placement", "No mechanical old/new rule", "Passive for topic continuity", "Context before details", "Actions in verbs", "Clause hierarchy", "Logical gaps", "Topic strings", "Paragraph progression", "Syntax before typography", "Seven closing principles", "Principles-not-rules limitations"]
for i, sec in enumerate(gs_article, 1):
    cov("GS90", i, sec, "pp. 550–558", "full", "Operational heuristic extracted and evidence status qualified", "cohesion-emphasis")

tufte_chapters = ["Short Sentences", "Noun Phrases", "Verb Phrases", "Adjectives and Adverbs", "Prepositions", "Conjunctions and Coordination", "Dependent Clauses", "Sentence Openers and Inversion", "Free Modifiers: Branching Sentences", "The Appositive", "Interrogative, Imperative, Exclamatory", "Parallelism", "Cohesion", "Syntactic Symbolism", "Bibliography", "Index"]
for i, sec in enumerate(tufte_chapters, 1):
    cov("TUF", i, sec, "catalog TOC" if i <= 14 else "pp. 275–299/index", "partial", "Chapter accounted; purpose-driven catalog marks derived detail", "sentence-variety" if i <= 14 else "reference-only", "Full chapter unavailable")

min96 = ["Part I Logic in Writing", "1 Why a Pyramid Structure?", "2 Substructures Within the Pyramid", "3 How to Build a Pyramid Structure", "4 Fine Points of Introductions", "5 Deduction and Induction", "Part II Logic in Thinking", "6 Imposing Logical Order", "7 Summarizing Grouped Ideas", "Part III Logic in Problem Solving", "8 Defining the Problem", "9 Structuring Analysis", "Part IV Logic in Presentation", "10 Reflecting the Pyramid on the Page", "11 Reflecting the Pyramid on the Screen", "12 Reflecting the Pyramid in Prose", "Appendix A Structureless Situations", "Appendix B Introductory Structures", "Appendix C Key Points"]
for i, sec in enumerate(min96, 1):
    owner = "memo-structure" if not any(x in sec for x in ["Part IV", "on the Page", "on the Screen"]) else "reference-only"
    cov("MIN96", i, sec, "catalog TOC", "partial", "Chapter accounted; accessible method mapped where supported", owner, "Full chapter unavailable")

min26 = ["Part I Logic in Writing", "1 Why the pyramid structure", "2 Substructures", "3 Build", "4 Fine points of introductions", "5 Deduction and induction", "6 Highlight structure", "Part II Logic in Thinking", "7 Question order/grouping", "8 Question problem-solving process", "9 Question summary statement", "10 Putting into readable words", "Appendix Problem Solving in Structureless Situations"]
for i, sec in enumerate(min26, 1):
    cov("MIN26", i, sec, "official TOC", "partial", "Current-edition section accounted; content relation to 1996 unresolved", "memo-structure", "Full text unavailable")

dia_pages = [
    ("Home", "https://diataxis.fr/"), ("Start here", "https://diataxis.fr/start-here/"), ("Applying Diátaxis", "https://diataxis.fr/application/"), ("Tutorials", "https://diataxis.fr/tutorials/"), ("How-to guides", "https://diataxis.fr/how-to-guides/"), ("Reference", "https://diataxis.fr/reference/"), ("Explanation", "https://diataxis.fr/explanation/"), ("The compass", "https://diataxis.fr/compass/"), ("Workflow", "https://diataxis.fr/how-to-use-diataxis/"), ("Understanding Diátaxis", "https://diataxis.fr/theory/"), ("Foundations", "https://diataxis.fr/foundations/"), ("The map", "https://diataxis.fr/map/"), ("Quality", "https://diataxis.fr/quality/"), ("Tutorials and how-to guides", "https://diataxis.fr/tutorials-how-to/"), ("Reference and explanation", "https://diataxis.fr/reference-explanation/"), ("Colophon", "https://diataxis.fr/colophon/"), ("Help translate", "https://diataxis.fr/translation/"), ("News & Updates", "https://diataxis.fr/news/")]
for i, (sec, url) in enumerate(dia_pages, 1):
    cov("DIA", i, sec, url, "full", "Complete page extracted; principle/type/architecture/change disposition recorded", "doc-typing")

gar_front = ["Preface and edition method", "List of Essay Entries", "Abbreviations", "Pronunciation Key", "Key to Language-Change Index", "Glossary of grammatical/rhetorical terms", "Timeline of usage books", "Select bibliography"]
for i, sec in enumerate(gar_front, 1):
    cov("GAR5", i, sec, "Oxford Reference/front matter", "partial", "Meta-method/taxonomy disposition recorded", "usage-adjudicator", "Some items subscription-protected")
for j, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", len(gar_front)+1):
    cov("GAR5", j, f"A–Z entries: {letter}", "Oxford Reference browse", "unavailable-full", "Letter category explicitly accounted; no exhaustive headword extraction claimed", "usage-adjudicator", "Subscription barrier; issue index is schema plus verified seeds only")

str_rules = ["Introductory", "1 Possessive singular", "2 Serial comma", "3 Parenthetic commas", "4 Comma before coordinate clause", "5 No comma splice", "6 Do not break sentences", "7 Opening participial phrase attachment", "8 Paragraph unit", "9 Topic sentence/end conformity", "10 Active voice", "11 Positive form", "12 Definite/specific/concrete", "13 Omit needless words", "14 Avoid succession of loose sentences", "15 Parallel coordinate ideas", "16 Keep related words together", "17 One tense in summaries", "18 Emphatic words at end", "Matters of Form", "Words and Expressions Commonly Misused", "Words Commonly Misspelled", "Exercises"]
for i, sec in enumerate(str_rules, 1):
    cov("STR18", i, sec, "full public-domain text", "full", "Rule classified in exclusion dossier", "negative-control")

str20_sections = [
    "Introductory", "1 Possessive singular", "2 Serial comma", "3 Parenthetic commas", "4 Comma before coordinate clause", "5 No comma splice", "6 Do not break sentences", "7 Opening participial phrase attachment",
    "8 Paragraph unit", "9 Topic sentence/end conformity", "10 Active voice", "11 Positive form", "12 Definite/specific/concrete", "13 Omit needless words", "14 Avoid succession of loose sentences", "15 Parallel coordinate ideas", "16 Keep related words together", "17 One tense in summaries", "18 Emphatic words at end",
    "Matters of Form", "Words and Expressions Commonly Misused", "Words Commonly Misspelled", "Exercises",
]
for i, sec in enumerate(str20_sections, 1):
    cov("STR20", i, sec, "full Project Gutenberg trade text", "full", "Rule/section classified in exclusion dossier; unchanged operational content maps to the corresponding SW-NEG principle", "negative-control", "Trade-edition renumbering and exercise addition are recorded; duplicated rules are not duplicated as principles")

sw_sections = ["Introduction"] + [f"Usage rule {i}" for i in range(1,12)] + [f"Composition rule {i}" for i in range(12,23)] + ["A Few Matters of Form", "Words and Expressions Commonly Misused"] + [f"Approach to Style reminder {i}" for i in range(1,22)] + ["Afterword", "Glossary"]
for i, sec in enumerate(sw_sections, 1):
    cov("SW4", i, sec, "official TOC", "partial", "Heading classified in exclusion dossier", "negative-control", "Full prose and Chapter IV inventory unavailable")

pullum_sections = ["Introduction/edition history", "Inaccuracy", "Verb agreement/none", "Pronoun agreement/singular they", "Split infinitives", "Gerund-participial subjects", "Restrictive which and however", "Passive-voice analysis", "Internal rule contradictions", "Keep-related-words qualification", "Conclusion", "References"]
for i, sec in enumerate(pullum_sections, 1):
    cov("PULLUM", i, sec, "author manuscript HTML", "full-author-manuscript", "Critical claim classified and qualified", "negative-control")

plat_sections = ["Skill directory structure", "Required SKILL.md name/description", "Progressive disclosure", "Explicit activation", "Implicit description matching", "Optional agents/openai.yaml", "Local discovery scopes", "Plugin distribution", "API upload limits", "Best practices/testing", "Help Center creation/install/admin behavior"]
for i, sec in enumerate(plat_sections, 1):
    cov("PLAT", i, sec, "official docs", "full-current", "Packaging decision encoded", "portfolio-infrastructure", "Six-day post-cutoff retrieval caveat")

principles = []
def add(source_id, principle_id, section, author_term, canonical_term, writing_level, fault_class, reader_problem, diagnostic_signal, diagnostic_question, revision_operation, skill_owner, *, procedure="Diagnose in context; apply the smallest supported change; run the semantic-preservation audit.", conditions="Use only when the observable signal causes the stated reader problem.", exceptions="Marked form may be functional; consult the owning skill's exceptions.", risks="Mechanical application can change meaning, hierarchy, register, evidence, or voice.", counterexamples="A clean instance of the marked form should remain unchanged.", evidence_type="rhetorical heuristic", empirical_status="normative/case-supported; not universal empirical law", secondary_skill="", reference_only=False, exclusion_reason="", examples="", tests="", confidence="medium", location=""):
    s = sources[source_id]
    principles.append({
        "principle_id": principle_id, "source_id": source_id, "author": s["author"], "work": s["work"], "edition": s["edition"],
        "chapter_or_section": section, "page_or_location": location or s["url"], "author_term": author_term, "canonical_term": canonical_term,
        "writing_level": writing_level, "fault_class": fault_class, "reader_problem": reader_problem, "diagnostic_signal": diagnostic_signal,
        "diagnostic_question": diagnostic_question, "revision_operation": revision_operation, "procedure": procedure, "conditions": conditions,
        "exceptions": exceptions, "risks": risks, "counterexamples": counterexamples, "evidence_type": evidence_type,
        "empirical_status": empirical_status, "skill_owner": skill_owner, "secondary_skill": secondary_skill,
        "reference_only": reference_only, "exclusion_reason": exclusion_reason, "example_ids": examples, "test_ids": tests, "confidence": confidence,
    })

# Williams/Bizup: every accessible operational chapter disposition.
wb_cla = [
    ("WB-CLA-01", "Actions/Characters", "characters and actions", "actor–action alignment", "Sentence", "misaligned story grammar", "reader cannot identify central actor/action", "subject/verb do not express central actor/action", "Who or what is doing what?", "align supported actor with subject and action with verb"),
    ("WB-CLA-02", "Actions", "nominalization", "buried action", "Clause", "buried action", "action is obscured", "action noun sits beside a light verb", "Would a finite verb expose the main action?", "promote action noun to verb when useful"),
    ("WB-CLA-03", "Characters", "character", "useful grammatical subject", "Clause", "misleading subject", "agency/topic is hard to recover", "shell or abstract subject displaces relevant actor", "Does agency matter here?", "use known relevant actor as subject"),
    ("WB-CLA-04", "Shape", "start fast", "manageable clause opening", "Sentence", "slow windup", "main clause arrives too late", "long opener delays kernel", "Does the opener provide needed context?", "move, compress, or split opener"),
    ("WB-CLA-05", "Characters", "passive", "functional voice choice", "Clause", "agent suppression", "accountability or action is hidden", "passive suppresses relevant known agent", "Does suppression harm comprehension/accountability?", "recover agent or retain passive by function"),
    ("WB-CLA-06", "Shape", "subject-verb split", "dependency proximity", "Clause", "obstructive dependency", "reader loses subject–verb relation", "heavy movable unit interrupts dependency", "Is the interruption mis-ranked or burdensome?", "move, shorten, or promote interruption"),
    ("WB-CLA-07", "Understanding Style", "reason-based principle", "minimal intervention", "Sentence", "unnecessary rewrite", "clean prose loses voice", "revision has no reader-problem rationale", "Is the revision more than merely different?", "retain original")]
for row in wb_cla: add("WB5", *row, skill_owner="sentence-clarity", confidence="medium-high", tests="sc-*", examples="sentence-clarity/examples")
add("WB5", "WB-ETH-01", "The Ethics of Style", "ethical clarity", "semantic and ethical fidelity", "Document", "meaning distortion", "revision misstates evidence or responsibility", "scope/certainty/agency changes", "Did the edit preserve every protected proposition?", "restore meaning or reject edit", "sentence-clarity", secondary_skill="all skills", confidence="medium")

for i, (term, canon, signal, op) in enumerate([
    ("old information", "accessible backward link", "opening lacks link to prior discourse", "place accessible context/topic early"),
    ("topic string", "topic continuity", "sentence topics shift without a relation", "repeat, summarize, or explicitly bridge topics"),
    ("cohesion", "local connective flow", "references/lexical chains are ambiguous", "repair referents and lexical links"),
    ("coherence", "recoverable paragraph logic", "sentences are locally clear but point/order is obscure", "reorder or add missing premise"),
    ("old before new", "given-before-dependent-new", "new detail precedes interpretive context", "move context before dependent novelty"),
    ("transition", "explicit logical relation", "transition labels unsupported logic", "supply relation or remove transition"),
    ("global coherence", "document frame", "reader lacks problem/point/order", "frame context, motivating problem, point, and forecast"),
    ("point", "paragraph/document governing claim", "unit has topics but no claim", "state or recover governing claim")], 1):
    add("WB5", f"WB-COH-{i:02d}", "Cohesion and Coherence/Global Coherence", term, canon, "Paragraph" if i < 7 else "Document", "flow/coherence", "reader cannot connect or rank propositions", signal, "What backward relation and forward movement should the reader recover?", op, "cohesion-emphasis", secondary_skill="memo-structure" if i >= 7 else "", confidence="medium")

for i, (term, canon, signal, op) in enumerate([
    ("stress", "syntactic closure emphasis", "payoff sits in weak/intermediate position", "move payoff to a controlled closure"),
    ("end weight", "late heavy constituent", "heavy constituent overloads opening", "place longer material later when compatible"),
    ("new information", "advancing material", "sentence ends with already settled detail", "end with advancing information"),
    ("complexity", "context-dependent complexity placement", "technical detail precedes frame", "provide frame first"),
    ("emphasis", "clause hierarchy", "secondary grammar carries primary claim", "promote claim to main clause"),
    ("short ending", "controlled final emphasis", "several endings compete", "split or punctuate units to control closure")], 1):
    add("WB5", f"WB-EMP-{i:02d}", "Emphasis/Shape", term, canon, "Sentence", "buried emphasis", "reader stresses/ranks wrong material", signal, "Does structural prominence match substantive importance?", op, "cohesion-emphasis", secondary_skill="sentence-variety", confidence="medium")

for i, (term, signal, op, exc) in enumerate([
    ("metadiscourse", "frame comments do not orient/qualify", "delete or state point", "retain useful navigation/stance"),
    ("redundancy", "pair repeats same meaning", "keep informative element", "retain conventional or safety repetition"),
    ("meaningless modifier", "modifier adds no calibrated content", "delete or specify", "retain defined technical modifiers"),
    ("repeated meaning", "proposition recurs without function", "consolidate", "retain cohesion/emphasis/learning repetition"),
    ("phrase for word", "long phrase has precise transparent equivalent", "compress", "avoid jargon substitution"),
    ("hedging/intensification", "stack exceeds evidentiary need", "calibrate", "preserve warranted uncertainty"),
    ("negative form", "negative circumlocution adds work", "state affirmative when exact", "keep prohibitions, contrast, absence"),
    ("terseness", "cutting makes prose harder", "restore enough context/rhythm", "longer can be more concise in reader effort")], 1):
    add("WB5", f"WB-CON-{i:02d}", "Concision", term, "genuine excess", "Phrase", "wordiness", "reader spends effort without gaining function", signal, "Can this be removed without changing protected meaning/function?", op, "concision", exceptions=exc, confidence="medium")

for pid, sec, term, canon, owner in [
    ("WB-UNDER-01", "Understanding Style", "choice", "style as reader-oriented choice", "shared-reference"),
    ("WB-SHP-01", "Shape", "resumptive/summative/free modifier", "controlled sentence expansion", "sentence-variety"),
    ("WB-SHP-02", "Shape", "coordination", "equal logical relation", "sentence-variety"),
    ("WB-ELG-01", "Elegance", "balance and parallelism", "purposeful symmetry", "sentence-variety"),
    ("WB-ELG-02", "Elegance", "rhythm", "audible syntactic movement", "sentence-variety"),
    ("WB-ELG-03", "Elegance", "suspension", "controlled periodic emphasis", "sentence-variety")]:
    add("WB5", pid, sec, term, canon, "Sentence", "form-purpose mismatch", "syntax does not express relationship", "form/rhythm conflicts with rhetorical job", "What relationship should the syntax make perceptible?", "select least marked fitting form", owner, confidence="low-medium")

# Lanham.
lan_steps = [
    ("circle prepositions", "preposition-chain scan", "many prepositional relations delay kernel", "mark and assess each relation"),
    ("circle is", "copular/light-verb scan", "copular frame may carry hidden action", "mark and distinguish state from padding"),
    ("who's kicking whom", "recover actor/action", "action and actor are obscured", "identify supported actor/action"),
    ("simple active verb", "direct action candidate", "action remains nominal/compound", "test a simple finite verb"),
    ("start fast", "windup removal", "empty opening delays clause", "cut or move opening"),
    ("read aloud", "attention/rhythm audit", "revision sounds telegraphic or mis-emphasized", "read with intended feeling"),
    ("rhythmic units", "rhythm-unit map", "cadence is monotonous or uncontrolled", "mark units and repair"),
    ("sentence lengths", "length-pattern map", "length pattern reinforces monotony", "mark lengths as secondary evidence"),
    ("lard factor", "compression statistic", "word savings are unmeasured", "calculate descriptive percentage"),
    ("final reconstruction", "post-cut repair", "deletion leaves grammar/meaning/voice damage", "rebuild and preserve")]
for i, (term, canon, signal, op) in enumerate(lan_steps, 1):
    add("LAN5", f"LAN-PM-{i:02d}", "Action/Attention/Voice", term, canon, "Sentence", "official-style wordiness", "reader attention is consumed by verbal padding", signal, "Does the marked material add protected meaning or function?", op, "concision", secondary_skill="sentence-variety" if i in [6,7,8] else "sentence-clarity", confidence="medium-high", location="Pinto review: Action p.14; Attention p.34; Voice p.42; lard formula review p.4")
for i, (term, signal, op) in enumerate([
    ("Official Style", "institutional prestige style hides action", "translate into direct accountable prose"),
    ("slow windup", "introductory frame delays point", "start with content"),
    ("Skotison", "obscurity appears intentional", "surface purpose and ethical stakes"),
    ("professional jargon", "discipline-licensed phrasing excludes without precision", "retain terms; cut status padding")], 1):
    add("LAN5", f"LAN-OFF-{i:02d}", "Skotison/Business/Professional Prose", term, "institutional padding", "Sentence", "official prose", "action, actor, or point is obscured", signal, "Does this phrasing add precision or merely institutional distance?", op, "concision", confidence="medium")
for pid, sec, term, owner in [("LAN-ATT-01","Attention","reader attention","concision"),("LAN-VOICE-01","Voice","rhythm after cutting","sentence-variety"),("LAN-ELEC-01","Electronic Prose","iterative visual revision","reference-only"),("LAN-WHY-01","Why Bother?","method as beginning","reference-only")]:
    add("LAN5", pid, sec, term, term, "Sentence", "method limit", "mechanical editing displaces judgment", "editor treats method as complete theory", "What additional context or voice check is required?", "apply as diagnostic pedagogy, not total composition system", owner, reference_only=owner=="reference-only", confidence="medium")

# Full Gopen–Swan article.
gs_terms = [
    ("structural expectations", "structural role cue", "material's role is misread", "place it in a fitting structural unit"),
    ("subject-verb expectation", "subject–verb proximity", "interruption burdens dependency", "move/shorten/promote interruption"),
    ("stress position", "closure emphasis", "reader emphasizes wrong material", "place payoff at controlled closure"),
    ("topic position", "opening anchor", "reader lacks backward link/context", "open with accessible topic/context"),
    ("old information", "backward-linking given", "sentence does not link backward", "put accessible link early"),
    ("new information", "advancing information", "new detail lacks context or emphasis", "contextualize then place for stress"),
    ("action in verb", "main-clause action", "action is structurally secondary", "promote action to main verb"),
    ("context before new", "interpretive frame", "technical detail arrives uninterpreted", "supply context first"),
    ("topic string", "paragraph topic continuity", "topics shift without bridge", "relate consecutive topics"),
    ("principles not rules", "heuristic override", "mechanical edit conflicts with purpose", "allow deliberate exception")]
for i, (term, canon, problem, op) in enumerate(gs_terms, 1):
    add("GS90", f"GS-RE-{i:02d}", "full article", term, canon, "Paragraph" if i==9 else "Sentence", "reader-expectation mismatch", problem, problem, "What role/link/emphasis should this structural position signal?", op, "cohesion-emphasis", evidence_type="rhetorical case analysis", empirical_status="full article inspected; no controlled experiment; components have independent support", confidence="high source/medium generalization", location="American Scientist 78.6 (1990), 550–558")

# Tufte chapter-level and derived catalog.
add("TUF", "TUF-ORG-01", "entire organization", "syntax as style", "purpose-driven syntactic repertoire", "Sentence", "form-purpose mismatch", "prose is flat or relationships are obscured", "same architecture repeats without rhetorical function", "What rhetorical job should change?", "choose a syntactic form by function", "sentence-variety", confidence="medium")
add("TUF", "TUF-SHORT-01", "Short Sentences", "short sentence", "purposeful short unit", "Sentence", "choppiness", "related ideas appear falsely equal/disconnected", "series of short independent clauses", "Does separation create contrast/closure or merely chop?", "combine or retain by purpose", "sentence-variety", confidence="low-medium")
for i, canon in enumerate(["left-branching", "right-branching", "mid-branching", "free-modifier control"], 1):
    add("TUF", f"TUF-BR-{i:02d}", "Free Modifiers: Branching Sentences", "branching sentence", canon, "Sentence", "uncontrolled branching", "reader loses kernel/attachment", "branch direction or modifier attachment conflicts with purpose", "Can the reader recover kernel and modifier relation?", "reorder, bound, split, or retain controlled branch", "sentence-variety", confidence="low-medium")
tuf_forms = ["noun phrase", "verb phrase", "adjective/adverb phrase", "prepositional phrase", "coordination", "dependent clause", "relative clause", "adverbial clause", "noun clause", "sentence opener", "inversion", "appositive", "interrogative", "imperative", "exclamatory", "parallelism", "balance/antithesis", "repetition", "ellipsis", "asyndeton/polysyndeton", "fragment", "punctuation-controlled unit"]
for i, form in enumerate(tuf_forms, 1):
    add("TUF", f"TUF-CAT-{i:02d}", "visible chapter taxonomy/derived catalog", form, form, "Sentence", "form-purpose mismatch", "syntax obscures relation or becomes monotonous", f"{form} is repeated, misattached, or rhetorically unmotivated", "What relation or emphasis would this form express?", "select/repair only for a named rhetorical purpose", "sentence-variety", empirical_status="chapter provenance partial; grammatical elaboration marked derived", confidence="low-medium")
add("TUF", "TUF-SYM-01", "Syntactic Symbolism", "syntactic symbolism", "form enacts meaning", "Sentence", "ornament", "display distracts or obscures", "marked form has no reader-serving function", "Does the form clarify or merely imitate?", "retain only apt, clear iconic form", "sentence-variety", confidence="low-medium")

# Minto.
min_principles = [
    ("MIN-WR-01","governing thought","governing answer","Document","no controlling answer","state best-supported answer"),
    ("MIN-WR-02","reader's question","governing question","Document","document answers no clear question","recover audience question"),
    ("MIN-PYR-01","point above summarizes below","parent summary","Section","parent is a topic label","write an insight-bearing parent"),
    ("MIN-PYR-02","vertical logic","question-answer dependency","Section","children do not answer parent-raised question","repair hierarchy"),
    ("MIN-PYR-03","horizontal logic","same-kind sibling group","Section","siblings mix logical kinds","regroup"),
    ("MIN-PYR-04","logical order","declared sibling order","Section","order shifts silently","choose time/structure/degree order"),
    ("MIN-PYR-05","summary statement","insight-bearing summary","Section","category label substitutes for claim","state inference"),
    ("MIN-ORD-01","deduction","premise-case-implication","Section","premise/implication hidden","expose short chain"),
    ("MIN-ORD-02","induction","bounded generalization","Section","unlike facts grouped","group comparable evidence"),
    ("MIN-ORD-03","time order","chronological/process order","Section","steps unordered","order by time"),
    ("MIN-ORD-04","structure/degree order","parts or rank order","Section","mixed basis","declare structure or priority"),
    ("MIN-MECE-01","mutually exclusive","practical non-overlap","Section","categories duplicate","clarify boundaries/disclose overlap"),
    ("MIN-MECE-02","collectively exhaustive","claim-bounded coverage","Section","material gap undermines claim","add gap or narrow claim"),
    ("MIN-MECE-03","MECE","coverage test, not truth guarantee","Document","clean grid hides uncertainty","surface evidence/overlap"),
    ("MIN-SCQA-01","situation","shared relevant context","Document","reader lacks baseline","state minimum shared context"),
    ("MIN-SCQA-02","complication","decision-driving change/tension","Document","reason to care is missing","state complication"),
    ("MIN-SCQA-03","question","governing issue","Document","opening raises several questions","focus question"),
    ("MIN-SCQA-04","answer","governing conclusion","Document","answer buried","state when interpretable/fair"),
    ("MIN-SCQA-05","introduction","reader-preparing opening","Document","formula distorts genre","compress/omit SCQ elements"),
    ("MIN-PS-01","define problem","problem boundary","Document","symptom confused with problem","define gap/standard/current state"),
    ("MIN-PS-02","issue tree","question decomposition","Document","analysis branches overlap/gap","repair decomposition"),
    ("MIN-PS-03","top-down","hypothesis-led construction","Document","assumed answer goes untested","test/replace branches"),
    ("MIN-PS-04","bottom-up","evidence-led synthesis","Document","answer invented before evidence","group facts then infer"),
    ("MIN-PS-05","analysis vs presentation","reasoning/presentation separation","Document","layout substitutes for reasoning","validate analysis first"),
    ("MIN-PS-06","problem-solving process","stage separation","Document","definition/diagnosis/options/recommendation collapse","separate stages")]
for pid, term, canon, level, signal, op in min_principles:
    add("MIN96", pid, "official concept/course; 1996 TOC", term, canon, level, "argument-structure fault", "decision-maker cannot recover or test reasoning", signal, "Does each level answer the reader's governing question with valid support?", op, "memo-structure", empirical_status="normative consulting method; full book unavailable", confidence="medium-high direct method/low page detail")

# Diátaxis full site.
dia_defs = [
    ("DIA-FND-01","action/cognition","reader activity axis"),("DIA-FND-02","acquisition/application","reader-context axis"),("DIA-FND-03","four needs","four-type map"),("DIA-FND-04","architecture","needs-based information architecture"),
    ("DIA-CMP-01","compass","scale-sensitive task classification"),
    ("DIA-TUT-01","learning experience","managed acquisition through action"),("DIA-TUT-02","meaningful activity","real learner achievement"),("DIA-TUT-03","safe path","complete reliable sequence"),("DIA-TUT-04","visible results","early/often feedback"),("DIA-TUT-05","notice","observation cue"),("DIA-TUT-06","repeatability","repeatable learning path"),("DIA-TUT-07","test tutorial","learner validation"),
    ("DIA-HTG-01","goal","real-world user goal"),("DIA-HTG-02","competence","application context"),("DIA-HTG-03","directions","adaptable executable sequence"),("DIA-HTG-04","flow","task-ordered movement"),("DIA-HTG-05","branching","necessary conditional action"),("DIA-HTG-06","omit explanation","action focus"),
    ("DIA-REF-01","technical description","machinery description"),("DIA-REF-02","accuracy","fact validation"),("DIA-REF-03","completeness","scope-bounded completeness"),("DIA-REF-04","neutrality","austere factual style"),("DIA-REF-05","mirror structure","product-shaped architecture"),("DIA-REF-06","standard patterns","consistent lookup schema"),("DIA-REF-07","illustration","brief factual example"),
    ("DIA-EXP-01","understanding","cognitive acquisition"),("DIA-EXP-02","context","background frame"),("DIA-EXP-03","connections","conceptual relations"),("DIA-EXP-04","alternatives","tradeoff/perspective"),("DIA-EXP-05","bounded topic","scope boundary"),("DIA-EXP-06","reflection","why-oriented discussion"),
    ("DIA-APP-01","add/move/remove/change","incremental migration"),("DIA-APP-02","do not impose structure","non-formulaic application"),("DIA-APP-03","close-up compass","section-level typing"),("DIA-APP-04","workflow","iterative maintenance"),
    ("DIA-QUAL-01","accuracy","functional quality"),("DIA-QUAL-02","completeness/consistency/precision","functional quality set"),("DIA-QUAL-03","deep quality","contextual fit/flow"),("DIA-QUAL-04","expose gaps","typing as diagnostic, not guarantee")]
for pid, term, canon in dia_defs:
    typ = "tutorial" if "TUT" in pid else "how-to" if "HTG" in pid else "reference" if "REF" in pid else "explanation" if "EXP" in pid else "framework"
    add("DIA", pid, typ, term, canon, "Document", "documentation type mismatch", "reader contract is violated or content is hard to find/use", f"content serves a different reader activity/context than the dominant {typ} contract", "What is the reader doing and what do they know now?", "classify, bound, move, split, link, or repair type-specific content", "doc-typing", evidence_type="normative living framework", empirical_status="author framework; full site inspected; not universal cognitive taxonomy", confidence="high source/medium universality")

# Garner meta-method and derived taxonomy.
for i, canon in enumerate(["exact issue framing", "grammar/style distinction", "sense/construction disambiguation", "register", "formality", "dialect/region", "World English variety", "field/medium", "time sensitivity"], 1):
    add("GAR5", f"GAR-META-{i:02d}", "front matter/A–Z method", canon, canon, "Usage or convention", "decontextualized verdict", "reader receives unsupported right/wrong claim", "issue lacks exact context dimension", "Which form, sense, construction, audience, register, region, field, and date control?", "narrow issue and condition verdict", "usage-adjudicator", empirical_status="usage lexicography; full 5e corpus unavailable", confidence="medium")
for i, (term, canon) in enumerate([("Stage 1 rejected","rejected"),("Stage 2 widely shunned","widely shunned"),("Stage 3 widespread but…","widespread but avoided in careful usage"),("Stage 4 ubiquitous but…","ubiquitous with residual objection"),("Stage 5 fully accepted","fully accepted"),("index purpose","acceptance-change scale"),("asterisk","invariably inferior marker")], 1):
    add("GAR5", f"GAR-LCI-{i:02d}", "Language-Change Index", term, canon, "Usage or convention", "misreported acceptance", "stage is treated as grammar/frequency/timeless law", "stage is inferred or stripped of context", "Is the stage verified in the exact entry/edition?", "report Garner stage separately and date it", "usage-adjudicator", empirical_status="first-party prescriptive acceptance scale", confidence="high definition/low uninspected issue")
for i, canon in enumerate(["dictionary triangulation", "balanced corpus", "recent monitor corpus", "regional corpus", "normalized frequency", "concordance context", "field/house authority", "query/retrieval record"], 1):
    add("GAR5", f"GAR-EV-{i:02d}", "evidence protocol (derived)", canon, canon, "Usage or convention", "stale or biased evidence", "recommendation misstates present usage", "single authority/raw count controls", "What current, register-matched evidence corroborates or conflicts?", "triangulate and document limits", "usage-adjudicator", evidence_type="derived evidence protocol", empirical_status="portfolio method using authoritative corpora/dictionaries", confidence="high method")
for i, canon in enumerate(["contextual status", "Garner position", "current evidence", "practical recommendation", "disagreement", "confidence", "neutral recast", "uncertainty admission"], 1):
    add("GAR5", f"GAR-DEC-{i:02d}", "decision procedure (derived)", canon, canon, "Usage or convention", "unsupported adjudication", "reader cannot act on nuanced dispute", "verdict lacks one output component", "Does the answer separate authority, current evidence, and recommendation?", "return five-part contextual adjudication", "usage-adjudicator", evidence_type="derived operational procedure", confidence="high design")

gar_tax = ["grammar/syntax", "morphology/inflection", "meaning/diction/confusables", "idiom/collocation", "spelling/capitalization/hyphenation", "punctuation/typography", "pronunciation/stress", "register/formality", "regional/World English", "legal/field jargon", "bias/dated language", "redundancy/pleonasm", "innovation/skunked/folklore", "archaism/euphemism/hypercorrection"]
for i, term in enumerate(gar_tax, 1):
    add("GAR5", f"GAR-TAX-{i:02d}", "A–Z coverage taxonomy", term, term, "Usage or convention", "reference architecture", "issue cannot be retrieved consistently", "entry lacks taxonomy field", "Which usage-question type is this?", "index by derived taxonomy", "usage-adjudicator", reference_only=True, evidence_type="derived taxonomy; Garner A–Z full text unavailable", confidence="medium")

# Strunk/White: explicit negative-control dispositions.
str_dispositions = [
    ("possessive singular", "usage convention", "usage-adjudicator", "already owned; current convention controls"),
    ("serial comma", "punctuation convention", "usage-adjudicator", "house/ambiguity conditioned"),
    ("parenthetic commas", "punctuation/attachment", "usage-adjudicator", "more precise punctuation diagnostics"),
    ("comma before coordinate clause", "punctuation convention", "usage-adjudicator", "already owned"),
    ("no comma splice", "sentence boundary convention", "usage-adjudicator", "register/punctuation exceptions"),
    ("do not break sentences", "fragment control", "sentence-variety", "purposeful fragments allowed"),
    ("opening participial attachment", "modifier attachment", "sentence-clarity", "valid but already owned"),
    ("paragraph unit", "paragraph focus", "cohesion-emphasis", "genre-conditioned and superseded"),
    ("topic sentence/end conformity", "paragraph framing", "cohesion-emphasis", "not universal"),
    ("active voice", "functional voice choice", "sentence-clarity", "crude maxim; passive often useful"),
    ("positive form", "affirmative/negative choice", "concision", "negation often essential"),
    ("definite/specific/concrete", "precision", "shared-reference", "goal too vague for independent procedure"),
    ("omit needless words", "genuine excess", "concision", "superseded by Williams/Lanham diagnostics"),
    ("avoid loose-sentence succession", "purposeful syntax", "sentence-variety", "loose/cumulative syntax can work"),
    ("parallel coordinate ideas", "logical parallelism", "sentence-variety", "already owned"),
    ("keep related words together", "dependency proximity", "sentence-clarity", "already owned; periodic exception"),
    ("one tense in summaries", "genre convention", "usage-adjudicator", "not universal"),
    ("emphatic words at end", "stress position", "cohesion-emphasis", "superseded by precise closure model")]
for i, (term, canon, owner, reason) in enumerate(str_dispositions, 1):
    add("STR18", f"SW-NEG-{i:02d}", f"1918 rule {i}", term, canon, "Usage or convention" if owner=="usage-adjudicator" else "Sentence", "negative-control rule", "blanket maxim can cause incorrect edits", "rule activates without a reader problem", "Which stronger diagnostic and exception controls?", "route to stronger owner or exclude", owner, reference_only=True, exclusion_reason=reason, empirical_status="historical normative advice; negative control", confidence="high")
    principles[-1]["source_id"] = "STR18;STR20"
    principles[-1]["edition"] = "1918 original; 1920 trade"
    principles[-1]["chapter_or_section"] = f"1918 rule {i}; 1920 retained/renumbered counterpart"

white_reminders = ["background", "natural style", "suitable design", "nouns and verbs", "revise", "do not overwrite", "do not overstate", "avoid qualifiers", "avoid breezy manner", "orthodox spelling", "do not explain too much", "awkward adverbs", "speaker identification", "avoid fancy words", "dialect caution", "be clear", "do not inject opinion", "figures sparingly", "no shortcut at clarity cost", "avoid foreign languages", "standard over offbeat"]
for i, term in enumerate(white_reminders, 1):
    add("SW4", f"SW-WHITE-{i:02d}", f"Approach to Style reminder {i}", term, term, "Document", "negative-control reminder", "vague/taste-based rule can distort genre, evidence, or voice", "heading lacks reproducible threshold or conflicts with valid genre", "Can a stronger source supply an observable reader problem?", "route, qualify, or exclude", "negative-control", reference_only=True, exclusion_reason="taste/vague/register-specific/already covered; see dossier", empirical_status="normative taste; full reminder prose unavailable", confidence="medium heading/high access gap")

# Platform principles.
for i, (term, canon) in enumerate([("SKILL.md", "required skill instruction file"),("name", "required canonical name"),("description", "required activation metadata"),("progressive disclosure", "metadata-first loading"),("explicit invocation", "@ in ChatGPT; $ or /skills in Codex"),("implicit invocation", "description-based match"),("agents/openai.yaml", "optional UI/policy/dependencies"),("plugin", "multi-skill distribution package"),("one SKILL.md", "single-skill upload constraint"),("test descriptions", "activation validation")], 1):
    add("PLAT", f"PLAT-{i:02d}", "Build skills", term, canon, "Document", "package/activation fault", "skill fails validation, discovery, or routing", "artifact violates schema or description collides", "Does package match official required/optional structure?", "repair metadata/package/test", "portfolio-infrastructure", evidence_type="official platform requirement", empirical_status="current official documentation with cutoff temporal caveat", confidence="high current")

# Claim ledger: high-consequence synthesis claims only.
claims = [
    ["CL-001", "Basics fifth is the baseline edition; Lessons thirteenth is a current related flagship, not the same edition line", "WB5;WBL13", sources["WB5"]["url"], "direct publisher metadata", "high"],
    ["CL-002", "Lanham fifth contains eight chapters and an eight-step method spanning action, attention, and voice", "LAN5", sources["LAN5"]["url"], "publisher TOC + peer-reviewed review", "medium-high"],
    ["CL-003", "Gopen–Swan's principles are rhetorical heuristics, not a reported controlled experiment", "GS90", "https://people.tamu.edu/~khuffenberger/resources/science-of-writing.pdf", "full article and methods absence", "high"],
    ["CL-004", "Virginia Tufte was Edward Rolf Tufte's mother, not wife", "TUF", "https://www.edwardtufte.com/notebook/artful-sentences-syntax-as-style-by-virginia-tufte-now-published/", "first-party statement + USC obituary", "very high"],
    ["CL-005", "Minto 2026 is latest publisher-numbered edition; 1996 is latest author-designated expanded text visible on her site", "MIN26;MIN96", sources["MIN26"]["url"], "publisher + author metadata", "high; relation unresolved"],
    ["CL-006", "Diátaxis current site exposes 18 English navigation pages and four needs/forms", "DIA", "https://diataxis.fr/", "full site/navigation inspection", "high"],
    ["CL-007", "Garner fifth (2022) is current and full A–Z access was unavailable", "GAR5", sources["GAR5"]["url"], "OUP/Oxford Reference access audit", "high"],
    ["CL-008", "Strunk 1918/1920 are fully public-domain; White fourth is only TOC-accessible here", "STR18;STR20;SW4", sources["SW4"]["url"], "full public texts + publisher metadata", "high"],
    ["CL-009", "OpenAI requires SKILL.md name/description and recommends focused skills with description-driven activation", "PLAT", sources["PLAT"]["url"], "official documentation", "high current; cutoff caveat"],
    ["CL-010", "Global-to-local pass order minimizes invalidated local edits", "portfolio synthesis", "portfolio-pass-order.md", "dependency inference tested in fixtures", "high design"],
]

trigger_rows = [
    ["sentence-clarity", "clarify this sentence; who is doing what; buried action", "awkward/bureaucratic sentence without explicit fault", "make shorter; paragraphs do not flow; vary syntax", "cohesion controls old/new and passive-for-flow; concision controls excess", "explicit user wording controls"],
    ["concision", "make shorter; wordy; bureaucratic; tighten", "simplify", "who is doing what; flat syntax; usage question", "after clarity; before variety; preserve hedges", "explicit length request controls"],
    ["cohesion-emphasis", "paragraphs do not flow; point buried; topic shifts", "improve readability across passage", "isolated actor-action; make shorter", "before clarity/concision; owns old/new and stress", "explicit flow request controls"],
    ["sentence-variety", "flat; repetitive architecture; choppy; all built same", "improve rhythm", "same length only; clean repetition; shorten", "after concision; only form-purpose mismatch", "explicit variety request still preserves clarity"],
    ["memo-structure", "executive memo; recommendation first; SCQ/SCQA; MECE", "organize report", "tutorial; reference; incident chronology", "global argument pass before prose", "explicit conversion allowed if evidence/genre preserved"],
    ["doc-typing", "tutorial or how-to; API page mixes explanation/reference", "organize docs", "memo logic; sentence polish", "first for technical docs; classify by task not heading", "explicit labels do not override reader evidence"],
    ["usage-adjudicator", "which usage is correct; accepted in formal English", "grammar check", "general rewrite; shorter/flow", "last after wording stabilizes; exact issue only", "explicit issue/context controls"],
    ["coordinated portfolio", "edit/polish this whole document", "make this better", "narrow targeted request", "diagnose levels once; run only nonempty passes global-to-local", "explicit narrow wording prevents portfolio fan-out"],
]

def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            if isinstance(row, dict): w.writerow(row)
            else: w.writerow(dict(zip(fields, row)))

write_csv(ROOT / "source-access-ledger.csv", access_fields, access_rows)
write_csv(ROOT / "source-coverage-ledger.csv", ["source_id", "order", "chapter_or_section", "page_or_location", "access", "operational_disposition", "skill_owner", "notes"], coverage)
(ROOT / "principle-registry.json").write_text(json.dumps(principles, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
write_csv(ROOT / "principle-registry.csv", list(principles[0].keys()), principles)
write_csv(ROOT / "claim-to-source-ledger.csv", ["claim_id", "claim", "source_ids", "source_or_artifact", "support_type", "confidence"], claims)
write_csv(ROOT / "trigger-matrix.csv", ["primary_skill", "strong_activation", "weak_activation", "do_not_activate", "ownership_and_sequence", "explicit_wording_rule"], trigger_rows)

print(f"generated {len(access_rows)} access rows, {len(coverage)} coverage rows, {len(principles)} principles")
