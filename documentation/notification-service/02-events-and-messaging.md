# 📑 Events, Commands og meldingsmønster

Dette dokumentet beskriver alle kontrakter som utveksles over meldingsbussen (RabbitMQ via MassTransit),
og mønsteret for hvordan en innkommende hendelse behandles fram til en e-post er sendt.

## Navnerom og struktur

* **Events (hendelser):** Passive, fortidskonstruerte navneformer (`UserRegisteredEvent`). Publiseres
  asynkront (`Publish`).
* **Commands (kommandoer):** Imperative navneformer (`DeleteFailedNotificationCommand`). Sendes målrettet
  mot én mottaker (`Send`).
* **Queries (spørringer):** Forespørsler med forventet svar (`GetFailedNotificationsQuery`). Bruker
  MassTransit sitt Request-Response-mønster.

Kontraktene er gruppert etter domene (`UserActions`, `SystemActions`, `AdminActions`,
`NotificationManagement`) i `Contracts/`, og samme domeneinndeling går igjen i `Infrastructure/Processors/`,
`Service/Consumers/` og `Infrastructure/TemplateService/Templates/`.

---

## 👤 UserActions (`Contracts.Events.UserActions`)

Trigges direkte av brukerhandlinger (typisk fra `recipe-auth-api` / kontaktskjema).

| Event | Felter | Beskrivelse |
| --- | --- | --- |
| `UserRegisteredEvent` | `UserId`, `Name`, `Email`, `ConfirmationLink`, `RegisteredAt` | Ny registrering - velkomst- og bekreftelses-e-post. |
| `UserRegisteredWithGoogleEvent` | `UserId`, `Email`, `Name`, `RegisteredAt` | Velkomst til bruker registrert via Google OAuth (ingen bekreftelseslenke). |
| `ResendEmailConfirmationRequestedEvent` | `UserId`, `Email`, `Name`, `ConfirmationLink`, `RequestedAt` | Bruker ber om ny bekreftelseslenke. |
| `PasswordResetRequestedEvent` | `UserId`, `Email`, `Name`, `ResetLink`, `RequestedAt` | Glemt passord - inneholder tilbakestillingslenke. |
| `PasswordChangedEvent` | `UserId`, `Name`, `Email`, `ChangedAt`, `IpAddress`, `DeviceInfo` | Sikkerhetsvarsel om at passordet er endret. |
| `ContactFormSubmittedEvent` | `Name`, `Email`, `Subject`, `Message`, `SubmittedAt` | Genererer to e-poster: varsel til admin/support og kvittering til avsender. |
| `UserAccountDeletedByUserEvent`\* | `UserId`, `Email`, `Name`, `DeletedAt` | Bekreftelse på brukerinitiert kontosletting. |

\* Klassen heter `UserAccountDeletedByUserEvent`, selv om filen ligger som `AccountDeletedByUserEvent.cs`.

---

## ⚙️ SystemActions (`Contracts.Events.SystemActions`)

Trigges av tidsstyrte jobber i `recipe-auth-api` (GDPR-opprydding, inaktivitets- og
bekreftelsespåminnelser).

| Event | Felter | Beskrivelse |
| --- | --- | --- |
| `Confirmation7DaysReminderEvent` | `UserId`, `Email`, `Name`, `ConfirmationLink`, `RegisteredAt` | Første påminnelse til ubekreftet bruker etter 7 dager. |
| `Confirmation14DaysReminderEvent` | `UserId`, `Email`, `Name`, `ConfirmationLink`, `LockedAt` | Varsel om at ubekreftet konto er midlertidig sperret etter 14 dager. |
| `Inactivity6MonthsWarningEvent` | `UserId`, `Email`, `Name`, `WarnedAt` | "Vi savner deg"-varsel etter 6 måneders inaktivitet. |
| `Inactivity1YearLockedEvent` | `UserId`, `Email`, `Name`, `LockedAt` | Varsel om deaktivering etter 1 års inaktivitet. |
| `UserAccountDeletedBySystemEvent`\* | `UserId`, `Email`, `Name`, `DeletionReason`, `DeletedAt` | Bekreftelse på automatisk systemstyrt kontosletting. |

\* Klassen heter `UserAccountDeletedBySystemEvent`, selv om filen ligger som `AccountDeletedBySystemEvent.cs`.

---

## 🛡️ AdminActions (`Contracts.Events.AdminActions`)

Trigges når en administrator utfører en manuell handling via admin-panelet.

| Event | Felter | Beskrivelse |
| --- | --- | --- |
| `AdminCustomEmailRequestedEvent` | `UserId`, `Email`, `Name`, `Subject`, `Message`, `SentAt` | Egendefinert e-post sendt manuelt av admin. |
| `EmailManuallyConfirmedByAdminEvent` | `UserId`, `Email`, `Name`, `ConfirmedAt` | E-postadresse bekreftet av admin. |
| `UserAccountDeletedByAdminEvent` | `UserId`, `Email`, `Name`, `DeletedAt` | Konto slettet av admin. |
| `UserDeletedAndBlacklistedByAdminEvent` | `UserId`, `Email`, `Name`, `Reason?`, `DeletedAt` | Konto slettet og e-postadresse svartelistet. |
| `UserLockedByAdminEvent` | `UserId`, `Email`, `Name`, `ReasonDetails`, `LockedAt` | Konto midlertidig sperret, med begrunnelse. |
| `UserUnlockedByAdminEvent` | `UserId`, `Email`, `Name`, `UnlockedAt` | Konto gjenåpnet. |
| `UserUpdatedByAdminEvent` | `UserId`, `Email`, `Name`, `OldEmail`, `NewEmail`, `UpdatedAt` | Profilinformasjon oppdatert av admin. |

---

## 🚨 Systemvarsel (`Contracts.Events`)

| Event | Felter | Beskrivelse |
| --- | --- | --- |
| `InvalidEmailDetectedEvent` | `UserId`, `Email`, `Reason`, `DetectedAt` | Publiseres av `PendingEmailService` ved hard bounce. Konsumeres av `recipe-auth-api` for sperring/opprydding av kontoen. |

---

## 🛠️ NotificationManagement (`Contracts.{Commands,Queries}.NotificationManagement`)

Se [05-notification-management-and-planned-work.md](05-notification-management-and-planned-work.md) for
full beskrivelse av admin-flyten og en viktig merknad om planlagt flytting til `recipe-system-api`.

| Kontrakt | Type | Felter |
| --- | --- | --- |
| `GetFailedNotificationsQuery` / `GetFailedNotificationsResponse` | Query (Request-Response) | Response: `List<FailedNotificationDto>` |
| `RetryFailedNotificationCommand` | Command | `NotificationIds: List<Guid>` |
| `DeleteFailedNotificationCommand` | Command | `NotificationIds: List<Guid>` |

---

## Consumer → Processor-mønsteret

Hvert event har tre deler:

1. **Consumer** (`Service/Consumers/{Domain}/{EventName}Consumer.cs`) - implementerer
   `IConsumer<TEvent>`, logger at eventet er mottatt, og delegerer umiddelbart til en prosessor. Skal
   **ikke** inneholde forretningslogikk.
2. **Processor** (`Infrastructure/Processors/{Domain}/{EventName}Processor.cs`) - bygger Scriban-modellen,
   kaller `ITemplateRenderService.RenderTemplateAsync(...)` og deretter
   `IPendingEmailService.ProcessEmailWithRetryAsync(...)`.
3. **`IEventProcessor<TEvent>`** (`Infrastructure/Processors/Interfaces/IEventProcessor.cs`) - **ett felles
   generisk grensesnitt** som alle prosessorer implementerer (`IEventProcessor<UserRegisteredEvent>` osv.).
   Det finnes **ikke** egne `I{EventName}Processor`-grensesnitt per event lenger - det ble fjernet fordi
   det var seremoni uten reell polymorfi (20 nesten identiske grensesnitt som aldri ble brukt til annet
   enn dependency injection).

Registrering skjer manuelt to steder i `Service/Extensions/` - det finnes ingen assembly-scanning:

```csharp
// MailProcessorExtensions.cs
services.AddTransient<IEventProcessor<UserRegisteredEvent>, UserRegisteredProcessor>();

// MassTransitExtensions.cs
x.AddConsumer<UserRegisteredConsumer>();
```

## Sjekkliste: legge til en ny e-postnotifikasjon

1. **Kontrakt** - opprett event-/kommando-klasse under `Contracts/{Events|Commands}/{Domain}/`. Inkluder
   kun nødvendige felt.
2. **Publisering** - injiser `IPublishEndpoint` i den utløsende tjenesten (f.eks. `recipe-auth-api`) og
   publiser eventet.
3. **HTML-mal** - se [03-email-templates-and-design.md](03-email-templates-and-design.md) for
   layout-mekanismen (`_Layout.html` + `capture`/`include`).
4. **Prosessor** - opprett `{Domain}/{EventName}Processor.cs` som implementerer
   `IEventProcessor<{EventName}Event>`. Bygg modellen, rendre malen, send via
   `IPendingEmailService.ProcessEmailWithRetryAsync(..., nameof(EventName))`.
5. **Consumer** - opprett `{Domain}/{EventName}Consumer.cs : IConsumer<TEvent>` som tar
   `IEventProcessor<TEvent> processor` i konstruktøren og kaller den fra `Consume`.
6. **DI-registrering** - registrer prosessoren (`Transient`) i `MailProcessorExtensions.cs` og consumeren
   i `MassTransitExtensions.cs`, under riktig domeneseksjon.
7. **Testing** - se [06-test-strategy.md](06-test-strategy.md):
   * Processor-enhetstest: verifiser stibane/modell mot `ITemplateRenderService`, og riktige parametre mot
     `IPendingEmailService`.
   * Template-integrasjonstest: bekreft at malen kompilerer/rendrer fra disk.
   * Consumer-komponenttest: bekreft at `MassTransit.TestHarness` fanger opp eventet og kaller prosessoren.
