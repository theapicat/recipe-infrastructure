# Hendelser og meldingsutveksling i `recipe-core-api`

---

Per 2026-09-19. Sjekk mot faktisk kode ved tvil.

## 1. Oppsett

MassTransit + RabbitMQ brukes til asynkron kommunikasjon med søstertjenester
(`recipe-scraper-service`, `recipe-notification-service`) — aldri direkte HTTP mellom tjenestene.

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
RabbitMQ-instans som `recipe-scraper-service` og `recipe-notification-service` kobler seg til. Ingen
egen sync-tabell er skrevet ennå siden kun én kontrakt er i bruk (se §3) — utvid denne seksjonen når flere
meldingstyper krysser tjenestegrenser.

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

### `Contracts.Event.ContactFormSubmittedEvent`

Publisert fra `SendContactFormCommandHandler` (se [`03-cqrs-and-mediatr.md`](03-cqrs-and-mediatr.md)) når
noen sender inn kontaktskjemaet. Konsumeres av `recipe-notification-service` (utløser e-postutsendelse) —
ingen konsument finnes i dette repoet.

```csharp
namespace Contracts.Event;

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

**⚠️ Planlagt — ikke bygget:** ingen `IConsumer<T>`-klasser finnes i dette repoet ennå. Når den første
konsumenten bygges (f.eks. for at scraper-tjenesten skal spørre core-api om en ingrediens finnes i
katalogen), er den naturlige plasseringen `Application/Messaging/Consumers/`, siden `Application` etter
sammenslåingen med `Infrastructure` (se [`01-architecture-and-setup.md`](01-architecture-and-setup.md))
har direkte tilgang til `IMediator` uten noen ekstra prosjektreferanse-omvei.

Merk forskjellen på mønster: `ContactFormSubmittedEvent` er fire-and-forget (`Publish`). En fremtidig
"finnes denne ingrediensen"-forespørsel fra scraper-tjenesten er trolig **request/response**
(`IRequestClient`/`ConsumeContext.RespondAsync`), ikke samme mønster — ikke besluttet i detalj ennå.

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
