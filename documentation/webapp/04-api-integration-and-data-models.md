# 04 – API-integrasjon & Datamodeller

## 1. Lagene, i rekkefølge

```
Klientkomponent ("use client")
   │  agentInternal.get/post/put/delete<T>("/api/...", body)
   ▼
Route handler  app/api/**/route.ts        (server, kjører i Next.js)
   │  apiRoute(feilmelding, async (options) => { ... })
   │    └─ agentExternal.get/post/put/delete/postForm<T>("/auth/...", body, options)
   ▼
Recipe Gateway API (YARP, port 5000)      → validerer JWT, injiserer X-User-Id
   ▼
recipe-authentication-api (5001)  /  recipe-core-api (5002)
```

Route handlers er en **tynn oversettelsesjobb**, ikke forretningslogikk: de tar imot JSON fra klienten,
kaller `agentExternal` direkte, gjør eventuelt sesjonsarbeid (cookies via `sessionManager`), og
`apiRoute` pakker resultatet i en konsistent konvolutt (se punkt 3). Det finnes **ingen** mellomlag av
per-endepunkt-wrappere mellom route handler og `agentExternal`.

## 2. `lib/agent/` og `lib/http/` — filene

Appen har **nøyaktig to agenter**. Ikke legg til flere (ingen `agentRecipes.ts`, `agentCore.ts` osv.) — nye
endepunkter er nye kall til `agentExternal` direkte fra route handleren som trenger dem.

| Fil                          | Ansvar                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `lib/agent/agentInternal.ts` | `"use client"`. Same-origin `fetch` mot denne appens egne `/api/*`-ruter. Ingen auth-header — cookien følger automatisk. Generisk: `agentInternal.get<T>(url)` gir en `ApiResponse<T>`, dvs. en vanlig `Response` der `json()` er typet som `HttpResponse<T>`. Fanger 401, fornyer tokenet via `POST /api/auth/refresh` og gjentar kallet én gang — se [03](./03-auth-and-session.md#5-token-fornyelse-for-api-kall-agentinternal--apiauthrefresh). |
| `lib/agent/agentExternal.ts` | Server-only. Eneste sted som snakker med Gatewayen. Se detaljer under.                                                                                                                                                                                                                                                                                                                                                                              |
| `lib/agent/ApiError.ts`      | `Error`-subklasse med et `status`-felt — se seksjon 6.                                                                                                                                                                                                                                                                                                                                                                                              |
| `lib/agent/fetchWithTimeout` | `fetch` med 10 sekunders tidsgrense. Brukes av `agentExternal` og av `proxy.ts`.                                                                                                                                                                                                                                                                                                                                                                    |
| `lib/http/apiRoute.ts`       | Felles ramme for route handlers (ikke en agent) — se seksjon 3.                                                                                                                                                                                                                                                                                                                                                                                     |

### `agentExternal`

Metodene `get`, `post`, `put`, `delete` (JSON) og `postForm` (`x-www-form-urlencoded`, kreves av
OAuth2-endepunktene `/connect/*` og `/account/register`) er alle generiske: `agentExternal.get<T>(path, options?)`.

- **Sti relativt til `GATEWAY_URL`**, f.eks. `"/auth/account/me"` eller (senere) `"/user/recipes"`. URL-en bygges
  i agenten, så route handlers trenger ingen egne base-URL-konstanter.
- **Token:** `Authorization: Bearer <token>` hentes fra `sessionManager.getToken()`. Utelates hvis det ikke finnes
  noe token. `options.token` overstyrer — brukes kun rett etter innlogging, før cookien er satt.
- **Retur:** den parsede JSON-bodyen som `T`. En tom eller ikke-JSON body (204, eller Core sitt kontaktskjema som
  svarer med ren tekst) gir `undefined` — derfor bruker route handlers `result?.message`.
- **Feil:** kaster `ApiError` med Gatewayens faktiske statuskode. Meldingen hentes fra det første av disse feltene
  som finnes: `detail` (Core, ProblemDetails) → `message` (Auth API) → `error_description` → `error` (OpenIddict) →
  `title` (kun på 409, siden Core sin database-409 bare har `title`). Ellers brukes `options.errorMessage`, og til
  slutt en generell norsk standardtekst. `title` på 400/404 brukes bevisst ikke — den er engelsk og ikke
  presenterbar (bindingsfeil gir `title: "One or more validation errors occurred."`).
- **Nettverksfeil:** uoppnåelig Gateway → `ApiError` 503 ("Kunne ikke nå serveren…"), timeout → 504.
- **Refresh:** `agentExternal` fornyer **ikke** selv et utløpt token (se [03](./03-auth-and-session.md)).

## 3. Responskonvolutt: `HttpResponse<T>` og `apiRoute`

**Alle** route handlers under `app/api/**` som svarer klientkomponentene returnerer konvolutten:

```ts
interface HttpResponse<T = undefined> {
  statusCode: number;
  message: string;
  errors?: Record<string, string[]>;
  body?: T;
  timestamp?: string; // ISO-streng
}
```

Unntak: `/api/health` (egen `HealthResponse`-form) og Google-rutene (`/api/auth/google`, `/google-callback`) som
er ren redirect. `statusCode`-feltet i body er informativt — den faktiske HTTP-statuskoden på responsen er
autoritativ.

`apiRoute<T>(feilmelding, action)` i `lib/http/apiRoute.ts` bygger konvolutten for alle handlers:

```ts
export const POST = (request: Request) =>
  apiRoute("Kunne ikke sperre brukeren.", async (options) => {
    const data: LockUserRequest = await request.json();
    const result = await agentExternal.post<MessageResponse>(
      "/auth/admin/users/lock",
      data,
      options,
    );
    return { message: result?.message || "Brukeren har blitt sperret." };
  });
```

- `feilmelding` er den norske reservemeldingen. Den sendes til `action` som `options`, slik at `agentExternal`
  bruker den når backend ikke oppgir en brukbar melding — og `apiRoute` bruker den for alt som ikke er en
  `ApiError` (f.eks. ugyldig JSON i requesten). Brukeren får aldri en rå feiltekst som "Unexpected end of JSON".
- `action` returnerer `{ message, body?, status? }`. Suksess blir `HttpResponse<T>` med den statusen (standard 200).
- En `ApiError` — kastet av `agentExternal`, eller bevisst inne i `action` — propagerer sin egen melding og
  statuskode. Alt annet gir 400.

I klienten typer generikken `body`:

```ts
const res = await agentInternal.get<AdminUserListItem[]>("/api/admin/users");
if (res.ok) {
  const { body } = await res.json(); // body: AdminUserListItem[] | undefined
}
```

Feil leses fra `message` i konvolutten (`const data: Partial<HttpResponse> = await res.json().catch(() => ({}))`
der svaret kanskje ikke er JSON, f.eks. en HTML-feilside fra en proxy).

## 4. `lib/models/` — konvensjon

Én fil per DTO/interface, gruppert etter domene:

```
lib/models/
├── auth/                     # login, registrering, passord, profil (bruker-domenet)
├── admin/users/              # admin-spesifikke request/response-typer
├── enums/                    # f.eks. BlacklistType
├── public/                   # kontaktskjema o.l.
├── catalog/                  # CatalogResource (hvitliste over adminkatalogene) + CatalogModelMap
├── recipes/                  # Recipe, RecipeListItem, RecipeRequest, RecipeNutrition, ... (speiler recipe-core-api)
├── ingredients/              # Ingredient, IngredientListItem, IngredientRequest, NutrientDefinition, UnconfirmedIngredient, ...
├── units/                    # Unit, UnitType
├── httpResponse.ts
├── messageResponse.ts        # { message } — enkel bekreftelse fra Auth API
└── types.ts                  # UserRoleType + normalizeRole() — se 03-auth-and-session.md, seksjon 6
```

**Advarsel — filnavn må matche interface-navnet.** `lib/models/admin/users/BlacklistedEntry.ts` og
`DeleteAndBlacklistUserAdminRequest.ts` hadde til nylig byttet om innhold (filen med det ene navnet inneholdt
det andre interfacet). Dette er nå rettet — men understreker regelen: når du lager en ny modellfil, dobbeltsjekk
at filnavn og `export interface`-navn er identiske, ellers blir det umulig å navigere kodebasen etter navn.

## 5. Modellene mot `recipe-core-api`

Modellene i `recipes/`, `ingredients/` og `units/` speiler ledningsformatet (wire format) til `recipe-core-api`
1:1. Reglene som gjelder alle:

- **`| null`, ikke `?`,** for felt backend alltid sender men som kan være ukjente (`imageUrl: string | null`).
  `?` brukes kun i **request**-modeller, for felt klienten kan utelate.
- **Enums er strenger med stor forbokstav:** `"Manual" | "Scraped"`, `"Pending"`, `"ToTaste"` (også i query-strenger).
- **Navn og titler lagres lowercase** i backend (oppskriftstitler, ingrediensnavn, katalognavn, …) — kapitaliser
  ved visning, og lowercase aldri selv før sending. Unntak: næringsstoffnavn, enhetsforkortelser og fritekst.
- **Id-er er Guid-er satt av serveren.** Send aldri `id` ved opprettelse. Eneste unntak: `NutrientDefinition.id`
  er kildens tekstkode (`"Vit C"`) og må URL-encodes i stier.
- **Response- og request-modeller er forskjellige** (`Recipe` vs. `RecipeRequest`): requests har ingen id-er og
  ingen utledede felt.
- **`PUT` erstatter alt** for oppskrifter og ingredienser (barn får nye id-er) — send alltid hele objektet.
- **Ingen egen request-modell når den er identisk med response-modellen.** Bruk modellen direkte: `Omit<Unit, "id">`
  ved opprettelse (serveren tildeler id), hele `Unit` ved oppdatering. En egen request-modell lages kun når formen
  faktisk er forskjellig (`RecipeRequest` har ingen id-er/utledede felt og andre nøstede typer).

Det finnes fortsatt ingen `lib/models`-filer for måltidsplaner eller handlelister; disse sidene har heller ingen
ekte API-integrasjon ennå. Se [07 – Kjente problemer](./07-known-issues-and-tech-debt.md#store-monolittiske-sider-uten-backend)
for status per side.

## 6. Feilhåndteringsmønster (gjelder alle route handlers)

Feilhåndteringen er samlet i to funksjoner, ikke gjentatt i hver handler:

1. `agentExternal` kaster `ApiError(melding, status)` ved alle feil (HTTP-feil, uoppnåelig Gateway, timeout).
2. `apiRoute` fanger den og svarer `HttpResponse<undefined>` med `statusCode`/`message` fra feilen, og HTTP-status
   lik `error.status`.

`ApiError` (`lib/agent/ApiError.ts`) bærer Gatewayens faktiske HTTP-statuskode, som blir propagert videre i stedet
for å flates til 400. Dette er det `agentInternal.ts` bruker til å avgjøre om et mislykket kall skal utløse et
fornyelsesforsøk (kun ved nøyaktig 401) — se
[03 – Auth & sesjon, seksjon 5](./03-auth-and-session.md#5-token-fornyelse-for-api-kall-agentinternal--apiauthrefresh).
For feil som ikke er en `ApiError` (f.eks. `JSON`-feil på selve requesten) svarer `apiRoute` 400 med den norske
reservemeldingen.

Trenger en handler en bestemt statuskode for en feil den oppdager selv, kaster den `new ApiError("Melding", 400)`
inne i `action` (f.eks. manglende felt i `app/api/auth/confirm-email`).

## 7. Mal: slik legger du til et nytt backend-endepunkt

Dette er den faste fremgangsmåten for **alle** nye funksjoner som snakker med en backend (Core API, Auth API,
og fremtidige tjenester). Følg den, så ser alle endepunkter like ut og kan leses uten å måtte lære et nytt
mønster hver gang.

**1. Modeller** — `lib/models/<domene>/`, én fil per interface, filnavn == interface-navn (se seksjon 4 og 5).
Lag separate response- og request-modeller. Kopier ledningsformatet fra backend; ikke oppfinn egne former.

**2. Route handler** — `app/api/<sti>/route.ts`. Stien speiler Gateway-stien, slik at den er forutsigbar:
Gateway `/user/recipes` → `app/api/user/recipes/route.ts`, Gateway `/admin/allergens` →
`app/api/admin/allergens/route.ts`. (Auth API sine admin-endepunkter ligger historisk under
`app/api/admin/users/*` og `app/api/auth/*`; det er ingen kollisjon — Core og Auth har ulike stinavn.)
Bruk alltid `apiRoute` + `agentExternal`, aldri rå `fetch` og aldri egen `try/catch`:

```ts
// app/api/user/recipes/route.ts
export const GET = () =>
  apiRoute<RecipeListItem[]>("Kunne ikke hente oppskrifter.", async (options) => {
    const recipes = await agentExternal.get<RecipeListItem[]>("/user/recipes", options);
    return { message: "Oppskrifter hentet.", body: recipes };
  });

export const POST = (request: Request) =>
  apiRoute<Recipe>("Kunne ikke opprette oppskriften.", async (options) => {
    const data: RecipeRequest = await request.json();
    const recipe = await agentExternal.post<Recipe>("/user/recipes", data, options);
    return { message: "Oppskriften ble opprettet.", body: recipe, status: 201 };
  });
```

Regler og fallgruver:

- **Første argument til `apiRoute` er alltid en norsk reservemelding** som beskriver hva som feilet ("Kunne ikke …").
  Send `options` videre til `agentExternal`-kallet, slik at meldingen også brukes når backend ikke gir en.
- **Sti til `agentExternal` er relativ til `GATEWAY_URL`** (`"/user/recipes"`, `"/auth/account/me"`), aldri en full URL.
- **Type `agentExternal`-kallet** med responsen: `agentExternal.get<T>(...)`. Bruk `<undefined>` (eller utelat) for
  204-svar. Tomme svar gir `undefined` — les meldinger som `result?.message`.
- **Dynamiske segmenter:** `(_request: Request, { params }: { params: Promise<{ id: string }> })` — `params` er en
  Promise i denne Next-versjonen. Tekst-id-er (f.eks. næringsstoff-koder som `"Vit C"`) må gjennom
  `encodeURIComponent`. Query-parametere bygges med `URLSearchParams` og legges på stien.
- **Route-filer kan kun eksportere HTTP-metoder** (`GET`, `POST`, ...) og Next-konfig. Delt logikk mellom to handlere
  kan derfor ikke eksporteres fra den ene route-filen — legg den i `lib/` eller (hvis den er liten) dupliser den med en
  kommentar (slik `register` gjør med innloggingen).
- **Sesjonsarbeid** (cookies) gjøres inne i `action` via `sessionManager` — aldri `cookies()` direkte.
- **Egne valideringsfeil** kastes som `throw new ApiError("Melding", 400)` inne i `action`.
- **Bruk `status` i returverdien** når backend svarer noe annet enn 200 (f.eks. `201` ved opprettelse).
- **Nye gateway-kall går alltid via `agentExternal`** (som bruker `fetchWithTimeout`) — se
  [03](./03-auth-and-session.md#2-to-http-klienter--ikke-bland-dem). Unntak er kun `proxy.ts`.

**3. Klient** — `agentInternal.<metode><T>("/api/<sti>")` fra en klientkomponent (skjema via
`components/forms/**`, se [06](./06-forms-and-design-system.md)). `T` er typen på `body`. Vis `message` fra
konvolutten ved feil; les `body` ved suksess:

```ts
const res = await agentInternal.post<Recipe>("/api/user/recipes", values);
const data = await res.json();
if (res.ok && data.body) {
  /* … */
} else {
  setErrorMessage(data.message);
}
```

**4. Dokumentasjon** — legg endepunktet i listen i [02, seksjon 6](./02-routing-and-pages.md#6-api-ruter-appapiroutets),
og oppdater [07](./07-known-issues-and-tech-debt.md) når en mock-side kobles til ekte data.

**5. Før du er ferdig** — `npx tsc --noEmit`, `npm run lint` og `npx prettier --check <endrede filer>` skal være
rene. `res.json()` er løst typet, så `tsc` fanger ikke alle feil mellom handler og komponent: les gjennom
begge sider av grensesnittet.

### 7.1 Variant: én dynamisk rute for flere like ressurser

Når flere backend-ressurser har **identisk kontrakt** (samme HTTP-metoder, samme feil, bare ulik modell), lages én
dynamisk rute i stedet for ett filsett per ressurs. Eksempelet er de seks adminkatalogene:
`app/api/admin/[resource]/route.ts` (GET, POST, PUT) og `app/api/admin/[resource]/[id]/route.ts` (DELETE).

```ts
export const GET = (_request: Request, { params }: CatalogContext) =>
  apiRoute<CatalogItem[]>("Kunne ikke hente katalogen.", async (options) => {
    const resource = await resolveCatalogResource(params); // 404 hvis ikke på hvitlisten
    const items = await agentExternal.get<CatalogItem[]>(`/admin/${resource}`, options);
    return { message: "Katalogen ble hentet.", body: items };
  });
```

Regler:

- **Hvitliste er obligatorisk.** Segmentet kommer fra brukeren; uten en liste kan ruten misbrukes til å nå andre
  admin-endepunkter. Listen (`CATALOG_RESOURCES`) og en `isCatalogResource`-vakt ligger i
  `lib/models/catalog/CatalogResource.ts`; `resolveCatalogResource` (`lib/http/`) kaster `ApiError` 404 for ukjente navn
  og 405 for skriving mot skrivebeskyttede (`READ_ONLY_CATALOG_RESOURCES`). Hjelpefunksjonen ligger i `lib/`, ikke i
  route-filen, siden route-filer kun kan eksportere HTTP-metoder.
- **Typekartet** `CatalogModelMap` kobler hvert navn til sin modell. UI-konfigurasjonen
  (`components/admin/catalog/catalogConfig.ts`) er en `Record<WritableCatalogResource, …>` (hvitlisten minus de
  skrivebeskyttede, i dag `unit-types`) — legger man til en katalog i hvitlisten uten å konfigurere den, feiler
  TypeScript. En skrivebeskyttet ressurs kan leses (som data), men gir 405 ved skriving og har ingen fane.
- **Avvikende ressurser får egen rute.** En statisk mappe (`app/api/admin/ingredients/`) har forrang over
  `[resource]`, så en ressurs som avviker fra kontrakten (f.eks. ingredienser med barnelister og `PUT` med id i stien)
  lages som vanlig, egen rute etter malen i seksjon 7 — uten å røre den dynamiske. Ingredienslisten er et eksempel:
  `app/api/admin/ingredients/route.ts`.
- Klientsiden er generisk på samme måte (`CatalogTable`, `CatalogItemForm`), og kun det som faktisk avviker (enheter:
  ekstra kolonner og et eget skjema) er eget.
