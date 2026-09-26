# Autentisering og autorisering i `recipe-core-api`

---

Per 2026-09-20. Sjekk mot faktisk kode ved tvil.

## 1. Prinsipp

Core API validerer JWT-en selv (`Microsoft.AspNetCore.Authentication.JwtBearer`), på samme måte som
gatewayen og `recipe-auth-api` gjør hver for seg. Gatewayen videresender `Authorization`-headeren uendret.

**Core API stoler aldri på `X-User-Id`/`X-User-Roles`-headere** — tjenesten er direkte nåbar på
`localhost:5002` utenom gatewayen i dev, så slike headere kan forfalskes. Identitet og roller leses kun
fra validerte JWT-claims.

Implementasjon: `API/Extensions/JwtAuthenticationExtensions.cs` (`AddJwtAuthentication`), kalt fra
`Program.cs` sammen med `AddAuthorization()`. Middleware-rekkefølge:

```
UseRouting() → UseAuthentication() → UseAuthorization() → MapControllers() / MapRealtimeHubs()
```

---

## 2. Konfigurasjon som må holdes i sync

| Core API (`appsettings`) | Gateway | Auth API | Dev-verdi |
| --- | --- | --- | --- |
| `Jwt:Key` | `Jwt:Key` | `JWT:SecretKey` | Samme som i gatewayens og Auth API sin dev-config — **ikke skrevet her**. |
| `Jwt:Issuer` | `Jwt:Issuer` | `JWT:Issuer` | `http://recipe-auth-app/` |
| `Jwt:Audience` | `Jwt:Audience` | `JWT:Audience` | `recipe-frontend` |

`AddJwtAuthentication` kaster `InvalidOperationException` ved oppstart hvis noen av de tre mangler.

Issuer må være skrevet **bokstavelig likt** i alle tre (en absolutt URI med avsluttende `/`). Auth API setter den fast med OpenIddict `SetIssuer`; uten det ville `iss` i tokenet blitt forespørselens URL (`http://localhost:5000/`), og både gatewayen og Core ville avvist tokenet med `401 The issuer … is invalid`.

`Jwt:Key` i `API/appsettings.Development.json` er satt til den delte dev-nøkkelen (identisk med gatewayen og Auth API,
fylt inn 2026-09-19). Ingen ekte nøkkel skal noensinne stå i `appsettings.json`; i Docker/produksjon settes den via
miljøvariabel (`Jwt__Key`).

---

## 3. Tilgangsnivåer og ruter

Se [`02-endpoints-and-controllers.md`](02-endpoints-and-controllers.md) for full endepunktstabell. Kort
oppsummert:

| Basiskontroller | Rute | Attributt | Gateway-policy foran |
| --- | --- | --- | --- |
| `PublicController` | `/api/public` | `[AllowAnonymous]` | ingen |
| `UserController` | `/api/user` | `[Authorize]` | `AuthenticatedUser` |
| `AdminController` | `/api/admin` | `[Authorize(Roles = "admin")]` | `AdminUser` |
| `RecipeHub` (SignalR) | `/hubs/...` | `[Authorize]` | `AuthenticatedUser` |

Rollenavn er **alltid små bokstaver** (`admin`, `user`) — case-sensitivt. Gatewayen er første
forsvarslinje, ikke den eneste; Core API håndhever `[Authorize]` selv uansett.

Gatewayens `AdminUser`-policy sjekker `RequireRole("admin")` (små bokstaver), lik rollen Auth API utsteder og
`[Authorize(Roles = "admin")]` i Core. (Rettet 2026-09-20: policyen sto tidligere som `"Admin"` og ga `403` for gyldige
admin-token via gatewayen.) Er noe av dette med stor bokstav noe sted, er det en feil.

---

## 4. Å hente innlogget bruker

- **Bruker-ID:** `User.FindFirstValue(ClaimTypes.NameIdentifier)` → `Guid.Parse`. **Ikke** `FindFirst("sub")`
  — standard `JwtBearer` omdøper `sub` til `ClaimTypes.NameIdentifier`.
- **Roller:** `[Authorize(Roles = "admin")]` eller `User.IsInRole("admin")`.
- Uthentingen skal skje ett sted i API-laget (en `ClaimsPrincipal`-extension), og bruker-ID sendes inn i
  MediatR-commands/-queries som eksplisitt parameter. **`Application` skal aldri kjenne til `HttpContext`
  eller `ClaimsPrincipal`** — dette er en hard grense, ikke en anbefaling.
- **Eierskap:** bruker-ID kommer alltid fra tokenet, aldri fra request-body/query/rute. Ingen
  `/api/user`-endepunkt skal ta imot en `userId`-parameter som påstår hvem eieren er.

**Bygget (2026-09-20):** `API/Extensions/ClaimsPrincipalExtensions.GetUserId()` er det eneste stedet bruker-id hentes fra
tokenet (`ClaimTypes.NameIdentifier`; `"sub"` gir bevisst ikke treff). Den brukes av
`UserUnconfirmedIngredientController`, som sender id-en inn i hver kommando som eksplisitt `UserId` — request-body har
ingen bruker-id-felt. Enhetstester låser regelen: `Tests/API/Extensions/ClaimsPrincipalExtensionsTests` og
`Tests/API/Controllers/UnconfirmedIngredientControllerTests` (id kommer fra tokenet, ikke fra body).

**Bygget (2026-09-20):** oppskrifter (`Recipe.OwnerUserId`) følger samme mønster: `UserRecipeController` sender `User.GetUserId()` inn i hver kommando/spørring, alle
SQL-funksjoner filtrerer på eier (også barnetabellene), og en annen brukers oppskrift gir samme `404` som en id som ikke finnes — verifisert mot ekte Postgres
(liste tom, detalj/endre/slett/favoritt/næring gir `404`, og en annen brukers ubekreftede ingrediens kan ikke brukes i en oppskrift). Admin har ingen tilgang til andres oppskrifter.

---

## 5. Andre brukeres data og åpne spørsmål

**Avgjort (2026-09-19):** En annen brukers data *eksisterer ikke* for den innloggede brukeren. Alle
brukerspesifikke spørringer (`/api/user/**`) filtrerer på eier hentet fra tokenet (aldri fra body eller
URL), og treffer de ikke noe, er resultatet «ikke funnet»: en tom liste. Det gir hverken `403` eller en
`404` som avslører at ressursen finnes. Dette er standard for all brukerspesifikk funksjonalitet.

**Implementert for ubekreftede ingredienser (2026-09-20):** oppslag, endring og sletting av *én* ressurs på id som
tilhører en annen bruker gir nøyaktig samme `404` (med samme lille `ProblemDetails`-kropp, uten `detail`) som en id som ikke finnes — handleren sjekker
`CreatedByUserId` mot tokenets bruker, og databasefunksjonene har i tillegg eier i `WHERE`. Verifisert mot ekte
Postgres. Foreslått som standard også for oppskrifter; endelig avgjørelse tas når de bygges.

---

## 6. Kjente begrensninger (bevisste, ikke glemt)

- Access-token er en frittstående JWT — Core API slår ikke opp brukeren i noen database per kall. En
  sperret eller slettet bruker kan bruke et allerede utstedt access-token til det utløper (opptil 60
  minutter). Akseptert eksponeringsvindu, samme som i Auth API sin dokumentasjon.
- Kontosletting i Auth API publiserer en hendelse Core API må konsumere for å kaskadeslette brukerens
  data. Ikke en del av autentiseringen i seg selv, men relevant den dagen `OwnerUserId`-data finnes.

---

Sjekk mot faktisk kode ved tvil.
