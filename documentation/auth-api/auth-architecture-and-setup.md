# Arkitektur og Oppsett for `recipe-auth-api`

---

## 1. Systemarkitektur og Lagdeling

`recipe-auth-api` er bygget opp etter prinsippene for **Clean Architecture** for å sikre streng ansvarsfordeling, testbarhet og uavhengighet av eksterne rammeverk.

```text
               ┌─────────────────────────────────────────────────────────┐
               │                        API                              │
               │   (Controllers, Consumers, Jobs, Extensions, Program)   │
               └───────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
               ┌─────────────────────────────────────────────────────────┐
               │                    Application                          │
               │       (MediatR CQRS, TokenService, Handlers)            │
               └──────────────┬───────────────────────────┬──────────────┘
                              │                           │
                              ▼                           ▼
┌─────────────────────────────────────────┐   ┌─────────────────────────────────────────┐
│               Persistence               │   │                Contracts                │
│ (EF Core, OpenIddict Store, Identity)   │   │     (Asynkrone Event-kontrakter)        │
└─────────────────────────────┬───────────┘   └─────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                         Domain                                        │
│               (Entities, DTOs, Enums, Options, Systemgrensesnitt)                     │
└───────────────────────────────────────────────────────────────────────────────────────┘

```

### Ansvarsfordeling per prosjekt

* **`API`:** Innfallsvinkelen for applikasjonen. Inneholder HTTP-kontrollere, MassTransit event-consumers (`InvalidEmailDetectedConsumer`), Quartz-bakgrunnsjobber (`AccountLifecycleJob`) og utvidelser for DI-registrering.
* **`Application`:** Kjernen i forretningslogikken. Inneholder alle CQRS Commands, Queries og Handlers, samt `TokenService` for sammensetting av `ClaimsPrincipal` og JWT-utstedelse.
* **`Domain`:** Inneholder kjernemodeller, entiteter (`ApplicationUser`, `BlacklistedEntry`), enumer, DTO-er og konfigurasjonsklasser (`Options`). Har ingen avhengigheter til andre prosjekter.
* **`Contracts`:** Inneholder rene datakontrakter for eventer som publiseres over meldingsbussen (oppdelt i `UserActions`, `AdminActions` og `SystemActions`).
* **`Persistence`:** Håndterer databasemodellering mot PostgreSQL via Entity Framework Core, ASP.NET Core Identity og lagringsadaptere for OpenIddict.

---

## 2. Teknologistakk

* **Kjøremiljø:** .NET 10 (C#)
* **Databaselag:** Entity Framework Core med PostgreSQL
* **Identitet & Sikkerhet:** ASP.NET Core Identity & OpenIddict (OAuth2 / OpenID Connect)
* **Meldingsbuss:** MassTransit over RabbitMQ
* **Bakgrunnsjobber:** Quartz.NET
* **Logging:** Serilog (Konsoll & Seq på `http://localhost:5341`)

---

## 3. Konfigurasjonsstruktur (`Options`-mønsteret)

Tjenesten benytter .NET sitt `IOptions<T>`-mønster for å binde konfigurasjonsseksjoner fra `appsettings.json` til sterkt typede objekter i `Domain/Options`:

* **`AppSettings` (`AppSettings`):** Inneholder `FrontendUrl` for e-postlenker/callbacks, samt client_id-er for OpenIddict-seeding (`recipe-web-app` og `recipe-mobile-app`).
* **`AdminUserOptions` (`AdminUser`):** Standard identitet (`admin@kjoekkenhylla.local`) og oppstartspassord som benyttes av `IdentitySeeder` for opprettelse av initial administrator.
* **`JwtOptions` (`JWT`):** Styrer JWT-signeringsnøkkel, utsteder (`recipe-auth-app`), målgruppe (`recipe-frontend`) og konfigurerbare levetider for Access Tokens (60 minutter) og Refresh Tokens (14 dager).
* **`AccountLifecycleOptions` (`AccountLifecycle`):** Konfigurerer tidsfrister for automatisk opprydding og sperring av inaktive eller ubekreftede kontoer, samt Quartz-kroneskjema (`0 0 3 * * ?`).
* **`RabbitMqOptions` (`RabbitMQ`):** Tilkoblingsdetaljer (vert, port, virtuell vert, brukernavn og passord) for RabbitMQ.

---

## 4. Hemmeligheter og Miljøvariabler (Secrets Management)

For å forhindre at sensitive opplysninger lekker til kildekontroll (GitHub), holdes alle hemmeligheter utenfor kildekoden i produksjon/staging.

### Kritiske hemmeligheter

| Konfigurasjonsnøkkel | Beskrivelse | Miljøvariabel (Linux / Docker) |
| --- | --- | --- |
| `JWT:SecretKey` | HMAC-SHA256 signeringsnøkkel for JWTs | `JWT__SecretKey` |
| `Authentication:Google:ClientId` | Google OAuth2 Client ID | `Authentication__Google__ClientId` |
| `Authentication:Google:ClientSecret` | Google OAuth2 Client Secret | `Authentication__Google__ClientSecret` |
| `AdminUser:Password` | Passord for initial administrator | `AdminUser__Password` |
| `ConnectionStrings:DefaultConnection` | Tilkoblingsstreng til PostgreSQL | `ConnectionStrings__DefaultConnection` |
| `RabbitMQ:Password` | Passord for RabbitMQ-tilkobling | `RabbitMQ__Password` |

### Konfigurasjon i lokalutvikling (User Secrets)

For lokalutvikling benyttes .NET User Secrets, som lagres i brukerens lokalprofil uavhengig av prosjektmappen:

```bash
cd API

# Sett Google OAuth2 legitimasjon
dotnet user-secrets set "Authentication:Google:ClientId" "DIN_GOOGLE_CLIENT_ID"
dotnet user-secrets set "Authentication:Google:ClientSecret" "DIN_GOOGLE_CLIENT_SECRET"

# Sett JWT Secret Key
dotnet user-secrets set "JWT:SecretKey" "DIN_SUPER_HEMMELIGE_SIGNERINGSNØKKEL"

```

### Konfigurasjon i Docker / Produksjon

I containeriserte miljøer oversettes .NET sine kolon-separerte nøkler (`:`) til dobbelt understrek (`__`):

```bash
docker run -e Authentication__Google__ClientId="YOUR_CLIENT_ID" \
           -e Authentication__Google__ClientSecret="YOUR_CLIENT_SECRET" \
           -e JWT__SecretKey="YOUR_SECRET_KEY" \
           recipe-auth-api

```

---

## 5. Lokal Oppstart og Databasedrift

### 1. Felles Lokal Infrastruktur (`recipe-infrastructure`)

Lokal infrastruktur for hele plattformen (PostgreSQL, RabbitMQ, MongoDb, Seq og Mailpit) styres sentralt via repoet **[`recipe-infrastructure`](https://github.com/theapicat/recipe-infrastructure)**.

Før `recipe-auth-api` startes opp lokalt, må containerne i infrastrukturen være oppe og kjøre:

```bash
git clone https://github.com/theapicat/recipe-infrastructure.git
cd recipe-infrastructure
docker compose up -d

```

Dette vil blant annet starte containeren `recipe-auth-db` (PostgreSQL på port 5432), `recipe-message-broker` (RabbitMQ på port 5672/15672) og `recipe-seq` (Seq loggdashboard på port 5341).

### 2. Databasemigrering og Seeding

Når infrastrukturcontainerne kjører, opprettes og oppdateres datatabellene i `recipe-auth-db` ved å kjøre Entity Framework Core-migreringer:

```bash
dotnet ef database update --project Persistence --startup-project API

```

Under oppstart av `Program.cs` kjøres automatisk to seedere mot databasen:

1. **`IdentitySeeder`:** Oppretter standard roller (`Admin`, `User`) samt den initiale administratorkontoen (`admin@kjoekkenhylla.local`) dersom denne ikke finnes fra før.
2. **`OpenIddictSeeder`:** Oppretter og konfigurerer godkjente OAuth2-klienter (`recipe-web-app` og `recipe-mobile-app`) i OpenIddict-tabellene.

### 3. Utviklingssertifikater (HTTPS)

For at lokal kommunikasjon mellom Next.js, API Gateway og `recipe-auth-api` skal fungere sømløst over HTTPS uten SSL-sertifikatfeil, må det lokale .NET-sertifikatet klareres på maskinen:

```bash
dotnet dev-certs https --trust

```