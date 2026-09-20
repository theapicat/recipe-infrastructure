# Hva testene gjør (lesebok)

Denne filen forklarer hva hver eneste test i `api-tests/` gjør, hva den forventer og hvorfor. Den er ment å leses fra
topp til bunn. Oppsett, kjøring og sikkerhet står i [`README.md`](README.md). Sist gjennomgått mot koden 2026-09-20. Testene dekker bare endepunkter som finnes og skal virke; kjente feil og planlagte funksjoner testes ikke.

**Tall:** 59 testfunksjoner blir til **293 testtilfeller**, fordi mange kjøres én gang per endepunkt, katalog eller rolle
(«parametrisering»). Tabellene under viser funksjonene, og antall tilfeller står i overskriften.

| Fil | Funksjoner | Tilfeller |
| --- | ---: | ---: |
| `test_gateway.py` | 10 | 13 |
| `test_auth_token.py` | 7 | 7 |
| `test_auth_public.py` | 7 | 19 |
| `test_auth_account.py` | 14 | 14 |
| `test_auth_admin.py` | 13 | 39 |
| `test_core_public.py` | 2 | 3 |
| `test_core_catalog_access.py` | 1 | 162 |
| `test_core_catalog_crud.py` | 5 | 36 |

---

## 1. Slik tenker testene

**Alt går utenfra, som en ekte klient.** Testene sender vanlige HTTP-kall (`requests`) til gatewayen på `localhost:5000`
(eller rett til Auth/Core med `--direct`). De importerer ingen kode fra tjenestene, og kjenner bare
kontrakten: URL, metode, statuskode og JSON. Derfor kan de brukes mot et hvilket som helst miljø som oppfører seg likt.

**Tre roller.**

| Rolle | Hvem | Hva den kan |
| --- | --- | --- |
| `anon` | ingen innlogging | bare offentlige ruter |
| `user` | en vanlig bruker testene selv registrerer | `/api/user/**` og egne kontoendepunkter |
| `admin` | den seedede administratoren (`admin@kjoekkenhylla.local`) | alt, inkludert `/api/admin/**` og `/api/auth/admin/*` |

**Statuskodene testene forventer.** `200` OK, `204` OK uten kropp (sletting), `302` redirect, `400` ugyldig forespørsel,
`401` ikke innlogget (mangler eller ugyldig token), `403` innlogget, men feil rolle, `404` finnes ikke, `405` metoden finnes
ikke på ruten. `5xx` er alltid en feil hos tjenesten.

**DTO-er (modeller) er strenge.** Når en test sier «svaret valideres mot `UserProfile`», betyr det at hvert felt i JSON
må finnes med riktig type, og at det ikke kan finnes felt DTO-en ikke kjenner. Endres et svar i en tjeneste, feiler
testen til DTO-en i `apitests/models/` er oppdatert. Slik oppdager du kontraktsendringer før webappen gjør det.

**Testdata og opprydding.** Alt testene oppretter heter `apitest-<kjøre-ID>-<navn>` (brukere: `…@example.com`).
Hver opprettet ting registreres for sletting umiddelbart, og etter kjøringen kontrolleres det at ingenting er igjen.
Rester fra en avbrutt kjøring fjernes ved neste oppstart.

**E-post.** Testene sjekker ikke selv at e-post kommer fram. De skriver en avkrysningsliste
(`reports/email-checklist-*.md`) som du kontrollerer manuelt i Mailpit. I tabellene under står ✉️ ved tester som utløser
e-post, og hva slags e-post.

**Hvem kan kjøre hva.** Tester merket 🔒 endrer data (oppretter brukere/rader), og tester merket ✉️ utløser e-post. Begge
typer hoppes over med mindre `API_TEST_ENV` er `local` (standard) eller `test`. `--read-only` kjører bare resten.

---

## 2. Hva som skjer i en kjøring

1. **Forhåndssjekk** (`stack`): gateway, Auth og Core må svare på helsesjekkene. Ellers avbrytes alt med en tydelig melding.
2. **Miljøvern:** i `local` må alle URL-er være localhost.
3. **Opprydding ved start:** rester med `apitest-` fra en tidligere avbrutt kjøring slettes, og det står i sluttrapporten.
4. **Innlogging som admin** (én gang, gjenbrukes av alle tester).
5. **Testene kjører.** Brukere opprettes ved behov (registrering, admin-bekreftelse, innlogging).
6. **Opprydding til slutt:** registrerte slettinger kjøres bakover (barn før foreldre), så kontrolleres det at ingenting
   med `apitest-` er igjen. Rester feies bort, og kjøringen feiler med en tydelig melding.
7. **E-postsjekklisten skrives** til `reports/`.

Hjelpefunksjoner testene bruker, definert i `conftest.py`:

| Navn | Hva det gir testen |
| --- | --- |
| `anon`, `admin` | rollene (én klient per tjeneste hver) |
| `user` | én delt vanlig bruker for rene lese-/tilgangstester. Tester som endrer brukeren lager sin egen |
| `user_factory("navn")` | en fersk, bekreftet, innlogget bruker (registrert via API-et, e-post bekreftet via admin) |
| `track_user`, `cleanup` | registrerer ting for sletting |
| `checklist` | e-postsjekklisten |
| `core_ready` | hopper over Core-tester hvis Core avviser tokenet (unngår hundrevis av følgefeil; selve feilen rapporteres av en egen test) |
| `core_admin_ready` | hopper over Core-skrivetester hvis admin blokkeres på `/api/admin/**` |
| `create_row` | oppretter en katalograd i Core og registrerer den for sletting |

---

## 3. `test_gateway.py`: gatewayen (13 tilfeller)

Tester at inngangsdøra oppfører seg riktig, uavhengig av hvilken tjeneste bak den.

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_gateway_health` | `GET /api/gateway/health` uten innlogging | 200, `HealthResponse`, `status = Healthy`, `service = recipe-gateway-api` |
| `test_core_health_is_public` | `GET /api/public/health` | 200, `service = recipe-core-api` |
| `test_auth_health_is_public` | `GET /api/auth/health` | 200, `status = Healthy` |
| `test_unknown_route_is_404` | kaller en sti som ikke finnes | 404 |
| `test_protected_gateway_routes_reject_anonymous` (×3) | anonym mot `/api/user/units`, `/api/admin/units`, `/hubs/anything` | 401 på alle |
| `test_spoofed_identity_headers_do_not_authenticate` (×2) | anonym med falske `X-User-Id` og `X-User-Roles: admin,Admin` mot `/api/user/units` og `/api/admin/units` | 401: klienten kan ikke selv erklære seg som admin |
| `test_user_cannot_escalate_with_spoofed_role_header` 🔒 | vanlig bruker med falsk `X-User-Roles: admin,Admin` mot `/api/admin/units` | 401 eller 403 |
| `test_cors_allows_the_frontend_origin` | forhåndsforespørsel (`OPTIONS`) med `Origin: http://localhost:3000` | svaret tillater akkurat den opprinnelsen, med credentials |
| `test_cors_does_not_allow_other_origins` | `OPTIONS` med `Origin: http://evil.example` | ingen `Access-Control-Allow-Origin` |
| `test_issued_token_is_accepted_by_gateway_and_core` | tokenet admin fikk fra `/connect/token` brukes mot `GET /api/user/unit-types` | 200. Kontrakten mellom Auth og resten (issuer, audience, nøkkel må være identiske). Feiler med tokenets issuer i meldingen |

---

## 4. `test_auth_token.py`: innlogging og tokens (7 tilfeller)

OAuth2 mot `POST /api/auth/connect/token` og `/connect/revoke`. Kroppen sendes som skjema (`application/x-www-form-urlencoded`).

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_admin_login_issues_a_token_pair` | logger inn som admin | `TokenResponse` (`Bearer`, `expires_in > 0`). Tokenets claims: riktig e-post, **`role = admin` (små bokstaver)**, `aud = recipe-frontend`, `client_id = recipe-web-app` |
| `test_wrong_password_is_rejected` | riktig bruker, feil passord | 400, `invalid_grant` |
| `test_unknown_user_gets_the_same_error_as_wrong_password` | ukjent bruker vs. feil passord | begge gir **samme** feil og beskrivelse, så ingen kan finne ut hvilke adresser som finnes |
| `test_unsupported_grant_type_is_rejected` | `grant_type=client_credentials` | 400, `unsupported_grant_type` |
| `test_token_endpoint_requires_form_encoding` | sender JSON i stedet for skjema | 400 eller 415 |
| `test_refresh_token_grant_and_revocation` 🔒 | ny bruker: bytter refresh token mot nye tokens, **inndrar** det nye refresh tokenet, prøver å bruke det igjen | nye tokens for riktig bruker, revokering gir 200, gjenbruk gir 400 `invalid_grant` |
| `test_login_accepts_the_right_password_and_rejects_a_wrong_one` 🔒 | ny bruker: riktig og feil passord | token, og 400 for feil |

---

## 5. `test_auth_public.py`: anonym tilgang til Auth (19 tilfeller, endrer ingenting)

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_account_endpoints_reject_anonymous` (×7) | alle kontoendepunkter som krever innlogging, uten token: `GET /me`, `PUT /profile`, `POST /change-password`, `POST /set-password`, `GET /complete-welcome`, `POST /resend-confirmation`, `DELETE /me` | 401 |
| `test_account_endpoints_reject_a_garbage_token` (×7) | samme sju med `Authorization: Bearer undefined` (det webappen sender uten sesjon) | 401 (ikke 500 eller 200) |
| `test_register_validation_errors_are_reported_per_field` | registrering med ugyldig e-post, passord `x`, tomme navn | 400, `ProblemDetails` med feil for akkurat `Email`, `Password`, `FirstName`, `LastName` |
| `test_register_rejects_a_password_that_breaks_the_rules` | passord `alltidsmatt` (mangler stor bokstav, tall, spesialtegn) | 400 med feil på `Password` |
| `test_recover_password_never_reveals_whether_the_email_exists` | glemt passord for en adresse som ikke finnes | 200 med generisk tekst («Dersom e-posten er registrert …»), og ingen e-post |
| `test_confirm_email_for_an_unknown_user_id_is_404` | bekreft e-post for en tilfeldig bruker-ID | 404 (ID-en er en GUID og kan ikke gjettes, så det avslører ingenting) |
| `test_google_login_redirects_to_google` | `GET /account/external-login?provider=Google` | 302 med `Location` som starter på `https://accounts.google.com/`. Selve Google-innloggingen kan ikke automatiseres |

---

## 6. `test_auth_account.py`: kontoflyten som innlogget bruker (14 tilfeller) 🔒 ✉️

Hver test lager sin egen bruker (registrert via API-et, bekreftet av admin) og sletter den til slutt.

| Test | Hva den gjør | Forventer | ✉️ E-post |
| --- | --- | --- | --- |
| `test_register_creates_an_unconfirmed_user` | registrerer «Kari Nordmann» | 200, `UserProfile`: e-post = brukernavn, riktige navn, `role = user`, har passord, ikke Google, **ikke bekreftet**, velkomst ikke fullført, ikke sperret | velkomst + bekreftelse |
| `test_register_rejects_a_duplicate_email` | registrerer samme adresse to ganger | 400, «E-postadressen er allerede i bruk.» | |
| `test_unconfirmed_user_can_log_in_but_is_flagged` | bruker uten bekreftet e-post logger inn og henter `/me` | 200 og `isEmailConfirmed = false`. Bevisst: 14 dagers frist | |
| `test_resend_confirmation_only_for_unconfirmed_users` | ubekreftet bruker ber om ny bekreftelse; admin bekrefter; prøver igjen | første 200, etterpå 400 «allerede bekreftet» | ny bekreftelseslenke, «manuelt bekreftet» |
| `test_me_returns_the_logged_in_users_profile` | `GET /me` som delt bruker | `UserProfile` med riktig ID, e-post, `role = user`, bekreftet | |
| `test_update_profile` | `PUT /profile` med nytt navn | 200 med nytt navn, og `/me` viser det samme | |
| `test_update_profile_requires_both_names` | tomme fornavn og etternavn | 400 med feil på `FirstName` og `LastName` | |
| `test_complete_welcome_marks_the_wizard_as_done` | `welcomeCompleted` er først false, så kalles `GET /complete-welcome` | blir true | |
| `test_change_password_flow` | feil nåværende passord, for svakt nytt passord, riktig endring | 400 `PasswordMismatch`; 400 valideringsfeil; 200 «Passord ble endret». Deretter virker nytt passord og gammelt gir `invalid_grant` | passord endret |
| `test_set_password_is_rejected_when_a_password_exists` | `POST /set-password` på en bruker som har passord | 400 «allerede et passord» | |
| `test_recover_password_for_an_existing_user_gives_the_same_answer` | glemt passord for kjent og ukjent adresse | **identisk** svartekst (ingen brukeropplisting) | tilbakestillingslenke (kun kjent adresse) |
| `test_reset_password_with_an_invalid_token_is_rejected` | tilbakestill passord med ugyldig token | 400, første feilkode `InvalidToken` | |
| `test_confirm_email_with_an_invalid_token_is_rejected` | bekreft e-post med ugyldig token | 400, `InvalidToken` | |
| `test_user_can_delete_own_account` | `DELETE /me` | 200 «slettet». Innlogging feiler etterpå, og admin ser brukeren som 404 | konto slettet av bruker |

> Ikke testet (krever lenke fra e-post): den *vellykkede* varianten av `confirm-email` og `reset-password`. Brukere bekreftes i stedet via admin-endepunktet.

---

## 7. `test_auth_admin.py`: admin i Auth API (39 tilfeller) 🔒 ✉️

**Tilgangsmatrisen** kjører de samme 14 admin-endepunktene mot to roller:

`GET /users`, `GET /users/{id}`, `PUT /users`, `POST /users/lock`, `/unlock`, `/confirm-email`, `/resend-confirmation`,
`/reset-password-request`, `/delete`, `/delete-and-blacklist`, `GET /blacklist`, `POST /blacklist`,
`DELETE /blacklist/{id}` og `POST /send-email` (alle under `/api/auth/admin`).

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_admin_endpoints_reject_anonymous` (×14) | hvert endepunkt uten innlogging | 401 |
| `test_admin_endpoints_reject_a_normal_user` (×14) | hvert endepunkt som vanlig bruker | 403 |

Deretter selve funksjonaliteten som admin:

| Test | Hva den gjør | Forventer | ✉️ E-post |
| --- | --- | --- | --- |
| `test_list_users_matches_the_dto_for_every_user` | `GET /users` | listen valideres strengt mot `AdminUserListItem` **for hver eneste bruker** i systemet. Testbrukeren finnes (rolle `user`, bekreftet, ikke sperret), og den seedede admin har rolle `admin` | |
| `test_user_details` | `GET /users/{id}` | `AdminUserDetails`, riktig bruker, `lockoutReason = "None"` | |
| `test_unknown_user_is_404` | ukjent ID | 404 «ikke funnet» | |
| `test_admin_can_update_a_user` | `PUT /users` med nye navn | 200, og detaljene viser de nye navnene | profil oppdatert av admin |
| `test_lock_blocks_login_and_unlock_restores_it` | sperrer, prøver å logge inn, gjenåpner, logger inn | sperret gir 400 med «sperret»; etter gjenåpning virker innlogging | konto sperret, konto gjenåpnet |
| `test_admin_can_confirm_email_and_trigger_mails` | ubekreftet bruker: ny bekreftelse, manuell bekreftelse, ny bekreftelse igjen, tilbakestillingslenke | 200, 200, 400 «allerede bekreftet», 200. Detaljene viser bekreftet | 3 stk |
| `test_admin_can_send_a_custom_email` | `POST /send-email` med emne og melding | 200 | melding fra admin (emnet inneholder kjøre-ID) |
| `test_admin_can_delete_a_user` | `POST /users/delete` | 200. Brukeren gir 404, finnes ikke i listen, og kan ikke logge inn | konto slettet av admin |
| `test_delete_and_blacklist_blocks_re_registration` | slett og svartelist | 200. Adressen står i svartelisten som «eksakt e-post», og ny registrering gir 400 «ikke tillatt» | konto slettet og svartelistet |
| `test_blacklist_exact_email_and_domain` | legger til en eksakt adresse og et domene, registrerer mot begge, fjerner begge, registrerer på nytt | listen viser riktig type på hver. Begge blokkerer registrering (400). Etter fjerning virker registrering igjen | registrering (til slutt) |
| `test_blacklist_requires_a_pattern` | legger til med tomt mønster | 400 med feil på `Pattern` | |

---

## 8. `test_core_public.py`: Core sine offentlige endepunkter (3 tilfeller)

Kontaktskjemaet **må virke for brukere som ikke er innlogget**. Testene kjører via gatewayen.

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_contact_form_works_for_users_who_are_not_signed_in` (×2) | `POST /api/public/contact-form` uten `Authorization`, og med `Bearer undefined` (det webappen sender uten sesjon) | 200 med en bekreftelsestekst. Ingenting i flyten krever en bruker |
| `test_contact_form_also_works_for_signed_in_users` 🔒 | samme kall som innlogget bruker | 200 |

**E-post:** kontaktskjema-e-postene (til administrator og kvittering til avsender) er ikke med i sjekklisten. I dag leveres de ikke
(eventet publiseres med et annet namespace enn notification-service lytter på; se `todos/consistency-audit.md`). Testene endrer
ingenting ved det, og kontaktskjema-koden er ikke rørt.

---

## 9. Katalogene i Core (198 tilfeller)

Core har seks kataloger som admin styrer: `units`, `unit-types`, `allergens`, `ingredient-categories`, `search-keywords`,
`recipe-categories`. Hver har lese-ruter under `/api/user/…` (alle innloggede) og full CRUD under `/api/admin/…` (kun admin).
De er beskrevet i én liste (`apitests/catalogs.py`), og både matrisen og livssyklustestene går gjennom hele listen automatisk.
Legges det til en ny katalog der, dekkes den uten ny testkode.

### 9.1 `test_core_catalog_access.py`: tilgangsmatrisen (162 tilfeller) 🔒

Én funksjon, `test_catalog_access_matrix`, kjørt for 27 kombinasjoner av (endepunkt, rolle) per katalog. Ingen data opprettes:
tilfellene er enten lesing, eller skriving som skal nektes. Forventet statuskode per rolle:

| Kall | anon | user | admin |
| --- | :---: | :---: | :---: |
| `GET /api/user/{katalog}` | 401 | 200 | 200 |
| `GET /api/user/{katalog}/{id}` (ukjent id) | 401 | 404 | 404 |
| `GET /api/admin/{katalog}` | 401 | 403 | 200 |
| `GET /api/admin/{katalog}/{id}` (ukjent id) | 401 | 403 | 404 |
| `POST`, `PUT` på `/api/admin/{katalog}` | 401 | 403 | (dekkes av 9.2) |
| `DELETE /api/admin/{katalog}/{id}` | 401 | 403 | (dekkes av 9.2) |
| `POST`, `PUT`, `DELETE` på `/api/user/{katalog}` | 401 eller 405 | 405 | 405 |

Å skrive på brukerrutene skal aldri gå, heller ikke for admin (metoden finnes ikke, derfor 405). Rett mot Core svarer anonym
405 i stedet for 401 (rutingen avviser ukjent metode før innloggingen sjekkes), og begge godtas siden begge betyr «nektet».

### 9.2 `test_core_catalog_crud.py`: livssyklus og feilhåndtering (36 tilfeller) 🔒

Testene lager egne rader (`apitest-…`) via admin-ruten, og sletter dem igjen selv om testen feiler. Rader som peker på andre
(`units` peker på `unit-types`) får en ny forelder opprettet først, og slettes før forelderen.

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_full_lifecycle` (×6, én per katalog) | 1) oppretter en rad. 2) leser den på admin- **og** brukerruten. 3) ser den i begge listene. 4) endrer den med `PUT`. 5) leser den igjen (også fra brukerlisten). 6) sletter den. 7) sjekker at den er borte overalt. 8) sletter en gang til | opprett 200; lesing gir raden **identisk** med det som ble sendt, validert mot DTO; listene viser endringene umiddelbart (cachen ugyldiggjøres); sletting 204; deretter 404; sletting av en rad som ikke finnes gir også 204 (idempotent) |
| `test_every_existing_row_matches_the_dto` (×12: 6 kataloger × brukerrute og adminrute) | leser hele katalogen | 200, og **hver** eksisterende rad matcher DTO-en strengt (ingen rader er da nødvendig; listen kan være tom) |
| `test_create_without_required_fields_is_rejected` (×6) | `POST` med bare en `id` | 400 `ProblemDetails` med feil |
| `test_malformed_id_is_not_found` (×6) | `GET /…/ikke-en-guid` | 404 |
| `test_unknown_id_is_404_and_delete_is_idempotent` (×6) | `GET` og `DELETE` av en ID som ikke finnes | 404, og 204 |

---

## 10. Slik leser du et resultat

```text
293 passed in 5.6s
```

* **passed**: testen oppfylte forventningen.
* **failed**: en ny feil. Meldingen viser forespørselen, statuskoden og starten av svaret. Kjør på nytt med `--direct` for å avgjøre om
  feilen ligger i gatewayen eller i tjenesten, og med `-k <navn> -x` for å følge én test.
* **skipped**: testen kunne ikke kjøre (`-rs` viser hvorfor, for eksempel `--read-only` eller at Core avviser tokenet).
* **OPPRYDDING**: noe med `apitest-` ble ikke ryddet av testen selv. Det er feid bort, men testen som lekket bør sjekkes.
