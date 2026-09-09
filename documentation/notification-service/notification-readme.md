# 📧 Recipe Notification Service

**Recipe Notification Service** er en spesialisert mikrotjeneste i Kjøkkenhylla-plattformen. Tjenesten har ansvar for å prosessere, rendre og levere e-postnotifikasjoner asynkront basert på hendelser fra meldingsbussen (RabbitMQ), samt håndtere feilsituasjoner og administrasjon av uleverte meldinger via MongoDB.

---

## 🏛️ Arkitektur og Nøkkelkonsepter

* **Asynkron meldingsbehandling:** Integrert med MassTransit over RabbitMQ.
* **Malmotor:** Scriban HTML-maler strukturert under domenespesifikke mapper (`UserActions`, `SystemActions`, `AdminActions`).
* **Resiliens & Feilhåndtering:**
  * **Fail-Fast:** Malkompilerings- og syntaksfeil kaster `TemplateRenderException` og avbrytes umiddelbart uten gjenforsøk.
  * **In-line Retry Strategy:** Transient feil mot SMTP prøves på nytt opptil 5 ganger før meldingen paktles og lagres i MongoDB.
  * **Hard Bounce Detection:** Ved permanent avviste adresser (f.eks. `550 User unknown`) avbrytes videre forsøk, og `InvalidEmailDetectedEvent` publiseres til Auth API.
* **Tilstandsstyring & Admin-varsling:**
  * Singleton `NotificationStateStore` sporer om det finnes ubehandlede e-poster og sikrer avduplisert e-postvarsel til administrator.
  * Egen oppstartsjobb (`StateStoreInitializerHostedService`) sjekker MongoDB ved applikasjonsstart og setter tilstand dersom uleverte meldinger gjenstår.

---

## 📂 Prosjektstruktur

```text
recipe-notification-service/
├── Contracts/                 # Shared contracts (Events, Commands, Queries)
├── Documentation/             # Modulær arkitektur- og testdokumentasjon
├── Infrastructure/
│   ├── EmailDelivery/         # SMTP-utsending og PendingEmailService (Retry/DLQ)
│   ├── Exceptions/            # Domeneunntak (TemplateRenderException, etc.)
│   ├── Processors/            # Forretningslogikk for e-postbehandling
│   ├── State/                 # NotificationStateStore og oppstartsinitialisering
│   └── TemplateService/       # Scriban HTML-maler og rendering
├── Persistence/               # MongoDB settings, entiteter og repository
├── Service/                   # Worker-vert, MassTransit Consumers og DI Extensions
└── Tests/                     # xUnit, NSubstitute, Shouldly & MassTransit TestHarness

```

---

## 📑 Støttede Hendelser & Funksjonalitet

### 👤 User Actions

* Brukerregistrering & Velkomst-e-post
* Registrering via Google
* Utsending og re-utsending av e-postbekreftelse
* Tilbakestilling og endring av passord (sikkerhetsvarsel)
* Innsending av kontaktskjema (kopi til bruker + admin-notifikasjon)
* Brukerinitiert kontosletting

### ⚙️ System Actions (Tidsstyrte jobber fra Auth API)

* 7-dagers påminnelse om ubekreftet e-postadresse
* 14-dagers sperrevarsel pga. manglende bekreftelse
* 6-måneders inaktivitetsvarsel ("Vi savner deg")
* 1-års inaktivitetsdeaktivering og sperrevarsel
* Automatisk systemstyrt kontosletting (e-postutsendelse)

### 🛡️ Admin Actions

* Manuell e-postbekreftelse fra administrator
* Konto sperret / gjenåpnet av administrator
* Konto slettet eller svartelistet av administrator
* Profiloppdateringer utført av administrator
* Skreddersydde e-postmeldinger sendt fra admin-panelet

### 🛠️ Notification Management (Core API / Admin-panel)

* `GetFailedNotificationsQuery` — Hent uleverte e-poster fra MongoDB.
* `RetryFailedNotificationCommand` — Re-prosesser valgte feilede e-poster på nytt.
* `DeleteFailedNotificationCommand` — Slett uleverte e-poster fra bufferen.

---

## 🗺️ Roadmap & Kompakt Sjekkliste

* [x] **Fase 1: Tilstandsstyring & Resiliens** (`NotificationStateStore`, `PendingEmailService`, oppstartsjobb).
* [x] **Fase 2: Management Kontrakter & Consumers** (MongoDB request-response og admin-kommandoer).
* [x] **Fase 3: Refaktorering av Prosessorer** (Migrert alle `UserActions`, `SystemActions` og `AdminActions` til `IPendingEmailService`).
* [ ] **Fase 4: Testing (`Tests/`)**
* [ ] Enhetstester for prosessorer (`NSubstitute`, `Shouldly`).
* [ ] Enhetstester for infrastruktur og resiliens (`PendingEmailService`, `NotificationStateStore`).
* [ ] Integrasjonstester for HTML-maler (`TemplateRenderService` mot Scriban).
* [ ] Komponenttester for Consumers (`MassTransit.TestHarness`).


* [ ] **Fase 5: Optimalisering av Maler & Ressurser**
* [ ] Erstatte inlinede SVG-ikoner i HTML-malene med eksterne bildelenker (URL-ressurser fra sentralt CDN/hosting) for bedre vedlikeholdbarhet og mindre malstørrelse.


* [ ] **Fase 6: Verifikasjon & Opprydding**
* [ ] Kjøre alle xUnit-tester og verifisere at alt kjører grønt.
* [ ] Teste lokal e-postmottak i Mailpit (`http://localhost:8025`).