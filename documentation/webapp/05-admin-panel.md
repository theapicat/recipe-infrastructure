# 05 – Adminpanelet

Adminpanelet ligger under `app/admin/` (egen top-level-mappe, **ikke** en route group), og er beskyttet av
`proxy.ts` sin rolle-sjekk (se [03](./03-auth-and-session.md#3-proxyts--nextjs-proxy-tidligere-middleware)).
Modenheten varierer mye fra side til side — dette dokumentet sier eksplisitt hva som er koblet til ekte
backend og hva som er UI-skisser.

## 1. Sideoversikt

| Side                                                        | Status                                       | Beskrivelse                                                                                                                                                                                                                    |
| ----------------------------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/admin/dashboard`                                          | Statisk roadmap-widget                       | En intern to-do/roadmap-sjekkliste (`initialRoadmap`, hardkodet i komponenten) — ikke en driftsdashboard koblet til noe API. Nyttig som prosjektstyringsverktøy for utviklerne selv, men bør ikke forveksles med systemstatus. |
| `/admin/users` + `/admin/users/[Id]` + `/admin/users/email` | **Ekte, koblet til backend**                 | Se seksjon 2.                                                                                                                                                                                                                  |
| `/admin/whitelist`                                          | UI-skisse (`mockDomainsData`)                | Ingen `agentInternal`-kall, ingen tilhørende `lib/models`.                                                                                                                                                                     |
| `/admin/catalog`                                            | **Ekte, koblet til backend**                 | De delte katalogene: oppskrifts- og ingrediens­kategorier, allergener, søkeord og enheter (vertikal meny) — se seksjon 3.                                                                                                      |
| `/admin/ingredients`                                        | **Ekte, koblet til backend** (full CRUD)     | Ingrediensregisteret: søk og filtre, utvidet visning, redigering, verifisering, oppretting og sletting i en skuff — se seksjon 4.                                                                                              |
| `/admin/system`                                             | UI-skisse (`mockServices`, `mockRecentLogs`) | Samme mønster.                                                                                                                                                                                                                 |

## 2. Brukeradministrasjon — den ferdige delen

Dette er den mest komplette funksjonaliteten i hele appen. Flyt:

```
app/admin/users/page.tsx          → agentInternal.get("/api/admin/users") → AdminUserTable
app/admin/users/[Id]/page.tsx     → detaljvisning: AdminUserHeader, AdminUserActionPanel,
                                      AdminUserEditForm, AdminUserTimeline
app/admin/users/email/page.tsx    → AdminSendEmailForm, AdminUserCard
```

Handlinger tilgjengelig fra `AdminUserTable.tsx` / `AdminUserActionPanel.tsx`, alle via `agentInternal` →
tilsvarende `/api/admin/users/*`-rute → `agentExternal` (mot Auth API sine `/auth/admin/*`-endepunkter):

- Lås / lås opp bruker (`/api/admin/users/lock` / `unlock`)
- Bekreft e-post manuelt / send bekreftelse på nytt
- Send passord-tilbakestilling på vegne av bruker
- Send fritekst-e-post til bruker
- Slett bruker, eller slett + svartelist bruker
- Hent og administrer svarteliste (`AdminBlacklistTable.tsx`)

Modeller: `lib/models/admin/users/*.ts` — én fil per request/response-type. Se
[04 – API-integrasjon](./04-api-integration-and-data-models.md#4-libmodels--konvensjon) for regelen om at
filnavn må matche interface-navn (nylig rettet for `BlacklistedEntry`/`DeleteAndBlacklistUserAdminRequest`).

### Paginering: bevisst client-side (for nå)

Det fantes tidligere en påbegynt, ikke fullført migrering til server-side paginering
(`AdminUserQueryParams`/`PaginatedResponse`-modeller lagt til, men verken route handleren eller selve siden brukte
dem konsekvent). Dette er ryddet opp: `app/api/admin/users/route.ts` henter nå en flat liste uten query-params, i tråd med at `app/admin/users/page.tsx` allerede gjør all
søk/filter/sortering/paginering client-side i en `useMemo`. De ubrukte modellene er slettet. Server-side
paginering kan bygges skikkelig senere når brukerlisten faktisk blir stor nok til å trenge det — se
[07 – Kjente problemer](./07-known-issues-and-tech-debt.md).

## 3. Katalog (`/admin/catalog`)

Erstatter den gamle mock-siden `/admin/categories`. Administrerer katalogene i `recipe-core-api`:
**oppskriftskategorier**, **ingrediens­kategorier**, **allergener**, **søkeord** og **enheter**. Menyen er vertikal (til
venstre), gruppert med overskrifter — oppskrifter / ingredienser / enheter — og antall per katalog; på smale skjermer
(under 48em) blir den en horisontal rad som scroller sideveis. «Råvareregisteret» fra mocken er _ikke_ en del av denne
siden — ingredienser har en egen side (seksjon 4).

**Enhetstyper (vekt/volum/antall) har ingen egen fane:** de er uforanderlige og brukes overalt. De lastes kun som data —
til «Enhetstype»-kolonnen, enhetsfilteret og enhetsskjemaet. `unit-types` står i `READ_ONLY_CATALOG_RESOURCES`, så API-ruten
avviser skriving med 405 (næringsberegningen i backend finner vekt/volum via typenes navn).

```
app/admin/catalog/page.tsx        → tynn server-side (tittel + <CatalogManager />), ingen <Suspense>
components/admin/catalog/
  CatalogManager.tsx              → vertikal meny (grupper), antall i menyen
  CatalogPanel.tsx                → én katalog: søk, tabell, opprett/rediger (modal), slett (bekreftelse)
  CatalogTable.tsx                → generisk tabell + klientside-paginering (se 06, B.8)
  CatalogItemForm.tsx             → opprett/rediger for kataloger med kun navn
  UnitForm.tsx / UnitFilters.tsx  → enhetsskjema (navn, forkortelse, type, forholdstall) og filtre (type, forholdstall fra/til)
  deleteBlockedReason.ts          → hvorfor «Slett» er deaktivert (standardoppføring / i bruk / har varianter)
  catalogPayload.ts               → fjerner serverstyrte felt (isSystem, usageCount) fra PUT-body
  useCatalogs.ts                  → laster alle seks katalogene parallelt; reload(resource) etter endring
  catalogConfig.ts / unitTypeInfo.ts / catalogValidation.ts
components/common/                → TablePagination + usePagedItems (se 06, B.8) og DeleteConfirmModal (felles slettedialog for kataloger og ingredienser)
app/api/admin/[resource]/…        → dynamisk rute mot Core (hvitliste, se 02 og 04, seksjon 7.1)
```

Bevisste valg:

- **Ingen klient-cache.** Backend cacher katalogene og invalidérer ved skriving. Backend svarer `200`/`204` uten
  body på `PUT`/`DELETE`, så listen leses på nytt etter hver endring. Alle seks lastes ved oppstart (små lister,
  ~430 rader totalt) — det gir antall i menyen og enhetstypene enhetsskjemaet trenger.
- **Valget i menyen er lokal state, ikke i URL-en** — da trenger siden verken `useSearchParams` eller `<Suspense>`.
- **Ingen «status»/«aktiv»-felt:** nye oppføringer er tilgjengelige umiddelbart. Antall oppskrifter/ingredienser per
  oppføring er utsatt (backend har ikke endepunktet) — se [10](./10-backlog.md).
- **Enhetsfilter:** «Enhetstype» og «Forholdstall fra/til» (begge grenser inkludert, norsk desimalkomma). Kombineres med
  søkefeltet; «Nullstill filtre» og et «Viser x av y»-sammendrag vises når et filter er aktivt.

**Validering på frontend** (backend sjekker kun tomt navn → 400 og duplikat/fremmednøkkel → 409, og _ingenting_ for
forkortelse/forholdstall):

| Felt                | Regel                                                                                                 |
| ------------------- | ----------------------------------------------------------------------------------------------------- |
| Navn                | Ikke tomt; ikke duplikat (uavhengig av store/små bokstaver, trimmet, sammenpressede mellomrom)        |
| Forkortelse (enhet) | Ikke tom; unik uavhengig av store/små bokstaver (`l` og `L` er samme symbol). Vises med original case |
| Enhetstype          | Må velges                                                                                             |
| Forholdstall        | Tall > 0, maks 10 desimaler, norsk desimalkomma. **Låst til 1 for «antall»**                          |

Navn sendes som skrevet (backend lowercaser) og vises med stor forbokstav. Å endre forholdstall eller enhetstype på en
enhet gir en advarsel i bekreftelsesdialogen: det endrer næringsberegningen for alle oppskrifter som bruker enheten.
Å slette en oppføring som er i bruk gir `409`, som vises som en forståelig melding. **Slett er deaktivert (med begrunnelse)** for
standardoppføringer (`isSystem`) og oppføringer i bruk (`usageCount`) — når backend leverer de feltene, se [10](./10-backlog.md), seksjon 7 (B7);
før det forblir knappen aktiv og 409 er siste skanse.

## 4. Ingredienser (`/admin/ingredients`)

Hele ingredienslisten (~1 565 rader, `GET /admin/ingredients`) lastes én gang og søkes/filtreres i klienten, 50 rader per side
som standard (25/50/100 kan velges, se [06, B.8](./06-forms-and-design-system.md#b8-lange-lister-og-paginering)), sortert på
navn. Filtre: **søk** (ingrediensnavn _og_ søkeord, som backend), **kategori**, **inneholder allergen**, **søkeord**,
**verifisert** og **opprinnelse** (offisiell/egen). Kolonner: navn (med «Variant» under varianter), kategori, standardenhet, energi per
100 g, allergener og verifisert (ikon + tekst, bevisst dempet), og — når backend leverer det — opprinnelse. Opprinnelse-filteret er
deaktivert («Venter på backend») og kolonnen skjult til backend leverer `isOfficial` på listen
([10](./10-backlog.md), seksjon 7, B2): listeradene har ingen kilde-id å utlede det fra, mens skuffen utleder det fra kilde-id. **Full CRUD** skjer i en skuff til høyre — se under.

```
app/admin/ingredients/page.tsx                  → tynn server-side
app/api/admin/ingredients/route.ts              → GET (liste), POST (opprett)      — egen statisk rute
app/api/admin/ingredients/[id]/route.ts         → GET (full ingrediens), PUT, DELETE
app/api/user/nutrient-definitions/route.ts      → GET (næringsstoffkatalogen, 57 stk; admin-token godtas på /user/**)
components/admin/ingredients/
  IngredientManager.tsx                         → filtre, oppslag id → navn, «Ny ingrediens», eier skuffen
  IngredientTable.tsx                           → tabell + paginering; klikk på rad åpner skuffen
  IngredientDrawer.tsx                          → skuffen: visning / redigering / oppretting, forrige/neste, verifiser, slett
  IngredientDetailView.tsx                      → skrivebeskyttet utvidet visning (delbar — brukerens oppslag skal gjenbruke den)
  IngredientForm.tsx                            → editoren (opprett og rediger)
  ingredientForm.ts                             → skjema ⇄ request-mapping og all validering
  nutrientGrouping.ts / ingredientLookups.ts    → gruppering av næringsstoffer (hoved-/undergrupper), id → navn
  useIngredients.ts / useIngredient.ts / useNutrientDefinitions.ts
```

**Skuffen** (bred, til høyre) lar listen stå urørt bak, med filtre og side intakte, så admin kan gå fra ingrediens til
ingrediens uten å miste plassen: **forrige/neste** følger listens rekkefølge (filtrert og sortert), med posisjon «3 / 120».

| Modus       | Innhold                                                                                                                                                                                                                                                                                |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Visning** | Nøkkelfakta (kategori, enhet, energi kcal/kJ, spiselig del, variant av, kilde), allergener, søkeord, porsjoner og næringsverdier gruppert etter næringsstoffgruppe (alle grupper åpne). Handlinger: **Rediger**, **Verifiser**/**Fjern verifisering**, **Opprett variant**, **Slett**. |
| **Rediger** | Alle felt (offisielle: se låsingen under): grunndata, allergener, søkeord, kilde/variant, porsjoner og alle næringsstoffer (tomt felt = ikke målt, 0 = målt til null). `PUT` erstatter alt, så hele settet sendes — inkludert kildens id per næringsverdi, som ellers ville gått tapt. |
| **Opprett** | Fra bunnen, eller **avledet fra en eksisterende ingrediens** («Basert på …» / «Opprett variant»): skjemaet fylles ut fra basen (backend kopierer ikke selv), `variantOfIngredientId` settes, navn og kilde tømmes, og den nye starter uverifisert.                                     |

Regler (frontend håndhever; backend-ønsker i [10](./10-backlog.md), seksjon 7):

- **Offisielle ingredienser er delvis låst.** En offisiell ingrediens er kildedata fra det offentlige (Matvaretabellen) og skal være
  identisk med kilden. Derfor er **navn, energi (kcal/kJ), spiselig del, alle næringsverdier, kilde-id og kilde-URL låst** (deaktiverte
  felt med lås, en forklaring øverst og en «Opprett variant»-snarvei). Det vi selv kuraterer kan endres: **allergener, søkeord,
  kategori, enhetstype/standardenhet, porsjoner** og verifisering. Vil man endre en låst verdi, oppretter man en **variant** — den er
  «Egen» og fullt redigerbar. En ingrediens regnes som offisiell når den har kilde-id (til backend leverer `isOfficial`, se
  [10](./10-backlog.md), seksjon 7, B2), og vises med merket **Offisiell**/**Egen**. Kilde-id er forbeholdt offisielle ingredienser og tilbys ikke
  på egne; kilde-URL er en fri referanse på egne.
- **Handlingene ligger fast øverst i skjemaet:** en linje med **Verifisert**, **Avbryt** og **Lagre/Opprett** følger med når man scroller i
  det lange skjemaet (festet rett under skuffens topplinje). «Slett» hører hjemme i visningen, ikke i redigeringsskjemaet.
- **Verifisering krever næringsverdier** (minst ett næringsstoff). Ellers er «Verifiser» deaktivert med begrunnelse, og
  «Verifisert» i skjemaet kan ikke slås på. Å fjerne verifisering er alltid lov. Verifisering sender i dag hele ingrediensen
  (`PUT`); et eget lett endepunkt er ønsket.
- **Sletting er blokkert** (knapp deaktivert med begrunnelse) når ingrediensen har varianter (regnes ut fra listen) eller er i bruk
  (`usageCount`, når backend leverer det). Backend sin 409 vises som en forståelig melding som siste skanse.
- **Validering** speiler backend og legger på det backend ikke sjekker ennå: navn påkrevd og unikt (uavhengig av store/små
  bokstaver), kategori/enhetstype/standardenhet påkrevd og standardenheten må høre til enhetstypen, kcal ≥ 0, kJ ≥ 0, spiselig
  del i (0, 100], kilde-URL må være `http(s)`, næringsverdier ≥ 0, porsjoner med gram > 0 og unik enhet, ikke variant av seg selv.
- **Porsjoner** velges i to steg (2026-09-23): først enhetstype (vekt/volum/antall), så enhet — enhetslisten filtreres til den
  valgte typen, og vekt er i tillegg begrenset til gram/hektogram/kilogram (mikrogram/milligram-variantene finnes kun i
  katalogen for næringsstoffenes skyld, ikke til bruk i porsjoner) — se `lib/units/unitTypeInfo.ts`, `unitsOfType()`.
- **Ulagrede endringer:** lukker man skuffen, blar eller bytter modus med endringer, spørres det om forkasting. (Ingen egen
  lagre-bekreftelse som i profilskjemaet — admin redigerer mange ingredienser, og en dialog per lagring ville vært i veien.)
- **Allergener** vises alltid med forbeholdet «ingen registrert betyr ikke at ingrediensen er fri for allergener» — dataene er
  ufullstendige (se [10](./10-backlog.md), seksjon 7, B8–B9).

**Ikke bygget ennå** (se [10](./10-backlog.md)): godkjenningskøen for brukeres ubekreftede ingredienser (godkjenn som ny — evt.
avledet fra en eksisterende — eller slå sammen med en eksisterende; gjenbruker editoren), massehandlinger (krever
backend-endepunkter), og brukerens ingrediensoppslag (`/user/ingredients`, gjenbruker `IngredientDetailView`).

## 5. UI-skissene (whitelist/system)

Disse følger **ikke** skjema-arkitekturen i [06](./06-forms-and-design-system.md) og har ingen
`agentInternal`-kall — all data er `const mock... = [...]` øverst i filen, og alle handlinger (opprett,
rediger, slett) muterer kun lokal React-state. De er nyttige som visuell spesifikasjon av hvordan
funksjonaliteten skal se ut, men **ingen** av dem er koblet til `recipe-core-api` eller
`recipe-authentication-api` ennå. Se
[07 – Kjente problemer](./07-known-issues-and-tech-debt.md#store-monolittiske-sider-uten-backend) for full
liste over slike sider (samme mønster finnes også i `(user)`-delen: recipes/mealplan/shoppinglist/import).
