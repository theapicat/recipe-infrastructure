# 🧪 Teststrategi for Recipe Notification Service

Dette dokumentet beskriver teststrategien, verktøykassen og mønstrene for enhetstesting og integrasjonstesting av **Recipe Notification Service**.

---

## 🎯 Formål med Testing

Hovedmålet med testene i denne tjenesten er å garantere at:
1. **Forretningslogikken i prosessorene** behandler innkommende hendelser korrekt (riktige variabler, korrekt emnefelt og riktige mottakere).
2. **Scriban HTML-malene** lar seg rendre uten syntaksfeil eller manglende variabler.
3. **MassTransit Consumers** fanger opp hendelser fra meldingsbussen og videresender dem til sine respektive prosessorer.
4. **Feilhåndteringen** fungerer som forventet uten uønskede bivirkninger eller tap av meldinger.

---

## 🧰 Verktøykasse & Biblioteker

Testprosjektet opprettes som et eget .NET 10 xUnit-prosjekt (`Service.Tests`) med følgende biblioteker:

* **`xUnit`**: Testrammeverk og testkjører (`[Fact]` for enkle tester, `[Theory]` for datadrevne tester).
* **`NSubstitute`**: Mocking-rammeverk for å lage isolerte og kontrollerte tester av grensesnitt (`IEmailDeliveryService`, `ITemplateRenderService`, osv.).
* **`FluentAssertions`**: Gir et intuitivt, lesbart språk for testbevis (f.eks. `result.Should().BeTrue()`).
* **`MassTransit.TestHarness`**: Innebygd testmiljø for å verifisere meldingsforbruk og konsumenter uten å mønstre opp en reell RabbitMQ-instans.

---

## 🏗️ Prosjektstruktur for Testene

Testprosjektet placeres i rotmappen og speiler strukturen i `Infrastructure` og `Service` for enkel navigasjon:

```text
recipe-notification-service/
├── Documentation/
│   ├── design-system.md
│   └── notification-test-strategy.md
├── Service.Tests/
│   ├── Service.Tests.csproj
│   ├── Processors/
│   │   ├── AdminActions/
│   │   │   └── UserLockedByAdminProcessorTests.cs
│   │   ├── SystemActions/
│   │   │   └── Confirmation7DaysReminderProcessorTests.cs
│   │   └── UserActions/
│   │       ├── ContactFormProcessorTests.cs
│   │       └── UserRegisteredProcessorTests.cs
│   ├── TemplateService/
│   │   └── TemplateRenderServiceTests.cs
│   └── Consumers/
│       └── UserActions/
│           └── ContactFormSubmittedConsumerTests.cs

```

---

## 🏛️ De 3 Testpilarene

Testing av applikasjonen er delt inn i tre lag basert på ansvarsområde:

### 1. Pilar A: Processors (Forretningslogikk) — *Enhetstester*

Prosessorene utgjør hjertet av forretningslogikken. De isoleres fullstendig ved å mocke alle avhengigheter.

* **Hva testes:**
* At uthenting av data fra event-kontraktene er korrekt.
* At `ITemplateRenderService` kalles med **eksakt riktig malnavn** og **riktige variabler**.
* At `IEmailDeliveryService` kalles med **riktig mottaker-e-post** og **raskt/korrekt emnefelt**.
* At avvik og uventede feil kastes videre slik at MassTransit kan overta retries / DLQ-håndtering.


* **Avhengigheter som mockes (`NSubstitute`):**
* `IEmailDeliveryService`
* `ITemplateRenderService`
* `ILogger<T>`



---

### 2. Pilar B: TemplateRenderService & HTML-maler — *Integrasjonstester*

For å sikre at Scriban-motoren og HTML-malene faktisk fungerer sammen på filsystemet uten krasj.

* **Hva testes:**
* At `TemplateRenderService` klarer å lese alle `.html`-filer fra `Templates/`-mappen.
* At variabler som `{{ name }}`, `{{ confirmation_link }}`, `{{ reason }}` erstattes korrekt med reelle verdier i den genererte HTML-strengen.
* At renderingen feiler grasiøst dersom nødvendige maler eller variabler mangler.



---

### 3. Pilar C: Consumers (MassTransit-integrasjon) — *Komponenttester*

Sikrer at MassTransit fanger opp hendelser og sender dem videre til riktig prosessor.

* **Hva testes:**
* At publisering av et event på den virtuelle bussen (`ITestHarness`) aktiverer riktig Consumer.
* At Consumer kaller sin tilhørende Processor.
* At feil i prosessoren fører til at meldingen havner i feilkø (DLQ / Fault endpoint) som forventet.



---

## 📋 Eksempel på Testforløp (Arrange-Act-Assert)

En typisk enhetstest for en processor skal følge AAA-mønsteret:

```csharp
[Fact]
public async Task ProcessAsync_WhenValidEvent_ShouldRenderTemplateAndSendEmail()
{
    // Arrange (Klargjør mocks og testdata)
    var templateService = Substitute.For<ITemplateRenderService>();
    var deliveryService = Substitute.For<IEmailDeliveryService>();
    var logger = Substitute.For<ILogger<UserRegisteredProcessor>>();

    templateService.RenderAsync(Arg.Any<string>(), Arg.Any<object>())
                   .Returns(Task.FromResult("<html>Velkommen</html>"));

    var processor = new UserRegisteredProcessor(templateService, deliveryService, logger);
    var @event = new UserRegisteredEvent { Email = "test@example.com", Name = "Ola Nordmann" };

    // Act (Utfør handlingen)
    await processor.ProcessAsync(@event, CancellationToken.None);

    // Assert (Verifiser resultatene med FluentAssertions / NSubstitute)
    await templateService.Received(1)
        .RenderAsync("UserActions/UserRegisteredWelcome", Arg.Is<object>(x => x != null));

    await deliveryService.Received(1)
        .SendEmailAsync("test@example.com", Arg.Any<string>(), "<html>Velkommen</html>", Arg.Any<CancellationToken>());
}

```

---

## 🚀 Gjennomføringsplan for Implementasjon

1. **Opprettelse:** Opprett xUnit-prosjektet `Service.Tests` og installer pakkene (`NSubstitute`, `FluentAssertions`, `Microsoft.NET.Test.Sdk`).
2. **Knytt sammen:** Legg prosjektet til i løsningen (`recipe-notification-service.sln`) og legg til prosjektreferanser til `Infrastructure`, `Contracts` og `Service`.
3. **Fase 1 - Processors:** Skriv tester for alle `UserActions`, `AdminActions` og `SystemActions` prosessorer.
4. **Fase 2 - Templates:** Skriv tester for `TemplateRenderService` som kjører gjennom alle HTML-malene på disken.
5. **Fase 3 - Consumers:** Implementer MassTransit `TestHarness`-tester for event-forbrukerne.