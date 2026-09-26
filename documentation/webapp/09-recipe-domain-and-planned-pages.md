# 09 – Oppskriftsdomenet: Modell & Planlagte Sider

**Status: modellene i seksjon 1 er skrevet og justert mot `recipe-core-api` (2026-09-21). Oppskriftssidene
(`/user/recipes/*`, full CRUD + kokemodus + næringsfane) er bygget (2026-09-22–23) — se seksjon 0. Resten av
seksjon 2 er ikke bygget ennå.**

## 0. Oppskriftssidene (`/user/recipes/*`) — bygget

Full CRUD, lagdelt som beskrevet i [08, seksjon 6](./08-model-and-component-structure-proposal.md#6-konkret-migreringsrekkefølge-når-dere-er-klare):

- `app/(user)/user/recipes/page.tsx` → `components/recipes/RecipeManager.tsx`: liste med søk, kategorifilter og
  «kun favoritter», favorittmerking og sletting direkte fra kortet (`RecipeCard.tsx`, `RecipeFilterBar.tsx`).
- `app/(user)/user/recipes/create/page.tsx` og `[id]/edit/page.tsx` → felles `components/recipes/RecipeForm.tsx`
  (`IngredientListEditor.tsx`, `StepListEditor.tsx` for de dynamiske listene). PUT erstatter alt, som ingrediens-
  editoren.
- `app/(user)/user/recipes/[id]/page.tsx` → `components/recipes/RecipeDetailView.tsx`: hero, klientside
  porsjonsskalering (kun visning), ingredienser (bruker det denormaliserte `RecipeIngredient.name` — ikke oppslag),
  fremgangsmåte, favoritt/rediger/slett, og en fane for næringsinnhold (se under).
- `app/(user)/user/recipes/[id]/cook/page.tsx` — kokemodus, ekte data (2026-09-23): steg for steg med
  nedtellingstimer per steg (flere samtidig, med lyd og varsel når tiden er ute), Wake Lock (skjermen holdes på),
  porsjonsskalert ingrediensliste (hurtigvisning + full sjekkliste i en skuff). Lydet
  (`lib/audio/kitchenChime.ts`) er en frittstående, gjenbrukbar liten modul.
- **Næringsfanen** (`RecipeNutritionView.tsx`, hentet på forespørsel via `useRecipeNutrition.ts` — kun når fanen
  faktisk åpnes, siden beregningen skjer på serveren hver gang): to uavhengige valg — omfang (hele oppskriften vs.
  per porsjon, begge tallene ligger allerede i `RecipeNutrition`-svaret) og detaljnivå (enkel: energi/fett/
  karbohydrat/protein som fire ruter; utvidet: en vanlig næringsdeklarasjon inkl. «herav mettet»/«herav
  sukkerarter»/fiber/salt; detaljert: alt som faktisk er målt, gruppert som i ingrediens-editoren via
  `groupNutrients()`). Viser også hvor mange ingredienser som faktisk ble talt med og hvorfor resten ble hoppet
  over (`skippedLines`). `useNutrientDefinitions`/`groupNutrients` flyttet fra `components/admin/ingredients/` til
  `lib/nutrients/` siden oppskriftssiden nå bruker dem også.
- Hooks: `useRecipes`/`useRecipe` (samme mønster som ingrediensenes `useIngredients`/`useIngredient`),
  `useRecipeLookups` (kategorier, enheter, ingredienser — parallelt, som `useCatalogs`),
  `useIngredientDetailCache` (henter og cacher hele ingredienser, inkl. `portions`, på forespørsel når en
  ingrediens velges i en oppskriftslinje — til enhetsinnsnevringen under), `useRecipeNutrition` (lat henting av
  næringsberegningen). Domenelogikk (skjemaverdier, validering, request-mapping) i `recipeForm.ts`.
- **Enhetsvelgeren per ingredienslinje** viser kun enheter som faktisk kan regnes om til gram for den valgte
  ingrediensen: enheter av samme type som ingrediensens `primaryUnitTypeId` (universell omregning), pluss enhetene
  ingrediensen selv har en definert porsjon for (`Ingredient.portions[].unitId`, f.eks. melk sine
  desiliter/glass-liten/glass-stor) — se `components/recipes/recipeLookups.ts`, `unitsForIngredient()`. Porsjonene
  hentes på forespørsel (`GET /api/user/ingredients/{id}`) siden den lette søkelisten ikke har dem.
- **Ikke bygget i denne runden:** Ingredienslinjer kan ikke opprette en ny ubekreftet ingrediens fra skjemaet (kun
  beholde en eksisterende linje som allerede peker på én) — se [10, seksjon 2](./10-backlog.md).
- **Gateway-stiene er bekreftet 2026-09-23** mot `recipe-core-api`-kildekoden (ikke lenger antatt) — se
  `backend-notes.md`, B16–B18.

## 1. Datamodellene

`lib/models/recipes/`, `lib/models/ingredients/` og `lib/models/units/` inneholder DTO-ene for
oppskrifts-domenet, og speiler ledningsformatet til `recipe-core-api` 1:1 (`| null` for ukjente felt, enums som
strenger med stor forbokstav, egne request-modeller uten id-er — se
[04, seksjon 5](./04-api-integration-and-data-models.md#5-modellene-mot-recipe-core-api)).

Kort oppsummert: `Recipe` er strengt bruker-eid (`ownerUserId`), skiller manuelle fra skrapede oppskrifter via
`RecipeSource`, og henter ingredienser fra en delt `Ingredient`-katalog (med en `UnconfirmedIngredient`-vei for
brukerinnsendte ingredienser som ikke finnes der, med en review-livssyklus: `NotRequested` → `Pending` →
`Approved`/`Merged`/`Rejected`). Næring er modellert som en egen `NutrientDefinition`-katalog (skrivebeskyttet,
nøstet i grupper) + sparsomme `IngredientNutrientValue`-rader (ikke et fast sett faste felt), fordi kildedataen fra
Matvaretabellen er hierarkisk og de fleste matvarer bare har verdi for et delsett av næringsstoffene. Næring for en
oppskrift beregnes på forespørsel (`RecipeNutrition`) og lagres aldri.

Følger mønsteret fra [08 – Forslag: mappestruktur](./08-model-and-component-structure-proposal.md): én fil per
DTO, gruppert på domene, `page.tsx` tynn + feature-komponenter når sidene faktisk bygges.

## 2. Planlagte sider (ikke bygget)

`app/(user)/user/recipes/*` er bygget mot ekte backend, se seksjon 0. Resten under er fortsatt planer.

Nye sider som er planlagt basert på modelldesign-samtalen:

- **`app/(user)/user/ingredients/` (ny)** — søkbar oppslagsside der brukeren kan finne en ingrediens og se
  næringsinnhold, porsjonsstørrelser og en lenke til den offisielle Matvaretabellen-siden (`Ingredient.sourceUrl`).
  Tenkt som frittstående oppslag, ikke bundet til en oppskrift — "hva får jeg av å ete to gulrøtter"-type bruk.
- **Katalog-admin — gjort (`/admin/catalog`, se [05](./05-admin-panel.md)).** Dekker `IngredientCategory`,
  `RecipeCategory`, `Allergen`, `UnitType` (skrivebeskyttet), `Unit` og `SearchKeyword`. `NutrientDefinition`-katalogen er
  skrivebeskyttet i backend og får ingen admin-flate.
- **Ingrediens-admin** — en egen side (`/admin/ingredients`). **Full CRUD er bygget** (liste, utvidet visning, redigering med
  allergener, verifisering, oppretting og sletting i en skuff, se [05](./05-admin-panel.md), seksjon 4). Gjenstår:
  admin-køen for `UnconfirmedIngredient` — godkjenn som ny ingrediens (evt. avledet fra en eksisterende) eller slå sammen med en
  eksisterende (erstatter den i brukernes oppskrifter) — og avvis. Køen gjenbruker editoren.

Den første av punktene over er bygget; resten er ikke startet — dette er en oversikt for å ikke miste kontekst mellom
sesjoner.
