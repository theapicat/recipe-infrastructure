# CQRS og MediatR i `recipe-auth-api`

---

## 1. Mønster og Arkitekturprinsipper

`recipe-auth-api` benytter **CQRS (Command Query Responsibility Segregation)** i kombinasjon med **MediatR** for å skille lese- og skriveoperasjoner i `Application`-laget. Dette sikrer en ryddig Clean Architecture hvor forretningslogikk er fullstendig frakoblet HTTP-infrastrukturen.

### Kjernepinsipper i Tjenesten

* **Tynne Kontrollere (Thin Controllers):** REST-kontrollere (`AccountController`, `AdminController`, `AuthorizationController`) har ingen forretningslogikk. De fungerer utelukkende som HTTP-adaptere som pakker innkommende forespørsler inn i MediatR-kommandoer/spørringer, sender dem videre til mønsterbussen, og returnerer riktig HTTP-respons.
* **Tydelig Skille mellom Kommandoer og Spørringer:**
* **Commands (`IRequest<TResult>`):** Handlinger som endrer tilstand i systemet (opprettelse, oppdatering, sletting, låsing, passordbytte). Kommandoer kan også trigge asynkrone domene-hendelser over MassTransit.
* **Queries (`IRequest<TResponse>`):** Leseoperasjoner som henter ut data fra databasen uten sideeffekter eller endring av systemtilstand.


* **Resultat-mønster (Explicit Results):** Forretningsfeil og valideringsavvik (f.eks. feil passord, sperret konto, eller e-post på svarteliste) håndteres ikke ved å kaste uventede unntak (Exceptions). I stedet returneres eksplisitte resultat-objekter (`RegisterUserResult`, `TokenExchangeResult`, osv.) med statusflagg og feilbeskrivelser. Dette gir en forutsigbar flyt og renere feilhåndtering i API-laget.

---

## 2. Modulstruktur i Application-laget

All CQRS-logikk er organisert under `Application/Mediator/`, inndelt etter funksjonelle domener:

```text
Application/Mediator/
├── Account/            # Sluttbrukers selvbetjening og kontostyring
│   ├── Commands/       # Endrer brukertilstand (Registrering, Passord, Profil, osv.)
│   └── Queries/        # Henter brukerrelaterte data (f.eks. brukerprofil)
├── Admin/              # Administrativ bruker- og systemstyring
│   ├── Commands/       # Overstyring, sperring, manuell bekreftelse og svartelisting
│   └── Queries/        # Oppslag i brukermasse, brukerdetaljer og svartelister
└── Authorization/      # OAuth2 / OpenIddict Token Exchange
    └── Commands/       # Password Grant og Refresh Token Grant

```

---

## 3. Oversikt over Behandlere (Handlers)

### Brukeroperasjoner (`Account`)

Modulen dekker alle handlinger en sluttbruker kan utføre på sin egen konto:

* **Commands:**
* `RegisterUserCommand`: Registrerer ny bruker med passordvalidering, sjekk mot svarteliste og publisering av `UserRegisteredEvent`.
* `ConfirmEmailCommand`: Verifiserer e-postadresse ved hjelp av kryptografisk token.
* `ChangePasswordCommand`: Bytter passord for en innlogget bruker.
* `RecoverPasswordCommand`: Genererer tilbakestillingstoken og utløser e-postutsendelse om passordgjenoppretting.
* `ResetPasswordCommand`: Fullfører passordtilbakestilling med gyldig token.
* `SetPasswordCommand`: Setter passord for brukere som opprinnelig kun registrerte seg via Google OAuth.
* `UpdateProfileCommand`: Oppdaterer personopplysninger (navn) på profil.
* `CompleteWelcomeCommand`: Markerer at velkomstveilederen er gjennomført i frontend.
* `ResendConfirmationCommand`: Re-genererer og sender ny e-postbekreftelse på forespørsel.
* `DeleteAccountCommand`: Brukerinitiert sletting av egen konto (utløser kaskadesletting i økosystemet).
* `ProcessGoogleCallbackCommand`: Behandler callback fra Google OAuth2, oppretter/knytter brukerkonto, og utsteder OpenIddict-tokens.
* `RemoveBlacklistEntryCommand`: Fjerner en svartelisteoppføring hvis vilkår er oppfylt.


* **Queries:**
* `GetUserProfileQuery`: Henter profil- og kontodetaljer for den innloggede brukeren.



---

### Administratoroperasjoner (`Admin`)

Modulen benyttes av plattformadministratorer for å håndtere utestengelser, sikkerhetsinngrep og overvåking:

* **Commands:**
* `AddBlacklistEntryCommand`: Manuelt legge til en e-postadresse eller et helhetlig domene i `BlacklistedEntries`.
* `LockUserCommand`: Midlertidig eller permanent sperre en brukerkonto med spesifisert årsak (`LockoutReason`).
* `UnlockUserCommand`: Oppheve sperre på en brukerkonto.
* `DeleteUserAdminCommand`: Administrativ sletting av en brukerkonto.
* `DeleteAndBlacklistUserCommand`: Kombinert handling som sletter brukeren, inndrar alle tokens og automatisk svartelister e-postadressen.
* `ManuallyConfirmEmailCommand`: Overstyre og manuelt bekrefte e-postadressen til en bruker.
* `AdminResendConfirmationCommand`: Administrativ re-utsending av e-postbekreftelse.
* `AdminSendPasswordResetCommand`: Administrativ utsending av passordtilbakestillingslenke.
* `SendUserEmailAdminCommand`: Sende tilpasset direktemelding/e-post til en enkeltbruker.
* `AdminUpdateUserCommand`: Oppdatere brukerinformasjon, e-post eller roller på vegne av brukeren.


* **Queries:**
* `GetUsersQuery`: Hente paginert liste over brukere i systemet med filtrering og søk.
* `GetUserDetailsQuery`: Hente fullstendige administrative detaljer for en spesifikk bruker (inkludert innloggingshistorikk, sperrestatus og roller).
* `GetBlacklistEntryQuery`: Slå opp og hente oppføringer fra svartelisten.



---

### Autorisasjon og Tokenutstedelse (`Authorization`)

Modulen kobler OpenIddict sine protokollkall direkte mot Identity-systemet:

* **Commands:**
* `PasswordGrantCommand`: Validerer legitimasjon (e-post/passord), sjekker om kontoen er sperret eller deaktivert, oppdaterer `LastLoginAt`, og bygger `ClaimsPrincipal` for tokens.
* `RefreshTokenGrantCommand`: Validerer eksisterende refresh token, bekrefter at brukeren fortsatt er aktiv/ikke-sperret i databasen, og re-oppretter en oppdatert `ClaimsPrincipal` for fornyelse.



---

## 4. Typisk Eksekveringsflyt i en Behandler

Mønsteret for en skriveoperasjon følger en fast, forutsigbar livssyklus:

```
[REST Controller]
       │
       ▼  (mediator.Send)
[Command Handler]
       │
       ├── 1. Domene- & Svartelistekontroll (Sjekk mot BlacklistedEntries / UserManager)
       │
       ├── 2. Identity-operasjon (Tilstandsendring i ApplicationDbContext)
       │
       ├── 3. Event Publishing (Asynkron publisering til RabbitMQ via IPublishEndpoint)
       │
       └── 4. Returner Resultat-objekt (Success/Failure med eventuell feilmelding)

```

Ved å holde denne strukturen konsistent på tvers av alle 28 behandlere i `recipe-auth-api`, oppnås en arkitektur som er enkel å fange opp i enhetstester, lett å utvide, og godt beskyttet mot utilsiktede bivirkninger.