# OpenIddict, Sikkerhet og Bakgrunnsjobber i `recipe-auth-api`


## 1. Sikkerhetsarkitektur og OpenIddict-konfigurasjon

`recipe-auth-api` benytter **OpenIddict** i kombinasjon med **ASP.NET Core Identity** for å håndtere identiteter, passordpolicyer, token-utstedelse og øktkontroll.

### Identity-policyer

* **Passordkrav:** Minimum 8 tegn, krever tall og stor bokstav. Ingen krav til spesialtegn for å opprettholde god brukervennlighet uten å gå på bekostning av sikkerheten.
* **Unik e-post:** E-postadresse benyttes som primær brukeridentifikator og må være unik på tvers av systemet.
* **Roller:** To roller finnes, `admin` og `user` — alltid små bokstaver, både som `IdentityRole`-navn i databasen og i alt som sendes ut (JWT `role`-claim, `/account/me`, Google-redirect). `IdentitySeeder` oppretter dem ved oppstart og retter automatisk opp eventuelle eldre `Admin`/`User`-rader (stor forbokstav) til lowercase, så ingen manuell databasemigrering er nødvendig ved oppgradering. `[Authorize(Roles = "admin")]` og `IsInRoleAsync(user, "admin")`-sjekker rundt om i kodebasen må speile denne casingen.

### OpenIddict Server & Token-konfigurasjon

* **Protokoll & Endepunkt:** OAuth2 og OpenID Connect-tokenutstedelse håndteres via `POST /api/auth/connect/token` (`application/x-www-form-urlencoded`).
* **Tillatte Flows:**
* **Password Grant (`grant_type=password`):** Førstegangs innlogging med brukernavn/e-post og passord.
* **Refresh Token Grant (`grant_type=refresh_token`):** Automatisk og sømløs fornyelse av økten uten at brukeren må oppgi legitimasjon på nytt.
* **Token-inndragelse:** `POST /api/auth/connect/revoke` (RFC 7009) — se seksjon 2.1 under.


* **Token-typer og levetid:**
* **Access Token (JWT):** Signert med HMAC-SHA256 (`SymmetricSecurityKey`). Inneholder claims for bruker-ID, e-post, fornavn, etternavn og roller. Standard levetid er **60 minutter** (konfigurerbart via `Jwt:AccessTokenLifetimeInMinutes`).
* **Refresh Token:** Cryptographic token registrert og validert mot OpenIddict sin tilstand i databasen. Standard levetid er **14 dager** (konfigurerbart via `Jwt:RefreshTokenLifetimeInDays`).


* **Scopes:** `openid`, `profile`, `roles` og `offline_access`.

---

## 2. Token-utstedelse og Innloggingsflyt

All token-utstedelse styres gjennom `AuthorizationController`, som ruter forespørsler direkte til tilhørende MediatR-behandlere for isolert forretningslogikk.

```
[Klient / Next.js Proxy] 
       │
       ▼
POST /api/auth/connect/token
       │
       ├──► grant_type = "password" ──────► PasswordGrantCommandHandler
       │                                         │
       │                                         ├── Validerer passord & sperrestatus
       │                                         └── Utsteder ClaimsPrincipal & Tokens
       │
       └──► grant_type = "refresh_token" ──► RefreshTokenGrantCommandHandler
                                                 │
                                                 ├── Validerer existerende Principal
                                                 ├── Sjekker sperrestatus i DB
                                                 └── Re-utsteder oppdatert Principal

```

### 1. Password Grant Flyt

1. Slår opp bruker basert på e-post eller brukernavn.
2. Kontrollerer at kontoen ikke er sperret (`IsLockedOutAsync`) eller deaktivert (`CanSignInAsync`).
3. Sjekker passord via `SignInManager`.
4. Oppdaterer `LastLoginAt` i databasen.
5. Genererer en ny `ClaimsPrincipal` via `TokenService` og returnerer et gyldig OpenIddict-svar.

### 2. Refresh Token Flyt

1. Henter og validerer eksisterende `ClaimsPrincipal` fra det innkommende refresh-tokenet.
2. Slår opp brukeren i databasen og bekrefter at kontoen fortsatt eksisterer og ikke er sperret.
3. Oppdaterer `LastLoginAt`.
4. Genererer en helt fersk `ClaimsPrincipal` slik at eventuelle nye roller, navneendringer eller tilgangsendringer blir inkludert i det nye access-tokenet.

### 2.1 Token-inndragelse (`POST /connect/revoke`)

RFC 7009-kompatibelt endepunkt som inndrar et refresh-token permanent. OpenIddict håndterer dette endepunktet **helt internt** når `SetRevocationEndpointUris` er registrert i `OpenIddictExtensions.cs` — det finnes ingen passthrough-mekanisme for revocation (i motsetning til token-endepunktet), så det er heller ingen egen kontrollerkode å lese for å forstå oppførselen; alt skjer inne i OpenIddicts eget bibliotek.

* **Forespørsel:** `token` + `token_type_hint=refresh_token` + `client_id` som `application/x-www-form-urlencoded`. Klientene (`recipe-web-app` / `recipe-mobile-app`) er registrert som `Public` uten hemmelighet, så ingen client-autentisering kreves — samme mønster som token-endepunktet allerede bruker.
* **Klienttilknytning er avgjørende:** Et token kan kun inndras av samme `client_id` det ble utstedt til. Dette er grunnen til at `TokenService` (se seksjon 3 under) eksplisitt setter `ClientId = recipe-web-app` på transaksjonen når den utsteder tokens for Google-innlogging — uten det ville ikke revoke funnet igjen tokenet.
* **Viktig begrensning:** Access-tokens er selvstendige, lokalt validerte JWT-er (ikke reference-tokens slått opp i databasen ved hver forespørsel). Å inndra refresh-tokenet gjør **ikke** et allerede utstedt access-token ugyldig før det utløper naturlig (opptil 60 minutter). Dette er en bevisst, akseptert eksponeringsvindu-avveining — ikke noe som er glemt. Skulle det bli nødvendig med umiddelbar access-token-invalidering senere, er de reelle alternativene enten reference/opaque access-tokens (Gatewayen må gjøre et introspection-kall per forespørsel) eller en `jti`-baserte denylist Gatewayen sjekker ved hver validering.
* **Kalles fra frontend:** `recipe-webapp` sin utloggingsrute kaller dette endepunktet **best-effort** rett før den sletter sine egne cookies — en feil her stopper aldri selve utloggingen.

---

## 3. Ekstern Autentisering (Google OAuth2)

`recipe-auth-api` støtter sømløs innlogging og registrering via Google OAuth2.

### Google Callback-forløp (`ProcessGoogleCallbackCommandHandler`)

1. **Svartelistekontroll:** Sjekker umiddelbart om Google-kontoens e-postadresse eller e-postdomene finnes i `BlacklistedEntries`. Dersom treff finnes, avbrytes prosessen og brukeren ruting-omdirigeres med feilkode.
2. **Eksisterende bruker:** Dersom brukeren finnes fra før, kontrolleres sperrestatus. Google-tilkoblingen knyttes til brukerkontoen dersom den ikke allerede er registrert (`AddLoginAsync`).
3. **Ny bruker (Automatisk registrering):**
* Oppretter ny `ApplicationUser` med `EmailConfirmed = true` (siden Google allerede har verifisert e-posten).
* Tildeler standardrollen `user` (små bokstaver, se rollecasing-notatet i seksjon 1).
* Publiserer domenehendelsen `UserRegisteredWithGoogleEvent` til MassTransit.


4. **Token-generering & Omdirigering:**
* Kaller `TokenService.IssueTokenPairAsync(user, baseUri)` for å utstede et ekte, OpenIddict-generert og -lagret access-/refresh-token-par — **samme underliggende mekanisme** som password-/refresh-grant-flyten i seksjon 2 bruker, ikke en separat, håndrullet implementasjon.
* Omdirigerer brukeren tilbake til frontend sin callback-mottaker med tokens, brukeropplysninger og flagg for fullført velkomst/passordkonfigurasjon — tokens sendes rått i redirect-URL-en, ikke som en engangskode, siden det er slik frontend-kontrakten er bygget (`recipe-webapp` sin `/api/auth/google-callback`-rute leser `access_token`/`refresh_token` direkte fra query-parametrene).

**Hvorfor `IssueTokenPairAsync` ikke bare kaller `SignIn()` slik `AuthorizationController` gjør:** Password-/refresh-grant-flyten kjører inne i en levende `/connect/token`-HTTP-forespørsel, der OpenIddicts ASP.NET Core-middleware allerede har satt opp en `OpenIddictServerTransaction` den kan henge `SignIn()`-kallet på. Google-callbacken er derimot en helt vanlig MVC-action (`GET /external-login-callback`) — ingen slik transaksjon finnes der. `TokenService.IssueTokenPairAsync` løser dette ved å drive OpenIddicts interne `OpenIddict.Server`-pipeline direkte:

1. Oppretter en fersk transaksjon via `IOpenIddictServerFactory.CreateTransactionAsync()`.
2. Setter manuelt det ASP.NET Core-verten ellers ville satt automatisk fra selve HTTP-forespørselen:
   * `transaction.BaseUri` — uten denne (eller en global `Options.Issuer`, som ikke er konfigurert her) kaster OpenIddict et unntak i `PrepareAccessTokenPrincipal` fordi den ikke finner noen issuer å bruke.
   * `transaction.Response` — et tomt `OpenIddictResponse`-objekt. `AttachSignInParameters` skriver token-verdiene inn i dette; uten det kastes en `NullReferenceException`.
   * `transaction.Request.ClientId = recipe-web-app` — knytter tokenet til riktig klient, avgjørende for at `POST /connect/revoke` (seksjon 2.1) skal finne det igjen senere.
3. Dispatcher en `ProcessSignInContext` via `IOpenIddictServerDispatcher`, akkurat den samme handler-kjeden OpenIddict selv kjører for `SignIn()`.
4. Et lite fallback-event for `ApplyTokenResponseContext`, registrert i `OpenIddictExtensions.cs`, sørger for at pipelinen fullfører selv uten en tilknyttet `HttpContext` å skrive HTTP-responsen til (den innebygde ASP.NET Core-handleren for dette hopper over synthetiske transaksjoner som denne, siden den krever en ekte tilknyttet forespørsel). Fallback-handleren kjøres sist og rører aldri ekte, nettleserbaserte forespørsler — de er allerede markert håndtert av ASP.NET Core-handleren innen den når frem.

Resultatet er et refresh-token som er identisk i format og databaseforankring med et password-grant-utstedt token — det kan løses inn via `grant_type=refresh_token` og inndras via `/connect/revoke` akkurat som ethvert annet token. Den tidligere implementasjonen bygde en JWT for hånd og satte inn en rå GUID direkte som `Payload` på en manuelt opprettet `OpenIddictToken`-rad — det var aldri et gyldig, innløsbart OpenIddict-tokenformat, og eldre Google-kontoer registrert før dette ble rettet (2026-09-14) kan ha en ubrukelig token-rad liggende igjen; en vanlig ny innlogging utsteder et korrekt token og løser det uten videre inngrep.



### Konfigurasjon og Hemmeligheter (Google OAuth)

Google Client ID og Client Secret hentes fra konfigurasjonsstrukturen under seksjonen `AppSettings` (`AppSettings:GoogleClientId` / `AppSettings:GoogleClientSecret`), lest direkte i `ApplicationExtensions.AddApplicationServices`.

#### Konfigurasjonseksempel (`appsettings.json` / `appsettings.Development.json`):

```json
{
  "AppSettings": {
    "GoogleClientId": "DIN_GOOGLE_CLIENT_ID.apps.googleusercontent.com",
    "GoogleClientSecret": "DIN_GOOGLE_CLIENT_SECRET"
  }
}

```

#### Håndtering i lokalutvikling og miljøvariabler:

For å unngå at hemmeligheter havner i kildekontroll, benyttes .NET User Secrets i lokalmiljøet, eller miljøvariabler i produksjon/Docker:

* **Via .NET User Secrets (CLI):**
```bash
dotnet user-secrets set "AppSettings:GoogleClientId" "YOUR_CLIENT_ID" --project API
dotnet user-secrets set "AppSettings:GoogleClientSecret" "YOUR_CLIENT_SECRET" --project API

```


* **Via Miljøvariabler (Docker / Linux):**
```bash
Authentication__Google__ClientId="YOUR_CLIENT_ID"
Authentication__Google__ClientSecret="YOUR_CLIENT_SECRET"

```



---

## 4. Tidsstyrte Bakgrunnsjobber (`AccountLifecycleJob`)

For å opprettholde datahygiene, beskytte e-postomdømmet og overholde plattformens brukervilkår (§ 3), kjøres den automatiserte bakgrunnsjobben `AccountLifecycleJob` via **Quartz.NET**.

### Kjøreplan og Konfigurasjon

* **Standard kroneskjema:** Hver natt klokken 03:00 (`0 0 3 * * ?`), konfigurerbart via `AccountLifecycle:CronSchedule`.
* **Sikkerhetsregel:** Administratorer (brukere med `admin`-rollen) er eksplisitt skjermet og berøres aldri av automatiske sperringer eller slettinger.

---

### Livsløpsregler for Kontoer

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        UBEKREFTEDE KONTOER                              │
├─────────────┬───────────────────────────────────────────────────────────┤
│ 7 Dager     │ Sendes påminnelse om bekreftelse via e-post               │
│ 14 Dager    │ Kontoen sperres midlertidig for innlogging                │
│ 30 Dager    │ Permanent sletting av konto og data fra databasen         │
└─────────────┴───────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         INAKTIVE KONTOER                                │
├─────────────┬───────────────────────────────────────────────────────────┤
│ 6 Måneder   │ E-postvarsel om inaktivitet sendes til brukeren           │
│ 1 År        │ Kontoen sperres midlertidig pga. inaktivitet              │
│ 1 År + 30d  │ Permanent sletting dersom brukeren ikke reaktiverer       │
└─────────────┴───────────────────────────────────────────────────────────┘

```

#### 1. Ubekreftet e-post

1. **7 Dager (`ConfirmationReminderDays`):** Genererer ny bekreftelsestoken og publiserer `Confirmation7DaysReminderEvent` over MassTransit slik at Notification Service kan sende e-post.
2. **14 Dager (`ConfirmationLockoutDays`):** Låser kontoen permanent (`LockoutEnd = MaxValue`) med årsak `UnconfirmedEmail14Days`. Publiserer `Confirmation14DaysReminderEvent`.
3. **30 Dager (`ConfirmationDeletionDays`):** Sletter brukerkontoen permanent fra Identity. Publiserer `UserAccountDeletedBySystemEvent`.

#### 2. Inaktivitet (Inaktive innlogginger)

Beregnes ut fra brukerens seneste aktivitet (`LastLoginAt ?? CreatedAt`).

1. **6 Måneder (`InactivityWarningMonths`):** Publiserer `Inactivity6MonthsWarningEvent` for å informere brukeren om at kontoen har vært inaktiv.
2. **1 År (`InactivityLockoutYears`):** Låser kontoen med årsak `Inactivity1Year`. Publiserer `Inactivity1YearLockedEvent`.
3. **1 År + 30 Dager (`InactivityDeletionDays`):** Dersom kontoen har vært låst pga. inaktivitet i mer enn 30 dager uten at brukeren har tatt kontakt for gjenåpning, slettes kontoen permanent. Publiserer `UserAccountDeletedBySystemEvent`.