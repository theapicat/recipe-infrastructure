# OpenIddict, Sikkerhet og Bakgrunnsjobber i `recipe-auth-api`


## 1. Sikkerhetsarkitektur og OpenIddict-konfigurasjon

`recipe-auth-api` benytter **OpenIddict** i kombinasjon med **ASP.NET Core Identity** for å håndtere identiteter, passordpolicyer, token-utstedelse og øktkontroll.

### Identity-policyer

* **Passordkrav:** Minimum 8 tegn, krever tall og stor bokstav. Ingen krav til spesialtegn for å opprettholde god brukervennlighet uten å gå på bekostning av sikkerheten.
* **Unik e-post:** E-postadresse benyttes som primær brukeridentifikator og må være unik på tvers av systemet.

### OpenIddict Server & Token-konfigurasjon

* **Protokoll & Endepunkt:** OAuth2 og OpenID Connect-tokenutstedelse håndteres via `POST /api/auth/connect/token` (`application/x-www-form-urlencoded`).
* **Tillatte Flows:**
* **Password Grant (`grant_type=password`):** Førstegangs innlogging med brukernavn/e-post og passord.
* **Refresh Token Grant (`grant_type=refresh_token`):** Automatisk og sømløs fornyelse av økten uten at brukeren må oppgi legitimasjon på nytt.


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

---

## 3. Ekstern Autentisering (Google OAuth2)

`recipe-auth-api` støtter sømløs innlogging og registrering via Google OAuth2.

### Google Callback-forløp (`ProcessGoogleCallbackCommandHandler`)

1. **Svartelistekontroll:** Sjekker umiddelbart om Google-kontoens e-postadresse eller e-postdomene finnes i `BlacklistedEntries`. Dersom treff finnes, avbrytes prosessen og brukeren ruting-omdirigeres med feilkode.
2. **Eksisterende bruker:** Dersom brukeren finnes fra før, kontrolleres sperrestatus. Google-tilkoblingen knyttes til brukerkontoen dersom den ikke allerede er registrert (`AddLoginAsync`).
3. **Ny bruker (Automatisk registrering):**
* Oppretter ny `ApplicationUser` med `EmailConfirmed = true` (siden Google allerede har verifisert e-posten).
* Tildeler standardrollen `user`.
* Publiserer domenehendelsen `UserRegisteredWithGoogleEvent` til MassTransit.


4. **Token-generering & Omdirigering:**
* Genererer et JWT Access Token og oppretter et registrert OpenIddict Refresh Token direkte i databasen.
* Omdirigerer brukeren tilbake til frontend sin callback-mottaker med tokens, brukeropplysninger og flagg for fullført velkomst/passordkonfigurasjon.



### Konfigurasjon og Hemmeligheter (Google OAuth)

Google Client ID og Client Secret hentes fra konfigurasjonsstrukturen under seksjonen `Authentication:Google` (eller `Google`).

#### Konfigurasjonseksempel (`appsettings.json` / `appsettings.Development.json`):

```json
{
  "Authentication": {
    "Google": {
      "ClientId": "DIN_GOOGLE_CLIENT_ID.apps.googleusercontent.com",
      "ClientSecret": "DIN_GOOGLE_CLIENT_SECRET"
    }
  }
}

```

#### Håndtering i lokalutvikling og miljøvariabler:

For å unngå at hemmeligheter havner i kildekontroll, benyttes .NET User Secrets i lokalmiljøet, eller miljøvariabler i produksjon/Docker:

* **Via .NET User Secrets (CLI):**
```bash
dotnet user-secrets set "Authentication:Google:ClientId" "YOUR_CLIENT_ID" --project API
dotnet user-secrets set "Authentication:Google:ClientSecret" "YOUR_CLIENT_SECRET" --project API

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
* **Sikkerhetsregel:** Administratorer (brukere med `Admin`-rollen) er eksplisitt skjermet og berøres aldri av automatiske sperringer eller slettinger.

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