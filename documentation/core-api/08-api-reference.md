# API-referanse for `recipe-core-api` (utvidet endepunktguide)

---

Per 2026-09-20. Alle **71 endepunkter** med forventet innkommende og utgående data. Eksemplene er hentet fra det kjørende API-et
(mot migrert og seedet dev-database), ikke skrevet fra hukommelsen. Kort oversikt over kontrollere og tilgangsnivåer:
[`02-endpoints-and-controllers.md`](02-endpoints-and-controllers.md). Autentisering: [`05-authentication-and-authorization.md`](05-authentication-and-authorization.md).
Sjekk mot faktisk kode ved tvil.

## 1. Grunnregler (gjelder alle endepunkter)

### Adresse og autentisering
- Klienten går alltid via gatewayen (`http://localhost:5000/api` i dev; stiene under er relative til `…/api`). Core API lytter direkte på
  `http://localhost:5002` i dev, men skal ikke kalles direkte av frontend.
- Alle `/api/user/**` og `/api/admin/**` krever `Authorization: Bearer <access token>` fra Auth API. Kun `/api/public/**` er åpent.
- Roller er små bokstaver: `user` og `admin`. `admin` er også godkjent på alle `/api/user/**`-endepunkter. Admin har **ingen** tilgang til andres oppskrifter.
- **Identitet kommer bare fra tokenet** (`sub` → bruker-id). Ingen endepunkt tar imot en bruker-id i sti, query eller body.

### JSON
- `camelCase`. Ukjente/tomme verdier kommer som `null` (utelates ikke). `decimal` er JSON-tall. Datoer er ISO 8601 i UTC med offset (`2026-09-20T20:22:49.809431+00:00`).
- **Id-er er Guid (UUIDv7) tildelt av serveren** — aldri send `id` ved opprettelse (en id fra klienten ignoreres). Unntak: næringsstoffer har Matvaretabellens tekstkode som id (`"Vit C"`, `"Fett"`), er skrivebeskyttet, og må URL-enkodes i stien.
- **Enum-verdier er tekst med stor forbokstav** (`"Pending"`, `"Manual"`, `"ToTaste"`), også som query-parametere.
- **Navn og titler lagres med små bokstaver** (kataloger, søkeord, ingredienser, enhetsnavn, oppskriftstitler). Serveren trimmer, slår sammen mellomrom og
  gjør om til små bokstaver; klienten gjør om til stor forbokstav ved visning. Navn må være unike per katalog. Unntak: næringsstoffnavn, enhetsforkortelser
  (symboler som `µg`, `mg-ATE`) og fritekst (beskrivelse, steg, notat).
- **Ingen paginering.** Alle lister er komplette (ingredienser ca. 700, oppskrifter maks 500 per bruker) — klienten filtrerer og søker selv.

### Feil (ProblemDetails, RFC 7807)
| Status | Når | Eksempel på kropp |
| --- | --- | --- |
| `400` (forretningsregel) | Ugyldig innhold | `{"title":"Bad Request","status":400,"detail":"Oppskriften må ha minst ett steg.","traceId":"…"}` |
| `400` (bindings-/formatfeil) | Manglende påkrevd felt, ugyldig id i rute | `{"title":"One or more validation errors occurred.","status":400,"errors":{"$":["JSON deserialization for type '…RecipeRequest' was missing required properties including: 'title'."]}}` |
| `401` | Ingen/utløpt/ugyldig token | Tom kropp |
| `403` | Gyldig token, men ikke `admin` på `/api/admin/**` | Tom kropp |
| `404` | Finnes ikke **eller tilhører en annen bruker** (bevisst identisk) | `{"title":"Not Found","status":404,"traceId":"…"}` (ingen `detail`) |
| `409` (forretningsregel) | Feil status, grense nådd, navn finnes allerede | `{"title":"Conflict","status":409,"detail":"En ingrediens med dette navnet finnes allerede i katalogen. Bruk den i stedet."}` |
| `409` (databasen) | Fremmednøkkel/unikhet: raden er i bruk, peker på noe som ikke finnes, eller finnes fra før | `{"title":"Operasjonen bryter en relasjon: raden er i bruk av andre data, eller peker på noe som ikke finnes.","status":409}` (kun `title`, ingen `detail`; unikhet: «Raden finnes allerede.») |

Meldingen til brukeren er `detail ?? title`; les aldri en melding fra `404`/`401`/`403`.

## 2. Alle endepunkter

`<r>` = `ingredient-categories`, `allergens`, `search-keywords`, `unit-types`, `units`, `recipe-categories` (Guid-nøkkel). «Bruker» = alle innloggede.

| Metode | Sti | Tilgang | Forespørsel → svar |
| --- | --- | --- | --- |
| POST | `/api/public/contact-form` | anonym | `ContactFormRequest` → `200` tekst / `400` tekst |
| GET | `/api/public/health` | anonym | → `{status, service, environment, timestamp}` |
| GET | `/api/user/<r>` | bruker | → liste (hele katalogen) |
| GET | `/api/user/<r>/{id}` | bruker | → element / `404` (`400` ved ugyldig id) |
| GET | `/api/admin/<r>` | admin | → liste |
| GET | `/api/admin/<r>/{id}` | admin | → element / `404` |
| POST | `/api/admin/<r>` | admin | element uten `id` → `201` + `Location` + element / `400` tomt navn / `409` navnet finnes |
| PUT | `/api/admin/<r>` | admin | element **med `id`** i body → `200` (tom kropp) / `400` mangler id eller navn / `409` |
| DELETE | `/api/admin/<r>/{id}` | admin | → `204` / `404` ukjent id / `409` systemrad eller i bruk |
| GET | `/api/user/nutrient-definitions` | bruker | → `NutrientDefinition[]` (57, sortert på `sortOrder`) |
| GET | `/api/user/nutrient-definitions/{id}` | bruker | → `NutrientDefinition` / `404` (id URL-enkodet) |
| GET | `/api/user/ingredients` | bruker | query-filtre → `IngredientListItem[]` |
| GET | `/api/user/ingredients/{id}` | bruker | → `Ingredient` (full) / `404` |
| GET | `/api/admin/ingredients` | admin | som over |
| GET | `/api/admin/ingredients/{id}` | admin | som over |
| POST | `/api/admin/ingredients` | admin | `IngredientRequest` → `201` + `Ingredient` / `400` / `409` |
| PUT | `/api/admin/ingredients/{id}` | admin | `IngredientRequest` → `200` + `Ingredient` (barna erstattes) / `400` / `404` / `409` |
| DELETE | `/api/admin/ingredients/{id}` | admin | → `204` / `404` / `409` `"Brukes av {n} {hva} og kan ikke slettes."` (f.eks. «Brukes av 3 ingredienser …») (brukt av oppskrift, variant eller ubekreftet) |
| GET | `/api/user/unconfirmed-ingredients` | bruker | → egne `UnconfirmedIngredient[]` (nyeste først) |
| GET | `/api/user/unconfirmed-ingredients/{id}` | bruker | → element / `404` |
| POST | `/api/user/unconfirmed-ingredients` | bruker | `{name, requestReview?}` → `201` + element / `400` / `409` |
| PUT | `/api/user/unconfirmed-ingredients/{id}` | bruker | `{name}` → `200` + element / `404` / `409` |
| POST | `/api/user/unconfirmed-ingredients/{id}/request-review` | bruker | (tom kropp) → `200` + element / `404` / `409` |
| DELETE | `/api/user/unconfirmed-ingredients/{id}` | bruker | → `204` / `404` / `409` (brukt av en oppskrift) |
| GET | `/api/admin/unconfirmed-ingredients` | admin | `?status=`/`?all=true` → køen (standard: `Pending`, eldste først) |
| GET | `/api/admin/unconfirmed-ingredients/{id}` | admin | → element / `404` |
| POST | `/api/admin/unconfirmed-ingredients/{id}/approve` | admin | `IngredientRequest` → `200` + ny `Ingredient` / `400` / `404` / `409` |
| POST | `/api/admin/unconfirmed-ingredients/{id}/merge` | admin | `{ingredientId}` → `200` + element / `400` / `404` / `409` |
| POST | `/api/admin/unconfirmed-ingredients/{id}/reject` | admin | `{reason?}` → `200` + element / `404` / `409` |
| GET | `/api/user/recipes` | bruker | → `RecipeListItem[]` (hele lista, sortert på tittel) |
| GET | `/api/user/recipes/{id}` | bruker | → `Recipe` / `404` |
| POST | `/api/user/recipes` | bruker | `RecipeRequest` → `201` + `Location` + `Recipe` / `400` / `409` |
| PUT | `/api/user/recipes/{id}` | bruker | `RecipeRequest` → `200` + `Recipe` (alt erstattes) / `400` / `404` / `409` |
| DELETE | `/api/user/recipes/{id}` | bruker | → `204` / `404` |
| PUT | `/api/user/recipes/{id}/favorite` | bruker | `{isFavorite}` → `204` / `404` |
| GET | `/api/user/recipes/{id}/nutrition` | bruker | → `RecipeNutrition` / `404` |

Totalt: 2 offentlige + 14 brukerlesing av kataloger (seks vanlige + næringsstoffer) + 30 admin-CRUD (seks kataloger) + 7 ingrediens + 11 ubekreftet ingrediens + 7 oppskrift = **71**.

## 3. Kataloger

Seks adminstyrte kataloger. Skjema (alle `id` er Guid, tildelt av serveren):

```json
// Allergen, IngredientCategory, SearchKeyword, RecipeCategory
{ "id": "01a088b5-a202-73e1-98cd-73c0a3e2ab13", "name": "egg", "isSystem": true, "usageCount": 15 }

// UnitType: name er bare en visningsetikett; dimension (Weight | Volume | Count, påkrevd på POST/PUT) er det beregningene bruker
{ "id": "01a088b5-a201-7d1c-86ed-0faaf8ff9a8d", "name": "volum", "dimension": "Volume", "isSystem": true, "usageCount": 230 }

// Unit (name og abbreviation er unike; abbreviation er et symbol og beholder store/små bokstaver: "g", "dl", "µg RAE", "mg-ATE")
{ "id": "01a088b5-a205-7f7c-9319-cf1910cf8f70", "name": "desiliter", "abbreviation": "dl",
  "unitTypeId": "01a088b5-a201-7d1c-86ed-0faaf8ff9a8d",   // vekt, volum eller antall
  "baseUnitRatio": 100,                                   // til enhetstypens basisenhet: gram (vekt) eller milliliter (volum); antall = 1 (ingen omregning)
  "isSystem": true, "usageCount": 230 }
```
Seedet: 16 ingrediens-kategorier, 15 allergener (14 EU + laktose), 13 oppskriftskategorier, 3 enhetstyper og 52 enheter (vekt: g, hg, kg, mg, µg, µg RAE, µg RE, mg-ATE;
volum: ml, cl, dl, l, ts, ss, krm; antall: stk, klype, bunt, skive, fedd, neve, pk og ~30 porsjonsenheter som `glass` og `boks (liten)`).

- **`isSystem`** (2026-09-22) er `true` kun for seed-rader (alle katalograder over unntatt `search-keywords`, som starter tom). Tildeles av
  seed-data; kan aldri settes eller endres via `POST`/`PUT` (et forsøk ignoreres stille, og et forsøk om å sette den på `POST` blir i
  tillegg nullstilt før den ekko-es tilbake i `201`-svaret). Blokkerer kun sletting — en systemrad er fortsatt fritt redigerbar.
- **`usageCount`** (2026-09-22) telles fra referansene til raden ved hver lesing, aldri lagret (se fremmednøkkel-kartet i
  `Documentation/06-persistence-and-data-access.md`). En rad med `usageCount > 0` kan ikke slettes.

**Skriving (admin):** `POST` tar elementet uten `id` (og uten `isSystem`/`usageCount` — begge ignoreres om de sendes) og svarer `201` med
elementet (server-tildelt id, `isSystem: false`, `usageCount: 0`). `PUT` tar hele elementet med `id` i body (ingen id i stien) og svarer
`200` uten kropp — også når raden ikke finnes (ingen `404`, dette er det eneste stedet i API-et som fremdeles har dette avviket, se
`todo.md`). `DELETE` → `204`, `404` hvis raden ikke finnes, `409` `"Systemrader (fra seed-data) kan ikke slettes."` for en systemrad, eller
`409` `"Brukes av {n} {hva} og kan ikke slettes."` (f.eks. «Brukes av 3 ingredienser …») hvis `usageCount > 0`. Tomt navn → `400`, eksisterende navn → `409`.

**Enheter (`units`) har egne regler**, håndhevet i samme `POST`/`PUT` (`400` med norsk `detail`, sjekket etter navnesjekken): `abbreviation` kan ikke være tom (`"Forkortelse må oppgis."`);
`baseUnitRatio` må være større enn 0 (`"Forholdstallet må være større enn 0."` — en ratio på 0 ville gitt feil næringsberegning uten synlig feil); `unitTypeId` må finnes (`"Enhetstypen finnes ikke."`);
og for enheter av typen `antall` må `baseUnitRatio` være nøyaktig 1 (`"Enheter av typen antall regnes ikke om - forholdstallet må være 1."`, siden «antall»-enheter i praksis er ulike ting per ingrediens, se
`ingredient_portion` under Ingredienser). Databasen har i tillegg `CHECK`-er på `abbreviation <> ''` og `base_unit_ratio > 0` som sikkerhetsnett.

### Næringsstoffer (skrivebeskyttet, kun GET)
Statisk katalog fra seed-data; det finnes ingen skriving og ingen egne endepunkter for grupper — gruppen og enheten er nøstet i hvert stoff.

```json
{ "id": "Vit C", "name": "Vitamin C (askorbinsyre)",
  "unitId": "01a088b5-a211-71f1-b489-b996350034d2", "unit": "mg", "unitTypeId": "01a088b5-a200-713f-8326-46fedd9fe90d",
  "decimalPrecision": 1,
  "group": { "id": "01a088b5-a209-78cb-b528-5bd58d53a38e", "name": "vitamin c", "sortOrder": 10,
             "parentGroup": { "id": "01a088b5-a206-7c5d-bf95-99a9a60f413a", "name": "vitaminer", "sortOrder": 7, "parentGroup": null } },
  "sourceUrl": "https://www.matvaretabellen.no/vitamin-c-askorbinsyre/", "sortOrder": 42 }
```
57 stoffer i 15 grupper: fett (med undergruppene mettede/enumettede/flerumettede fettsyrer), karbohydrat (inkl. kostfiber), protein, vitaminer (undergruppene vitamin a–e),
mineraler, sporstoffer og annet (vann, alkohol). Listen er sortert på `sortOrder` (1–57). Stoffer direkte i en hovedgruppe kommer før undergruppene, og **første stoff i en
undergruppe er summen** (`Mettet`, `Enumet`, `Flerum`, `Vit A`), resten er delverdiene. Det finnes ingen `parentId` på stoffene.

## 4. Ingredienser

**Søk** — `GET /api/{user|admin}/ingredients` filtrerer en cachet lettvektsliste i minnet (alle filtre er valgfrie og kombineres med OG):

| Parameter | Betydning |
| --- | --- |
| `name` | Delvis treff (små/store bokstaver uvesentlig) mot ingrediensnavn **og** søkeord |
| `categoryId` | Kun denne kategorien |
| `allergenId` | Kun ingredienser som **inneholder** allergenet |
| `excludeAllergenId` | Kan gjentas (`?excludeAllergenId=a&excludeAllergenId=b`): utelater ingredienser som inneholder noen av dem |
| `searchKeywordId` | Kun ingredienser med dette søkeordet |
| `isOfficial` | `true` = kun offisielle (Matvaretabellen + derivater), `false` = kun ikke-offisielle |
| `isVariant` | `true` = kun derivater/varianter (`variantOfIngredientId` satt), `false` = kun grunningredienser |

```json
// IngredientListItem (søkeresultat)
{ "id": "01a0c079-1096-7072-8bb5-0c4f309e4e58", "name": "egg, rå", "categoryId": "01a088b5-a201-7d6d-bc03-348c6500982e",
  "primaryUnitTypeId": "01a088b5-a201-7d1c-86ed-0faaf8ff9a8d", "defaultUnitId": "01a088b5-a205-7f7c-9319-cf1910cf8f70",
  "energyKcal": 149, "isVerified": true, "isOfficial": true,
  "createdAt": "2026-09-22T20:38:31.420758+00:00", "updatedAt": "2026-09-22T20:38:31.420758+00:00", "verifiedAt": null,
  "allergensReviewed": false, "nutrientValueCount": 57, "portionCount": 1, "usageCount": 0,
  "variantOfIngredientId": null, "allergenIds": [], "searchKeywordIds": [] }
```

```json
// Ingredient (GET .../ingredients/{id}, alltid fersk fra databasen) - forkortet
{ "id": "01a0c079-1096-7072-8bb5-0c4f309e4e58", "name": "egg, rå", "categoryId": "…", "allergenIds": [],
  "primaryUnitTypeId": "…", "defaultUnitId": "…", "energyKcal": 149, "energyKj": 620,
  "ediblePartPercent": 88,                          // andel spiselig del (null = ukjent)
  "searchKeywordIds": [], "sourceId": "02.001", "sourceUrl": "https://www.matvaretabellen.no/egg-ra/", "variantOfIngredientId": null,
  "nutrientValues": [ { "id": "…", "ingredientId": "…", "nutrientDefinitionId": "Alko", "quantity": 0, "sourceId": "50" } ],
  "portions": [ { "id": "…", "ingredientId": "…", "unitId": "<stk>", "gramsPerPortion": 55 },
                { "id": "…", "ingredientId": "…", "unitId": "<dl>",  "gramsPerPortion": 100 } ],
  "isVerified": true, "isOfficial": true, "updatedAt": "2026-09-22T19:47:52.629097+00:00",
  "createdAt": "2026-09-22T18:12:04.001000+00:00", "allergensReviewed": false, "usageCount": 0,
  "updatedByUserId": null, "verifiedAt": null, "verifiedByUserId": null }
```
- `nutrientValues` er **per 100 g spiselig del** og sparsomme (kun målte verdier; `0` = målt som null, manglende = ukjent). `energyKcal`/`energyKj` er per 100 g spiselig del.
- `portions` er enhet → gram **for spiselig del** (banan: 1 stk = 120 g ved 66 % spiselig).
- Alle 703 seedede ingredienser (642 fra Matvaretabellen + 61 derivater av dem) har `isVerified: true` og `isOfficial: true`, `allergensReviewed: false`. Kilden har ikke allergendata; de **åpenbare** allergenene er tagget i seed (`seed_32`: melk/laktose, gluten, egg, fisk, skalldyr, bløtdyr, nøtter, peanøtter, soya, sesam, selleri, sennep, sulfitt), men de er AI-generert (ikke fra kilden), usikre varer og «spor av» er utelatt og ingen er gjennomgått manuelt — allergenfilteret er derfor en veiledning, ikke en garanti.
- **`isOfficial`** er `true` kun for Matvaretabellen-seeden. Tildeles av serveren; kan aldri settes eller endres via `POST`/`PUT` (et forsøk ignoreres stille — feltet finnes ikke i `IngredientRequest`). Se «Skriving» under for hva låsen betyr.
- **`updatedAt`** brukes til optimistisk samtidighetskontroll, se under. **`createdAt`** (2026-09-22) settes én gang ved opprettelse og endres aldri (samme mønster som `isOfficial` — ikke en parameter i `update_ingredient`).
- **`allergensReviewed`** (2026-09-22, `false` som standard) skilles fra en tom `allergenIds`-liste: sistnevnte kan bety "ingen allergener" eller "ingen har sjekket ennå" — dette feltet gjør skillet eksplisitt. Settes av admin via `IngredientRequest` og er fritt redigerbart **selv på en offisiell ingrediens** (ikke omfattet av kildedatalåsen under).
- **Revisjon** (2026-09-24): `updatedByUserId` (hvem som sist endret ingrediensen), `verifiedAt` og `verifiedByUserId` (når/av hvem den ble verifisert) settes av serveren fra tokenet - aldri fra request-body. Verifisering starter når `isVerified` går fra `false` til `true`, beholdes mens den er `true`, og nullstilles når den går til `false`. Alle tre er `null` for seed-rader (verifisert av kilden). Lista har i tillegg `updatedAt`, `verifiedAt`, `nutrientValueCount` og `portionCount` (for å sortere/filtrere «endret nylig», «ikke gjennomgått», «mangler næring/porsjoner» uten å hente hele ingrediensen).
- **`usageCount`** (2026-09-22) telles fra oppskriftslinjer, varianter og løste ubekreftede ingredienser ved hver lesing, aldri lagret. En ingrediens med `usageCount > 0` kan ikke slettes.
- `defaultUnitId` er valgt ut fra porsjonene (dl hvis den har dl-porsjon, ellers stk, ellers ss, ellers første porsjon, ellers gram) — kan derfor være `dl` også for egg, og da er også `primaryUnitTypeId` volum, ikke vekt (settes fra samme regel).

**Skriving (admin)** — `IngredientRequest` (ingen id-er, ingen `isOfficial`; serveren tildeler id for ingrediensen og alle barn; `PUT` erstatter alle barn):

```json
{ "name": "gulrot, lilla", "categoryId": "…", "primaryUnitTypeId": "…", "defaultUnitId": "…", "energyKcal": 35,   // påkrevd: navn, kategori, enhetstype, standardenhet, kcal (≥ 0)
  "energyKj": 147, "ediblePartPercent": 85, "sourceId": null, "sourceUrl": null,
  "variantOfIngredientId": null,                     // sett for en variant av en annen ingrediens (klienten forhåndsutfyller data fra basen)
  "isVerified": false, "allergenIds": [], "searchKeywordIds": [],
  "allergensReviewed": false,                        // fritt redigerbar - også på en offisiell ingrediens, se under
  "updatedAt": "2026-09-22T19:47:52.629097+00:00",   // valgfri, kun PUT: verdien fra klientens siste GET (se «Samtidighet» under)
  "nutrientValues": [ { "nutrientDefinitionId": "Fett", "quantity": 0.2, "sourceId": null } ],   // quantity ≥ 0, ett per stoff, ingen duplikater
  "portions": [ { "unitId": "<stk>", "gramsPerPortion": 90 } ] }                                  // gramsPerPortion > 0, ingen to porsjoner for samme enhet
```

**Validering** (alle `400` med norsk `detail`, sjekket i denne rekkefølgen: format → samtidighet → offisiell-lås → fremmednøkler):
- Tomt navn; `energyKcal`/`energyKj` negativ; `ediblePartPercent` utenfor `(0, 100]`; tall som ikke får plass i kolonnen (f.eks. `energyKcal` > 99 999 999,99); duplikat `nutrientDefinitionId`; `isVerified: true` uten minst én næringsverdi (`"Ingrediensen må ha næringsverdier for å kunne verifiseres."`); `sourceUrl` som ikke er http(s).
- **Fremmednøkler finnes** (i stedet for en generisk `409` fra databasen): ukjent `categoryId`/`primaryUnitTypeId`/`defaultUnitId`/allergen/søkeord/næringsstoff-id gir en spesifikk `400` som navngir typen (f.eks. `"Kategorien finnes ikke."`, `"Næringsstoffet Fett finnes ikke."`). `defaultUnitId` må høre til `primaryUnitTypeId` (`"Standardenheten må høre til den valgte enhetstypen."`). To porsjoner med samme enhet gir `400` med enhetens navn (`"Enheten gram er brukt i flere porsjoner."`) — databasen har i tillegg en unik indeks `(ingredient_id, unit_id)` som sikkerhetsnett.
- **`variantOfIngredientId`:** må finnes (`"Basisingrediensen finnes ikke."`), kan ikke være ingrediensen selv (`"En ingrediens kan ikke være en variant av seg selv."`), og variantkjeden kan ikke danne en løkke (`"Variantkjeden danner en løkke."`).

**Offisielle ingredienser (`isOfficial: true`) — kildedata er låst.** `PUT` avvises med `400`, `detail`: **"Offisielle ingredienser kan ikke endre kildedata. Opprett en variant."**, hvis noe av dette avviker fra det lagrede (etter normalisering): `name`, `energyKcal`, `energyKj`, `ediblePartPercent`, `sourceId`, `sourceUrl`, eller **settet** av næringsverdier
(`{nutrientDefinitionId, quantity, sourceId}` sammenlignet uavhengig av rad-id og rekkefølge — å sende dem i annen rekkefølge med nye id-er er altså greit). Fritt redigerbart uansett: `categoryId`, `primaryUnitTypeId`, `defaultUnitId`, `allergenIds`, `searchKeywordIds`, `portions`, `isVerified`, `allergensReviewed`. Offisielle *derivater* (seed_30: spaghetti, penne, whisky, fanta osv.) er varianter (`variantOfIngredientId` peker på basisraden de arver tall fra) og har `sourceId: null`, men beholder basisens `sourceUrl`. `POST` setter alltid `isOfficial = false`, uansett hva klienten sender. `DELETE` av en offisiell ingrediens er fortsatt lov når den ikke er i bruk.

**Barne-id-er:** `PUT` på en ingrediens erstatter alle næringsverdier og porsjoner, så de får **nye id-er ved hver lagring** — klienten må aldri cache barnas id-er (bruk `nutrientDefinitionId` / `unitId` som nøkkel).

**Samtidighet (optimistisk):** send `updatedAt` fra siste `GET` tilbake i `PUT`-body. Er den eldre enn det som er lagret → `409`, `detail`: **"Ingrediensen er endret av noen andre siden du åpnet den. Last den på nytt."** Utelates feltet, gjøres ingen sjekk (bakoverkompatibelt).

`409` ved eksisterende navn eller kilde-id. `DELETE` → `404` hvis ingrediensen ikke finnes, `409` `"Brukes av {n} {hva} og kan ikke slettes."` (f.eks. «Brukes av 3 ingredienser …») hvis den brukes av en oppskrift, en variant eller en ubekreftet ingrediens.

## 5. Ubekreftede ingredienser

En bruker som ikke finner en ingrediens lager en **privat** ubekreftet ingrediens og kan be admin ta den inn i katalogen.

```json
// UnconfirmedIngredient
{ "id": "01a0c07c-5874-7bfb-bd3f-1fb639989ba3", "name": "lilla gulrot", "createdByUserId": "…",
  "reviewStatus": "Pending",            // NotRequested | Pending | Approved | Merged | Rejected
  "rejectionReason": null, "reviewedAt": null,
  "resolvedIngredientId": null,          // satt kun ved Approved/Merged: den offisielle ingrediensen
  "createdAt": "2026-09-20T20:22:49.7163842+00:00" }
```
Livssyklus: `NotRequested → Pending → Approved | Merged | Rejected` (`Rejected` er terminal og forblir privat). Bare `NotRequested` kan endres (navn); bare `Pending` kan avgjøres av admin.
`Approved`/`Merged` betyr at brukeren ikke lenger «eier» ingrediensen; oppskriftslinjer som pekte på den flyttes automatisk til den offisielle ingrediensen (i samme transaksjon), og raden beholdes som historikk.

- **Bruker:** `POST {name, requestReview?}` (`requestReview: true` gir `Pending` direkte), `PUT {name}`, `POST …/request-review`, `DELETE`. Navnet må ikke finnes som offisiell ingrediens og ikke som en av brukerens egne (`409`).
  Grenser: maks **100** egne, maks **10** ventende, navn 1–200 tegn.
- **Admin:** køen (`GET`, standard `Pending`, `?status=Rejected`, `?all=true`), `approve` (`IngredientRequest` → ny ingrediens; sett `variantOfIngredientId` for å godkjenne som variant),
  `merge` (`{ingredientId}`), `reject` (`{reason?}`).

## 6. Oppskrifter

Oppskrifter er strengt brukereide. Bare selve oppskriften er en ressurs — steg, ingredienslinjer og kilde er nøstet og leses/skrives sammen med den.

```json
// RecipeRequest (POST og PUT) - ingen id-er og ingen avledede felt
{ "title": "Kremet Kyllinggryte", "description": "Enkel hverdagsmiddag.", "categoryId": "…", "servings": 4,     // påkrevd
  "imageUrl": "https://example.test/gryte.jpg", "imageAttribution": null,                                       // valgfritt; http(s)
  "source": { "reference": "min kokebok" },                                                                     // kun fritekst; type/url styres av serveren
  "steps": [ { "description": "Kutt kyllingen." }, { "description": "Kok i 20 minutter.", "timerMinutes": 20 } ],   // minst ett; nummereres etter rekkefølge
  "ingredients": [                                                                                              // minst én; rekkefølgen beholdes
    { "ingredientId": "<offisiell>", "amount": 2, "unitId": "<stk>" },
    { "unconfirmedIngredientId": "<egen>", "amount": 100, "unitId": "<g>", "note": "finhakket" },
    { "ingredientId": "<offisiell>", "unitId": "<g>" } ] }                                                     // amount utelatt/0 = «etter smak»
```

```json
// Recipe (svar på GET / 201 / 200) - forkortet
{ "id": "01a0c07c-58d1-7a4a-b270-82af7bf08a67", "ownerUserId": "…", "title": "kremet kyllinggryte", "description": "Enkel hverdagsmiddag.",
  "categoryId": "…", "cookTimeMinutes": 20,          // avledet: summen av steg-timerne
  "servings": 4, "imageUrl": "https://example.test/gryte.jpg", "imageAttribution": null, "isFavorite": false,
  "ingredients": [ { "id": "…", "recipeId": "…", "ingredientId": "…", "unconfirmedIngredientId": null, "amount": 2, "unitId": "…",
                     "note": null, "sortOrder": 1, "name": "egg, rå" } ],     // name = ingrediensens navn (offisiell eller egen), kun lesing
  "steps": [ { "id": "…", "recipeId": "…", "stepNumber": 1, "description": "Kutt kyllingen.", "timerMinutes": null } ],
  "source": { "type": "Manual", "reference": "min kokebok", "url": null, "isEditedFromSource": null },
  "createdAt": "2026-09-20T20:22:49.809431+00:00", "updatedAt": "2026-09-20T20:22:49.809431+00:00" }

// RecipeListItem (GET /recipes) - hele lista, sortert på tittel, ingen paginering
{ "id": "…", "title": "kremet kyllinggryte", "imageUrl": "https://example.test/gryte.jpg", "categoryId": "…", "cookTimeMinutes": 20, "servings": 4, "isFavorite": false }
```

**Regler** (feil → `400` med norsk `detail`, med mindre annet er oppgitt):
- Tittel (lagres med små bokstaver ≤ 200 tegn), beskrivelse (≤ 5 000), `servings` 1–1 000, minst ett steg (≤ 100, hver beskrivelse ≤ 2 000, timer 0–10 080 min) og minst én ingrediensrad (≤ 100).
- Hver rad peker på **nøyaktig én** av `ingredientId`/`unconfirmedIngredientId`. Den ubekreftede må være brukerens egen og ikke løst (`Approved`/`Merged` → bruk den offisielle) — ellers `400` (samme svar som for en som ikke finnes).
- `amount` er valgfri: utelatt eller `0` = «etter smak» (regnes som ingenting i næringsberegningen). Negativ → `400`. Notat ≤ 200 tegn.
- `imageUrl` må være en gyldig http(s)-adresse. Ukjent kategori/ingrediens/enhet → `409`.
- **Tittelen er unik per bruker** (2026-09-24; sammenlignet etter normalisering til små bokstaver) → `409` `"Du har allerede en oppskrift med denne tittelen. Velg en annen tittel."` på `POST` og `PUT` (en oppskrift kan beholde sin egen tittel). Ulike brukere kan ha samme tittel. Databasen har unik indeks `(owner_user_id, title)` som sikkerhetsnett.
- **Maks 500 oppskrifter per bruker** → `409`. Grensen ligger samlet i `RecipeLimits.MaxPerUser` (kan senere knyttes til kontotype).
- **Kilde:** oppskrifter laget via API-et er alltid `Manual`. `Scraped` (med låst `url`) settes av backend når scraper-tjenesten leverer en oppskrift. Redigeres en skrapet oppskrift, settes `isEditedFromSource` automatisk; type og url kan aldri endres.
- `PUT` **erstatter alt** (også steg og ingredienser, som får nye id-er) og beholder id, eier, favoritt og `createdAt`; `updatedAt` settes av serveren.
- `PUT …/favorite` med `{ "isFavorite": true }` slår favoritt av/på uten å sende hele oppskriften.

### Næring: `GET /api/user/recipes/{id}/nutrition`
Regnes ut på forespørsel fra dagens ingrediensdata (lagres ikke i oppskriften, er aldri utdatert). Veiledende, ikke absolutt.

```json
{ "recipeId": "01a0c07c-58d1-7a4a-b270-82af7bf08a67", "servings": 4,
  "energyKcal": { "total": 163.9, "perServing": 40.975 },      // null når 0/ukjent (samme for energyKj)
  "energyKj":   { "total": 682, "perServing": 170.5 },
  "nutrients": [ { "nutrientId": "Fett", "total": 11.77, "perServing": 2.9425 }, { "nutrientId": "Omega-3", "total": 0.187, "perServing": 0.0468 } ],   // KUN stoffer med verdi > 0, sortert som katalogen
  "countedIngredients": 1, "totalIngredients": 3,
  "skippedLines": [ { "recipeIngredientId": "…", "name": "lilla gulrot", "reason": "Unconfirmed" },
                    { "recipeIngredientId": "…", "name": "egg, rå", "reason": "ToTaste" } ] }
```
- `reason`: `ToTaste` (mengde 0), `Unconfirmed` (brukerens egen ingrediens har ingen næringsdata), `NoConversion` (enheten kan ikke omregnes til gram for ingrediensen).
- Enhet, navn, desimaler og gruppe for `nutrientId` slås opp i næringsstoff-katalogen. Per porsjon = total / `servings` og endres ikke når brukeren skalerer porsjoner.
- **Fra linje til gram** (alle verdier er per 100 g *spiselig* del): (1) ingrediensens egen porsjon for akkurat den enheten (ingen fratrekk — porsjonsvekter er allerede spiselig vekt); (2) vektenhet → mengde × enhetens forholdstall,
  minus uspiselig del (`ediblePartPercent`; 500 g hel banan ved 66 % = 330 g); (3) volumenhet uten egen porsjon → skalert via ingrediensens største volumporsjon (gram per ml; 1 ss ut fra dl-vekten); (4) ellers `NoConversion`.
  Enhetstypene gjenkjennes på navnet (`vekt`, `volum`).
- **Måltidsplan (senere):** en måltidsplan-post skal ta et *øyeblikksbilde* av næringen når måltidet planlegges/spises.

## 7. Grenser og kjente begrensninger

| Område | Grense |
| --- | --- |
| Ubekreftede ingredienser | 100 per bruker, 10 ventende, navn ≤ 200 tegn |
| Oppskrifter | 500 per bruker, ≤ 100 steg, ≤ 100 ingredienser |
| Lister | Ingen paginering — hele lista returneres |

Ikke bygget ennå: deling av oppskrifter (kopi til en annen bruker), opprydding når en konto slettes, bildeopplasting (kun `imageUrl`), måltidsplan, handleliste og produkt-modell,
varsling når en ubekreftet ingrediens avgjøres, allergen-tilordning på de seedede ingrediensene. Se `todo.md` (lokalt) for status.

---

Sjekk mot faktisk kode ved tvil.
