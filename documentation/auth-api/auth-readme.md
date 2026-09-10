# `recipe-auth-api`

Autentiserings- og identitetstjeneste for Kjøkkenhylla-plattformen. Tjenesten er bygget på **.NET 10** med **Clean Architecture**, **CQRS (MediatR)**, **OpenIddict** (OAuth2/OIDC), **ASP.NET Core Identity**, **MassTransit** (RabbitMQ) og **Quartz.NET**.

---

## 🚀 Hurtigstart for Lokalutvikling

### 1. Start Felles Infrastruktur (`recipe-infrastructure`)

Lokal infrastruktur (PostgreSQL, RabbitMQ, MongoDB, Seq, Mailpit m.m.) håndteres sentralt via prosjektet [`recipe-infrastructure`](https://github.com/theapicat/recipe-infrastructure).

Klon og start containerne før du kjører `recipe-auth-api`:

```bash
git clone https://github.com/theapicat/recipe-infrastructure.git
cd recipe-infrastructure
docker compose up -d

```

### 2. Sett Opp Hemmeligheter (User Secrets)

Gå til prosjektmappen `API` i `recipe-auth-api` og sett opp lokalhemmeligheter via .NET CLI:

```bash
cd API

# Google OAuth2 Legitimasjon
dotnet user-secrets set "Authentication:Google:ClientId" "DIN_GOOGLE_CLIENT_ID"
dotnet user-secrets set "Authentication:Google:ClientSecret" "DIN_GOOGLE_CLIENT_SECRET"

# JWT Signeringsnøkkel
dotnet user-secrets set "JWT:SecretKey" "DIN_SUPER_HEMMELIGE_SIGNERINGSNØKKEL"

```

### 3. Oppdater Database og Kjør Seedere

Kjør databasemigreringer mot PostgreSQL-containeren (`recipe-auth-db`):

```bash
dotnet ef database update --project Persistence --startup-project API

```

* `IdentitySeeder` oppretter standard roller (`Admin`, `User`) og en initial admin-konto (`admin@kjoekkenhylla.local`).
* `OpenIddictSeeder` oppretter godkjente OAuth2-klienter (`recipe-web-app` og `recipe-mobile-app`).

### 4. Tillit til Utviklingssertifikat

```bash
dotnet dev-certs https --trust

```

---

## 📚 Dokumentasjonsoversikt (`Documentation/`)

Prosjektets dokumentasjon er modulært oppdelt under mappen `Documentation/` for å gi dyp, teoretisk og konseptuell innsikt i alle deler av mikrotjenesten:

| Dokument                                                                                                                                                                            | Beskrivelse |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------| --- |
| **[`01-architecture-and-setup.md`](/Documentation/01-architecture-and-setup.md)**                                                                                                   | Dybdeinnsikt i Clean Architecture-lagene, teknologistakk, konfigurasjon (`Options`), User Secrets og felles infrastruktur. |
| **[`02-endpoints-and-controllers.md`](/Documentation/02-endpoints-and-controllers.md)**       | REST API-spesifikasjon og endepunktsoversikt for `AccountController`, `AdminController`, `AuthorizationController` og `HealthController`. |
| **[`03-cqrs-and-mediatr.md`](/Documentation/03-cqrs-and-mediatr.md)**                         | Arkitektur for `Application`-laget med oversikt over alle 28 Command/Query-behandlere, tynne kontrollere og resultat-mønsteret. |
| **[`04-events-and-messaging.md`](/Documentation/04-events-and-messaging.md)**                 | Event-drevet kommunikasjon via MassTransit/RabbitMQ. Beskriver `InvalidEmailDetectedConsumer` (hard bounce), utgående hendelser og kaskadesletting. |
| **[`05-openiddict-security-and-jobs.md`](/Documentation/05-openiddict-security-and-jobs.md)** | OAuth2/OIDC token-utstedelse (Password & Refresh grant), Google OAuth2 callback-flyt, og Quartz.NET `AccountLifecycleJob`. |
| **[`06-test-strategy.md`](/Documentation/06-test-strategy.md)**                               | Testpyramide og strategi for testprosjektet. Omfatter enhetstesting av MediatR-handlers, event-testing, jobber og integrasjonstester. |

---

## 🛠️ Testing og Kvalitetssikring

Prosjektets testsuite ligger i `Tests/` og kjøres med xUnit:

```bash
# Kjør alle enhets- og integrasjonstester
dotnet test Tests/Tests.csproj

```