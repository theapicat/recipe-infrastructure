# `recipe-core-api`

Nås via gateway via fire ruter, alle mot `core-cluster`:

| Rute | Sikkerhetspolicy på gatewayen |
| --- | --- |
| `/api/public/{**catch-all}` | ingen (anonym) |
| `/api/user/{**catch-all}` | `AuthenticatedUser` |
| `/api/admin/{**catch-all}` | `AdminUser` |
| `/hubs/{**catch-all}` | `AuthenticatedUser` |

Som alltid: gatewayen strippet ingen prefiks. Stien videresendes uendret til core-api.

## ⚠️ Nåværende tilstand (2026-09-13): kun `/api/public` er faktisk implementert

Dette er viktig å vite før noen antar mer funksjonalitet finnes enn det som faktisk er bygget:

- **Kun to endepunkter eksisterer i det hele tatt**, begge under `PublicController` (`[Route("/api/public")]`, `[AllowAnonymous]`):
  - `GET /api/public/health`
  - `POST /api/public/contact-form`
- **Det finnes ingen controllere for `/api/user` eller `/api/admin`** — disse gateway-rutene peker i dag på et cluster uten noen faktiske endepunkter for de stiene. Kall dit vil 404 hos core-api selv om de eventuelt slipper gjennom gatewayens autorisasjon.
- **Ingen SignalR-hub finnes** — `/hubs/{**catch-all}`-ruten har heller ingen mottaker i core-api ennå.
- **core-api gjør ingen egen autentisering i det hele tatt.** Det finnes verken `AddAuthentication`/`AddJwtBearer` i `Program.cs`, `UseAuthentication()`/`UseAuthorization()` i middleware-pipelinen, eller kode som leser `X-User-Id`/`X-User-Roles`-headerne gatewayen injiserer. Med andre ord: core-api stoler i dag på nettverksisolasjon alene (kun nåbar via gatewayen), ikke på noen form for identitet — verken egen JWT-validering eller gatewayens injiserte headere.

## Konsekvens for fremtidig arbeid

Når `/api/user`- og `/api/admin`-controllere faktisk bygges i core-api, må det tas et eksplisitt valg:

1. **Stol på gatewayens injiserte `X-User-Id`/`X-User-Roles`-headere** (slik `ReverseProxyExtensions` i gateway-repoet allerede er designet for) — enklest, men krever at core-api aldri er nåbar utenom gatewayen (se punkt 2 i `gateway-jwt-audit-notes.md`: nettverksisolasjon må være reell, ikke antatt).
2. **Valider JWT selv**, uavhengig av gatewayen — tilsvarende hvordan `recipe-auth-api` gjør det via OpenIddict.

Uansett hvilket valg som tas, bør det dokumenteres her når det er implementert, siden det endrer hvilke sikkerhetsgarantier core-api faktisk har.

## Konfigurasjon som må holdes i sync

Ingen i dag. `appsettings.json`/`appsettings.Development.json` i core-api inneholder kun Serilog/Seq-logging, en Postgres-tilkoblingsstreng og RabbitMQ-innstillinger — ingen JWT-nøkkel, issuer eller audience å synkronisere med gatewayen ennå.
