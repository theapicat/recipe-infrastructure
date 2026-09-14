# 🛠️ Notification Management og planlagt arbeid

## Dagens admin-flyt

All kommunikasjon mellom admin-dashbordet og `recipe-notification-service` for å håndtere uleverte
e-poster går over MassTransit (Request-Response for spørringer, Send for kommandoer) - det finnes ingen
REST-endepunkter på denne tjenesten.

| Kontrakt | Type | Consumer | Beskrivelse |
| --- | --- | --- | --- |
| `GetFailedNotificationsQuery` | Query | `GetFailedNotificationsConsumer` | Returnerer alle dokumenter fra `failed_notifications` som `List<FailedNotificationDto>`. |
| `RetryFailedNotificationCommand` | Command | `RetryFailedNotificationCommandConsumer` | Nullstiller `RetryCount`, forsøker å sende e-postene på nytt via `PendingEmailService`. Se [04-error-handling-and-resilience.md](04-error-handling-and-resilience.md) for de eksakte reglene om når dokumentet slettes vs. beholdes. |
| `DeleteFailedNotificationCommand` | Command | `DeleteFailedNotificationCommandConsumer` | Sletter valgte dokumenter permanent fra MongoDB uten å forsøke re-sending. |

Begge kommando-consumerne tilbakestiller `NotificationStateStore` når antall gjenværende dokumenter i
MongoDB når 0.

`FailedNotificationDto` (i `GetFailedNotificationsResponse`) inneholder: `Id`, `RecipientEmail`, `Subject`,
`HtmlBody`, `EventType`, `LastErrorMessage`, `RetryCount`, `CreatedAt`, `LastAttemptAt`.

---

## 🔮 Planlagt: utskilling til `recipe-system-api`

> **Status:** Planlagt, ikke påbegynt. Beskrevet her som en markør for fremtidig arbeid - detaljert design
> gjenstår.

All redigering, endring og retry av usendte/feilede e-poster er tenkt flyttet ut av admin-dashbordets
direkte kommunikasjon med `recipe-notification-service`, og over til en egen, ny mikrotjeneste:
**`recipe-system-api`**.

Praktisk betyr dette at kontraktene under `Contracts/{Commands,Queries}/NotificationManagement/` (og
tilhørende consumers i `Service/Consumers/NotificationManagement/`) på sikt forventes å bli konsumert og
eid av `recipe-system-api` i stedet for å bli kalt direkte fra Core API / admin-panelet mot denne
tjenesten. `recipe-notification-service` vil sannsynligvis fortsatt eie selve MongoDB-bufferen og
utsendingslogikken (`PendingEmailService`), men grensesnittet for administrasjon av den kan flytte.

Inntil dette er planlagt i detalj og implementert:

* Dagens oppførsel (beskrevet over og i 04-error-handling-and-resilience.md) er fortsatt gjeldende og
  produksjonsriktig.
* Ikke bygg videre på antakelsen om at Core API kaller denne tjenesten direkte for
  NotificationManagement-operasjoner uten å sjekke om `recipe-system-api` har overtatt dette ansvaret.
* Oppdater dette dokumentet så snart utskillingen faktisk er planlagt/påbegynt.
