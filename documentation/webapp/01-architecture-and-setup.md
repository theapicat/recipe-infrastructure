# 01 – Arkitektur & Oppsett

## 1. Hva er Kjøkkenhylla?

Kjøkkenhylla er en webapplikasjon for privat/delt organisering av oppskrifter, ukentlig måltidsplanlegging,
generering av handlelister og oversikt over næringsinnhold. `recipe-webapp` er **kun frontend- og
proxy-laget** i et større økosystem — all forretningslogikk og datalagring skjer i separate .NET-tjenester.

> Næringsberegningene er kun veiledende og utgjør ikke medisinsk eller helsefaglig rådgivning.

## 2. Økosystemet

```
                         ┌────────────────────┐
   Nettleser  ───────►   │   recipe-webapp     │   (denne appen — Next.js 16)
                         │   Frontend + Proxy   │
                         └──────────┬──────────┘
                                    │  REST (JSON / x-www-form-urlencoded)
                                    ▼
                         ┌────────────────────┐
                         │  Recipe Gateway API  │   (YARP, port 5000)
                         │  - Validerer JWT      │
                         │  - Renser headers     │
                         │  - Injiserer X-User-Id│
                         └──────┬───────┬───────┘
                                │       │
                 ┌──────────────┘       └──────────────┐
                 ▼                                      ▼
   ┌───────────────────────────┐          ┌───────────────────────────┐
   │ recipe-authentication-api  │          │      recipe-core-api       │
   │ (port 5001) — OpenIddict,  │          │ (port 5002) — oppskrifter, │
   │ brukere, admin, blacklist  │          │ måltidsplaner, handleliste │
   └───────────────────────────┘          └───────────────────────────┘

   En egen skrapetjeneste håndterer import av oppskrifter fra godkjente eksterne
   nettsteder, og nås også via Gatewayen.
```

`recipe-webapp` snakker **aldri direkte** med `recipe-authentication-api` eller `recipe-core-api` — alt går
via Gatewayen på port 5000. Se [`03-auth-and-session.md`](./03-auth-and-session.md) for hvordan JWT og
cookies flyter gjennom dette.

## 3. Teknologistack

| Kategori          | Teknologi                                                                                          |
| ----------------- | -------------------------------------------------------------------------------------------------- |
| Rammeverk & språk | Next.js 16 (App Router, **Proxy**-konvensjon — se boks under), React 19, TypeScript                |
| UI & styling      | Mantine v9 (`@mantine/core`, `@mantine/form`, `@mantine/notifications`, `@mantine/dates`), PostCSS |
| Datavisualisering | Mantine Charts, Recharts                                                                           |
| Ikoner & verktøy  | Tabler Icons, Dayjs, React Markdown                                                                |

> **⚠️ Denne Next.js-versjonen er nyere enn det du kjenner fra opplæring/minne.**
> `middleware.ts` heter nå **`proxy.ts`** (se root av repoet). Før du gjør endringer i routing, caching eller
> proxy-atferd: les `node_modules/next/dist/docs/` (vendored dokumentasjon for denne spesifikke versjonen).
> Se `AGENTS.md` i rot for detaljer — den filen genereres/oppdateres automatisk av `next dev`.

## 4. Miljøvariabler (`.env.local`)

```env
# Base-URL for Recipe Gateway API. Auth-endepunkter nås som {GATEWAY_URL}/auth/*,
# kjerne-endepunkter (oppskrifter, måltidsplan m.m.) direkte som {GATEWAY_URL}/*
GATEWAY_URL=http://localhost:5000/api

# Google OAuth client-id (eksponeres til nettleseren)
NEXT_PUBLIC_GOOGLE_CLIENT_ID=...
```

Én variabel for hele Gatewayen — bevisst, ikke to. Det fantes tidligere to separate variabler (`AUTH_API`,
`CORE_API`) som pekte på samme host med ulikt path-prefiks, pluss en tredje (`NEXT_PUBLIC_AUTH_API` i
`proxy.ts`) som aldri var satt og stille falt tilbake til en hardkodet URL. Alle tre er slått sammen til
`GATEWAY_URL` nettopp for å gjøre det umulig for dem å komme ut av synk igjen — se
[`03-auth-and-session.md`](./03-auth-and-session.md) for detaljer om hvor den brukes.

## 5. Kom i gang

```bash
npm install
npm run dev      # http://localhost:3000
npm run build    # produksjonsbygg
npm run start    # kjør produksjonsbygg
npm run lint     # ESLint (flat config, eslint-config-next)
```

Det finnes **ingen testkjører** konfigurert i dette repoet per nå (ingen `test`-script, ingen Jest/Vitest).
Se [`07-known-issues-and-tech-debt.md`](./07-known-issues-and-tech-debt.md).

## 6. Mappeoversikt (høyt nivå)

| Mappe                | Ansvar                                                                                               |
| -------------------- | ---------------------------------------------------------------------------------------------------- |
| `app/`               | Next.js App Router — sider, route handlers (`api/`), route groups                                    |
| `components/`        | React-komponenter, gruppert etter `forms/`, `admin/`, `layout/`, `containers/`                       |
| `lib/agent/`         | HTTP-klienter mot egne API-ruter og mot Gatewayen (se [04](./04-api-integration-and-data-models.md)) |
| `lib/session/`       | Cookie-/sesjonshåndtering og React-context for innlogget bruker                                      |
| `lib/models/`        | TypeScript-modeller/DTO-er, gruppert etter domene (`auth/`, `admin/users/`, ...)                     |
| `documentation/`     | Denne dokumentasjonen                                                                                |
| `public/docs/legal/` | Juridiske dokumenter servert direkte til brukere (speiles av `(legal)`-rutene)                       |
| `proxy.ts`           | Next.js "Proxy" (tidligere Middleware) — auth-gating og token-refresh på sidenavigasjon              |
| `theme.ts`           | Mantine-tema (se [`06-forms-and-design-system.md`](./06-forms-and-design-system.md))                 |

## 7. Videre lesning

1. [02 – Ruting & sider](./02-routing-and-pages.md)
2. [03 – Auth & sesjon](./03-auth-and-session.md)
3. [04 – API-integrasjon & datamodeller](./04-api-integration-and-data-models.md)
4. [05 – Adminpanelet](./05-admin-panel.md)
5. [06 – Skjemaer & designsystem](./06-forms-and-design-system.md)
6. [07 – Kjente problemer & teknisk gjeld](./07-known-issues-and-tech-debt.md)
7. [08 – Forslag: mappestruktur for modeller & komponenter](./08-model-and-component-structure-proposal.md)
