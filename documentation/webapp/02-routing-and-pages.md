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
  se [03](./03-auth-and-session.md#hva-proxyts-ikke-dekker).

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
| `app/error.tsx`                | Global error boundary (client component, Next.js-konvensjon). Viser feilmelding + "Prøv igjen"/"Tilbake".                                                             |
| `app/not-found.tsx`            | Global 404-side. Brukes bl.a. når `proxy.ts` avviser en ikke-admin fra `/admin/*`.                                                                                    |
| `app/(legal)/legal/layout.tsx` | Egen to-kolonne-layout (sidemeny + innhold) kun for `/legal/*`-rutene.                                                                                                |
| `app/confirm-email/page.tsx`   | Ligger bevisst **utenfor** `(auth)`-gruppen siden lenken kommer fra e-post og ikke skal ha samme layout-kontekst som innloggingssidene.                               |

## 5. Navigasjonslenker

`components/layout/header/navlinks.ts` definerer tre lenkesett — `GUEST_LINKS`, `USER_LINKS`, `ADMIN_LINKS`
— som `Header.tsx` velger mellom basert på `session.role`. **NB:** denne sammenligningen bruker
`session.role === "Admin"` (stor bokstav), mens resten av kodebasen (proxy.ts, login/register-sidene)
konsekvent bruker `.toLowerCase() === "admin"`. Se
[07 – Kjente problemer](./07-known-issues-and-tech-debt.md#inkonsistent-rollesjekk-i-header).

## 6. API-ruter (`app/api/**/route.ts`)

Route handlers er ikke sider, men de følger samme mappestruktur og er dokumentert separat i
[04 – API-integrasjon & datamodeller](./04-api-integration-and-data-models.md). Fullstendig liste over
tilgjengelige endepunkter:

```
/api/health                              GET   – enkel healthcheck (status, service, env, timestamp)
/api/public/contact                      POST  – kontaktskjema → GATEWAY_URL

/api/auth/login                          POST
/api/auth/register                       POST
/api/auth/logout                         POST
/api/auth/refresh                        POST  – fornyer access-token, brukt internt av agentInternal.ts
/api/auth/me                             GET
/api/auth/google                         GET   – redirect til Gateway sin external-login
/api/auth/google-callback                GET   – mottar tokens/profil som query-params fra Gateway
/api/auth/updateProfile                  PUT
/api/auth/change-password                POST
/api/auth/set-password                   POST
/api/auth/deleteProfile                  DELETE
/api/auth/confirm-email                  POST
/api/auth/resend-confirmation            POST
/api/auth/recover                        POST
/api/auth/reset-password                 POST
/api/auth/complete-welcome               GET

/api/admin/users                         GET, PUT
/api/admin/users/[id]                    GET
/api/admin/users/lock                    POST
/api/admin/users/unlock                  POST
/api/admin/users/confirm-email           POST
/api/admin/users/resend-confirmation     POST
/api/admin/users/reset-password-request  POST
/api/admin/users/send-email              POST
/api/admin/users/delete                  POST
/api/admin/users/delete-and-blacklist    POST
/api/admin/users/blacklist               GET, POST
/api/admin/users/blacklist/[id]          DELETE
```
