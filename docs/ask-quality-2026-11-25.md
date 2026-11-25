# TrialLens Ask verification — 25 November 2026

## Baseline and candidate

The resumed registry cohort answered the protocol question correctly. The supplied record describes a planned FF versus placebo comparison with a pre-dose PM PEF endpoint, and the answer disclosed the absence of the requested morning result. The posted-results draft exceeded the local reservation headroom before contacting the provider. The remaining registry and asthma cases are untested on this run. See the [baseline answers](../apps/api/evaluation/answer_coverage/results/packet-current-2026-11-25.json).

The evaluation-only structured attribution pilot rendered the broad paper Results answer with exact citation markers and retained the signed −0.94% estimate and its confidence bounds. It failed semantic coverage. Both ± terms were omitted despite appearing in the supplied Results paragraph. The answer implied access to the complete article and did not identify the interval as coming from the caption. Source-level structure solved the syntax error without resolving those claims. The rewrite received a draft, then stopped on the revision quota guard. Its displayed fallback earns no pass. See the [candidate answers](../apps/api/evaluation/answer_coverage/results/paper-structured-2026-11-25.json).

The successful candidate parent and its interrupted follow-up used the earlier wrapper identified by the capture hash starting `c7404b4c`. The checked-in variant clarifies abstention phrasing and wrapper order. Its verification is offline. The capture and its provenance were preserved. The only hosted provider used was Cloudflare Free.

At the end of the run the local evaluation ledger held 8,309.17 neurons used or reserved of 9,000, leaving 690.83 with one pending reservation. The reserve guard checks an upper bound for the exact request. The remaining balance does not suffice for the attempted rewrite revision. The provider reset is at 00:00 UTC. No reservations were removed. Both captures satisfied production-store isolation.

## Outcome

The existing production configuration stays active, and deployment qualification remains open. The [implementation plan](ask-quality-plan-2026-11-25.md) defines the remaining live comparisons and semantic gates. The [research note](ask-quality-research-2026-11-25.md) details a distinct evidence-bound verification experiment for the remaining attribution and completeness failures.

Verification: 733 API tests passed, including strict source-index rendering and unchanged final numeric rejection through the two-pass service. The offline authored holdout located all 10 required passages with ranked context versus 8 with the first-eight baseline. This measures passage availability. The live answer confirmed that available evidence can still be omitted.
