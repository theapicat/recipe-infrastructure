# `system-api` (planlagt — ikke bygget)

Et separat, planlagt prosjekt. Ikke påbegynt per 2026-09-13. Dokumentert her på forhånd fordi gateway-ruten allerede er reservert og klar til bruk den dagen prosjektet finnes.

## Formål

Mer enn bare helse/oppetid — tenkt som en administrativ oversikts- og styringsflate på tvers av økosystemet. Eksempel på planlagt funksjon: se og manuelt sende på nytt e-poster som `recipe-notification-service` har feilet å sende (se [`notification-service.md`](./notification-service.md) — mekanismen for dette, `FailedNotification`/`RetryFailedNotificationCommand`, finnes allerede der og kan gjenbrukes over RabbitMQ).

## Gateway-ruten (allerede konfigurert)

| Rute | Cluster | Sikkerhetspolicy |
| --- | --- | --- |
| `/api/system/{**catch-all}` | `system-cluster` | `AdminUser` |

Standardadresser satt opp i gatewayens config, klare til å pekes om når tjenesten finnes:

- Docker/produksjonslignende (`appsettings.json`, `docker-compose.yml`): `http://recipe-system-api:80`
- Lokal dev (`appsettings.Development.json`): `http://localhost:5003`

Som alltid: gatewayen vil videresende hele stien uendret (`/api/system/...` inn = `/api/system/...` ut) — `system-api` må selv mappe sine controllere til `api/system/...`, på samme måte som `recipe-auth-api` gjør for `api/auth/...`.

## Kommunikasjon med resten av økosystemet

`system-api` er tenkt å snakke med de andre tjenestene **internt via MassTransit/RabbitMQ**, ikke via gatewayen — gatewayen er kun inngangsdøren for eksterne klienter (frontend/admin-brukere) inn til `system-api` selv. Eksempel: for å hente/sende på nytt feilede notifikasjoner, sender `system-api` en `GetFailedNotificationsQuery`/`RetryFailedNotificationCommand` over bussen til `recipe-notification-service`, slik `recipe-notification-service` allerede støtter.

## Åpne spørsmål til når prosjektet startes

- Skal `system-api` validere JWT selv (som `recipe-auth-api`), eller stole på gatewayens injiserte `X-User-Id`/`X-User-Roles`-headere (som allerede injiseres for `AdminUser`-policyen)?
- Skal helse-/statusdelen aggregere status fra de andre tjenestene (som selv må eksponere noe å spørre), eller kun rapportere `system-api` sin egen tilstand?
