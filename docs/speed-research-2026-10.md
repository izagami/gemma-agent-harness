# Dense-model decode speed research (2026-10-18)

Baseline on B70 @150 W, Gemma 4 12B QAT UD-Q4_K_XL: SYCL tg ~51 tok/s (343 GB/s = 56% of 608 GB/s),
MTP n=3 in llama-server 85-111 tok/s. Plain decode headroom is only ~15-20%; the big lever is cheaper
speculative verification. On SYCL, verifying a 16-token batch costs ~8x a single token (PR #29864), so keep
draft lengths <= 8 there.

Ranked options to try (gains unverified on this box unless measured):
1. MTP tuning: sweep --spec-draft-n-max 2..6, add --spec-draft-p-min 0.5, compare MTP Q4_0/Q8_0 drafters;
   rejection-sampling verify (PR #27694) in builds after 2026-10-02.
2. n-gram drafting with MTP: --spec-type draft-mtp,ngram-mod, ngram-mod n-min/n-max ~8/16. Big win on code
   edits and repeated text (agent workloads).
3. XMX multi-column verify kernel (PR #29864, open): +23% with MTP on 27B Q4_K_S; Q4_0 not covered, would
   need a Q4_K_S requant from google/gemma-4-12B-it-qat-q4_0-unquantized.
4. Power cap 150 -> 200 W (dense 27B measured +20% here).
5. SYCL tensor split across both cards (-sm tensor, level_zero:0,1, GGML_SYCL_DEV2DEV_MEMCPY): -20%..+30%,
   card 2 is Gen3 x4 via chipset.
6. vLLM XPU 0.31 (XPU graphs default, fused decode ops) with gemma4_mtp, then TP=2.
7. DFlash drafter z-lab/gemma4-12B-it-DFlash (conversion bug fixed 2026-10-01) - likely below MTP on SYCL.
8. Several users: one server per card (done for the agent eval).
9. Small: F16 SYCL build, AOT -DGGML_SYCL_DEVICE_ARCH, GGML_SYCL_ENABLE_GRAPH (negligible), q8_0 KV only for
   long context.
10. OpenVINO GenAI 2026.4 (Gemma 4 12B + MTP) - one experiment.
Skip: IQ quants on SYCL, Vulkan, layer split, IPEX-LLM (archived), EAGLE-3 checkpoint format.

Measured here: parallel slots (-np 4) on SYCL with MTP collapse per-slot decode to 3-9 tok/s.

Sources: llama.cpp discussions #23313, PRs #29864 #27694 #29604 #29802 #28725 #30380, docs/speculative.md,
docs/backend/SYCL.md, Puget Systems B70 multi-GPU article, vLLM v0.31.0 release notes, intel/llm-scaler,
openvino.genai 2026.4.0.0 release.
