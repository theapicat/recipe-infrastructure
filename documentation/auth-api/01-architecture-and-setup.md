# recipe-auth-api

Autentiserings- og identitetstjeneste for Kjøkkenhylla-plattformen. Tjenesten er bygget på **.NET 10** med **Clean Architecture**, **CQRS (MediatR)**, **OpenIddict** (OAuth2/OIDC), **ASP.NET Core Identity**, **MassTransit** (RabbitMQ) og **Quartz.NET**.

---

## 🏗️ Arkitektur og Lagdeling

Applikasjonen følger prinsippene for Clean Architecture for å sikre klar ansvarsfordeling og høy testbarhet:

* **API:** HTTP-kontrollere, MassTransit event-consumers, Quartz-bakgrunnsjobber og DI-konfigurasjon.
* **Application:** CQRS Commands, Queries, Handlers og TokenService.
* **Domain:** Entiteter, DTO-er, enumer og konfigurasjonsklasser (Options).
* **Contracts:** Rene hendelseskontrakter for asynkron meldingsutveksling over bussen.
* **Persistence:** EF Core datakontekst mot PostgreSQL, ASP.NET Core Identity og OpenIddict-lagring.

---

## 🚀 Hurtigstart for Lokalutvikling

### 1. Start Felles Infrastruktur (recipe-infrastructure)
Lokal infrastruktur (PostgreSQL, RabbitMQ, MongoDB, Seq, Mailpit m.m.) styres sentralt via prosjektet [recipe-infrastructure](https://github.com/theapicat/recipe-infrastructure).
Klon og start containerne før du kjører recipe-auth-api:

```bash
git clone https://github.com/theapicat/recipe-infrastructure.git
cd recipe-infrastructure
docker compose up -d

```

### 2. Sett Opp Hemmeligheter (User Secrets)

Gå til prosjektmappen `API` og konfigurer lokalhemmeligheter via .NET CLI:

```bash
cd API

# Google OAuth2 Legitimasjon (AppSettings-prefiks)
dotnet user-secrets set "AppSettings:GoogleClientId" "GOOGLE_CLIENT_ID.apps.googleusercontent.com"
dotnet user-secrets set "AppSettings:GoogleClientSecret" "DIN_GOOGLE_CLIENT_SECRET"

# JWT Signeringsnøkkel
dotnet user-secrets set "JWT:SecretKey" "DIN_SUPER_HEMMELIGE_SIGNERINGSNØKKEL"

```

### 3. Oppdater Database og Kjør Seedere

Kjør databasemigreringer mot PostgreSQL-containeren (`recipe-auth-db`):

```bash
dotnet ef database update --project Persistence --startup-project API

```

* **IdentitySeeder:** Oppretter standard roller (`admin`, `user` — alltid små bokstaver) og en initial admin-konto (`admin@kjoekkenhylla.local`). Retter automatisk opp eventuelle eldre `Admin`/`User`-rader til lowercase ved oppstart.


* **OpenIddictSeeder:** Oppretter godkjente OAuth2-klienter (`recipe-web-app` og `recipe-mobile-app`) og legger til manglende permissions (f.eks. `Endpoints.Revocation`) på klienter som allerede finnes fra før.



### 4. Tillit til Utviklingssertifikat

```bash
dotnet dev-certs https --trust

```

---

## 🔑 Autentisering og Endepunkter

All innkommende trafikk rutes gjennom API Gateway med prefikset `/api/auth/*`. Kontrollerne er utformet som tynne kontrollere som videresender forespørsler til MediatR.

* **AccountController (`/api/auth/account`):** Registrering, profiladministrasjon, passordbytte, e-postbekreftelse, velkomstveileder og Google OAuth2.


* **AdminController (`/api/auth/admin`):** Brukeradministrasjon, sperring/gjenåpning, manuell e-postoverstyring og styring av e-postsvartelisten.


* **AuthorizationController (`/api/auth/connect`):** OpenIddict OAuth2/OIDC token-utstedelse (`password` og `refresh_token` grants).


* **HealthController (`/api/auth/health`):** Helsetest-endepunkt for status- og tilkoblingssjekk.



---

## ⚡ Meldingsarkitektur og Bakgrunnsjobber

* **Event-driven messaging (MassTransit / RabbitMQ):** Asynkron kommunikasjon med e-posttjenesten (`recipe-notification-service`) og domenetjenester (`recipe-core-api`).


* **InvalidEmailDetectedConsumer:** Reagerer på uleverbare e-poster via `InvalidEmailDetectedConsumer` for automatisk svartelisting, token-inndragning og kontosletting.


* **Kaskadesletting:** Publiserer slettehendelser slik at andre mikrotjenester rydder opp relaterte brukerdata.


* **Quartz.NET (`AccountLifecycleJob`):** Automatisk nattlig opprydding av ubekreftede kontoer (7d påminnelse, 14d sperring, 30d sletting) og inaktive kontoer (6m varsel, 1y sperring, 1y+30d sletting).



---

## 🛠️ Teststrategi og Kvalitetssikring

Prosjektets testsuite ligger under `Tests/` og følger en firelags testpyramide:

1. **Enhetstester (MediatR Handlers):** Kjøres mot en ekte `UserManager`/`SignInManager`/`RoleManager` over en SQLite in-memory-database (ikke EF Core In-Memory, se testverktøy under), med NSubstitute-mocker kun for rene grensesnitt (`IPublishEndpoint`, `ITokenService`, m.fl.).


2. **Consumer-tester (MassTransit):** Verifisering av hendelseshåndtering (f.eks. `InvalidEmailDetectedConsumer`) via MassTransit In-Memory Test Harness.


3. **Bakgrunnsjobber (Quartz.NET):** Verifisering av livsløpsregler i `AccountLifecycleJob` med tidsmanipulerte kontoer.


4. **API- og Integrasjonstester:** End-to-end verifisering av HTTP-pipeline, OpenIddict token-utstedelse/-fornyelse/-inndragelse og autorisasjon med `WebApplicationFactory` mot den fullt oppstartede verten — det eneste laget som faktisk kjører OpenIddicts interne pipeline, og dermed det eneste som kan fange feil der mockede handler-tester ikke kan.



### Testverktøy

* **xUnit:** Hovedrammeverk for testkjøring.


* **NSubstitute & Shouldly:** Mocking og ekspressive assertions.


* **MassTransit Test Framework & SQLite in-memory (`Microsoft.EntityFrameworkCore.Sqlite`):** In-memory testmiljøer — ekte relasjonell semantikk uten Docker-avhengighet.


* **Microsoft.AspNetCore.Mvc.Testing:** `WebApplicationFactory` for integrasjonstester.



### Kjør tester

```bash
dotnet test Tests/Tests.csproj

```

---

## 📚 Dokumentasjonsoversikt (`Documentation/`)

Prosjektets dokumentasjon er modulært oppdelt under `Documentation/` for å gi dypere innsikt i alle deler av mikrotjenesten:

| Dokument | Beskrivelse |
| --- | --- |
| **[01-architecture-and-setup.md](01-architecture-and-setup.md)** | Dybdeinnsikt i Clean Architecture-lagene, teknologistakk, konfigurasjon (Options), User Secrets og felles infrastruktur.
| **[02-endpoints-and-controllers.md](02-endpoints-and-controllers.md)** | REST API-spesifikasjon og endepunktsoversikt for AccountController, AdminController, AuthorizationController og HealthController.
| **[03-cqrs-and-mediatr.md](03-cqrs-and-mediatr.md)** | Arkitektur for Application-laget med oversikt over alle 28 Command/Query-behandlere, tynne kontrollere og resultat-mønsteret.
| **[04-events-and-messaging.md](04-events-and-messaging.md)** | Event-drevet kommunikasjon via MassTransit/RabbitMQ. Beskriver InvalidEmailDetectedConsumer (hard bounce), utgående hendelser og kaskadesletting.
| **[05-openiddict-security-and-jobs.md](05-openiddict-security-and-jobs.md)** | OAuth2/OIDC token-utstedelse (Password & Refresh grant), Google OAuth2 callback-flyt, og Quartz.NET AccountLifecycleJob.
| **[06-test-strategy.md](06-test-strategy.md)** | Testpyramide og strategi for testprosjektet. Omfatter enhetstesting av MediatR-handlers, event-testing, jobber og integrasjonstester.
