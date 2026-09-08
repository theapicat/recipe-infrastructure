# 🧪 Teststrategi for Recipe Notification Service

Dette dokumentet beskriver teststrategien, verktøykassen og mønstrene for enhetstesting, integrasjonstesting og komponenttesting av **Recipe Notification Service**.

---

## 🎯 Formål med Testing

Hovedmålet med testene i denne tjenesten er å garantere at:

1. **Forretningslogikken i prosessorene** behandler innkommende hendelser korrekt (riktige malvariabler, tittel, mottaker og event-type mot `IPendingEmailService`).
2. **Resiliens- og feilhåndteringslogikken** (`PendingEmailService` og `NotificationStateStore`) håndterer in-line retries (opptil 5 forsøk), hard bounce-deteksjon (`InvalidEmailDetectedEvent`), avduplisert admin-varsling og MongoDB-buffering som forventet.
3. **Scriban HTML-malene** lar seg kompilere og rendre fra disk uten syntaksfeil eller manglende variabler.
4. **MassTransit Consumers & Admin Commands** fanger opp hendelser fra meldingsbussen og utfører riktige CRUD- og re-try-operasjoner mot MongoDB.

---

## 🧰 Verktøykasse & Biblioteker

Testprosjektet er opprettet som et .NET 10 xUnit-prosjekt (`Tests`) med følgende biblioteker:

* **`xUnit`**: Testrammeverk og testkjører (`[Fact]` for enkle tester, `[Theory]` for datadrevne tester).
* **`NSubstitute`**: Mocking-rammeverk for å lage isolerte og kontrollerte tester av grensesnitt (`IPendingEmailService`, `ITemplateRenderService`, `IFailedNotificationRepository`, osv.).
* **`Shouldly`**: Gir et ekspressivt, lesbart språk for testbevis (f.eks. `result.ShouldBeTrue()`).
* **`MassTransit.TestHarness`**: Innebygd testmiljø for å verifisere meldingsforbruk og konsumenter uten å mønstre opp en reell RabbitMQ-instans.

---

## 🏗️ Prosjektstruktur for Testene

Testprosjektet speiler strukturen i `Infrastructure`, `Persistence` og `Service` for enkel navigasjon:

```text
recipe-notification-service/
├── Documentation/
│   ├── notification-contracts.md
│   ├── notification-error-handling.md
│   ├── notification-design-system.md
│   └── notification-test-strategy.md
└── Tests/
    ├── Tests.csproj
    ├── Processors/
    │   ├── AdminActions/
    │   │   └── UserLockedByAdminProcessorTests.cs
    │   ├── SystemActions/
    │   │   └── Confirmation7DaysReminderProcessorTests.cs
    │   └── UserActions/
    │       ├── ContactFormProcessorTests.cs
    │       └── UserRegisteredProcessorTests.cs
    ├── Infrastructure/
    │   ├── PendingEmailServiceTests.cs
    │   └── NotificationStateStoreTests.cs
    ├── TemplateService/
    │   └── TemplateRenderServiceTests.cs
    └── Consumers/
        ├── UserActions/
        │   └── ContactFormSubmittedConsumerTests.cs
        └── NotificationManagement/
            ├── GetFailedNotificationsConsumerTests.cs
            ├── RetryFailedNotificationCommandConsumerTests.cs
            └── DeleteFailedNotificationCommandConsumerTests.cs

```

---

## 🏛️ De 4 Testpilarene

Testing av applikasjonen er delt inn i fire lag basert på ansvarsområde:

### 1. Pilar A: Processors (Forretningslogikk) — *Enhetstester*

Prosessorene utgjør hjertet av domenelogikken. De isoleres ved å mocke `ITemplateRenderService` og `IPendingEmailService`.

* **Hva testes:**
* At `ITemplateRenderService.RenderTemplateAsync` kalles med **eksakt riktig stibanemønster** (f.eks. `"UserActions/UserRegisteredWelcome"`) og korrekt utfylte anonyme modell-variabler (`name`, `confirmation_link`, `terms_link`).
* At `IPendingEmailService.ProcessEmailWithRetryAsync` kalles med riktig mottaker-e-post, emnefelt, generert HTML-body og korresponderende event-type (`nameof(UserRegisteredEvent)`).
* At `TemplateRenderException` sendes ubehandlet videre (Fail-Fast).


* **Avhengigheter som mockes (`NSubstitute`):**
* `ITemplateRenderService`
* `IPendingEmailService`
* `ILogger<T>`



---

### 2. Pilar B: Infrastruktur & Resiliens — *Enhetstester*

Tester kjernetjenestene for feilhåndtering, re-try, tilstandsstyring og buffering.

* **`NotificationStateStoreTests`:**
* Verifiserer trådsikker oppdatering av `HasPendingNotifications` og `HasNotifiedAdmin`.
* Verifiserer at `Reset()` eller `SetPendingStatus(false)` tilbakestiller `HasNotifiedAdmin` til `false`.


* **`PendingEmailServiceTests`:**
* **Suksess på 1. forsøk:** Ingen lagring i MongoDB eller admin-varsel.
* **Transient feil med re-try suksess:** Feiler 2 ganger med `EmailDeliveryException`, men lykkes på 3. forsøk. Verifiserer at meldingen sendes og at ingenting havner i MongoDB.
* **5 mislykkede forsøk (Buffer i MongoDB):** Feiler 5 ganger på rad -> Verifiserer lagring i `IFailedNotificationRepository` med `RetryCount = 5` og utsending av avduplisert admin-varsel.
* **Hard Bounce:** Ved permanent avviste adresser (f.eks. `550 User unknown`) avbrytes vidare gjenforsøk umiddelbart etter **første forsøk**, og `InvalidEmailDetectedEvent` publiseres på MassTransit.
* **Avduplisert admin-varsel:** Sjekker at e-post til admin kun sendes idet `HasNotifiedAdmin` overgår fra `false` til `true`.



---

### 3. Pilar C: TemplateRenderService & HTML-maler — *Integrasjonstester*

Sikrer at Scriban-motoren og HTML-malene på filsystemet fungerer uten krasj.

* **Hva testes:**
* At `TemplateRenderService` klarer å lese og kompilere alle `.html`-filer fra `Templates/`-mappen.
* At variabler som `{{ name }}`, `{{ confirmation_link }}`, `{{ reason }}` erstattes korrekt med reelle verdier i den genererte HTML-strengen.
* At manglende maler eller syntaksfeil kaster `TemplateRenderException`.



---

### 4. Pilar D: Consumers & Admin Management — *Komponenttester*

Bruk av `MassTransit.TestHarness` for å verifisere meldingsbehandling og admin-handlinger.

* **Event Consumers (`UserRegisteredConsumer`, osv.):**
* Publisering av eventer aktiverer riktig Consumer som videresender til tilhørende Processor.


* **Management Consumers:**
* **`GetFailedNotificationsConsumer`:** Svarer med korrekt DTO-liste fra repository-et.
* **`RetryFailedNotificationCommandConsumer`:** Tilbakestiller gjenforsøk, kjører `PendingEmailService` på nytt, sletter fra MongoDB ved suksess og nullstiller `NotificationStateStore` hvis databasen tømmes.
* **`DeleteFailedNotificationCommandConsumer`:** Sletter spesifiserte dokumenter fra MongoDB og tilbakestiller `NotificationStateStore` hvis antall dokumenter når 0.



---

## 📋 Eksempel på Testforløp (Arrange-Act-Assert med Shouldly)

Eksempel på enhetstest for `UserRegisteredProcessor` med `NSubstitute` og `Shouldly`:

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
        _processor = new UserRegisteredProcessor(
            _templateRenderService,
            _pendingEmailService,
            _appSettings,
            _logger);
    }

    [Fact]
    public async Task ProcessAsync_WhenValidEvent_ShouldRenderTemplateAndProcessWithRetry()
    {
        // Arrange
        const string expectedHtml = "<html>Velkommen</html>";
        _templateRenderService
            .RenderTemplateAsync(Arg.Any<string>(), Arg.Any<object>())
            .Returns(Task.FromResult(expectedHtml));

        var @event = new UserRegisteredEvent
        {
            Email = "ola@example.com",
            Name = "Ola Nordmann",
            ConfirmationLink = "https://kjokkenhylla.no/confirm?token=123"
        };

        // Act
        await _processor.ProcessAsync(@event, CancellationToken.None);

        // Assert (NSubstitute verifikasjon)
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

---

## 🚀 Gjennomføringsplan for Implementasjon

1. **Konfigurasjon:** Verifiser at testprosjektet `Tests` har prosjektreferanser til `Infrastructure`, `Persistence`, `Contracts` og `Service`, samt at NuGet-pakkene (`NSubstitute`, `Shouldly`, `MassTransit.TestHarness`) er installert.
2. **Pilar A (Processors):** Implementer enhetstester for alle prosessorer under `UserActions`, `AdminActions` og `SystemActions`.
3. **Pilar B (Infrastruktur):** Skriv enhetstester for `PendingEmailService` (mottaksforsøk, hard bounce, MongoDB-lagring) og `NotificationStateStore`.
4. **Pilar C (Templates):** Implementer integrasjonstester for `TemplateRenderService` som kjører gjennom Scriban HTML-malene på disken.
5. **Pilar D (Consumers):** Implementer MassTransit `TestHarness`-tester for event-forbrukere og admin-kommandoer.