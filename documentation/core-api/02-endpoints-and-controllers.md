# Endepunkter og kontrollere i `recipe-core-api`

---

Full oversikt over registrerte endepunkter per 2026-09-19, verifisert direkte mot ASP.NET Core sin
`EndpointDataSource` (ikke bare lest ut av kildekoden). Sjekk mot faktisk kode ved tvil.

## 1. Tilgangsnivåer

Tre basiskontrollere bærer rute-prefiks og tilgangskrav (`API/Controllers/*Controller.cs`), samme mønster
for alle: `[ApiController]` + `[Route]` + tilgangsattributt, ingen handlers selv.

| Basiskontroller | Rute-prefiks | Attributt | Brukes til |
| --- | --- | --- | --- |
| `PublicController` | `/api/public` | `[AllowAnonymous]` | Uautentiserte endepunkter — kontaktskjema, health. Sjelden brukt; de fleste funksjoner i appen krever innlogget bruker. |
| `UserController` | `/api/user` | `[Authorize]` | Enhver innlogget bruker (rolle `user` eller `admin`). |
| `AdminController` | `/api/admin` | `[Authorize(Roles = "admin")]` | Kun administratorer. |

**⚠️ Strukturelt unntak:** de generiske katalogkontrollerne (§3) arver *ikke* fra `UserController`/
`AdminController` — C# tillater bare én baseklasse, og de arver i stedet fra
`ReadCatalogController<T>`/`ReadWriteCatalogController<T>` (CQRS-formen). Hver konkret kontroller setter
derfor `[Route]`/`[Authorize(...)]` direkte på seg selv i stedet for å arve det. `PublicController` er
foreløpig den eneste tilgangsbasen som faktisk brukes som arv (av `ContactFormController`/`HealthController`).

Full autentiseringsprosedyre (JWT-validering, rollenavn, hvordan bruker-ID hentes) står i
[`05-authentication-and-authorization.md`](05-authentication-and-authorization.md).

---

## 2. `PublicControllers/`

**Rute-prefiks:** `/api/public`
**Autorisasjon:** Anonym
**Formål:** De få endepunktene som ikke krever innlogging.

| Metode | Endepunkt | Tilgang | Formål / Beskrivelse |
| --- | --- | --- | --- |
| POST | `/api/public/contact-form` | Anonym | Mottar kontaktskjema, publiserer `ContactFormSubmittedEvent`. |
| GET | `/api/public/health` | Anonym | Helsesjekk — returnerer tjenestenavn, miljø og tidsstempel. |

---

## 3. Katalogkontrollere (generisk mal)

De seks adminstyrte katalogene (`IngredientCategory`, `Allergen`, `SearchKeyword`, `UnitType`, `Unit`,
`RecipeCategory`) deler samme generiske kontrollerpar — se
[`03-cqrs-and-mediatr.md`](03-cqrs-and-mediatr.md) for hvorfor og hvordan. Konkret kontroller er bare en
`[Route]`/`[Authorize]`-attributt og én linje arv; all logikk ligger i de to generiske basene.

### `UserControllers/Catalog/` — lesing

**Rute-prefiks:** `/api/user/<ressurs>`
**Autorisasjon:** Autentisert (`[Authorize]`, ingen rollekrav)
**Formål:** Alle innloggede brukere kan lese katalogene (f.eks. for å velge ingrediens/allergen/enhet når
de lager en oppskrift).

| Metode | Endepunkt | Tilgang | Formål / Beskrivelse |
| --- | --- | --- | --- |
| GET | `/api/user/ingredient-categories` | Autentisert | Hele katalogen (cachet). |
| GET | `/api/user/ingredient-categories/{id:guid}` | Autentisert | Én rad, alltid fersk fra databasen. |
| GET | `/api/user/allergens` | Autentisert | Hele katalogen (cachet). |
| GET | `/api/user/allergens/{id:guid}` | Autentisert | Én rad, alltid fersk fra databasen. |
| GET | `/api/user/search-keywords` | Autentisert | Hele katalogen (cachet). |
| GET | `/api/user/search-keywords/{id:guid}` | Autentisert | Én rad, alltid fersk fra databasen. |
| GET | `/api/user/unit-types` | Autentisert | Hele katalogen (cachet). |
| GET | `/api/user/unit-types/{id:guid}` | Autentisert | Én rad, alltid fersk fra databasen. |
| GET | `/api/user/units` | Autentisert | Hele katalogen (cachet). |
| GET | `/api/user/units/{id:guid}` | Autentisert | Én rad, alltid fersk fra databasen. |
| GET | `/api/user/recipe-categories` | Autentisert | Hele katalogen (cachet). |
| GET | `/api/user/recipe-categories/{id:guid}` | Autentisert | Én rad, alltid fersk fra databasen. |

### `AdminControllers/Catalog/` — full CRUD

**Rute-prefiks:** `/api/admin/<ressurs>`
**Autorisasjon:** `admin`-rolle (`[Authorize(Roles = "admin")]`)
**Formål:** Administrasjon av katalogene. Samme seks ressurser som over, pluss skriveoperasjoner.

| Metode | Endepunkt | Tilgang | Formål / Beskrivelse |
| --- | --- | --- | --- |
| GET | `/api/admin/<ressurs>` | `admin` | Hele katalogen (cachet). |
| GET | `/api/admin/<ressurs>/{id:guid}` | `admin` | Én rad, alltid fersk — brukes til redigeringsskjema. |
| POST | `/api/admin/<ressurs>` | `admin` | Oppretter ny rad, ugyldiggjør cachen. |
| PUT | `/api/admin/<ressurs>` | `admin` | Oppdaterer eksisterende rad (hel entitet i body, inkl. `Id`), ugyldiggjør cachen. |
| DELETE | `/api/admin/<ressurs>/{id:guid}` | `admin` | Sletter rad, ugyldiggjør cachen. Returnerer `204` uansett om raden fantes. |

`<ressurs>` er en av: `ingredient-categories`, `allergens`, `search-keywords`, `unit-types`, `units`,
`recipe-categories`. Alle tolv kontrollerne (seks `User*`, seks `Admin*`) er verifisert med reell
route-inspeksjon 2026-09-19 — se `Tests/API/Controllers/`.

**Åpne spørsmål:** ingen dedikert håndtering ennå for "ressurs finnes ikke" vs. "ressurs tilhører en annen
bruker" — katalogene er delte/adminstyrte så dette gjelder ikke dem, men blir relevant når
oppskrift-endepunkter bygges (se [`05-authentication-and-authorization.md`](05-authentication-and-authorization.md)).

---

## 4. Ikke bygget ennå

Oppskrifter, måltidsplan, handleliste, og `nutrient_definition`/`ingredient`/`unconfirmed_ingredient`
(katalogmodeller som trenger mer enn den enkle 5-operasjons-malen). Se `todo.md` i repo-roten for status.
