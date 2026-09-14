# 🧪 Teststrategi

> Dette dokumentet er verifisert mot en full gjennomgang av testsuiten (103 tester, alle grønne). De to
> hullene som tidligere sto beskrevet her - manglende fail-fast-test på de fleste prosessorer, og manglende
> direkte consumer-tester for de tynne event-consumerne - er nå tettet (se punkt 1 og 4 under).

## Formål

Testene i denne tjenesten skal garantere at:

1. **Prosessorene** behandler innkommende hendelser korrekt (riktig stibane/modell mot
   `ITemplateRenderService`, riktig mottaker/emne/event-type mot `IPendingEmailService`).
2. **Resiliens- og feilhåndteringslogikken** (`PendingEmailService`, `NotificationStateStore`) håndterer
   in-line retries, hard bounce, avduplisert admin-varsling og MongoDB-buffering korrekt - inkludert at et
   bufret dokument aldri slettes automatisk ved et mislykket re-forsøk (se
   [04-error-handling-and-resilience.md](04-error-handling-and-resilience.md)).
3. **Scriban-malene** (inkludert den delte `_Layout.html`) kompilerer og rendrer fra disk uten feil.
4. **MassTransit-consumers** fanger opp hendelser fra bussen og utfører riktige operasjoner.

## Verktøykasse

* **xUnit** - testrammeverk (`[Fact]`, `[Theory]`).
* **NSubstitute** - mocking av grensesnitt (`IPendingEmailService`, `ITemplateRenderService`,
  `IFailedNotificationRepository`, `IEventProcessor<TEvent>`, osv.).
* **Shouldly** - lesbare assertions (`result.ShouldBeTrue()`).
* **MassTransit.TestHarness** - verifiserer consumers uten en reell RabbitMQ-instans.

## Prosjektstruktur for testene

Speiler `Infrastructure`, `Persistence` og `Service`:

```text
Tests/
├── Processors/{AdminActions,SystemActions,UserActions}/   - én testklasse per prosessor
├── Infrastructure/
│   ├── PendingEmailServiceTests.cs
│   └── NotificationStateStoreTests.cs
├── TemplateService/
│   └── TemplateRenderServiceTests.cs
└── Consumers/
    ├── AdminActions/     - én testklasse per event-consumer (7 stk)
    ├── SystemActions/    - én testklasse per event-consumer (5 stk)
    ├── UserActions/      - én testklasse per event-consumer (7 stk)
    └── NotificationManagement/
        ├── GetFailedNotificationsConsumerTests.cs
        ├── RetryFailedNotificationCommandConsumerTests.cs
        └── DeleteFailedNotificationCommandConsumerTests.cs
```

Hver av de 19 event-consumerne har nå sin egen `MassTransit.TestHarness`-test som verifiserer at
`Consume(...)` faktisk kalles og delegerer til riktig `IEventProcessor<TEvent>` med riktig
`CancellationToken` - dette dekker DI-oppsettet og selve `IConsumer<T>`-implementasjonen, ikke bare
prosessorlogikken bak den.

## De fire testpilarene

### 1. Processors - enhetstester

Isoleres ved å mocke `ITemplateRenderService` og `IPendingEmailService`. Verifiserer:

* At `RenderTemplateAsync` kalles med **eksakt riktig stibane** (f.eks. `"UserActions/UserRegisteredWelcome"`)
  og korrekt utfylte modell-variabler.
* At `ProcessEmailWithRetryAsync` kalles med riktig mottaker, emne, HTML-body og `nameof(EventType)`.
* At `TemplateRenderException` forplanter seg ufanget (fail-fast) - dekket for **alle 19** prosessorer.

Prosessorene testes som **konkrete klasser**, ikke via `IEventProcessor<TEvent>` - det delte grensesnittet
brukes ikke til mocking her, kun til DI og til consumer-testene (pilar 4).

### 2. Infrastruktur og resiliens - enhetstester

* **`NotificationStateStoreTests`** - trådsikker oppdatering av `HasPendingNotifications`/`HasNotifiedAdmin`,
  og at `Reset()`/`SetPendingStatus(false)` nullstiller `HasNotifiedAdmin`.
* **`PendingEmailServiceTests`** dekker blant annet:
  * Suksess på 1. eller senere forsøk - ingen MongoDB-skriving.
  * Hard bounce - stopper etter første forsøk, publiserer `InvalidEmailDetectedEvent`.
  * Alle 5 forsøk feiler - lagrer i MongoDB (`RetryCount = 5`) og sender avduplisert admin-varsel via
    Scriban-malen `AdminActions/PendingEmailAlert`, til den konfigurerte `AdminNotificationEmail`.
  * At mottaker/emne/feilmelding HTML-encodes før de sendes til admin-malen.
  * Retry av et **eksisterende** dokument (`existingNotificationId` satt): slettes kun ved suksess,
    oppdateres in-place (`MarkRetryFailedAsync`) - aldri slettet eller duplisert - ved fornyet feil eller
    hard bounce.

### 3. TemplateRenderService og HTML-maler - integrasjonstester

* At alle `.html`-filer under `Templates/` (inkludert de som bruker `{{ include "_Layout" }}`) kompilerer
  og rendrer uten feil via den ekte Scriban-motoren og filsystemet.
* At variabler som `{{ name }}`, `{{ confirmation_link }}` erstattes korrekt.
* At `_Layout.html` faktisk inkluderes (f.eks. ved å sjekke at `<!DOCTYPE html>` og standard-footeren
  dukker opp i output for en mal som ikke setter `footer_note`), og at `footer_note`-override fungerer for
  malene som bruker det.
* At manglende maler eller syntaksfeil kaster `TemplateRenderException`.

### 4. Consumers - komponenttester

Bruk av `MassTransit.TestHarness`:

* At publisering av et event aktiverer riktig consumer, som videresender til riktig prosessor (mocket via
  `IEventProcessor<TEvent>`) med riktig `CancellationToken` - dekket for **alle 19** event-consumers.
* **Management-consumers:** `GetFailedNotificationsConsumer` svarer med korrekt DTO-liste;
  `RetryFailedNotificationCommandConsumer` nullstiller retry-teller og delegerer retry+sletting til
  `PendingEmailService` (uten selv å slette dokumentet direkte - se
  [04-error-handling-and-resilience.md](04-error-handling-and-resilience.md));
  `DeleteFailedNotificationCommandConsumer` sletter valgte dokumenter og nullstiller
  `NotificationStateStore` ved 0 gjenværende.

## Eksempel: Processor-enhetstest

```csharp
using Contracts.Events.UserActions;
using Infrastructure.EmailDelivery.Interfaces;
using Infrastructure.Options;
using Infrastructure.Processors.UserActions;
using Infrastructure.TemplateService.Interfaces;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using NSubstitute;
using Shouldly;
using Xunit;

namespace Tests.Processors.UserActions;

public class UserRegisteredProcessorTests
{
    private readonly ITemplateRenderService _templateRenderService = Substitute.For<ITemplateRenderService>();
    private readonly IPendingEmailService _pendingEmailService = Substitute.For<IPendingEmailService>();
    private readonly IOptions<AppSettings> _appSettings = Options.Create(new AppSettings { FrontendUrl = "https://kjokkenhylla.no" });
    private readonly ILogger<UserRegisteredProcessor> _logger = Substitute.For<ILogger<UserRegisteredProcessor>>();

    private readonly UserRegisteredProcessor _processor;

    public UserRegisteredProcessorTests()
    {
        _processor = new UserRegisteredProcessor(_templateRenderService, _pendingEmailService, _appSettings, _logger);
    }

    [Fact]
    public async Task ProcessAsync_WhenValidEvent_ShouldRenderTemplateAndProcessWithRetry()
    {
        const string expectedHtml = "<html>Velkommen</html>";
        _templateRenderService
            .RenderTemplateAsync(Arg.Any<string>(), Arg.Any<object>())
            .Returns(Task.FromResult(expectedHtml));

        var @event = new UserRegisteredEvent
        {
            UserId = Guid.NewGuid(),
            Email = "ola@example.com",
            Name = "Ola Nordmann",
            ConfirmationLink = "https://kjokkenhylla.no/confirm?token=123"
        };

        await _processor.ProcessAsync(@event, CancellationToken.None);

        await _templateRenderService.Received(1)
            .RenderTemplateAsync("UserActions/UserRegisteredWelcome", Arg.Is<object>(x => x != null));

        await _pendingEmailService.Received(1)
            .ProcessEmailWithRetryAsync(
                "ola@example.com",
                "Velkommen til Kjøkkenhylla! Bekreft din e-postadresse",
                expectedHtml,
                nameof(UserRegisteredEvent),
                Arg.Any<CancellationToken>());
    }
}
```

## Gjennomføringsplan for nye testområder

1. Verifiser at `Tests.csproj` har prosjektreferanser til `Infrastructure`, `Persistence`, `Contracts` og
   `Service`, samt at NuGet-pakkene (`NSubstitute`, `Shouldly`, `MassTransit.TestHarness`) er installert.
2. **Pilar 1 (Processors):** enhetstester for alle prosessorer under `UserActions`, `AdminActions` og
   `SystemActions`.
3. **Pilar 2 (Infrastruktur):** `PendingEmailService` (retry, hard bounce, MongoDB-lagring/oppdatering) og
   `NotificationStateStore`.
4. **Pilar 3 (Templates):** integrasjonstester som kjører gjennom alle Scriban-malene, inkludert layout-
   inkludering.
5. **Pilar 4 (Consumers):** `MassTransit.TestHarness`-tester for event-forbrukere og admin-kommandoer.
