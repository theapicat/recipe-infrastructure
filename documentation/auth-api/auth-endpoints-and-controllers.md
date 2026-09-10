# Endepunkter og Kontrollere i `recipe-auth-api`

---

## 1. Oversikt og Ruting-arkitektur

All innkommende trafikk til `recipe-auth-api` rutes gjennom **API Gateway**. Gatewayen prefikserer alle forespørsler til autentiseringstjenesten med stien `/api/auth/*` før de videresendes til de respektive kontrollerne.

### Kontrollernes Ansvar

Kontrollerne i `recipe-auth-api` følger prinsippet om **tynne kontrollere** (Thin Controllers). De inneholder ingen forretningslogikk, men utfører følgende oppgaver:

* Ekstraherer argumenter, DTO-er og kontekst (f.eks. gjeldende bruker-ID fra JWT/OpenIddict claims eller IP-adresse).
* Instansierer og sender MediatR Commands og Queries til applikasjonslaget.
* Mapper resultatobjekter (`IsSuccess`, `Errors`, `IsForbidden`, `IsNotFound`) til standardiserte HTTP-statuskoder (200 OK, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found).

---

## 2. Sluttbrukerselvbetjening (`AccountController`)

**Rute-prefiks:** `/api/auth/account`

**Formål:** Håndtere sluttbrukeres registrering, profiladministrasjon, passordhåndtering, e-postbekreftelse og kontosletting.

### Endepunktsoversikt

| Metode | Endepunkt | Tilgang | Formål / Beskrivelse |
| --- | --- | --- | --- |
| `POST` | `/register` | Anonym | Registrerer ny brukerkonto (`RegisterRequest`). Sjekker e-post mot svartelisten og sender bekreftelses-e-post. |
| `GET` | `/me` | Autentisert | Henter profil- og kontodetaljer for innlogget bruker. |
| `PUT` | `/profile` | Autentisert | Oppdaterer personalia (`FirstName`, `LastName`). |
| `POST` | `/change-password` | Autentisert | Endrer passord for brukere med eksisterende lokal legitimasjon. |
| `POST` | `/set-password` | Autentisert | Oppretter et lokalt passord for brukere som opprinnelig registrerte seg via Google OAuth. |
| `GET` | `/complete-welcome` | Autentisert | Markerer at brukeren har gjennomført velkomstveilederen i frontend. |
| `POST` | `/resend-confirmation` | Autentisert | Re-genererer og sender ny bekreftelseslenke til brukerens e-postadresse. |
| `POST` | `/confirm-email` | Anonym | Bekrefter e-postadresse ved bruk av kryptografisk token sendt på e-post (`ConfirmEmailRequest`). |
| `POST` | `/recover` | Anonym | Initiere passordgjenoppretting ved tapt passord. Genererer token og sender e-post. |
| `POST` | `/reset-password` | Anonym | Tilbakestiller passord ved å oppgi gyldig token fra e-post (`ResetPasswordRequest`). |
| `DELETE` | `/me` | Autentisert | Brukerinitiert permanent sletting av egen konto (utløser kaskadesletting i andre mikrotjenester). |
| `GET` | `/external-login` | Anonym | Initiere ekstern OAuth2-utfordring mot Google (`provider=Google`). |
| `GET` | `/external-login-callback` | Anonym | Callback-mottaker fra Google OAuth2 som prosesserer token og omdirigerer til frontend. |

---

## 3. Administrative Operasjoner (`AdminController`)

**Rute-prefiks:** `/api/auth/admin`

**Autorisasjon:** Krever at brukeren er autentisert via OpenIddict og har rollen `Admin` (`Roles = "Admin"`).

**Formål:** Overvåking av brukermasse, manuell overstyring, tilgangssperring, administrative slettinger og styring av e-postsvartelisten.

### Endepunktsoversikt

| Metode | Endepunkt | Formål / Beskrivelse |
| --- | --- | --- |
| `GET` | `/users` | Henter paginert liste over registrerte brukere i systemet. |
| `GET` | `/users/{id:guid}` | Henter detaljert administrativ oversikt for en spesifikk bruker (innlogging, roller, sperrestatus). |
| `PUT` | `/users` | Redigerer brukerens personalia og e-postadresse på vegne av brukeren (`AdminUpdateUserRequest`). |
| `POST` | `/users/lock` | Sperrer en brukerkonto manuelt med spesifisert begrunnelse (`LockUserRequest`). |
| `POST` | `/users/unlock` | Fjerner manuell eller automatisk sperre på en brukerkonto (`UnlockUserRequest`). |
| `POST` | `/users/confirm-email` | Manuelt overstyrer og bekrefter e-postadressen til en bruker uden e-posttoken. |
| `POST` | `/users/resend-confirmation` | Trigger utsending av bekreftelses-e-post på vegne av bruker. |
| `POST` | `/users/reset-password-request` | Trigger utsending av lenke for passordtilbakestilling på vegne av bruker. |
| `POST` | `/users/delete` | Administrativ permanent sletting av en brukerkonto (`DeleteUserAdminRequest`). |
| `POST` | `/users/delete-and-blacklist` | Kombinert sikkerhetsinngrep: Sletter brukeren permanent, inndrar tokens og fører e-posten i svartelisten. |
| `GET` | `/blacklist` | Henter liste over alle aktuelt svartelistede e-postadresser og domener (`GetBlacklistEntriesQuery`). |
| `POST` | `/blacklist` | Legger direkte til et mønster (eksakt e-post eller domene) i svartelisten (`AddBlacklistRequest`). |
| `DELETE` | `/blacklist/{id:guid}` | Fjerner en spesifikk oppføring fra svartelisten slik at e-posten igjen kan benyttes til registrering. |
| `POST` | `/send-email` | Sender en tilpasset, direkte e-post/melding til en enkeltbruker via Notification Service. |

---

## 4. OAuth2 Token Exchange (`AuthorizationController`)

**Rute-prefiks:** `/api/auth/connect`

**Content-Type:** `application/x-www-form-urlencoded`

**Formål:** Åpen standard OAuth2 / OpenID Connect-utstedelse og fornyelse av tilgangstokens.

### Endepunktsoversikt

| Metode | Endepunkt | Grant Type | Formål / Beskrivelse |
| --- | --- | --- | --- |
| `POST` | `/token` | `password` | Førstegangs innlogging med e-post/brukernavn og passord. Validerer identitet og returnerer JWT Access Token og Refresh Token. |
| `POST` | `/token` | `refresh_token` | Automatisk fornyelse av utløpt tilgangstoken uten at bruker må oppgi passord på nytt. |

---

## 5. System- og Helsesjekk (`HealthController`)

**Rute-prefiks:** `/api/auth/health`

**Tilgang:** `[AllowAnonymous]`

**Formål:** Tilby en lettvektig statusindikator for mikrotjenesten.

### Endepunktsoversikt

| Metode | Endepunkt | Formål / Beskrivelse |
| --- | --- | --- |
| `GET` | `/` | Returnerer HTTP 200 OK med informasjon om applikasjonsnavn, kjøremiljø (Environment) og tidsstempel. |

> **Merk angående helsesjekk:**
> Dagens `/api/auth/health`-endepunkt er en midlertidig løsning primært beregnet på utviklerskripter for å verifisere at containeren/tjenesten svarer under oppstart. En mer omfattende helsesjekk-arkitektur (som inkluderer tilkoblingstester mot PostgreSQL, RabbitMQ og OpenIddict) er planlagt implementert på et senere tidspunkt.