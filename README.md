# 🏗️ Overordnet Arkitekturdokument: Kjøkkenhylla

## 1. Systemvisjon og Prinsipper
**Kjøkkenhylla** er arkitekturert som et distribuert, mikrotjeneste-basert system. Systemet er designet for å være skalerbart, fleksibelt og forberedt for fremtidige utvidelser (som en dedikert mobilapplikasjon), samtidig som det skiller skarpt mellom ulike ansvarsområder (*Separation of Concerns*).

### Hovedprinsipper:
* **Single Gateway Inngang**: All ekstern trafikk sluses gjennom én felles API Gateway (`recipe-gateway-api`).
* **Isolerte Tjenester**: Hver applikasjon har sitt eget Git-repositorium, definerte ansvarsområder og eier sine egne data.
* **Hybrid Kommunikasjon**: Synkroni (gRPC) brukes der lav forsinkelse er kritisk, mens asynkroni (RabbitMQ) brukes for tunge bakgrunnsjobber.
* **Full Containerisering**: Alle tjenester, databaser og infrastrukturelementer kjører som isolerte Docker-containere koblet på et felles eksternt Docker-nettverk (`recipe-net`).

---

## 2. Applikasjonsoversikt & Teknologistack

| Prosjektnavn (Repo) | Hovedteknologi | Rolle & Hovedansvar | Nettverkseksponering |
| :--- | :--- | :--- | :--- |
| **`recipe-web-app`** | Next.js, TypeScript, React | Brukergrensesnitt for web. Rendring av sider, brukermoduler, interaktive verktøy og sanntidsoppdateringer. | **Offentlig** (Port 3000 / 443) |
| **`recipe-gateway-api`** | .NET, YARP | Sentral inngangsdør (Reverse Proxy). Håndterer SSL-terminering, routing, rate-limiting, JWT-sjekk og WebSocket-proxying. | **Offentlig** (Port 80 / 443) |
| **`recipe-authentication-api`** | .NET, OpenIddict, ASP.NET Core Identity | Identitetsstyring. Håndterer brukerregistrering, innlogging, utstedelse og validering av OAuth2/OIDC-tokens samt bruker-admin. | **Internt Docker-nettverk** (`recipe-net`) |
| **`recipe-core-api`** | .NET, SignalR Hub | Kjernedomenet. Håndterer forretningslogikk for oppskrifter, ingredienser og brukertilpasninger. Vert for SignalR sanntidshub. | **Internt Docker-nettverk** (`recipe-net`) |
| **`recipe-scraper-service`** | .NET, Playwright (Headless Chromium) | Ekstern datainnhenting. Skraper, parser og strukturerer oppskrifter fra eksterne nettsider ved hjelp av nettleserautomatisering. | **Internt Docker-nettverk** (`recipe-net`) |
| **`recipe-infrastructure`** | Docker Compose (Offisielle Images) | Felles repository for databaser og infrastrukturtjenester (PostgreSQL, MongoDB, RabbitMQ). | **Internt Docker-nettverk** (`recipe-net`) |

### Infrastruktur-containere (Styrt via `recipe-infrastructure`):
* **`recipe-auth-db`** (PostgreSQL): Lagring av brukerkontoer, passord-hashes, tilganger, roller og autentiseringshistorikk.
* **`recipe-core-db`** (PostgreSQL): Lagring av domenefelt som oppskrifter, trinn, ingredienser, kategorier og brukermetadata.
* **`recipe-scraper-cache`** (MongoDB): Dokumentdatabase (NoSQL) for mellomlagring av skrapt rådata og eksternt innhold med automatisk TTL (utløpstid).
* **`recipe-message-broker`** (RabbitMQ): Meldingsbuss for asynkron oppgavekø, belastningsstyring og hendelsesbasert kommunikasjon (Event-driven).

---

## 3. Kommunikasjonsmodeller og Protokoller

Kommunikasjonen i systemet er delt inn etter behov for responstid og belastning:


```
=================================================================================
                            [ recipe-web-app ]
                            (Next.js Frontend)
=================================================================================
                                    |
                         HTTP REST / WebSockets
                                    v
=================================================================================
                         [ recipe-gateway-api ]
                           (YARP API Gateway)
=================================================================================
           |                                             |
     gRPC (Auth)                                   gRPC (Data)
           v                                             v
+-------------------------------+             +---------------------------------+
|  recipe-authentication-api    |             |        recipe-core-api          |
|    (OAuth2 / OpenIddict)      |             |    (Core API & SignalR Hub)     |
+-------------------------------+             +---------------------------------+
           |                                       |       ^                ^
           v                                  gRPC |       | SignalR        | 
   [recipe-auth-db]                        (Cache) |       | Event Push     | 
     (PostgreSQL)                                  v       |                |
                                              +---------------------+       |
                                              | recipe-scraper-     |       |
                                              |      service        |       |
                                              +---------------------+       |
                                                   |         |              |
                                                   v         v              |
                                        [recipe-scraper-  [recipe-message-broker]
                                            cache]           (RabbitMQ)-----+
                                          (MongoDB)

```

### Kommunikasjonsprotokoller:
1. **HTTP REST (Ekstern $\rightarrow$ Gateway)**: Standardisert JSON-basert HTTP-kommunikasjon fra `recipe-web-app` til `recipe-gateway-api`.
2. **WebSockets / SignalR (Ekstern $\leftrightarrow$ Gateway $\leftrightarrow$ Core API)**: Toveis sanntidsforbindelse for å skyve oppdateringer fra `recipe-core-api` til klienten uten sideinnlasting.
3. **gRPC (Gateway $\rightarrow$ Interne Tjenester & Core $\rightarrow$ Scraper)**: Høyytelses binær protokoll med streng typesikkerhet. Brukes til synkrone interne interaksjoner hvor lavest mulig latens kreves.
4. **RabbitMQ AMQP (Core API $\leftrightarrow$ Scraper Service)**: Asynkron meldingskø for frikobling av krevende operasjoner.

---

## 4. Informasjonsflyt og Prosesser

### Prosess A: Standard Forespørsel & Autentisering (Synkron)
1. Klienten sender en HTTP-forespørsel med et JWT-token i headeren til **`recipe-gateway-api`**.
2. **`recipe-gateway-api`** validerer tokenet (ved hjelp av **`recipe-authentication-api`** sin offentlige nøkkel/JWKS).
3. Dersom tokenet er gyldig, beriker Gateway forespørselen med en intern identitetsheader (`X-User-Id`) og ruter kallet videre til **`recipe-core-api`** over **gRPC**.
4. **`recipe-core-api`** behandler forespørselen mot **`recipe-core-db`** og returnerer svaret tilbake samme vei.

### Prosess B: Skraping av Ekstern Oppskrift (Hybrid Synkron / Asynkron)
1. **Initiell forespørsel**: Bruker limer inn en ekstern URL i `recipe-web-app`. Klienten sender forespørsel til Gateway.
2. **Rask Cache-sjekk (Synkron gRPC)**: `recipe-core-api` gjør et umiddelbart gRPC-kall til **`recipe-scraper-service`**: *"Finnes denne URL-en i cachen?"*
   * **Treff i cache**: Data hentes direkte fra **`recipe-scraper-cache`** (MongoDB), returneres til `recipe-core-api`, og videre til brukeren.
   * **Ikke i cache**: Prosessen går over til asynkron modus.
3. **Asynkron Skrapejobb**:
   * `recipe-core-api` legger en oppgavemelding (`ScrapeRecipeCommand`) på **`recipe-message-broker`** (RabbitMQ) og returnerer status `202 Accepted` til klienten.
   * Frontend viser en visuell indikator ("Henter oppskrift...").
4. **Bakgrunnsutførelse**:
   * **`recipe-scraper-service`** plukker jobben fra RabbitMQ i et kontrollert tempo, kjører **Playwright (Chromium)** for å rendre og hente ut strukturerte data, og lagrer rådataen i **`recipe-scraper-cache`**.
   * Scraper Service publiserer deretter en hendelsesmelding (`RecipeScrapedEvent`) tilbake på RabbitMQ.
5. **Sanntidsvarsling (SignalR Push)**:
   * **`recipe-core-api`** lytter på hendelsen fra RabbitMQ, prosesserer og lagrer den nye oppskriften i **`recipe-core-db`**.
   * Core API benytter sin **SignalR Hub** til å sende en "oppskrift klar"-melding direkte til brukerens aktive WebSocket-forbindelse.
   * **`recipe-web-app`** mottar meldingen og oppdaterer UI-et sømløst i sanntid.

---

## 5. Sikkerhet og Identitetsstyring

* **Sentralisert Token-validering**: `recipe-gateway-api` fungerer som et skjold mot omverdenen. Ingenting slipper gjennom til interne tjenester uten gyldig autentisering.
* **Isolering av Brukerdata**: `recipe-authentication-api` eier alt som har med passord, tokens, tofaktorautentisering og brukerkontoer å gjøre. `recipe-core-api` forholder seg kun til bruker-ID-er (`X-User-Id`), noe som sikrer at sensitive innloggingsdata aldri blandes med oppskriftsdata.
* **Sikre Interne Nettverk**: Kun `recipe-gateway-api` og `recipe-web-app` er tilgjengelige fra utsiden. Alle mikrotjenester, meldingskøer og databaser ligger skjermet i det interne Docker-nettverket.

---

## 6. Driftsmodell og Docker-organisering

* **Felles Eksternt Docker-nettverk (`recipe-net`)**: 
  * Nettverket `recipe-net` opprettes og eies av **`recipe-infrastructure`**-repositoriet.
  * Alle andre applikasjons-repoer (`recipe-core-api`, `recipe-authentication-api`, osv.) kobler seg til dette nettverket som et eksternt nettverk (`external: true`).
* **Intern Navneoppslag (DNS)**: Tjenestene kommuniserer direkte med hverandre på `recipe-net` via sine definerte containernavn (f.eks. `http://recipe-authentication-api`, `http://recipe-scraper-service`, `amqp://recipe-message-broker`).
* **Spesialiserte Base-images**:
  * Standard .NET-tjenester kjører på slanke, optimaliserte ASP.NET runtime-images.
  * `recipe-scraper-service` kjører på Microsofts offisielle Playwright .NET-image som inneholder alle nødvendige OS-biblioteker for kjøring av headless nettlesere.
* **Persistent Datalagring**: Både PostgreSQL-instansene og MongoDB benytter dedikerte Docker Volumes definert i `recipe-infrastructure` for å garantere at data overlever container-oppdateringer og omstarter.
