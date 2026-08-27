# 🛠️ Utvikler-setup & Infrastrukturnotater

## 1. Port-oversikt & Tjeneste-adresser

### 🟢 Lokal Utvikling (`dotnet watch` / `npm run dev` på vertssystemet)

* **`recipe-web-app` (Next.js)**: `http://localhost:3000`
* **`recipe-gateway-api` (YARP)**: `http://localhost:5000` *(Klientens eneste inngangsport)*
* **`recipe-authentication-api`**: `http://localhost:5001` *(Ruteres via Gateway på `/api/auth`)*
* **`recipe-core-api`**: `http://localhost:5002` *(Ruteres via Gateway på `/api/public`, `/api/user`, `/api/admin` og `/hubs`)*
* **`recipe-seq` (Log Dashboard)**: `http://localhost:5341`
* **RabbitMQ Dashboard**: `http://localhost:15672`

### 🔵 Docker Container / Produksjon (Internt på `recipe-net`)

* **`recipe-gateway-api`**: `http://recipe-gateway-api:80`
* **`recipe-authentication-api`**: `http://recipe-authentication-api:80`
* **`recipe-core-api`**: `http://recipe-core-api:80`
* **`recipe-seq`**: `http://recipe-seq:80` *(Sinks sender logger hit)*

---

## 2. Autentisering & Gateway Sikkerhetsmodell

* **Lokal JWT-validering**: Gateway-en validerer JWT-tokens i minnet via en symmetrisk nøkkel (`JWT__KEY`). Den gjør ingen nettverskall mot Auth API for validering.
* **Header Sanitization & Injection**: Gateway renser innkommende forespørsler for `X-User-Id` og `X-User-Roles` for å forhindre spoofing, og injiserer verifiserte verdier fra JWT videre til de interne tjenestene.
* **Påkrevde Miljøvariabler (`.env` / `appsettings`)**:

```env
  JWT__ISSUER=recipe-auth-app
  JWT__AUDIENCE=recipe-frontend
  JWT__KEY=din-super-hemmelige-og-lange-dev-nokkel-her-12345!
```

---

## 3. Tilkoblingsstrenger (Connection Strings)

### 🟢 Lokal Utvikling (`dotnet watch` på vertssystemet)

* **`recipe-authentication-api` (PostgreSQL)**:
`Host=localhost;Port=5432;Database=recipe_auth_db;Username=auth_user;Password=auth_secure_password_dev;Client Encoding=UTF8;`
* **`recipe-core-api` (PostgreSQL)**:
`Host=localhost;Port=5433;Database=recipe_core_db;Username=core_user;Password=core_secure_password_dev;Client Encoding=UTF8;`
* **`recipe-scraper-service` (MongoDB)**:
`mongodb://mongo_user:mongo_secure_password_dev@localhost:27017/recipe_scraper_cache?authSource=admin`
* **RabbitMQ Message Broker**:
`amqp://rabbit_user:rabbit_secure_password_dev@localhost:5672/`

### 🔵 Docker Container (Internt på `recipe-net`)

* **`recipe-authentication-api`**: `Host=recipe-auth-db;Port=5432;...`
* **`recipe-core-api`**: `Host=recipe-core-db;Port=5432;...`
* **`recipe-scraper-service`**: `mongodb://mongo_user:mongo_secure_password_dev@recipe-scraper-cache:27017/...`
* **RabbitMQ Message Broker**: `amqp://rabbit_user:rabbit_secure_password_dev@recipe-message-broker:5672/`

---

## 4. Utvikler-arbeidsflyt (Hybrid tilnærming)

* **Infrastruktur**: Kjører i Docker via `recipe-infrastructure` (`docker compose up -d`).
* **Applikasjoner under utvikling**: Kjøres nativt på maskinen for lynrask re-kompilering og hot reload (`dotnet watch run` / `npm run dev`).
* **Program.cs Structure**: Kodebasen bruker en "Extension-first"-struktur der retningslinjer (CORS, Auth, Proxy, Serilog) ligger i egne klasser i `API/Extensions/`.

---

## 5. Garanti for UTF-8 Tegnsett

* **PostgreSQL-instanser** initialiseres med `--encoding=UTF8 --lc-collate=C --lc-ctype=C`.
* Init-skript tvinger `SET client_encoding = 'UTF8';`.
* Npgsql connection strings inkluderer `Client Encoding=UTF8;`.

---

## 6. Nyttige Docker Kommandoer

* **Start infra**: `docker compose up -d`
* **Stopp infra (behold data)**: `docker compose down`
* **Nullstill databaser og volumer helt**: `docker compose down -v`
* **Sjekk logger for spesifikk container**: `docker logs recipe-seq`
