# Meldingsarkitektur og Hendelseshåndtering i `recipe-auth-api`


## 1. Oversikt og Meldingsarkitektur

`recipe-auth-api` benytter en asynkron, hendelsesdrevet arkitektur (Event-Driven Architecture) bygget på **MassTransit** over **RabbitMQ**. Dette sikrer lav kobling (loose coupling) og høy resiliens mellom autentiseringstjenesten, e-posttjenesten (`recipe-notification-service`) og domenetjenester som `recipe-core-api`.

### Rolle i Økosystemet

* **Event Publisher (Utgående):** Publisere tilstandsendringer i brukerkontoer, sikkerhetshendelser og administrative inngrep til meldingsbussen.
* **Event Consumer (Inngående):** Lytte på tilbakemeldinger og reaksjoner fra andre tjenester (f.eks. uleverbare e-postmeldinger).

Topologyen konfigureres automatisk via `ConfigureEndpoints` i MassTransit, hvor vert, port, virtuell vert og autentisering styres via `RabbitMqOptions`.

---

## 2. Inngående Hendelser og Konsumenter (Inbound)

For å opprettholde god datahygiene og beskytte plattformens e-postomdømme, reagerer `recipe-auth-api` på tilbakemeldinger fra e-postinfrastrukturen.

### `InvalidEmailDetectedConsumer`

Lytter på `InvalidEmailDetectedEvent` publisert fra `recipe-notification-service` dersom en e-postutsendelse avvises permanent (Hard Bounce / 550-feil).

```
[Notification Service] ──(Hard Bounce)──► InvalidEmailDetectedEvent
                                                    │
                                                    ▼
                                     [InvalidEmailDetectedConsumer]
                                                    │
             ┌──────────────────────────────────────┼──────────────────────────────────────┐
             ▼                                      ▼                                      ▼
1. Svartelisting (EF Core)              2. Token-inndragning (OpenIddict)      3. Kontosletting (Identity)
   Legger e-posten i                       Inndrar alle aktiverte                 Sletter brukeren permanent
   BlacklistedEntries                      Access- og Refresh-tokens              fra databasen

```

#### Arbeidsflyt og prosessering:

1. **Normalisering og Svartelisting:** E-postadressen vaskes (`trim` og `lowercase`). Sjekker om e-posten allerede er svartelistet. Hvis ikke, opprettes en `BlacklistedEntry` med svartelistetype `ExactEmail` og begrunnelse fra hendelsen. System-ID (`Guid.Empty`) settes som oppretter for å indikere en automatisk systemhandling.
2. **Brukeridentifisering:** Slår opp brukeren i Identity via `UserId` dersom denne finnes i meldingen, eller med oppslag på e-postadresse.
3. **Sikkerhets- og Token-inndragning:** Dersom brukeren eksisterer i systemet, hentes alle utstedte OpenIddict-tokens knyttet til brukerens identitet (`FindBySubjectAsync`) og revokeres fortløpende (`TryRevokeAsync`). Dette avskjærer umiddelbart alle aktive sesjoner og forhindrer videre token-fornyelse.
4. **Permanent sletting:** Brukeren slettes fra ASP.NET Core Identity via `UserManager.DeleteAsync`.

---

## 3. Utgående Hendelser og Kategorier (Outbound)

Kontraktene i `Contracts.Events` representerer domene-hendelser som publiseres til bussen. De er bevisst utformet som rene databærere uten forretningslogikk.

### 1. Brukerinitierte Hendelser (`UserActions`)

Utløses direkte av at en sluttbruker utfører en handling i applikasjonen:

* **Registrering og Konto:** `UserRegisteredEvent`, `UserRegisteredWithGoogleEvent`, `AccountDeletedByUserEvent`.
* **Sikkerhet og Profil:** `PasswordChangedEvent`, `PasswordResetRequestedEvent`, `ResendEmailConfirmationRequestedEvent`, `ContactFormSubmittedEvent`.

### 2. Administrative Hendelser (`AdminActions`)

Utløses når en administrator gjør manuelle endringer eller inngrep via `AdminController`:

* **Kontostatus:** `UserLockedByAdminEvent`, `UserUnlockedByAdminEvent`, `UserUpdatedByAdminEvent`.
* **Sletting og Svartelisting:** `UserAccountDeletedByAdminEvent`, `UserDeletedAndBlacklistedByAdminEvent`.
* **E-post og Overstyring:** `EmailManuallyConfirmedByAdminEvent`, `AdminCustomEmailRequestedEvent`.

### 3. Tidsstyrte Systemhendelser (`SystemActions`)

Utløses automatisk av `AccountLifecycleJob` i Auth API basert på passivitet eller manglende bekreftelse:

* **Ubekreftet e-post:** `Confirmation7DaysReminderEvent`, `Confirmation14DaysReminderEvent`.
* **Inaktivitet:** `Inactivity6MonthsWarningEvent`, `Inactivity1YearLockedEvent`.
* **Automatisk sletting:** `UserAccountDeletedBySystemEvent`.

---

## 4. Kaskadesletting og Resiliens i Økosystemet

Den hendelsesdrevne arkitekturen benyttes for å opprettholde personvern (GDPR) og datakonsistens uten direkte koblinger mellom mikrotjenestene.

```
                   ┌──► recipe-notification-service (Sender bekreftelses- e-post)
                   │
[UserAccountDeleted]──► recipe-core-api (Kaskadesletter oppskrifter, måltidsplaner og handlelister)
                   │
                   └──► recipe-analytics-service (Anonymiserer eller fjerner brukerspor)

```

### Kaskadesletting på tvers av mikrotjenester

Når en brukerkonto slettes i Auth API (uavhengig av om årsaken er brukerstyrt sletting, administrativ utestengelse, automatisk opprydding etter 30 dager eller uleverbar e-post), publiseres en slettehendelse til MassTransit.

Mottagende mikrotjenester som `recipe-core-api` lytter på disse hendelsene og utfører kaskadesletting av brukerens tilhørende domenedata (f.eks. eide oppskrifter, lagrede favoritter, måltidsplaner og handlelister) i sine egne databaser.

### Resiliens og Feilhåndtering

* **Feilkøer (Error Queues):** Meldinger som feiler under prosessering i en konsument (f.eks. ved midlertidig databasedriftstopp) flyttes automatisk til dedikerte `_error`-køer i RabbitMQ for inspeksjon og re-publisering.
* **Idempotens:** Konsumenter som `InvalidEmailDetectedConsumer` utformes idempotente – de sjekker eksisterende tilstand (f.eks. om e-posten allerede er svartelistet eller brukeren allerede er slettet) før endringer utføres, noe som forhindrer feil ved re-levering av meldinger.