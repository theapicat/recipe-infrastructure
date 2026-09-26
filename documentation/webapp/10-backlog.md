# 10 – Backlog & utsatte avklaringer

Sist oppdatert 2026-09-23. Dette dokumentet samler ting som **bevisst er utsatt** — det er ikke feil i koden
(det er [07](./07-known-issues-and-tech-debt.md)), men arbeid, avklaringer og backend-avhengigheter vi har snakket
om og valgt å ta senere. Ta en ting av lista og flytt den til 07/02/09 når den bygges.

## 1. Besluttet rekkefølge og arbeidsprinsipper

- **Rekkefølge:** kataloger (admin) → ingredienser → oppskrifter → måltidsplan → handleliste. Oppskrifter avhenger
  av ingredienser, som igjen avhenger av katalogene (se [08, seksjon 6](./08-model-and-component-structure-proposal.md#6-konkret-migreringsrekkefølge-når-dere-er-klare)).
- **Kun de modellene backend faktisk har.** Frontend bygges mot modellene i `recipe-core-api`. Funksjoner mockene
  viser som backend ikke har (se seksjon 3) bygges ikke før backend har dem.
- **Kun to HTTP-agenter** (`agentInternal`, `agentExternal`), og alle nye endepunkter følger malen i
  [04, seksjon 7](./04-api-integration-and-data-models.md#7-mal-slik-legger-du-til-et-nytt-backend-endepunkt).
- **Ingen caching på frontend.** Backend cacher katalogene. Om vi trenger å lagre data i nettleseren tas det opp når
  vi begynner på komponentene (spesielt ingredienslisten på ~1 565 rader og katalogene som brukes til id → navn-oppslag).
- **Ingen frontend-tester foreløpig** — se seksjon 4. Backend har omfattende tester (enhetstester og
  endepunkt-tester).

## 2. Neste på lista

1. ✅ **Kataloger (admin) — bygget** (`/admin/catalog`, se [05](./05-admin-panel.md), seksjon 3): fem kataloger med
   egen fane (enhetstypene er faste og vises kun som data, med filter og kolonne i enhetstabellen). Erstattet mock-siden `app/admin/categories`. Næringsstoffdefinisjoner er
   skrivebeskyttet i backend og har ingen admin-flate. Gjenstår: manuell testing mot ekte backend.
2. **Ingredienser:** egen admin-side `/admin/ingredients` — det gamle «Råvareregister» fra mocken. ✅ **Bygget** (se
   [05](./05-admin-panel.md), seksjon 4): liste med søk og filtre (inkl. opprinnelse — venter på backend), utvidet visning,
   redigering (også allergener), verifisering/fjerning av den (krever næringsverdier), oppretting (også avledet fra en
   eksisterende), sletting (blokkert når i bruk), og **offisielle ingredienser delvis låst** (kildedata; vil man endre dem lager man en
   variant). **Gjenstår:**
   - **Godkjenningskøen** for brukeres ubekreftede ingredienser. «Godkjenn» er enten å opprette en ny offisiell ingrediens (evt.
     avledet fra en eksisterende, med editoren forhåndsutfylt) eller å **slå den sammen** med en eksisterende (erstatter den ubekreftede
     i brukernes oppskrifter — det er en sammenslåing, ikke en verifisering), eller å avvise den. Gjenbruker editoren.
   - **«Mine ingredienser»** for brukeren (egne ubekreftede ingredienser med review-livssyklus).
   - **Brukerens ingrediensoppslag** (`/user/ingredients`, se [09](./09-recipe-domain-and-planned-pages.md)) — gjenbruker `IngredientDetailView`.
   - **Massehandlinger** (velg flere → verifiser / legg til allergen) — krever backend, se seksjon 7 (B11).
     Ingrediens-endepunktene avviker fra katalogkontrakten og har egne ruter (se
     [04, seksjon 7.1](./04-api-integration-and-data-models.md#71-variant-én-dynamisk-rute-for-flere-like-ressurser)).
3. **Oppskrifter:** ✅ **Bygget** (2026-09-22, se [09](./09-recipe-domain-and-planned-pages.md), seksjon 0): liste
   (søk, kategorifilter, favoritter), opprettelse, redigering (delt skjema med søkbar ingrediens- og enhetsvelger,
   kolonneoverskrifter over ingredienslinjene), detalj (favoritt/rediger/slett, klientside porsjonsskalering) og
   sletting — alt mot ekte `recipe-core-api`. Ingrediensvelgeren tilbyr å legge til en ingrediens som ikke finnes i
   katalogen som brukerens egen (ubekreftet), rett fra søket — se `AddUnconfirmedIngredientDialog.tsx`. Enhetsvelgeren
   på hver ingredienslinje er innsnevret til enheter som **faktisk har en gram-omregning for den valgte ingrediensen**:
   vekt og volum låses opp som hele (kuraterte) typer — ingrediensens egen primærtype alltid, og den andre typen i
   tillegg om ingrediensen har en porsjon i den — mens antall (stk, skive, glass, ...) kun gir akkurat de enhetene
   som er definert som porsjon for akkurat den ingrediensen. Vekt er begrenset til gram/hektogram/kilogram
   (`SENSIBLE_WEIGHT_UNIT_NAMES`); volum og antall er ikke ytterligere kuttet. Samme to-stegs type-så-enhet-velger
   og vekt-begrensning er nå også i admin-ingrediensskjemaets «Porsjoner»-seksjon (tidligere ett flatt, ufiltrert
   enhetsvalg over alle ~90 enheter). Se `lib/units/unitTypeInfo.ts` (`unitsOfType()`), `recipeLookups.ts`
   (`unitsForIngredient()`) og `components/admin/ingredients/IngredientForm.tsx`. Alle brukervendte ruter dette bygger på
   (`/api/user/recipes*`, `/api/user/recipe-categories`, `/api/user/units`, `/api/user/unit-types`,
   `/api/user/ingredients[/{id}]`, `/api/user/unconfirmed-ingredients`) er **bekreftet 2026-09-23 mot
   `recipe-core-api`-kildekoden** (se `backend-notes.md`, B16–B18) — ingen er lenger antatt. **Kokemodus**
   (`/user/recipes/[id]/cook`, 2026-09-23) bruker nå den valgte oppskriften — steg for steg med nedtellingstimer
   (flere samtidig, lyd + varsel), Wake Lock og porsjonsskalert ingrediensliste. **Næringsfanen** på detaljsiden
   (2026-09-23, `RecipeNutritionView.tsx`) viser total/per porsjon i tre detaljnivåer (enkel/utvidet/detaljert).
   **Gjenstår:**
   - Kategorivelgeren tilbyr kun eksisterende kategorier — bevisst, ikke en mangel; om det skal bli mulig å legge
     til en ny kategori derfra er en åpen avklaring, ikke besluttet.
   - Manuell testing mot en kjørende Gateway/Core gjenstår (dette er verifisert mot kildekoden og `tsc`/`lint`, ikke
     kjørt i praksis ennå).

## 3. Utsatt fordi backend ikke har det ennå

| Funksjon                                      | Status / merknad                                                                                                                                                                                   |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| «Laget X ganger» / «sist laget»               | Skal **ikke** være tellere på oppskriften. Løses trolig av en egen modell («kokelogg» — hva ble laget når) som hører sammen med måltidsplanen. Mock-fanen «Ofte laget» bygges ikke før den finnes. |
| Forberedelses- vs. koketid, «forfatter»       | Backend har kun `cookTimeMinutes` (utledet av stegtimere) og ingen forfatterfelt. Bygges ikke.                                                                                                     |
| Allergen-preferanser / brukerinnstillinger    | Skal bo i Core (brukerinnstillinger). Ikke startet. Mock-innstillingssiden har kun lokal state. Ekskluder-allergen-filteret er uansett ikke pålitelig før ingrediensene er allergen-tagget.        |
| Sletting av konto → opprydding                | Auth API sender en hendelse når en konto slettes, og Core skal slette brukerens oppskrifter og øvrige data. Ikke bygget i Core ennå — til da blir brukerdata liggende igjen.                       |
| Måltidsplan, handleliste                      | Ikke startet i backend. Avhenger av avklaringen «ingrediens vs. produkt» (egen produktmodell, flytte ingrediens → produkt).                                                                        |
| Import (skraping)                             | Skrapetjenesten leverer via RabbitMQ; Core-siden (consumer som oppretter `Scraped`-oppskrifter) er ikke bygget. `app/(user)/user/import` er en mock.                                               |
| Deling av oppskrifter                         | Planlagt som «kopier til annen bruker» (ny rad, ingen lineage). Mock-listen har en «del på e-post»-dialog som skjules/deaktiveres.                                                                 |
| Opplasting av bilder                          | Kun `imageUrl` (http/https) per i dag.                                                                                                                                                             |
| Varsler når en ubekreftet ingrediens avgjøres | Planlagt (hendelse → e-post). Inntil videre ser brukeren utfallet på listen sin.                                                                                                                   |
| Admin `whitelist` og `system`                 | Ingen backend for disse. Forblir mocks.                                                                                                                                                            |
| «Legg til på handleliste»-knappen             | Skjules/deaktiveres til handlelisten finnes.                                                                                                                                                       |

## 4. Utsatt frontend-arbeid og åpne avklaringer

- **Frontend-oppfølging når backend leverer** (se seksjon 7; feltene er valgfrie i modellene, så ingenting brekker før det):
  send `updatedAt` med `PUT` og vis «endret av noen andre»-meldingen (B3); bytt verifisering til det lette endepunktet (B10); bryter
  «Allergener gjennomgått» i editoren og tydelig skille mellom «ikke gjennomgått» og «ingen» (B9); radvalg + massehandlinger i
  ingredienslisten (B11); sortering/filter på endret/verifisert/mangler næringsdata (B12); åpne enhetstyper for redigering (B13);
  fjern utledningen av «offisiell» fra `sourceId` når `isOfficial` kommer (B2). Flytt varslene (toasts) til nederst til høyre om de dekker
  handlingslinjen i skuffen.
- **Teststrategi for frontend** (rammeverk, hva som dekkes først — trolig ren logikk som næringsgruppering,
  enhetsvalg og porsjonsskalering, samt auth-flyten). Bevisst utelatt i denne runden.
- **Verifisering gjennom Gatewayen.** Core er så langt testet direkte mot sin egen port. Må sjekkes når tjenestene
  kjører: path-enkodede næringsstoff-id-er (`Vit%20C`, `Mono%2BDi`), `Location`-headeren ved 201 (inneholder Cores egen
  vert — bruk `id` fra body), og gjentatt query-parameter `excludeAllergenId`.
- **Server Components / Server Actions som alternativ til route handlers.** `agentExternal` er kun server-side
  (leser httpOnly-cookien), så klientkomponenter kan ikke kalle den direkte. Dagens løsning er route handlers +
  `agentInternal`. Server Components (lesing) og Server Actions (skriving) kunne kalt `agentExternal` uten egne
  ruter — ikke besluttet; se [04, seksjon 7](./04-api-integration-and-data-models.md) for gjeldende mal. Verifiser i
  så fall at `proxy.ts` fornyer tokenet også for Server Actions.
- **Sjekk auth-/admin-modellene** (`lib/models/auth`, `lib/models/admin/users`) mot Auth API sine DTO-er. Kun
  Core-modellene er verifisert mot backend.
- **`/api/auth/refresh` nullstiller sesjonen ved enhver feil**, også ved nettverksfeil mot Gatewayen (ikke bare når
  refresh-tokenet er utløpt). Bevisst uendret i refaktoreringen; kan skille 503/504 fra 401/400 senere.
- **`POST /connect/revoke` på Gatewayen** (ekte token-invalidering ved utlogging) — se
  [03, seksjon 4.3](./03-auth-and-session.md).
- **Passord-policy** er inkonsekvent på tvers av tre skjemaer — se [07](./07-known-issues-and-tech-debt.md).
- **`@mantine/dates`** mangler `DatesProvider`-oppsett — tas sammen med måltidsplanen.
- **Per-side `<Suspense>`** i `admin/users/email`, `confirm-email` og `reset-password` finnes bare fordi sidene bruker
  `useSearchParams`. Vurder å erstatte dem med segment-`loading.tsx` (som `app/admin/loading.tsx`) — verifiser først at
  produksjonsbygget godtar det.
- **`agentRules`-blokken** som `next dev` skriver inn i `CLAUDE.md` (se [01](./01-architecture-and-setup.md)) kan slås av
  i `next.config.ts` om den blir plagsom.

## 5. Forbehold i backend som påvirker UI (status per 2026-09-20)

Kilde: `recipe-core-api` sine egne notater og `Documentation/08-api-reference.md` i det repoet.

- Alle 1 565 seedede ingredienser har i dag `isVerified: false` og **ingen allergener**. Besluttet: de skal seedes som
  verifiserte, men uten gjettede allergener — se seksjon 7 (B8). Ikke selg allergenfilteret som en sikkerhetsfunksjon ennå.
- `defaultUnitId` er `dl` for mange ingredienser (f.eks. egg) fordi den utledes fra porsjonene. Vurder å foretrekke
  `stk` i enhetsvalget når ingrediensen har en stk-porsjon.
- Kalkulatoren for næring finner vekt/volum via **navnet** på enhetstypene (`vekt`, `volum`). Omdøpes de, gir alle
  linjer `NoConversion` (aldri feil tall). Be admin ikke omdøpe dem.
- Generisk katalog-`PUT` på en rad som ikke finnes gir `200` (ikke `404`), og `DELETE` gir `204` selv om ingenting ble
  slettet. Ingredienser, ubekreftede ingredienser og oppskrifter gir `404`.
- Oppskriftstittel-unikhet per bruker er ikke besluttet (ikke håndhevet). Grensen på 500 oppskrifter per bruker kan
  senere variere med kontotype — ikke hardkod tallet mange steder.
- Seeden inneholder mange produkt-/rett-lignende oppføringer (yoghurt med smak, ferdigretter, brød). Ikke bygg UI som
  antar at ingredienslisten er endelig — en egen produktmodell er planlagt.

## 6. Idéer: bruk og statistikk for katalogene (senere)

Ikke nødvendig for at katalogene skal fungere, men nyttig for admin. Ingen av dem er mulig uten nye backend-endepunkter
(eller, for noen, tunge klientberegninger).

- **Antall per oppføring («bruk»):** oppskrifter per oppskriftskategori, ingredienser per kategori/allergen/søkeord,
  hvor ofte et søkeord brukes, hvilke enheter som er i bruk. Foreslått design: et eget `GET /admin/<resource>/usage` →
  `[{id, count}]`, slik at den cachede og delte katalogformen ikke endres. Ingrediensbaserte tall kan i prinsippet telles
  klientside fra ingredienslisten, men det gir misvisende tall for enheter (porsjoner og oppskriftslinjer teller også),
  og oppskriftskategorier krever et aggregat i backend (admin har ikke innsyn i brukeres oppskrifter — kun tall).
- **Slett-vern:** ✅ bygget i frontend mot valgfrie `isSystem`/`usageCount` (avhenger av at backend leverer dem — se seksjon 7, B7).
- **Filter «ubrukte»**, spesielt nyttig for de ~300 søkeordene.
- **Sammenslåing** av to oppføringer (flytt all bruk til én, slett den andre) — krever backend-støtte.
- **Masse-tillegg:** lim inn en liste med søkeord.
- **Eksport** (CSV) og **«sist endret av/når»**.
- «Status/aktiv»-feltet fra den gamle mocken er bevisst fjernet: en oppføring er tilgjengelig så snart den er
  registrert.

## 7. Avhengigheter til backend (oppsummering)

Frontend er bygget til å **fungere uten noe av dette** — den speiler reglene selv, faller tilbake til vanlige 409-svar, og de nye feltene er
**valgfrie** i modellene og lyser opp av seg selv når backend begynner å levere dem. Men API-et bør ikke stole på frontend.

Den **detaljerte spesifikasjonen** (kontrakter, feilmeldinger, skjemaendringer, seed-endringer, akseptansetester, åpne avklaringer) ligger i et
**privat arbeidsnotat, `backend-notes.md` i repo-roten**. Det er bevisst _ikke_ en del av den offentlige dokumentasjonen og skal aldri
committes eller stages (samme status som `frontend-notes.md`). Nummerne **B1–B19** er de samme i begge; kode og dokumentasjon viser til dem.

**Prioritet:** **P1** = trengs for at admin-redigering skal være trygg. **P2** = trengs for at det som allerede er bygget skal virke fullt ut.
**P3** = nyttig.

| #   | Ønske                                                                                                                                                                                                                                                                                                    | Prio | Frontend i dag → når levert                                                                                     |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---- | --------------------------------------------------------------------------------------------------------------- |
| B1  | **Håndhev låsen på offisielle ingredienser** (avvis endring av navn, energi, spiselig del, næringsverdier, kilde)                                                                                                                                                                                        | P1   | Frontend låser feltene → backend blir sikringen                                                                 |
| B2  | **`isOfficial`** på `Ingredient` og `IngredientListItem` (+ `createdAt`, `origin`)                                                                                                                                                                                                                       | P1   | Utledes fra `sourceId` i skuffen; filter og kolonne «Opprinnelse» i listen er bygget og **venter** på feltet    |
| B3  | **Samtidighetskontroll** (`updatedAt`) på `PUT` av ingrediens                                                                                                                                                                                                                                            | P1   | Ingen i dag (siste lagring vinner) → 409 med klar melding; frontend må da sende `updatedAt`                     |
| B4  | **Validering med klare 400-svar** (prosent, enhet ↔ enhetstype, variant-løkke, duplikate næringsstoffer/porsjoner, URL, størrelser)                                                                                                                                                                      | P1   | Frontend speiler reglene → backend gir samme meldinger                                                          |
| B5  | **Håndhev «verifisert krever næringsverdier»**                                                                                                                                                                                                                                                           | P1   | Frontend deaktiverer «Verifiser» → backend avviser også                                                         |
| B6  | **Enhetsvalidering** (`abbreviation` ikke tom, `baseUnitRatio` > 0, `antall` = 1)                                                                                                                                                                                                                        | P1   | Frontend validerer; forholdstall 0 gir stille feil næringstall om det slipper gjennom                           |
| B7  | **`isSystem` + `usageCount`** på kataloger og ingredienser, og `DELETE` som avviser dem med forklaring                                                                                                                                                                                                   | P2   | «Slett» er bygget mot feltene (deaktivert med begrunnelse når de finnes); i dag aktiv, med 409 som siste skanse |
| B8  | **Seed:** offisielle ingredienser verifiserte, katalograder `is_system`, **ingen gjettede allergener**                                                                                                                                                                                                   | P2   | I dag viser registeret «Nei» (uverifisert) på alle 1 565                                                        |
| B9  | **`allergensReviewed`** — skille «ukjent» fra «ingen allergener» (forslag)                                                                                                                                                                                                                               | P2   | Forbeholdstekst «ingen registrert ≠ fri for allergener»; allergenfilteret kan ikke selges som sikkerhet         |
| B10 | **Lett verifiserings-endepunkt**                                                                                                                                                                                                                                                                         | P2   | Verifisering sender hele ingrediensen (`PUT` med alle barn)                                                     |
| B11 | **Massehandlinger** (verifiser mange, legg til/fjern allergen på mange)                                                                                                                                                                                                                                  | P2   | Ikke bygget — gjennomgang av ~1 565 ingredienser er urealistisk uten                                            |
| B12 | **Revisjons- og listefelt** (`updatedAt`/`By`, `verifiedAt`/`By`, `nutrientValueCount`, `portionCount`)                                                                                                                                                                                                  | P3   | Ingen sortering/filter på «endret nylig», «mangler næringsdata»                                                 |
| B13 | **`dimension` på enhetstyper** i stedet for navnematching                                                                                                                                                                                                                                                | P3   | Enhetstyper er skrivebeskyttet i frontend; med dimensjon kan de åpnes                                           |
| B14 | **Katalog-`PUT`/`DELETE` på manglende rad → 404** (i dag 200/204)                                                                                                                                                                                                                                        | P3   | Frontend leser listen på nytt etter hver endring, så det merkes ikke                                            |
| B15 | **Slette-meldinger med forklaring** og dokumentasjon (bl.a. at `PUT` gir barna nye id-er)                                                                                                                                                                                                                | P3   | Generisk 409-melding vises                                                                                      |
| B16 | ✅ **Løst 2026-09-23** — alle antatte stier (favoritt, ingrediens-/kategori-/enhets-/enhetstype-velgere) bekreftet mot `recipe-core-api`-kildekoden, ingen avvik                                                                                                                                         | –    | Ingen handling i backend nødvendig                                                                              |
| B17 | ✅ **Løst 2026-09-23** — `POST /user/unconfirmed-ingredients` bekreftet, matcher skjemaet nøyaktig                                                                                                                                                                                                       | –    | Ingen handling i backend nødvendig                                                                              |
| B18 | ✅ **Løst 2026-09-23** — var en frontend-feil, ikke et backend-hull: `GET /user/ingredients/{id}` returnerer allerede `portions`, skjemaet leste den bare ikke ennå. Presisert samme dag med eierens eksempler (melk, agurk) og en vekt-enhetsbegrensning (kun g/hg/kg) — begge deler også frontend-only | –    | Ingen handling i backend nødvendig. Se `backend-notes.md` for detaljene og begrunnelsen.                        |
| B19 | **Ingredienskatalogen har for mange nær-duplikater** (f.eks. ~20 varianter av margarin, mange like kjøttdeig-oppføringer) — trenger en opprydding                                                                                                                                                        | P2   | Gjør det vanskelig å velge riktig ingrediens i søket. Ingen løsning valgt ennå. Se `backend-notes.md`.          |

**Beslutninger frontend bygger på** (se [05](./05-admin-panel.md), seksjon 3–4):

- **Verifisert** betyr offisiell/gjennomgått oppføring — _ikke_ at allergendata er komplett. En ingrediens kan bare verifiseres med næringsverdier;
  å fjerne verifisering er alltid lov.
- **Offisielle ingredienser er kildedata** og delvis låst (navn, energi, spiselig del, næringsverdier, kilde). Allergener, søkeord, kategori, enheter,
  porsjoner og verifisering kan endres; vil man endre en låst verdi lager man en variant.
- **Ingen ingrediens i bruk kan slettes, og standardoppføringene i katalogene kan aldri slettes.** Enhetstyper er faste (skrivebeskyttet).
- **Offisielle ingredienser skal seedes som verifiserte, uten gjettede allergener** (ingen offentlig datakilde; feil data er verre enn ingen).

**Allerede på Core sin egen liste** (ingen frontend-handling): opprydding når en konto slettes, verifisering gjennom Gatewayen, skrapetjeneste-konsument,
deling av oppskrifter, bildeopplasting, varsler når en ubekreftet ingrediens avgjøres, kontotype-avhengige grenser, produktmodell, måltidsplan og
handleliste. Merk: Core sitt punkt «allergen-tagging» foreslår en regelbasert seed — det er i strid med beslutningen over og bør rettes.

## 8. Avklaringer og idéer for brukergrensesnittet

- **Tekstmarkering (`.selectable`):** appen har ingen markerbar tekst som standard (se
  [06, B.7](./06-forms-and-design-system.md#b7-tekstmarkering-og-markør)). Avgjør senere hvor kopiering faktisk er nyttig
  og legg klassen `selectable` der: e-post/id-er i admin-tabellene (brukerliste, svarteliste), oppskriftsinstruksjoner og
  ingredienslister, juridiske tekster, og feilmeldinger man vil sende videre.
- **Sortering av kolonner** i katalog- og ingredienstabellene (i dag er de sortert på navn). Naturlig for enheter
  (forholdstall) og ingredienser (energi).
- **Ingredienstabell:** klikk på en rad for detaljvisning (næringsverdier, porsjoner, kilde). Hører sammen med
  ingrediens-editoren.
- **Antall lenker i headeren:** admin har 6 lenker og går til burger-menyen under 1200px. Blir det flere, vurder en
  gruppert/nedtrekksmeny for adminlenkene i stedet.
- **Tema og styling (lav prioritet, ikke en kjernefunksjon):** leke med fargetemaer og styling av komponentene (`theme.ts`, se
  [06](./06-forms-and-design-system.md), del B), uten å endre sidenes layout, og gjøre en gjennomgang av at alle sidene ser konsistente ut.
  Ting å se på i gjennomgangen: sidebredder (`MainContainer` bruker `lg` på katalogsiden, `xl` på ingredienssiden), tabell-, kort- og
  filterstil, merker (badges) og ikonbruk, lys/mørk modus og tilgjengelighet (ikke fargen alene). Kjent forskjell: de eldre
  mock-sidene i admin har emoji i tittelen (f.eks. «👥 Brukeradministrasjon»), de nye sidene har det ikke.
