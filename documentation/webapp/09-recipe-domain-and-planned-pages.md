# 09 – Oppskriftsdomenet: Modell & Planlagte Sider

**Status: modellene i seksjon 1 er skrevet og pushet (2026-09-16). Sidene i seksjon 2 er ikke bygget ennå —
dette er en plan, ikke en beskrivelse av eksisterende kode.**

## 1. Datamodellene

`lib/models/recipes/`, `lib/models/ingredients/` og `lib/models/units/` er nå fylt med de første DTO-ene for
oppskrifts-domenet, designet i samarbeid mellom bruker og Claude. Se `RECIPE_BACKEND_NOTES.md` i repo-roten for
full begrunnelse bak hvert valg (bruker-eierskap, Matvaretabellen som næringskilde, hierarkisk
næringsstoff-katalog, osv.) — den filen er skrevet for å kopieres til `recipe-core-api`, men gjelder like mye
her siden frontend-DTO-ene speiler C#-modellene 1:1. Et speilende sett C#-modeller ligger i
`csharp-models-draft/` i repo-roten (midlertidig, til de flyttes til `recipe-core-api`).

Kort oppsummert: `Recipe` er strengt bruker-eid (`ownerUserId`), skiller manuelle fra skrapede oppskrifter via
`RecipeSource`, og henter ingredienser fra en delt `Ingredient`-katalog (med en `UnconfirmedIngredient`-vei for
brukerinnsendte ingredienser som ikke finnes der). Næring er modellert som en egen `NutrientDefinition`-katalog
+ sparsomme `IngredientNutrientValue`-rader (ikke et fast sett faste felt), fordi kildedataen fra
Matvaretabellen er hierarkisk og de fleste matvarer bare har verdi for et delsett av næringsstoffene.

Følger mønsteret fra [08 – Forslag: mappestruktur](./08-model-and-component-structure-proposal.md): én fil per
DTO, gruppert på domene, `page.tsx` tynn + feature-komponenter når sidene faktisk bygges.

## 2. Planlagte sider (ikke bygget)

**Eksisterende oppskriftssider forblir som de er for nå** — `app/(user)/user/recipes/*` fortsetter å bruke
mock-data til de faktisk kobles mot ekte backend (se [07 – Kjente problemer](./07-known-issues-and-tech-debt.md)
for status). Ingen endring i dem som følge av modellarbeidet i seksjon 1.

Nye sider som er planlagt basert på modelldesign-samtalen:

- **`app/(user)/user/ingredients/` (ny)** — søkbar oppslagsside der brukeren kan finne en ingrediens og se
  næringsinnhold, porsjonsstørrelser og en lenke til den offisielle Matvaretabellen-siden (`Ingredient.sourceUrl`).
  Tenkt som frittstående oppslag, ikke bundet til en oppskrift — "hva får jeg av å ete to gulrøtter"-type bruk.
- **Adminpaneler for ingrediens-/næringsdomenet (nye)** — utvider dagens `app/admin/categories/page.tsx`
  (i dag én mock-side med faner for kategorier/ingredienser/enheter) til å faktisk dekke alle katalogene fra
  modellen: `IngredientCategory`, `RecipeCategory`, `Allergen`, `UnitType`/`Unit`, `SearchKeyword`, og en egen
  flate for `NutrientDefinition`-katalogen. Admin skal også kunne godkjenne/behandle `UnconfirmedIngredient`-køen
  brukere legger til.

Ingen av disse er startet — dette er en oversikt for å ikke miste kontekst mellom sesjoner, ikke en beskrivelse
av kode som finnes.
