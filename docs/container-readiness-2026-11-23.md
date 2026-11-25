# Local container readiness — 23 November 2026

The standalone Cloudflare profile built and ran locally on Docker Desktop 29.2.1, Linux arm64. Website/API routing, configuration-disabled Ask fallback, review/Brief persistence across restart, and a stopped whole-directory backup restored into a second fresh volume passed. This is local operational evidence, not a remote deployment or proof of provider inference readiness.

## Isolation and build inputs

- Used only `compose.cloudflare.yaml`, explicitly `--env-file /dev/null`, project `tlready1123_7f29`, loopback web port `3102`, fresh volumes `triallens_readiness_1123_7f29_data` and `triallens_readiness_1123_7f29_restored`.
- Explicitly set `CLOUDFLARE_ACCOUNT_ID=''`, `CLOUDFLARE_API_TOKEN=''`, and `TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED=false`. No `.env` or real provider secrets were read. Runtime presence checks confirmed credentials blank and free-plan flag false.
- Did not use `compose.yaml`, Ollama, a local model, paid inference, the user's port 3001, or `triallens_data`. API port remained unpublished; web published only `127.0.0.1:3102->3000`.
- Standard Docker CLI commands stalled before registry metadata resolution. A temporary empty Docker config, installed plugin directory, and explicit local daemon socket resolved the stall without accessing saved registry credentials. Only the three identified commands started for this test were terminated; no Docker configuration was changed globally.
- API `main.py` SHA256 in the running image: `6e13209c5ed78f02a2dee7e4a61b6ba2a385284a58818e5bc96a4a21aaa72d28`.
- Patched web manifest SHA256: `8315a6e171208a35b0315d546d8530d7336ebd268090827383353ff96253f350`; lockfile SHA256: `4128f226ca33570586183c186f05cb1e777032b92488e52800ad0ca159e57f9f`.


## Commands and observed results

All Compose operations used this controlled prefix (temporary CLI config contains only a plugin-directory setting):

```sh
export DOCKER_CONFIG=/private/tmp/tlready1123_7f29-docker
export DOCKER_HOST=unix:///Users/beam.t/.docker/run/docker.sock
export CLOUDFLARE_ACCOUNT_ID='' CLOUDFLARE_API_TOKEN=''
export TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED=false
export TRIALLENS_WEB_PORT=3102
export TRIALLENS_DATA_VOLUME=triallens_readiness_1123_7f29_data
docker compose --env-file /dev/null -f compose.cloudflare.yaml -p tlready1123_7f29 config --quiet
docker compose --env-file /dev/null -f compose.cloudflare.yaml -p tlready1123_7f29 build api web
docker compose --env-file /dev/null -f compose.cloudflare.yaml -p tlready1123_7f29 up -d --no-build --wait --wait-timeout 90
```

| Check | Result |
| --- | --- |
| Controlled Compose validation | Passed |
| API production image build | Passed |
| Web clean `npm ci`, production build and TypeScript | Passed, Next.js 16.4.5 |
| Web production dependency prune audit | Zero vulnerabilities reported during image build; full build dependencies reported 8 advisories (7 moderate, 1 high) |
| Runtime versions/users | Node v22.23.5 / Next.js 16.4.5, UID 1000; API UID 10001 |
| API health check | Passed; `chat=extractive`, `provider=cloudflare` |
| Website and same-origin `/api/health` | HTTP 200; actual HTML and API JSON verified |
| Create workspace through `/api/workspaces` | Passed |
| Existing public fixture indexing | Passed, 1 source and 1 extraction |
| Review extraction through PATCH API | Passed, `review_status=reviewed` |
| Ask through production web proxy | Passed, extractive answer with explicit incomplete-Cloudflare-setup note |
| Save answer to Brief through PATCH API | Passed; generated Brief contains saved answer and reviewed count 1 |
| Restart API/web, repeat read assertions | Passed |
| Stop writers, copy all data, restore into fresh second volume | Passed |
| Post-restore workspace/source/answer/review/Brief | All IDs and review/save state preserved |
| SQLite exact count and integrity | Before/after restart/restore: `(count, sum(charge), sum(pending), sum(answered)) = (3, 0, 0, 3)`; `PRAGMA integrity_check = ok` |
| Backup/restored JSON checksum | Identical: `d255559047a467ef5de141933448fc7802169b00db251b5cf8cfbc259933d622` |

Fixture: existing public ClinicalTrials.gov snapshot `apps/api/evaluation/answer_coverage/fixtures/ctgov-NCT00545844-2026-10-31.json`, SHA256 `8cb7b3d3c682018993c553730398d3fe23ad0e142dcff99f21334c4bdfeec5c4`. It was seeded through the image's `JsonStore`, `build_chunks`, `build_extractions`, and outcome parser rather than using live ingestion or fabricating external research evidence. Workspace creation, review, Ask, Brief saving, and all read verification used the actual production web proxy/API. This does not verify live upstream ingestion.

Three zero-cost historical counter rows were deliberately seeded using `UsageLedger.free_answer('cloudflare')` solely to make restoration of a nonzero counter testable. They represent no inference or genuine generated-answer validation. The configuration-disabled Ask did not increment that counter. Cloudflare quota ledger showed zero requests, zero pending requests and zero used neurons throughout.

The Ask returned: “Cloudflare setup is incomplete. Add the server credentials and confirm the Workers Free plan. Showing source excerpts; no local model or paid provider was called.”

Backup sequence used only this test project: `stop web api`; `cp api:/app/data/. /private/tmp/tlready1123_7f29-backup/`; `down` without volume removal; switch `TRIALLENS_DATA_VOLUME` to the second fresh volume; `create api`; `cp` the backup into the stopped API; run a temporary API container as UID 0 only to chown `/app/data` to 10001; then `up -d --no-build --wait`. Backup contained JSON, its lock file and SQLite; no SQLite sidecars existed at the stopped snapshot. Restoration compared IDs, review/save flags, nonzero SQLite count and exact JSON bytes.

After the production guard fixes were frozen, the API was rebuilt and recreated against the restored volume. Final startup/health through the production proxy passed, and workspace/source/review/saved Brief/counter assertions still passed. Runtime file hashes exactly matched the final source:

- `main.py`: `6e13209c5ed78f02a2dee7e4a61b6ba2a385284a58818e5bc96a4a21aaa72d28`.
- `answer_checks.py`: `c84e0777dc517f8090406d4b081894b563e3f50013e98359b257f0c1a98f2db0`.
- `conversation.py`: `3f7fbfc59afd72d70bcc94c3f1e16ed74517d570580ccedc855e94209af432d6`.

Final API image: `sha256:f7f412ed7256c39a7ef983dce26f6ac58e62d82b57a78780f27ec0445ca4dad4`. The full restart/restore operation used the preceding API image; final-image validation covered startup, health and reading the restored state, without generation.

Initial image IDs:

- API: `sha256:ba4d58b131f7669f4f2495704639ceda255cfb54f6b2a67bd7047df0f9c23170`.
- Web: `sha256:9fff984af4597e8fc4524e0267860e2a57c58870f3c2b6d536ce2074d215abec`.
- Python base digest: `sha256:a83ba18aef0f865b1a4a611c2cf460fe446f2795673bbb9fe43be570439e3b39`.
- Node base digest: `sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee`.

## Limits

Provider credentials, account authorization, Cloudflare free-plan entitlement, real inference, inference quality/latency and external authenticated HTTPS access were intentionally untested. `/health` and Compose API health describe process/configuration, not successful inference. The web service has no own healthcheck; Compose `--wait` considers it running, and the explicit HTTP check supplied website evidence.

`/usage` returned `cloudflare.available=true` with blank credentials because quota-ledger access succeeded. This field must not be interpreted as authenticated provider readiness. The test harness initially assumed false, then corrected its assertion to check zero provider requests and the actual health/fallback response; no application fix was needed for these storage checks.

No browser interaction, source refresh over the network, remote deployment, host reboot recovery, load test, off-host backup storage, or model request was performed. This report does not close those release gates.

## Cleanup

Removed only project `tlready1123_7f29` containers/network and the two explicitly named readiness volumes. Filtered post-cleanup container/volume inventories were empty. Never used Docker prune or volume removal against the user's project. The built image tags remain available locally; no service from this test remains running. Temporary fixture state, backup and credential-free CLI config were removed. No external deployment or commit was performed.
