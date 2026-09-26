# CQRS og MediatR i `recipe-core-api`

---

Per 2026-09-20. Sjekk mot faktisk kode ved tvil.

## 1. Grunnmønster

MediatR brukes til all kommunikasjon mellom kontroller og forretningslogikk: kontroller oversetter HTTP
til et command/query-objekt, sender det via `IMediator.Send(...)`, og oversetter resultatet tilbake til
en HTTP-respons. Ingen forretningslogikk i kontrollere.

Registrering skjer via `services.AddMediatR(cfg => cfg.RegisterServicesFromAssemblyContaining<ApplicationMarker>())`
i `Application/Extensions/ApplicationExtensions.cs`, som skanner hele `Application`-assemblyen og finner alle
vanlige (ikke-generiske) handlers automatisk.

Tre mønstre lever side om side under `Application/MediatR/`. Mappene speiler kontrollermappene i `API/Controllers/`
(`Public/`, `User/`, `Admin/`), med ett bevisst unntak: kode som brukes av *flere* tilganger ligger som søsken
til dem (`Catalog/`, `Ingredients/`), ikke under én av dem.

```
Application/MediatR/
├── Public/ContactForm/              ← konkret, håndskrevet (referansemønster)
├── Catalog/                         ← generisk, delt av alle katalogmodeller (§3)
├── Ingredients/                     ← delt lesing av ingredienser (søk)
├── Admin/Ingredients/               ← admin-skriving av ingredienser
├── Admin/UnconfirmedIngredients/    ← admin-køen: godkjenn / slå sammen / avslå
└── User/UnconfirmedIngredients/     ← brukerens egne ubekreftede ingredienser
```

Mappenavnene er bevisst i flertall (`Ingredients`, ikke `Ingredient`): et namespace `…Ingredient` ville skygget for
typen `Domain.Ingredients.Ingredient`.

---

## 2. Konkret mønster: `Public/ContactForm/`

Referanseimplementasjonen for en vanlig, ikke-generisk command:

- `SendContactFormCommand` (`IRequest<bool>`) — rene inputdata fra kontrolleren.
- `SendContactFormCommandHandler` — validerer/logger, bygger `Contracts.Events.UserActions.ContactFormSubmittedEvent`,
  publiserer den via `Application.Messaging.Interfaces.IEventPublisher` (se
  [`04-events-and-messaging.md`](04-events-and-messaging.md)).

---

## 3. Generisk mønster: `Catalog/`

De adminstyrte katalogene (`IngredientCategory`, `Allergen`, `SearchKeyword`, `UnitType`, `Unit`, `RecipeCategory`) er
strukturelt like og trenger de samme fem operasjonene. I stedet for ett sett handler-kode per modell finnes ett
generisk sett, parametrisert over modellen `T` og nøkkeltypen `TKey` (`Guid`; malen støtter også `string`).
`NutrientDefinition` (med enhet og gruppe nøstet inni) er en statisk, skrivebeskyttet katalog og får bare de to lesehandlerne (`AddGetAll`/`AddGetById`
i `CatalogExtensions`) — ingen Insert/Update/Delete-handler, ingen `DbWriter` og ingen skrivefunksjoner i SQL:

| Type | Retning | Oppførsel |
| --- | --- | --- |
| `GetAllCatalogQuery<T>` / `…Handler<T>` | Lesing | Cache-aside: sjekker cache, henter fra `DbReader<T>` og fyller cachen ved miss. |
| `GetCatalogByIdQuery<T, TKey>` / `…Handler<T, TKey>` | Lesing | Går alltid direkte til databasen — brukes til redigeringsskjema der data må være ferskt. |
| `InsertCatalogCommand<T, TKey>` / `…Handler<T, TKey>` | Skriving | Tildeler id (se under), skriver via `DbWriter<T>`, ugyldiggjør cachen, **returnerer id-en**. |
| `UpdateCatalogCommand<T>` / `…Handler<T>` | Skriving | Validerer (`Result`), skriver via `DbWriter<T>`, ugyldiggjør cachen. |
| `DeleteCatalogCommand<T, TKey>` / `…Handler<T, TKey>` | Skriving | Krever `T : IHasUsageMetadata`. Slår opp raden først og returnerer `Result`: `NotFound` (ukjent id), `Conflict` (systemrad eller `UsageCount > 0`), ellers sletter og ugyldiggjør cachen. |

Insert/Update/Delete returnerer `Result<TKey>`/`Result` (ikke rå `TKey`/`bool`) siden 2026-09-22 - se «Navnenormalisering og
-validering» under for hvorfor.

`CatalogCacheKey.ForAll<T>()` (internal) bygger nøkkelen (`catalog:{typeof(T).Name}:all`) — samme hjelper for lese-
og skriveside, slik at nøkkelformatet ikke kan drifte fra hverandre.

### Server-tildelte id-er: `IHasId<TKey>`

Modeller med primærnøkkel implementerer `Domain.IHasId<TKey>`. `InsertCatalogCommandHandler` tildeler
`Guid.CreateVersion7()` til alle `IHasId<Guid>`-modeller (uansett hva klienten sendte) og returnerer id-en, så
kontrolleren kan svare `201 Created` med `Location`. For `string`-nøkler tildeles ingenting — kalleren oppgir den
(ingen skrivbar katalog bruker dette i dag; `NutrientDefinition` har `string`-nøkkel, men er skrivebeskyttet). Derfor er `Id` ikke `required` på Guid-modellene (det ville krevd at
klienten sendte en id serveren likevel overskriver).

### Oppskrifter: `MediatR/User/Recipes/`

Håndskrevne handlers (ikke den generiske katalogmalen): `GetOwnRecipesQuery`, `GetOwnRecipeQuery`, `CreateRecipeCommand`,
`UpdateRecipeCommand`, `DeleteRecipeCommand`, `SetRecipeFavoriteCommand`, alle med `UserId` (fra tokenet) som første parameter og `Result`/
`Result<T>` som svar. `RecipeMapper` validerer (`Validate`) og bygger domenemodellen (`ToRecipe`: server-tildelte id-er, nummerering,
koketid = sum av steg-timerne, tittel normalisert). `RecipeLimits` samler grensene (`MaxPerUser` = 500 osv.).
`UnconfirmedIngredientCheck` sikrer at en linje bare bruker brukerens egen, uløste ubekreftede ingrediens. Opprett/oppdater leser
oppskriften tilbake fra databasen så svaret har ingrediensnavnene med. `GetRecipeNutritionQuery` henter rådata (`RecipeNutritionInput`: linjer,
porsjoner, næringsverdier) fra `IRecipeReader` og overlater regnestykket til `RecipeNutritionCalculator` — en ren, statisk klasse, så logikken (omregning til
gram, uspiselig del, kun stoffer med verdi) er enhetstestbar uten database.

### Navnenormalisering og -validering

Insert- og Update-handlerne kaller `CatalogValidation.ValidateAsync` (`Result.Invalid` ved feil) **før** `CatalogNormalization.Apply`
(som trimmer navnet og gjør det om til små bokstaver, og trimmer - men beholder store/små bokstaver på - enhetens forkortelse via
`NameNormalizer.Tidy`). `CatalogValidation` dispatcher på `T` akkurat som `CatalogNormalization` (samme mønster): tomt navn (flyttet hit fra
kontrolleren 2026-09-22, siden kontrolleren ikke skal inneholde forretningsregler) gjelder alle typer, og `Domain.Units.Unit` får i tillegg egne
regler som krever et oppslag mot enhetstype-katalogen (blank forkortelse, forholdstall ≤ 0, ukjent enhetstype, «antall»-enheter med annet
forholdstall enn 1 - se `Documentation/08-api-reference.md`). Databasen håndhever navnereglene i tillegg (unik indeks + `CHECK (name =
lower(name))`), så en kodesti som glemmer normalisering feiler høylytt i stedet for å lagre feil.

### Hvorfor cache-orkestreringen ligger i handleren, ikke i cache-tjenesten

`ICacheService` (se `Application/Caching/`) er bevisst holdt til rene primitiver — `Get`/`Set`/`Remove` —
uten noen `GetOrCreate`-metode som tar en factory: en cache-tjeneste som kjenner til *hvordan* man henter data
ved miss, blander ansvar. `GetAllCatalogQueryHandler<T>` gjør selv sjekk-null-så-hent-så-fyll-sekvensen.

### ⚠️ DI-registrering: ikke ekte åpne generiske handlers

MediatR sin assembly-scanning registrerer **ikke** automatisk en åpen generisk handler der både forespørsel og
respons er avledet fra samme delte typeparameter. Verifisert eksperimentelt: .NET sin DI-container krever
samsvarende arity mellom åpen service-type og åpen implementasjonstype.

Løsningen ligger i `Application/Extensions/CatalogExtensions.AddCatalogHandlers()`: for hver katalogtype (og dens
nøkkeltype) lukkes hver handler-type via `Type.MakeGenericType(...)` før registrering. Nye katalogtyper legges til i
ett array (`CatalogTypes`) — ikke ved å skrive en ny handler-klasse. Samme sted registreres to lese-only-tilfeller:
`GetAllCatalogQuery<IngredientListItem>` (den cachede lista) og `GetCatalogByIdQuery<Ingredient, Guid>`.

**⚠️ Namespace-kollisjon å passe på:** `Domain.Units.Unit` kolliderer med `MediatR.Unit` i enhver fil som har
`using` for begge. Løses med et alias (`using DomainUnit = Domain.Units.Unit;`).

---

## 4. `Result`-mønsteret for forventede forretningsfeil

Forventede feil (ikke funnet, feil status, grense nådd, ugyldig innhold) kastes ikke som unntak; de returneres som
`Application.Results.Result` / `Result<T>` med en `ResultStatus` (`Ok`, `NotFound`, `Conflict`, `Invalid`) og en
valgfri norsk feilmelding. Kontrolleren oversetter via `API/Extensions/ResultExtensions.ToActionResult(...)`:
`NotFound` → `404`, `Conflict` → `409`, `Invalid` → `400` (feil som `ProblemDetails`).

Databasefeil som ikke er forretningsregler (brudd på fremmednøkkel/unikhet) kastes av Npgsql og oversettes til `409`
av `API/ExceptionHandlers/PostgresExceptionHandler` — se [`02-endpoints-and-controllers.md`](02-endpoints-and-controllers.md).

---

## 5. Ingredienser (håndskrevet, ikke generisk)

- **Lesing:** `SearchIngredientsQuery`/`Handler` henter den cachede `IngredientListItem`-lista via
  `GetAllCatalogQuery<IngredientListItem>` (gjenbruker cache-aside-logikken via mediator, dupliserer den ikke) og
  filtrerer i minnet. Navnefilteret matcher også søkeordkatalogen (`GetAllCatalogQuery<SearchKeyword>`, cachet).
  Enkeltoppslag bruker den generiske `GetCatalogByIdQuery<Ingredient, Guid>` mot `IngredientReader`, som henter
  ingrediensen og alle barn i ett databasekall.
- **Skriving:** `Create`/`Update`/`DeleteIngredientCommand` under `Admin/Ingredients/`. Innholdet er en
  `IngredientRequest` **uten id-er**; `IngredientMapper.ToIngredient` tildeler UUIDv7 til ingrediensen og hvert barn
  og dedupliserer allergen-/søkeordkoblinger (sammensatt primærnøkkel). `IngredientMapper.Validate` fanger det
  databasen ikke gir en brukbar feil for (tomt navn, negative verdier). Skrivingen skjer i **én transaksjon** i
  `IngredientWriter` (se [`06-persistence-and-data-access.md`](06-persistence-and-data-access.md)), og alle skriv
  ugyldiggjør liste-cachen.

## 6. Ubekreftede ingredienser (håndskrevet, brukerstyrt)

Ikke cachet (brukerspesifikt og lite). Handlerne avhenger av `IUnconfirmedIngredientReader`/`Writer` (egne
grensesnitt i `Persistence/Interfaces/` — de trenger spørringer utover malen). Kjernereglene:

- **Eier-id kommer alltid inn som eksplisitt parameter** (`UserId` i kommandoen, satt av kontrolleren fra tokenet).
  `Application` kjenner aldri til `HttpContext`/`ClaimsPrincipal`. En annen brukers ingrediens gir `NotFound`,
  identisk med en id som ikke finnes.
- **Tilstandsmaskinen** (`NotRequested → Pending → Approved | Merged | Rejected`) håndheves både i handleren
  (tydelig `Conflict`-melding) og i databasefunksjonene (`WHERE review_status = …`), så et løp mellom to
  forespørsler ikke kan avgjøre samme rad to ganger.
- **Grenser** i `UnconfirmedIngredientLimits`: 100 per bruker, 10 ventende, navn ≤ 200 tegn.
- **Godkjenning** (`ApproveUnconfirmedIngredientCommand`) oppretter ingrediensen og avgjør forespørselen i én
  transaksjon via `IUnconfirmedIngredientWriter.ResolveAsync`, som også flytter oppskriftslinjer. Tid hentes fra
  `TimeProvider` (registrert som `TimeProvider.System`) så handlerne kan testes deterministisk.

---

## 7. Fremtidig: cache som pipeline behavior

Cache-sjekken er i dag skrevet eksplisitt i `GetAllCatalogQueryHandler<T>`. Hvis flere ulike spørringstyper trenger
samme cache-aside-mønster, er neste steg en generisk `IPipelineBehavior<TRequest, TResponse>` merket med et
markørgrensesnitt (`ICacheableQuery`). Ikke bygget — for lite variasjon i bruksmønsteret til å rettferdiggjøre det.

---

Sjekk mot faktisk kode ved tvil.
