# 🕵️ Arc-Notater: `recipe-scraper-service`

Dette dokumentet beskriver arkitekturen, prosjektstrukturen og informasjonsflyten for **`recipe-scraper-service`**. Tjenesten fungerer som en isolert, asynkron bakgrunnstjeneste for skraping og mellomlagring av oppskrifter fra eksterne nettsider.

---

## 🎯 Hensikt & Hovedansvar

1. **Asynkron Oppgavehåndtering**: Lytter på meldinger fra RabbitMQ via MassTransit i stedet for å eksponere et direkte HTTP REST API.
2. **Kildevalidering & Whitelist**: Sjekker om den innkommende URL-en tilhører et godkjent domene.
3. **Caching i MongoDB (`recipe-scraper-cache`)**: Normaliserer URL-en (fjerner query-parametere o.l.) og sjekker om oppskriften allerede er skrapt. Unngår unødvendig skraping.
4. **Playwright-basert Skraping**: Benytter et utvidbart strategi-mønster (`ISiteScraper`) for å åpne Playwright-instanser og skrape spesifikke nettsider.
5. **Event-basert Tilbakemelding**: Publiserer hendelser (`RecipeScrapedEvent` eller `RecipeScrapeFailedEvent`) tilbake til meldingsbussen når jobben er utført.

---

## 🏗️ Prosjektstruktur (.NET Clean Architecture)

```text
recipe-scraper-service/
├── Recipe.Scraper.Contracts/          # DTO-er og RabbitMQ-events (deles med andre tjenester)
├── Recipe.Scraper.Domain/             # Kjerne-domenemodeller (ScrapedRecipe, Ingredient, Step, Domain-regler)
├── Recipe.Scraper.Application/        # MediatR-handlers, URL-normalisering, domenevalidering
├── Recipe.Scraper.Persistence/        # MongoDB-kobling, Document-modeller og repositories
├── Recipe.Scraper.Engine/             # Playwright-infrastruktur, ISiteScraper-grensesnitt og nettsidespesifikke skrapere
└── Recipe.Scraper.Service/            # Host (Worker Service), MassTransit consumers, Serilog og DI-konfigurasjon

```

---

## 📦 Pakkefordeling (NuGet)

| Prosjekt | NuGet-pakker | Beskrivelse / Ansvar |
| --- | --- | --- |
| **`Recipe.Scraper.Contracts`** | *Ingen* / `MassTransit.Abstractions` | Rene C# `record`-typer for bussen (`ScrapeRecipeCommand`, `RecipeScrapedEvent`). |
| **`Recipe.Scraper.Domain`** | *Ingen* | Domene-entiteter, verdiobjekter (`NormalizedUrl`) og logikk for domenevalidering. |
| **`Recipe.Scraper.Application`** | `MediatR` | Orchestration. Koordinerer sjekk mot godkjente domener, MongoDB-spørring og skrapemotor. |
| **`Recipe.Scraper.Persistence`** | `MongoDB.Driver` | MongoDB repository-implementasjon for spørringer mot `recipe-scraper-cache`. |
| **`Recipe.Scraper.Engine`** | `Microsoft.Playwright` | Playwright-robot. Inneholder `ScraperFactory` og `ISiteScraper`-implementasjoner per nettside. |
| **`Recipe.Scraper.Service`** | `MassTransit.RabbitMQ`<br>

<br>`Serilog.AspNetCore`<br>

<br>`Serilog.Sinks.Seq` | Worker Service host. Setter opp Dependency Injection, MassTransit, Serilog og Seq. |

---

## 🔄 Informasjonsflyt

```text
[ RabbitMQ / MassTransit ] 
         │
         ▼
1. RecipeScraperConsumer (Recipe.Scraper.Service)
         │
         ▼
2. MediatR Command (Recipe.Scraper.Application)
         │
         ├───► A. Valider URL & Domene (Whitelist)
         │        └─► Hvis UGYLDIG: Publiser RecipeScrapeFailedEvent (Ugodkjent kilde)
         │
         ├───► B. Sjekk MongoDB på normalisert URL (Recipe.Scraper.Persistence)
         │        └─► Hvis TREFF: Returner eksisterende oppskrift fra cache
         │
         └───► C. Skrap nettside med Playwright (Recipe.Scraper.Engine)
                  ├─► Velg riktig ISiteScraper ut fra domene
                  ├─► Åpne Playwright Browser Context & hent data
                  ├─► Lagre ny oppskrift i MongoDB
                  └─► Publiser RecipeScrapedEvent tilbake på bussen

```

---

## 💡 Nøkkelprinsipper & Mønstre

* **Strategi-mønster for Skrapere**: Nye nettsider legges til ved å opprette nye klasser som implementerer `ISiteScraper` i `Recipe.Scraper.Engine`.
* **Gjenbruk av Playwright Browser Context**: Nettleserinstansen håndteres isolert i `Engine` for å optimalisere ytelse og minnebruk.
* **Normalisering av URL**: Ekstra query-parametere (f.eks. `?utm_source=...` eller `#step1`) fjernes før oppslag i MongoDB, slik at samme oppskrift aldri skrapes to ganger.
* **Observability**: Serilog sender strukturerte logger direkte til Seq (`http://localhost:5341`) for sporing av feil og tidsbruk under skraping.