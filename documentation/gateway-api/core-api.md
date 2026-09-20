# `recipe-core-api`

Nås via gateway via fire ruter, alle mot `core-cluster`:

| Rute | Sikkerhetspolicy på gatewayen |
| --- | --- |
| `/api/public/{**catch-all}` | ingen (anonym) |
| `/api/user/{**catch-all}` | `AuthenticatedUser` |
| `/api/admin/{**catch-all}` | `AdminUser` |
| `/hubs/{**catch-all}` | `AuthenticatedUser` |

Som alltid: gatewayen strippet ingen prefiks. Stien videresendes uendret til core-api.

## Autentisering (oppdatert 2026-09-20)

Core API validerer JWT-tokenet **selv** (`AddJwtAuthentication`, `JwtBearer` med symmetrisk nøkkel, issuer, audience,
levetid og `ClockSkew = 0`, altså samme parametre som gatewayen) og håndhever tilgangsnivåene med
`[Authorize]` / `[Authorize(Roles = "admin")]`. Gatewayens policyer er første forsvarslinje, ikke den eneste. Core
bruker ikke `X-User-Id`/`X-User-Roles` som identitetskilde.

- `/api/public/**`: anonym (kontaktskjema, helse).
- `/api/user/**`: enhver innlogget bruker.
- `/api/admin/**`: rollen `admin` (små bokstaver, case-sensitivt, både i gatewayens `AdminUser`-policy og i Core).
- `/hubs/**`: SignalR, krever innlogging; tokenet sendes som `?access_token=` (se Cores egen dokumentasjon for status).

Fullstendig endepunktstabell og detaljer: `recipe-core-api/Documentation/02-endpoints-and-controllers.md` og
`05-authentication-and-authorization.md`. Ikke gjengitt her, siden den listen endrer seg raskt.

## Konfigurasjon som må holdes i sync

`Jwt:Key`, `Jwt:Issuer` (`http://recipe-auth-app/`) og `Jwt:Audience` (`recipe-frontend`) i Core API må være identiske
med gatewayens `Jwt`-seksjon og med `JWT:SecretKey`/`Issuer`/`Audience` i `recipe-auth-api`. Core kaster
`InvalidOperationException` ved oppstart hvis en av dem mangler. Issuer er en absolutt URI som må skrives helt likt
overalt (med avsluttende `/`). Se `auth-api.md` i denne mappen for hvorfor.
