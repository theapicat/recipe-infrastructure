# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`recipe-infrastructure` is the central hub for the "Kjøkkenhylla" microservices ecosystem — it is **not** one of the application services itself. It owns the shared local Docker Compose stack (two Postgres instances, MongoDB, RabbitMQ, Seq, Mailpit), cross-repo dev tooling, a mirrored copy of each sibling service's documentation, and LOC/progress tracking. See `README.md` for the full architecture diagram and service matrix.

Sibling repos — `recipe-auth-api`, `recipe-core-api`, `recipe-gateway-api`, `recipe-notification-service`, `recipe-scraper-service`, `recipe-webapp` — live as sibling directories under the same parent folder (`~/Repo/RecipeProject/`) and are each independent git repos, not submodules.

**Scope rule: only make changes inside this repo unless the user explicitly asks otherwise.** This has been stated explicitly and repeatedly — treat it as a hard boundary, not a default to relax by inference, even when a fix "obviously" belongs in a sibling repo (log such things in `todos/consistency-audit.md` instead of editing them directly).

The parent folder (`~/Repo/RecipeProject/`) is intentionally **not** itself a git repository — each project is cloned there as its own independent repo. Don't `git init` at that level even if it looks missing; a stray root-level `.git` was found and removed previously because it had accidentally turned `recipe-auth-api` into a git submodule.

## Commands

```bash
# Start everything: Docker infra + all 6 microservices, each in its own terminal window
./dev-scripts/start-project.sh
./dev-scripts/start-project.sh auth-api notification-service   # only a subset
./dev-scripts/start-project.sh --no-infra                      # skip "docker compose up -d"

# Stop
./dev-scripts/stop-project.sh
./dev-scripts/stop-project.sh --with-infra                     # also "docker compose down"

# Quick health check of already-running HTTP services/dashboards
./dev-scripts/health-test.sh

# Lines-of-code / progress tracking
python3 dev-scripts/count_loc.py                    # full run: terminal + progress-log/ report + history + dashboard
python3 dev-scripts/count_loc.py --no-report         # terminal output only, writes nothing
python3 dev-scripts/count_loc.py --service recipe-auth-api   # deep-dive on one service

# Infra containers directly
docker compose up -d
docker compose down
```

Valid service keys for `start-project.sh` / `stop-project.sh`: `gateway-api auth-api core-api notification-service scraper-service webapp` (defined in `dev-scripts/lib.sh`'s `SERVICE_ORDER`).

## Architecture

### `dev-scripts/lib.sh` is the single source of truth for the shell scripts
`start-project.sh`, `stop-project.sh`, and `health-test.sh` all source `lib.sh` for service definitions (`SERVICE_DIR`/`SERVICE_CMD`/`SERVICE_TITLE`), health-check URLs, terminal-emulator detection, and PID tracking. Don't re-duplicate service/URL lists into the individual scripts — that exact duplication (health-check arrays copy-pasted across two scripts, drifting out of sync) was the original design's bug source and was deliberately refactored away.

### How service processes are launched and tracked (`build_service_inner` in `lib.sh`)
Each service runs as a **plain foreground command** inside its terminal window: `export PATH='...'; cd '<dir>' && echo $$ > '<pidfile>' && ... && <cmd>; exec bash`. This looks unsophisticated on purpose. Two earlier, "smarter" attempts both broke `dotnet watch` in practice: backgrounding the command with `set -m` to capture `$!` reliably, and `exec`-replacing the wrapper with the command — both caused `dotnet watch` to exit almost immediately, because it needs genuine foreground/interactive terminal access. Because there's no job control here, the launched command shares a process group with the wrapper shell, so the wrapper's own PID (written via `$$`) doubles as a valid process-group id for `kill -TERM -- -$PID` later. **Do not reintroduce backgrounding or `exec` here without re-verifying against a real terminal window** — a sandboxed/non-tty test will not reproduce the failure. The unconditional `; exec bash` tail is also deliberate: the window must never auto-close, crash or not, so failures stay visible and the terminal remains usable afterward.

PIDs live in `dev-scripts/.run/*.pid` (gitignored). `stop-project.sh` also sweeps ports 5000/5001/5002/3000 via `lsof` as a fallback safety net for anything started outside this tracking (e.g. from Rider or a manually-run `dotnet watch`).

### `documentation/` is a manually-maintained mirror, not a source of truth
`documentation/{auth-api,gateway-api,notification-service,webapp}/` are copies of each sibling service's own `Documentation/`/`Dokumentasjon/` folder; `documentation/legal/` mirrors `recipe-webapp/public/docs/legal/`. These do **not** update automatically and will silently drift out of date (this already happened once — see `todos/consistency-audit.md`). Re-copy manually from the source repo when asked to refresh docs; don't edit the mirrored copies as if they were canonical. `count_loc.py` explicitly excludes this whole subtree from line counts for the same reason — otherwise every mirrored line gets counted twice.

### `count_loc.py` data model
`progress-log/history.jsonl` is append-only, one JSON object per run, never overwritten — it's the data source for the sparklines and Mermaid charts embedded in the generated `.md` reports (including a per-service trend column). `progress-log/dashboard.md` is always overwritten with the same content as the most recent report, giving a stable link. Report filenames include time as well as date (`YYYY-MM-DD_HH-MM-SS_LOC.md`) so multiple runs on the same day don't collide. `progress-log/` is git-tracked (this was a deliberate choice for portfolio visibility on GitHub — don't re-add it to `.gitignore`).

### Known cross-repo issues (tracked, not fixed here)
`todos/consistency-audit.md` lists inconsistencies found across the sibling services — e.g. a MassTransit contract namespace mismatch between `recipe-core-api` and `recipe-notification-service` for `ContactFormSubmittedEvent` that likely silently breaks message delivery. These are intentionally left unfixed: `recipe-core-api` is very early / mostly unbuilt, and the user plans to address contract consistency once its core domain features exist, not before. `todos/notification-integration.md` tracks a separate, larger pending integration (wiring `recipe-notification-service`'s failed-notification admin flow into `recipe-auth-api`, `recipe-core-api`, and the webapp admin panel).

### Consistency audits (recurring task)

The user periodically asks for a cross-repo consistency audit — this is a manual review (no automated script exists for it, unlike `count_loc.py`), covering exactly these four things:

1. **Dockerfiles** — find every `Dockerfile` across the sibling repos (`find <repo> -maxdepth 2 -iname Dockerfile`) and compare multi-stage structure: base images should match (`mcr.microsoft.com/dotnet/aspnet:10.0` runtime / `dotnet/sdk:10.0` build — *not* `dotnet/runtime`, since `Serilog.AspNetCore` needs the ASP.NET Core shared framework even in non-HTTP Worker Services), same stage names (`base`/`build`/`publish`/`final`).
2. **Serilog config** — for every `appsettings*.json` under each service's API/Service project, the base (non-Development) file's `Serilog` block should have structurally identical `Using`/`MinimumLevel`/`WriteTo`/`Enrich`, and `Properties.Application` must equal the actual repo name exactly (caught `recipe-authentication-api` and a copy-pasted `recipe-core-api` drifting from their real repo names before — see git history of this file for the fix).
3. **MassTransit/RabbitMQ contracts** — any event/command/query class shared between two services (under `Contracts/Events/`, `Contracts/Commands/`, etc.) must have an *identical namespace* in both the publishing and the consuming repo, not just identical fields — MassTransit's default RabbitMQ topology binds exchanges by fully-qualified type name, so a namespace-only mismatch (e.g. `Contracts.Events` vs `Contracts.Events.UserActions`) silently drops messages with no exception anywhere. `diff` the actual `.cs` files across repos; grep for `IPublishEndpoint.Publish`/`IConsumer<T>` to confirm a publisher and a matching consumer both actually exist for each contract.
4. **Documentation mirror freshness** — `diff` each `documentation/<service>/*.md` file here against its source file in the sibling repo; flag anything that has drifted (expected to happen naturally as the sibling repos evolve — this mirror is not auto-synced, see above).

Findings go into `todos/consistency-audit.md`, using its existing format (🔴 real bug / 🟡 inconsistency worth fixing / 🟢 confirmed fine, with a short "consequence" line for anything 🔴). Per the scope rule above: log findings there, don't fix them directly in a sibling repo without asking first — the one prior exception was the Serilog fixes, which the user explicitly authorized in-session.

### GitHub ownership
All 7 repos are meant to be owned by the `theapicat` GitHub account (the account used throughout `README.md`'s links). `recipe-webapp` and `recipe-gateway-api`'s local `origin` remotes still point at an old personal account (`mrBellwood84`) they were created under before ownership moved to `theapicat` — both accounts still have the repos, this is known and considered harmless, not something to "fix" unprompted.
