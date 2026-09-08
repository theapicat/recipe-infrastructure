# Todo!!

## Notifications service integrering i ande applikasjoner!

### 🔑 1. Auth API (Sikkerhet & Konto-håndtering)

Hovedoppgaven til Auth API er å fange opp oppdagede e-postfeil fra `recipe-notification-service` og iverksette sikkerhetstiltak på brukerkontoen.

* [ ] **Konsumere `InvalidEmailDetectedEvent`:**
* Legge til en MassTransit Consumer for `InvalidEmailDetectedEvent`.


* [ ] **Håndtering av Hard Bounce:**
* Når eventet mottas: Finne brukeren via `Email` eller `UserId`.
* Marker e-postadressen som ugyldig (f.eks. `IsEmailInvalid = true`).
* Sett brukerkontoen i karantene / sperret tilstand med begrunnelsen `"Ugyldig eller feilet e-postadresse"`.
* (Valgfritt): Utløs en tidsstyrt oppryddingsjobb som sletter eller svartelister ubekreftede kontoer med permanent avviste e-postadresser etter et gitt antall dager.

---

### ⚙️ 2. Core API (Admin Backend & Meldingsformidling)

Core API fungerer som broen mellom administrasjonspanelet i frontend og `recipe-notification-service` over MassTransit.

* [ ] **Endepunkter for Administrasjon av Feilede E-poster:**
* `GET /api/admin/notifications/failed`:
* Sender `GetFailedNotificationsQuery` over MassTransit via Request-Response mønster.
* Returnerer `GetFailedNotificationsResponse` (`List<FailedNotificationDto>`) til frontend.


* `POST /api/admin/notifications/retry`:
* Tar imot en liste med ID-er (`List<Guid> notificationIds`).
* Sender `RetryFailedNotificationCommand` til `recipe-notification-service`.


* `DELETE /api/admin/notifications/failed`:
* Tar imot en liste med ID-er (`List<Guid> notificationIds`).
* Sender `DeleteFailedNotificationCommand` til `recipe-notification-service`.


* [ ] **Publisering av Administrative Events:**
* Sørge for at administrative handlinger i Core API publiserer sine respektive eventer på meldingsbussen:
* `AdminCustomEmailRequestedEvent`
* `UserLockedByAdminEvent` / `UserUnlockedByAdminEvent`
* `EmailManuallyConfirmedByAdminEvent`
* `UserDeletedAndBlacklistedByAdminEvent`
* `UserUpdatedByAdminEvent`

---

### 💻 3. Admin Webapp / Frontend (Mantine UI)

Utsikten og kontrollpanelet hvor administrator har full oversikt og styring over den transiente feilkøen (DLQ).

* [ ] **Dedikert Side / Fane for E-postkø (Failed Notifications / DLQ):**
* Opprette en oversiktsside under admin-panelet (f.eks. `/admin/notifications`).


* [ ] **Tabellvisning (`<Table/>`):**
* Vise feltene fra `FailedNotificationDto`:
* **Mottaker:** (`RecipientEmail`)
* **Emne / Type:** (`Subject` / `EventType`)
* **Feilmelding:** (`LastErrorMessage` — med tooltip/modal for lange feilmeldinger)
* **Forsøk:** (`RetryCount`)
* **Dato opprettet / Sist forsøkt:** (`CreatedAt` / `LastAttemptAt`)


* [ ] **Handlingsknapper & Bulk Actions:**
* Avkrysningsbokser for rader i tabellen (velge én, flere eller alle).
* **Knapp "Prøv på nytt" (`terracotta` / `sage` primary):** Sender valgte ID-er til `POST /api/admin/notifications/retry`.
* **Knapp "Slett" (`red` / danger):** Sender valgte ID-er til `DELETE /api/admin/notifications/failed`.


* [ ] **Varselsbanner / Status-indikator:**
* Vise et lite varselbanner i toppmenyen/dashbordet dersom systemet har aktive feil i e-postkøen, slik at admin umiddelbart ser når noe krever ettersyn.