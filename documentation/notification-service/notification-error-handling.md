# 🛡️ Arkitektur for Feilhåndtering og E-postbuffer (`Pending Notifications`)

Dette dokumentet beskriver systemets strategier for håndtering av e-postleveransefeil, ugyldige mottakeradresser, tilstandsovervåking i minnet og den transiente MongoDB-bufferen.

---

## 📐 Arkitektoniske Kjerneprinsipper

1. **Fail-Fast ved Kritiske Utviklingsfeil (`TemplateRenderException`):**
Dersom en Scriban-mal mangler på disk, har syntaksfeil eller mangler påkrevde modellvariabler, kastes `TemplateRenderException`. Prosessen avbrytes umiddelbart slik at meldinger i RabbitMQ stoppes og feilen logges kritisk i Seq.
2. **Deteksjon av Ugyldige E-postadresser (Hard Bounce):**
Dersom SMTP-serveren avviser sendingen med en permanent feilmelding (f.eks. `550 User unknown` / `Recipient address rejected`), avbrytes videre utsendingsforsøk umiddelbart etter **første forsøk**. Tjenesten publiserer et `InvalidEmailDetectedEvent` på meldingsbussen (MassTransit). Dette eventet fanges opp av `Auth API`, som kan iverksette tiltak som deaktivering, sperring eller tidsbegrenset karantene av kontoen.
3. **In-line Gjenforsøk ved Transient SMTP-feil (`EmailDeliveryException`):**
Dersom e-postadressen er gyldig, men utsendelsen feiler av transient årsaker (nettverksblink, SMTP-timeout, leverandørbrudd), gjennomfører systemet **5 in-line gjenforsøk** direkte i den gjeldende skopede prosessen.
4. **Transient MongoDB-buffer (Dead-Letter Queue):**
MongoDB benyttes **kun som en midlertidig buffer** for e-poster som har feilet 5 ganger in-line og krever manuell sjekk eller korrigering. Så fort en e-post blir levert vellykket, slettes dokumentet umiddelbart fra databasen.
5. **Sentrert Tilstandsbevaring og Avduplisert Admin-varsling:**
En Singleton-tjeneste i minnet overvåker om det finnes feilede e-poster i systemet. Administrator varsles per e-post **kun én gang** idet tilstanden går fra 0 til 1 feil, noe som forhindrer varsel-spam dersom mange e-poster feiler samtidig.
6. **100 % Meldingsbasert Admin-Grensesnitt:**
All kommunikasjon mellom `Core API` (admin-dashbordet i frontend) og `recipe-notification-service` går over MassTransit (Request-Response mønster).

---

## 🧩 Komponentoversikt

```text
[ Incoming MassTransit Event ]
              │
              ▼
    [ Domain Processor ] ──(Render fail)──► [ TemplateRenderException ] 🛑 (Fail-Fast)
              │
              ▼ (Render OK)
   [ PendingEmailService ] ──(Hard bounce)─► Publish [ InvalidEmailDetectedEvent ] ──► [ Auth API ]
              │
              ├─► In-line Retries (Opptil 5 forsøk over SMTP)
              │
              └─► (5/5 Feilet) ──► Save to MongoDB [ failed_notifications ]
                                              │
                                              ▼
                                 [ NotificationStateStore ]
                                              │
                               (Endring fra 0 til 1 feilet e-post?)
                                      ├── JA  ──► Send varsel til Admin 📧
                                      └── NEI ──► (Admin allerede varslet, ingen ny e-post)

```

### 1. `PendingEmailService` (Scoped Service)

* **Levetid:** Kjører innenfor meldingskonsumentens scope og opprettes kun ved behov.
* **Ansvar:**
* Utfører in-line gjenforsøk (opptil 5 ganger) mot `IEmailDeliveryService`.
* Gjenkjenner permanent avviste adresser og publiserer `InvalidEmailDetectedEvent`.
* Ved 5 mislykkede forsøk: Lagrer e-postinnholdet og feilmeldingen i MongoDB via `IFailedNotificationRepository`.
* Triggere statusoppdatering i `NotificationStateStore`.



### 2. `NotificationStateStore` (Singleton Service)

* **Levetid:** Singleton (lever gjennom hele applikasjonens levetid).
* **Ansvar:**
* Holder trådsikre, boolske flagg i minnet:
* `HasPendingNotifications` (`bool`): Angir om det ligger minst én ubehandlet e-post i MongoDB.
* `HasNotifiedAdmin` (`bool`): Forhindrer at admin mottar mer enn én varsling per feilperiode.


* Inneholder metoder for tilbakestilling når databasen tømmes.



### 3. `FailedNotificationRepository` (Persistence)

* **Levetid:** Singleton / Scoped Mongo Client.
* **Ansvar:**
* Tilbyr operasjoner for å legge til, hente, slette (enkel eller bulk) og nullstille gjenforsøkstellinger (`RetryCount = 0`) i MongoDB-samlingen `failed_notifications`.



---

## 🔄 Prosessflyt

### 1. Oppstartsvalidering (Startup State Initialization)

Når `recipe-notification-service` starter opp, kjøres en oppstartsjobb som teller antall eksisterende dokumenter i MongoDB:

* **`Count > 0`:** Set `HasPendingNotifications = true` i `NotificationStateStore`.
* **`Count == 0`:** Set `HasPendingNotifications = false` i `NotificationStateStore`.

### 2. Håndtering av Transient Feil (5 In-line Forsøk)

1. `PendingEmailService` prøver å sende e-posten.
2. Dersom utsendelsen kaster `EmailDeliveryException`, venter tjenesten et kort intervall før den prøver på nytt.
3. Dersom utsendelsen lykkes på forsøk 1–5, fullføres prosessen og meldingen godkjennes (ACK).
4. Dersom forsøk 5 feiler:
* E-posten lagres som et nytt dokument i MongoDB (`FailedNotification`).
* `PendingEmailService` sjekker `NotificationStateStore.HasNotifiedAdmin`.
* Hvis `false`: Flagget settes til `true`, og det sendes en varslingse-post til administrator om at e-postkøen krever ettersyn.
* Hvis `true`: Ingen admin-varsling sendes (admin er allerede informert om at feilkøen er aktiv).



### 3. Admin-Gjenoppretting og Opprydding via MassTransit

1. Administrator åpner oversikten over feilede e-poster i frontend.
2. `Core API` sender en `GetFailedNotificationsQuery` over MassTransit.
3. `recipe-notification-service` returnerer listen fra MongoDB.
4. Administrator utbedrer den underliggende feilen (f.eks. retter nettverk/SMTP-konfigurasjon) og velger enten **Slett** eller **Prøv på nytt** (enkeltvis eller som bulk):
* **Ved Sletting:** Core API sender `DeleteFailedNotificationCommand`. Dokumentet fjernes fra MongoDB.
* **Ved Re-send / Tilbakestilling:** Core API sender `RetryFailedNotificationCommand`. `PendingEmailService` kjøres på nytt for de valgte e-postene.


5. Når alle feilede e-poster er enten sendt eller slettet, og antall dokumenter i MongoDB når **0**:
* `NotificationStateStore` tilbakestiller flaggene (`HasPendingNotifications = false`, `HasNotifiedAdmin = false`).
* Systemet returnerer til normal grønn tilstand, klar til å gi nytt varsel dersom en framtidig feil skulle oppstå.



---

## 📜 Kontrakter (MassTransit Events & Commands)

* **`InvalidEmailDetectedEvent` (Event):**
* **Felt:** `Guid UserId`, `string Email`, `string Reason`, `DateTime DetectedAt`
* **Mottaker:** `Auth API` (for sperring/opprydding av brukerkonto).


* **`GetFailedNotificationsQuery` / `GetFailedNotificationsResponse` (Request-Response):**
* **Mottaker:** `recipe-notification-service` (Returnerer liste over dokumenter fra MongoDB).


* **`RetryFailedNotificationCommand` (Command):**
* **Felt:** `List<Guid> NotificationIds`
* **Mottaker:** `recipe-notification-service` (Trigger ny utsendelse via `PendingEmailService`).


* **`DeleteFailedNotificationCommand` (Command):**
* **Felt:** `List<Guid> NotificationIds`
* **Mottaker:** `recipe-notification-service` (Fjernet dokumenter fra MongoDB).