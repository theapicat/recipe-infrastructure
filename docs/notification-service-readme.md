# 📧 Recipe Notification Service

En dedikert, asynkron bakgrunnstjeneste for e-postdistribusjon og varsling i Recipe-plattformen. Tjenesten lytter utelukkende på meldinger fra meldingsbussen (RabbitMQ) og håndterer alt fra bekreftelses-e-poster og passordtilbakestillinger til kontaktskjemaer, oppskriftsdeling og automatisert konto-opprydding.

---

## 🎯 Hensikt og Formål

* **Lynrask Brukeropplevelse:** E-postutsendelse over SMTP tar tid. Ved å flytte utsendelsen til en egen bakgrunnstjeneste får brukeren umiddelbar respons i applikasjonen, mens e-posten behandles asynkront i bakgrunnen.
* **Isolasjon av E-postlogikk:** Skiller e-postmaler, HTML-design og e-postleverandører (SMTP/MailKit) helt ut fra `Account API` og `Core API`.
* **Automatisk Livssyklus & GDPR:** Håndterer påminnelser, deaktivering og permanent sletting av inaktive eller ubekreftede kontoer i henhold til plattformens juridiske brukervilkår.
* **Vekst & Sosiale Funksjoner:** Støtter vervelenker, invitasjoner og oppskriftsdeling for å skape en naturlig vekstmotor for plattformen.
* **Enkel Vedlikeholdbarhet:** HTML-maler ligger adskilt fra kildekoden, slik at e-postdesign kan endres uten å røre forretningslogikken.

---

## ⚖️ Konto-livssyklus & Juridiske Frister

Tjenesten orkestrerer e-postvarsler knyttet til brukerkontoenes livssyklus basert på plattformens juridiske brukervilkår:

### 📩 Ubekreftede Kontoer (E-postverifisering)

* **Dag 7:** Første varsel og påminnelse om å bekrefte e-postadressen.
* **14 dager (2 uker):** Kontoen blir midlertidig **sperret** dersom e-posten fortsatt ikke er bekreftet.
* **+30 dager etter sperring:** Kontoen og tilhørende data slettes permanent.

### 💤 Inaktive Kontoer

* **6 måneder:** Varsel om inaktivitet sendes til brukeren ("Vi savner deg").
* **1 år:** Kontoen **sperres** midlertidig på grunn av langvarig inaktivitet.
* **+30 dager etter sperring:** Kontoen og alle personaliserte data **slettes permanent** (GDPR-opprydding).

---

## ✨ Kjerne-features

### 1. 📬 Hendelsesbasert E-postutsendelse (Event-Driven)

* **Support:** Kontaktskjema-henvendelser og automatisk kvittering til avsender.
* **Konto & Sikkerhet:** Velkomst-e-post, manuell re-utsending av verifisering, og tilbakestilling av passord.
* **Livssyklus & GDPR:** Påminnelser om ubekreftede/inaktive kontoer, sperrenotiser og bekreftelse på sletting.
* **Sosialt:** App-anbefalinger til venner, samt deling av oppskrifter med registrerte og uregistrerte brukere.

### 2. 🎨 Dynamiske HTML-Maler (Scriban Engine)

* Benytter ren HTML kombinert med **Scriban** som malmotor.
* Dynamiske variabler som `{{ name }}`, `{{ subject }}`, `{{ submitted_at }}` fylles inn automatisk fra hendelsene.

### 3. 🧩 Dekoblet Arkitektur & Prosessering

* Skiller skarpt mellom levering (`EmailDeliveryService`), mal-rendering (`EmailTemplateRenderer`) og forretningsorkestrering (`Processors`).

### 4. 🧪 Trygg Lokal Testing (Mailpit)

* Integrert mot **Mailpit** i utviklingsmiljøet (`http://localhost:8025`). Alle e-poster fanges opp i en lokal catch-all-innboks.

---

## 🗺️ Arbeidsflyt (Execution Flow)

```text
[ RabbitMQ / MassTransit ]
          │
          ▼ (Mottar hendelse, f.eks. ContactFormSubmittedEvent)
1. Consumer (ContactFormSubmittedConsumer)
          │
          ▼ (Passerer melding & CancellationToken)
2. Processor (ContactFormNotificationProcessor)
          │
          ├──► Step 1: Render HTML (EmailTemplateRenderer / Scriban)
          │        └─ Leser mal fra TemplateService/Templates/*.html
          │
          ├──► Step 2: Send e-post (EmailDeliveryService / MailKit)
          │        ├─ E-post 1: Varsel til Support / Admin
          │        └─ E-post 2: Kvittering til Bruker
          │
          └──► Step 3: Feilhåndtering & DLQ
                   └─ Ved hard bounce/feil kastes exception (MassTransit retry / DLQ) 🛑

```

---

## 📋 Master-oversikt over E-postmaler

| Kategori | Malnavn (`TemplateName`) | Mottaker | Trigger-hendelse / Beskrivelse |
| --- | --- | --- | --- |
| **Support** | `ContactFormAdminNotification` | Admin / Support | `ContactFormSubmittedEvent` (Innsendt kontaktskjema) |
| **Support** | `ContactFormUserReceipt` | Bruker (Avsender) | `ContactFormSubmittedEvent` (Kvittering på henvendelse) |
| **Verifisering** | `UserRegisteredWelcome` | Ny bruker | `UserRegisteredEvent` (Velkommen + verifiseringslenke) |
| **Verifisering** | `EmailVerificationReminder` | Ubekreftet bruker | Automatisk påminnelse om å bekrefte e-post (Dag 7) |
| **Verifisering** | `EmailVerificationManualRequested` | Ubekreftet bruker | `EmailVerificationRequestedEvent` (Manuell forespørsel om ny lenke) |
| **Verifisering** | `AccountLockedUnverified` | Ubekreftet bruker | Konto midlertidig sperret pga. unnlatt bekreftelse (Dag 14) |
| **Sikkerhet** | `PasswordResetRequested` | Bruker | `PasswordResetRequestedEvent` (Glemt passord / gjenoppretting) |
| **Sikkerhet** | `PasswordChangedSecurityNotice` | Bruker | `PasswordChangedEvent` (Sikkerhetsvarsel om endret passord) |
| **Livssyklus** | `UserInactivityWarning` | Inaktiv bruker | Varsel om inaktivitet (6 måneder uten innlogging) |
| **Livssyklus** | `AccountLockedInactivity` | Inaktiv bruker | Konto midlertidig sperret pga. inaktivitet (1 år) |
| **Sletting** | `AccountSelfDeletedConfirmation` | Bruker | `UserAccountDeletedEvent` (Bruker har slettet kontoen selv) |
| **Sletting** | `AccountDeletedConfirmation` | Tidligere bruker | Permanent sletting utført etter sperrefrist (+30 dager) |
| **Sosialt** | `AppRecommendation` | Potensiell bruker | `AppRecommendationSentEvent` (Bruker inviterer en venn) |
| **Sosialt** | `RecipeSharedExistingUser` | Registrert bruker | `RecipeSharedWithUserEvent` (Deling av oppskrift internt) |
| **Sosialt** | `RecipeSharedPendingUser` | Potensiell bruker | `RecipeSharedWithNonRegisteredUserEvent` (Deling eksternt) |


---

## 📋 Sjekkliste for Utvikling

* [x] **1. Infrastruktur & Meldingsbuss (`Infrastructure & Service`)**
* [x] Opprette oppkobling til RabbitMQ via MassTransit.
* [x] Etablere `EmailDeliveryService` (MailKit / SMTP).
* [x] Etablere `EmailTemplateRenderer` (Scriban engine).
* [x] Konfigurere `<Content>` i `.csproj` for automatisk kopiering av HTML-maler til `bin/`.


* [x] **2. Kontaktskjema Utsending (`Support Flow`)**
* [x] Opprette `ContactFormAdminNotification.html` og `ContactFormUserReceipt.html`.
* [x] Bygge `ContactFormNotificationProcessor` for tosidig utsending (admin + bruker).
* [x] Bygge `ContactFormSubmittedConsumer` koblet mot RabbitMQ.


* [ ] **3. Konto & Sikkerhet (`Account Flow`)**
* [ ] Bygge prosessor og mal for `UserRegisteredWelcome`.
* [ ] Bygge prosessor og mal for `PasswordResetRequested`.
* [ ] Implementere `EmailDeliveryFailedEvent` for feedback loop ved hard bounces.


* [ ] **4. Livssyklus & GDPR (`Lifecycle Flow`)**
* [ ] Bygge maler for 7-dagers og 14-dagers verifiseringsvarsler.
* [ ] Bygge maler for 6-måneders og 1-års inaktivitetsvarsler.


* [ ] **5. Sosiale Funksjoner (`Social Flow`)**
* [ ] Bygge prosessor og maler for app-anbefaling og oppskriftsdeling.
