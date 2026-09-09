# Routing contract

## Narrow requests

Explicit user wording selects the narrowest matching skill. Do not fan out merely because several skills can improve writing.

| User need | Primary owner | Do not silently add |
|---|---|---|
| “Clarify this sentence”; “Who is doing what?” | sentence-clarity | general shortening, flow, variety |
| “Make this shorter”; “wordy/bureaucratic” | concision | active-at-all-costs rewrite |
| “Paragraphs do not flow”; “point is buried” | cohesion-emphasis | empty transitions, memo conversion |
| “Flat/repetitive”; “same sentence structure” | sentence-variety | length quotas, decoration |
| “Structure this executive memo”; “recommendation first” | memo-structure | tutorial/reference conversion |
| “Tutorial or how-to?”; “API page mixes types” | doc-typing | heading-only classification |
| “Which usage is correct/accepted formally?” | usage-adjudicator | a full style rewrite |

## Weak triggers

“Simplify,” “organize,” “improve readability,” and “grammar check” are ambiguous. Inspect the supplied text and activate only if a distinct fault class is observable; otherwise ask one short question when the choice would materially change the result.

## Broad requests

“Edit,” “polish,” or “make this better” triggers a coordinated diagnosis, not seven automatic rewrites. Use `portfolio-pass-order.md`; skip empty passes; preserve clean spans; assign one owner per fault. `sentence-clarity` may serve as the local entry point when the host selects only one skill, but it must follow the shared routing reference and must not absorb adjacent methods.

## Two-skill collisions

| Collision | Owner / order |
|---|---|
| Buried action also adds words | sentence-clarity establishes actor/action; concision removes residual excess |
| Passive looks indirect but maintains topic | cohesion-emphasis controls; clarity/concision retain it |
| Nominalization is both topic link and action noun | cohesion-emphasis controls topic link; clarity changes only if key action remains hidden |
| Shortening produces choppiness | concision first; sentence-variety repairs cadence without restoring excess |
| Minto answer-first vs Diátaxis tutorial | doc-typing controls genre; memo-structure does not activate |
| Usage substitution changes flow/emphasis | usage decision last, then local cohesion reread |

## Preservation contract

Every pass must preserve factual scope, quantities, negation, conditions, justified uncertainty, attribution, citations, technical terms, legal effect, relevant agency, useful repetition, and authorial voice unless the user asks for a substantive/register change. A clean sentence or section is a protected asset.

## Relation to `communication`

`skills/communication` is a second layer, not an eighth editing skill. It is always on and governs how the model talks to the reader; this contract is narrow-activation and governs how the model edits text it is handed. At the seam, when a user hands over text to edit: the portfolio owns the method, the pass order, and the preservation contract; `communication` owns how the result is reported (revised text first, one brief note only for a material choice, no preamble, no closer). Its "facts survive verbatim" rule is this contract's preservation clause at reply scale. Its five-item list cap yields to a whole-document audit under its own "a rule fights the task" clause: a long inventory is split and ranked, not truncated. Nothing in `communication` loads the portfolio's references into every turn, and nothing here changes how `communication` shapes an ordinary reply.
