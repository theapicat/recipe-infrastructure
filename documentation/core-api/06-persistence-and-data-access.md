# Persistens og dataadgang i `recipe-core-api`

---

Per 2026-09-20. Sjekk mot faktisk kode ved tvil.

## 1. Prinsipp

Dapper mot Postgres via Npgsql — ingen EF Core. Alle spørringer/kommandoer er Postgres-funksjoner
(`CREATE FUNCTION`), aldri rå SQL bygget i C#. `Persistence`-prosjektet inneholder de generiske malklassene og de
konkrete klassene som kobler en modell til navnet på funksjonene den bruker; selve SQL-en ligger i migreringsskript
(§3).

Dapper-oppsett (satt i `PersistenceExtensions.AddPersistenceServices`):

- `DefaultTypeMap.MatchNamesWithUnderscores = true` — snake_case-kolonner matches mot PascalCase-egenskaper
  (`owner_user_id` → `OwnerUserId`) uten alias. Egenskapsnavnet må derfor tilsvare kolonnenavnet
  (`review_status` → `ReviewStatus`, ikke `Status`).
- `DateTimeOffsetTypeHandler` — Npgsql leverer `timestamptz` som `DateTime`, og Dapper konverterer ikke selv til
  `DateTimeOffset`. Skriving sender alltid UTC (Npgsql avviser andre offsets).
- **Enum sendes som tekst.** Dapper sender ellers enum som heltall, som feiler mot en `text`-kolonne med `CHECK`. Lesing
  fra tekst til enum fungerer direkte; ved skriving sendes `.ToString()` eksplisitt (se `UnconfirmedIngredientWriter`).
- `uuid[]` leveres som `Guid[]` — modeller som leses direkte fra en array-kolonne bruker `Guid[]`, ikke `List<Guid>`
  (`IngredientListItem`).

---

## 2. Generisk mal: `DbConnection` / `DbReader<T>` / `DbWriter<T>`

`Persistence/Services/`:

- `DbConnection(string connectionString)` — abstrakt basisklasse, åpner en `NpgsqlConnection`.
- `DbReader<T>` — abstrakt, virtuelle `GetAllQuery`/`GetByIdQuery`-strenger (null som standard), generiske
  `GetAllAsync()`/`GetByIdAsync<TId>(id)`. Kaster `DbQueryMissingException<T>` hvis en query ikke er overstyrt.
- `DbWriter<T>` — samme mønster for `InsertCommand`/`UpdateCommand`/`DeleteCommand`, kaster
  `DbCommandMissingException<T>`. `DeleteAsync` returnerer **antall slettede rader**: `delete_*`-funksjonene returnerer
  `integer`, og malen leser det som skalar (et `SELECT` gir ikke pålitelig «rader berørt» via `ExecuteAsync`).

Hver modell får sitt eget par i `Persistence/Implementation/` — for de enkle katalogene kun overstyring av
query/command-strenger, ingen annen logikk:

```csharp
public class AllergenReader(IConfiguration configuration)
    : DbReader<Allergen>(configuration.GetConnectionString("DefaultConnection")!)
{
    public override string? GetAllQuery { get; } = "SELECT * FROM get_all_allergen();";
    public override string? GetByIdQuery { get; } = "SELECT * FROM get_allergen_by_id(@Id);";
}
```

Registrert i DI mot malen (`DbReader<Allergen>` → `AllergenReader`), ikke et eget grensesnitt. Et grensesnitt per modell
finnes **bare** når modellen trenger metoder utover malen.

### Modeller som går utover malen

- **`Ingredient`** — `IngredientReader` overstyrer `GetByIdAsync` og henter raden og alle barn (allergener, nøkkelord,
  næringsverdier, porsjoner) i ett `QueryMultiple`-kall. `IngredientWriter` overstyrer `AddAsync`/`UpdateAsync` slik at
  ingrediensen og barna skrives i **én transaksjon** (malen åpner ellers ny forbindelse per kall). Oppdatering
  erstatter barna (slett + sett inn). Delt SQL-logikk ligger i `IngredientPersistence` (internal). `is_official` er bevisst ikke en
  parameter i `update_ingredient` (kun i `insert_ingredient`) - kan derfor strukturelt ikke endres via oppdatering, selv om et
  fremtidig skrivevei skulle glemme å beskytte det i C#. `created_at` er samme mønster (kun i `insert_ingredient`). `updated_at` og
  `allergens_reviewed` settes eksplisitt av handleren (ingen `DEFAULT`-avhengighet) ved både opprettelse og oppdatering, til bruk i
  `IngredientMapper.ValidateOfficialLock`/samtidighetssjekken i `UpdateIngredientCommandHandler` (`Documentation/08-api-reference.md`).
  `usage_count` er ikke en kolonne i det hele tatt - se «Brukstelling og systemrader» under. Revisjonskolonnene `updated_by_user_id`, `verified_at` og `verified_by_user_id` (2026-09-24, ingen FK - brukeridentitet eies av auth-api) settes av handlerne (`IngredientAudit`) fra tokenet og er parametere i både `insert_` og `update_ingredient`; de er ikke med i `IngredientRequest`, så klienten kan ikke sette dem. `get_all_ingredient_list_item()` teller også `nutrient_value_count`/`portion_count` per rad. `recipe` har unik indeks `(owner_user_id, title)`.
- **`IngredientListItem`** — `IngredientListItemReader`, kun `GetAll` (lettvekts-liste til cachen).
- **`UnconfirmedIngredient`** — egne grensesnitt i `Persistence/Interfaces/` (`IUnconfirmedIngredientReader`/
  `Writer`) siden den trenger spørringer per bruker/status, telling til grenser og statusendringer. Endrende metoder
  returnerer `bool` (`false` = ingen rad matchet vilkåret: finnes ikke, feil eier eller feil status). `ResolveAsync`
  oppretter evt. en ny ingrediens, avgjør forespørselen og flytter oppskriftslinjer i én transaksjon.
- **`Recipe`** — brukereid, så egne grensesnitt i `Persistence/Interfaces/` (`IRecipeReader`/`IRecipeWriter`, ikke `DbReader<T>`-malen):
  *alle* funksjoner tar eier (`p_owner_user_id`) og filtrerer på den — også barnefunksjonene (`get_recipe_steps`,
  `get_recipe_ingredients`) — så en annen brukers oppskrift er umulig å lese eller endre selv om id-en er kjent. Lista
  (`get_all_recipe_list_item`) er lettvekts og sortert på tittel; detaljen leses i ett `QueryMultiple`-kall (rad, steg, linjer med
  ingrediensnavn via `COALESCE(ingredient.name, unconfirmed_ingredient.name)`). `RecipeWriter` skriver oppskriften og barna i **én
  transaksjon**; oppdatering endrer bare raden hvis den tilhører eieren (0 rader → rollback, `false`), og erstatter deretter barna (slett + sett
  inn). `update_recipe` rører aldri eier, kilde-type/-url, favoritt eller `created_at`. `RecipeRow` (flat rad med kilde-kolonnene) bygges
  om til `Recipe` med nøstet `Source`. `recipe_ingredient.sort_order` (1..n) gir rekkefølgen; `amount` er `NOT NULL DEFAULT 0` (0 = «etter smak»).
  Næringsberegningen henter rådata via tre eier-filtrerte funksjoner i ett `QueryMultiple`-kall (`get_recipe_by_id` + `get_recipe_nutrition_lines` (linje med enhetstype/-ratio og
ingrediensens energi/spiselig del) + `get_recipe_nutrition_portions` + `get_recipe_nutrition_values`); regnestykket ligger i C#, ikke i SQL.
Tabellene har `CHECK`: `servings > 0`, `cook_time_minutes >= 0`, `step_number > 0`, `timer_minutes >= 0`, `amount >= 0`, tittel med
  små bokstaver.
- **`NutrientDefinition`** — statisk og skrivebeskyttet: bare `NutrientDefinitionReader`, ingen Writer og ingen
  `insert_/update_/delete_`-funksjoner i SQL; radene kommer kun fra seed-data. `unit_id` er en `uuid`-fremmednøkkel til `unit`,
  og `group_id` en `uuid`-fremmednøkkel til `nutrient_group` (hoved- og undergrupper via `parent_group_id`; alle id-er er Guid).
  Hierarkiet ligger i gruppene — det er ingen `parent_id` på stoffene. `nutrient_group` har **ingen egen Reader, funksjon eller
  endepunkt**: lesefunksjonene (`get_all_nutrient_definition`/`…_by_id`, `RETURNS TABLE`) folder ut enheten (`unit` =
  forkortelsen, `unit_type_id`) og gruppen (`group_*` og `parent_group_*`) i én flat rad, og readeren
  (`NutrientDefinitionRow.ToNutrientDefinition`) bygger den om til `NutrientDefinition` med `Group` (og `Group.ParentGroup`)
  nøstet inni.

### Brukstelling og systemrader (2026-09-22)

De seks adminstyrte katalogene (`ingredient_category`, `allergen`, `search_keyword`, `unit_type`, `unit`,
`recipe_category`) og `ingredient` har alle `Domain.IHasUsageMetadata`/en tilsvarende `UsageCount`-egenskap. Begge feltene
er serverstyrte og kan ikke settes fra klienten - se «Sikring mot klientmanipulasjon» under.

- **`unit_type.dimension`** (2026-09-24) er en `text`-kolonne med `CHECK` (`Weight`/`Volume`/`Count`). Næringsberegningen (`get_recipe_nutrition_lines`/`…_portions` returnerer `unit_dimension`) og enhetsvalideringen bruker den - aldri enhetstypens navn, som bare er en etikett. `UnitTypeWriter` sender den som tekst (`ToString()`), siden Dapper ellers sender enum som heltall.
- **`is_system`** er en ekte `boolean NOT NULL DEFAULT false`-kolonne på de seks katalogtabellene. Seed-radene
  (`seed_01`, `seed_04`, `seed_05`, `seed_06`) setter den til `true`; adminopprettede rader får `false` fra kolonnens
  `DEFAULT` (kolonnen er aldri nevnt i `insert_<catalog>`/`update_<catalog>` sitt parameterlys).
- **`usage_count` er ikke en kolonne noe sted** - den beregnes med en skalar-subquery per rad i
  `get_all_<catalog>()`/`get_<catalog>_by_id()` (nå `RETURNS TABLE`, ikke `RETURNS SETOF <tabell>`) og i
  `get_all_ingredient_list_item()`/`get_ingredient_by_id()`. Fremmednøkkel-kartet (hva som telles for hver tabell):

  | Katalog | `usage_count` = |
  | --- | --- |
  | `ingredient_category` | `count(ingredient WHERE category_id = denne)` |
  | `allergen` | `count(ingredient_allergen WHERE allergen_id = denne)` |
  | `search_keyword` | `count(ingredient_search_keyword WHERE search_keyword_id = denne)` |
  | `recipe_category` | `count(recipe WHERE category_id = denne)` |
  | `unit_type` | `count(unit WHERE unit_type_id = denne) + count(ingredient WHERE primary_unit_type_id = denne)` |
  | `unit` | `count(ingredient WHERE default_unit_id = denne) + count(ingredient_portion WHERE unit_id = denne) + count(recipe_ingredient WHERE unit_id = denne) + count(nutrient_definition WHERE unit_id = denne)` |
  | `ingredient` | `count(recipe_ingredient WHERE ingredient_id = denne) + count(ingredient WHERE variant_of_ingredient_id = denne) + count(unconfirmed_ingredient WHERE resolved_ingredient_id = denne)` |

  Telles ved hver lesing, ikke lagret eller cachet separat - lesingen går uansett gjennom den vanlige
  katalog-/ingrediens-cachen (`ICacheService`), så en midlertidig unøyaktig telling har samme ferskhet som resten av
  den cachede lista allerede har (ingen ny cache-invalideringsproblemstilling).
- **Sikring mot klientmanipulasjon:** siden `insert_<catalog>`/`update_<catalog>` aldri refererer `@IsSystem`, og
  `usage_count` ikke er en kolonne i det hele tatt, kan ingen av dem endres via skriving uansett hva klienten sender
  (samme Dapper-triks som `ingredient.is_official`). `InsertCatalogCommandHandler` nullstiller i tillegg begge feltene
  på entiteten rett etter id-tildeling, slik at en klient-oppgitt `isSystem: true`/`usageCount: 99` ikke engang blir
  ekko-et tilbake i `201`-svaret (som sender entiteten direkte via `CreatedAtAction`).
- **Sletting:** `DeleteCatalogCommandHandler<T,TKey>` (og `DeleteIngredientCommandHandler`) slår opp raden først - `404`
  hvis den ikke finnes, `409` hvis `IsSystem` er `true` («Systemrader (fra seed-data) kan ikke slettes.») eller
  `UsageCount > 0` («Brukes av {n} {hva} og kan ikke slettes.» (`UsageDescription`)), ellers slettes raden og `204` returneres.
  Tidligere ga katalog-`DELETE` alltid `204` uansett (ingen sjekk); ingrediens-`DELETE` stolte på en generisk FK-`409`
  fra Postgres uten telling i meldingen.

---

## 3. Migreringsskript (`Persistence/Scripts/`)

Kjøres av DbUp (`Persistence/Extensions/DatabaseMigrationExtensions.cs`, `MigrateDatabase`), kalt fra `Program.cs`
før noe annet. Filene er embedded resources, sortert alfabetisk på fullt ressursnavn (tall før bokstaver).
DbUp kjører hvert skript **én gang** og journalfører navnet i `schemaversions`.

### Nummereringskonvensjon

| Område | Nummerserie | Innhold |
| --- | --- | --- |
| Databasekonfigurasjon | `00000`–`09999` | Extensions, roller, skjema. Sjeldent — ingen skript ennå (id-er genereres i applikasjonen). |
| Opprette tabeller | `10000`–`10999` | Én fil per feature-gruppe (ikke per tabell). `10000` = oppskrifter/ingredienser/næring. |
| Endre tabeller | `11000`–`19999` | Én fil per endring, økes fortløpende. |
| Spørringer (lesing) | `20000`–`20999` | `SELECT`-funksjoner. Suffiks-parer med tilhørende `10000`-fil. |
| Endre spørringer | `21000`–`29999` | |
| Kommandoer (skriving) | `30000`–`30999` | `INSERT`/`UPDATE`/`DELETE`-funksjoner. |
| Endre kommandoer | `31000`–`39999` | |
| Seed-data | `Persistence/Scripts/SeedData/seed_<nn>_<beskrivelse>.sql` | Undermappen sorterer etter alle numeriske skript (siffer før bokstaver). Innad i mappen styrer tosifret `<nn>` rekkefølgen (avhengigheter først) — se «Seed-data» under. |

Hver kategori har 1000 plasser til «opprett» og 9000 til «endre» — mer enn nok, siden endringer er langt hyppigere enn
nye feature-grupper.

Bygget så langt (alle for feature-gruppen oppskrifter/ingredienser/næring):

- `10000_recipes_ingredients_nutrition_tables.sql` — alle tabeller (enheter, ingredienskataloger,
  næringsstoffer, `ingredient` med barn, `unconfirmed_ingredient`, oppskrifter).
- `20000_recipes_ingredients_nutrition_queries.sql` — `get_all_*`/`get_*_by_id` for alle katalogtyper og
  ingrediens (inkl. `get_all_ingredient_list_item` med `array_agg`-kolonner og barnefunksjonene), samt per bruker/
  status/telling for ubekreftede ingredienser. De fleste read-funksjonene returnerer `SETOF <tabell>` (Postgres lager en
  rad-type per tabell); de seks katalogtypene og `ingredient` bruker i stedet eksplisitt `RETURNS TABLE` for å kunne
  folde inn en beregnet `usage_count`-kolonne (se «Brukstelling og systemrader» over).
- `30000_recipes_ingredients_nutrition_commands.sql` — `insert_*`/`update_*`/`delete_*` for alle katalogtyper og
  ingrediens (raden + barnefunksjoner), og statusfunksjonene for ubekreftede ingredienser
  (`request_…_review`, `reject_…`, `resolve_…`). `delete_*` og statusfunksjonene returnerer antall berørte rader.

### Seed-data (`Persistence/Scripts/SeedData/`)

Seed-data er vanlige SQL-skript som DbUp kjører (embedded resources, ingen egen kode). De kjører etter alle nummererte skript,
hvert **én gang** (journalført i `schemaversions`), og er skrevet idempotent (`ON CONFLICT DO NOTHING`) i tillegg.

| Skript | Innhold |
| --- | --- |
| `seed_01_units` | 3 enhetstyper (vekt, volum, antall), kjerneenheter (inkl. mg, µg, µg RAE, µg RE, mg-ATE for næringsstoffene) og 30 antall-enheter avledet av Matvaretabellens porsjonstyper. Først, fordi næringsstoffene refererer til enhetene. |
| `seed_02_nutrient_groups` | 15 næringsgrupper (Guid-id-er): fett (med undergruppene mettede/enumettede/flerumettede fettsyrer), karbohydrat, protein, vitaminer (med undergruppene vitamin a–e), mineraler, sporstoffer, annet. |
| `seed_03_nutrient_definitions` | 57 næringsstoffer fra Matvaretabellen, med enhet (`unit_id`) og gruppe (`group_id`) som eksplisitte Guid-er (klartekst i en kommentar per rad) og `sort_order` 1–57 i rekkefølgen fett, karbohydrat, protein, vitaminer, mineraler, sporstoffer, annet. Skrivebeskyttet katalog. |
| `seed_04_ingredient_categories` | 16 ingrediens-kategorier. |
| `seed_05_allergens` | De 14 EU-allergenene + laktose. |
| `seed_06_recipe_categories` | 13 oppskriftskategorier. |
| `seed_10`–`seed_25_ingredients_<kategori>` | 642 ingredienser (én fil per kategori, kuratert 2026-09-23 fra 1565: kun reelle råvarer, uten merkevarer, ferdigretter, hjemmebakst og varianter av samme vare) med næringsverdier (36 110), porsjoner (1 036) og 220 søkeord. Alle tall kommer uendret fra Matvaretabellen. |
| `seed_30_ingredient_derivatives` | 61 derivater (pastaformer i vanlig og fullkorn, sprit, vin, øl, brus, poteter, sukkertyper, ris, urter, kaffe m.m.). Offisielle (`is_official = true`), men varianter av en eksisterende rad fra seed_10–25: `variant_of_ingredient_id`, `source_url`, energi, enhetsvalg, næringsverdier (med opprinnelig verdikilde), porsjoner og søkeord kopieres i SQL fra basen - ingen tall skrives inn. `source_id` er tom (unik per Matvaretabell-matvare). |
| `seed_32_ingredient_allergens` | 271 åpenbare allergenkoblinger på 231 ingredienser (melk/laktose i meieri, gluten i hvete/rug/bygg/havre og produkter av dem, egg, fisk, skalldyr, bløtdyr, nøtter, peanøtter, soya, sesam, selleri, sennep, sulfitt i vin/cider) og arv til derivater. Konservativt: usikre varer (ferdigsauser, pålegg, krydderblandinger, tørket frukt) er ikke tagget. `allergens_reviewed` settes ikke. |
| `seed_31_ingredient_synonyms` | 55 synonymord som `search_keyword`-koblinger på eksisterende ingredienser («kyllingbryst» → kyllingfilet, «fløte» → kremfløte osv.). Kun navn, ingen næringstall. Utvides fortløpende, viktig for skrapte oppskrifter. |

`seed_01`, `04`, `05` og `06` setter `is_system = true` på alle radene sine (2026-09-22, se «Brukstelling og
systemrader» over) - `search_keyword` har ingen seed-fil og starter tom, så ingenting å merke der.

- **Små kataloger har faste id-er** (deterministiske UUIDv7-lignende, generert én gang), slik at senere skript kan referere
  til dem uten å slå opp på navn (navn kan endres av admin). Ingredienser, verdier og søkeord får id fra en midlertidig
  `pg_temp.seed_uuid_v7()` (Postgres 16 har ikke UUIDv7 innebygd) og kobles på Matvaretabellens matvare-id (`source_id`).
- **Utvalg:** kun matvarer som brukes som ingredienser eller i måltider — ikke spedbarnsmat, ferdigretter, kosttilskudd,
  kaker/desserter, snacks. «Diverse matvarer» er fordelt på de andre kategoriene. Admin kan rydde bort det som ikke
  trengs; manglende ingredienser legges til senere (via admin eller nye seed-skript). Produkter kjøpt ferdig i kafé/bakeri
  (12 stk, navn med «kjøpt i kafé/bakeri») er tatt ut. Andre ferdigprodukter og retter (yoghurt med smak, ferdigmat …) er
  bevisst beholdt inntil videre: skillet mellom ingrediens og produkt er ikke avgjort ennå (se `todo.md`).
- **Alle importerte ingredienser har `is_verified = true` og `is_official = true`** (2026-09-22: de er offisielle, ferdig
  næringsbelagte rader fra kilden - kun allergener mangler). Kilden har ingen allergendata; `seed_32_ingredient_allergens` (2026-09-24) tagger bare de **åpenbare** allergenene (se tabellen over; **AI-generert** fra generell kunnskap, ikke fra kilden og ikke manuelt verifisert; «kan inneholde spor av» er bevisst ikke modellert - brukervilkårene pålegger brukeren å sjekke emballasjen), så
  allergenfilteret er en veiledning, ikke en garanti - `allergens_reviewed` (2026-09-22, `DEFAULT false`, fortsatt `false` overalt) skiller «ingen har
  gjennomgått dette» fra «gjennomgått, ingen allergener» i stedet for å overlate det til en tom `allergenIds`-liste, og settes til `true` av admin når tilordningen er
  verifisert komplett (fritt redigerbar selv om ingrediensen er offisiell, se `Documentation/08-api-reference.md`). `is_official`
  låser kildedata mot endring via `PUT` (`IngredientMapper.ValidateOfficialLock`).
- **Næringsverdier** er *per 100 g spiselig del* (Matvaretabellens konvensjon; `edible_part_percent` sier hvor stor del av
  matvaren som er spiselig), og sparsomme: kun målte verdier lagres (`0` = målt som null, manglende rad = ukjent).
- Skriptene ble generert (2026-09-20) av et engangs hjelpescript fra Matvaretabellens rådata (`foods.json`, `nutrients.json`,
  `food-groups.json`). Rådataene og skriptet ligger ikke i repoet (eier har en kopi utenfor repoet, og dataene kan lastes ned på nytt);
  **SQL-skriptene er fasit**. Nye eller endrede data går i nye seed-skript.
  Filene er ca. 4 MB til sammen og kjøres på ca. 12 sekunder mot en tom database.
- **Etter frysepunktet** (første utrulling) endres seed-skript aldri på stedet — nye/endrede data går i et nytt
  seed-skript med høyere `<nn>`.

### Idempotente skript og frysepunkt

Alle setninger er idempotente: `CREATE TABLE/INDEX IF NOT EXISTS`, `CREATE OR REPLACE FUNCTION`. Det hindrer feil ved
gjenkjøring, men **endrer ikke et objekt som allerede finnes** (en eksisterende tabell får ikke nye kolonner av
`IF NOT EXISTS`, og `CREATE OR REPLACE` kan ikke endre returtype).

**Frysepunkt:** så lenge ingen database utenfor en utvikler sin maskin finnes, redigeres `10000`/`20000`/`30000` på
stedet og dev-databasen tilbakestilles (`DROP SCHEMA public CASCADE; CREATE SCHEMA public;` — husk at det også fjerner
`uuid-ossp`-utvidelsen infrastruktur-oppsettet legger inn, som må opprettes på nytt). Fra den første utrullingen
(staging/produksjon) er de tre filene **skrivebeskyttet**, og alle endringer går i `11000`/`21000`/`31000`-seriene.

### Navn: små bokstaver og unike

Alle navnekolonner (`name` i kataloger, ingrediens, ubekreftet ingrediens, `nutrient_group`; `recipe.title`) har
`CHECK (col = lower(col))`, og katalogtabellene har unik indeks på navnet (`ux_<tabell>_name`). `unit.abbreviation` er et
symbol (`µg`, `mg-ATE`) og er unntatt fra små-bokstav-regelen; den har unik indeks på `lower(abbreviation)`. Siden mikrogram
er 0,000001 g er `unit.base_unit_ratio` `numeric(20,10)`. Ubekreftede ingredienser har unik `(created_by_user_id, name)` bortsett fra løste (`Approved`/`Merged`,
som er historikk). Brudd gir `409` via `PostgresExceptionHandler`. `nutrient_definition.name` er unntatt (navn som NaCl
og EPA beholder store bokstaver). Seed-data må derfor være skrevet med små bokstaver.

`unit` har i tillegg `CHECK (abbreviation <> '')` og `CHECK (base_unit_ratio > 0)` (2026-09-22) - et sikkerhetsnett bak
`CatalogValidation` i Application, som er der de faktiske `400`-feilmeldingene kommer fra (`Documentation/08-api-reference.md`).
`ingredient_portion` har unik indeks `(ingredient_id, unit_id)` av samme grunn: to porsjonsdefinisjoner for samme enhet ville
gjort omregningen tvetydig.

### Primærnøkler

Alle genererte ID-er er `uuid`-kolonner, generert i applikasjonslaget med `Guid.CreateVersion7()` (ikke `Guid.NewGuid()`)
for bedre indekslokalitet — Postgres er heap-organisert, så tilfeldig UUID-rekkefølge er langt mindre kostbart her enn i
et tidligere MySQL-prosjekt. `NutrientDefinition.Id` er unntaket: en `text`-kolonne som speiler Matvaretabellens
stabile kode.

---

## 4. Tilkoblingsstreng

`ConnectionStrings:DefaultConnection` i appsettings — `localhost:5433` i dev (`appsettings.Development.json`),
Docker-tjenestenavn `recipe-core-db:5432` i container-/produksjonsoppsett (`appsettings.json`).

---

Sjekk mot faktisk kode ved tvil.
