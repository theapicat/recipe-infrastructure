# 🔌 Connection Strings (`ConnectionStrings.md`)

## 1. Auth Database (PostgreSQL - `recipe-auth-db`)

Brukes av `recipe-authentication-api` for brukerkontoer, passord-hashes, tilganger og roller.

**Lokal utvikling (Rider / IDE - Port 5432):**

```text
Host=localhost;Port=5432;Database=recipe_auth_db;Username=auth_user;Password=auth_secure_password_dev

```

**Internt i Docker (`recipe-net` - Port 5432):**

```text
Host=recipe-auth-db;Port=5432;Database=recipe_auth_db;Username=auth_user;Password=auth_secure_password_dev

```

---

## 2. Core Database (PostgreSQL - `recipe-core-db`)

Brukes av `recipe-core-api` for oppskrifter, trinn, ingredienser og kategorier.

**Lokal utvikling (Rider / IDE - Port 5433 på vert):**

```text
Host=localhost;Port=5433;Database=recipe_core_db;Username=core_user;Password=core_secure_password_dev

```

**Internt i Docker (`recipe-net` - Port 5432 internt):**

```text
Host=recipe-core-db;Port=5432;Database=recipe_core_db;Username=core_user;Password=core_secure_password_dev

```

---

## 3. Scraper Cache (MongoDB - `recipe-scraper-cache`)

Brukes av `recipe-scraper-service` for mellomlagring av skrapt rådata.

**Lokal utvikling (Rider / IDE - Port 27017):**

```text
mongodb://mongo_user:mongo_secure_password_dev@localhost:27017

```

**Internt i Docker (`recipe-net` - Port 27017):**

```text
mongodb://mongo_user:mongo_secure_password_dev@recipe-scraper-cache:27017

```

---

## 4. Message Broker (RabbitMQ - `recipe-message-broker`)

Brukes av alle mikrotjenester for asynkron meldingsutveksling via MassTransit.

**Lokal utvikling (Rider / IDE - Port 5672):**

```text
amqp://rabbit_user:rabbit_secure_password_dev@localhost:5672

```

**Internt i Docker (`recipe-net` - Port 5672):**

```text
amqp://rabbit_user:rabbit_secure_password_dev@recipe-message-broker:5672

```