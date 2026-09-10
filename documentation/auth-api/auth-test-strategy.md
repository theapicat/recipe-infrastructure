# Teststrategi for `recipe-auth-api`


## 1. Formål og Testfilosofi

Siden `recipe-auth-api` er den mest kritiske sikkerhets- og identitetstjenesten i Kjøkkenhylla-plattformen (håndtering av autentisering, autorisasjon, OpenIddict-tokens, sikkerhets-cookies og svartelisting), må teststrategien gi 100 % trygghet uten at testkjøringen blir treg eller vanskelig å vedlikeholde.

Strategien bygger på en lagdelt testpyramide forankret i Clean Architecture:

* **Forretningslogikken isoleres:** Kontrollerne i Auth API er bevisst tynne og gjør lite annet enn å rute innkommende HTTP-forespørsler direkte videre til MediatR.
* **MediatR er arbeidshesten:** Den reelle enhetstestingen skjer på MediatR Commands, Queries og Handlers i `Application`-laget.
* **In-Memory isolasjon:** Både database og meldingsbuss kjøres i minnet under testing, slik at testsettet kjører lynraskt uten eksterne avhengigheter til Docker eller fysiske databaser.

---

## 2. Testlag og Ansvarsområder

### Lag 1: Enhetstesting av Forretningslogikk (MediatR Handlers)

* **Hovedfokus:** Dette utgjør kjernen i enhetstestene. Siden controllere kun fungerer som tynne ruting-komponenter, ligger hele forretningslogikken i MediatR-behandlerne.
* **Hva verifiseres:**
* Validering av input og forretningsregler (f.eks. avvisning av registrering dersom e-posten ligger i svartelisten).
* Tilstandsendringer i Identity- systemet (passordbytte, e-postbekreftelse, brukerprofilering).
* Korrekt publisering av utgående domene-hendelser over MassTransit (f.eks. `UserRegisteredEvent`).


* **Testmetode:** Handlere testes i full isolasjon. Eksterne avhengigheter (`UserManager`, `SignInManager`, `IPublishEndpoint`) mockes ut, mens datatiltand valideres mot en In-Memory EF Core database.

### Lag 2: Hendelses- og Meldingstesting (MassTransit Consumers)

* **Hovedfokus:** Verifisere asynkron, event-drevet kommunikasjon fra andre mikrotjenester.
* **Hva verifiseres:**
* Reaksjonsmønstre på meldinger utenfra – spesielt `InvalidEmailDetectedConsumer` ved uleverbare e-poster (Hard Bounce fra Notification Service).
* At mottak av hendelsen utløser korrekt sikkerhetsrespons: permanent sletting av brukerkontoen, oppføring i `BlacklistedEntries`, og umiddelbar revokering av aktive OpenIddict-tokens.


* **Testmetode:** Kjøres i minnet via MassTransit sin In-Memory Test Harness uten behov for en ekstern RabbitMQ-broker.

### Lag 3: Bakgrunnsjobber og Livsløpslogikk (Quartz.NET)

* **Hovedfokus:** Automatiserte, tidsstyrte oppryddings- og vedlikeholdsprosesser (`AccountLifecycleJob`).
* **Hva verifiseres:**
* **Opprydding av ubekreftede kontoer:** Korrekt tidslinje for e-postpåminnelse (7 dager), sperring (14 dager) og permanent sletting (30 dager).
* **Inaktivitet:** Varsling etter 6 måneders inaktivitet og sperring etter 1 år.


* **Testmetode:** Eksekvering av jobblogikken direkte mot In-Memory databasen med tidsmanipulerte tilstander på brukerkontoene (`CreatedAt`, `LastLoginAt`).

### Lag 4: API- og Integrasjonstesting (Controllers & OpenIddict)

* **Hovedfokus:** Verifisere at hele HTTP-pipelinen, middleware, OpenIddict token-utstedelse og rollebasert autorisasjon fungerer som en helhet.
* **Hva verifiseres:**
* **OAuth2 / OpenIddict:** Korrekt utstedelse og fornyelse av JWT og Refresh Tokens via `/connect/token`.
* **Sikkerhet og Cookies:** Verifisering av at følsomme sesjonstokens returneres i `HttpOnly` cookies.
* **Autorisasjon:** At administrative endepunkter (`/api/admin/*`) krever Admin-rolle, og avviser vanlige brukere eller uautentiserte forespørsler med korrekt HTTP-statuskode (401/403).


* **Testmetode:** Kjøres som "end-to-end" tester mot `WebApplicationFactory` i et kontrollert testmiljø.

---

## 3. Testverktøy og Biblioteker

For å holde testkoden konsistent med resten av økosystemet benyttes følgende etablerte verktøy:

* **xUnit:** Hovedrammeverk for testkjøring og strukturering.
* **NSubstitute:** Enkelt og lesbart mocking-bibliotek for å erstatte grensesnitt og avhengigheter.
* **Shouldly:** Ekspressivt assertion-bibliotek som gir klare og lesbare feilmeldinger hvis en test feiler.
* **MassTransit Test Framework:** In-memory harness for testing av meldingskøer, consumers og event-publisering.
* **EF Core In-Memory:** Rask database i minnet for isolert testing av datatransaksjoner og identitetsoperasjoner.
* **Microsoft.AspNetCore.Mvc.Testing (`WebApplicationFactory`):** Rigg for end-to-end API- og integrasjonstester.

---

## 4. Retningslinjer for Vedlikehold og CI/CD

1. **Rask tilbakemelding:** Enhetstester for MediatR-handlere og event-consumers skal kjøres på få sekunder lokalt i IDE/terminal før kode commitles.
2. **Krav ved nye funksjoner:** Hver gang en ny MediatR Command eller Query legges til i `Application`-laget, skal det skrives tilhørende enhetstester som dekker både suksess- og feilscenarier.
3. **Automatisert pipeline:** Hele testsettet (unit, consumer, job og integrasjon) kjøres automatisk i CI/CD-pipelinen ved bygging og Pull Requests.