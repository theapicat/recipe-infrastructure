# 📧 Recipe Notification Service

En dedikert, asynkron bakgrunnstjeneste for e-postdistribusjon og varsling i Recipe-plattformen. Tjenesten lytter utelukkende på meldinger fra meldingsbussen (RabbitMQ) og håndterer alt fra bekreftelses-e-poster og passordtilbakestillinger til kontaktskjemaer og håndtering av ugyldige e-postadresser.

---

## 🎯 Hensikt og Formål

* **Lynrask Brukeropplevelse:** E-postutsendelse over SMTP kan ta sekunder. Ved å flytte utsendelsen til en egen bakgrunnstjeneste får brukeren umiddelbar respons i applikasjonen, mens e-posten behandles asynkront i bakgrunnen.
* **Isolasjon av E-postlogikk:** Skiller e-postmaler, HTML-design og e-postleverandører (SMTP/Resend/MailKit) helt ut fra `Account API` og `Core API`.
* **Konto-opprydding ("Dead Email"-håndtering):** Ved permanente leveringsfeil (hard bounces) kan tjenesten publisere en melding tilbake på bussen slik at brukerkontoen flagges for administrativ opprydding eller sletting.
* **Enkel Vedlikeholdbarhet:** HTML-maler ligger adskilt fra kildekoden, slik at e-postdesign kan endres og forbedres uten å røre forretningslogikken.

---

## ✨ Kjerne-features

### 1. 📬 Hendelsesbasert E-postutsendelse (Event-Driven)

* **Konto-opprettelse:** Reagerer på `UserRegisteredEvent` og sender ut e-post med bekreftelseslenke.
* **Gjenoppretting:** Reagerer på `PasswordResetRequestedEvent` og sender tilbakestillingslenke.
* **Kontaktskjema:** Reagerer på `ContactFormSubmittedEvent` og videresender henvendelser til support/admin.

### 2. 🎨 Dynamiske HTML-Maler (Scriban Engine)

* Benytter ren HTML kombinert med **Scriban** som malmotor.
* Dynamiske variabler som `{{ first_name }}`, `{{ confirmation_link }}` fylles inn automatisk basert på event-payloaden.
* Fleksibelt oppsett hvor nye maler enkelt kan legges til som `.html`-filer.

### 3. 🛡️ Bounces & Feilhåndtering (DLQ & Feedback Loop)

* Midlertidige nettverksfeil håndteres automatisk via retries og Dead-Letter Queues (DLQ) i MassTransit.
* Ved permanente avvisninger (hard bounce/ugyldig e-postadresse) publiseres `EmailDeliveryFailedEvent` tilbake til RabbitMQ, slik at `Account API` kan markere kontoen.

### 4. 🧪 Trygg Lokal Testing (Mailpit Integration)

* Fullstendig integrert med **Mailpit** i utviklingsmiljøet.
* Alle e-poster fra mock-brukere fanges opp i en lokal catch-all innboks (`http://localhost:8025`) uten fare for at e-poster sendes til ekte mottakere.

### 5. 🔒 Skjermet Bakgrunnstjeneste (Worker Service)

* Eksponerer ingen offentlige HTTP REST-endepunkter.
* Kommuniserer utelukkende internt over Docker-nettverket (`recipe-net`) via RabbitMQ.

---

## 🗺️ Arbeidsflyt (Execution Flow)

```text
[ RabbitMQ / MassTransit ]
         │ (Mottar hendelse, f.eks. UserRegisteredEvent)
         ▼
1. UserRegisteredConsumer
         │
         ├──► Step 1: Hent og bygg HTML-mal (Scriban Engine)
         │        └─ Fyller ut Templates/UserRegistered.html med data
         │
         ├──► Step 2: Send e-post via SMTP / MailKit
         │        └─ Sendes til Mailpit (dev) eller e-postleverandør (prod)
         │
         └──► Step 3: Feilhåndtering ved "Hard Bounce"
                  └─ Publiser EmailDeliveryFailedEvent (flagger konto for admin) 🛑

```

---

## 📋 Fremtidig Sjekkliste for Utvikling

* [ ] **1. Meldingskontrakter (`Contracts`)**
* Opprett `UserRegisteredEvent`, `PasswordResetRequestedEvent` og `ContactFormSubmittedEvent`.
* Opprett `EmailDeliveryFailedEvent` for tilbakemelding om døde e-postadresser.


* [ ] **2. Domenemodeller & Grensesnitt (`Domain`)**
* Definer `EmailMessage`-modellen.
* Definer grensesnittene `IEmailSender` og `IEmailTemplateEngine`.


* [ ] **3. Infrastruktur & HTML-Maler (`Infrastructure`)**
* Implementer `ScribanTemplateEngine` for parsing av `.html`-filer.
* Implementer `MailKitEmailSender` mot Mailpit (`localhost:1025`).
* Lag grunnleggende HTML-maler for velkomst, passordtilbakestilling og kontaktskjema.


* [ ] **4. Consumers & DI Setup (`Service`)**
* Bygg MassTransit-consumers for de definerte hendelsene.
* Konfigurer Serilog mot Seq for oversikt over sendte e-poster og feil.