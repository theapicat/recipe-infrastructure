# 🏗️ Overordnet Arkitekturdokument: Kjøkkenhylla

---

## 🎯 Del 1: Systemvisjon, Tjenestematrise & Kommunikasjon

### 1. Systemvisjon og Prinsipper

**Kjøkkenhylla** er arkitekturert som et distribuert, mikrotjeneste-basert system. Systemet er designet for å være skalerbart, fleksibelt og forberedt for fremtidige utvidelser (som en dedikert mobilapplikasjon), samtidig som det skiller skarpt mellom ulike ansvarsområder (*Separation of Concerns*).

#### Hovedprinsipper:

* **Single Gateway Inngang**: All ekstern trafikk sluses gjennom én felles API Gateway (`recipe-gateway-api`).
* **Isolerte Tjenester**: Hver applikasjon har sitt eget Git-repositorium, sine egne definerte ansvarsområder og sine egne data.
* **Driven av Åpen Kildekode (Open Source First)**: Systemet tilstreber utelukkende bruken av lisensfrie åpen kildekode-rammeverk. Identitetsstyringen benytter OpenID / ASP.NET Core Identity. Bakgrunnsmeldinger håndteres i dag via MassTransit over RabbitMQ, men planlegges migrert til **OpenTransit** så snart det blir tilgjengelig.
* **Hendelsesbasert & Dekoblet Kommunikasjon**: Ingen synkro interne RPC-kall mellom bakgrunnstjenester; all inter-tjenestekommunikasjon er 100 % asynkron og hendelsesbasert over meldingsbuss (RabbitMQ/AMQP).
* **Stateless Auth & Header Injection**: Gateway validerer JWT-tokens lokalt i minnet og beriker forespørsler videre internt med verifiserte identitets-headers (`X-User-Id`, `X-User-Roles`).
* **Enhetstesting**: .NET 10-bakendetjenestene innehar eller rigges med xUnit-enhetstester (`Service.Tests`).
* **Sentralisert Logging**: Alle tjenester sender strukturerte logger (Serilog) til et felles Seq-dashboard for full sporbarhet.
* **Full Containerisering av Infrastruktur**: Alle infrastrukturelementer (PostgreSQL-databaser, MongoDB-cache, RabbitMQ meldingsbuss, Mailpit innboks og Seq loggmotor) orkestreres samlet som isolerte Docker-containere via `recipe-infrastructure` på et felles Docker-nettverk (`recipe-net`).

---

### 2. Applikasjonsoversikt & Repositorium-matrise

Detaljert dokumentasjon, domenemodeller og enhetstester for de enkelte tjenestene finnes i deres respektive repositorier:

| Prosjektnavn (GitHub Repo) | Hovedteknologi | Rolle & Hovedansvar | Nettverkseksponering |
| :--- | :--- | :--- | :--- |
| [**`recipe-infrastructure`**](https://github.com/theapicat/recipe-infrastructure) | Docker Compose, Bash, Python | Sentral orkestrering av alle databaser, meldingsbuss, logging, Mailpit, felles skript og systemdokumentasjon. | **Internt Docker-nettverk** (`recipe-net`) |
| [**`recipe-webapp`**](https://github.com/theapicat/recipe-webapp) | Next.js 16, TypeScript, React | Brukergrensesnitt for web. Rendring av sider, brukermoduler og sanntidsoppdateringer. | **Offentlig** (Port 3000) |
| [**`recipe-gateway-api`**](https://github.com/theapicat/recipe-gateway-api) | .NET 10, YARP | Sentral inngangsdør (Web API Reverse Proxy). Håndterer CORS, YARP-routing, lokal JWT-validering og header-sanitering. | **Offentlig** (Port 5000) |
| [**`recipe-authentication-api`**](https://github.com/theapicat/recipe-authentication-api) | .NET 10 Web API, OpenID / Identity, EF Core, PostgreSQL | Identitetsstyring. Brukerregistrering, innlogging, token-utstedelse og publisering av brukerhendelser. | **Internt / Lokal host** (Port 5001) |
| [**`recipe-core-api`**](https://github.com/theapicat/recipe-core-api) | .NET 10 Web API, Dapper, PostgreSQL, SignalR | Kjernedomenet. Forretningslogikk for oppskrifter, ingredienser, kategorier og SignalR sanntidshub. | **Internt / Lokal host** (Port 5002) |
| [**`recipe-scraper-service`**](https://github.com/theapicat/recipe-scraper-service) | .NET 10, Playwright, MongoDB | Ekstern datainnhenting. Skraper og strukturerer oppskrifter fra eksterne nettsider asynkront via meldingskø. | **Internt Docker-nettverk** (`recipe-net`) |
| [**`recipe-notification-service`**](https://github.com/theapicat/recipe-notification-service) | .NET 10, MassTransit, MailKit, Scriban | Asynkron e-postdistribusjon (velkomst, passord, admin-varsler, verifisering og GDPR-sletting). | **Internt Docker-nettverk** (`recipe-net`) |

---

### 3. Infrastruktur-containere (Styrt via `recipe-infrastructure`)

Alle felles bakgrunnstjenester kjøres og orkestreres via `docker-compose.yaml` i `recipe-infrastructure`:

* **`recipe-auth-db`** (PostgreSQL - Port 5432): Lagring av brukerkontoer, passord-hashes, tilganger og roller.
* **`recipe-core-db`** (PostgreSQL - Port 5433 på vert): Lagring av oppskrifter, trinn, ingredienser og kategorier.
* **`recipe-scraper-cache`** (MongoDB - Port 27017): Dokumentdatabase for mellomlagring av skrapt rådata.
* **`recipe-message-broker`** (RabbitMQ - Port 5672 / 15672): Meldingsbuss for asynkron oppgavekø og hendelsesbasert kommunikasjon (AMQP).
* **`recipe-seq`** (Seq - Port 5341): Sentralisert dashboard for mottak og visualisering av strukturerte Serilog-logger.
* **`recipe-mailpit`** (Mailpit - Port 1025 / 8025): Lokal SMTP-felle og web-dashboard for trygg e-postinspeksjon i utviklingsmiljøet.

---

### 4. Kommunikasjonsmodeller og Protokoller

```text
=================================================================================
                               [ recipe-webapp ]
                             (Next.js 16 Frontend)
=================================================================================
                                       │
                            HTTP REST / WebSockets
                                       ▼
=================================================================================
                             [ recipe-gateway-api ]
                          (YARP Gateway - Port 5000)
=================================================================================
           │                                             │
    HTTP REST (/api/auth)                   HTTP REST (/api/public, /user, /hubs)
           ▼                                             ▼
+-------------------------------+             +---------------------------------+
|  recipe-authentication-api    |             |        recipe-core-api          |
|  (.NET 10 Web API - EF Core)  |             |   (.NET 10 Web API - Dapper)    |
|    (Port 5001 - Auth API)     |             |  (Port 5002 - Core & SignalR)   |
+-------------------------------+             +---------------------------------+
           │                                   │         │               │
  SQL      │                          SQL      │    AMQP │          AMQP │
  (Auth)   ▼                          (Core)   ▼         ▼               ▼
   [recipe-auth-db]                       [recipe-core-db] [recipe-message-broker]
     (PostgreSQL)                           (PostgreSQL)      (RabbitMQ)
                                                                 │       │
                                                      AMQP Event │       │ AMQP Event
                                                                 ▼       ▼
                                                     +-----------------------+ +-----------------------+
                                                     | recipe-scraper-service| | recipe-notification-  |
                                                     |  (Playwright Skraper) | |        service        |
                                                     +-----------------------+ +-----------------------+
                                                                 │                         │
                                                         MongoDB ▼                         ▼ SMTP (Dev)
                                                        [recipe-scraper-cache]       [recipe-mailpit]

```

#### Kommunikasjonsprotokoller:

1. **HTTP REST (Ekstern $\rightarrow$ Gateway $\rightarrow$ Mikrotjenester)**: Standard JSON-basert HTTP-kommunikasjon. Gateway validerer JWT og ruter kallet videre over HTTP.
2. **WebSockets / SignalR (Ekstern $\leftrightarrow$ Gateway $\leftrightarrow$ Core API)**: Toveis sanntidsforbindelse for oppskriftsoppdateringer.
3. **AMQP via RabbitMQ (Bakendetjenester internt)**: Asynkron, hendelsesbasert kommunikasjon som sikrer at tunge skrapeoppgaver og e-postutsendelser utføres helt dekoblet fra brukerens HTTP-forespørsler.

---

## 🛠️ Del 2: Utviklingsverktøy, Skript & Sikkerhet

---

### 5. Utviklingsskript & Progresjonslogg (`dev-scripts/`)

For smidig lokal utvikling i terminalen inneholder dette repositoriet hjelpeskript under `dev-scripts/`. Skriptene forutsetter at prosjektene ligger plassert i samme rotmappe (`~/Repo/RecipeProject/`):

```text
~/Repo/RecipeProject/
├── recipe-auth-api/
├── recipe-core-api/
├── recipe-gateway-api/
├── recipe-infrastructure/
├── recipe-notification-service/
├── recipe-scraper-service/
└── recipe-webapp/

```

#### Nøkkelverktøy:

* **`start-project.sh`**: Starter hele infrastrukturen i Docker Compose, alle .NET 10-bakendetjenestene og Next.js-webappen i separate terminaløkter for lokal utvikling.
* **`stop-project.sh`**: Stopper alle kjørende prosesser og rydder opp lokale porter.
* **`health-test.sh`**: Utfører en hurtigsjekk av alle definerte helseendepunkter og porter i utviklingsmiljøet.
* **`count_loc.py`**: Statistikkverktøy skrevet i Python. Teller *Lines of Code* (LOC) på tvers av hele prosjektporteføljen (ekskludert auto-genererte filer som `bin`, `obj`, `.next`, `node_modules`).
* Skriver ut en oppsummering direkte i terminalen.
* Genererer/oppdaterer en datostemplet Markdown-fil under `progress-log/YYYY-MM-DD_LOC.md` som en kontinuerlig historikk og benchmark på utviklingstempo.



---

### 6. Sikkerhet og Identitetsstyring

* **Sentralisert Token-validering i Gateway**: Ingen uautentiserte forespørsler slipper gjennom til beskyttede endepunkter i bakenden.
* **Isolering av Brukerdata**: `recipe-authentication-api` eier brukeridentiteter og tilganger. `recipe-core-api` forholder seg kun til verifiserte identitets-headers (`X-User-Id` og `X-User-Roles`), noe som sikrer at sensitive innloggingsdata aldri leker inn i kjerne-domenet.
* **Sikre Interne Nettverk**: Kun `recipe-gateway-api` og `recipe-webapp` eksponeres eksternt i produksjon. Databaser, meldingskøer og bakgrunnstjenester kommuniserer skjermet på Docker-nettverket (`recipe-net`).

---

### 7. Oppstart av Lokal Infrastruktur (Docker Compose)

All infrastruktur kjøres med én enkelt kommando fra `recipe-infrastructure`-mappen:

```bash
# Start alle infrastruktur-containere (databaser, RabbitMQ, Seq, Mailpit)
docker compose up -d

# Stopper alle containere
docker compose down

```

---

### 8. Dokumentasjonshierarki

Dypere teknisk dokumentasjon, teststrategier og fasedokumenter for enkeltkomponenter ligger organisert i egne undermapper under `documentation/`:

```text
documentation/
└── notification-service/
    ├── notification-readme.md          # Domene- og arkitekturdokumentasjon
    ├── notification-test-strategy.md   # xUnit & NSubstitute teststrategi
    └── notification-design-system.md   # Sage/Terracotta HTML e-post designsystem

```