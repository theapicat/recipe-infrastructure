# 📝 Utviklernotat: `recipe-notification-service`

Dette dokumentet oppsummerer arkitekturen, pakkefordelingen, den tekniske informasjonsflyten og den fremtidige implementasjonsplanen for **`recipe-notification-service`**. Notatet er ment som en teknisk referanse og huskeliste for videre utvikling.

---

## 🎯 Oversikt & Ansvar

`recipe-notification-service` er en helisolert, asynkron **Worker Service** bygget på **.NET 10** som tar seg av e-postdistribusjon og varsling for Recipe-plattformen.

* **Frikoblet arkitektur:** Tjenesten lytter utelukkende på hendelser fra meldingsbussen (**RabbitMQ / MassTransit**). Ingen REST API-endepunkter eksponeres.
* **Ytelse & Asynkronitet:** Tunge e-postoperasjoner og nettverkskall mot SMTP-servere blokkerer ikke brukeren i `recipe-web-app` eller `recipe-authentication-api`.
* **Feilhåndtering & Dead Email / Bounces:** Tjenesten håndterer automatisk retries ved midlertidige feil via Dead-Letter Queues (DLQ). Ved hard bounces (permanente feil) kan tjenesten publisere en `EmailDeliveryFailedEvent` tilbake til bussen slik at `Account API` kan merke brukerkontoen for administrativ opprydding.

---

## 🏗️ Prosjektstruktur (.NET Clean Architecture)

Tjenesten er delt inn i fire isolerte prosjekter for å skille hendelseskontrakter, forretningslogikk, mal-generering og oppstartskonfigurasjon:

```text
recipe-notification-service/
├── Recipe.Notification.Contracts/       # Class Library: Rene C# record-events (deles/siteres med andre microservices)
├── Recipe.Notification.Domain/          # Class Library: E-postmodeller, avsender/mottaker-objekter, grensesnitt (IEmailSender, IEmailTemplateEngine)
├── Recipe.Notification.Infrastructure/  # Class Library: MailKit (SMTP), Scriban (HTML-malmotor) og mal-filer (.html)
└── Recipe.Notification.Service/         # Worker Service Host: MassTransit Consumers, Serilog, Seq og DI-konfigurasjon

```

---

## 📦 Pakkekartlegging (NuGet per prosjekt)

| Prosjekt | NuGet-pakker | Beskrivelse / Ansvar |
| --- | --- | --- |
| **`Recipe.Notification.Contracts`** | *Ingen* | Rene C# `record`-typer (`UserRegisteredEvent`, `PasswordResetRequestedEvent`, `EmailDeliveryFailedEvent`). Helt fri for eksterne avhengigheter. |
| **`Recipe.Notification.Domain`** | *Ingen* | Kjerne-domenemodeller (`EmailMessage`) og grensesnitt (`IEmailSender`, `IEmailTemplateEngine`). |
| **`Recipe.Notification.Infrastructure`** | `MailKit`<br>

<br>`Scriban` | MailKit for SMTP/MimeMessage-bygging. Scriban for parsing og innfylling av variabler i HTML-maler (`.html`). |
| **`Recipe.Notification.Service`** | `MassTransit.RabbitMQ`<br>

<br>`Serilog.AspNetCore`<br>

<br>`Serilog.Sinks.Seq`<br>

<br>`Serilog.Settings.Configuration` | Host-prosjektet. Håndterer MassTransit-konsumenter, Serilog-konfigurasjon koblet til Seq og Dependency Injection. |

---

## 🔄 Teknisk Arbeidsflyt & Informasjonsflyt

```text
[ Ekstern Tjeneste (f.eks. Auth API) ]
                 │
                 │ Publiserer hendelse (f.eks. UserRegisteredEvent)
                 ▼
     [ RabbitMQ Message Broker ]
                 │
                 ▼
1. UserRegisteredConsumer (Recipe.Notification.Service)
                 │
                 ├─► 2. Generer HTML (Recipe.Notification.Infrastructure)
                 │      └─ ScribanTemplateEngine fyller ut Templates/UserRegistered.html
                 │
                 ├─► 3. Send E-post (Recipe.Notification.Infrastructure)
                 │      └─ MailKitEmailSender kobler til Mailpit (SMTP: 1025)
                 │
                 └─► 4. Ved Hard Bounce (Feilhåndtering)
                        └─ Publiserer EmailDeliveryFailedEvent tilbake på bussen 🛑

```

---

## 🧪 Lokal Test-infrastruktur (Mailpit)

I lokal utvikling fanges alle utgående e-poster opp av **Mailpit** (kjører i Docker via `recipe-infrastructure`). E-postene blir aldri sendt til ekte mottakere, men samles i et felles Web UI.

* **SMTP Host (fra vert/IDE):** `localhost:1025`
* **SMTP Host (internt i Docker-nettverk):** `recipe-mailpit:1025`
* **Innboks Dashboard (Web UI):** `http://localhost:8025`

### Konfigurasjon i `appsettings.Development.json` (`Recipe.Notification.Service`):

```json
{
  "ConnectionStrings": {
    "RabbitMq": "amqp://rabbit_user:rabbit_secure_password_dev@localhost:5672"
  },
  "MailSettings": {
    "Host": "localhost",
    "Port": 1025,
    "FromName": "Recipe Platform",
    "FromEmail": "no-reply@recipe.local"
  },
  "Serilog": {
    "WriteTo": [
      { "Name": "Console" },
      {
        "Name": "Seq",
        "Args": { "serverUrl": "http://localhost:5341" }
      }
    ]
  }
}

```

---

## 🛠️ E-postmaler med Scriban

Scriban benyttes som malmotor i `Recipe.Notification.Infrastructure`. Malfilene plasseres under en `Templates/`-mappe som `.html`-filer og fylles ut dynamisk.

### Eksempel: `Templates/UserRegistered.html`

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>Velkommen til Recipe</title>
</head>
<body style="font-family: sans-serif; line-height: 1.6;">
    <h2>Hei {{ first_name }}!</h2>
    <p>Takk for at du registrerte deg på Recipe-plattformen.</p>
    <p>Vennligst bekreft e-postadressen din ved å trykke på knappen under:</p>
    <p>
        <a href="{{ confirmation_link }}" 
           style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
           Bekreft konto
        </a>
    </p>
</body>
</html>

```

---

## 🚀 Implementasjonsplan / Sjekkliste for Neste Økt

Når kodingen av denne tjenesten skal ferdigstilles, anbefales følgende stegvise rekkefølge:

* [ ] **1. Meldingskontrakter (`Recipe.Notification.Contracts`)**
* Legg til `UserRegisteredEvent.cs` (`UserId`, `Email`, `FirstName`, `ConfirmationToken`).
* Legg til `PasswordResetRequestedEvent.cs` (`UserId`, `Email`, `ResetToken`).
* Legg til `ContactFormSubmittedEvent.cs` (`SenderEmail`, `Subject`, `Message`).
* Legg til `EmailDeliveryFailedEvent.cs` (`UserId`, `Email`, `Reason`, `Timestamp`).


* [ ] **2. Domenemodeller & Grensesnitt (`Recipe.Notification.Domain`)**
* Definer `EmailMessage.cs` (To, Subject, HtmlBody, PlainTextBody).
* Definer `IEmailSender.cs` (`Task SendAsync(EmailMessage message, CancellationToken ct)`).
* Definer `IEmailTemplateEngine.cs` (`Task<string> RenderAsync<T>(string templateName, T model)`).


* [ ] **3. Infrastruktur & Malutskrift (`Recipe.Notification.Infrastructure`)**
* Implementer `ScribanTemplateEngine.cs`.
* Implementer `MailKitEmailSender.cs` med SMTP-tilkobling mot Mailpit (`1025`).
* Opprett HTML-maler i `Templates/` og sett *"Copy to Output Directory"* til `CopyIfNewer`.


* [ ] **4. MassTransit Consumers & DI Host (`Recipe.Notification.Service`)**
* Bygg `UserRegisteredConsumer.cs`, `PasswordResetConsumer.cs` og `ContactFormConsumer.cs`.
* Sett opp MassTransit med RabbitMQ i `Program.cs`.
* Verifiser at logger sendes til Seq (`http://localhost:5341`) og e-poster dukker opp i Mailpit UI (`http://localhost:8025`).