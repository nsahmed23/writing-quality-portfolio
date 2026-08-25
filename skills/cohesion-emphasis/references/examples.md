# Original examples

| Problem | Before | Revision / decision |
|---|---|---|
| Broken topic string | “The gateway rejected the token. Rotation of tenant keys happens nightly.” | “The gateway rejected the token because its tenant key had rotated overnight.” (Only if causality is supported.) |
| Missing premise | “Costs fell. Therefore, we should replace the service.” | Add the decision criterion or remove *therefore*; a transition cannot supply it. |
| Old/new flow | “A regional signing-key mismatch caused the failure. The incident began after deployment.” | If deployment is the known context: “After deployment, the incident began with a regional signing-key mismatch.” |
| Passive for continuity | “The request enters the gateway. It is validated, signed, and routed.” | Keep passive; request remains the topic. |
| Buried emphasis | “The rollout succeeded, although there were delays, in the two regulated regions.” | “Despite delays, the rollout succeeded in the two regulated regions.” or place *regulated regions* last if that is the payoff. |
| Pronoun ambiguity | “The proxy notified the controller after it failed.” | Name the failed component. |
| Clean repetition | “The key is local. The key is encrypted. The key never leaves KMS.” | Keep if the repeated topic supports an assurance sequence. |
