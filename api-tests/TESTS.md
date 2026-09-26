# Hva testene gjør (lesebok)

Denne filen forklarer hva hver eneste test i `api-tests/` gjør, hva den forventer og hvorfor. Den er ment å leses fra
topp til bunn. Oppsett, kjøring og sikkerhet står i [`README.md`](README.md). Sist gjennomgått mot koden 2026-09-26 (`recipe-core-api` sin `Domain/`/`Application/` og `Documentation/08-api-reference.md`, 71 endepunkter). Testene dekker bare endepunkter som finnes og skal virke; kjente feil og planlagte funksjoner testes ikke.

**Tall:** 177 testfunksjoner blir til **578 testtilfeller**, fordi mange kjøres én gang per endepunkt, katalog eller rolle
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
| `test_core_catalog_crud.py` | 18 | 93 |
| `test_core_nutrients.py` | 8 | 14 |
| `test_core_ingredients.py` | 34 | 67 |
| `test_core_unconfirmed_ingredients.py` | 28 | 53 |
| `test_core_recipes.py` | 23 | 82 |
| `test_core_recipe_nutrition.py` | 12 | 12 |

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

**Statuskodene testene forventer.** `200` OK, `201` opprettet (med `Location`), `204` OK uten kropp (sletting), `302` redirect, `400` ugyldig forespørsel,
`401` ikke innlogget (mangler eller ugyldig token), `403` innlogget, men feil rolle, `404` finnes ikke (også en annen brukers ressurs), `409` konflikt (navnet finnes, raden er i bruk, ugyldig referanse, feil status), `405` metoden finnes
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
3. **Opprydding ved start:** rester med `apitest-` fra en tidligere avbrutt kjøring slettes, og det står i sluttrapporten. Det
   gjelder også oppskrifter og ubekreftede ingredienser som tilhører gjenværende testbrukere (Core rydder dem når en konto
   slettes, men asynkront via RabbitMQ og bare når Core kjører, så sweepen logger inn som testbrukeren med det kjente
   testpassordet og sletter dem først).
4. **Innlogging som admin** (én gang, gjenbrukes av alle tester).
5. **Testene kjører.** Brukere opprettes ved behov (registrering, admin-bekreftelse, innlogging).
6. **Opprydding til slutt:** registrerte slettinger kjøres bakover (barn før foreldre). Slettinger som feiler prøves på nytt i
   opptil tre runder, for eksempel en ingrediens som ble brukt av en oppskrift som ryddes senere. Så kontrolleres det at
   ingenting med `apitest-` er igjen. Rester feies bort, og kjøringen feiler med en tydelig melding.
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
| `create_row` | oppretter en katalograd i Core (201, server-tildelt id) og registrerer den for sletting |
| `alice`, `bob` | to vanlige brukere for tester der én brukers data ikke skal være synlig for en annen |
| `fresh_user("navn")` | en ny bruker helt uten data (for «en bruker uten oppskrifter får en tom liste») |
| `ref` | seedede referanser (enheter `g`, `stk`, `dl`, `ss` …, enhetstypene slått opp på `dimension`, kategorier, næringsstoffer, én ekte ingrediens) som fremmednøkler |
| `make_ingredient` | oppretter en (ikke-offisiell, `isOfficial: false`) ingrediens som admin (100 kcal, to næringsstoffer, 1 stk = 50 g), sletter den etterpå |
| `make_unconfirmed(bruker)` | oppretter en ubekreftet ingrediens, og sletter den når testen er ferdig (grensene er per bruker) |
| `make_recipe(bruker)` | oppretter en oppskrift, og sletter den når testen er ferdig |
| `approve(rad)` | godkjenner en ventende ubekreftet ingrediens som admin (ny offisiell ingrediens) og rydder den |

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

**E-post:** hver innsending gir to e-poster, og begge står i sjekklisten: et varsel til administrator («[Kontaktskjema] <emne>», til
`SmtpSettings:AdminNotificationEmail`) og en kvittering til avsenderen («Takk for din henvendelse: <emne>»). De ble ikke levert før
Core rettet navnerommet på `ContactFormSubmittedEvent` 2026-09-24; bekreftet i Mailpit 2026-09-26.

---

## 9. Katalogene i Core (255 tilfeller)

Core har seks kataloger som admin styrer: `units`, `unit-types`, `allergens`, `ingredient-categories`, `search-keywords`,
`recipe-categories`. Hver har lese-ruter under `/api/user/…` (alle innloggede) og full CRUD under `/api/admin/…` (kun admin).
De er beskrevet i én liste (`apitests/catalogs.py`), og både matrisen og livssyklustestene går gjennom hele listen automatisk.
Legges det til en ny katalog der, dekkes den uten ny testkode. Alle radene har de serverstyrte feltene `isSystem` (seed-rad, kan ikke
slettes) og `usageCount` (antall rader som peker på den, regnes ved lesing). Enhetstyper har i tillegg `dimension`
(`Weight`/`Volume`/`Count`, påkrevd); navnet er bare en etikett, og beregningene bruker dimensjonen.

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

### 9.2 `test_core_catalog_crud.py`: livssyklus, serverregler og feilhåndtering (93 tilfeller) 🔒

Serveren tildeler alltid id-en (en `id` fra klienten ignoreres), og gjør navn om til små bokstaver. Testene lager egne rader
(`apitest-…`) via admin-ruten, og sletter dem igjen selv om testen feiler. Rader som peker på andre (`units` peker på
`unit-types`) får en ny forelder opprettet først, og slettes før forelderen. Enhetsforkortelsen er også unik og utledes derfor av navnet.
Testenes egne enhetstyper har dimensjonen `Weight`, slik at enhetene under dem kan ha et forholdstall ulikt 1.

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_full_lifecycle` (×6, én per katalog) | 1) oppretter en rad. 2) leser den på admin- **og** brukerruten. 3) ser den i begge listene. 4) endrer den med `PUT` (hele raden, `id` i body). 5) leser den igjen (også fra brukerlisten). 6) sletter den. 7) sjekker at den er borte overalt. 8) sletter en gang til | opprett **201** med `Location` og raden; lesing gir raden **identisk**, validert mot DTO; `PUT` gir **200 uten kropp**; listene viser endringene umiddelbart (cachen ugyldiggjøres); sletting 204; deretter 404; sletting av en rad som ikke finnes gir også 404 |
| `test_every_existing_row_matches_the_dto` (×12: 6 kataloger × brukerrute og adminrute) | leser hele katalogen | 200, og **hver** eksisterende rad matcher DTO-en strengt |
| `test_server_assigns_the_id_and_normalizes_the_name` (×6) | oppretter med en egen `id` og navnet `  APITEST-…-STOR   BOKSTAV  ` | raden får en annen id, og navnet er trimmet, med ett mellomrom og små bokstaver |
| `test_unit_abbreviation_keeps_its_case` | oppretter en enhet med forkortelsen `AtU-X` | forkortelsen beholder store/små bokstaver (symboler som `µg`, `mg-ATE`) |
| `test_is_system_and_usage_count_cannot_be_set_by_the_client` (×6) | sender `isSystem: true` og `usageCount: 99` på `POST` og `PUT` | 201-svaret og den lagrede raden har `false` og `0` |
| `test_an_existing_name_is_a_conflict` (×6) | oppretter samme navn en gang til (med store bokstaver) | 409 `ProblemDetails` |
| `test_a_catalog_row_in_use_cannot_be_deleted` | sletter en enhetstype som en enhet peker på, deretter enheten og enhetstypen | `usageCount = 1`; 409 «Brukes av 1 enheter og ingredienser og kan ikke slettes.»; så 204, `usageCount = 0` og 204 |
| `test_seed_rows_are_system_rows_and_cannot_be_deleted` (×6) | sletter en seedet rad (`isSystem: true`) som også er i bruk | 409 «Systemrader (fra seed-data) kan ikke slettes.», og raden finnes fortsatt. Bruker bevisst en rad i bruk, så bruks-sjekken stopper slettingen selv om systemsjekken skulle svikte. Hoppes over for kataloger uten seedede rader i bruk (i dag `search-keywords` og `recipe-categories`) |
| `test_every_seeded_unit_type_has_a_dimension` | leser de seedede enhetstypene | én hver av `Weight`, `Volume`, `Count` |
| `test_invalid_units_are_rejected_on_create_and_update` (×4) | enhet med tom forkortelse, forholdstall 0 og −1, ukjent enhetstype, både på `POST` og `PUT` | 400 med den spesifikke meldingen («Forkortelse må oppgis.», «Forholdstallet må være større enn 0.», «Enhetstypen finnes ikke.»); raden er uendret etter `PUT` |
| `test_count_units_must_have_ratio_one` | enhet med forholdstall 1,5 under en enhetstype med dimensjonen `Count`, så med 1 | 400 «Enheter av typen antall regnes ikke om - forholdstallet må være 1.»; 201 |
| `test_unit_types_keep_their_dimension` (×3) | oppretter en enhetstype per dimensjon | dimensjonen lagres og leses tilbake |
| `test_a_unit_type_needs_a_valid_dimension` (×4) | uten `dimension`, med `Length`, `vekt` og `7` | 400 |
| `test_create_without_required_fields_is_rejected` (×6) | `POST` med `{}` | 400 `ProblemDetails` med feil |
| `test_create_with_a_blank_name_is_rejected` (×6) | `POST` med navnet `"   "` | 400 `ProblemDetails` «Navn må oppgis.» |
| `test_update_requires_an_id` (×6) | `PUT` uten `id` | 400 |
| `test_malformed_id_is_a_bad_request` (×12: 6 × brukerrute og adminrute) | `GET /…/ikke-en-guid` | **400** (de generiske katalogkontrollerne; de håndskrevne svarer 404) |
| `test_unknown_id_is_404` (×6) | `GET` og `DELETE` av en ID som ikke finnes | 404 på begge |

## 10. `test_core_nutrients.py`: næringsstoffer (14 tilfeller) 🔒

`/api/user/nutrient-definitions` er en statisk, skrivebeskyttet katalog fra Matvaretabellen, med tekstkode som id (`Fett`, `Vit C`).
Det finnes ingen admin-rute for den, så admin leser via brukerruten.

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_nutrients_require_a_signed_in_user` | liste og `GET /Fett` uten innlogging | 401 |
| `test_every_signed_in_role_can_list_the_nutrients` (×2: user, admin) | `GET` listen | 200, alle rader validert strengt mot `NutrientDefinition` (med nøstet gruppe og enhet) |
| `test_the_list_is_sorted_by_sort_order` | leser listen | `sortOrder` er 1, 2, 3 … uten hull, og id-ene er unike |
| `test_groups_are_nested_at_most_one_level` | sjekker `group.parentGroup` på alle stoffer | hovedgrupper har ingen forelder, undergrupper peker på en hovedgruppe (aldri dypere) |
| `test_unit_is_consistent_with_the_units_catalog` | sammenligner `unitId`/`unit`/`unitTypeId` på hvert stoff med `/api/user/units` | forkortelse og enhetstype stemmer med enheten stoffet peker på |
| `test_every_nutrient_can_be_read_by_its_url_encoded_id` | henter hvert stoff på URL-enkodet id (mellomrom, `+`, `:`) | 200 og lik listeraden, for alle stoffer |
| `test_unknown_nutrient_is_404` | `GET /finnes-ikke` | 404 |
| `test_the_catalog_is_read_only` (×6: `POST`/`PUT`/`DELETE` × user/admin) | forsøker å skrive | 405 (metoden finnes ikke) |

---

## 11. `test_core_ingredients.py`: ingredienser (67 tilfeller) 🔒

Alle innloggede søker og leser, kun admin skriver. Søket filtrerer en cachet lettvektsliste (`IngredientListItem`), mens
`GET /{id}` gir hele ingrediensen (`Ingredient`, med næringsverdier og porsjoner) ferskt fra databasen. Testene lager egne
ingredienser (`apitest-…`) og sletter dem etterpå. Ingredienser laget via API-et er aldri offisielle (`isOfficial: false`).

Seed-radene (`isOfficial: true`) endres **aldri** av testene. Testene av låsen på offisielle ingredienser sender i tillegg en ukjent kategori:
låsen sjekkes før fremmednøklene, så en virkende lås svarer med låsemeldingen, og en ødelagt lås stoppes av fremmednøkkelsjekken i stedet
(testen feiler, men ingenting skrives).

**Tilgang:**

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_reading_requires_a_signed_in_user_and_admin_routes_require_admin` | lesing anonymt, og adminrutene som vanlig bruker | 401 og 403 |
| `test_writing_is_admin_only` (×3: `POST`, `PUT`, `DELETE`) | skriving som anonym og som vanlig bruker | 401 og 403 |
| `test_user_routes_have_no_write_methods` | `POST` og `DELETE` på `/api/user/ingredients`, som bruker og admin | 405 |

**Lesing og søk:**

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_the_whole_list_matches_the_dto_for_users_and_admin` | henter hele lista som bruker og som admin | over 500 rader (seed: ca. 700), alle matcher DTO-en, og begge ser de samme ingrediensene |
| `test_seeded_ingredients_are_official_and_verified` | `?isOfficial=true` | over 500 rader, alle offisielle og verifiserte; derivatene (spaghetti, whisky …) peker på en offisiell basis |
| `test_a_sample_of_full_ingredients_matches_the_dto` | henter 25 jevnt fordelte ingredienser i full form | 200, `Ingredient` strengt, og id/navn/kcal stemmer med listeraden |
| `test_unknown_or_malformed_ingredient_id_is_404` | ukjent id og `ikke-en-guid`, på bruker- og adminrute | 404 |
| `test_search_by_name_is_partial_and_case_insensitive` | søker på hele navnet, navnet med store bokstaver, navnet uten siste tegn og et navn som ikke finnes | riktig rad i de tre første, tom liste i den siste |
| `test_search_by_name_also_matches_search_keywords` | lager et søkeord og en ingrediens som bruker det, søker på ordet | ingrediensen kommer med, både på `name=` og `searchKeywordId=` |
| `test_search_filters_by_category_and_keyword` | filtrerer på `categoryId` og `searchKeywordId` | alle rader har kategorien/søkeordet, og ingrediensen mangler i en annen kategori |
| `test_allergen_filters_include_and_exclude` | `allergenId`, `excludeAllergenId` (også gjentatt) og begge samtidig | bare ingredienser med/uten allergenet; begge samtidig gir tom liste |
| `test_search_filters_by_origin_and_variant` | `isOfficial=true/false` og `isVariant=true/false` med en egen basis og variant | testradene er bare med i `isOfficial=false`; varianten bare i `isVariant=true`, basisen bare i `isVariant=false`; alle rader oppfyller filteret |
| `test_filters_are_combined_with_and` | navn + riktig kategori, og navn + feil kategori | én rad, og tom liste |

**Admin: opprette, endre, slette:**

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_create_returns_the_full_ingredient_with_server_assigned_ids` | oppretter en ingrediens med to næringsverdier og en porsjon | 201, alle verdier som sendt, navnet i små bokstaver, egne id-er på alle barn, lik ved `GET` på admin- og brukerrute, og med i søkelista (cache ugyldiggjort) med `nutrientValueCount = 2`, `portionCount = 1`, `usageCount = 0` og samme tidsstempler |
| `test_server_controlled_fields_cannot_be_set_by_the_client` | sender `isOfficial`, `usageCount`, `createdAt` og revisjonsfeltene i kroppen | ignoreres: ikke offisiell, `usageCount = 0`, `createdAt` = nå, `updatedByUserId` fra tokenet, ingen verifiseringsdata |
| `test_verification_is_audited` | oppretter verifisert, endrer (fortsatt verifisert), fjerner verifiseringen | `verifiedAt`/`verifiedByUserId` settes ved opprettelse, beholdes ved endring, nullstilles når `isVerified` blir false; `createdAt` er uendret og `updatedAt` øker |
| `test_allergens_reviewed_is_a_normal_editable_field` | oppretter med `allergensReviewed: true`, `PUT` uten feltet | true, så false |
| `test_create_gives_201_with_a_location_header` | leser `Location` | peker på den nye ingrediensen |
| `test_names_are_normalized_and_unique` | navn med store bokstaver og flere mellomrom; så samme navn med andre bokstaver | normalisert; 409 for duplikatet |
| `test_create_can_make_a_variant_of_another_ingredient` | oppretter en variant med `variantOfIngredientId` | variantens basis vises på raden og i søkelista |
| `test_invalid_content_is_rejected_with_a_specific_400` (×21) | tomt navn; negativ kcal/kJ; spiselig del 0 og 100,5; for stor energi; `ftp:`-kilde; negativ og duplisert næringsverdi; verifisert uten næringsverdier; porsjon med 0 gram; ukjent kategori, enhetstype, standardenhet, allergen, søkeord, næringsstoff, porsjonsenhet og basisingrediens; standardenhet av en annen enhetstype; to porsjoner med samme enhet | 400 `ProblemDetails` med nøyaktig den norske meldingen (f.eks. «Kategorien finnes ikke.», «Enheten stykk er brukt i flere porsjoner.»). Ukjente referanser ga tidligere en generisk 409 fra databasen |
| `test_required_fields_are_enforced` (×5) | utelater `name`, `categoryId`, `primaryUnitTypeId`, `defaultUnitId`, `energyKcal` | 400 `ProblemDetails` med feil |
| `test_update_replaces_the_ingredient_and_all_children` | `PUT` med nytt navn, ny kcal, ett annet næringsstoff og to porsjoner | 200 og hele ingrediensen; barna er byttet ut med **nye** id-er; søkelista viser nye verdier |
| `test_update_validates_like_create` | `PUT` med tomt navn, ukjent kategori og variant av seg selv | 400 på alle, med spesifikk melding; ingrediensen er uendret |
| `test_a_variant_chain_cannot_form_a_loop` | gjør basisen til en variant av sin egen variant | 400 «Variantkjeden danner en løkke.» |
| `test_optimistic_concurrency_rejects_a_stale_update` | to `PUT` med samme `updatedAt` fra én `GET`; så med fersk `updatedAt`; så uten | første 200; andre 409 «Ingrediensen er endret av noen andre …» og ikke lagret; fersk 200; uten `updatedAt` 200 (ingen sjekk) |
| `test_source_data_of_an_official_ingredient_is_locked` (×8) | `PUT` på en seedet ingrediens med endret navn, kcal, kJ, spiselig del, kilde-id, kilde-URL, fjernet eller endret næringsverdi | 400 «Offisielle ingredienser kan ikke endre kildedata. Opprett en variant.» (se avsnittet øverst: skriver aldri) |
| `test_other_fields_of_an_official_ingredient_pass_the_lock` | `PUT` på en seedet ingrediens med endret `allergensReviewed`, porsjoner og næringsverdiene i omvendt rekkefølge | slipper forbi låsen og stoppes av den ukjente kategorien (400 «Kategorien finnes ikke.»); seed-raden er uendret |
| `test_update_of_an_unknown_ingredient_is_404` | `PUT` på ukjent id | 404 |
| `test_delete_removes_the_ingredient_everywhere` | sletter | 204; borte på begge rutene og i søkelista; ny sletting gir 404 |
| `test_delete_of_an_unknown_ingredient_is_404` | `DELETE` på ukjent id | 404 (ikke idempotent, i motsetning til katalogene) |
| `test_an_ingredient_used_by_a_recipe_cannot_be_deleted` | sletter en ingrediens en oppskrift bruker | `usageCount = 1` i lista og på `GET`; 409 «Brukes av 1 oppskriftslinjer, varianter og ubekreftede ingredienser og kan ikke slettes.»; går først når oppskriften er slettet |
| `test_a_base_ingredient_with_a_variant_cannot_be_deleted` | sletter basisen før varianten | 409, så går det når varianten er borte |
| `test_an_ingredient_used_by_an_unconfirmed_ingredient_cannot_be_deleted` | sletter en ingrediens en sammenslått ubekreftet rad peker på | 409; går først når raden er slettet |

---

## 12. `test_core_unconfirmed_ingredients.py`: ubekreftede ingredienser (53 tilfeller) 🔒

En bruker som ikke finner en ingrediens lager en **privat** rad og kan be admin ta den inn (`NotRequested → Pending → Approved | Merged | Rejected`).
Testene bruker `alice` og `bob`; grensen på 10 ventende testes med en egen fersk bruker.

**Tilgang:**

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_anonymous_is_rejected` (×11) | alle seks brukerendepunktene og alle fem adminendepunktene uten innlogging | 401 |
| `test_the_review_queue_is_admin_only` (×5) | de fem adminendepunktene som vanlig bruker | 403 |

**Brukerens egne rader:**

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_create_read_rename_and_delete` | oppretter, leser, gir nytt navn (med store bokstaver), sletter, og sletter en gang til | 201 med `NotRequested`, `createdByUserId` = meg, tomme avgjørelsesfelt og `createdAt` ≈ nå; `PUT` gir 200 med normalisert navn; 204; deretter 404 |
| `test_create_gives_201_with_a_location_and_a_normalized_name` | navn med store bokstaver og mellomrom rundt | `Location` peker på raden, navnet er trimmet og i små bokstaver |
| `test_the_list_is_newest_first` | oppretter to rader | nyeste først |
| `test_request_review_moves_a_row_to_pending_and_locks_it` | ber om vurdering, prøver igjen, gir nytt navn, sletter | 200 `Pending`; 409; 409 (bare `NotRequested` kan endres); 204 (eieren kan slette uansett status) |
| `test_request_review_can_be_given_at_creation` | `requestReview: true` | rett til `Pending` |
| `test_unknown_id_is_404` (×8: 4 kall × ukjent/ugyldig id) | `GET`, `PUT`, `request-review`, `DELETE` | 404 (også for `ikke-en-guid`) |
| `test_a_name_must_be_1_to_200_characters` (×3) | tomt navn, bare mellomrom, 201 tegn | 400 |
| `test_a_name_of_exactly_200_characters_is_accepted` | 200 tegn | 201 |
| `test_the_name_field_is_required` | `{}` | 400 `ProblemDetails` med feil |
| `test_rename_validates_the_name` | nytt navn tomt og for langt | 400 |
| `test_a_name_that_exists_as_an_official_ingredient_is_a_conflict` | navn som en seedet ingrediens (også med store bokstaver), og endring til det navnet | 409 |
| `test_a_user_cannot_have_the_same_name_twice_but_others_can` | samme navn to ganger hos Alice, og samme navn hos Bob | 409; 201 (radene er private per bruker) |
| `test_at_most_10_requests_can_be_pending_at_once` | en ny bruker får 10 ventende, prøver en 11. og ber om vurdering for en 12. | 409 begge steder |

**Isolasjon:**

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_a_user_only_sees_their_own_rows` | Bob og admin (brukerruten) leser Alice sin rad | ikke i listene; `GET`, `PUT`, `request-review`, `DELETE` som Bob gir 404; Alice sin rad er uendret |
| `test_a_new_user_starts_with_an_empty_list` | ny bruker henter listen | `[]` |

**Admin: køen og avgjørelsene:**

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_the_queue_shows_pending_rows_oldest_first` | to ventende (Alice og Bob) og en som ikke er bedt om | begge ventende i køen, eldste først, ikke den tredje |
| `test_the_queue_can_show_all_rows_or_one_status` | `?all=true`, og `?status=Rejected` etter et avslag | alle statuser; bare avslåtte |
| `test_admin_can_read_any_users_row_by_id` | admin henter Alice sin rad, og en ukjent id | 200 lik raden; 404 |
| `test_approve_creates_the_official_ingredient` | godkjenner med en `IngredientRequest` | 200 og ny ingrediens (ikke offisiell); raden er `Approved` med `resolvedIngredientId` og `reviewedAt`; ingrediensen er lesbar og søkbar for alle, med `usageCount = 1` (den løste raden peker på den; svaret på `approve` viser alltid 0); raden er ute av køen |
| `test_approve_can_make_the_ingredient_a_variant` | godkjenner med `variantOfIngredientId` | ingrediensen er en variant av basisen |
| `test_merge_links_to_an_existing_ingredient` | `merge` mot en eksisterende ingrediens | 200, `Merged` og `resolvedIngredientId` |
| `test_reject_is_final_and_stays_private` | avslår med begrunnelse, prøver alle andre avgjørelser, ber om ny vurdering, endrer navn og sletter | `Rejected` med begrunnelse; 409 på alt videre; eieren kan slette |
| `test_reject_reason_is_optional` | avslår uten begrunnelse | `Rejected`, `rejectionReason = null` |
| `test_only_pending_rows_can_be_decided` | avgjør en rad som ikke er bedt om, og en som allerede er sammenslått | 409 på `approve`, `merge` og `reject`; brukeren kan ikke endre eller be om ny vurdering |
| `test_invalid_decisions_are_rejected_and_leave_the_row_pending` | `approve` med tomt navn og ukjent kategori, `merge` mot ukjent ingrediens | 400, 400 «Kategorien finnes ikke.» og 400; raden er fortsatt `Pending` |
| `test_deciding_an_unknown_row_is_404` (×3) | `approve`, `merge`, `reject` på ukjent id | 404 |

---

## 13. `test_core_recipes.py`: oppskrifter (82 tilfeller) 🔒

Oppskrifter er strengt brukereide. Eieren kommer alltid fra tokenet, og en annen brukers oppskrift gir **samme 404** som en id
som ikke finnes. Admin har ingen tilgang til andres oppskrifter. Bare selve oppskriften er en ressurs (steg, linjer og kilde følger med).

**Hver bruker får bare sine egne:**

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_anonymous_is_rejected` (×7) | alle syv oppskriftsendepunktene uten innlogging | 401 |
| `test_a_user_with_no_recipes_gets_an_empty_list` | en helt ny bruker henter `GET /recipes` | 200 og `[]` |
| `test_a_user_with_ten_recipes_gets_exactly_those_ten_and_others_get_none` | Carol lager 10 oppskrifter; Carol, Dave (ny) og Bob henter listene sine | Carol får akkurat de ti, sortert på tittel; Dave får `[]`; Bob ser ingen av dem |
| `test_each_user_only_sees_their_own_recipes` | Alice og Bob lager hver sin; begge og admin henter listen | hver ser bare sin egen, og admin ser ingen av dem |
| `test_someone_elses_recipe_does_not_exist` (×10: 5 operasjoner × Bob/admin) | Bob og admin prøver `GET`, `PUT`, `DELETE`, `favorite` og `nutrition` på Alice sin oppskrift | 404, og svaret er **identisk** (statuskode og kropp uten `traceId`) med svaret for en id som ikke finnes; Alice sin oppskrift er uendret |
| `test_identity_comes_only_from_the_token` | Alice sender `ownerUserId` = Bob og en egen `id` i kroppen, både ved opprettelse og `PUT` | eieren er Alice, id-en er servertildelt, og Bob ser ikke oppskriften |

**Livssyklus:**

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_create_returns_the_whole_recipe` | oppretter med tre steg (to med timer), tre linjer (én med notat, én uten mengde), kilde og bilde | 201 med `Location`; tittelen i små bokstaver; `cookTimeMinutes` = summen av timerne (25); steg nummerert 1–3; linjer i rekkefølge, utelatt mengde blir 0; kilden er `Manual` med bare `reference`; egne id-er på alt; `createdAt = updatedAt`; `GET` gir det samme |
| `test_read_update_favorite_and_delete` | lista og `GET`; favoritt på; `PUT` med alt nytt; favoritt av; sletting; sletting igjen | listeraden stemmer; favoritt gir 204 uten kropp og vises i `GET` og liste; `PUT` gir 200 og erstatter alt, med **nye id-er** på steg og linjer, mens id, eier, favoritt og `createdAt` beholdes og `updatedAt` øker; 204; deretter 404 i `GET` og lista; ny sletting gir 404 |
| `test_the_list_is_sorted_by_title` | tre oppskrifter i tilfeldig rekkefølge | sortert på tittel |
| `test_unknown_or_malformed_id_is_404` (×10) | `GET`, `PUT`, `DELETE`, `favorite`, `nutrition` med ukjent id og `ikke-en-guid` | 404 |
| `test_the_source_is_manual_and_only_the_reference_can_be_set` | sender `type: Scraped`, `url` og `isEditedFromSource` sammen med en `reference` | `Manual`, bare `reference` beholdt, `url` og `isEditedFromSource` er `null` |
| `test_recipe_lines_can_be_to_taste` | linjer med utelatt mengde, `0` og `1.5` | lagres som 0, 0 og 1.5, i rekkefølge |

**Unik tittel per bruker:**

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_a_title_is_unique_per_user` | Alice lager samme tittel en gang til (store bokstaver, mellomrom rundt); Bob lager samme tittel | 409 «Du har allerede en oppskrift med denne tittelen. Velg en annen tittel.» og ingenting lagret; 201 for Bob |
| `test_a_recipe_keeps_its_own_title_on_update_but_cannot_take_another` | `PUT` med egen tittel, og `PUT` som tar tittelen til en annen av Alice sine oppskrifter | 200; 409 med samme melding, og tittelen er uendret |

**Validering:**

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_invalid_content_is_rejected_with_400` (×26) | tom/for lang tittel (201 tegn) og beskrivelse (5 001); porsjoner 0, −2 og 1 001; ingen steg, tomt/for langt steg (2 001), negativ timer, timer over en uke (10 081), 101 steg; ingen ingredienser, 101 linjer, negativ mengde, for langt notat (201); linje uten ingrediens, med begge typer og med ukjent ubekreftet ingrediens; bildeadresse uten protokoll, `ftp:` og `javascript:`; manglende `title`, `description`, `categoryId` og `servings` | 400 `ProblemDetails`, og ingenting lagres |
| `test_the_limits_themselves_are_accepted` (×9) | 1 og 1 000 porsjoner, timer 0 og 10 080, 100 steg, 100 linjer, tittel på 200 tegn, `http:` og `https:` | 201 (grensene er tillatt, en mer enn grensen er ikke) |
| `test_references_to_things_that_do_not_exist_give_409` (×3) | ukjent kategori, ingrediens og enhet | 409 |
| `test_update_validates_like_create_and_changes_nothing_when_it_fails` | `PUT` med tom tittel, uten steg og med ukjent kategori | 400, 400 og 409; oppskriften er uendret |
| `test_the_favorite_request_needs_a_boolean` | `isFavorite: "kanskje"` | 400, og favoritt er uendret |

**Egne (ubekreftede) ingredienser i en oppskrift:**

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_a_recipe_can_use_the_users_own_unconfirmed_ingredient` | en linje med `unconfirmedIngredientId`; så slette den ubekreftede før og etter oppskriften | linja har `name` fra den ubekreftede og `ingredientId = null`; sletting av ingrediensen gir 409 så lenge oppskriften bruker den, og 204 etterpå |
| `test_someone_elses_unconfirmed_ingredient_cannot_be_used` | Alice bruker Bob sin ubekreftede ingrediens | 400 (samme svar som for en som ikke finnes) |
| `test_approving_moves_the_recipe_lines_to_the_official_ingredient` | admin godkjenner Alice sin ubekreftede ingrediens som en oppskrift bruker | linja peker nå på den offisielle ingrediensen (mengde og enhet uendret); en ny oppskrift kan ikke bruke den løste ubekreftede (400) |
| `test_merging_moves_the_recipe_lines_to_the_existing_ingredient` | samme med `merge` | linja peker på ingrediensen den ble slått sammen med |

---

## 14. `test_core_recipe_nutrition.py`: næring per oppskrift (12 tilfeller) 🔒

`GET /api/user/recipes/{id}/nutrition` regnes ut på forespørsel fra dagens ingrediensdata (lagres ikke). Testene lager
ingredienser med kjente verdier og sjekker regnestykket. Tallene sammenlignes med små avrundingsmarginer (veiledende verdier).

| Test | Hva den gjør | Forventer |
| --- | --- | --- |
| `test_nutrition_is_total_and_per_serving` | 200 g av 100 kcal/100 g, fire porsjoner | 200 kcal totalt og 50 per porsjon (kJ og to stoffer likeså); stoffet med verdi 0 er ikke med; 1 av 1 ingrediens telt |
| `test_nutrients_come_in_the_order_of_the_catalog` | ingrediens med stoffene sendt i omvendt rekkefølge | stoffene kommer i katalogens rekkefølge |
| `test_per_serving_follows_the_servings_but_the_total_does_not` | endrer porsjoner fra 4 til 8 med `PUT` | totalen er uendret, per porsjon halveres |
| `test_several_lines_are_summed` | 100 g av en og 50 g av en annen (300 kcal) | 250 kcal, 2 av 2 telt |
| `test_an_own_portion_is_used_without_deducting_the_inedible_part` | 2 stk (1 stk = 50 g) av en ingrediens med 50 % spiselig del | 100 g regnes med (ingen fratrekk for uspiselig del) |
| `test_weight_units_lose_the_inedible_part` | 500 g av en ingrediens med 50 % spiselig del | 250 g regnes med |
| `test_weight_units_are_converted_with_the_unit_ratio` | 0,5 kg | 500 g regnes med (enhetens forholdstall) |
| `test_volume_uses_the_weight_of_the_ingredients_volume_portion` | ingrediens med 1 dl = 90 g; 2 dl og 2 ss | dl brukes direkte (180 g), ss skaleres via gram per ml fra dl-porsjonen |
| `test_lines_that_cannot_be_counted_are_reported_with_a_reason` | fire linjer: telles, «etter smak», egen ubekreftet og dl uten volumporsjon | 1 av 4 telt; `skippedLines` har `ToTaste`, `Unconfirmed` og `NoConversion`, hver med linjens id og navn |
| `test_a_recipe_with_nothing_to_count_has_no_totals` | bare en «etter smak»-linje | `energyKcal`/`energyKj` er `null`, ingen stoffer, 0 av 1 telt |
| `test_nutrition_follows_changes_to_the_ingredient` | admin endrer ingrediensens kcal fra 100 til 300 | neste kall gir 300 (aldri utdatert) |
| `test_an_approved_ingredient_starts_counting_when_it_gets_nutrition_data` | en ubekreftet linje (hoppet over) godkjennes som en ingrediens med 120 kcal | linja er nå telt og bidrar med 120 kcal |

> Ikke testet (bevisst utelatt, ville kreve henholdsvis 100 og 500 opprettelser per kjøring): grensene på 100 egne ubekreftede ingredienser og 500 oppskrifter per bruker.
> Grensen på 10 ventende er testet. Ikke bygget i Core ennå (og derfor ikke testet): deling av oppskrifter, bildeopplasting, måltidsplan
> og handleliste. Opprydding når en konto slettes er bygget i Core (via RabbitMQ fra Auth API), men testes ikke her: testene sletter selv
> oppskrifter og ubekreftede ingredienser før brukeren slettes (se README).

---

## 15. Slik leser du et resultat

```text
576 passed, 2 skipped in 11.2s
```

* **passed**: testen oppfylte forventningen.
* **failed**: en ny feil. Meldingen viser forespørselen, statuskoden og starten av svaret. Kjør på nytt med `--direct` for å avgjøre om
  feilen ligger i gatewayen eller i tjenesten, og med `-k <navn> -x` for å følge én test.
* **skipped**: testen kunne ikke kjøre (`-rs` viser hvorfor, for eksempel `--read-only` eller at Core avviser tokenet).
* **OPPRYDDING**: noe med `apitest-` ble ikke ryddet av testen selv. Det er feid bort, men testen som lekket bør sjekkes.
