# 08 – Forslag: Mappestruktur for Modeller & Komponenter

**Status: kjerneopprydningen i seksjon 2 og `ContactForm`-flyttingen i seksjon 4 er gjennomført
(2026-09-13).** Domenemappene i seksjon 3 og 5 er fortsatt bare et forslag — opprettes når hvert domene
faktisk bygges. Dette dokumentet beskriver hvordan `lib/models/` og
`components/` bør utvides _før_ oppskrifter, måltidsplan, handleliste og de resterende admin-sidene
(kategorier, whitelist, system) migreres fra mock-data til ekte backend-integrasjon. Målet er å unngå å
gjenta mønsteret som allerede finnes for disse sidene i dag: ~4300 linjer fordelt på 8 sider, alt inline i
`page.tsx`, ingen delte modeller, ingen delte komponenter (se
[07 – Kjente problemer](./07-known-issues-and-tech-debt.md#store-monolittiske-sider-uten-backend)).

Auth- og admin/users-delen av kodebasen viser at mønsteret (page → container → form/feature-komponent →
felt, én modellfil per DTO gruppert på domene) fungerer godt i praksis. Forslaget under er å bruke nøyaktig
det samme mønsteret for de nye domenene, ikke noe nytt.

## 1. `lib/models/` — dagens struktur

```
lib/models/
├── auth/                       # login, registrering, passord, profil
├── admin/users/                # brukerdata, lås/svarteliste-requests
├── enums/                      # BlacklistType
├── public/                     # ContactRequest
├── httpResponse.ts             # delt, ligger i rot
└── types.ts                    # UserRoleType, ligger i rot
```

## 2. Opprydning før noe nytt legges til

- ✅ **`PaginatedResponse` og `AdminUserQueryParams` er slettet, ikke flyttet.** Den opprinnelige planen var å
  flytte `PaginatedResponse.ts` til `lib/models/`-rot (parallelt med `HttpResponse.ts`), men den halvferdige
  paginerings-migreringen den hørte til ble i stedet rullet tilbake til dagens fungerende client-side
  filtrering (se [07](./07-known-issues-and-tech-debt.md)). Begge modellene er derfor slettet siden ingenting
  bruker dem lenger. **Når** server-side paginering faktisk bygges senere (for brukerlisten, eller for en ny
  liste som oppskrifter), gjelder fortsatt prinsippet: en generisk `PaginatedResponse<T>`-wrapper hører hjemme
  i `lib/models/`-rot, ikke i en domenemappe.
- ✅ **`lib/models/auth/openIddictResponse.ts`, `lib/models/auth/deleteProfileRequest.ts`,
  `lib/models/user/user.ts`** — alle ubrukte, slettet.
- ✅ **`UserRoleType`** er nå `"admin" | "user"` (små bokstaver, slik backend sender dem), og `normalizeRole()` i
  `lib/models/types.ts` brukes overalt en rolle kommer inn i appens tilstand, inkludert `google-callback/route.ts`.

## 3. Ny struktur — legg til domenemapper etter behov, ikke på forskudd

**Anbefaling: ikke opprett tomme mapper nå.** Opprett `lib/models/<domene>/` idet dere faktisk begynner å
bygge backend-integrasjonen for det domenet — akkurat som `admin/users/` ble til da adminpanelet for brukere
ble bygget. Konvensjonen å følge når det skjer:

```
lib/models/
├── recipes/
│   ├── Recipe.ts                    # kjerne-DTO (matcher GET /recipes/{id})
│   ├── RecipeListItem.ts            # slankere variant til listevisning (jf. AdminUserListItem vs. AdminUserDetails)
│   ├── RecipeIngredient.ts
│   ├── RecipeStep.ts
│   ├── CreateRecipeRequest.ts
│   └── UpdateRecipeRequest.ts
├── mealplan/
│   ├── MealPlanEntry.ts
│   ├── MealPlanWeek.ts
│   └── AddMealPlanEntryRequest.ts
├── shoppinglist/
│   ├── ShoppingListItem.ts
│   └── GenerateShoppingListRequest.ts
└── admin/
    ├── categories/                  # når /admin/categories går fra mock til ekte
    └── whitelist/                   # når /admin/whitelist går fra mock til ekte
```

Én fil per DTO, filnavn == interface-navn (se den ombyttede `BlacklistedEntry`/`DeleteAndBlacklistUserAdminRequest`-
saken i [07](./07-known-issues-and-tech-debt.md) for hvorfor dette håndheves strengt).

## 4. `components/` — dagens struktur

```
components/
├── admin/
│   └── users/
│       ├── detail/
│       └── email/
├── containers/                       # MainContainer/AsyncMainContainer
├── forms/
│   ├── auth/
│   ├── common/                       # FormContext, FormField, CreateFormContainer, EditFormContainer
│   └── public/                       # ContactForm.tsx — flyttet hit, speiler lib/models/public/
└── layout/
    └── header/
```

✅ `ContactForm.tsx` er flyttet fra `components/forms/ContactForm.tsx` til
`components/forms/public/ContactForm.tsx` for å speile `lib/models/public/`.

## 5. Ny struktur for kommende domener

Samme prinsipp som modellene: opprett når domenet faktisk bygges, ikke før.

```
components/
├── recipes/
│   ├── RecipeCard.tsx                # gjenbrukes i liste, dashboard-widgets, søk
│   ├── RecipeFilterBar.tsx
│   ├── RecipeForm.tsx                # erstatter inline-skjemaet i recipes/create og recipes/[id]/edit
│   ├── IngredientListEditor.tsx
│   └── StepListEditor.tsx
├── mealplan/
│   ├── WeekGrid.tsx
│   ├── MealSlotCard.tsx
│   └── MealPlanForm.tsx
├── shoppinglist/
│   ├── ShoppingListItemRow.tsx
│   └── ShoppingListGenerator.tsx
└── admin/
    ├── categories/
    └── whitelist/
```

Når disse bygges, gjelder samme lagdeling som i [06 – Skjemaer & designsystem](./06-forms-and-design-system.md):
`page.tsx` blir tynn, feature-komponenten eier state og kaller `agentInternal`, og
`CreateFormContainer`/`EditFormContainer`/`FormField` gjenbrukes i stedet for at hver side bygger sin egen
`<Paper><form>`-oppsett fra bunnen (slik `recipes/create/page.tsx`, `recipes/[id]/edit/page.tsx` osv. gjør i
dag).

## 6. Konkret migreringsrekkefølge når dere er klare

Anbefalt rekkefølge — start med oppskrifter siden måltidsplan og handleliste begge refererer til dem:

1. `lib/models/recipes/*` + `agentRecipes.ts` (samme mønster som `agentAuth.ts`) + `app/api/recipes/**`
   route handlers.
2. Bryt `app/(user)/user/recipes/page.tsx` (541 linjer) opp i `page.tsx` (tynn) +
   `components/recipes/RecipeCard.tsx` + `RecipeFilterBar.tsx`, koblet til ekte data.
3. Gjenta for `recipes/create` og `recipes/[id]/edit` med en delt `RecipeForm.tsx` (de to sidene gjør i dag
   nesten identisk skjemaarbeid inline, hver for seg).
4. `recipes/[id]/page.tsx` og `recipes/[id]/cook/page.tsx` — detaljvisning og "kokemodus", begge leser samme
   `Recipe`-modell.
5. Deretter måltidsplan (`lib/models/mealplan/*`, `agentMealplan.ts`) — den refererer allerede til
   oppskrifter (`MOCK_USER_RECIPES` peker på recipe-data), så den bør komme etter punkt 1–4.
6. Til slutt handleliste, som typisk genereres _fra_ måltidsplanen.

Adminsidene (`whitelist`, `categories`, `system`) kan tas uavhengig av dette løpet — de har ingen avhengighet
til oppskrifts-domenet.
