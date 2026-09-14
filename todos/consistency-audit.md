# Konsistenssjekk på tvers av tjenester (2026-09-14, oppdatert 2026-09-14)

Automatisk gjennomgang av Dockerfiles, Serilog-oppsett og MassTransit-contracts i alle
`.NET`-tjenestene.

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

## 🟡 Pending: `recipe-core-api` og `recipe-scraper-service` er begge tidlig i utviklingen

Bruker har bekreftet: `recipe-core-api` har foreløpig kun kontaktskjema-funksjonaliteten
implementert (resten av kjernedomenet — oppskrifter, måltidsplaner, m.m. — er ikke påbegynt),
og `recipe-scraper-service` er et bevisst utsatt fremtidig prosjekt som ikke påbegynnes før
core-api har kommet et godt stykke. Funnene under er derfor ikke noe som haster — de blir
naturlig ryddet opp i etter hvert som disse tjenestene bygges ut, og er kun listet her som en
påminnelse for når det arbeidet starter:

* **`ContactFormSubmittedEvent`-namespace er ulikt** mellom `recipe-core-api`
  (`Contracts.Events`, i mappa `Contracts/Event/` — entall) og
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
