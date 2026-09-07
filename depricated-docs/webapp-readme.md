# Kjøkkenhylla (`recipe-webapp`)

**Kjøkkenhylla** er en personlig oppskriftshubb og måltidsplanlegger. Webapplikasjonen lar deg samle og organisere oppskrifter, generere automatiserte handlelister, skrape retter fra nettet og holde oversikt over næringsinnhold.

---

## 🌟 Funksjonalitet

* **Oppskriftshåndtering:** Lagre egne oppskrifter manuelt eller importer direkte fra godkjente nettsteder (f.eks. Matprat).
* **Måltidsplanlegging & Handleliste:** Planlegg måltider på dags- og ukesbasis og få generert strukturerte handlelister.
* **Næringsinnhold & Veiledning:** Oversikt over energi og makronæringsstoffer (proteiner, fett, karbohydrater, fiber) per ingrediens, måltid og akkummulert på ukesbasis. *(Kun veiledende)*.
* **Autentisering & Sikkerhet:** Full integrasjon med `recipe-auth-api` via OpenIddict (JWT & Refresh Tokens), Google OAuth SSO, konto-sperring og svartelisting.
* **Admin Dashboard:** Innebygd administrative verktøy for brukeradministrasjon, utsendelse av e-poster, systemstatus og infrastruktursnarveier (Seq, RabbitMQ).

---

## 🏗️ Arkitektur & Mikrotjenester

Webappen er primærgrensesnittet i økosystemet og kommuniserer med baksystemene via **API Gateway** (Port 5000):

1. **`recipe-webapp` (Denne appen):** Next.js App Router med server-side proxy og interceptors.
2. **`recipe-auth-api`:** Håndterer brukere, sikkerhet, tokens og admin-operasjoner.
3. **`recipe-core-api`:** Behandler oppskrifter, kategorier, måltidsplaner og næringsberegning.
4. **`recipe-scraper-service`:** Mikrotjeneste for uthenting av oppskrifter fra eksterne nettsteder.
5. **`recipe-notification-service`:** Event-drevet e-posttjeneste koblet mot RabbitMQ.

Internt benytter frontend-applikasjonen dedikerte HTTP-agenter (`agentInternal` for server-side API-ruter og `agentExternal` for direkte REST-kall).

---

## 🛠️ Teknologistakk

| Kategori | Teknologi |
| --- | --- |
| **Rammeverk & Språk** | Next.js 16 (App Router), React 19, TypeScript 5 |
| **UI & Styling** | Mantine v9 (`core`, `form`, `hooks`, `dates`, `notifications`), PostCSS |
| **Datavisualisering** | Mantine Charts, Recharts |
| **Ikoner & Verktøy** | Tabler Icons (`@tabler/icons-react`), Dayjs, React Markdown |

---

## ⚙️ Miljøvariabler (`.env`)

Konfigurer følgende variabler i din `.env`-fil i rotmappen:

```env
# URL til API Gateway (Autentisering og kjernedata)
AUTH_API=http://localhost:5000/api/auth
CORE_API=http://localhost:5000/api

# Google OAuth Client ID for frontend SSO
NEXT_PUBLIC_GOOGLE_CLIENT_ID=535946804678-04o2l5f6b7j7jdojc1n0j3g8gms81p1e.apps.googleusercontent.com

```

---

## 🚀 Komme i gang

### Forutsetninger

* Node.js (versjon 20 eller nyere)
* `npm`

### Installasjon & Kjøring

1. **Installer avhengigheter:**
```bash
npm install

```


2. **Start utviklingsserveren:**
```bash
npm run dev

```


3. Åpne `http://localhost:3000` i nettleseren.

---

## 📄 Juridisk & Dokumentasjon

Offentlig informasjon og vilkår ligger tilgjengelig under `public/docs/legal/`:

* `accessibility.md` – Tilgjengelighetserklæring
* `cookies.md` – Informasjon om informasjonskapsler
* `privacy.md` – Personvernerklæring
* `terms.md` – Brukervilkår
