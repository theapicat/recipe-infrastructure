# CQRS og MediatR i `recipe-core-api`

---

Per 2026-09-19. Sjekk mot faktisk kode ved tvil.

## 1. Grunnmønster

MediatR brukes til all kommunikasjon mellom kontroller og forretningslogikk: kontroller oversetter HTTP
til et command/query-objekt, sender det via `IMediator.Send(...)`, og oversetter resultatet tilbake til
en HTTP-respons. Ingen forretningslogikk i kontrollere.

Registrering skjer via `services.AddMediatR(cfg => cfg.RegisterServicesFromAssemblyContaining<ApplicationMarker>())`
i `Application/Extensions/ApplicationExtensions.cs`, som skanner hele `Application`-assemblyen.

To ulike mønstre lever side om side under `Application/MediatR/`, avhengig av om logikken er
modellspesifikk eller generisk:

```
Application/MediatR/
├── Public/ContactForm/     ← konkret, hånd-skrevet (referansemønster)
└── Catalog/                ← generisk, delt av alle seks katalogmodeller
```

---

## 2. Konkret mønster: `Public/ContactForm/`

Referanseimplementasjonen for en vanlig, ikke-generisk command:

- `SendContactFormCommand` (`IRequest<bool>`) — rene inputdata fra kontrolleren.
- `SendContactFormCommandHandler` — validerer/logger, bygger `Contracts.Event.ContactFormSubmittedEvent`,
  publiserer den via `Application.Messaging.Interfaces.IEventPublisher` (se
  [`04-events-and-messaging.md`](04-events-and-messaging.md)).

Brukes som mal for fremtidige modellspesifikke handlers (oppskrifter, måltidsplan) som ikke passer inn i
det generiske katalogmønsteret under.

---

## 3. Generisk mønster: `Catalog/`

De seks adminstyrte katalogene (`IngredientCategory`, `Allergen`, `SearchKeyword`, `UnitType`, `Unit`,
`RecipeCategory`) er strukturelt identiske — `{Id, Name}` eller nært beslektet — og trenger nøyaktig de
samme fem operasjonene. I stedet for seks sett med nesten identisk handler-kode finnes ett generisk sett,
parametrisert over `<T>`:

| Type | Retning | Cache-oppførsel |
| --- | --- | --- |
| `GetAllCatalogQuery<T>` / `GetAllCatalogQueryHandler<T>` | Lesing | Cache-aside: sjekker cache først, henter fra `DbReader<T>` og fyller cachen ved miss. |
| `GetCatalogByIdQuery<T>` / `GetCatalogByIdQueryHandler<T>` | Lesing | Går alltid direkte til databasen — brukes til redigeringsskjema der data må være ferskt. |
| `InsertCatalogCommand<T>` / `InsertCatalogCommandHandler<T>` | Skriving | Skriver via `DbWriter<T>`, ugyldiggjør cachen. |
| `UpdateCatalogCommand<T>` / `UpdateCatalogCommandHandler<T>` | Skriving | Skriver via `DbWriter<T>`, ugyldiggjør cachen. |
| `DeleteCatalogCommand<T>` / `DeleteCatalogCommandHandler<T>` | Skriving | Sletter via `DbWriter<T>`, ugyldiggjør cachen, returnerer `bool` basert på antall berørte rader. |

`CatalogCacheKey.ForAll<T>()` (internal) bygger nøkkelen (`catalog:{typeof(T).Name}:all`) — samme
hjelpemetode brukes av både lese- og skrivesiden, slik at nøkkelformatet ikke kan drifte fra hverandre.

### Hvorfor cache-orkestreringen ligger i handleren, ikke i cache-tjenesten

`ICacheService` (se `Application/Caching/`) er bevisst holdt til rene primitiver — `Get`/`Set`/`Remove` —
uten noen `GetOrCreate`-metode som tar en factory. Første versjon hadde en slik metode, men det ble
reversert: en cache-tjeneste som kjenner til *hvordan* man henter data ved miss, blander ansvar. Nå gjør
`GetAllCatalogQueryHandler<T>` selv sjekk-null-så-hent-så-fyll-sekvensen.

### ⚠️ DI-registrering: ikke ekte åpne generiske handlers

MediatR sin assembly-scanning registrerer **ikke** automatisk en åpen generisk handler der både
forespørsel og respons er avledet fra samme delte typeparameter (som `GetAllCatalogQuery<T> :
IRequest<List<T>>` sammen med `GetAllCatalogQueryHandler<T>`). Dette ble verifisert eksperimentelt
2026-09-19: `.NET` sin DI-container krever samsvarende arity mellom åpen service-type og åpen
implementasjonstype, og en handler med kun én åpen typeparameter kan ikke registreres direkte mot
`IRequestHandler<,>` (to typeparametre).

Løsningen ligger i `Application/Extensions/CatalogExtensions.AddCatalogHandlers()`: for hver av de seks
katalogtypene lukkes hver av de fem handler-typene manuelt via `Type.MakeGenericType(...)` før
registrering. Nye katalogtyper legges til i ett array (`CatalogTypes`) i samme fil — ikke ved å skrive en
ny handler-klasse.

**⚠️ Namespace-kollisjon å passe på:** `Domain.Units.Unit` kolliderer med `MediatR.Unit` (MediatRs eget
"ingen respons"-resultat) i enhver fil som har `using` for begge namespacene. Løses med et alias
(`using DomainUnit = Domain.Units.Unit;`). Skjedde allerede én gang under utvikling, fanget av
kompilatoren.

---

## 4. Fremtidig: cache som pipeline behavior

Cache-sjekken er i dag skrevet eksplisitt i hver `GetAllCatalogQueryHandler<T>`. Når flere ulike
spørringstyper (ikke bare katalogmodellene) trenger samme cache-aside-mønster, er neste steg en generisk
`IPipelineBehavior<TRequest, TResponse>` merket med et markørgrensesnitt (`ICacheableQuery`), slik at
cache-logikken skrives én gang for hele MediatR-pipelinen i stedet for i hver handler. Ikke bygget ennå —
ingen nok variasjon i bruksmønsteret til å rettferdiggjøre det per denne datoen.

---

Sjekk mot faktisk kode ved tvil.
