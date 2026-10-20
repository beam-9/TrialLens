# Run a private TrialLens pilot

The Compose setup packages the web app, API and Ollama on one host. Only the website is published, on **127.0.0.1:3001** by default. It is a starting point for a trusted private pilot, not a public multiuser deployment. It does not add accounts or workspace ownership: people with access share the installation's research workspaces.

## Choose the inference host first

The default local model is `qwen3.5:9b`, approximately 6.6 GB to download. Keep sufficient RAM and disk for the model, its context cache, images and research data. The deployment has no GPU allocation configured. CPU-only execution may be substantially slower than the native development setup. Docker Desktop on an Apple Silicon Mac does not give this Linux container the native Ollama Metal acceleration; use the documented native launcher for local Mac work, or validate a suitable accelerated Linux host before inviting remote users.

The application intentionally sends inference to `127.0.0.1:11434`. Compose makes this work by giving the API the Ollama service's network namespace. The web server reaches the API as `http://ollama:8000`; browser requests use the website's same-origin `/api` proxy. Neither port 8000 nor 11434 is published to the host. Do not replace this with direct browser access to the model.

## Provision and start

Install Docker with the Compose plugin and start its daemon. Run these commands from the repository root:

```sh
docker compose config --quiet
docker compose build
docker compose up -d ollama
docker compose exec ollama ollama pull qwen3.5:9b
docker compose up -d api web
docker compose ps
```

Open `http://127.0.0.1:3001`. The explicit pull is the only model provisioning step; no model is baked into an image. Ollama cloud features are disabled, and the API provider is explicitly local. There is no paid provider fallback or API key in this stack. Public-source ingestion still needs outbound internet access. Building the web image also needs npm and Google Fonts access.

For a different model, use the same value for provisioning and API configuration:

```sh
TRIALLENS_LOCAL_MODEL=qwen3.5:9b docker compose up -d api web
docker compose exec ollama ollama pull qwen3.5:9b
```

Only use an actually local model; cloud tags are rejected. Changing the model requires repeating the semantic evaluation. `TRIALLENS_WEB_PORT` can select another host port while retaining the loopback binding. A local `.env` used for Compose interpolation is excluded from image builds and Git; the stack does not load the development API `.env`.

The images use Python 3.11, Node 22 and Ollama 0.32.14. Application dependencies are pinned by the Python requirements and npm lockfile. Base-image tags are versioned but not immutable digests; capture the actual image IDs used for a pilot release and retain them for rollback.

## Check readiness and the actual workflow

```sh
curl --fail http://127.0.0.1:3001/api/health
docker compose exec ollama ollama list
docker compose logs --tail=100 api web ollama
```

`/health` confirms API configuration and connectivity, not whether a model can answer. Compose's Ollama check also confirms only runtime availability. Confirm that `ollama list` contains the configured model, then submit a real Ask question and a referential follow-up through the UI. Inspect every biomedical claim against its cited source. A conversational badge means formatting/provenance checks passed, not that the answer is medically validated.

Before admitting users, exercise create/ingest, source inspection and filters, an open-ended question, a numerical question, missing evidence, a follow-up, save/remove from Brief, Markdown export and reload. Test a cold model start and a model failure. Measure response times and concurrent-request behavior on this host. The model runs one inference stream at a time; the 100-answer alert is not an admission or rate limit.

The Next.js proxy allows long local-model requests; configure any additional gateway/proxy timeout to accommodate the measured worst case. Each model pass has a 180-second timeout and an answer uses two passes. Avoid a platform with a shorter hard request-duration limit unless the implementation is changed to asynchronous jobs.

## Persist, back up and restore

The named `triallens_data` volume holds **both** workspace JSON and the SQLite usage ledger, so restarts preserve answers, review state and usage. `triallens_models` stores model downloads. The `api` image initializes its data directory for the unprivileged application user (UID 10001). Do not use `docker compose down --volumes` for routine shutdown; it deletes these persistent volumes.

For a consistent manual data backup, stop writers first. These commands leave Ollama running:

```sh
docker compose stop web api
mkdir -p backups/pilot-data
docker compose cp api:/app/data/. backups/pilot-data/
docker compose up -d api web
```

Store the backup outside the deployment host and record the application commit/image IDs alongside it. Do not commit workspace or usage data. Back up the entire directory, including any SQLite sidecar files, rather than copying the JSON alone.

To restore, stop web/API, keep the old snapshot separately, and copy a known-good backup into the stopped API container's mounted data directory:

```sh
docker compose stop web api
docker compose cp backups/pilot-data/. api:/app/data/
docker compose run --rm --no-deps --user 0 api python -c "import os; from pathlib import Path; [os.chown(p, 10001, 10001) for p in [Path('/app/data'), *Path('/app/data').rglob('*')]]"
docker compose up -d api web
```

This copies files over the existing directory; restore into a clean data volume for a full rollback so extra files from a newer version cannot survive. Practice restoration on a separate test stack/volume, then verify a workspace, saved brief and usage count before relying on the procedure. Backup/restore has not been exercised in a container during this implementation pass.

## Remote access and operation

Keep the loopback binding. Before any remote use, put the entire website **and its `/api` routes** behind an authenticated HTTPS gateway or trusted VPN/SSH access path. An identity gateway on the same host can proxy to 127.0.0.1:3001. Do not publish the raw API or inference ports. A login screen in the frontend alone would leave the backend unprotected. Configure access intentionally before sharing a URL.

Use restart policies plus host monitoring; arrange startup after host reboot. The Ollama network namespace is shared, so after replacing/recreating the Ollama container recreate its dependent API and web services together. Keep the persistent volumes. For an application rollback, restore the recorded prior source/image version, rebuild/restart API and web, and verify the current data format is compatible before serving it. Roll back data from a tested backup if a future migration requires it.

This pilot handles public research queries and working research notes. It has no patient-data workflow, per-user data isolation, automatic retention policy or deletion UI. Confirm the access group understands the shared workspace scope.

## Verification limits

`docker compose config --quiet` passes. The pinned Ollama image manifest was checked and exists for Linux amd64 and arm64. The local Docker daemon was unavailable, so images were not built, containers were not started, model provisioning was not repeated inside Docker, and no throughput or restore claim is made. Finish those checks on the chosen host before deployment. See `deployment-readiness.md` for remaining release gates.
