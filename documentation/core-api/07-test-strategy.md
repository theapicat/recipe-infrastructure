# Teststrategi i `recipe-core-api`

---

Per 2026-09-20. Sjekk mot faktisk kode ved tvil.

## 1. Oppsett

To testprosjekter: `Tests/Tests.csproj` (xUnit, enhetstester uten eksterne avhengigheter) og `IntegrationTests/IntegrationTests.csproj` (mot ekte Postgres, se §3). Enhetstestprosjektet har referanse til `API`, `Application`, `Contracts`, `Domain`
og `Persistence`. Mappestrukturen speiler kildekoden 1:1 (samme regel som ellers i løsningen: namespace
skal alltid matche mappebanen).

```bash
dotnet test Tests/Tests.csproj
```

291 enhetstester, alle grønne (kjørt 2026-09-24), ingen ekstern avhengighet (ingen Postgres/RabbitMQ trengs for å kjøre dem).

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
| Generiske katalog-handlers (`GetAll`/`GetById`/`Insert`/`Update`/`Delete`) | `Tests/Application/MediatR/Catalog/` | Cache-treff kaller aldri `DbReader<T>`; cache-miss henter fra reader og fyller cachen; skriveoperasjoner ugyldiggjør cachen; `Insert` nullstiller `IsSystem`/`UsageCount` uansett hva klienten sendte; `Delete` (nå `Result`, ikke `bool`) gir `404` for ukjent id, `409` for en systemrad eller en rad i bruk (med antallet i meldingen), ellers sletter og ugyldiggjør cachen. |
| Katalogvalidering | `Tests/Application/MediatR/Catalog/CatalogValidationTests` | Blank navn (alle katalogtyper); enhet: blank forkortelse, forholdstall ≤ 0, ukjent enhetstype, «antall» med forholdstall ≠ 1. |
| `CatalogExtensions.AddCatalogHandlers()` | `Tests/Application/Extensions/` | Regresjonstest for et reelt problem oppdaget under utvikling — at alle fem handler-typer faktisk blir registrert for hver av de seks skrivbare katalogtypene, og at næringsstoffene kun får lesehandlerne (næringsgrupper har ingen egne handlers) (se [`03-cqrs-and-mediatr.md`](03-cqrs-and-mediatr.md) for hvorfor dette ikke skjer automatisk). |
| `MassTransitEventPublisher` | `Tests/Application/Messaging/` | Delegerer korrekt til `IPublishEndpoint.Publish`. |
| `SendContactFormCommandHandler` | `Tests/Application/MediatR/Public/ContactForm/` | Bygger og publiserer riktig hendelse, returnerer `true`. |
| Kontosletting: forbrukere + handler | `Tests/Application/Messaging/Consumers/`, `Tests/Application/MediatR/Users/` | Hver av de fire `IConsumer<T>` sender `DeleteAllUserDataCommand` videre med riktig `UserId` fra hendelsen; `DeleteAllUserDataCommandHandler` kaller `IUserDataEraser` med riktig id. |
| `ReadCatalogController<T>`/`ReadWriteCatalogController<T>` | `Tests/API/Controllers/` | Riktig HTTP-resultat (`Ok`/`NotFound`/`Created` med server-tildelt id/`BadRequest` uten id på PUT eller med tomt navn/`NoContent`) basert på hva mediator returnerer, også for tekstnøkler (testet med en lokal testentitet). |
| `JwtAuthenticationExtensions` | `Tests/API/Extensions/` | Kaster `InvalidOperationException` når `Jwt:Key`/`Issuer`/`Audience` mangler; lykkes når alt er satt. |
| Server-tildelte id-er (`InsertCatalogCommandHandler`) | `Tests/Application/MediatR/Catalog/` | Guid-nøkler får en ny UUIDv7 (klientens id ignoreres); tekstnøkler beholdes. |
| Navnenormalisering | `Tests/Application/Naming/`, `Tests/Application/MediatR/Catalog/`, `…/User/…` | `NameNormalizer` (trim, mellomrom, små bokstaver, æøå; `Tidy` beholder store/små bokstaver for enhetsforkortelser); Insert/Update-handlerne lagrer navn og enhetsforkortelse med små bokstaver; ubekreftet ingrediens avvises (`409`) når en offisiell ingrediens har samme navn. Controlleren avviser tomt navn med `400`. |
| Ingrediens: mapping og validering | `Tests/Application/MediatR/Admin/Ingredients/` | `IngredientMapper` tildeler id til ingrediensen og alle barn og dedupliserer koblinger; validering av tomt navn/negative verdier/desimalgrenser (`numeric`-overflow)/duplikat næringsstoff/ugyldig kilde-URL/verifisert uten næring; `ValidateOfficialLock` (kildedata låst på offisielle ingredienser, unntatt tillatte felt, navn med bare endret store/små bokstaver, og `allergensReviewed` — fritt redigerbar selv om offisiell); `IngredientForeignKeyValidator` (ukjent kategori/enhetstype/enhet/allergen/søkeord/næringsstoff, feil enhetstype på standardenhet, dupliserte porsjonsenheter, variant-selvreferanse/-løkke); create/update/delete-handlere (404, `409` samtidighet/i-bruk, `createdAt` satt ved opprettelse og videreført uendret ved oppdatering, cache-invalidering). |
| Ingrediens: søk | `Tests/Application/MediatR/Ingredients/` | Filtrering i minnet: navn (også søkeord), kategori, allergen inkluder/ekskluder, søkeord, `isOfficial`, `isVariant`, kombinasjon med OG. |
| Ubekreftede ingredienser | `Tests/Application/MediatR/User/…` og `…/Admin/UnconfirmedIngredients/` | Grenser (totalt/ventende), tilstandsmaskinen (kun `Pending` kan avgjøres, kun `NotRequested` kan endres), en annen brukers rad gir samme `NotFound` som en manglende, approve/merge/reject. |
| Eier fra token | `Tests/API/Controllers/UnconfirmedIngredientControllerTests`, `Tests/API/Extensions/ClaimsPrincipalExtensionsTests` | Bruker-id leses fra `NameIdentifier` og sendes inn i kommandoen; aldri fra body. |
| Feilmapping | `Tests/API/Extensions/ResultExtensionsTests`, `Tests/API/ExceptionHandlers/` | `Result` → 404/409/400; Postgres FK-/unikhetsbrudd → 409, andre feil ignoreres. |
| `NutrientDefinitionRow` | `Tests/Persistence/Implementation/` | Den flate raden bygges om til `NutrientDefinition` med gruppen og evt. overordnet gruppe nøstet inni. |
| Næringsberegning | `Tests/Application/MediatR/User/Recipes/RecipeNutritionCalculatorTests`, `GetRecipeNutritionQueryHandlerTests` | Per 100 g skaleres på gram; per porsjon; kun stoffer med verdi (ingen nuller), katalog-rekkefølge; uspiselig del trekkes fra kun for vektenheter, ikke for porsjonsvekter; porsjon foretrekkes; volum skaleres via største volumporsjon; `ToTaste`/`Unconfirmed`/`NoConversion` rapporteres; kJ utelates uten data. |
| Oppskrifter | `Tests/Application/MediatR/User/Recipes/`, `Tests/API/Controllers/UserRecipeControllerTests`, `Tests/Persistence/Implementation/RecipeRowTests` | `RecipeMapper` (validering: tittel/beskrivelse, minst ett steg og én ingrediens, én ingrediens-id per linje, mengde 0 = «etter smak», bilde-url; bygging: nummerering, koketid, normalisert tittel); opprett (grense 500, Manual-kilde, eier fra tokenet, ubekreftet ingrediens må være egen og uløst); oppdatering (skrapet → `isEditedFromSource`, låst type/url, behold favoritt/`createdAt`); hent/slett/favoritt gir `NotFound` når ingenting matcher; controlleren bruker bruker-id fra tokenet. *Skrevet 2026-09-20, kjøres og telles først etter gjennomgang.* |
| `DateTimeOffsetTypeHandler` | `Tests/Persistence/Implementation/` | `DateTime` fra Npgsql tolkes som UTC; skriving sender alltid UTC. |

---

## 3. Hva som ikke er dekket her

**Endepunkttester ligger utenfor dette repoet.** Brukeren har en uavhengig, omfattende endepunkttestpakke. Denne
pakken tester derfor kun klassenes funksjonalitet, og skal ikke utvides med endepunkt- eller kanttilfelletester.

**Verifisert utenfor enhetstestene:**

- **Integrasjonstester mot ekte Postgres — bygget 2026-09-24** i eget prosjekt `IntegrationTests/` (Testcontainers, `postgres:16-alpine`,
  krever Docker, kjøres separat: `dotnet test IntegrationTests/IntegrationTests.csproj`, 14 tester). Fixturen migrerer og seeder databasen
  med DbUp akkurat som API-et. Dekker: seedet (antall, unike navn, alt offisielt, standardenheter av riktig type og omregnbare, egg = stykk,
  derivater kopierer basens tall/kilde, synonymord koblet), katalogene (`isSystem`/`usageCount`, klienten kan ikke gjøre en rad til systemrad),
  ingrediensskriving (`is_official`/`created_at` endres aldri ved oppdatering, `allergens_reviewed` lagres, `usage_count` teller varianter, revisjonsfeltene lagres og listen viser antall næringsverdier/porsjoner), unik oppskriftstittel per bruker, og
  `UserDataEraser` (sletter riktig brukers oppskrifter og ubekreftede ingredienser i riktig rekkefølge, andre brukere urørt). Ikke dekket
  ennå: øvrige Reader/Writer-SQL, `RecipeReader`-næringsspørringene og `resolve_unconfirmed_ingredient`.
- **Ingrediens- og enhetsvalidering (B1-B6)** er i tillegg kjørt ende-til-ende mot det ekte API-et og en migrert scratch-database (2026-09-22, 22 kontroller, opprydding etterpå):
  offisiell-lås, samtidighetskontroll, verifisert-krever-næring, alle fremmednøkkel-meldingene, variantkjede-løkke, enhetsvalidering.
- **`isSystem`/`usageCount`/`createdAt`/`allergensReviewed`** er kjørt ende-til-ende mot det ekte API-et og en fersk scratch-database
  (2026-09-22, opprydding etterpå): seed-rader har `isSystem: true`/`usageCount` beregnet riktig (kategori og enhet mot faktiske
  seed-ingredienser); sletting av en systemrad → `409`, av en ukjent id → `404`; insert-forsøk på å sette `isSystem`/`usageCount` fra
  klienten blir ignorert i både lagret rad og `201`-svaret; en opprettet variant løfter basisingrediensens `usageCount` til 1 og
  blokkerer sletting, fjerning av varianten senker den tilbake til 0; `allergensReviewed` kan endres på en offisiell ingrediens uten
  at `ValidateOfficialLock` slår ut, mens `createdAt` er uendret og `updatedAt` oppdatert etterpå.
- **Kontosletting-forbrukerne** er kjørt ende-til-ende mot det **ekte delte dev-RabbitMQ-oppsettet** (2026-09-23, ikke en
  engangs-broker - dette er innkommende tjeneste-til-tjeneste-kobling, må testes mot samme infrastruktur som
  `recipe-notification-service` faktisk bruker): en instans uten eksplisitt `Endpoint`-navn viste seg som forbruker #2 på
  `recipe-notification-service` sin ekte `AccountDeletedByUser`-kø (bekreftet via RabbitMQ sitt management-API) - rettet med et
  eget `CoreApi-`-prefikset kønavn per forbruker, verifisert på nytt (hver kø 1 forbruker igjen). Deretter publisert en ekte
  MassTransit-innpakket testmelding på den delte utvekslingen: begge køene mottok sin egen kopi (fan-out), handleren logget
  riktig (0 oppskrifter/0 ubekreftede ingredienser for testbrukeren), og ingenting havnet i `recipe-notification-service` sin
  feilkø. Scratch-Postgres og scratch-API-prosessen ble ryddet opp; de nye `CoreApi-*`-køene ble stående (tomme, ufarlige -
  det er de faktiske produksjonskønavnene nå som koden finnes, ikke testrester).
- **Oppskrifter og næring** er i tillegg kjørt ende-til-ende mot det ekte API-et og en migrert dev-database (2026-09-20, 37 + 1 kontroller, opprydding etterpå): opprett/hent/
  endre/favoritt/slett, eierskap (annen bruker → `404`), validering, ubekreftet ingrediens, og næringsberegningen sammenlignet med utregning for hånd (porsjonsvekt, uspiselig del for vektenheter,
  volumskalering, `ToTaste`/`Unconfirmed`/`NoConversion`) — ikke en permanent test.
- **Seed-skriptene** (`SeedData/`) er kjørt mot en tom Postgres (engangs-container og dev-databasen, 2026-09-20) med kontroll av
  antall rader, UUIDv7-id-er og at `CHECK`/unikhetsreglene godtar dem — ikke en permanent test. Hører hjemme i de
  samme integrasjonstestene som SQL-funksjonene.
- **`Persistence.Extensions.MigrateDatabase`** — krever en ekte databaseforbindelse, hører hjemme i
  integrasjonstester, ikke enhetstester.

---

Sjekk mot faktisk kode ved tvil.
