# Konsistenssjekk på tvers av tjenester (2026-09-14, oppdatert 2026-09-26)

Gjennomgang av Dockerfiles, Serilog-oppsett, MassTransit-contracts, dokumentasjonsspeil og
`appsettings*.json` i alle `.NET`-tjenestene. Seksjonen «2026-09-26» er nyest; «2026-09-19» og
«2026-09-14» under er historikk (statusen der er oppdatert der den har endret seg).

---

# 2026-09-26

Full revisjon (alle fem punktene) etter en uke med arbeid i `recipe-core-api` (P1/P2, kontosletting, `dimension`, seed-opprydding,
allergener). `recipe-scraper-service` er holdt utenfor som før. API-testsuiten er oppdatert og kjørt grønn mot den levende stacken:
**576 bestått, 2 hoppet over** via gatewayen, like mange med `--direct`, og 65 med `--read-only`.

## ✅ Løst / bekreftet

* **Kontaktskjemaet leverer e-post (var 🔴).** Core flyttet `ContactFormSubmittedEvent` til `Contracts.Events.UserActions` 2026-09-24, nå
  byte-identisk i core, notification og auth. Bekreftet ende-til-ende 2026-09-26: hver innsending gir varsel til admin («[Kontaktskjema] …»)
  og kvittering til avsender («Takk for din henvendelse: …») i Mailpit; køen `ContactFormSubmitted` har 1 consumer og tom `_error`-kø.
  Begge e-postene står nå i testsuitens e-postsjekkliste. **Men se 🔴 under: valideringen mangler fortsatt.**
* **Kontosletting rydder brukerdata i Core** (bygget 2026-09-23). Køene `CoreApi-AccountDeletedByUser`, `CoreApi-AccountDeletedBySystem`,
  `CoreApi-UserAccountDeletedByAdmin` og `CoreApi-UserDeletedAndBlacklistedByAdmin` har hver 1 consumer, 0 meldinger og ingen `_error`-kø,
  etter en testkjøring som slettet ~50 testbrukere. Core bruker eksplisitte kønavn (`CoreApi-…`), så den deler ikke kø med notification.
* **Verifisert gjennom gatewayen** (TECHNICAL_DEBT #6), dekket av testsuiten via `:5000`: URL-enkodede næringsstoff-id-er (`Vit C`,
  `Mono+Di` osv., alle 57), gjentatt `excludeAllergenId`, og `Location` ved `201`. Se 🟡 om verten i `Location`.
* **`CORE_5XX_ON_CLIENT_ERROR` (var 🟡) er i praksis løst:** ukjente fremmednøkler gir nå spesifikke `400` (ingredienser, enheter), en
  katalograd eller ingrediens i bruk gir `409` med melding, og ukjent id på `DELETE` gir `404`. Klienten kan ikke lenger sende id-er ved
  opprettelse. Gjenstår som dokumentert avvik: `PUT` på en ukjent katalog-id gir `200` uten å gjøre noe.
* **JWT** er identisk i alle seks kildene (auth `appsettings` ×2, core Development, gateway Development, gatewayens `.env` og
  compose-fallback): issuer `http://recipe-auth-app/`, audience `recipe-frontend`, samme nøkkel (sammenlignet som hash). **Delt JWT-oppsett:**
  auth signerer (`JWT:SecretKey`), gateway og core validerer hver for seg (`Jwt:Key`/`Issuer`/`Audience`); alle tre må endres samtidig,
  ellers gir hvert kall `401` uten annen feilmelding. Utenfor Development må verdiene komme fra miljøvariabler (`Jwt__Key` osv.), siden
  gatewayens og cores base-`appsettings.json` ikke har noen `Jwt`-blokk.
* **Dockerfiles:** auth, gateway og notification følger fortsatt samme mønster (`aspnet:10.0`/`sdk:10.0`, `base/build/publish/final`).
  Core og webapp har ingen Dockerfile ennå (dockerisering er parkert).
* **Serilog:** alle fem tjenestene har identisk struktur; `Properties.Application` = repo-navnet; Seq `recipe-seq:80` i base og
  `localhost:5341` i Development.
* **RabbitMQ-blokken** er identisk i auth, core og notification (base og Development), og passordet stemmer med infra-`.env`.
  Postgres-strengene i Development stemmer med `.env` (auth `5432`, core `5433`).
* **Dokumentasjonsspeilet** er kopiert på nytt: `core-api/` (01–07 endret, `08-api-reference.md` ny) og `webapp/` (01–09 endret,
  `10-backlog.md` ny). Alle sju speil verifisert med `diff -rq` (tomt resultat).
* **Alle 19 hendelsene mellom auth og notification** (utenom den døde kontaktskjema-kopien i auth) har samme namespace i begge repoene, og alle har en consumer.

## 🔴 Kontaktskjemaet er et åpent e-postrelé nå som det virker

Feil 2 fra 2026-09-19 (under) står uendret, men er ikke lenger teoretisk: e-postene går faktisk ut. `ContactFormRequest` har ingen
valideringsattributter, `SubmittedAt` kommer fra klienten, det finnes ingen rate limiting i gateway eller core, og malene
(`ContactFormAdminNotification.html`, `ContactFormUserReceipt.html`) skriver `{{ name }}`/`{{ subject }}`/`{{ message }}` uten
`html.escape`. **Konsekvens:** hvem som helst kan uten innlogging få Kjøkkenhylla sin avsenderadresse til å sende en kvittering med
fritt valgt emne og HTML-innhold til en hvilken som helst adresse, så mange ganger de vil. I dev er det ufarlig, men det må rettes
før noe settes i drift. Ikke rørt (kontaktskjema-koden endres bare på uttrykkelig beskjed).

## 🟡 Nye funn

* **`PASSWORD_CHANGED_NULLABILITY`:** `PasswordChangedEvent.IpAddress`/`DeviceInfo` er `string?` i auth, men `string` i notification.
  Samme namespace og type, så meldingen kommer fram; `null` blir `null` i notification og malen skriver tom tekst. Samme type avvik som
  `UserDeletedAndBlacklistedByAdminEvent.Reason` (`string?` i auth og core, `string` i notification, TECHNICAL_DEBT #3).
* **Filnavn ≠ typenavn i to repoer, ikke bare auth:** `AccountDeletedByUserEvent.cs` og `AccountDeletedBySystemEvent.cs` inneholder
  `UserAccountDeletedByUserEvent`/`UserAccountDeletedBySystemEvent` i både auth og notification (core har riktige filnavn). Kun kosmetisk.
* **Død kopi:** auth har `ContactFormSubmittedEvent` uten publisher eller consumer.
* **Kønavn:** notification (22 consumers) og auth (`InvalidEmailDetectedConsumer`) bruker MassTransit sine standardnavn (`PasswordChanged`,
  `AccountDeletedByUser` …); bare core setter egne. En ny tjeneste med en consumer med samme klassenavn ville stille delt køen
  (TECHNICAL_DEBT #2).
* **Foreldreløs kø:** `UserAccountDeleted` (0 consumers, 0 meldinger) er en rest fra et eldre navn. Ufarlig; kan slettes i RabbitMQ-UI-et.
* **`Location` via gatewayen peker på Core sin egen vert:** `POST http://localhost:5000/api/admin/allergens` svarer
  `Location: http://localhost:5002/api/admin/allergens/<id>`. Gatewayen skriver ikke om headeren. Frontend bruker `id` fra kroppen, så
  ingenting brekker, men en klient som følger `Location` går forbi gatewayen. Rettes eventuelt i gatewayen (YARP-transform) eller ved å
  la core lage en relativ `Location`.
* **`usageCount` i skrivesvar er alltid 0 (core):** svaret på `POST`/`PUT` av en ingrediens og på `approve` setter `usageCount = 0`, fordi
  tallet bare regnes ved lesing. Etter `approve` gir `GET` `1` (den løste ubekreftede raden peker på ingrediensen). Testene tar høyde for det.
* **Seedede søkeord er ikke systemrader (core):** `seed_31` (55 synonymer) og søkeordene i `seed_11`, `seed_13`, `seed_20` settes inn uten
  `is_system`, så de kan slettes når de ikke er i bruk. `08-api-reference.md` sier fortsatt at `search-keywords` «starter tom».
* **Utdatert i core sin `08-api-reference.md`:** «Per 2026-09-20»; nederst står «opprydding når en konto slettes» og «allergen-tilordning»
  som ikke bygget (begge finnes nå), og næringsavsnittet sier at enhetstypene gjenkjennes på navnet (nå `dimension`).
* **Ukommitterte rettelser:** fiksene fra 2026-09-20 (fast `SetIssuer`, `role` med små bokstaver i gateway-policyen, oppdatert
  gateway-dokumentasjon og compose-fallback) ligger fortsatt som ukommitterte endringer i `recipe-auth-api` og `recipe-gateway-api`. De
  kjørende tjenestene bruker dem, men de finnes ikke i git ennå.

## 🟡 Fortsatt åpne fra tidligere (sjekket 2026-09-26, uendret)

* `RESET_PASSWORD_REVEALS_USERS`, `REGISTER_JSON_NOT_BOUND` (`[Consumes(... "application/json")]` + `[FromForm]`),
  `AUTH_HEALTH_SERVICE_NAME` (`/api/auth/health` gir fortsatt `service: "API"`).
* `recipe-scraper-cache` er fortsatt den containeren som holder `localhost:27017`, og `recipe-mongo-db` er ikke koblet til noe nettverk
  (se under).
* Cores base-`appsettings.json` blander Docker-navn og `localhost` (parkert til core dockeriseres).

---

# 2026-09-19

## ✅ Løst 2026-09-19

* **Dokumentasjonsspeilet** i `documentation/` er oppdatert og verifisert identisk med kildene
  (`diff -rq`) for alle seks speil: `auth-api`, `core-api`, `gateway-api`, `notification-service`,
  `webapp`, `legal` (og `scraper-service`-README). `core-api/` speiler nå de sju dokumentene i
  `recipe-core-api/Documentation/` i stedet for README-en, og `webapp/` har fått
  `09-recipe-domain-and-planned-pages.md`.
* **`CLAUDE.md` og `README.md`** i dette repoet er oppdatert: fjernet referansen til den ikke-eksisterende
  `todos/notification-integration.md`, rettet MongoDB-containernavnet i README (`recipe-mongo-db`, delt av
  notification- og scraper-tjenesten), lagt til appsettings-revisjon som punkt 5 i revisjonsrutinen, og
  skrevet inn brukerens avgjørelser (se under).
* **JWT-nøkkelen i `recipe-core-api`** (`API/appsettings.Development.json`) var tom, så Core API ville ha
  kastet `InvalidOperationException` ved oppstart. Fylt inn med samme dev-nøkkel som Auth API og gateway
  (godkjent av bruker).
* **`recipe-gateway-api/docker-compose.yml`**: standardverdien for `JWT_KEY` (brukes kun hvis `.env` mangler)
  var en helt annen nøkkel enn den Auth API signerer med. Da ville alle tokens gitt `401` uten annen
  feilmelding. Satt til samme dev-nøkkel.
* **`DOCUMENTATION_GUIDE.md`** er fjernet av bruker. De tre døde referansene i `recipe-core-api`
  (`CLAUDE.md`, `RECIPE_BACKEND_NOTES.md`, `todo.md`) er fjernet.

## 📌 Avgjort av bruker 2026-09-19

* **Andre brukeres data eksisterer ikke for innlogget bruker.** Brukerspesifikke spørringer filtrerer på eier
  fra tokenet og gir tomt resultat (tom liste), aldri `403`, og ikke en `404` som avslører at ressursen
  finnes. Skrevet inn i `recipe-core-api` (`Documentation/05`, `RECIPE_BACKEND_NOTES.md`, `todo.md`) og i
  `CLAUDE.md` her. Gjennomgang av eksisterende API-er: I Auth API er det kun `AdminController`
  (rolle `admin`) som har id-ruter (`users/{id}`, `blacklist/{id}`); `AccountController` handler alltid på
  «meg» fra token-claims; Core API har ingen
  eide ressurser ennå (kun delte kataloger, `Recipe.OwnerUserId` er eneste spor). Ingenting å endre i dag.
  **Fortsatt åpent:** statuskode/kropp for oppslag, endring eller sletting av *én* ressurs på id som tilhører
  en annen bruker.
* **Kontaktskjemaet er anonymt** og skal fungere for brukere som ikke er innlogget. Se under: ingenting i
  dag krever en bruker. **Ingen endringer i kontaktskjema-eventet uten uttrykkelig beskjed.**

## Funnet av den nye API-testsuiten (`api-tests/`)

Suiten (se `api-tests/README.md`) ble kjørt mot en levende stack 2026-09-19. De to første (🔴) er rettet 2026-09-20.
Feilene som fortsatt står (🟡) testes **ikke** lenger (fjernet etter ønske 2026-09-20: testsuiten skal bare dekke det som
finnes og skal virke). De står her som notater, til de eventuelt rettes.

**✅ RETTET 2026-09-20 — `TOKEN_ISSUER` (var 🔴: ingen innlogget bruker kom gjennom til Core).**
Tokenet Auth API utstedte via `/connect/token` fikk `iss` lik forespørselens base-URL (`http://localhost:5000/` via
gatewayen, `:5001` direkte), mens gateway og Core validerte mot `Jwt:Issuer`. Alle innloggede brukere fikk
`401 The issuer '…' is invalid` på `/api/user/**` og `/api/admin/**`. Ingen hadde merket det fordi Auth validerer mot sin
egen issuer, og fordi Core sine brukerendepunkter er nye. Rettet med en fast issuer: `options.SetIssuer(...)` i
`recipe-auth-api/API/Extensions/OpenIddictExtensions.cs`, med vakt som kaster ved oppstart hvis `JWT:Issuer` ikke er en
absolutt URI på normalisert form. Verdien er endret fra `recipe-auth-app` til `http://recipe-auth-app/` og står nå
bokstavelig likt i auth (appsettings ×2), gateway (Development, compose-fallback, lokal `.env`, README) og core
(Development, testkonfig, docs). Verifisert: tokenet har `iss = http://recipe-auth-app/` uansett om det hentes via
gatewayen eller direkte, og både gateway og Core godtar det. Auth 119/119 og Core 34/34 xUnit-tester består.
*Effekt ved utrulling:* tokens og refresh tokens utstedt før endringen er ugyldige; alle må logge inn på nytt.

**✅ RETTET 2026-09-20 — `GATEWAY_ADMIN_ROLE_CASING` (var 🔴: admin fikk 403 på `/api/admin/**` via gatewayen).**
`AdminUser`-policyen brukte `RequireRole("Admin")` mens tokenet har `role: admin`. Rettet til `RequireRole("admin")` i
`recipe-gateway-api/API/Extensions/GatewayPolicyExtensions.cs`. Verifisert: admin får 200 på admin-rutene både via
gatewayen og direkte mot Core, og vanlig bruker får fortsatt 403. Øvrige forekomster av «Admin»/«User» som rollenavn
er gjennomgått (kode, kommentarer og docs i alle repoer); se «Løst» øverst.

**✅ (i praksis) `CORE_5XX_ON_CLIENT_ERROR`** — se 2026-09-26. Core svarer `500` med Npgsql-unntakstekst i kroppen på: dupliserte id-er
(`23505`), ugyldig fremmednøkkel (`23503`, f.eks. en unit med ukjent `unitTypeId`) og sletting av en rad andre rader
peker på (`23503`). Skal være 4xx (400/409) og skal ikke lekke databasedetaljer. Dessuten: `PUT` på ukjent id gir
`200` uten å gjøre noe, og duplikate *navn* aksepteres (ingen unikhetsregel) — dokumentert oppførsel, ikke testet som feil.

**🟡 `RESET_PASSWORD_REVEALS_USERS`.** `POST /api/auth/account/reset-password` gir `404 «Bruker ikke funnet»` for
ukjent e-post, men `400` (ugyldig token) for kjent. Dermed kan man finne registrerte adresser, selv om `/recover`
er nøye generisk. Begge tilfeller bør gi samme svar.

**🟡 `REGISTER_JSON_NOT_BOUND`.** `POST /api/auth/account/register` har `[Consumes("…form-urlencoded", "application/json")]`
men `[FromForm]`, så en JSON-body aksepteres og bindes aldri (alle felt «mangler»). Webappen sender skjema, så det
virker i praksis; enten fjern `application/json` fra `[Consumes]` eller bytt til `[FromBody]`.

**🟡 `AUTH_HEALTH_SERVICE_NAME`.** `GET /api/auth/health` returnerer `service: "API"` mens gateway og Core returnerer
repo-navnet.

**🟡 `CONTACT_FORM_NO_VALIDATION`.** (Se også kontaktskjema-seksjonen under.) Bekreftet av testsuiten: tomme felt gir `200`.

**🟢 Bekreftet i orden (verifisert av suiten):**
* Anonym avvises (`401`) på alle beskyttede gateway-ruter, og vanlig bruker får `403` på alle 14 admin-endepunkter i Auth API og alle admin-ruter i Core.
* Spoofede `X-User-Id`/`X-User-Roles` fra klienten gir aldri tilgang.
* CORS tillater kun frontend-opprinnelsen.
* Innlogging før e-postbekreftelse er tillatt (bevisst, 14-dagers frist), sperrede brukere kan ikke logge inn, slettede brukere kan ikke logge inn.
* Hele livssyklusen (opprett, les, endre, slett) virker for alle seks kataloger (rett mot Core), og admin-endringer ugyldiggjør cachen i brukerlistene umiddelbart.
* Kontaktskjemaet virker uten innlogging (uten header og med `Bearer undefined`) og krever ingen bruker.
* E-postsjekklisten stemmer med hva Mailpit faktisk mottok. Unntaket er de 6 kontaktskjema-e-postene per kjøring, som forventet ikke kommer (namespace-feilen under). Bekreftet empirisk: eksakt de e-postene sjekklisten merker med ⚠️ uteblir.

**Mangler noe i endepunktene for å teste «opprett, endre, slett, rydd»?** Nei, ingenting som blokkerer:
brukere kan slettes fullstendig (`POST /admin/users/delete`), svartelisteoppføringer kan fjernes, og katalograder kan slettes
med klient-valgt id. Begrensninger (ikke blokkeringer): `GET /admin/users` har ikke filter/paginering (`PaginatedResponse`
finnes, men brukes ikke), så testene filtrerer klientsiden; e-postlenke-flyter (`confirm-email`, `reset-password` med
gyldig token) kan bare fullføres ved å lese e-posten, så brukere bekreftes via admin-endepunktet; katalogene er tomme i
dev (`source-data/` lastes ikke), så det finnes ingen seedet referansedata å lese; ingredienser, næringsstoffer,
oppskrifter, måltidsplan og handleliste har ingen endepunkter ennå. De to reelle blokkeringene (`TOKEN_ISSUER` og
`GATEWAY_ADMIN_ROLE_CASING`) er rettet 2026-09-20, og Core-endepunktene testes nå via gatewayen som en ekte bruker.

## ✅ Kontaktskjemaet: meldinger forsvant stille (Feil 1 rettet i core 2026-09-24, verifisert 2026-09-26; Feil 2 er fortsatt åpen, se 🔴 øverst)

**Flyt (verifisert i koden):** `ContactForm.tsx` → Next-rute `app/api/public/contact/route.ts` →
gateway `POST /api/public/contact-form` (`public-route`, ingen policy, ingen fallback-policy) →
`ContactFormController` (`[AllowAnonymous]`, `PublicController`) → `SendContactFormCommandHandler` →
`IEventPublisher` (MassTransit) → RabbitMQ → `ContactFormSubmittedConsumer` → `ContactFormProcessor` →
to e-poster (admin + kvittering til avsender).

**Krever noe i flyten en bruker? Nei.** Ingen `UserId`, ingen `X-User-Id`, ingen oppslag mot Auth API i
webapp-ruten, kontrolleren, kommandoen, eventet eller prosessoren. Eventet har kun
`Name/Email/Subject/Message/SubmittedAt`. Testet også at en anonym forespørsel med
`Authorization: Bearer undefined` (det webappens `agentExternal.post` sender uten sesjon, fordi
`getToken()` gir `undefined`) slipper gjennom et `[AllowAnonymous]`-endepunkt med samme JwtBearer-oppsett som
gateway/core: `200` uten header, med `Bearer undefined` og med `Bearer `; `401` kun på `[Authorize]`.
Ren kosmetikk: `agentExternal.post` bør utelate headeren når token mangler, slik `postForm` allerede gjør.

**Feil 1 — ✅ (var 🔴) namespace-uoverensstemmelse (bekreftet mot kjørende RabbitMQ; rettet 2026-09-24):**

| | Namespace | Exchange |
| --- | --- | --- |
| Core API i dag | `Contracts.Event` (entall, mappe `Contracts/Event/`) | `Contracts.Event:ContactFormSubmittedEvent` — finnes ikke ennå (Core har ikke publisert med dagens kode) |
| Notification-service (consumer) | `Contracts.Events.UserActions` | `Contracts.Events.UserActions:ContactFormSubmittedEvent` → bundet til kø `ContactFormSubmitted` |
| Auth API | `Contracts.Events.UserActions` (identisk kopi) | ingen publisher og ingen consumer; død kopi |

MassTransit binder exchange på fullt kvalifisert typenavn. Første gang Core publiserer, opprettes
`Contracts.Event:ContactFormSubmittedEvent` **uten noen binding til noen kø**, og RabbitMQ forkaster meldingen
uten feil. **Konsekvens:** handleren returnerer `true`, brukeren ser «Takk! Meldingen er sendt», og verken
admin-varsel eller kvittering blir noen gang sendt. Ingenting logges som feil noe sted.
Broker-historikk: det finnes også en `Contracts.Events:ContactFormSubmittedEvent`-exchange (samme namespace
som Core hadde ved revisjonen 14. sept.) som fortsatt er bundet til `ContactFormSubmitted`-køen, og en
`MassTransit:Fault--Contracts.Events:ContactFormSubmittedEvent--`-exchange. Trolig rester fra tidligere
namespace-varianter (ikke undersøkt nærmere); de gjør ikke dagens problem mindre.
Ingen kall er observert så langt (køen `ContactFormSubmitted` har 0 meldinger og 0 consumers akkurat nå;
notification-servicen kjørte ikke).

**Forslag til retting (IKKE gjort, venter på beskjed):** flytt eventet i Core til
`Contracts/Events/UserActions/ContactFormSubmittedEvent.cs` med `namespace Contracts.Events.UserActions;`,
byte-identisk med Notification (og ev. slett den døde kopien i Auth API). En liten test i Core som
sammenligner `typeof(ContactFormSubmittedEvent).FullName` med den forventede strengen fanger regresjon.

**Feil 2 — 🟡 ingen serverside-validering på et anonymt endepunkt:**

* `ContactFormRequest` (i `Domain`, som har `<Nullable>disable</Nullable>`) har ingen valideringsattributter,
  så tom/manglende `Name`, `Email`, `Subject`, `Message` slipper gjennom. Webappen validerer (gyldig e-post,
  emne ≤ 150, melding ≤ 2000 tegn), men det omgås ved direktekall mot `/api/public/contact-form`.
* Handleren returnerer alltid `true`; `BadRequest("Ugyldig epost eller forespørsel")` i kontrolleren kan aldri nås.
* `SubmittedAt` kommer fra klienten (standardverdi `DateTime.UtcNow`) og kan forfalskes.
* Ingen rate limiting i gateway eller Core.
* E-postmalene (`ContactFormAdminNotification.html`, `ContactFormUserReceipt.html`) skriver ut
  `{{ name }}`, `{{ subject }}`, `{{ message }}` uten `html.escape`, og Scriban escaper ikke automatisk.

**Samlet risiko når Feil 1 er rettet:** hvem som helst kan få din avsenderadresse til å sende en e-post
(med fritt valgt emne og HTML-innhold) til hvilken som helst adresse, uten pålogging og uten begrensning.
Verdt å ha validering og rate limiting på plass først.

## 🟡 `recipe-scraper-cache` er en foreldreløs container som holder port 27017

`docker ps` viser to Mongo-containere fra samme compose-prosjekt: `recipe-scraper-cache` (fra før tjenesten ble
omdøpt i `docker-compose.yaml`, opprettet 30. aug, volum `recipe-infrastructure_mongo_cache_data`, publisert
på `localhost:27017`, på `recipe-net`) og `recipe-mongo-db` (opprettet 16. sept., volum
`recipe-infrastructure_mongo_data`, **ikke koblet til noe nettverk**). Det som faktisk svarer på
`localhost:27017` er den gamle. `docker compose down` fjerner ikke foreldreløse containere, og
`recipe-mongo-db` (navnet Notification-servicens Docker-oppsett bruker) er ikke nåbar på `recipe-net`.
Ikke rørt (sletter data): når du vet at innholdet i det gamle volumet ikke trengs, kjør
`docker compose down --remove-orphans` og `docker compose up -d`, og ev.
`docker volume rm recipe-infrastructure_mongo_cache_data`.

## ✅ Dokumentasjon i `recipe-gateway-api` var utdatert: rettet 2026-09-20

`Dokumentasjon/core-api.md` sa at Core ikke gjør egen autentisering og at det ikke finnes konfigurasjon å holde i sync.
Omskrevet: Core validerer JWT selv, og `Jwt:Key`/`Issuer`/`Audience` må være identiske. Gatewayens `CLAUDE.md`, `README.md`
og `Dokumentasjon/auth-api.md` er oppdatert for små rollenavn og ny issuer. Speilet her er kopiert på nytt og verifisert.

## ✅ `AdminUser`-policyen i gatewayen: rettet 2026-09-20

`RequireRole("Admin")` → `RequireRole("admin")`. Se «RETTET 2026-09-20 — `GATEWAY_ADMIN_ROLE_CASING`» over.

## appsettings-revisjon 2026-09-19

Verdier sammenlignet uten å skrive ut hemmeligheter. **`recipe-scraper-service` er holdt utenfor** etter
brukerens ønske (prosjektet er ikke påbegynt; ingen opprydding der før arbeidet starter).

| Sjekk | Resultat |
| --- | --- |
| JWT `Issuer` og `Audience` i auth, gateway, core | 🟢 identiske; issuer endret 2026-09-20 til `http://recipe-auth-app/` (absolutt URI), `Audience` = `recipe-frontend` |
| JWT signeringsnøkkel: auth (`JWT:SecretKey`) = gateway (`Jwt:Key`, både `appsettings.Development.json` og `.env`) | 🟢 identiske |
| JWT-nøkkel i core (`Jwt:Key`) | 🟢 rettet: var tom (se «Løst») |
| Gatewayens `docker-compose.yml` standard `JWT_KEY` | 🟢 rettet: var en annen nøkkel (se «Løst») |
| `ClockSkew = 0` og `ValidateLifetime` i gateway og core; SignalR-token fra `?access_token=` kun under `/hubs` | 🟢 likt |
| `RabbitMQ`-blokk (host, port, vhost, bruker, passord) i auth, core, notification | 🟢 identiske. Scraper har ingen ennå (ikke bygget) |
| DB-, Mongo- og RabbitMQ-legitimasjon mot `recipe-infrastructure/.env` | 🟢 stemmer overalt |
| Postgres-porter: auth `5432`, core `5433` (Core Development bruker `5433`) | 🟢 stemmer med infra-`.env` |
| Serilog: base `recipe-seq:80`, Development `localhost:5341`, `Properties.Application` = repo-navn | 🟢 likt (uendret fra 14. sept.) |
| **Alle `appsettings.Development.json` mot infra-`.env`** (auth, core, notification, gateway): Postgres host/port/db/bruker/passord, Mongo-streng, RabbitMQ, SMTP `localhost:1025`, Seq `localhost:5341`, gatewayens clustere `localhost:5001/5002/5003` | 🟢 alle felt stemmer (kontrollert 2026-09-19). Forventet Postgres-streng: `Host=localhost;Port=<*_DB_PORT>;Database=<*_DB_NAME>;Username=<*_DB_USER>;Password=<*_DB_PASSWORD>;Client Encoding=UTF8;` (auth `5432`, core `5433`) |
| **Live innloggingstest** med nøyaktig strengene fra Development-filene mot de kjørende containerne | 🟢 auth (`localhost:5432`) og core (`localhost:5433`) logger inn, UTF8-koding; Mongo-strengen til notification svarer på `ping`; SMTP `1025`, Seq `5341` og Mailpit-UI `8025` svarer |
| `recipe-core-api/API/appsettings.json`: `ConnectionStrings` peker på `Host=recipe-core-db;Port=5432` (Docker-navn), mens auth/notification har `localhost` i base-filen og overstyrer via `docker-compose.yml`. Samme fil har `RabbitMQ:Host=localhost` og Seq `recipe-seq`, så den er også internt blandet | 🟡 parkert av bruker: dockerisering av appene er ikke i fokus (alt kjører på `localhost` unntatt infrastrukturen). Velg konvensjon når Core dockeriseres |
| Auth bruker `JWT:SecretKey`, gateway/core `Jwt:Key` | 🟢 nøkler i .NET-konfigurasjon er ikke case-sensitive; kun egenskapsnavnet er ulikt (kode, ikke endret) |
| Gatewayens `appsettings.json` har ingen `Jwt`-blokk (kun Development-filen), core har ingen i base-filen | 🟡 fungerer i Development og via compose; utenfor Development må verdiene komme fra miljøvariabler |
| Auth `Logging:LogLevel` (Debug/OpenIddict) skiller seg fra de andre i Development | 🟢 kun logging, ufarlig |
| `SmtpSettings:AdminNotificationEmail` (`admin@kjokkenhylla.no`) vs. Auth-admin (`admin@kjoekkenhylla.local`) | 🟢 to ulike formål, bevisst |

---

# 2026-09-14

## ✅ Løst: Serilog-oppsett er nå identisk på tvers av alle fem tjenester

Etter avklaring med bruker er dette rettet direkte i de aktuelle repoene (eneste unntak fra
regelen om at kun `recipe-infrastructure` skal endres — eksplisitt godkjent):

* `recipe-auth-api/API/appsettings.json`: lagt til manglende `MinimumLevel`-blokk, og rettet
  `"Application": "recipe-authentication-api"` → `"recipe-auth-api"`.
* `recipe-gateway-api/API/appsettings.json`: lagt til manglende `MinimumLevel`-blokk.
* `recipe-scraper-service/Service/appsettings.json`: rettet `"Application": "recipe-core-api"`
  (copy-paste-feil) → `"recipe-scraper-service"`.
* `recipe-core-api` og `recipe-notification-service` var allerede korrekte, ingen endring.

Alle fem `appsettings.json` har nå identisk `Serilog`-struktur (`Using`, `MinimumLevel` med
samme `Override`-verdier, `WriteTo` mot Console + Seq på `recipe-seq:80`, `Enrich`, og en
`Properties.Application` som matcher repo-navnet). Alle fem `appsettings.Development.json` var
allerede identiske (Console + Seq mot `localhost:5341`) — ingen endring nødvendig der.

## 🟢 Ikke en bug lenger: GitHub-kontoen `mrBellwood84` på `recipe-webapp` og `recipe-gateway-api`

Avklart med bruker: `mrBellwood84` var den private GitHub-kontoen prosjektet startet på før de
første to repoene (`recipe-webapp`, `recipe-gateway-api`) ble opprettet. Alle syv prosjekter er
siden flyttet/eid av `theapicat`-kontoen, men `origin`-remoten i disse to lokale klonene ble
aldri oppdatert til å peke dit. Ikke en reell inkonsistens i koden — bare en lokal git-remote
som peker på riktig repo, men under feil konto-URL. Kan rettes med `git remote set-url origin
https://github.com/theapicat/<repo>.git` i de to repoene den dagen brukeren ønsker det; ingen
hast.

## 🟢 Utdatert (historikk): `recipe-core-api` og `recipe-scraper-service` er begge tidlig i utviklingen

*2026-09-26: core-api har nå kataloger, ingredienser, oppskrifter og kontosletting, og kontaktskjemaets namespace er rettet. Avsnittet står som historikk.*

Bruker har bekreftet: `recipe-core-api` har foreløpig kun kontaktskjema-funksjonaliteten
implementert (resten av kjernedomenet — oppskrifter, måltidsplaner, m.m. — er ikke påbegynt),
og `recipe-scraper-service` er et bevisst utsatt fremtidig prosjekt som ikke påbegynnes før
core-api har kommet et godt stykke. Funnene under er derfor ikke noe som haster — de blir
naturlig ryddet opp i etter hvert som disse tjenestene bygges ut, og er kun listet her som en
påminnelse for når det arbeidet starter:

* **`ContactFormSubmittedEvent`-namespace er ulikt** mellom `recipe-core-api`
  (`Contracts.Event` i dag, i mappa `Contracts/Event/` — entall; var `Contracts.Events` da dette ble skrevet
  14. sept. Se «🔴 Kontaktskjemaet» øverst for verifisering mot RabbitMQ) og
  `recipe-notification-service`/`recipe-auth-api` (`Contracts.Events.UserActions`, i
  `Contracts/Events/` — flertall). MassTransit binder RabbitMQ-exchange på fullt kvalifisert
  typenavn som standard, så dette er i praksis to forskjellige exchanges — kontaktskjema-eventet
  fra `recipe-core-api` når etter alt å dømme aldri fram til `recipe-notification-service` i
  dag. Rettes naturlig når core-api sine contracts ryddes opp manuelt (bruker har sagt dette
  gjøres samlet, ikke per-funksjon).
* Utover kontaktskjemaet har `recipe-core-api` ingen egne MassTransit-contracts ennå — det
  meste av meldingsflyten i dag går kun mellom `recipe-auth-api` og
  `recipe-notification-service`.
* En tidligere plan om at et fremtidig "system/health"-API skulle høre til `recipe-core-api`
  (bl.a. for retry av feilede notifikasjoner) er droppet — dette blir i stedet en helt egen,
  uavhengig tredje applikasjon (`recipe-system-api` e.l.) for helsesjekker og drift på tvers av
  tjenestene. `recipe-gateway-api` har allerede reservert ruten `/api/system/{**catch-all}` for
  dette (se `documentation/gateway-api/system-api.md`).

## 🟢 Det som er konsistent

* Dockerfiles i `recipe-auth-api`, `recipe-gateway-api` og `recipe-notification-service` følger
  identisk multi-stage-mønster (`aspnet:10.0` runtime, `sdk:10.0` build, samme stage-navn).
  `recipe-core-api`, `recipe-scraper-service` og `recipe-webapp` mangler ennå egen Dockerfile —
  stemmer med at de er tidlig i utviklingen (se respektive README).
* Alle 18 event-kontraktene under `UserActions`/`AdminActions`/`SystemActions` (inkl.
  `InvalidEmailDetectedEvent`) er byte-for-byte identiske mellom `recipe-auth-api` og
  `recipe-notification-service` — akkurat slik delte MassTransit-contracts skal være.
* `recipe-webapp/public/docs/legal/*.md` og kopien i `recipe-infrastructure/documentation/legal/`
  er identiske.
