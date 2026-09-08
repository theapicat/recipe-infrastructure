# 📧 Recipe Notification Service

En dedikert, asynkron bakgrunnstjeneste for e-postdistribusjon og varsling i Kjøkkenhylla-plattformen. Tjenesten lytter utelukkende på meldinger fra meldingsbussen (RabbitMQ) og håndterer alt fra velkomstmeldinger og passordtilbakestillinger til admin-handlinger, sikkerhetsvarsler og automatisert konto-opprydding.

---

## 🎯 Hensikt og Formål

* **Asynkron E-postbehandling:** Avlaster `Account API` og `Core API` ved å flytte SMTP-sending til en isolert bakgrunnstjeneste for umiddelbar respons i frontend.
* **Isolasjon av E-postlogikk:** E-postmaler, HTML-design og MailKit/SMTP-konfigurasjon er helt adskilt fra andre mikrotjenester.
* **Strenge Domenegrenser:** Koden og malene er strukturert i tre isolerte domener: `AdminActions`, `SystemActions` og `UserActions`.
* **Resiliens & Buffering:** Innebygd støtte for in-line re-forsøk, varsling til admin og transient buffering i MongoDB dersom SMTP-utsendelse feiler.

---

## 🛠️ Teknologistack

* **Framework:** .NET 10 / C#
* **Meldingsbuss:** MassTransit 8 (med RabbitMQ som broker)
* **E-postmotor:** MailKit / MimeKit (SMTP)
* **Malmotor:** Scriban (HTML-rendering med dynamiske variabler)
* **Transient Buffer:** MongoDB (`recipe_notification_db`)
* **Lokal Testing:** Mailpit (`http://localhost:8025`)
* **Logging:** Serilog & Seq

---

## 📚 Dybdedokumentasjon

For spesifikke detaljer om feilhåndtering, kontrakter, teststrategi og design, se de dedikerte dokumentene i prosjektet:

* 📑 **[MassTransit Kontraktsspesifikasjon](https://github.com/theapicat/recipe-notification-service/blob/main/Documentation/notification-contracts.md):** Fullstendig oversikt over alle Events, Commands og Queries som utveksles over meldingsbussen.
* 🛡️ **[Arkitektur for Feilhåndtering & Resiliens](https://github.com/theapicat/recipe-notification-service/blob/main/Documentation/notification-error-handling.md):** Detaljert beskrivelse av `TemplateRenderException`, `EmailDeliveryException`, in-line re-forsøk, `NotificationStateStore` og MongoDB-bufferen.
* 🧪 **[Teststrategi & Verktøykasse](https://github.com/theapicat/recipe-notification-service/blob/main/Documentation/notification-test-strategy.md):** Retningslinjer for enhetstesting av prosessorer, mal-rendering og MassTransit Consumers vha. xUnit, NSubstitute og Shouldly / FluentAssertions.
* 🎨 **[Designsystem & E-poststiling](https://github.com/theapicat/recipe-notification-service/blob/main/Documentation/notification-design-system.md):** Kjøkkenhyllas fargepalett, WCAG AA-kontraster og inline CSS-regler for HTML-maler.

---

## 📋 Oversikt over Domener og E-postmaler

E-postutsendelser er organisert under sine respektive domener:

### 🛡️ 1. AdminActions (`AdminActions/*`)
Administrative handlinger utløst av administrator via admin-panelet:
* `AdminCustomEmail` (Egendefinert e-post)
* `EmailManuallyConfirmedByAdmin` (Manuell e-postbekreftelse)
* `UserAccountDeletedByAdmin` (Konto slettet av admin)
* `UserDeletedAndBlacklistedByAdmin` (Konto slettet og svartelistet)
* `UserLockedByAdmin` (Konto sperret med begrunnelse)
* `UserUnlockedByAdmin` (Konto gjenåpnet)
* `UserUpdatedByAdmin` (Profil oppdatert av admin)

### ⚙️ 2. SystemActions (`SystemActions/*`)
Automatiske system- og livssyklusprosesser (f.eks. GDPR):
* `Confirmation7DaysReminder` (Påminnelse om bekreftelse dag 7)
* `Confirmation14DaysReminder` (Konto midlertidig deaktivert dag 14)
* `AccountDeletedBySystem` (Permanent sletting etter 30 dager)

### 👤 3. UserActions (`UserActions/*`)
Sluttdokumenterte brukerhandlinger utløst fra webapplikasjonen:
* `UserRegisteredWelcome` (Velkomstmelding med bekreftelseslenke)
* `UserRegisteredWithGoogleWelcome` (Velkomst for Google OAuth)
* `ResendEmailConfirmation` (Ny bekreftelseslenke etter forespørsel)
* `PasswordResetRequested` (Lenke for tilbakestilling av passord)
* `PasswordChangedSecurityNotice` (Sikkerhetsvarsel om endret passord)
* `ContactFormAdminNotification` (Varsel til support om kontaktskjema)
* `ContactFormUserReceipt` (Kvittering til avsender)
* `AccountDeletedByUser` (Bekreftelse på egenhendig sletting)

---

## 🧪 Lokal Testing med Mailpit

I lokalmiljøet sendes e-poster til **Mailpit** for inspeksjon:

1. Start Mailpit via Docker Compose (`docker compose up -d recipe-mailpit`).
2. Åpne Web-UI i nettleseren på `http://localhost:8025`.
3. Alle utsendelser fra bakgrunnstjenesten fanges opp for inspeksjon av HTML, responsive rammer og dynamiske lenker.

---

## 🚀 Roadmap & Fremtidige Funksjoner

* [ ] **Migrering til OpenTransit:** Tjenesten planlegges migrert over til OpenTransit så snart dette rammeverket lanseres som erstatning for MassTransit.
* [ ] **Full Testdekning:** Implementere full enhetstestdekning for alle prosessorer og integrasjonstester for Scriban-rendering.
* [ ] **Sosiale Varsler (`Social Flow`):** Maler for deling av oppskrifter (`RecipeSharedWithUserEvent`) og vervelenker.
* [ ] **Inaktivitetsvarsler (`Inactivity Flow`):** Automatiske varsler for inaktive brukere etter 6 og 12 måneder.