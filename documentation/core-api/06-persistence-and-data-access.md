# Persistens og dataadgang i `recipe-core-api`

---

Per 2026-09-19. Sjekk mot faktisk kode ved tvil.

## 1. Prinsipp

Dapper mot Postgres via Npgsql — ingen EF Core. Alle spørringer/kommandoer er Postgres-funksjoner
(`CREATE FUNCTION`), aldri rå SQL bygget i C#. `Persistence`-prosjektet inneholder kun de generiske
malklassene og de konkrete klassene som kobler en modell til navnet på funksjonene den bruker; selve
SQL-en ligger i migreringsskript (§3), ikke i C#-strenger utover funksjonsnavn og parameterrekkefølge.

Dapper er konfigurert til å matche snake_case-kolonner mot PascalCase C#-egenskaper automatisk
(`DefaultTypeMap.MatchNamesWithUnderscores = true`, satt i `PersistenceExtensions.AddPersistenceServices`)
— ingen kolonne-alias trengs i noen spørring.

---

## 2. Generisk mal: `DbConnection` / `DbReader<T>` / `DbWriter<T>`

`Persistence/Services/`:

- `DbConnection(string connectionString)` — abstrakt basisklasse, åpner en `NpgsqlConnection`.
- `DbReader<T>` — abstrakt, virtuelle `GetAllQuery`/`GetByIdQuery`-strenger (null som standard), generiske
  `GetAllAsync()`/`GetByIdAsync<TId>(id)`. Kaster `DbQueryMissingException<T>` hvis en query ikke er
  overstyrt.
- `DbWriter<T>` — samme mønster for `InsertCommand`/`UpdateCommand`/`DeleteCommand`, kaster
  `DbCommandMissingException<T>` ved manglende overstyring.

Hver modell får sitt eget par i `Persistence/Implementation/` — kun overstyring av query/command-strenger,
ingen annen logikk:

```csharp
public class AllergenReader(IConfiguration configuration)
    : DbReader<Allergen>(configuration.GetConnectionString("DefaultConnection")!)
{
    public override string? GetAllQuery { get; } = "SELECT * FROM get_all_allergen();";
    public override string? GetByIdQuery { get; } = "SELECT * FROM get_allergen_by_id(@Id);";
}
```

Ingen `Interfaces/`-fil per modell med mindre en spesifikk modell trenger en metode utover det
`DbReader<T>`/`DbWriter<T>` allerede gir (ingen av de seks katalogmodellene gjør det per denne datoen).

Bygget så langt: `IngredientCategoryReader`/`Writer`, `AllergenReader`/`Writer`,
`SearchKeywordReader`/`Writer`, `UnitTypeReader`/`Writer`, `UnitReader`/`Writer`,
`RecipeCategoryReader`/`Writer`. Registrert i DI via `PersistenceExtensions.AddPersistenceServices()`, mot
den åpne generiske typen (`DbReader<Allergen>` → `AllergenReader`), ikke et eget grensesnitt.

---

## 3. Migreringsskript (`Persistence/Scripts/`)

Kjøres av DbUp (`Persistence/Extensions/DatabaseMigrationExtensions.cs`, `MigrateDatabase`), kalt fra
`Program.cs` før noe annet. Filene er embedded resources, oppdaget og sortert alfabetisk på fullt
ressursnavn av DbUp.

### Nummereringskonvensjon

| Område | Nummerserie | Innhold |
| --- | --- | --- |
| Databasekonfigurasjon | `00000`–`00999` | Extensions, roller, skjema. Sjeldent brukt — ingen skript her ennå siden ID-er genereres i applikasjonslaget (UUIDv7), ikke av Postgres. |
| Opprette tabeller | `10000`+ | Én fil per feature-gruppe (ikke per tabell). `10000` = oppskrifter/ingredienser/næring. |
| Endre tabeller | `11000`+ | Løper uavhengig av `10000`-serien, økes for hver faktiske endring. |
| Opprette prosedyrer/funksjoner | `20000`+ | Suffiks-parer med tilhørende `10000`-fil (`20000` hører til `10000`). |
| Endre prosedyrer | `21000`+ | Parallelt med `11000`. |
| Seed-data | `Persistence/Scripts/SeedData/seed_<beskrivelse>.sql` | Ikke tallprefiks — undermappen sorterer uansett etter alle numeriske skript siden tall < bokstaver i DbUp sin alfabetiske sortering. Ingen seed-skript finnes ennå. |

Bygget så langt:

- `10000_recipes_ingredients_nutrition_tables.sql` — alle tabeller for enheter, ingredienskataloger,
  næringsstoffdefinisjon, `ingredient`, og oppskrift-tabellene (`recipe`, `recipe_step`,
  `recipe_ingredient`, `recipe_category`).
- `20000_recipes_ingredients_nutrition_procedures.sql` — 30 funksjoner (5 hver) for de seks enkle
  katalogene: `get_all_<tabell>()`, `get_<tabell>_by_id(p_id)`, `insert_<tabell>(...)`,
  `update_<tabell>(...)`, `delete_<tabell>(p_id)`. Alle read-funksjoner returnerer `SETOF <tabell>` —
  Postgres oppretter automatisk en rad-type per tabell, så `get_all` (mange rader) og `get_by_id` (0/1
  rad) kan dele samme returform.

**⚠️ Planlagt — ikke bygget:** prosedyrer for `nutrient_definition` (hierarki), `ingredient` (tung modell
med næringsverdier/porsjoner/allergen-koblinger — parameterisert `search`-funksjon ble vurdert, men droppet
til fordel for full cache + LINQ-filtrering i `Application`, se
[`03-cqrs-and-mediatr.md`](03-cqrs-and-mediatr.md)), og `unconfirmed_ingredient`.

### Primærnøkler

Alle genererte ID-er er `uuid`-kolonner, generert i applikasjonslaget med `Guid.CreateVersion7()` (ikke
`Guid.NewGuid()`) for bedre indekslokalitet — Postgres er heap-organisert (ikke klustret på primærnøkkel
som MySQL/InnoDB), så tilfeldig UUID-rekkefølge er langt mindre kostbart her enn i et tidligere
MySQL-prosjekt der dette ga reelle ytelsesproblemer. `NutrientDefinition.Id` er unntaket — en `text`-kolonne
som speiler Matvaretabellens egen stabile kode, ikke en generert `Guid` (se `RECIPE_BACKEND_NOTES.md`).

---

## 4. Tilkoblingsstreng

`ConnectionStrings:DefaultConnection` i appsettings — `localhost:5433` i dev
(`appsettings.Development.json`), Docker-tjenestenavn `recipe-core-db:5432` i container-/produksjonsoppsett
(`appsettings.json`). Ingen hemmeligheter i disse filene utover dev-passord som allerede er ment å være
lokale.

---

Sjekk mot faktisk kode ved tvil.
