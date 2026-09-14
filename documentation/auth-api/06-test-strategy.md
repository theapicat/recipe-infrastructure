# Teststrategi for `recipe-auth-api`

> Revidert etter en full kodegjennomgang. Det opprinnelige utkastet (generert med begrenset innsyn i faktisk kode) fikk riktig overordnet struktur, men bommet på noen konkrete verktøyvalg og manglet en del sikkerhetskritiske edge-caser som bare dukker opp når man faktisk leser handlerne. De er lagt til under.

## 1. Formål og Testfilosofi

Siden `recipe-auth-api` er den mest kritiske sikkerhets- og identitetstjenesten i Kjøkkenhylla-plattformen (autentisering, autorisasjon, OpenIddict-tokens, svartelisting), skal teststrategien gi høy trygghet uten at testkjøringen blir treg eller vanskelig å vedlikeholde.

Strategien bygger på en lagdelt testpyramide forankret i Clean Architecture:

* **Forretningslogikken isoleres:** Kontrollerne er bevisst tynne og gjør lite annet enn å rute HTTP-forespørsler videre til MediatR.
* **MediatR er arbeidshesten:** Den reelle enhetstestingen skjer på Commands, Queries og Handlers i `Application`-laget.
* **Sociable, ikke fullstendig isolert, der Identity er involvert:** Se punkt 3 — `UserManager`/`SignInManager` mockes ikke, de kjøres ekte mot en lettvekts database.

---

## 2. Testlag og Ansvarsområder

### Lag 1: Enhetstesting av Forretningslogikk (MediatR Handlers)

* **Hovedfokus:** Kjernen i enhetstestene — all forretningslogikk ligger i MediatR-behandlerne.
* **Hva verifiseres:** input-validering og forretningsregler, tilstandsendringer i Identity, korrekt publisering av utgående hendelser.
* **Testmetode:** `UserManager<ApplicationUser>`/`SignInManager<ApplicationUser>` kjøres ekte mot en EF Core-database i minnet (se punkt 3 om providervalg) — ikke som mock. Rene grensesnitt (`IPublishEndpoint`, `ITokenService`, `IOpenIddictTokenManager`, `IOpenIddictApplicationManager`) mockes med NSubstitute.

### Lag 2: Hendelses- og Meldingstesting (MassTransit Consumers)

* **Hovedfokus:** Asynkron, event-drevet kommunikasjon — særlig `InvalidEmailDetectedConsumer`.
* **Hva verifiseres:** at mottak av `InvalidEmailDetectedEvent` utløser svartelisting, token-revokering (`IOpenIddictTokenManager`) og kontosletting — **og at gjentatt levering av samme event er trygt** (se testmatrise, punkt 4.3).
* **Testmetode:** MassTransit sin In-Memory Test Harness (`AddMassTransitTestHarness`). `IOpenIddictTokenManager.FindBySubjectAsync` returnerer `IAsyncEnumerable<object>` — NSubstitute krever et lite hjelpeoppsett for dette (f.eks. `System.Linq.Async` sin `ToAsyncEnumerable()`), ikke en triviell `Returns(...)`.

### Lag 3: Bakgrunnsjobber og Livsløpslogikk (Quartz.NET)

* **Hovedfokus:** `AccountLifecycleJob`.
* **Hva verifiseres:** de 6 uavhengige skannene (7d/14d/30d ubekreftet, 6m/1y/1y+30d inaktivitet) med tidsmanipulerte kontoer, **inkludert at de seks skannene kan overlappe i én og samme jobbkjøring** (se 4.4) og at admin-kontoer aldri rammes (`GetAdminUserIdsQuery`).
* **Testmetode:** Kjøres direkte mot databasen i minnet — se providervalg i punkt 3, siden `GetAdminUserIdsQuery` bruker en `Join`+`Contains`-spørring som ikke alltid oversettes likt på tvers av EF-providere.

### Lag 4: API- og Integrasjonstesting (Controllers & OpenIddict)

* **Hovedfokus:** Hele HTTP-pipelinen, OpenIddict token-utstedelse, rollebasert autorisasjon.
* **Hva verifiseres:** token-utstedelse/fornyelse via `/connect/token`, token-inndragelse via `/connect/revoke`, at `/api/auth/admin/*` krever `admin`-rollen (401/403 for andre).
* **Testmetode:** `WebApplicationFactory` (`Tests/Support/AuthApiWebApplicationFactory.cs`) — se providervalg i punkt 3, dette er laget der valg av databaseprovider betyr mest.
* **Dette er det eneste laget som kan fange feil inne i OpenIddicts egen handler-pipeline:** `Tests/Integration/TokenServiceIssueTokenPairTests.cs` kaller `TokenService.IssueTokenPairAsync` (Google-innloggingens token-utstedelse, se `Documentation/05-openiddict-security-and-jobs.md` seksjon 3) mot den ekte, fullt oppstartede verten. Dette var bevisst — samme funksjonalitet testet kun via mocket `ITokenService` i Lag 1 (`ProcessGoogleCallbackCommandHandlerTests`) skjulte tre reelle runtime-feil i OpenIddicts interne pipeline som kun dukket opp ved faktisk Google-innlogging i nettleseren. Lag 1-tester som mocker bort `ITokenService`/`IOpenIddictTokenManager` beviser aldri at selve tokenutstedelsen fungerer — kun at handleren *kaller* den riktig.

---

## 3. Testverktøy og Biblioteker — med to korrigerte valg

* **xUnit, NSubstitute, Shouldly:** Som opprinnelig planlagt.
* **MassTransit Test Framework:** Som opprinnelig planlagt.
* **Databaseprovider — SQLite in-memory i stedet for EF Core In-Memory:** `UseSqlite("DataSource=:memory:")` med en åpen `SqliteConnection` holdt i live for testens levetid. **Begrunnelse:** EF Core sin rene In-Memory-provider er ikke en relasjonell motor — den håndterer ikke alltid `Join`+`Contains`-spørringer korrekt (brukt i `AccountLifecycleJob.GetAdminUserIdsQuery`), og OpenIddict sine EF Core-stores forutsetter reell relasjonell oppførsel (unike constraints, transaksjoner) som In-Memory-provideren ikke håndhever. SQLite in-memory gir ekte SQL-semantikk uten Docker-avhengighet, og fungerer med både Identity og OpenIddict sine EF Core-stores.
* **Ekte `UserManager`/`SignInManager` i stedet for NSubstitute-mocks av dem:** Disse klassene har mye intern logikk (passordhashing, lockout-telling, concurrency stamps, e-post-normalisering) som er upraktisk og risikabelt å re-implementere korrekt via mocks — man ender fort med å teste mock-oppsettet i stedet for ekte atferd. Sett dem opp én gang via `AddIdentity<ApplicationUser, IdentityRole<Guid>>().AddEntityFrameworkStores<ApplicationDbContext>()` mot SQLite in-memory, og gjenbruk oppsettet i et delt test-fixture.
* **Microsoft.AspNetCore.Mvc.Testing (`WebApplicationFactory`):** Som opprinnelig planlagt, for Lag 4.

### Prosjektoppsett

`Tests.csproj` har `ProjectReference` til `API`, `Application`, `Persistence`, `Domain` og `Contracts`, samt alle pakkene nevnt over (`NSubstitute`, `Shouldly`, `MassTransit.TestFramework`, `Microsoft.EntityFrameworkCore.Sqlite`, `Microsoft.AspNetCore.Mvc.Testing`). Ingen ytterligere oppsett trengs for å legge til en ny test i noen av de fire lagene — se `Tests/Support/HandlerTestHarness.cs` (Lag 1–3) og `Tests/Support/AuthApiWebApplicationFactory.cs` (Lag 4) for de delte test-fixturene.

---

## 4. Konkret sikkerhetstestmatrise

Dette er scenarioer funnet ved faktisk å lese handlerne — ikke generiske "test suksess og feil"-punkter, men konkrete ting som *ville* vært lett å overse.

### 4.1 Admin-vs-admin-beskyttelse (nylig rettet, må låses fast med tester)

`LockUserCommandHandler`, `DeleteUserAdminCommandHandler`, `DeleteAndBlacklistUserCommandHandler` og `AdminUpdateUserCommandHandler` blokkerte tidligere kun *selv*-handling (`CurrentAdminId == targetGuid`) — en admin kunne låse, slette eller endre e-posten til en **annen** admin-konto uten sperre. Dette er nå rettet: alle fire sjekker `userManager.IsInRoleAsync(target, "admin")` og avviser handlingen uansett hvem som er mål. Testmatrise per handler:

* Admin A låser/sletter/endrer bruker B (vanlig bruker) → skal lykkes.
* Admin A låser/sletter/endrer **seg selv** → skal avvises (`IsBadRequest`/`IsForbidden`, spesifikk melding).
* Admin A låser/sletter/endrer **Admin B** (en annen administrator) → skal avvises (`IsBadRequest`, generisk "annen administratorkonto"-melding).
* `UnlockUserCommandHandler` har **ingen** slik sjekk i det hele tatt (kun `NotFound`) — vurder om oppheving av sperre på en admin-konto er en risiko verdt samme behandling, eller om det er trygt nok siden admin-kontoer aldri kan bli sperret av `AccountLifecycleJob` i utgangspunktet. Skriv en test som dokumenterer *dagens* valgte atferd eksplisitt, uansett konklusjon.

### 4.2 Svarteliste — konsistens på tvers av to uavhengige implementasjoner

`RegisterUserCommandHandler` og `ProcessGoogleCallbackCommandHandler` implementerer *samme* sjekk (eksakt e-post OG domene) helt uavhengig av hverandre. Skriv **parametriserte tester som kjører identiske scenarioer mot begge handlerne** (eksakt match, domene-match, case-sensitivitet — `Pattern.ToLower()` vs. innkommende e-post med blandet case, subdomene-forsøk som `bruker@sub.svartelistet-domene.no` som *ikke* skal matche et rent domene-mønster på `svartelistet-domene.no` med mindre det er tiltenkt). Dersom disse noensinne driver fra hverandre, skal testene fange det umiddelbart — vurder på sikt å trekke sjekken ut til en delt tjeneste.

### 4.3 `InvalidEmailDetectedConsumer` — idempotens ved gjenlevering

* Samme event konsumeres to ganger på rad → ingen duplikat i `BlacklistedEntries` (denne sjekken finnes allerede: `isAlreadyBlacklisted`), og andre kjøring (bruker allerede slettet) skal ikke kaste exception, bare logge og fortsette.
* Event uten `UserId` (kun e-post) mot en bruker som har byttet e-post siden → verifiser oppslag på e-post fungerer som forventet fallback.
* Bruker med aktive OpenIddict-tokens → verifiser at *alle* tokens faktisk revokeres (`TryRevokeAsync` kalt per token, ikke bare første) før sletting.

### 4.4 `AccountLifecycleJob` — overlappende skann i én kjøring

De 6 skannene er uavhengige og ekskluderer ikke hverandre. En bruker som er registrert og ubekreftet i 35 dager når jobben kjører for første gang (f.eks. etter nedetid), vil kunne bli **påminnet (skann 1), sperret (skann 2) og slettet (skann 3) i samme jobbkjøring** — slettingen i skann 3 sjekker ikke om skann 1/2 sine "sendt"-flagg er satt. Dette er sannsynligvis OK (sluttresultatet — sletting — er korrekt), men bør være et **eksplisitt, dokumentert testscenario**, ikke noe som oppdages ved en tilfeldighet senere. Test også: en admin-konto som ellers ville trigget alle 6 skannene skal ikke røres av noen av dem (`GetAdminUserIdsQuery`-ekskluderingen).

### 4.5 Token-livssyklus

* `PasswordGrantCommandHandler`/`RefreshTokenGrantCommandHandler`: sperret konto (`LockoutEnd` i fremtiden) og deaktivert konto (`CanSignInAsync == false` uten lockout) er to *forskjellige* tilstander — test begge separat, ikke bare én som proxy for begge.
* Refresh-token-flyten stoler på `AuthenticatedPrincipal.GetClaim(Subject)` — test at en bruker slettet *etter* at et gyldig refresh-token ble utstedt, men *før* det brukes til fornyelse, korrekt avvises (`FindByIdAsync` returnerer null).
* Faktisk token-revokering (Lag 4/integrasjon): etter at `DeleteAndBlacklistUserCommandHandler` eller `InvalidEmailDetectedConsumer` revokerer tokens, skal et påfølgende `refresh_token`-kall med det revokerte tokenet faktisk avvises av OpenIddict selv — dette er en integrasjonstest, ikke en unit test, siden avvisningen skjer i OpenIddict sin egen valideringspipeline før handleren nås.

### 4.6 Google-callback — rekkefølge

Svartelistesjekken skjer *før* både oppslag på eksisterende bruker og opprettelse av ny bruker (`ProcessGoogleCallbackCommandHandler`, steg 1). Test eksplisitt at en svartelistet e-post **aldri** når frem til `userManager.CreateAsync`/`AddLoginAsync` i det hele tatt (ikke bare at resultatet blir feil — bruk en spy/mock-verifisering på at disse metodene ikke ble kalt).

### 4.7 Transaksjonsatferd i `DeleteAndBlacklistUserCommandHandler`

Denne handleren bruker nå en eksplisitt DB-transaksjon (se tidligere endring). Test at hvis `userManager.DeleteAsync` feiler, blir svartelisteoppføringen **rullet tilbake** (ikke hengende igjen uten tilhørende sletting) — dette krever en ekte transaksjonell provider (SQLite in-memory), ikke EF Core In-Memory, som ikke støtter ekte transaksjoner.

---

## 5. Retningslinjer for Vedlikehold og CI/CD

1. **Rask tilbakemelding:** Enhetstester for MediatR-handlere og event-consumers skal kjøre på få sekunder lokalt før commit.
2. **Krav ved nye funksjoner:** Hver ny MediatR Command/Query skal ha tilhørende tester som dekker suksess- og feilscenarier — inkludert eventuelle admin/selv-beskyttelses-sjekker, etter mønsteret i punkt 4.1.
3. **Automatisert pipeline:** Hele testsettet kjøres automatisk i CI/CD ved bygging og Pull Requests.
