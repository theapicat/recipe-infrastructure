# 📋 Sjekkliste: Legge til ny e-postnotifikasjon

Hurtigguide for utvidelse av e-postutsendelser i **Recipe Notification Service**.

---

### 🔲 1. Kontrakt (`Contracts/`)

* [ ] Opprett event-klasse under `Contracts/Events/{DomainActions}/{EventName}.cs`.
* [ ] Inkluder kun nødvendige felt (`UserId`, `Email`, `Name`, unike lenker, datoer).

### 🔲 2. Publisering (Kildetjeneste)

* [ ] Injiser `IPublishEndpoint` i utløsende tjeneste (f.eks. Quartz Job/Controller i `recipe-auth-api`).
* [ ] Publiser eventet på meldingsbussen ved utløst handling.

### 🔲 3. HTML-mal (`Infrastructure/TemplateService/Templates/`)

* [ ] Opprett Scriban-mal under `Templates/{DomainActions}/{TemplateName}.html`.
* [ ] Følg designsystemet:
* Header-banner: `#2a3e30` med kokkelue-logo.
* Primærknapp: `#4a6b53`, sentrert (`align="center"`, `margin: 24px auto`).
* Varselboks (v/ tidsfrister): `#f9ebe6` bakgrunn, `#c86a4b` ramme.


* [ ] Verifiser at `.csproj` har `Copy to Output Directory: Copy if newer`.

### 🔲 4. Prosessor (`Infrastructure/Processors/`)

* [ ] Opprett grensesnitt i `Interfaces/{DomainActions}/I{EventName}Processor.cs`.
* [ ] Opprett prosessorklasse i `{DomainActions}/{EventName}Processor.cs`.
* [ ] Bygg anonym modell for Scriban-variablene.
* [ ] Rendre mal med `ITemplateRenderService.RenderTemplateAsync("{DomainActions}/{TemplateName}", model)`.
* [ ] Send via `IPendingEmailService.ProcessEmailWithRetryAsync(...)` med `nameof(EventName)`.

### 🔲 5. Consumer (`Service/Consumers/`)

* [ ] Opprett MassTransit Consumer i `Consumers/{DomainActions}/{EventName}Consumer.cs`.
* [ ] Implementer `IConsumer<TEvent>` og kalle tilhørende prosessor i `Consume`.

### 🔲 6. Registrering i DI (`Service/Extensions/`)

* [ ] Registrer prosessoren som **`Transient`** under sin domeneseksjon i `MailProcessorExtensions.cs`.
* [ ] Registrer consumer under sin domeneseksjon i `MassTransitExtensions.cs` (`x.AddConsumer<...>()`).

### 🔲 7. Testing (`Tests/`)

* [ ] **Processor Unit Test:** Verifiser at `ITemplateRenderService` kalles med korrekt stibane/modell, og at `IPendingEmailService` kalles med riktige parametere.
* [ ] **Template Integration Test:** Verifiser at Scriban-motoren kompilerer den nye `.html`-filen fra disk uten feil.
* [ ] **Consumer Component Test:** Verifiser at `TestHarness` fanger opp eventet og utløser prosessoren.