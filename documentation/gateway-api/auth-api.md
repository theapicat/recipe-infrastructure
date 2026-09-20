# `recipe-auth-api`

Nås via gateway-ruten `auth-route`: `/api/auth/{**catch-all}` → `auth-cluster`, ingen sikkerhetspolicy på selve gateway-ruten (anonym slipper gjennom gatewayen — hvert endepunkt vurderer selv om det krever token).

**Viktig:** gatewayen strippet *ikke* `/api/auth`-prefikset (se [[../README.md]]). `recipe-auth-api` sine controllere deklarerer selv den fulle stien inkludert `api/auth`-segmentet, så en forespørsel til gatewayens `/api/auth/account/me` treffer 1:1 auth-api sin `/api/auth/account/me` — ingen sti-omskriving skjer eller skal skje noe sted i kjeden.

## Autentiseringsmodell

`recipe-auth-api` validerer JWT-tokens **selv og uavhengig** av gatewayen, via OpenIddict sin valideringsmiddleware (`UseLocalServer()`, symmetrisk nøkkel). Den leser **ikke** `X-User-Id`/`X-User-Roles`-headerne som gatewayen injiserer for autentiserte kall — de er irrelevante for denne tjenesten. Gatewayen trenger kun å videresende `Authorization: Bearer <token>`-headeren uendret.

## Endepunkter

### `AccountController` — `api/auth/account`

| Metode | Sti | Krav |
| --- | --- | --- |
| POST | `/api/auth/account/register` | anonym |
| GET | `/api/auth/account/me` | gyldig token |
| PUT | `/api/auth/account/profile` | gyldig token |
| POST | `/api/auth/account/change-password` | gyldig token |
| POST | `/api/auth/account/set-password` | gyldig token |
| GET | `/api/auth/account/complete-welcome` | gyldig token |
| POST | `/api/auth/account/resend-confirmation` | gyldig token |
| POST | `/api/auth/account/confirm-email` | anonym |
| POST | `/api/auth/account/recover` | anonym |
| POST | `/api/auth/account/reset-password` | anonym |
| DELETE | `/api/auth/account/me` | gyldig token |
| GET | `/api/auth/account/external-login` | anonym (starter Google OAuth-redirect) |
| GET | `/api/auth/account/external-login-callback` | anonym (callback etter Google) |

Ingen av disse krever spesifikke roller — kun en gyldig, signert token.

### `AuthorizationController` — `api/auth/connect`

| Metode | Sti | Krav |
| --- | --- | --- |
| POST | `/api/auth/connect/token` | anonym |

OpenIddict sitt token-endepunkt (`password`- og `refresh_token`-grants). Konsumerer `application/x-www-form-urlencoded` — gatewayen må videresende skjema-body uendret (default YARP-oppførsel, ingen spesialhåndtering nødvendig i dag).

### `AdminController` — `api/auth/admin`

Alle handlinger krever `[Authorize(Roles = "admin")]` — altså `admin`-rolleclaim (små bokstaver) i selve JWT-tokenet (uavhengig av gatewayens `AdminUser`-policy, som gjelder core-cluster-ruter, ikke denne).

Ruter: `GET /users`, `GET /users/{id:guid}`, `PUT /users`, `POST /users/lock`, `POST /users/unlock`, `POST /users/confirm-email`, `POST /users/resend-confirmation`, `POST /users/reset-password-request`, `POST /users/delete`, `POST /users/delete-and-blacklist`, `GET /blacklist`, `POST /blacklist`, `DELETE /blacklist/{id:guid}`, `POST /send-email` — alle under `api/auth/admin/...`.

### `HealthController` — `api/auth/health`

| Metode | Sti | Krav |
| --- | --- | --- |
| GET | `/api/auth/health` | anonym |

## Google-innlogging

Dette er en nettleser-redirect-flyt, ikke et fetch/XHR-kall fra frontend:

1. `GET /api/auth/account/external-login?provider=Google` → redirecter brukeren til Google (`Challenge()`).
2. Google redirecter tilbake til `/api/auth/account/signin-google` — dette er ASP.NET sin Google-handler sin `CallbackPath` (satt i `API/Extensions/ApplicationExtensions.cs`), fanges opp av middleware **før** en controller-action nås. **Denne stien må være registrert som redirect-URI i Google Cloud Console, og må nå auth-api uendret gjennom gatewayen** (ingen transform, som alltid).
3. Fullføres i `GET /api/auth/account/external-login-callback`, som kjører `ProcessGoogleCallbackCommandHandler` og til slutt redirecter videre til **frontend** sin egen rute: `{AppSettings:FrontendUrl}/api/auth/google-callback?access_token=...&refresh_token=...&user_id=...&email=...&role=...` — dette siste steget går ikke om gatewayen i det hele tatt, det er en redirect rett til nettleseren/frontend.

## Konfigurasjon som må holdes i sync

`API/appsettings.json` / `appsettings.Development.json`, seksjon `JWT`:

- `JWT:SecretKey` — den symmetriske signeringsnøkkelen. **Denne må være identisk med `Jwt:Key` i `recipe-gateway-api`** sin config, siden begge validerer samme type token symmetrisk (se `gateway-jwt-audit-notes.md` i gateway-repoet for historikk på hvorfor dette har driftet ut av sync før).
- `JWT:Issuer` (`http://recipe-auth-app/`) og `JWT:Audience` (`recipe-frontend`) — må matche `Jwt:Issuer`/`Jwt:Audience` i gatewayen **bokstavelig**. Issuer er en absolutt URI skrevet på normalisert form (med avsluttende `/`). Auth API setter den fast med OpenIddict `SetIssuer` (og kaster ved oppstart hvis verdien er feilskrevet); uten det utleder OpenIddict `iss` fra forespørselens base-URL (`http://localhost:5000/` via gatewayen, `:5001` direkte), og gatewayen og Core avviser alle tokens med `401 The issuer … is invalid`.
- `AppSettings:FrontendUrl` — ikke gateway-relevant direkte, men brukes til redirect-lenker (Google-callback, passordtilbakestilling) som til syvende og sist går til frontend.
