# Endepunkter og kontrollere i `recipe-core-api`

---

Full oversikt over registrerte endepunkter per 2026-09-20 (71 stk: 14 brukerlesing av kataloger — seks vanlige, samt
næringsstoffer —, 30 admin-CRUD på seks kataloger, 7 ingrediens, 11 ubekreftet ingrediens, 7 oppskrift, 2 offentlige).
Antallet ble sist verifisert direkte mot ASP.NET Core sin `EndpointDataSource` (da 69, før næringsstoffene ble gjort
skrivebeskyttet), og arbeidsflytene (ikke oppskriftene ennå) er kjørt mot ekte Postgres. Sjekk mot faktisk kode ved tvil. **Forespørsel og svar (JSON) for hvert endepunkt, feilformat og grenser står i
[`08-api-reference.md`](08-api-reference.md).**

## 1. Tilgangsnivåer

Tre basiskontrollere bærer rute-prefiks og tilgangskrav (`API/Controllers/*Controller.cs`), samme mønster
for alle: `[ApiController]` + `[Route]` + tilgangsattributt, ingen handlers selv.

| Basiskontroller | Rute-prefiks | Attributt | Brukes til |
| --- | --- | --- | --- |
| `PublicController` | `/api/public` | `[AllowAnonymous]` | Uautentiserte endepunkter — kontaktskjema, health. Sjelden brukt; de fleste funksjoner i appen krever innlogget bruker. |
| `UserController` | `/api/user` | `[Authorize]` | Enhver innlogget bruker (rolle `user` eller `admin`). |
| `AdminController` | `/api/admin` | `[Authorize(Roles = "admin")]` | Kun administratorer. |

To kontrollertyper finnes:

- **Håndskrevne** kontrollere (ingrediens, ubekreftet ingrediens, kontaktskjema, health) arver fra en av
  tilgangsbasene over og legger handlingsrutene relativt til prefikset (`[HttpGet("ingredients")]`).
- **Generiske katalogkontrollere** (§3) arver *ikke* fra `UserController`/`AdminController` — C# tillater bare én
  baseklasse, og de arver i stedet fra `ReadCatalogController<T, TKey>`/`ReadWriteCatalogController<T, TKey>`
  (CQRS-formen). Hver konkret kontroller setter derfor `[Route]`/`[Authorize(...)]` direkte på seg selv.

Full autentiseringsprosedyre står i [`05-authentication-and-authorization.md`](05-authentication-and-authorization.md).

### Felles konvensjoner

- **Id-er tildeles alltid av serveren** (`Guid.CreateVersion7()`), og alle opprettelser returnerer `201 Created`
  med `Location`-header og den opprettede ressursen (inkl. id) i kroppen. Klientens eventuelle `id` ignoreres.
  Unntak: `nutrient-definitions`, som er skrivebeskyttet (se §3) og har Matvaretabellens tekstkode som id.
- **Navn lagres alltid med små bokstaver** (kataloger, søkeord, ingredienser, enhetsforkortelser). Serveren trimmer,
  slår sammen mellomrom og gjør om til små bokstaver før skriving (`Application.Naming.NameNormalizer`) — også ved
  søk. Frontend gjør om til stor forbokstav ved visning. Navn må være unike per katalog (unik indeks + `CHECK` i
  databasen): en duplikat gir `409`, et tomt navn gir `400`. Unntak: næringsstoffnavn (statiske), enhetsforkortelser
  (symboler som `µg`, `mg-ATE` — trimmes, men beholder store/små bokstaver; unike uavhengig av store/små) og fritekst i
  oppskrifter (beskrivelse, steg, notat).
- **Statuskoder for feil:** `400` ugyldig innhold, `404` ikke funnet, `409` konflikt — enten en forretningsregel
  (feil status, grense nådd) eller et databasebrudd på fremmednøkkel/unikhet (raden er i bruk, peker på noe som
  ikke finnes, eller finnes fra før). Feil returneres som `ProblemDetails`.
- **Enum-verdier** (f.eks. `reviewStatus`) serialiseres som tekst (`"Pending"`), ikke tall.
- **Rute-id** for `Guid`-ressurser er `{id:guid}` på håndskrevne kontrollere og `{id}` på de generiske (nøkkeltypen
  varierer); en ugyldig id gir `400` på de generiske og `404` på de håndskrevne.

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

Seks adminstyrte kataloger deler samme generiske kontrollerpar (og næringsstoffene har kun lesing) — se
[`03-cqrs-and-mediatr.md`](03-cqrs-and-mediatr.md) for hvorfor og hvordan. Konkret kontroller er bare en
`[Route]`/`[Authorize]`-attributt og én linje arv; all logikk ligger i de to generiske basene.

`<ressurs>` er en av: `ingredient-categories`, `allergens`, `search-keywords`, `unit-types`, `units` og
`recipe-categories` (Guid-nøkkel). `nutrient-definitions` (tekstnøkkel) finnes bare som brukerlesing, se under.

### `UserControllers/Catalog/` — lesing

**Rute-prefiks:** `/api/user/<ressurs>`
**Autorisasjon:** Autentisert (`[Authorize]`, ingen rollekrav)
**Formål:** Alle innloggede brukere kan lese katalogene (f.eks. for å velge allergen/enhet når de lager en oppskrift).

| Metode | Endepunkt | Tilgang | Formål / Beskrivelse |
| --- | --- | --- | --- |
| GET | `/api/user/<ressurs>` | Autentisert | Hele katalogen (cachet). |
| GET | `/api/user/<ressurs>/{id}` | Autentisert | Én rad, alltid fersk fra databasen. |

**`nutrient-definitions` er en statisk, skrivebeskyttet katalog** — fylles kun av seed-data, det finnes ingen
skrive-endepunkter (og ingen admin-kontroller; admin leser via `/api/user/nutrient-definitions` som alle innloggede kan).
Bare lesing: `GET` liste og `GET {id}`. Listen er **flat**, sortert på `sortOrder` 1–57 (gruppe for gruppe, dybde-først).

**Enhet og gruppe er nøstet i næringsstoffet** — det finnes ingen egne endepunkter, Reader eller Writer for dem; de leses bare
som en del av et stoff:
- **Enhet:** `unitId` (Guid, fremmednøkkel til enhetstabellen), `unit` (forkortelsen: `g`, `mg`, `µg`, `µg RAE` ...) og
  `unitTypeId` (enhetstypen, alle er `vekt`). Enhetens `baseUnitRatio` (fra `/api/user/units`) brukes til å omregne/summere
  næring i en oppskrift.
- **Gruppe:** `group` = `{ id (Guid), name, sortOrder, parentGroup }` der `parentGroup` (samme form, uten egen `parentGroup`)
  er satt for undergrupper. Hovedgrupper: `fett`, `karbohydrat`, `protein`, `vitaminer`, `mineraler`, `sporstoffer`, `annet`;
  undergrupper: `mettede fettsyrer`, `enumettede fettsyrer`, `flerumettede fettsyrer` (under fett) og `vitamin a` … `vitamin e`
  (under vitaminer). Det finnes ingen `parentId` på stoffene — hierarkiet ligger i gruppene. Klienten bygger visningen
  (overordnet ↔ dypere) ved å gruppere stoffene på `group`. Stoffer direkte i en hovedgruppe vises før undergruppene;
  **første stoff i en undergruppe er summen** for gruppen (`Mettet`, `Enumet`, `Flerum`, `Vit A`), resten er delverdiene.

Id-en (tekstkoden, f.eks. `Vit C`) kan inneholde mellomrom og tegn som `+` og `:` og må URL-enkodes i stien.
Næringsstoffnavnene beholder kildens store/små bokstaver (NaCl, EPA). Verdiene per ingrediens (`nutrientValues`) er
det admin redigerer, via ingrediensen.

### `AdminControllers/Catalog/` — full CRUD

**Rute-prefiks:** `/api/admin/<ressurs>`
**Autorisasjon:** `admin`-rolle (`[Authorize(Roles = "admin")]`)
**Formål:** Administrasjon av katalogene (unntatt næringsstoffene, som er skrivebeskyttet).

| Metode | Endepunkt | Tilgang | Formål / Beskrivelse |
| --- | --- | --- | --- |
| GET | `/api/admin/<ressurs>` | `admin` | Hele katalogen (cachet). |
| GET | `/api/admin/<ressurs>/{id}` | `admin` | Én rad, alltid fersk — brukes til redigeringsskjema. |
| POST | `/api/admin/<ressurs>` | `admin` | Oppretter rad → `201` med raden (server-tildelt id), ugyldiggjør cachen. |
| PUT | `/api/admin/<ressurs>` | `admin` | Oppdaterer (hel entitet i body, `id` påkrevd → ellers `400`), ugyldiggjør cachen. |
| DELETE | `/api/admin/<ressurs>/{id}` | `admin` | Sletter, ugyldiggjør cachen. `204`; `409` hvis raden er i bruk. |

---

## 4. Ingredienser (`UserControllers/Ingredients/`, `AdminControllers/Ingredients/`)

Ingrediensen er den tunge modellen (næringsverdier, porsjoner, allergen- og nøkkelordkoblinger), så den følger
ikke den generiske malen for skriving. Lesing er delt mellom brukere og admin.

**Lesing (begge tilganger):** `GET /api/{user|admin}/ingredients` søker i en **cachet lettvekts-liste**
(`IngredientListItem`, ~2000 rader) filtrert i minnet; `GET .../ingredients/{id}` gir hele ingrediensen med barn,
alltid fersk fra databasen.

| Query-parameter | Betydning |
| --- | --- |
| `name` | Delvis treff, uavhengig av store/små bokstaver, mot ingrediensnavn **og** søkeord (`SearchKeyword`). |
| `categoryId` | Kun denne kategorien. |
| `allergenId` | Kun ingredienser som **inneholder** allergenet. |
| `excludeAllergenId` | Kan gjentas. Utelater ingredienser som inneholder noen av dem (kostholds-/sikkerhetsfilter). |
| `searchKeywordId` | Kun ingredienser med dette søkeordet. |

Filtrene kombineres med OG. Uten filter returneres hele lista. `IngredientListItem` har `isVerified`,
`variantOfIngredientId` og id-arrays for allergener/søkeord, slik at klienten kan filtrere og gruppere uten å
hente de tunge modellene.

**Skriving (kun admin):**

| Metode | Endepunkt | Tilgang | Formål / Beskrivelse |
| --- | --- | --- | --- |
| POST | `/api/admin/ingredients` | `admin` | Oppretter ingrediens med alle barn i én transaksjon. Body er `IngredientRequest` **uten id-er**; svaret (`201`) er hele ingrediensen med tildelte id-er. |
| PUT | `/api/admin/ingredients/{id:guid}` | `admin` | Erstatter ingrediensen og alle barn (barna får nye id-er). `404` hvis den ikke finnes. |
| DELETE | `/api/admin/ingredients/{id:guid}` | `admin` | Sletter (barna følger med). `404` hvis den ikke finnes, `409` hvis den er i bruk (oppskrift, variant eller ubekreftet ingrediens). |

`IngredientRequest`: `name`, `categoryId`, `primaryUnitTypeId`, `defaultUnitId`, `energyKcal` (påkrevd);
`energyKj`, `ediblePartPercent`, `sourceId`, `sourceUrl`, `variantOfIngredientId`, `isVerified`, `allergenIds[]`,
`searchKeywordIds[]`, `nutrientValues[{nutrientDefinitionId, quantity, sourceId?}]`, `portions[{unitId, gramsPerPortion}]`.

---

## 5. Ubekreftede ingredienser

En bruker som ikke finner en ingrediens i katalogen lager en **privat** ubekreftet ingrediens, og kan be admin om
å ta den inn i den offisielle katalogen. Livssyklus (`reviewStatus`):

```
NotRequested ──(bruker ber om vurdering)──> Pending ──> Approved   admin oppretter ny offisiell ingrediens
                                                    ├─> Merged     admin kobler til en eksisterende ingrediens
                                                    └─> Rejected   admin avslår (terminal), valgfri begrunnelse
```

`Approved` og `Merged` betyr at ingrediensen er (eller er koblet til) en offisiell ingrediens tilgjengelig for
alle — brukeren «eier» den ikke lenger, og alle oppskriftslinjer som pekte på den flyttes til den offisielle i
samme databasetransaksjon. Raden beholdes som historikk (`resolvedIngredientId`, `reviewedAt`,
`rejectionReason`) slik at brukeren kan se utfallet. `Rejected` forblir en privat ingrediens hos brukeren.

### `UserControllers/UnconfirmedIngredients/`

**Rute-prefiks:** `/api/user/unconfirmed-ingredients`
**Autorisasjon:** Autentisert. Alt filtreres på bruker-id fra tokenet — en annen brukers ingrediens gir samme
`404` som en id som ikke finnes.
**Formål:** Brukerens egne ubekreftede ingredienser.

| Metode | Endepunkt | Tilgang | Formål / Beskrivelse |
| --- | --- | --- | --- |
| GET | `/api/user/unconfirmed-ingredients` | Autentisert | Egne ingredienser, alle statuser, nyeste først. |
| GET | `/api/user/unconfirmed-ingredients/{id:guid}` | Autentisert | Én egen ingrediens. |
| POST | `/api/user/unconfirmed-ingredients` | Autentisert | Body `{name, requestReview}` → `201`. `requestReview: true` gir status `Pending` direkte. |
| PUT | `/api/user/unconfirmed-ingredients/{id:guid}` | Autentisert | Endrer navn. Kun mens status er `NotRequested` (ellers `409`). |
| POST | `/api/user/unconfirmed-ingredients/{id:guid}/request-review` | Autentisert | `NotRequested` → `Pending`. |
| DELETE | `/api/user/unconfirmed-ingredients/{id:guid}` | Autentisert | Sletter egen (uansett status). `409` hvis en oppskrift bruker den. |

**Grenser mot misbruk** (`UnconfirmedIngredientLimits`): maks **100** egne ingredienser per bruker, maks **10**
ventende forespørsler om gangen, navn 1–200 tegn. Overskridelse gir `409`.

### `AdminControllers/UnconfirmedIngredients/`

**Rute-prefiks:** `/api/admin/unconfirmed-ingredients`
**Autorisasjon:** `admin`-rolle
**Formål:** Admin-køen og de tre utfallene.

| Metode | Endepunkt | Tilgang | Formål / Beskrivelse |
| --- | --- | --- | --- |
| GET | `/api/admin/unconfirmed-ingredients` | `admin` | Køen. Uten parametre: kun `Pending`. `?status=Rejected` filtrerer; `?all=true` gir alle. Eldste først. |
| GET | `/api/admin/unconfirmed-ingredients/{id:guid}` | `admin` | Én forespørsel. |
| POST | `/api/admin/unconfirmed-ingredients/{id:guid}/approve` | `admin` | Body er `IngredientRequest` (se §4). Oppretter ny offisiell ingrediens og avgjør som `Approved`. Sett `variantOfIngredientId` for å godkjenne som variant av en annen ingrediens (klienten forhåndsutfyller næringsdata fra basen — serveren kopierer ikke selv). Svar: den nye ingrediensen. |
| POST | `/api/admin/unconfirmed-ingredients/{id:guid}/merge` | `admin` | Body `{ingredientId}`. Ingen ny ingrediens; oppskriftslinjer flyttes til den eksisterende, status `Merged`. `400` hvis ingrediensen ikke finnes. |
| POST | `/api/admin/unconfirmed-ingredients/{id:guid}/reject` | `admin` | Body `{reason?}`. Status `Rejected`. |

Bare `Pending` kan avgjøres; ellers `409`. Feilaktige id-er i `approve`/`merge` (kategori, enhet, basisingrediens
…) gir `409` fra databasens fremmednøkler.

---

## 6. Oppskrifter (`UserControllers/Recipes/`)

**Rute-prefiks:** `/api/user/recipes` · **Autorisasjon:** Autentisert. Oppskrifter er strengt brukereide: eier kommer alltid fra
tokenet (aldri fra body/rute), alle spørringer filtrerer på eier, og en annen brukers oppskrift gir samme `404` som en id som ikke
finnes. Admin har ingen tilgang til andres oppskrifter.

**Bare selve oppskriften er en ressurs.** Steg, ingredienslinjer og kilde er en del av oppskriften — de leses og skrives sammen
med den og har ingen egne endepunkter (koketiden avledes av stegene, så helheten må skrives samlet).

| Metode | Endepunkt | Tilgang | Formål / Beskrivelse |
| --- | --- | --- | --- |
| GET | `/api/user/recipes` | Autentisert | **Hele** lista til brukeren som lettvekts `RecipeListItem` (id, tittel, bilde, kategori, koketid, porsjoner, favoritt), sortert på tittel. Ingen paginering og ingen filtre: klienten laster lista én gang og filtrerer/søker selv (tittel, kategori, favoritt). Begrenset av maks 500 oppskrifter. |
| GET | `/api/user/recipes/{id:guid}` | Autentisert | Hele oppskriften med steg og ingredienslinjer. Hver linje har `name` (ingrediensen, offisiell eller brukerens egen). |
| POST | `/api/user/recipes` | Autentisert | Oppretter hele oppskriften i én transaksjon → `201` + `Location` + full oppskrift. `409` ved maks 500 oppskrifter eller ugyldig fremmednøkkel (kategori/ingrediens/enhet), `400` ved ugyldig innhold. |
| PUT | `/api/user/recipes/{id:guid}` | Autentisert | Erstatter hele oppskriften, også steg og ingredienser (de får nye id-er) → `200` + full oppskrift. |
| DELETE | `/api/user/recipes/{id:guid}` | Autentisert | Sletter (steg og linjer følger med) → `204`. |
| PUT | `/api/user/recipes/{id:guid}/favorite` | Autentisert | Body `{isFavorite}` → `204`. Egen liten operasjon så favoritt kan slås av/på uten å sende hele oppskriften. |
| GET | `/api/user/recipes/{id:guid}/nutrition` | Autentisert | Beregnet næring (se under) → `200` / `404`. Hentes når brukeren åpner næringsfanen; ligger bevisst utenfor oppskriften. |

**Forespørselen (`RecipeRequest`)** har ingen id-er og ingen avledede felt: `title`, `description`, `categoryId`, `servings`,
`imageUrl?`, `imageAttribution?`, `source?: { reference? }`, `steps[{ description, timerMinutes? }]`,
`ingredients[{ ingredientId | unconfirmedIngredientId, amount?, unitId, note? }]`. Serveren tildeler id-er, nummererer steg og
ingredienser etter rekkefølge, regner ut `cookTimeMinutes` (summen av steg-timerne), bestemmer kilde-type og tidsstempler.

**Regler:**
- Tittel (lagres med små bokstaver, som øvrige titler/kategorier), beskrivelse, minst ett steg og minst én ingrediensrad kreves;
  `servings` ≥ 1. Lengdegrenser og maks 100 steg/ingredienser står i `RecipeLimits`.
- `amount` er valgfri: utelatt eller `0` betyr «etter smak» (bidrar ikke til næringsberegningen — verdiene er veiledende).
  Negative mengder gir `400`.
- En ingrediensrad peker på **nøyaktig én** av `ingredientId` og `unconfirmedIngredientId`. En ubekreftet ingrediens må være
  brukerens egen og ikke løst (`Approved`/`Merged` er erstattet av en offisiell ingrediens) — ellers `400`. Når admin godkjenner eller slår
  sammen en ubekreftet ingrediens, flyttes brukerens oppskriftslinjer automatisk til den offisielle.
- `imageUrl` må være en gyldig http(s)-adresse (bildeopplasting finnes ikke ennå).
- **Kilde:** brukeren kan bare oppgi fritekst-`reference`. Oppskrifter laget via API-et er alltid `Manual`; `Scraped` (med låst
  `url`) settes av backend når scraper-tjenesten leverer en oppskrift. Redigeres en skrapet oppskrift, settes `isEditedFromSource`
  automatisk; type og url kan aldri endres.
- Grensen på 500 oppskrifter per bruker (`RecipeLimits.MaxPerUser`) er samlet ett sted, så den senere kan gjøres avhengig av kontotype.

### Næring per oppskrift (`GET /recipes/{id}/nutrition`)

Næringen **lagres ikke** i oppskriften og er ikke en del av `GET /recipes/{id}`: den regnes ut på forespørsel fra dagens ingrediensdata
(`RecipeNutritionCalculator`, en ren klasse uten database), så den aldri er utdatert (admin kan endre ingrediensverdier, og godkjenning/
sammenslåing av ubekreftede ingredienser flytter linjer). Veiledende, ikke absolutt.

**Svaret:** `servings`, `energyKcal`/`energyKj` (`{total, perServing}`, kun når > 0), `nutrients[{nutrientId, total, perServing}]` — **kun stoffer med
verdi > 0**, sortert som næringsstoff-katalogen (enhet, navn og gruppe slås opp der på `nutrientId`) —, `countedIngredients`/`totalIngredients` og
`skippedLines[{recipeIngredientId, name, reason}]` med årsak `ToTaste` (mengde 0), `Unconfirmed` (brukerens egen ingrediens har ingen næringsdata)
eller `NoConversion` (enheten kan ikke omregnes til gram for ingrediensen). Per porsjon = total / `servings`; den endres ikke når brukeren skalerer porsjoner.

**Fra linje til gram** (alle næringsverdier er per 100 g *spiselig* del):
1. Ingrediensens egen porsjon for akkurat den enheten (f.eks. 1 stk = 120 g). Porsjonsvektene i Matvaretabellen er vekt av spiselig del
   (banan: 1 stk = 120 g ved 66 % spiselig), så det trekkes **ikke** fra uspiselig del her.
2. Vektenhet: mengden er innkjøpt vekt → trekk fra uspiselig del (`edible_part_percent`; ukjent/0/100 = alt spiselig). 500 g hel banan (66 %) = 330 g.
3. Volumenhet uten egen porsjon: skaleres via ingrediensens største volumporsjon (gram per ml), f.eks. 1 ss ut fra dl-vekten. Ingen fratrekk (volum måles på spiselig/tilberedt mat).
4. Ellers rapporteres linjen som `NoConversion`.

Enhetstypene kjennes igjen på navnet (`vekt`, `volum` — `Domain.Units.UnitTypeNames`); gis de nytt navn, blir linjene rapportert som ikke omregnbare.

**Planlagt, ikke bygget:** «kopier til en annen bruker» (deling). Opprydding når en konto slettes er bygget (2026-09-23): `recipe-auth-api` publiserer fire hendelser og `Application/Messaging/Consumers` sletter all brukerdata — se [`04-events-and-messaging.md`](04-events-and-messaging.md). **Måltidsplanen** skal ta et *øyeblikksbilde* av næringen
når et måltid brukes/spises (næringen for det som faktisk ble spist skal ikke endre seg når ingrediensdata senere endres) — beslutning for den funksjonen.

---

## 7. Ikke bygget ennå

Måltidsplan og handleliste. Varsling til brukeren når en forespørsel avgjøres (e-post via
`recipe-notification-service`, evt. SignalR) er planlagt, men ikke bygget — se `todo.md`.
