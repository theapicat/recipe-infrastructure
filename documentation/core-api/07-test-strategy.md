# Teststrategi i `recipe-core-api`

---

Per 2026-09-19. Sjekk mot faktisk kode ved tvil.

## 1. Oppsett

Ett testprosjekt, `Tests/Tests.csproj` (xUnit), referanse til `API`, `Application`, `Contracts`, `Domain`
og `Persistence`. Mappestrukturen speiler kildekoden 1:1 (samme regel som ellers i løsningen: namespace
skal alltid matche mappebanen).

```bash
dotnet test Tests/Tests.csproj
```

34 tester, alle grønne, ingen ekstern avhengighet (ingen Postgres/RabbitMQ trengs for å kjøre dem).

### Verktøyvalg

- **xUnit** — testrammeverk.
- **NSubstitute** — mocking. Valgt fordi det allerede lå i lokal NuGet-cache og har en moderne, enkel
  syntaks.
- **Innebygd `Assert`, ikke FluentAssertions** — FluentAssertions v8+ krever betalt lisens for kommersiell
  bruk, og dette er et kommersielt prosjekt. `Xunit.Assert` er tilstrekkelig og koster ingenting.

---

## 2. Hva som er dekket

| Område | Testfil(er) | Hva som verifiseres |
| --- | --- | --- |
| `Persistence/Services/DbReader<T>`/`DbWriter<T>` | `Tests/Persistence/Services/` | Kaster riktig exception-type når en query/command ikke er konfigurert — ingen databaseforbindelse trengs siden feilen kastes før tilkobling åpnes. |
| `Application/Caching/Services/MemoryCacheService` | `Tests/Application/Caching/` | Get/Set/Remove-primitivene med en ekte `IMemoryCache` (ingen mocking nødvendig). |
| Generiske katalog-handlers (`GetAll`/`GetById`/`Insert`/`Update`/`Delete`) | `Tests/Application/MediatR/Catalog/` | Cache-treff kaller aldri `DbReader<T>`; cache-miss henter fra reader og fyller cachen; skriveoperasjoner ugyldiggjør cachen; `Delete` returnerer `bool` basert på antall berørte rader. |
| `CatalogExtensions.AddCatalogHandlers()` | `Tests/Application/Extensions/` | Regresjonstest for et reelt problem oppdaget under utvikling — at alle fem handler-typer faktisk blir registrert for hver av de seks katalogtypene (se [`03-cqrs-and-mediatr.md`](03-cqrs-and-mediatr.md) for hvorfor dette ikke skjer automatisk). |
| `MassTransitEventPublisher` | `Tests/Application/Messaging/` | Delegerer korrekt til `IPublishEndpoint.Publish`. |
| `SendContactFormCommandHandler` | `Tests/Application/MediatR/Public/ContactForm/` | Bygger og publiserer riktig hendelse, returnerer `true`. |
| `ReadCatalogController<T>`/`ReadWriteCatalogController<T>` | `Tests/API/Controllers/` | Riktig HTTP-resultat (`Ok`/`NotFound`/`NoContent`) basert på hva mediator returnerer. |
| `JwtAuthenticationExtensions` | `Tests/API/Extensions/` | Kaster `InvalidOperationException` når `Jwt:Key`/`Issuer`/`Audience` mangler; lykkes når alt er satt. |

---

## 3. Hva som ikke er dekket

**⚠️ Planlagt — ikke bygget:**

- **Integrasjonstester mot ekte Postgres.** De konkrete `Reader`/`Writer`-klassenes faktiske SQL (funksjonene
  i `Persistence/Scripts/`) er kun verifisert manuelt med en engangs Docker-container under utvikling
  (opprettet og fjernet igjen samme økt), ikke med en permanent testpakke. Naturlig neste steg:
  Testcontainers-basert prosjekt som kjører migreringsskriptene mot en ekte Postgres-instans i CI.
- **Rute-/autorisasjonsverifikasjon som permanent test.** Selve endepunkttabellen i
  [`02-endpoints-and-controllers.md`](02-endpoints-and-controllers.md) ble verifisert ved å inspisere
  `EndpointDataSource` fra en kjørende host under utvikling, men denne sjekken er ikke gjort til en
  permanent test ennå.
- **`Persistence.Extensions.MigrateDatabase`** — krever en ekte databaseforbindelse, hører hjemme i
  integrasjonstester, ikke enhetstester.

---

Sjekk mot faktisk kode ved tvil.
