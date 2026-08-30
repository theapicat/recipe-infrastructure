# 🏗️ Overordnet Arkitekturdokument: Kjøkkenhylla

## 1. Systemvisjon og Prinsipper
**Kjøkkenhylla** er arkitekturert som et distribuert, mikrotjeneste-basert system. Systemet er designet for å være skalerbart, fleksibelt og forberedt for fremtidige utvidelser (som en dedikert mobilapplikasjon), samtidig som det skiller skarpt mellom ulike ansvarsområder (*Separation of Concerns*).

### Hovedprinsipper:
* **Single Gateway Inngang**: All ekstern trafikk sluses gjennom én felles API Gateway (`recipe-gateway-api`).
* **Isolerte Tjenester**: Hver applikasjon har sitt eget Git-repositorium, definerte ansvarsområder og eier sine egne data.
* **Stateless Auth & Header Injection**: Gateway validerer JWT-tokens lokalt i minnet og beriker forespørsler videre internt med verifiserte identitets-headers (`X-User-Id`, `X-User-Roles`).
* **Sentralisert Logging**: Alle tjenester sender strukturerte logger (Serilog) til et felles Seq-dashboard for full sporbarhet.
* **Full Containerisering**: Alle infrastrukturelementer (databaser, meldingsbuss, logging) kjører som isolerte Docker-containere koblet på et felles Docker-nettverk (`recipe-net`).

---

## 2. Applikasjonsoversikt & Teknologistack

| Prosjektnavn (Repo) | Hovedteknologi | Rolle & Hovedansvar | Nettverkseksponering |
| :--- | :--- | :--- | :--- |
| **`recipe-web-app`** | Next.js, TypeScript, React | Brukergrensesnitt for web. Rendring av sider, brukermoduler og sanntidsoppdateringer. | **Offentlig** (Port 3000) |
| **`recipe-gateway-api`** | .NET 8/9, YARP | Sentral inngangsdør (Reverse Proxy). Håndterer CORS, YARP-routing, lokal JWT-validering og header-sanitering. | **Offentlig** (Port 5000) |
| **`recipe-authentication-api`** | .NET, ASP.NET Core Identity | Identitetsstyring. Brukerregistrering, innlogging og utstedelse av JWT-tokens med felles hemmelig nøkkel. | **Internt / Lokal host** (Port 5001) |
| **`recipe-core-api`** | .NET, SignalR Hub | Kjernedomenet. Forretningslogikk for oppskrifter, ingredienser og SignalR sanntidshub. | **Internt / Lokal host** (Port 5002) |
| **`recipe-scraper-service`** | .NET, Playwright | Ekstern datainnhenting. Skraper og strukturerer oppskrifter fra eksterne nettsider. | **Internt Docker-nettverk** (`recipe-net`) |
| **`recipe-infrastructure`** | Docker Compose | Felles repository for databaser, meldingsbuss og loggmotor. | **Internt Docker-nettverk** (`recipe-net`) |

### Infrastruktur-containere (Styrt via `recipe-infrastructure`):
* **`recipe-auth-db`** (PostgreSQL - Port 5432): Lagring av brukerkontoer, passord-hashes, tilganger og roller.
* **`recipe-core-db`** (PostgreSQL - Port 5433 på vert): Lagring av oppskrifter, trinn, ingredienser og kategorier.
* **`recipe-scraper-cache`** (MongoDB - Port 27017): Dokumentdatabase for mellomlagring av skrapt rådata.
* **`recipe-message-broker`** (RabbitMQ - Port 5672 / 15672): Meldingsbuss for asynkron oppgavekø og hendelsesbasert kommunikasjon.
* **`recipe-seq`** (Seq - Port 5341): Sentralisert dashboard for mottak og visualisering av strukturerte Serilog-logger.

---

## 3. Kommunikasjonsmodeller og Protokoller


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
                          (YARP Gateway - Port 5000)
=================================================================================
           |                                             |
    HTTP REST (/api/auth)                   HTTP REST (/api/public, /user, /hubs)
           v                                             v
+-------------------------------+             +---------------------------------+
|  recipe-authentication-api    |             |        recipe-core-api          |
|    (Port 5001 - Auth API)     |             |  (Port 5002 - Core & SignalR)   |
+-------------------------------+             +---------------------------------+
           |                                   |         |              ^
           v                               SQL |    gRPC |         AMQP | Event Push
   [recipe-auth-db]                            v         v              |
     (PostgreSQL)                       [recipe-core-db] |              |
                                          (PostgreSQL)   v              |
                                              +---------------------+   |
                                              | recipe-scraper-     |   |
                                              |      service        |   |
                                              +---------------------+   |
                                                 |             |        |
                                         MongoDB |        AMQP |        |
                                                 v             v        |
                                        [recipe-scraper-  [recipe-message-broker]
                                            cache]           (RabbitMQ)---------+
                                          (MongoDB)
```

### Kommunikasjonsprotokoller:
1. **HTTP REST (Ekstern $\rightarrow$ Gateway $\rightarrow$ Mikrotjenester)**: Standard JSON-basert HTTP-kommunikasjon. Gateway validerer JWT og ruter kallet videre til riktig API over HTTP.
2. **WebSockets / SignalR (Ekstern $\leftrightarrow$ Gateway $\leftrightarrow$ Core API)**: Toveis sanntidsforbindelse. Gateway ruter `/hubs`-endepunkter videre med tilhørende access tokens.
3. **gRPC (Core $\rightarrow$ Scraper Service)**: Høyytelses binær protokoll for direkte, synkro interne cache-sjekker og spørringer.
4. **RabbitMQ AMQP (Core API $\leftrightarrow$ Scraper Service)**: Asynkron meldingskø for krevende bakgrunnsjobber (f.eks. tunge skrapeoperasjoner).

---

## 4. Informasjonsflyt og Prosesser

### Prosess A: Standard Forespørsel & Autentisering (Synkron)
1. Klienten sender en HTTP-forespørsel med et JWT Bearer-token i headeren til **`recipe-gateway-api`**.
2. **`recipe-gateway-api`** validerer tokenet **lokalt i minnet** vha. den delte `JWT__KEY`.
3. Gateway fjerner eventuelle innkommende `X-User-Id` / `X-User-Roles` headers fra klienten for å forhindre spoofing.
4. Dersom tokenet er gyldig, injiserer Gateway nye, verifiserte `X-User-Id`- og `X-User-Roles`-headers og ruter forespørselen videre over HTTP til **`recipe-core-api`** eller **`recipe-authentication-api`**.
5. Mikrotjenesten behandler forespørselen og returnerer svaret.

---

## 5. Sikkerhet og Identitetsstyring

* **Sentralisert Token-validering i Gateway**: Ingen uautentiserte forespørsler slipper gjennom til beskyttede endepunkter i bakenden.
* **Isolering av Brukerdata**: `recipe-authentication-api` eier brukeridentiteter. `recipe-core-api` forholder seg kun til verifiserte identitets-headers (`X-User-Id`), noe som sikrer at sensitive innloggingsdata aldri leker inn i domenelagene.
* **Sikre Interne Nettverk**: Kun `recipe-gateway-api` og `recipe-web-app` skal eksponeres eksternt i produksjon. Alle databaser, meldingskøer og interne APIs kommuniserer skjermet på Docker-nettverket (`recipe-net`).


## 6. Lokal E-posttesting (Mailpit)

I utviklingsmiljøet benyttes **Mailpit** som en lokal, felles SMTP-samlekasse (catch-all) for å teste alle e-postflyter (bekreftelser, passordtilbakestillinger, varsler) helt trygt uten eksterne e-postservere.

* **SMTP Host (fra vert/lokal app):** `localhost:1025`
* **SMTP Host (internt i Docker-nettverk):** `recipe-mailpit:1025`
* **Web UI Innboks:** `http://localhost:8025`
* **Autentisering:** Ingen (pass-through)

### Hurtigstart
1. Start tjenesten via Docker Compose:
   ```bash
   docker compose up -d recipe-mailpit