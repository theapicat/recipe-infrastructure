# 🏗️ Overordnet Arkitekturdokument: Recipe Application

## 1. Systemvisjon og Prinsipper

**Recipe Application** er arkitekturert som et distribuert, mikrotjeneste-basert system. Systemet er designet for å være skalerbart, fleksibelt og forberedt for fremtidige utvidelser (som en dedikert mobilapplikasjon), samtidig som det skiller skarpt mellom ulike ansvarsområder (*Separation of Concerns*).

### Hovedprinsipper:

* **Single Gateway Inngang**: All ekstern trafikk sluses gjennom én felles API Gateway (`recipe-gateway-api`).
* **Isolerte Tjenester**: Hver applikasjon har sitt eget Git-repositorium, definerte ansvarsområder og eier sine egne data.
* **Stateless Auth & Header Injection**: Gateway validerer JWT-tokens lokalt i minnet og beriker forespørsler videre internt med verifiserte identitets-headers (`X-User-Id`, `X-User-Roles`).
* **Helhetlig Asynkron Kommunikasjon**: All interntjeneste-kommunikasjon og bakgrunnsjobber håndteres asynkront via en felles meldingsbuss (RabbitMQ + MassTransit). Systemet benytter **ingen** synkrome gRPC- eller interne HTTP-kall mellom mikrotjenestene.
* **Sentralisert Logging**: Alle tjenester sender strukturerte logger (Serilog) til et felles Seq-dashboard for full sporbarhet.
* **Full Containerisering**: Alle infrastrukturelementer (databaser, meldingsbuss, logging) kjører som isolerte Docker-containere koblet på et felles Docker-nettverk (`recipe-net`).

---

## 2. Applikasjonsoversikt & Teknologistack

| Prosjektnavn (Repo) | Hovedteknologi | Rolle & Hovedansvar | Nettverkseksponering |
| --- | --- | --- | --- |
| **`recipe-web-app`** | Next.js, TypeScript, React | Brukergrensesnitt for web. Rendring av sider, brukermoduler og sanntidsoppdateringer. | **Offentlig** (Port 3000) |
| **`recipe-gateway-api`** | .NET, YARP | Sentral inngangsdør (Reverse Proxy). Håndterer CORS, YARP-routing, lokal JWT-validering og header-sanitering. | **Offentlig** (Port 5000) |
| **`recipe-authentication-api`** | .NET, ASP.NET Core Identity | Identitetsstyring. Brukerregistrering, innlogging, tokenutstedelse og kontobegrensninger. | **Internt / Lokal host** (Port 5001) |
| **`recipe-core-api`** | .NET, SignalR Hub | Kjernedomenet. Forretningslogikk for oppskrifter, ingredienser og SignalR sanntidshub. | **Internt / Lokal host** (Port 5002) |
| **`recipe-scraper-service`** | .NET, Playwright, MassTransit | Ekstern datainnhenting. Skraper og strukturerer oppskrifter fra eksterne nettsider basert på meldinger fra køen. | **Internt Docker-nettverk** (`recipe-net`) |
| **`recipe-notification-service`** | .NET 10, MassTransit, MailKit | Bakgrunnstjeneste for e-post og varsling. Genererer og sender e-poster for registrering, bekreftelser og henvendelser. | **Internt Docker-nettverk** (`recipe-net`) |
| **`recipe-infrastructure`** | Docker Compose | Felles repository for databaser, meldingsbuss og loggmotor. | **Internt Docker-nettverk** (`recipe-net`) |

### Infrastruktur-containere (Styrt via `recipe-infrastructure`):

* **`recipe-auth-db`** (PostgreSQL - Port 5432): Lagring av brukerkontoer, passord-hashes, tilganger og roller.
* **`recipe-core-db`** (PostgreSQL - Port 5433 på vert): Lagring av oppskrifter, trinn, ingredienser og kategorier.
* **`recipe-scraper-cache`** (MongoDB - Port 27017): Dokumentdatabase for mellomlagring av skrapt rådata.
* **`recipe-message-broker`** (RabbitMQ - Port 5672 / 15672): Sentral meldingsbuss for **all** internkommunikasjon, bakgrunnsjobber og hendelser.
* **`recipe-seq`** (Seq - Port 5341): Sentralisert dashboard for mottak og visualisering av strukturerte Serilog-logger.

---

## 3. Kommunikasjonsmodeller og Protokoller

```
# =================================================================================
[ recipe-web-app ]
(Next.js Frontend)
                                |
                     HTTP REST / WebSockets
                                v
# =================================================================================
[ recipe-gateway-api ]
(YARP Gateway - Port 5000)
       |                                             |
HTTP REST (/api/auth)                        HTTP REST (/api/public, /user)
       v                                             v
+-------------------------------+             +---------------------------------+
|  recipe-authentication-api    |             |        recipe-core-api          |
|    (Port 5001 - Auth API)     |             |    (Port 5002 - Core API)       |
+-------------------------------+             +---------------------------------+
       |               |                               |                |
  (PostgreSQL)         | AMQP Events                   | AMQP Events    | (PostgreSQL)
       v               v                               v                v
[recipe-auth-db]  +-------------------------------------------------+ [recipe-core-db]
                  |             recipe-message-broker               |
                  |                (RabbitMQ Bus)                   |
                  +-------------------------------------------------+
                               ^                       ^
                   AMQP Events |                       | AMQP Events
                               v                       v
                  +-------------------------+ +---------------------------------+
                  | recipe-scraper-service  | |  recipe-notification-service    |
                  |  (Playwright / Scraper) | | (MailKit / E-postutsendelse)    |
                  +-------------------------+ +---------------------------------+
                               |
                           (MongoDB)
                               v
                    [recipe-scraper-cache]

```

### Kommunikasjonsprotokoller:

1. **HTTP REST (Ekstern $\rightarrow$ Gateway $\rightarrow$ Mikrotjenester)**: Standard JSON-basert HTTP-kommunikasjon fra frontend til gateway, som ruter kallet videre over HTTP til riktig bakendepunkt.
2. **WebSockets / SignalR (Ekstern $\leftrightarrow$ Gateway $\leftrightarrow$ Core API)**: Toveis sanntidsforbindelse for sanntidsoppdateringer. Gateway ruter `/hubs`-endepunkter videre med tilhørende tilgangstokens.
3. **RabbitMQ AMQP / MassTransit (Felles Intern Meldingsbuss)**: **Eneste** protokoll for kommunikasjon *mellom* bakendens mikrotjenester. Alle bakgrunnsjobber, e-postutsendelser, skrapeforespørsler og domenehendelser publiseres asynkront via RabbitMQ.

---

## 4. Informasjonsflyt og Prosesser

### Prosess A: Standard Forespørsel & Autentisering (Synkron)

1. Klienten sender en HTTP-forespørsel med et JWT Bearer-token i headeren til **`recipe-gateway-api`**.
2. **`recipe-gateway-api`** validerer tokenet **lokalt i minnet** vha. den delte `JWT__KEY`.
3. Gateway fjerner eventuelle innkommende `X-User-Id` / `X-User-Roles` headers fra klienten for å forhindre spoofing.
4. Dersom tokenet er gyldig, injiserer Gateway nye, verifiserte `X-User-Id`- og `X-User-Roles`-headers og ruter forespørselen videre over HTTP til **`recipe-core-api`** eller **`recipe-authentication-api`**.

### Prosess B: Asynkron Hendelsesutveksling (Hendelsesdrevet)

1. Ved en hendelse i systemet (f.eks. `UserRegisteredEvent` fra Auth API eller `ScrapeRecipeRequestedEvent` fra Core API), publiseres en melding til **`recipe-message-broker`** (RabbitMQ) via MassTransit.
2. Relevante mikrotjenester (`recipe-notification-service` eller `recipe-scraper-service`) lytter på sine respektive køer, prosesserer oppgaven i sitt eget tempo og publiserer ev. svar- eller status-events tilbake på bussen.

---

## 5. Sikkerhet og Identitetsstyring

* **Sentralisert Token-validering i Gateway**: Ingen uautentiserte forespørsler slipper gjennom til beskyttede endepunkter i bakenden.
* **Isolering av Brukerdata**: `recipe-authentication-api` eier brukeridentiteter. `recipe-core-api` forholder seg kun til verifiserte identitets-headers (`X-User-Id`), noe som sikrer at sensitive innloggingsdata aldri leker inn i domenelagene.
* **Sikre Interne Nettverk**: Kun `recipe-gateway-api` og `recipe-web-app` skal eksponeres eksternt i produksjon. Alle databaser, meldingskøer og interne mikrotjenester kommuniserer skjermet på Docker-nettverket (`recipe-net`).