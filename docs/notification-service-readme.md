# 📧 Recipe Notification Service

En dedikert mikrotjeneste for asynkron håndtering og utsending av e-post og meldinger for Recipe-plattformen. Tjenesten fungerer som en frikoblet bakgrunnstjeneste som lytter på hendelser fra andre mikrotjenester og tar seg av e-postdistribusjon, mal-generering og feilhåndtering.

---

## 🎯 Hensikt og Rolle

* **Frikoblet E-postlogikk:** Skiller e-postutsending, HTML-maler og e-postleverandører helt ut fra Account API, Core API og øvrige mikrotjenester.
* **Asynkron Ytelse:** Sørger for at brukeroperasjoner (som registrering, passordtilbakestilling og kontaktskjemaer) oppleves lynraske i grensesnittet uten å bli blokkert av eksterne e-postservere.
* **Feiltoleranse & Bounces:** Håndterer midlertidige nettverksbrudd automatisk via retries, samt fanger opp permanente avvisninger (hard bounces/døde e-postadresser) via Dead-Letter Queues (DLQ).

---

## 🛠️ Teknologistakk & Sentrale Pakker

### Kjerne & Rammeverk

* **.NET 10 (C#)** – Bakgrunnsprosessering via Worker Service.
* **MassTransit** – Service Bus-rammeverk for hendelsesdrevet kommunikasjon.
* **RabbitMQ** – Asynkron meldingsmegler (Message Broker).

### E-post & Templating

* **MailKit / MimeKit** – Robust motor for e-post og SMTP-utsendelse.
* **Scriban / Fluid** – Templating engines for dynamisk innfylling i HTML-maler.

---

## 🏗️ Prosjektoversikt

* **`Recipe.Notification.Contracts`**
*Class Library* som inneholder alle felles meldingskontrakter og hendelsestyper (Events) som publiseres til og fra meldingsbussen.
* **`Recipe.Notification.Service`**
*Worker Service* som lytter på RabbitMQ via MassTransit, prosesserer innkommende hendelser, genererer e-postmaler og håndterer utsending.