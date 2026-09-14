# 04 – API-integrasjon & Datamodeller

## 1. Lagene, i rekkefølge

```
Klientkomponent ("use client")
   │  agentInternal.get/post/put/delete("/api/...", body)
   ▼
Route handler  app/api/**/route.ts        (server, kjører i Next.js)
   │  agentAuth.* / agentAuthAdmin.*
   ▼
agentExternal.get/post/put/delete(...)    (legger på Authorization: Bearer <token>)
   ▼
Recipe Gateway API (YARP, port 5000)      → validerer JWT, injiserer X-User-Id
   ▼
recipe-authentication-api (5001)  /  recipe-core-api (5002)
```

Route handlers er en **tynn oversettelsesjobb**, ikke forretningslogikk: de tar imot JSON fra klienten,
kaller riktig `agentAuth`/`agentAuthAdmin`-metode, og pakker resultatet i en konsistent konvolutt (se punkt 3).

## 2. `lib/agent/` — filene

| Fil                 | Ansvar                                                                                                                                                                                                                                                                                                                                 |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `agentInternal.ts`  | `"use client"`. Same-origin `fetch` mot denne appens egne `/api/*`-ruter. Ingen auth-header — cookien følger automatisk. Fanger opp 401-svar, fornyer tokenet via `POST /api/auth/refresh` og gjentar kallet én gang — se [03](./03-auth-and-session.md#5-token-fornyelse-for-api-kall-agentinternal--apiauthrefresh).                 |
| `agentExternal.ts`  | Server-only. `fetch` med `mode: "cors"` mot Gatewayen. Henter token via `sessionManager.getToken()` og setter `Authorization: Bearer`. Har også `postForm()` for `x-www-form-urlencoded` (OAuth2 token-endepunktet krever dette formatet).                                                                                             |
| `agentAuth.ts`      | Typet wrapper for alle `/account/*`- og `/connect/token`-kall (login, refresh, register, profil, passord, e-postbekreftelse). Kaster `ApiError` (melding + Gatewayens faktiske statuskode) ved `!response.ok`. `revokeToken()` er unntaket — kaster aldri, best-effort ved utlogging (se [03](./03-auth-and-session.md#43-utlogging)). |
| `agentAuthAdmin.ts` | Samme mønster for `/admin/*`-kall (brukerliste, lås/lås opp, svarteliste, send e-post).                                                                                                                                                                                                                                                |
| `ApiError.ts`       | `Error`-subklasse med et `status`-felt — se seksjon 6.                                                                                                                                                                                                                                                                                 |

**Regel:** ny funksjonalitet mot backend skal legges til som en ny metode i `agentAuth`/`agentAuthAdmin`, ikke
som et rått `fetch`-kall inne i en komponent eller route handler. `app/api/public/contact/route.ts` er unntaket
— den kaller `agentExternal` direkte siden den ikke er en del av auth/admin-domenet.

## 3. Responskonvolutt: `HttpResponse<T>`

De fleste (men ikke alle — se `/api/health`) route handlers returnerer:

```ts
interface HttpResponse<T> {
  statusCode: number;
  message: string;
  body?: T;
  timestamp: string; // ISO-streng
}
```

Klientkomponenter kaster om responsen til `HttpResponse<X>` og sjekker `res.ok && data.body` for
suksess. `statusCode`-feltet i body er informativt — det faktiske HTTP-statuskoden på responsen er
autoritativ.

## 4. `lib/models/` — konvensjon

Én fil per DTO/interface, gruppert etter domene:

```
lib/models/
├── auth/                     # login, registrering, passord, profil (bruker-domenet)
├── admin/users/              # admin-spesifikke request/response-typer
├── enums/                    # f.eks. BlacklistType
├── public/                   # kontaktskjema o.l.
├── httpResponse.ts
└── types.ts                  # UserRoleType + normalizeRole() — se 03-auth-and-session.md, seksjon 6
```

**Advarsel — filnavn må matche interface-navnet.** `lib/models/admin/users/BlacklistedEntry.ts` og
`DeleteAndBlacklistUserAdminRequest.ts` hadde til nylig byttet om innhold (filen med det ene navnet inneholdt
det andre interfacet). Dette er nå rettet — men understreker regelen: når du lager en ny modellfil, dobbeltsjekk
at filnavn og `export interface`-navn er identiske, ellers blir det umulig å navigere kodebasen etter navn.

## 5. Datamodeller som _ikke_ finnes ennå

Det finnes ingen `lib/models`-filer for oppskrifter, måltidsplaner eller handlelister. Dette er ikke en
forglemmelse i dokumentasjonen — de sidene har heller ingen ekte API-integrasjon ennå. Se
[07 – Kjente problemer](./07-known-issues-and-tech-debt.md#store-monolittiske-sider-uten-backend) for detaljer
og hva som må på plass før disse kan kobles til `recipe-core-api`.

## 6. Feilhåndteringsmønster (gjelder alle route handlers)

```ts
export const POST = async (request: Request) => {
  try {
    const body = await request.json();
    const result = await agentAuth.someMethod(body);
    return NextResponse.json({ statusCode: 200, message: "...", body: result, timestamp: ... }, { status: 200 });
  } catch (error: unknown) {
    const status = error instanceof ApiError ? error.status : 400;
    const errorMessage = error instanceof Error ? error.message : "Fallback-melding på norsk.";
    return NextResponse.json({ statusCode: status, message: errorMessage, timestamp: ... }, { status });
  }
};
```

`agentAuth`/`agentAuthAdmin` kaster `ApiError` (`lib/agent/ApiError.ts`) i stedet for en ren `Error` — den
bærer med seg Gatewayens faktiske HTTP-statuskode (`error.status`), som route handleren propagerer videre i
stedet for å flate alt til 400. Dette er det `agentInternal.ts` bruker til å avgjøre om et mislykket kall
skal utløse et fornyelsesforsøk (kun ved nøyaktig 401) — se
[03 – Auth & sesjon, seksjon 5](./03-auth-and-session.md#5-token-fornyelse-for-api-kall-agentinternal--apiauthrefresh).
For feil som ikke kommer fra `agentAuth`/`agentAuthAdmin` (f.eks. `JSON.parse`-feil på selve requesten) er
`error` ikke en `ApiError`, og statusen faller tilbake til 400 som før.
