# 📑 MassTransit Contracts Specification

Dette dokumentet gir en fullstendig oversikt over alle kontrakter som utveksles over meldingsbussen (RabbitMQ via MassTransit) i Kjøkkenhylla-plattformen.

Kontraktene er delt inn etter domener og operasjonstype (Events, Commands, Queries) for å opprettholde en streng og forutsigbar domeneisolasjon.

---

## 📐 Navnerom og Struktur

* **Events (Hendelser):** Pasitive, fortidskonstruerte navneformer (`UserRegisteredEvent`). Publiseres asynkront (`Publish`).
* **Commands (Kommandoer):** Imperative navneformer (`DeleteFailedNotificationCommand`). Sendes målrettet mot én mottaker (`Send`).
* **Queries (Spørringer):** Spesifikke forespørsler etter data med forventet respons (`GetFailedNotificationsQuery`). Benytter MassTransit Request-Response mønster.

---

## 🛡️ 1. AdminActions (`Contracts.Events.AdminActions`)

Events som trigges når en administrator utfører en manuell handling på en bruker eller konto via administrasjonspanelet.

| Event-navn | Felter / Egenskaper | Beskrivelse |
| --- | --- | --- |
| `AdminCustomEmailRequestedEvent` | `Guid UserId`, `string Email`, `string Name`, `string Subject`, `string MessageBody` | Egendefinert e-post utsendt manuelt av admin til en enkeltbruker. |
| `EmailManuallyConfirmedByAdminEvent` | `Guid UserId`, `string Email`, `string Name`, `DateTime ConfirmedAt` | Varsel til bruker om at e-postadressen er bekreftet av admin. |
| `UserAccountDeletedByAdminEvent` | `Guid UserId`, `string Email`, `string Name`, `DateTime DeletedAt` | Varsel til bruker om at brukerkontoen har blitt slettet av admin. |
| `UserDeletedAndBlacklistedByAdminEvent` | `Guid UserId`, `string Email`, `string Name`, `string? Reason`, `DateTime DeletedAt` | Varsel om at kontoen er slettet og e-postadressen svartelistet. |
| `UserLockedByAdminEvent` | `Guid UserId`, `string Email`, `string Name`, `string ReasonDetails`, `DateTime LockedAt` | Varsel til bruker om at kontoen er midlertidig sperret med begrunnelse. |
| `UserUnlockedByAdminEvent` | `Guid UserId`, `string Email`, `string Name`, `DateTime UnlockedAt` | Varsel til bruker om at kontoen har blitt gjenåpnet av admin. |
| `UserUpdatedByAdminEvent` | `Guid UserId`, `string Email`, `string Name`, `string OldEmail`, `string NewEmail`, `DateTime UpdatedAt` | Varsel til bruker om at profilinformasjon har blitt oppdatert av admin. |

---

## ⚙️ 2. SystemActions (`Contracts.Events.SystemActions`)

Events som trigges automatisk av bakgrunnsjobber og livssyklusprosesser i plattformen (f.eks. GDPR-opprydding og automatiske påminnelser).

| Event-navn | Felter / Egenskaper | Beskrivelse |
| --- | --- | --- |
| `Confirmation7DaysReminderEvent` | `Guid UserId`, `string Email`, `string Name`, `string ConfirmationToken` | Første påminnelse til ubekreftet bruker etter 7 dager. |
| `Confirmation14DaysReminderEvent` | `Guid UserId`, `string Email`, `string Name` | Varsel om at ubekreftet konto er midlertidig deaktivert etter 14 dager. |
| `AccountDeletedBySystemEvent` | `Guid UserId`, `string Email`, `string Name`, `DateTime DeletedAt` | Bekreftelse på at ubekreftet konto har blitt permanent slettet (+30 dager). |

---

## 👤 3. UserActions (`Contracts.Events.UserActions`)

Events som trigges direkte av sluttdokumenterte brukerhandlinger i `Account API` eller nettleseren.

| Event-navn | Felter / Egenskaper | Beskrivelse |
| --- | --- | --- |
| `UserRegisteredEvent` | `Guid UserId`, `string Email`, `string Name`, `string ConfirmationToken` | Sendes ved ny registrering for utsending av velkomst- og bekreftelsese-post. |
| `UserRegisteredWithGoogleEvent` | `Guid UserId`, `string Email`, `string Name` | Velkomstmelding til ny bruker som opprettet konto via Google OAuth. |
| `ResendEmailConfirmationRequestedEvent` | `Guid UserId`, `string Email`, `string Name`, `string ConfirmationToken` | Utløses når bruker ber om å få tilsendt bekreftelseslenke på nytt. |
| `PasswordResetRequestedEvent` | `Guid UserId`, `string Email`, `string Name`, `string ResetToken` | Utløses ved glemte passord; inneholder lenke med tilbakestillingstoken. |
| `PasswordChangedEvent` | `Guid UserId`, `string Email`, `string Name`, `DateTime ChangedAt` | Sikkerhetsvarsel til bruker om at passordet har blitt endret. |
| `ContactFormSubmittedEvent` | `Guid TicketId`, `string SenderName`, `string SenderEmail`, `string Subject`, `string Message` | Genererer to e-poster: Varsel til Support/Admin og bekreftelseskvittering til avsender. |
| `AccountDeletedByUserEvent` | `Guid UserId`, `string Email`, `string Name`, `DateTime DeletedAt` | Bekreftelse på at brukeren selv har slettet sin egen konto. |

---

## 🚨 4. NotificationManagement & Failures (`Contracts.*.NotificationManagement`)

Kontrakter for feilhåndtering, uleverbar e-post og administrering av den transiente MongoDB-bufferen fra admin-dashbordet.

### 📤 Events (Hendelser sendt fra Notification Service)

| Event-navn | Navnerom | Felter | Beskrivelse |
| --- | --- | --- | --- |
| `InvalidEmailDetectedEvent` | `Contracts.Events` | `Guid UserId`, `string Email`, `string Reason`, `DateTime DetectedAt` | Publiseres ved hard bounce / permanent avviste adresser. Konsumeres av `Auth API` for sperring av konto. |

---

### 📥 Queries & Responses (Request-Response: Core API ↔ Notification Service)

| Query / Response | Navnerom | Felter | Beskrivelse |
| --- | --- | --- | --- |
| `GetFailedNotificationsQuery` | `Contracts.Queries` | *Ingen (eller filter)* | Core API ber om oversikt over alle ubehandlede/feilede e-poster i MongoDB. |
| `GetFailedNotificationsResponse` | `Contracts.Queries` | `List<FailedNotificationDto> Items` | Returnerer listen med feilede e-poster, inkludert sist oppståtte SMTP-feilmelding. |

---

### 📥 Commands (Kommandoer fra Core API til Notification Service)

| Command-navn | Navnerom | Felter | Beskrivelse |
| --- | --- | --- | --- |
| `RetryFailedNotificationCommand` | `Contracts.Commands` | `List<Guid> NotificationIds` | Beordrer ny utsending (`PendingEmailService`) for spesifiserte feilede e-poster. |
| `DeleteFailedNotificationCommand` | `Contracts.Commands` | `List<Guid> NotificationIds` | Sletter spesifiserte e-poster fra MongoDB-bufferen uten å sende dem på nytt. |