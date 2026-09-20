# Arkitektur og oppsett i `recipe-core-api`

---

Dette dokumentet beskriver den faktiske prosjektstrukturen og hvordan man kommer i gang lokalt, per
2026-09-19. Sjekk mot faktisk kode ved tvil.

## 1. Hva tjenesten er

`recipe-core-api` er kjernebackend for Recipe-plattformen: oppskrifter, ingredienser/næringsinnhold,
måltidsplanlegging og brukerdata. Den ligger bak en YARP-gateway og snakker med søstertjenester
(`recipe-scraper-service`, `recipe-notification-service`) over RabbitMQ, aldri direkte HTTP.

Repoet er tidlig i utviklingen: domenemodellen og admin-katalogene (kategorier, allergener, enheter) er
bygget ende-til-ende, men oppskrifter, måltidsplan og handleliste er ikke påbegynt ennå. Se
`RECIPE_BACKEND_NOTES.md` for designbegrunnelsen bak domenemodellen.

---

## 2. Prosjektgraf

Clean Architecture, ett .NET-prosjekt per lag, kun referanser innover:

```
API  →  Application  →  Persistence  →  Domain
              ↓
          Contracts
```

- **Domain** — rene entitetsklasser, ingen persistens- eller rammeverksavhengigheter.
- **Contracts** — meldingskontrakter som publiseres på RabbitMQ (f.eks.
  `Contracts.Event.ContactFormSubmittedEvent`). Det eneste prosjektet som er ment å sammenlignes mot
  andre mikrotjenesters kontrakter.
- **Persistence** — Dapper mot Postgres via Npgsql, `dbup-postgresql` for migrering. Se
  [`06-persistence-and-data-access.md`](06-persistence-and-data-access.md).
- **Application** — MediatR-commands/-queries og deres handlers (CQRS), pluss alle tverrgående tekniske
  tjenester (caching, meldingspublisering, SignalR). Se [`03-cqrs-and-mediatr.md`](03-cqrs-and-mediatr.md)
  og [`04-events-and-messaging.md`](04-events-and-messaging.md).
- **API** — ASP.NET Core-kontrollere og DI/oppstartskobling. Kontrollere oversetter kun HTTP ↔ MediatR;
  ingen forretningslogikk i kontrollere. Se [`02-endpoints-and-controllers.md`](02-endpoints-and-controllers.md).

**⚠️ Historikk:** det fantes tidligere et eget `Infrastructure`-prosjekt for caching/meldinger/SignalR.
Det ble bevisst slått sammen med `Application` 2026-09-19 — brukerens vanlige vane er å samle alt i
`Application` og først bryte ut et eget prosjekt når noe konkret blir stort nok til å fortjene det.

## 3. Mappekonvensjon per prosjekt

Konsistent gjenbrukt navnekonvensjon for undermapper, satt av brukeren:

- **`Services/`** — kun ekte generiske malklasser ment å arves/lukkes per modell (f.eks.
  `Persistence.Services.DbReader<T>`/`DbWriter<T>`, eller `Application.Caching.Services.MemoryCacheService`
  som den generelle motoren). Opprett **ikke** denne mappen bare fordi noe "føles infrastrukturelt" — kun
  når det faktisk finnes et gjenbrukt malmønster.
- **`Implementation/`** — konkrete klasser som bruker/lukker en mal fra `Services/`, eller konkrete
  MediatR-handlers (f.eks. `Application.MediatR.Catalog`).
- **`Interfaces/`** — kun når en modell trenger metoder utover det generiske malen allerede gir. Ikke lag
  et grensesnitt som bare speiler basisklassens signatur.
- **`Exceptions/`** — egne exception-typer, kun når det faktisk finnes en konkret feiltilstand å dekke
  (se `Persistence/Exceptions/`).
- **`Extensions/`** — samlet ett sted per prosjekt (`API/Extensions/`, `Application/Extensions/`,
  `Persistence/Extensions/`), ikke spredt per undermappe. Én fil per konsern (f.eks.
  `MassTransitExtensions.cs`, `CatalogExtensions.cs`), med én samlende `AddApplicationServices(...)`
  (i `Application/Extensions/ApplicationExtensions.cs`) som kalles fra `API/Program.cs`.

Namespace skal alltid speile mappebanen nøyaktig (`Application/Caching/Services/X.cs` →
`namespace Application.Caching.Services;`), uten unntak.

---

## 4. Kjøre lokalt

```bash
dotnet build                          # bygg hele løsningen
dotnet run --project API              # kjør API-et (http://localhost:5002)
dotnet watch --project API run        # kjør med hot reload
dotnet test Tests/Tests.csproj        # kjør enhetstester (se 07-test-strategy.md)
```

Lokale avhengigheter (Postgres, RabbitMQ, Seq) kjører eksternt (f.eks. via plattformens docker-compose i
et søsken-repo) — tilkoblingsverdier ligger i `API/appsettings.Development.json` (localhost, port 5433 for
Postgres) vs. `API/appsettings.json` (Docker-tjenestenavn som `recipe-core-db`, brukt i
container-/produksjonsoppsett).

**⚠️ Kjent hull:** `Jwt:Key` i `appsettings.Development.json` er tom per denne datoen — API-et kaster
`InvalidOperationException` ved oppstart til den er fylt inn med samme utviklingsnøkkel som gateway og
`recipe-auth-api` bruker. Se [`05-authentication-and-authorization.md`](05-authentication-and-authorization.md).

---

## 5. Teknologistakk

- .NET 10, ASP.NET Core Web API, C# med nullable aktivert.
- MediatR for CQRS command/query-dispatch.
- MassTransit + RabbitMQ for asynkron meldingsutveksling mellom tjenester.
- Microsoft.AspNetCore.Authentication.JwtBearer for autentisering (Core API validerer JWT-en selv).
- SignalR for sanntidspush — kun en tom `Hub`-plassholder (`Application/Realtime/RecipeHub.cs`) foreløpig.
- Dapper + Npgsql for dataadgang, `dbup-postgresql` for skjemamigrering.
- Serilog (Console + Seq) for strukturert logging.
- xUnit + NSubstitute for testing (se [`07-test-strategy.md`](07-test-strategy.md)).

---

Sjekk mot faktisk kode ved tvil.
