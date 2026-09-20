# 03 – Auth & Sesjon

Dette er det mest kompliserte hjørnet av kodebasen, og der de fleste "hvorfor logges jeg ut?"-symptomene
oppstår. Les hele dette dokumentet før du gjør endringer i login/proxy/session-flyten.

## 1. Sesjonsmodellen: tre cookies

All sesjonstilstand ligger i tre cookies, satt/lest utelukkende gjennom `lib/session/sessionManager.ts`.
**Ingen annen kode skal lese/skrive disse cookiene direkte** — gå alltid via `sessionManager`.

| Cookie         | Innhold                                       | `httpOnly` | Levetid                                         |
| -------------- | --------------------------------------------- | ---------- | ----------------------------------------------- |
| `token`        | JWT access-token (OpenIddict)                 | Ja         | `expires_in` fra token-response (default 3600s) |
| `refreshToken` | OAuth2 refresh-token                          | Ja         | 14 dager                                        |
| `user_data`    | JSON av `UserProfileResponse` — lesbar for UI | Nei        | 14 dager                                        |

`sessionManager` eksponerer også to ren-JWT-hjelpere som dekoder base64-payloaden manuelt (ingen
JWT-bibliotek er i bruk):

- `getRemainingExpTime(token)` — sekunder til utløp, eller `-1` ved parse-feil/manglende `exp`.
- `getUserRole(token)` — leser `role`, `roles`, eller
  `http://schemas.microsoft.com/ws/2008/06/identity/claims/role`-claimet.

## 2. To HTTP-klienter — ikke bland dem

| Klient                       | Kjører i                | Brukes til                                                          | Auth-header                                                                          |
| ---------------------------- | ----------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `lib/agent/agentInternal.ts` | Klient (`"use client"`) | Kalle **denne appens egne** `app/api/**`-ruter, same-origin `fetch` | Ingen — cookien følger automatisk med                                                |
| `lib/agent/agentExternal.ts` | Server (route handlers) | Kalle **Gatewayen** direkte, `mode: "cors"`                         | `Authorization: Bearer <token fra sessionManager.getToken()>`, satt manuelt per kall |

`agentAuth.ts` og `agentAuthAdmin.ts` er tynne, typede wrappere rundt `agentExternal` — én metode per
Gateway-endepunkt (login, register, hent profil, lås bruker, svarteliste, ...).

**Viktig:** `agentExternal` gjør selv **ingen** forsøk på å fornye et utløpt token før den bruker det — den
henter bare det som ligger i cookien akkurat nå og sender det av gårde. Fornyelse skjer i to uavhengige lag:
`proxy.ts` ved sidenavigasjon (se under), og `agentInternal` ved API-kall (se seksjon 5).

**`fetchWithTimeout`** (`lib/agent/fetchWithTimeout.ts`, 10 sekunder default) brukes av alle fem metodene i
`agentExternal` og av `proxy.ts` sitt eget frittstående refresh-kall — den eneste plassen appen faktisk gjør
et nettverkskall mot Gatewayen. Uten dette kan et uoppnåelig Gateway (feil vert, brannmur som dropper pakker
stille, VPN nede — i motsetning til f.eks. "ingenting kjører på localhost" som feiler nesten øyeblikkelig)
henge et kall på ubestemt tid. Dette rammet i praksis logout (se seksjon 4.3): brukeren fikk ingen
tilbakemelding og satt fast, siden `agentAuth.revokeToken()` sitt kall aldri fikk en tidsgrense å gi opp ved.

## 3. `proxy.ts` — Next.js' "Proxy" (tidligere Middleware)

> Denne Next.js-versjonen har omdøpt `middleware.ts` til `proxy.ts`. Filen ligger i repo-roten og har samme
> jobb som `middleware.ts` hadde i eldre Next.js-prosjekter.

Matcher: `/dashboard/:path*`, `/user/:path*`, `/admin/:path*` — kjører altså kun ved navigasjon til disse
sidene, ikke ved API-kall (se punkt 5).

Logikk, i rekkefølge:

1. **Ingen tokens i det hele tatt** (verken `token` eller `refreshToken`) → redirect til `/login`.
2. **Trenger fornyelse?** Hvis `token` mangler, eller har mindre enn 300 sekunder igjen til utløp
   (`getRemainingExpTime`), og det finnes en `refreshToken` → kall
   `POST {GATEWAY_URL}/auth/connect/token` med `grant_type=refresh_token` direkte (uten å gå via
   `agentAuth`/`agentExternal` — dette er en frittstående `fetch`).
   - Lykkes det → nye tokens brukes resten av requesten, og settes på responsen som `Set-Cookie`.
   - Feiler det (f.eks. `invalid_grant` fordi refresh-tokenet er utløpt) → tvungen utlogging: cookies
     slettes, redirect til `/login?expired=true`.
3. **Token mangler og ingen refreshToken** → samme tvungne utlogging.
4. **Muterer request-headers** slik at Server Components i samme request-syklus ser det ferske tokenet med
   en gang (`NextResponse.next({ request: { headers } })`).
5. **Admin-gating:** for `/admin/*` dekodes rollen fra det (eventuelt nylig fornyede) tokenet. Er den ikke
   `admin` → redirect til `/404`.

### Miljøvariabel: én kilde til sannhet

Refresh-kallet i `proxy.ts` bruker:

```ts
const refreshUrl = `${process.env.GATEWAY_URL || "http://localhost:5000/api"}/auth/connect/token`;
```

— samme `GATEWAY_URL` som `agentAuth.ts`/`agentAuthAdmin.ts` bygger sin base-URL fra
(`` `${GATEWAY_URL}/auth` ``). Dette var tidligere to separate variabler (`AUTH_API`/`CORE_API`) pluss en
tredje, aldri satt variabel i `proxy.ts` alene (`NEXT_PUBLIC_AUTH_API`), som gjorde at proxyens token-refresh
kjørte på en hardkodet fallback-URL uten at noen la merke til det. Slått sammen til én variabel nettopp for at
dette ikke skal kunne skje igjen — endres Gateway-URL-en, er det ett sted å gjøre det.

## 4. Innloggingsflyter

### 4.1 E-post/passord

```
LoginForm (client) → agentInternal.post("/api/auth/login")
  → app/api/auth/login/route.ts
      → agentAuth.login()         (OAuth2 "password" grant → Gateway /connect/token)
      → fetch GET {GATEWAY_URL}/auth/account/me   (henter profil med det ferske access-tokenet)
      → sessionManager.setSession(tokens, profil)   (setter alle tre cookies)
  ← { statusCode, body: UserProfileResponse }
→ session.setUser(...) i SessionProvider, redirect til /dashboard eller /admin/dashboard
```

### 4.2 Google OAuth (avviker fra alt annet — leser IKKE via agentAuth)

```
GoogleLogin/GoogleRegister → window.location.href = "/api/auth/google"
  → app/api/auth/google/route.ts: redirect til {GATEWAY_URL}/auth/account/external-login?provider=Google
    (fullstendig browser-redirect, forlater Next.js)
  → [Gateway/Google OAuth-dans skjer utenfor denne appen]
  → Gateway redirecter tilbake til /api/auth/google-callback?access_token=...&refresh_token=...&user_id=...&email=...&...
    → app/api/auth/google-callback/route.ts bygger UserProfileResponse manuelt av query-parameterne
      og kaller sessionManager.setSession() + setter cookies eksplisitt på responsen
  → redirect til /user/welcome (førstegangsbruker) eller /dashboard
```

Feilkoder fra Gateway (`?error=account_locked|blacklisted|access_denied|google_failed|oauth_failed`) fanges
opp og oversettes til norske feilmeldinger i `app/(auth)/login/page.tsx` og `app/(auth)/register/page.tsx`.

### 4.3 Utlogging

`UserMenu.tsx` → `agentInternal.post("/api/auth/logout")` → `app/api/auth/logout/route.ts`:

1. `agentAuth.revokeToken()` — **best-effort** `POST {GATEWAY_URL}/auth/connect/revoke` med refresh-tokenet
   (RFC 7009-format, samme form-encoding som `/connect/token`). Kaster aldri — feiler kallet (f.eks. fordi
   Gatewayen ikke har endepunktet ennå, eller er helt uoppnåelig), fortsetter utloggingen som normalt. Går
   via `agentExternal`, som bruker `fetchWithTimeout` (se seksjon 2) — **kritisk** her, siden et uoppnåelig
   Gateway uten tidsgrense tidligere kunne henge dette kallet på ubestemt tid og la brukeren sitte fast
   midt i utlogging uten tilbakemelding. Se `BACKEND_REQUIREMENTS.md` i repo-roten for hva som forventes av
   backend, inkludert en viktig presisering om at revocation av refresh-tokenet ikke nødvendigvis gjør et
   allerede utstedt (JWT) access-token ugyldig før det utløper naturlig.
2. `sessionManager.removeSession()` — sletter de tre lokale cookiene.

`UserMenu.tsx` sin `handleLogout()` viser nå en `loading`-tilstand ("Logger ut …") mens kallet pågår, og en
feilmelding via `notifications` hvis logout-endepunktet svarer med feil eller nettverkskallet feiler — tidligere
ga et mislykket kall (`!res.ok`) ingen tilbakemelding i det hele tatt.

## 5. Token-fornyelse for API-kall (`agentInternal` + `/api/auth/refresh`)

`proxy.ts` sin matcher dekker ikke `/api/:path*` (se punkt 3) — token-fornyelse ved sidenavigasjon alene var
derfor ikke nok. Et klient-side `agentInternal`-kall som treffer en route handler mens access-tokenet er
utløpt vil få et ekte **401** tilbake fra Gatewayen, propagert helt ut til klienten takket være `ApiError`
(se [04 – API-integrasjon, seksjon 6](./04-api-integration-and-data-models.md#6-feilhåndteringsmønster-gjelder-alle-route-handlers)).

`agentInternal.ts` fanger opp nettopp dette:

```
Klientkomponent → agentInternal.get/post/put/delete(...)
  → fetch mot egen /api/**-rute
  → svar med status 401?
      nei → returner svaret som normalt
      ja  → kall POST /api/auth/refresh (agentAuth.refresh() + sessionManager.setToken/setRefreshToken)
              lykkes → gjenta det opprinnelige kallet én gang, returner det svaret
              feiler → returner det opprinnelige 401-svaret uendret
```

`app/api/auth/refresh/route.ts` er den nye ruten — bruker den tidligere ubrukte `agentAuth.refresh()` og
`sessionManager` sine individuelle settere (`setToken`, `setRefreshToken`). Feiler fornyelsen (refresh-tokenet
er også utløpt), nullstilles sesjonen (`sessionManager.removeSession()`) og ruten svarer 401.

**Samtidighetsvern:** flere `agentInternal`-kall som feiler med 401 omtrent samtidig (f.eks. flere widgets som
laster data på en gang) deler ett og samme fornyelsesforsøk via en modul-lokal `refreshPromise` — det trigges
aldri flere parallelle `POST /api/auth/refresh`-kall for samme utløpte token.

**Bevisst ikke gjort:** ved mislykket fornyelse tvinges IKKE en redirect til `/login` fra `agentInternal` selv
(slik `proxy.ts` gjør ved sidenavigasjon). Årsak: `agentInternal` brukes også av anonyme skjemaer (innlogging,
registrering), og et generelt "fornyelse feilet → send til /login"-grep ville i verste fall sendt en bruker
som akkurat skrev feil passord på `/login`-siden i en redirect-løkke til samme side. Oppførselen er derfor
fortsatt "bare vis feilmeldingen som før" for det sjeldne tilfellet der _selve refresh-tokenet_ også er dødt —
en mulig finpuss senere, ikke en regresjon fra i dag.

## 6. Rolle: normalisert til små bokstaver ved kilden

`lib/models/types.ts` definerer `UserRoleType = "admin" | "user"` og en delt `normalizeRole()`-funksjon.
Backend sender alltid rollen med små bokstaver (`"admin"`/`"user"`) på de tre stedene den forlater Auth API — JWT
`role`-claimet, `/account/me`-responsen, og Google-callbackens `role`-query-param. Frontend normaliserer
likevel defensivt til små bokstaver i alle fire punktene der en rolle kommer inn i appens tilstand, slik at resten av kodebasen kan stole på at `session.role`
alltid er `"admin"` eller `"user"`:

- `sessionManager.getUserRole(token)` — dekoder JWT-claimet.
- `sessionManager.setSession()` / `setUserData()` — det som lagres i `user_data`-cookien.
- `SessionProvider` sin egen **seeding** av `initialUser` (`normalizedInitialUser` i konstruktøren) — ikke
  bare `setUser()`/`updateUser()`. En cookie skrevet _før_ normaliseringen ble innført (f.eks. en økt som
  ikke har logget inn på nytt siden, eller på en annen maskin som ikke har fått siste kodeversjon) kunne
  ellers seede React-state med den rå, ikke-normaliserte verdien fra cookien — noe som i praksis fikk
  `Header.tsx` til å vise gjeste-navigasjon for en faktisk innlogget bruker. Rettet.
- `app/api/auth/google-callback/route.ts` — `role`-query-parameteren.

Dette fant sted etter at `Header.tsx` ble oppdaget å sammenligne rollen eksakt (`session.role === "Admin"`)
mens resten av appen normaliserte med `.toLowerCase()` — en reell, observert inkonsistens (rettet, se
git-historikk). De øvrige stedene som fortsatt gjør en (nå overflødig, men ufarlig) `.toLowerCase()`-sjekk ved
sammenligning (`LoginForm.tsx`, `UserMenu.tsx`, `ProfileEditForm.tsx`, `DeleteAccountForm.tsx`, m.fl.) er
bevisst ikke ryddet opp — de var aldri buggy, bare defensive.
