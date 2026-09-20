# 🧪 API-tester (integrasjonstester mot endepunktene)

Uavhengig, ekstern test av **endepunktene** i Kjøkkenhylla, uten Postman/Insomnia: pytest + `requests` + strenge
DTO-er (pydantic). Testene logger inn som **anonym**, **vanlig bruker** og **administrator** og sjekker at hver rolle
får riktig svar (riktig modell, eller nektet tilgang), at data kan opprettes, leses, endres og slettes, og at alt
ryddes bort igjen.

Dette er ikke enhetstester. Forretningslogikken testes av xUnit inne i hver tjeneste. Denne suiten tester det som
bare kan testes utenfra, med hele stacken oppe: gateway-policyer, JWT mellom tjenestene, statuskoder, DTO-formene
og kontraktene mellom webapp og backend. Går det her lokalt, skal det gå på nett; feiler det bare på nett, ligger
feilen i konfigurasjonen rundt, ikke i endepunktene. Testene dekker kun endepunkter som finnes og skal virke.

> **Vil du lese hva hver test gjør?** Se [`TESTS.md`](TESTS.md): alle testene forklart, med forventet resultat og hvilke e-poster de utløser.

## Kjøre

Krever at alt kjører: `docker compose up -d` og `./dev-scripts/start-project.sh` (gateway, auth-api, core-api og
gjerne notification-service, som sender e-postene).

Inngangspunktet er **`api-tests/run.sh`** (kan kjøres fra hvor som helst). `./dev-scripts/run-api-tests.sh` er bare en
snarvei til det samme.

```bash
./run.sh                # alle tester, via gatewayen (:5000)
./run.sh --direct       # rett mot Auth (:5001) og Core (:5002), uten om gatewayen
./run.sh --read-only    # kun lesetester: ingen data, ingen e-post
./run.sh -k admin -x    # alt annet sendes til pytest (-k filter, -x stopp ved første feil)
```

Første kjøring lager `api-tests/.venv` og installerer avhengigheter. Kjøringen tar noen sekunder. Testene kjører bevisst
sekvensielt (ikke parallelt): hele suiten tar ca. 5 sekunder, og parallellkjøring ville krevd mer komplisert delt tilstand
og opprydding uten å spare noe nevneverdig.

**Tips:** kjør både med og uten `--direct` når noe feiler. Feiler det bare via gatewayen, ligger feilen i gatewayen
(policy, JWT, ruting); feiler det begge steder, ligger den i tjenesten.

## Sikkerhet: hva som kan skje, og når

| `API_TEST_ENV` | Effekt |
| --- | --- |
| `local` (standard) | Alt kjøres. Alle URL-er MÅ peke på localhost, ellers avbrytes kjøringen. |
| `test` | Alt kjøres mot et dedikert testmiljø (URL-ene kan være andre enn localhost). |
| noe annet (`--read-only` bruker `readonly`) | KUN lesetester. Alt som oppretter/endrer/sletter data eller utløser e-post (`@pytest.mark.mutating` / `@pytest.mark.emails`) hoppes over. |

Alt testene oppretter har prefikset `apitest-` (brukere `apitest-<kjøring>-<tag>@example.com`, kataloger
`apitest-<kjøring>-<tag>`), så opprydding aldri kan treffe ekte data. `example.com` er et reservert domene, og Mailpit
fanger uansett all e-post i dev.

**Opprydding:** hver opprettet ting registreres for sletting (også når en test feiler). Etter kjøringen kontrolleres
det at ingenting med `apitest-` er igjen; rester feies bort og kjøringen feiler med en tydelig melding. Rester fra en
tidligere avbrutt kjøring fjernes ved oppstart, med et notat.

## E-postsjekkliste (manuell kontroll)

Testene verifiserer ikke e-postlevering selv. I stedet skriver hver kjøring en avkrysningsliste til
`api-tests/reports/email-checklist-<tid>.md` over alle e-poster som SKAL ha kommet, med mottaker og hva som utløste
dem. Åpne Mailpit (<http://localhost:8025>), søk på kjøre-ID-en (står øverst i lista) og kryss av. Kontaktskjemaets e-poster er bevisst ikke med (de leveres ikke i dag, se `../todos/consistency-audit.md`).

## Hva som testes

| Fil | Innhold |
| --- | --- |
| `test_gateway.py` | Helsesjekker, anonym avvises på beskyttede ruter, spoofede `X-User-*`-headere, CORS, og at tokenet Auth utsteder godtas av gateway/Core |
| `test_auth_token.py` | OAuth2 password/refresh/revoke, feilscenarier, ingen brukeropplisting ved feil passord |
| `test_auth_public.py` | Anonyme flyter og at kontoendepunkter avviser anonym og søppel-token (`Bearer undefined`) |
| `test_auth_account.py` | Registrering, profil, passord, bekreftelse, sletting av egen konto |
| `test_auth_admin.py` | Tilgangsmatrise for alle 14 admin-endepunkter, brukeradministrasjon, sperring, svarteliste |
| `test_core_public.py` | Kontaktskjemaet **må virke for anonyme** (uten og med ugyldig token) |
| `test_core_catalog_access.py` | Tilgangsmatrise (anonym/bruker/admin × endepunkt) for alle seks kataloger |
| `test_core_catalog_crud.py` | Livssyklus (opprett, les, endre, slett) per katalog, cache-ugyldiggjøring, DTO-kontroll av alle rader, feilhåndtering |

Ikke automatisert (bevisst eller umulig): selve Google-innloggingen (testen sjekker bare at den starter og
redirecter til Google), lykkelige stier som krever en lenke/token fra e-post (`confirm-email`, `reset-password`; brukere
bekreftes i stedet via admin-endepunktet), SignalR, scraper-service (ikke bygget).

## DTO-ene er strenge

`apitests/models/` speiler de ekte responsene (`Domain/DTOs` i auth, entitetene i core). Modellene har
`extra="forbid"`: et felt API-et returnerer som DTO-en ikke kjenner, eller et påkrevd felt som mangler, gir testfeil.
Endrer du et endepunkts respons, oppdater DTO-en her i samme slengen. Listetestene validerer *alle* eksisterende rader
(f.eks. alle registrerte brukere), ikke bare de nyopprettede.

## Struktur

```text
api-tests/
├── run.sh                 # inngangspunktet: kjører testene (lager .venv første gang)
├── TESTS.md               # lesebok: hva hver test gjør
├── conftest.py            # fixtures (anon/user/admin), miljøvern, forhåndssjekk, opprydding, e-postliste
├── pytest.ini             # markører: mutating, emails
├── requirements.txt
├── .env.example           # valgfrie overstyringer (URL-er, admin-konto, miljø)
├── apitests/
│   ├── config.py          # innstillinger og miljøvern
│   ├── http.py            # ApiClient + expect()/parse() som validerer mot DTO-er
│   ├── actors.py          # roller og felles handlinger (login, register, admin_*)
│   ├── catalogs.py        # beskrivelse av de seks katalogene
│   ├── cleanup.py         # slette-register og sweep av `apitest-*`
│   ├── emails.py          # e-postsjekklisten
│   └── models/            # DTO-er (auth, core, felles)
├── tests/
└── reports/               # genererte sjekklister (ikke i git)
```

## Legge til tester for nye endepunkter

1. Lag/oppdater DTO-en i `apitests/models/`.
2. Nytt katalog-/CRUD-endepunkt i Core: legg det til i `CATALOGS` i `apitests/catalogs.py`; tilgangsmatrisen og
   livssyklustestene dekker det da automatisk.
3. Andre endepunkter: skriv en test som bruker `anon`, `user` eller `admin` (fixtures i `conftest.py`) og `expect(...)`.
   Merk den `@pytest.mark.mutating` hvis den endrer data, `@pytest.mark.emails` hvis den sender e-post.
4. Alt som opprettes skal ha prefikset `apitest-` (`settings.test_name(...)` / `settings.test_email(...)`) og
   registreres for opprydding (`cleanup.register(...)` / `track_user`). Sweepen er sikkerhetsnettet, ikke hovedplanen.
5. Sender testen e-post: `checklist.expect(mottaker, hva, utløser)`.

## Konfigurasjon

Alt har fornuftige standardverdier for lokal utvikling. Overstyr med miljøvariabler eller en `api-tests/.env` (se
`.env.example`). Admin-kontoen leses som standard fra `recipe-auth-api/API/appsettings*.json` (`AdminUser`), altså
samme konto `IdentitySeeder` oppretter.
