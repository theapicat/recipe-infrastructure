# 05 – Adminpanelet

Adminpanelet ligger under `app/admin/` (egen top-level-mappe, **ikke** en route group), og er beskyttet av
`proxy.ts` sin rolle-sjekk (se [03](./03-auth-and-session.md#3-proxyts--nextjs-proxy-tidligere-middleware)).
Modenheten varierer mye fra side til side — dette dokumentet sier eksplisitt hva som er koblet til ekte
backend og hva som er UI-skisser.

## 1. Sideoversikt

| Side                                                        | Status                                                       | Beskrivelse                                                                                                                                                                                                                    |
| ----------------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/admin/dashboard`                                          | Statisk roadmap-widget                                       | En intern to-do/roadmap-sjekkliste (`initialRoadmap`, hardkodet i komponenten) — ikke en driftsdashboard koblet til noe API. Nyttig som prosjektstyringsverktøy for utviklerne selv, men bør ikke forveksles med systemstatus. |
| `/admin/users` + `/admin/users/[Id]` + `/admin/users/email` | **Ekte, koblet til backend**                                 | Se seksjon 2.                                                                                                                                                                                                                  |
| `/admin/whitelist`                                          | UI-skisse (`mockDomainsData`)                                | Ingen `agentInternal`-kall, ingen tilhørende `lib/models`.                                                                                                                                                                     |
| `/admin/categories`                                         | UI-skisse (`mockCategories`, `mockIngredients`, `mockUnits`) | Samme mønster.                                                                                                                                                                                                                 |
| `/admin/system`                                             | UI-skisse (`mockServices`, `mockRecentLogs`)                 | Samme mønster.                                                                                                                                                                                                                 |

## 2. Brukeradministrasjon — den ferdige delen

Dette er den mest komplette funksjonaliteten i hele appen. Flyt:

```
app/admin/users/page.tsx          → agentInternal.get("/api/admin/users") → AdminUserTable
app/admin/users/[Id]/page.tsx     → detaljvisning: AdminUserHeader, AdminUserActionPanel,
                                      AdminUserEditForm, AdminUserTimeline
app/admin/users/email/page.tsx    → AdminSendEmailForm, AdminUserCard
```

Handlinger tilgjengelig fra `AdminUserTable.tsx` / `AdminUserActionPanel.tsx`, alle via `agentInternal` →
tilsvarende `/api/admin/users/*`-rute → `agentAuthAdmin`:

- Lås / lås opp bruker (`lockUser` / `unlockUser`)
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
(`AdminUserQueryParams`/`PaginatedResponse`-modeller lagt til, men verken `agentAuthAdmin.getUsers()`,
route handleren eller selve siden brukte dem konsekvent). Dette er ryddet opp: `app/api/admin/users/route.ts`
henter nå en flat liste uten query-params, i tråd med at `app/admin/users/page.tsx` allerede gjør all
søk/filter/sortering/paginering client-side i en `useMemo`. De ubrukte modellene er slettet. Server-side
paginering kan bygges skikkelig senere når brukerlisten faktisk blir stor nok til å trenge det — se
[07 – Kjente problemer](./07-known-issues-and-tech-debt.md).

## 3. UI-skissene (whitelist/categories/system)

Disse følger **ikke** skjema-arkitekturen i [06](./06-forms-and-design-system.md) og har ingen
`agentInternal`-kall — all data er `const mock... = [...]` øverst i filen, og alle handlinger (opprett,
rediger, slett) muterer kun lokal React-state. De er nyttige som visuell spesifikasjon av hvordan
funksjonaliteten skal se ut, men **ingen** av dem er koblet til `recipe-core-api` eller
`recipe-authentication-api` ennå. Se
[07 – Kjente problemer](./07-known-issues-and-tech-debt.md#store-monolittiske-sider-uten-backend) for full
liste over slike sider (samme mønster finnes også i `(user)`-delen: recipes/mealplan/shoppinglist/import).
