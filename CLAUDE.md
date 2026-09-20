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

# External endpoint test suite (pytest, needs the whole stack up) — see "api-tests/" under Architecture
# Entry point is api-tests/run.sh (./dev-scripts/run-api-tests.sh is just a shortcut to it)
./api-tests/run.sh                  # via the gateway
./api-tests/run.sh --direct         # straight at auth (:5001) and core (:5002), bypassing the gateway
./api-tests/run.sh --read-only      # read-only tests only (no data, no e-mail)
./api-tests/run.sh -k admin -x      # extra args go to pytest

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
`documentation/{auth-api,core-api,gateway-api,notification-service,webapp}/` are copies of each sibling service's own `Documentation/`/`documentation/`/`Dokumentasjon/` folder; `documentation/legal/` mirrors `recipe-webapp/public/docs/legal/`; `documentation/scraper-service/` holds a copy of that repo's `README.md` because the service has no docs folder yet (replace it with the real docs once it gets one — `core-api/` went through the same switch on 2026-09-19). These do **not** update automatically and will silently drift out of date (this has happened twice — see `todos/consistency-audit.md`). Re-copy manually from the source repo when asked to refresh docs; don't edit the mirrored copies as if they were canonical. `count_loc.py` explicitly excludes this whole subtree from line counts for the same reason — otherwise every mirrored line gets counted twice.

Verify freshness with `diff -rq documentation/<service> ../recipe-<service>/<docs folder>` (empty output = in sync). Only the numbered docs are mirrored; other repo-level notes (e.g. `recipe-core-api/RECIPE_BACKEND_NOTES.md`, `CLAUDE.md`) are not.

### `api-tests/` is a black-box endpoint suite, independent of every service
pytest + `requests` + strict pydantic DTOs (`extra="forbid"`, in `apitests/models/`) that mirror the real responses; run through `api-tests/run.sh`. It runs sequentially on purpose (~5 s in total; the user decided against async/parallel runs as needless complexity — parallel workers would also need shared-state and cleanup changes). `api-tests/TESTS.md` documents every test; keep it in sync when tests are added or changed. It is the user's replacement for Postman/Insomnia, so keep it in sync when endpoints change: **whenever a sibling repo adds or changes an endpoint or a response shape, update the DTOs and tests here** (new Core catalog = one entry in `apitests/catalogs.py`; the access matrix and lifecycle tests then cover it automatically). Design rules that must survive edits:
- **Everything the tests create is prefixed `apitest-`** (`settings.test_name/test_email`) and registered for cleanup (`cleanup.register`/`track_user`). A final sweep deletes any `apitest-*` user, blacklist entry or catalog row and fails the run if the tests left something behind. Never make the sweep match anything broader than that prefix.
- **Data-changing tests are `@pytest.mark.mutating`, e-mail-sending tests `@pytest.mark.emails`.** Both are skipped unless `API_TEST_ENV` is `local` (default; all URLs must then be localhost) or `test`. The suite must never be able to write to or e-mail from a non-test environment.
- **E-mail delivery is deliberately not asserted.** Tests call `checklist.expect(recipient, what, trigger)` and each run writes `api-tests/reports/email-checklist-*.md` for a manual check in Mailpit (the user's explicit choice; don't add Mailpit automation unprompted). The checklist was verified against Mailpit on 2026-09-19.
- **Only test endpoints that exist and are supposed to work.** The user explicitly asked (2026-09-20) that tests for known bugs, unbuilt features (e.g. `system-api`) or things that will never exist are left out, and that the suite stays simple. Known bugs live as notes in `todos/consistency-audit.md`, not as tests (the earlier `known_issues.py`/xfail mechanism was removed). Don't add xfail/skip machinery for bugs; report them and ask.
- Users are confirmed through the admin endpoint (no e-mail links), and `register` is sent form-encoded because the endpoint binds `[FromForm]`.
- Use `--direct` to tell whether a failure lives in the gateway or in the service.

### `count_loc.py` data model
`progress-log/history.jsonl` is append-only, one JSON object per run, never overwritten — it's the data source for the sparklines and Mermaid charts embedded in the generated `.md` reports (including a per-service trend column). `progress-log/dashboard.md` is always overwritten with the same content as the most recent report, giving a stable link. Report filenames include time as well as date (`YYYY-MM-DD_HH-MM-SS_LOC.md`) so multiple runs on the same day don't collide. `progress-log/` is git-tracked (this was a deliberate choice for portfolio visibility on GitHub — don't re-add it to `.gitignore`).
**Test code is its own category (`Tester`), moved out of `Ren Kode`, never added on top** (`is_test_file` in `count_loc.py`: code under a `Tests`/`tests`/`test`/`__tests__`/`api-tests`/`*.Tests` directory, or named `*.test.ts(x)`, `*.spec.ts(x)`, `test_*.py`, `conftest.py`). So `code_lines + test_lines` equals the old `code_lines` and `total_lines` is unchanged; docs and config inside test folders keep their own categories, and `documentation/` (the mirror) plus `api-tests/reports/` stay excluded, so nothing is double counted. `history.jsonl` entries from before 2026-09-20 have no `test_lines`, so the first report after this change shows `Ren Kode` dropping by the test amount while `Tester` shows +0 — a one-off discontinuity, not lost work.

### Known cross-repo issues (tracked, not fixed here)
`todos/consistency-audit.md` lists inconsistencies found across the sibling services — e.g. a MassTransit contract namespace mismatch between `recipe-core-api` and `recipe-notification-service` for `ContactFormSubmittedEvent` that silently drops every contact-form message (published to an exchange nobody consumes). These are intentionally left unfixed. **Never change the contact-form event/endpoint/contract unless the user explicitly tells you to** — they have said this directly; investigate and report only. `recipe-core-api` has the admin-managed catalog models and JWT auth built, but recipes, meal planning and shopping lists are not started, and the user plans to address contract consistency together once those exist. The planned failed-notification admin flow lives in a separate future `recipe-system-api` (see `documentation/gateway-api/system-api.md`).

### Conventions the user has decided (apply when auditing or reviewing any service)

- **Other users' data does not exist for the current user.** User-scoped endpoints filter on the owner taken from the token and return an empty result (an empty list), never `403`, and not a `404` that reveals the resource exists. Auth API's account endpoints already follow the spirit of this (they only act on "me" from the token claims); core's recipe endpoints must follow it when built. Still open: exact status/body for get/update/delete of a *single* resource by id owned by someone else.
- **The contact form is anonymous.** `POST /api/public/contact-form` must work for users who are not signed in, so nothing in that path (webapp route, gateway route, core handler, event, notification processor) may require a user, a user id or a token. Currently true — verified 2026-09-19.
- **Dev setup = everything on `localhost` except the infrastructure containers** (Postgres, MongoDB, RabbitMQ, Seq, Mailpit from this repo's compose file); the apps themselves run natively (`dotnet watch` / `npm run dev`). So every `appsettings.Development.json` must point at `localhost` and the *host* ports from `.env` (Postgres: auth `5432`, core `5433`). A connection string is derived as `Host=localhost;Port=<*_DB_PORT>;Database=<*_DB_NAME>;Username=<*_DB_USER>;Password=<*_DB_PASSWORD>;Client Encoding=UTF8;` and was verified with real logins on 2026-09-19. Base `appsettings.json` plus compose `environment:` overrides (container names on `recipe-net`) only matter for dockerized runs, which the user has parked — don't refactor those unprompted.
- **Leave `recipe-scraper-service` alone**: the user hasn't started on it and has said no cleanup there yet. Exclude it from audits and fixes until told otherwise.
- **JWT settings are identical everywhere, literally**: issuer `http://recipe-auth-app/` (an absolute URI, written exactly like that — `recipe-auth-api` pins it with OpenIddict `SetIssuer` and refuses to start if it isn't in normalized form; without a pinned issuer OpenIddict derives `iss` from the request URL and gateway/core reject every token), audience `recipe-frontend`, and the same signing key in `recipe-auth-api` (`JWT:SecretKey`), `recipe-gateway-api` (`Jwt:Key`; also its compose fallbacks and local `.env`) and `recipe-core-api` (`Jwt:Key`). Verified 2026-09-20 by comparing all six places.
- **Role names are lowercase everywhere** (`admin`, `user`): the `role` claim, `[Authorize(Roles = "admin")]`, the gateway's `AdminUser` policy (`RequireRole("admin")`), `X-User-Roles`, the webapp. Role checks are case-sensitive, so an uppercase role string anywhere is a bug to report or fix (fixed in the gateway 2026-09-20).
- **Never `git commit`/`push` in any repo** — the user reviews and commits himself. After changing files, list which repos/files are affected so he can go through them.
- **Ask before adding new code or files** to any project (new scripts, test suites, modules): describe it briefly with a recommendation and wait for a yes. Fixes and docs he explicitly asks for don't need pre-approval. Config keys are case-insensitive, so `JWT` and `Jwt` are the same section; only the key property name differs in auth (`SecretKey`).

### Consistency audits (recurring task)

The user periodically asks for a cross-repo consistency audit — this is a manual review (no automated script exists for it, unlike `count_loc.py`), covering exactly these five things:

1. **Dockerfiles** — find every `Dockerfile` across the sibling repos (`find <repo> -maxdepth 2 -iname Dockerfile`) and compare multi-stage structure: base images should match (`mcr.microsoft.com/dotnet/aspnet:10.0` runtime / `dotnet/sdk:10.0` build — *not* `dotnet/runtime`, since `Serilog.AspNetCore` needs the ASP.NET Core shared framework even in non-HTTP Worker Services), same stage names (`base`/`build`/`publish`/`final`).
2. **Serilog config** — for every `appsettings*.json` under each service's API/Service project, the base (non-Development) file's `Serilog` block should have structurally identical `Using`/`MinimumLevel`/`WriteTo`/`Enrich`, and `Properties.Application` must equal the actual repo name exactly (caught `recipe-authentication-api` and a copy-pasted `recipe-core-api` drifting from their real repo names before — see git history of this file for the fix).
3. **MassTransit/RabbitMQ contracts** — any event/command/query class shared between two services (under `Contracts/Events/`, `Contracts/Commands/`, etc.) must have an *identical namespace* in both the publishing and the consuming repo, not just identical fields — MassTransit's default RabbitMQ topology binds exchanges by fully-qualified type name, so a namespace-only mismatch (e.g. `Contracts.Events` vs `Contracts.Events.UserActions`) silently drops messages with no exception anywhere. `diff` the actual `.cs` files across repos; grep for `IPublishEndpoint.Publish`/`IConsumer<T>` to confirm a publisher and a matching consumer both actually exist for each contract.
4. **Documentation mirror freshness** — `diff` each `documentation/<service>/*.md` file here against its source file in the sibling repo; flag anything that has drifted (expected to happen naturally as the sibling repos evolve — this mirror is not auto-synced, see above).
5. **appsettings / shared configuration** — read every `appsettings.json` and `appsettings.Development.json` (`recipe-auth-api/API`, `recipe-core-api/API`, `recipe-gateway-api/API`, `recipe-notification-service/Service`, `recipe-scraper-service/Service`) plus each repo's `docker-compose.yml`/`.env`, and check that settings that must agree do: the JWT `Issuer`/`Audience`/signing key (auth, gateway, core — including gateway's compose fallback default, its local `.env`, and any empty values; issuer must match literally, `http://recipe-auth-app/`), the `RabbitMQ` block (identical in every service that uses it), DB/Mongo/RabbitMQ credentials and host ports against `recipe-infrastructure/.env` (Postgres core is on host port 5433, auth on 5432), and the Seq URLs (`recipe-seq:80` in base files, `localhost:5341` in Development). Compare values without echoing secrets into the report. A blank or missing `Jwt` value makes core/gateway throw at startup; a mismatched key makes every token fail with 401 and no other clue.

Findings go into `todos/consistency-audit.md`, using its existing format (🔴 real bug / 🟡 inconsistency worth fixing / 🟢 confirmed fine, with a short "consequence" line for anything 🔴). Per the scope rule above: log findings there, don't fix them directly in a sibling repo without asking first — the one prior exception was the Serilog fixes, which the user explicitly authorized in-session.

### GitHub ownership
All 7 repos are meant to be owned by the `theapicat` GitHub account (the account used throughout `README.md`'s links). `recipe-webapp` and `recipe-gateway-api`'s local `origin` remotes still point at an old personal account (`mrBellwood84`) they were created under before ownership moved to `theapicat` — both accounts still have the repos, this is known and considered harmless, not something to "fix" unprompted.
