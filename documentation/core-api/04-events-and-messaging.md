# Hendelser og meldingsutveksling i `recipe-core-api`

---

Per 2026-09-23. Sjekk mot faktisk kode ved tvil.

## 1. Oppsett

MassTransit + RabbitMQ brukes til asynkron kommunikasjon med søstertjenester
(`recipe-scraper-service`, `recipe-notification-service`, `recipe-auth-api`) — aldri direkte HTTP mellom
tjenestene.

Registrering: `Application/Extensions/MassTransitExtensions.cs` (`AddMassTransitServices`), kalt fra
`ApplicationExtensions.AddApplicationServices`. Config leses fra `RabbitMQ:*`-seksjonen i appsettings,
med lokale fallback-verdier hvis nøklene mangler:

```json
"RabbitMQ": {
  "Host": "localhost",
  "Port": 5672,
  "VirtualHost": "/",
  "Username": "rabbit_user",
  "Password": "rabbit_secure_password_dev"
}
```

### Konfigurasjon som må holdes i sync

RabbitMQ-tilkoblingsverdiene (`Host`/`Port`/`VirtualHost`/`Username`/`Password`) må stemme med samme
RabbitMQ-instans som `recipe-scraper-service`, `recipe-notification-service` og `recipe-auth-api` kobler
seg til.

### ⚠️ Regel: hver tjeneste MÅ sette et eget `Endpoint`-navn på hver `AddConsumer<T>()`

Bekreftet med en ekte feil 2026-09-23 (se §4): MassTransits standard endepunkt-/kønavngiving bruker kun
forbrukerens **klassenavn uten navnerom** (`AccountDeletedByUserConsumer` → kø `"AccountDeletedByUser"`).
Hvis to tjenester begge har en forbrukerklasse med samme navn for samme hendelse — noe som er naturlig når
man bevisst kopierer navnekonvensjonen fra søstertjenesten, slik denne kontrakten gjorde — havner begge i
**samme kø** og konkurrerer om meldingene (hver hendelse går da til bare én av de to tjenestene, tilfeldig)
i stedet for at hver tjeneste får sin egen kø bundet til samme utveksling (fan-out, det man faktisk vil ha).
Verifisert live mot det delte dev-RabbitMQ-oppsettet: en midlertidig instans av denne tjenesten uten eget
endepunktnavn viste seg som forbruker #2 på `recipe-notification-service` sin ekte `AccountDeletedByUser`-kø.

**Løsning, obligatorisk for enhver ny `AddConsumer<T>()` i dette repoet:**
```csharp
x.AddConsumer<AccountDeletedByUserConsumer>().Endpoint(e => e.Name = "CoreApi-AccountDeletedByUser");
```
Prefiks kønavnet med tjenestenavnet (`CoreApi-...`) slik at det aldri kan kollidere med en annen
tjenestes kø for samme hendelse, uansett hva forbrukerklassen heter der.

---

## 2. Publisering: `IEventPublisher`

Handlers publiserer aldri direkte mot MassTransit sitt `IPublishEndpoint`. I stedet går de via
`Application.Messaging.Interfaces.IEventPublisher`:

```csharp
public interface IEventPublisher
{
    Task PublishAsync<TEvent>(TEvent @event, CancellationToken cancellationToken = default) where TEvent : class;
}
```

Implementasjonen (`Application.Messaging.Implementation.MassTransitEventPublisher`) er en tynn
delegering til `IPublishEndpoint.Publish(...)`. Abstraksjonen finnes for å holde handlers uavhengige av
MassTransit-spesifikke typer, og fordi `Application` opprinnelig hadde en håndrullet `HintPath`-referanse
til MassTransit-dllen i stedet for en ordentlig pakkereferanse — ryddet opp i samtidig som abstraksjonen
ble innført.

---

## 3. Meldingskontrakter (`Contracts` prosjektet)

Kun `Contracts` skal sammenlignes mot andre mikrotjenesters kontrakter — MassTransit ruter meldinger på
fullt kvalifisert namespace, så et avvik mellom to repoer får meldinger til å forsvinne stille.

### `Contracts.Events.UserActions.ContactFormSubmittedEvent`

Publisert fra `SendContactFormCommandHandler` (se [`03-cqrs-and-mediatr.md`](03-cqrs-and-mediatr.md)) når
noen sender inn kontaktskjemaet. Konsumeres av `recipe-notification-service` (utløser e-postutsendelse) —
ingen konsument finnes i dette repoet.

```csharp
namespace Contracts.Events.UserActions;

public record ContactFormSubmittedEvent
{
    public required string Name { get; init; }
    public required string Email { get; init; }
    public required string Subject { get; init; }
    public required string Message { get; init; }
    public DateTime SubmittedAt { get; init; }
}
```

---

## 4. Konsumenter

### Kontosletting (`recipe-auth-api` → `recipe-core-api`, 2026-09-23)

Denne tjenestens **første** innkommende forbruker (før dette var `MassTransitExtensions` kun oppsett for
publisering). `recipe-auth-api` sletter en konto på fire forskjellige måter (bruker sletter selv, admin
sletter, admin sletter + svartelister, eller en Quartz-jobb for 30-dagers ubekreftet e-post/1 års
inaktivitet), og publiserer én hendelse per variant — alle fire har samme kjernefelt
(`UserId`/`Email`/`Name`/`DeletedAt`), pluss ett ekstra felt hver (`DeletionReason` / ingen / `Reason`).

Kontraktene (kopiert byte-for-byte fra `recipe-auth-api/Contracts/Events/`, se §3-regelen om at kun
`Contracts` sammenlignes på tvers av repoer):

| Hendelse | Navnerom | Ekstra felt |
| --- | --- | --- |
| `UserAccountDeletedByUserEvent` | `Contracts.Events.UserActions` | — |
| `UserAccountDeletedBySystemEvent` | `Contracts.Events.SystemActions` | `string DeletionReason` |
| `UserAccountDeletedByAdminEvent` | `Contracts.Events.AdminActions` | — (alle felt `required`) |
| `UserDeletedAndBlacklistedByAdminEvent` | `Contracts.Events.AdminActions` | `string? Reason` |

Alle fire har en tynn `IConsumer<T>` i `Application/Messaging/Consumers/{UserActions,SystemActions,AdminActions}/`
som bare sender `Application.MediatR.Users.DeleteAllUserDataCommand(UserId)` videre via `IMediator` -
selve slettingen (`Persistence.Interfaces.IUserDataEraser`, i én transaksjon: oppskrifter **før** ubekreftede
ingredienser, siden `recipe_ingredient.unconfirmed_ingredient_id` har `ON DELETE RESTRICT`) er delt mellom
alle fire, siden det ikke spiller noen rolle *hvorfor* kontoen ble slettet. Slettingen dekker i dag
oppskrifter og ubekreftede ingredienser - utvides etter hvert som måltidsplan/handleliste/produkter bygges
(se `todo.md`), ikke en liste som byttes ut.

Hver `AddConsumer<T>()` har et eget `Endpoint`-navn (`CoreApi-<HendelseUtenPrefiks>`) — se
**⚠️-regelen i §1**, oppdaget som en ekte kollisjon med `recipe-notification-service` sin forbruker for
akkurat disse fire hendelsene under live-verifisering.

### Fremtidige konsumenter

Merk forskjellen på mønster: `ContactFormSubmittedEvent` og kontoslettings-hendelsene er fire-and-forget
(`Publish`/`Consume`). En fremtidig "finnes denne ingrediensen"-forespørsel fra scraper-tjenesten er trolig
**request/response** (`IRequestClient`/`ConsumeContext.RespondAsync`) i stedet — ikke besluttet i detalj ennå.

---

## 5. SignalR — plassholder

`Application/Realtime/RecipeHub.cs` er en tom `Hub`-klasse merket `[Authorize]`, registrert via
`Application/Extensions/RealtimeExtensions.cs` (`AddRealtimeServices`/`MapRealtimeHubs`, rute
`/hubs/recipe`). Ingen hub-metoder eller push-varsler er lagt til ennå — bygget bevisst som plassholder
for å holde funksjonen synlig i kodebasen, ikke fordi den er i bruk.

Når faktiske hub-metoder bygges: se autentiseringsnotatet i
[`05-authentication-and-authorization.md`](05-authentication-and-authorization.md) for hvordan JWT-token
hentes fra query-strengen for WebSocket-tilkoblinger (nettleseren kan ikke sette
`Authorization`-header på en WebSocket).

---

Sjekk mot faktisk kode ved tvil.
