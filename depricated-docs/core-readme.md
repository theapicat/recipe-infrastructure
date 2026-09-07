# 🍳 Recipe Core API

Selve motoren og hjertet i Recipe-plattformen. Dette API-et håndterer all kjernelogikk for oppskrifter, ingredienser, måltidsplanlegging og brukerdata, og fungerer som bindeleddet mellom brukergrensesnittet og de asynkrone bakgrunnstjenestene.

---

## 🎯 Hovedansvar & Features

* **📖 Oppskrifter & Næringsinnhold:** Lagring, redigering, sletting og henting av oppskrifter, trinnvise instruksjoner, ingredienser og beregnet næringsinnhold.
* **📅 Ukesplaner & Handlelister:** Generering og styring av dynamiske ukesplaner og interaktive handlelister som brukeren kan tilpasse i sanntid.
* **⚙️ Brukerinnstillinger:** Håndtering av personlige preferanser, allergier og visningsvalg.
* **📡 Sanntidsoppdateringer (SignalR):** Umiddelbare push-varsler til frontend når bakgrunnsjobber fullføres eller data endres.
* **🔄 Meldinger & Orkestrering (RabbitMQ):**
* Sender skrapeforespørsler videre til `recipe-scraper-service`.
* Utløser e-postutsendelser (f.eks. kontaktskjema) via `recipe-notification-service`.



---

## 🛠️ Teknologistakk & Designmønstre

* **.NET (Web API)** – Høyytelses web-API eksponert skjermet bak YARP Gateway.
* **PostgreSQL (`recipe-core-db`)** – Relasjonsdatabase for strukturert domenelagring.
* **Dapper & Dapper.Plus** – Lynrask dataadgang med skreddersydde SQL-spørringer og effektiv bulk-håndtering uten EF Core-overhead.
* **MediatR (CQRS)** – Skiller lesing (*Queries*) og skriving (*Commands*) i helt isolerte handlers for ryddig og skalerbar kildekode.
* **MassTransit & RabbitMQ** – Asynkron hendelsesstyrt kommunikasjon mot andre mikrotjenester.
* **Serilog & Seq** – Strukturt logging mot sentralisert dashboards på port `5341`.

---

## 🔄 Typiske Arbeidsflyter (Workflows)

```text
[ Web App / YARP Gateway ]
            │ (HTTP REST / WebSocket)
            ▼
   [ Recipe.Core.API ]
            │
            ▼ (MediatR CQRS)
 ┌──────────┴──────────┐
 │                     │
 ▼ (Queries / Read)    ▼ (Commands / Write)
[ Dapper / SQL ]     [ Dapper / SQL ] ──► [ PostgreSQL (recipe-core-db) ]
                       │
                       ├─► [ SignalR Hub ] ─────────► (Sanntids push til frontend)
                       │
                       └─► [ RabbitMQ Bus ] ───────┬─► (ScrapeRecipeCommand -> Scraper Service)
                                                   └─► (ContactFormSubmittedEvent -> Notification Service)

```

---

## 🏗️ Prosjektstruktur (Clean Architecture)

```text
recipe-core-api/
├── Recipe.Core.Contracts/     # Rene record-events for RabbitMQ (deles med andre mikrotjenester)
├── Recipe.Core.Domain/        # Kjerne-entiteter (Recipe, Ingredient, MealPlan), Enums og Value Objects
├── Recipe.Core.Application/   # MediatR Commands/Queries, Handlers, FluentValidation og interfaces
├── Recipe.Core.Persistence/   # Dapper/Dapper.Plus repositorier, Npgsql-kobling og rå SQL-skript
└── Recipe.Core.API/           # Controllers, SignalR Hubs, MassTransit Consumers og Serilog/DI-oppsett

```