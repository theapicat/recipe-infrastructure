# 02 – Ruting & Sider

## 1. App Router og route groups

Alle sider ligger under `app/`. Mappenavn i parenteser er **route groups** — de påvirker layout/organisering,
men vises aldri i URL-en:

| Route group      | Formål                                                                              | Eksempel-URL                                         |
| ---------------- | ----------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `(auth)`         | Innlogging, registrering, gjenoppretting                                            | `/login`, `/register`, `/recover`, `/reset-password` |
| `(info)`         | Offentlig informasjon                                                               | `/about`, `/contact`, `/faq`, `/features`, `/status` |
| `(legal)`        | Juridiske dokumenter, med egen sidemeny-layout                                      | `/legal`, `/legal/terms`, `/legal/privacy`, ...      |
| `(user)`         | Alt bak innlogging for vanlige brukere                                              | `/dashboard`, `/user/recipes`, `/user/mealplan`, ... |
| — (ingen gruppe) | `app/confirm-email`, `app/page.tsx` (forside), `app/error.tsx`, `app/not-found.tsx` | `/confirm-email`, `/`                                |
| `app/admin/`     | Adminpanelet (egen top-level-mappe, ikke en route group)                            | `/admin/dashboard`, `/admin/users`, ...              |

`(user)/user` har i tillegg en nøstet gruppe `(account)` for `/user/profile` og `/user/settings` — samme
mønster, bare ett nivå dypere.

## 2. Hvilke ruter er beskyttet, og hvordan

Tilgangskontroll skjer **ikke** i den enkelte `page.tsx`, men sentralt i `proxy.ts` (root av repoet). Se
[03 – Auth & sesjon](./03-auth-and-session.md) for full gjennomgang av selve token-logikken. Kort oppsummert:

```ts
export const config = {
  matcher: ["/dashboard/:path*", "/user/:path*", "/admin/:path*"],
};
```

- Alt annet (forsiden, `(auth)`, `(info)`, `(legal)`, `/confirm-email`) er offentlig og krever ingen token.
- `/admin/*` krever i tillegg at JWT-ets rolle-claim er `admin` — ellers redirectes brukeren til `/404`.
- **Merk:** matcher'en dekker ikke `/api/:path*`. Route handlers under `app/api/**` er _ikke_ beskyttet av
  proxyen — de stoler på at cookien inneholder et gyldig token når `agentExternal` kaller Gatewayen, og
  Gatewayen selv avviser ugyldige/utløpte tokens. Dette har praktiske konsekvenser for sesjonshåndtering,
  se [03](./03-auth-and-session.md#5-token-fornyelse-for-api-kall-agentinternal--apiauthrefresh).

## 3. Sidenes ansvar (konvensjon)

`page.tsx`-filer skal være tynne — de setter rammen (`MainContainer`/`AsyncMainContainer`, se
[06](./06-forms-and-design-system.md)) og eventuelt henter data server-side. All interaktiv logikk hører
hjemme i klientkomponenter under `components/`. Dette følges strengt for auth- og admin-sidene, men **ikke**
for kjernedomene-sidene (oppskrifter/måltidsplan/handleliste) — se avviket dokumentert i
[07 – Kjente problemer](./07-known-issues-and-tech-debt.md#store-monolittiske-sider-uten-backend).

## 4. Spesialfiler

| Fil                            | Rolle                                                                                                                                                                 |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/layout.tsx`               | Root layout. Setter opp `MantineProvider`, `Notifications`, `SessionProvider` (seedet server-side fra `sessionManager.getUserData()`) og `MainShell` (header/footer). |
| `app/admin/loading.tsx`        | Suspense-fallback for **alle** sider under `/admin` (Next pakker siden i `<Suspense>` med denne som fallback) — ingen admin-side trenger egen `<Suspense>`.           |
| `app/error.tsx`                | Global error boundary (client component, Next.js-konvensjon). Viser feilmelding + "Prøv igjen"/"Tilbake".                                                             |
| `app/not-found.tsx`            | Global 404-side. Brukes bl.a. når `proxy.ts` avviser en ikke-admin fra `/admin/*`.                                                                                    |
| `app/(legal)/legal/layout.tsx` | Egen to-kolonne-layout (sidemeny + innhold) kun for `/legal/*`-rutene.                                                                                                |
| `app/confirm-email/page.tsx`   | Ligger bevisst **utenfor** `(auth)`-gruppen siden lenken kommer fra e-post og ikke skal ha samme layout-kontekst som innloggingssidene.                               |

## 5. Navigasjonslenker

`components/layout/header/navlinks.ts` definerer tre lenkesett — `GUEST_LINKS`, `USER_LINKS`, `ADMIN_LINKS`
— som `Header.tsx` velger mellom basert på `session.role`. Rollen er alltid normalisert til `"admin"`/`"user"`
(små bokstaver) før den havner i sesjonstilstanden, så `Header.tsx` sammenligner med små bokstaver — se
[03 – Auth & sesjon, seksjon 6](./03-auth-and-session.md#6-rolle-normalisert-til-små-bokstaver-ved-kilden).

**Brytepunkt for burger-menyen:** lenkene vises i headeren fra `md` (992px), men et lenkesett med **flere enn 5 lenker**
(i dag admin: Dashboard, Brukere, Whitelist, Katalog, Ingredienser, System) trenger mer plass og går til burger-menyen
under `lg` (1200px) — ellers klippes brukermenyen ytterst til høyre. Regelen ligger i `Header.tsx` (`collapseBelow`) og
sendes til `NavLinksContainer` og `MobileNavDrawer`; legger du til flere lenker, trengs ingen endring der.

## 6. API-ruter (`app/api/**/route.ts`)

Route handlers er ikke sider, men de følger samme mappestruktur og er dokumentert separat i
[04 – API-integrasjon & datamodeller](./04-api-integration-and-data-models.md) (inkludert malen for nye endepunkter).
Alle svarer med `HttpResponse<T>`-konvolutten via `apiRoute`, unntatt `/api/health` og Google-rutene (redirect).
Fullstendig liste, med backend-endepunktet hver rute kaller (relativt til `GATEWAY_URL`):

```
/api/health                              GET   – enkel healthcheck (status, service, env, timestamp)
/api/public/contact                      POST  → /public/contact-form (Core)

/api/auth/login                          POST  → /auth/connect/token (password grant) + /auth/account/me
/api/auth/register                       POST  → /auth/account/register + /auth/connect/token
/api/auth/logout                         POST  → /auth/connect/revoke (best-effort)
/api/auth/refresh                        POST  → /auth/connect/token (refresh grant), brukt internt av agentInternal.ts
/api/auth/me                             GET   → /auth/account/me
/api/auth/google                         GET   – redirect til Gateway sin external-login
/api/auth/google-callback                GET   – mottar tokens/profil som query-params fra Gateway
/api/auth/updateProfile                  PUT   → /auth/account/profile
/api/auth/change-password                POST  → /auth/account/change-password
/api/auth/set-password                   POST  → /auth/account/set-password
/api/auth/deleteProfile                  DELETE → /auth/account/me
/api/auth/confirm-email                  POST  → /auth/account/confirm-email
/api/auth/resend-confirmation            POST  → /auth/account/resend-confirmation
/api/auth/recover                        POST  → /auth/account/recover
/api/auth/reset-password                 POST  → /auth/account/reset-password
/api/auth/complete-welcome               GET   → /auth/account/complete-welcome

/api/admin/users                         GET, PUT  → /auth/admin/users
/api/admin/users/[id]                    GET   → /auth/admin/users/{id}
/api/admin/users/lock                    POST  → /auth/admin/users/lock
/api/admin/users/unlock                  POST  → /auth/admin/users/unlock
/api/admin/users/confirm-email           POST  → /auth/admin/users/confirm-email
/api/admin/users/resend-confirmation     POST  → /auth/admin/users/resend-confirmation
/api/admin/users/reset-password-request  POST  → /auth/admin/users/reset-password-request
/api/admin/users/send-email              POST  → /auth/admin/send-email
/api/admin/users/delete                  POST  → /auth/admin/users/delete
/api/admin/users/delete-and-blacklist    POST  → /auth/admin/users/delete-and-blacklist
/api/admin/users/blacklist               GET, POST → /auth/admin/blacklist
/api/admin/users/blacklist/[id]          DELETE → /auth/admin/blacklist/{id}

/api/admin/[resource]                    GET, POST, PUT → /admin/<resource>  (Core, dynamisk rute — se under)
/api/admin/[resource]/[id]               DELETE → /admin/<resource>/{id}
/api/admin/ingredients                   GET, POST → /admin/ingredients  (Core, hele listen / opprett; egen statisk rute)
/api/admin/ingredients/[id]              GET, PUT, DELETE → /admin/ingredients/{id}  (full ingrediens; PUT erstatter alt)
/api/user/nutrient-definitions           GET   → /user/nutrient-definitions  (Core, næringsstoffkatalogen; admin-token godtas)
/api/user/recipes                        GET, POST → /user/recipes  (Core, hele listen / opprett)
/api/user/recipes/[id]                   GET, PUT, DELETE → /user/recipes/{id}
/api/user/recipes/[id]/favorite          PUT   → /user/recipes/{id}/favorite  (lettvekts av/på for isFavorite)
/api/user/recipes/[id]/nutrition         GET   → /user/recipes/{id}/nutrition  (beregnes på forespørsel, til næringsfanen)
/api/user/ingredients                    GET   → /user/ingredients  (lett, brukervendt ingrediensliste til velgeren i oppskriftsskjemaet)
/api/user/ingredients/[id]               GET   → /user/ingredients/{id}  (full ingrediens inkl. porsjoner, til enhetsinnsnevringen)
/api/user/unconfirmed-ingredients        POST  → /user/unconfirmed-ingredients  (brukerens egen ingrediens, opprettet fra oppskriftsskjemaet)
/api/user/recipe-categories              GET   → /user/recipe-categories  (skrivebeskyttet)
/api/user/units                          GET   → /user/units  (skrivebeskyttet)
/api/user/unit-types                     GET   → /user/unit-types  (skrivebeskyttet; ikke i faktisk bruk lenger, se under)
```

**`/api/admin/[resource]`** er én dynamisk rute for alle seks adminstyrte kataloger i `recipe-core-api`
(`recipe-categories`, `ingredient-categories`, `allergens`, `search-keywords`, `unit-types`, `units`) — de har samme
kontrakt, så de deler kode i stedet for ett filsett per katalog. Gyldige navn er hvitlisten i
`lib/models/catalog/CatalogResource.ts`; alt annet gir **404**, og skriving mot en skrivebeskyttet katalog
(`unit-types`) gir **405**. Enhetstypene kan derfor leses (de brukes som data i enhetstabellen og -filteret), men ikke endres. Statiske ruter som `/api/admin/users` har forrang over det dynamiske segmentet. Se
[04, seksjon 7.1](./04-api-integration-and-data-models.md#71-variant-én-dynamisk-rute-for-flere-like-ressurser).

Ingredienser har egne ruter (`/api/admin/ingredients`, full CRUD) og næringsstoffkatalogen leses via `/api/user/nutrient-definitions`.
Oppskrifter er nå bygget (`/api/user/recipes*`, se [09](./09-recipe-domain-and-planned-pages.md)), etter malen i 04, seksjon 7.
Næringsberegning (`GET /user/recipes/{id}/nutrition`) er koblet opp (næringsfanen på detaljsiden, se [09](./09-recipe-domain-and-planned-pages.md)).
`/api/user/recipe-categories`, `/api/user/units`, `/api/user/unit-types` og `/api/user/ingredients[/{id}]` er brukervendte
lese-stier parallelt med adminkatalogen, samme mønster som `/user/nutrient-definitions` — **alle bekreftet 2026-09-23 mot
`recipe-core-api`-kildekoden** (se `backend-notes.md`, B16). Enhetsvelgeren på hver ingredienslinje innsnevres til enheter
som faktisk har en gram-omregning for den valgte ingrediensen: samme enhetstype som ingrediensen normalt måles i, pluss
enhetene ingrediensen selv har en definert porsjon for (`GET /user/ingredients/{id}` → `portions`) —
`components/recipes/recipeLookups.ts`, `unitsForIngredient()`. `unit-types` er dermed ikke lenger i bruk til dette (var en
tidligere, mindre presis versjon av innsnevringen), men ruten er beholdt siden den er bekreftet og fungerer.
