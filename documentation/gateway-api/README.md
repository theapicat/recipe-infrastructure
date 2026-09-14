# Dokumentasjon

Denne mappen beskriver, sett fra gateway-ens ståsted, hvordan hver tjeneste i **Kjøkkenhylla**-økosystemet forholder seg til `recipe-gateway-api`: hvilke ruter/endepunkter som er tilgjengelige gjennom gatewayen, hvilke sikkerhetsbetingelser som gjelder, og eventuelle konfigurasjonsverdier som må holdes i sync mellom tjenestene.

Viktig premiss for all dokumentasjonen under: **gatewayen transformerer aldri stien** til en forespørsel. Hele den innkommende stien (inkludert prefiks som `/api/auth`) videresendes uendret til mål-clusteret — se `README.md` i prosjektroten.

## Tjenester

| Fil | Tjeneste | Nås via gateway? |
| --- | --- | --- |
| [`auth-api.md`](./auth-api.md) | `recipe-auth-api` | Ja — `/api/auth/{**catch-all}` |
| [`core-api.md`](./core-api.md) | `recipe-core-api` | Ja — `/api/public`, `/api/user`, `/api/admin`, `/hubs` |
| [`system-api.md`](./system-api.md) | `system-api` (planlagt, ikke bygget) | Ja (planlagt) — `/api/system/{**catch-all}` |

Denne dokumentasjonen beskriver tilstanden i de respektive tjenestene per **2026-09-13**. Sjekk alltid mot faktisk kode i det aktuelle repoet ved tvil — tjenestene kan ha endret seg siden.
