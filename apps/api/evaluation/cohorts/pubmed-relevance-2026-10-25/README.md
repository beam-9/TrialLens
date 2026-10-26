# Fresh PubMed relevance diagnostic

This public-source cohort is separate from the unchanged M0 benchmark. It was captured with the production `PubMedClient` after adding explicit relevance sort, stable returned-ID order and source publication types. Snapshot and inventory hashes are retained; no production workspaces or saved answers were copied. Search results can vary between live requests and records without abstracts are skipped.

The single authored question checks a broad plain-language synthesis, not clinical validity or a calibrated accuracy rate. Do not replace the frozen M0 inventory with this cohort or count its different source set as a controlled before/after quality comparison. The source abstracts include older reviews and a short clinical trial; they do not constitute current guideline verification or comprehensive coverage.

The runner was used with a scoped `unittest.mock.patch.object(cloudflare_run.benchmark, "INVENTORY", inventory_path)` pointing at this inventory and the existing persistent evaluation ledger. Its original inventory global was restored afterward. To reproduce, load server credentials privately, apply that scoped override, call `cloudflare_run.run` with new output paths and `quota_path=Path("data/evaluation-usage.sqlite3")` from `apps/api`, and retain both source and answer observations. Do not overwrite existing results. The same provider, source-hash, quota, HTTP isolation and production-store checks apply.

Captured result: `evaluation/m0/results/cloudflare-fresh-relevance-2026-10-25-answers.json`; timings and primary adjudication are sibling artifacts in the normal results locations. This answer remains partially supported/incomplete and is not a release gate pass.
