# Harness research notes (2026-10-18)

Summary of a literature/engineering survey on scaffolding for small local coding agents. Numbers mostly come
from larger models or SWE-bench; treat them as directional for Gemma 4 12B. Items marked (2nd) were seen only
in secondary summaries.

1. **Describe repeated/failed calls instead of echoing them.** "Feedback That Backfires" (arXiv 2608.23651,
   135M-1.7B models): showing a failure raised repeat probability 0.06 -> 0.54, 83% from the call's literal
   text; replacing it with a harness description removed 76% of the effect; "don't repeat" instructions did
   nothing; deleting the failed attempt was the worst option. OpenHands stuck detector:
   https://docs.openhands.dev/sdk/guides/agent-stuck-detector
2. **Harness-kept todo/plan.** arXiv 2609.20804 (176 harness settings): planning +11.6 pts SWE-bench Verified
   for a 30B model (2nd); mostly cost savings for strong models.
3. **String-replace edits with cascading match, re-indent, refuse ambiguity, syntax check + rollback,
   whole-file fallback.** Lita (arXiv 2509.25873); SWE-agent ACI (arXiv 2405.15793, 18.0 vs 11.0 on Lite);
   Aider edit formats https://aider.chat/docs/llms/editing-format.html
4. **Keep dedicated tools** (not bash-only) for weaker models (2609.20804, Lita).
5. **Mask old observations rather than summarise.** "The Complexity Trap" (arXiv 2508.21433).
6. **Harness-run verification + judge.** R2E-Gym (arXiv 2504.07164): execution-based + execution-free
   verifiers combined 51% vs ~42-43% each.
7. **Best-of-N with selection.** SWE-HERO (arXiv 2604.01496), Recursive Tournament Voting (arXiv 2604.16529).
8. **Chunked large-file writes** (append mode); llama.cpp warns aggressive KV quantisation hurts tool calling.
9. **SWE-agent-style observations** (line windows, explicit empty output, capped search results).
10. **PRM-guided pruning** (SWE-TRACE, arXiv 2604.14820) - lowest priority.

Unverified: per-component numbers of 2609.20804, SWE-agent lint ablation size, SWE-TRACE numbers, any
Gemma-4-12B- or Japanese-specific evidence.
