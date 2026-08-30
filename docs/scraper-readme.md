# 🕵️ Recipe Scraper Service

En isolert, asynkron bakgrunnstjeneste for skraping, strukturering og mellomlagring av oppskrifter fra eksterne nettsider for Recipe-plattformen.

---

## 🎯 Hensikt med Tjenesten

Hovedformålet med `recipe-scraper-service` er å hente inn oppskrifter fra eksterne kilder på en trygg, kontrollert og skalerbar måte:

* **Skjerme Hoved-API-et:** Skraping (spesielt med nettleser-automatisering) er ressurskrevende. Ved å flytte dette ut i en egen bakgrunnstjeneste som kommuniserer via meldingskø (RabbitMQ), forblir brukergrensesnittet og API-ene lynraske.
* **Unngå Dobbeltskraping:** Tjenesten sjekker alltid en egen cache (MongoDB) før den åpner en nettleser. En oppskrift skrapes **kun én gang** uavhengig av hvor mange brukere som importerer den.
* **Kontroll på Kilder:** Tjenesten godtar kun URL-er fra eksplisitt godkjente nettsider (whitelist).

---

## ✨ Kjerne-features & Planlagt Logikk

### 1. 🛡️ URL-validering & Domene-whitelist

* Sjekker innkommende forespørsler opp mot en liste med godkjente domener (f.eks. Matprat, Tine, Meny, etc.).
* Avviser ugodkjente eller potensielt skadelige lenker umiddelbart ved å publisere en feil-hendelse (`RecipeScrapeFailedEvent`).

### 2. 🧹 Smart Caching & URL-normalisering

* Vasker og normaliserer innkommende URL-er ved å fjerne tracking-parametere (f.eks. `?utm_source=...`, `#step1` eller rekkefølge på parametere).
* Slår opp i MongoDB (`recipe-scraper-cache`) på den normaliserte URL-en.
* **Cache Hit:** Oppskriften hentes direkte fra databasen og returneres på meldingsbussen uten å skrape nettsiden på nytt.

### 3. 🤖 Playwright Skrapemotor (Strategy Pattern)

* Dersom oppskriften ikke finnes i cache, startes en Playwright-nettleserinstans.
* Benytter **Strategy Pattern** (`ISiteScraper`): Hver støttede nettside har sin egen dedikerte skrape-klasse som vet nøyaktig hvordan ingredienser, porsjoner, fremgangsmåte og bilder skal hentes ut.
* Det skrapte resultatet lagres i MongoDB og publiseres som en `RecipeScrapedEvent`.

### 4. 🔄 Fullstendig Asynkron via RabbitMQ

* Eksponerer **ingen HTTP REST-endepunkter**.
* Lytter utelukkende på meldinger fra RabbitMQ/MassTransit og rapporterer status/resultat tilbake via hendelser (events).

---

## 🗺️ Planlagt Arbeidsflyt (Execution Flow)

```text
[ RabbitMQ / MassTransit ]
         │ (Mottar forespørsel om skraping)
         ▼
1. RecipeScraperConsumer
         │
         ▼
2. MediatR Command Handler
         │
         ├──► Step 1: Valider URL & Domene (Whitelist)
         │        └─ Ugyldig? Send RecipeScrapeFailedEvent 🛑
         │
         ├──► Step 2: Sjekk MongoDB (Normalisert URL)
         │        └─ Funnet i cache? Send RecipeScrapedEvent direkte 🚀
         │
         └──► Step 3: Skrap med Playwright (Engine)
                  ├─ Velg riktig ISiteScraper-strategi
                  ├─ Hent ingredienser, steg, bilde-URL og tidsbruk
                  ├─ Lagre i MongoDB (Cache hit for fremtiden)
                  └─ Send RecipeScrapedEvent 🚀

```

---

## 📋 Fremtidig Sjekkliste / Huskeliste når du starter opp igjen

Når du tar opp kodingen på denne tjenesten igjen, er dette den anbefalte rekkefølgen for å bygge ut funksjonaliteten:

* [ ] **1. Meldingskontrakter (`Contracts`)**
* Definer `ScrapeRecipeCommand` (URL, RequestedByUserId).
* Definer `RecipeScrapedEvent` (Tittel, Ingredienser, Steg, BildeURL, NormalisertURL).
* Definer `RecipeScrapeFailedEvent` (URL, Feilmelding/Årsak).


* [ ] **2. Domene & URL-normalisering (`Domain` / `Application`)**
* Implementer `NormalizedUrl`-verdiobjektet (fjerner query-støy).
* Lag en `DomainWhitelistService` med oversikt over støttede domener.


* [ ] **3. MongoDB Cache-lagring (`Persistence`)**
* Sett opp kobling mot MongoDB-containeren (`recipe-scraper-cache`).
* Implementer repository for hurtig oppslag på normalisert URL.


* [ ] **4. Playwright & Strategi-motor (`Engine`)**
* Sett opp Playwright `IBrowserContext`-håndtering.
* Lag grensesnittet `ISiteScraper`.
* Bygg første konkret skraper (f.eks. `MatpratScraper` eller `TineScraper`).


* [ ] **5. MassTransit Consumer & DI-oppsett (`Service`)**
* Konfigurer `RecipeScraperConsumer` med MassTransit og RabbitMQ.
* Sett opp Serilog-logging mot Seq.