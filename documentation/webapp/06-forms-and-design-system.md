# 06 – Skjemaer & Designsystem

Dette dokumentet er en sammenslåing av de tidligere `webapp_forms.md` og `design-system.md`, siden de
beskriver to sider av samme sak: den visuelle og strukturelle konvensjonen alle skjermbilder skal følge.

**Viktig avgrensning:** disse mønstrene følges strengt i auth- og admin-delen av appen. De følges **ikke** i
kjernedomene-sidene (oppskrifter, måltidsplan, handleliste, import, samt admin sine whitelist/categories/system-
sider) — de er per nå store, monolittiske `page.tsx`-filer uten `AppFormProvider`/`FormField`/containere. Se
[07 – Kjente problemer](./07-known-issues-and-tech-debt.md#store-monolittiske-sider-uten-backend).

---

## Del A — Skjemaarkitektur

### A.1 Overordnet arkitekturprinsipp

For å sikre at alle sider oppleves identiske for brukeren og er lette å vedlikeholde, skiller vi skarpt
mellom fire ansvarsområder:

```
[ Page Component (page.tsx) ]
       │
       └──> [ AsyncMainContainer / MainContainer ]
                 │
                 └──> [ Feature Form Component (f.eks. ProfileEditForm.tsx) ]
                           │
                           ├──> [ AppFormProvider (FormContext) ]
                           │
                           └──> [ CreateFormContainer / EditFormContainer ]
                                     │
                                     └──> [ FormField / Form Inputs ]
```

1. **Rute-sider (`page.tsx`)** — så rene som mulig. Setter rammen med `AsyncMainContainer`/`MainContainer`,
   henter ev. data server-side.
2. **Skjemakomponenter (`*Form.tsx`)** — isolerte klientkomponenter (`"use client"`) som eier skjematilstand
   (`useForm`), håndterer API-kall via `agentInternal`, og håndterer validering.
3. **Form-containere** (`CreateFormContainer` & `EditFormContainer`) — universelle visualiseringselementer:
   overskrifter, knapper, feilmeldinger (`Alert`), laste-tilstander, bekreftelses-modaler.
4. **Feltkomponenter (`FormField`)** — gjenbrukbare feltinnkapslinger koblet mot skjemakonteksten.

### A.2 Sentrale komponenter og verktøy

**`MainContainer` / `AsyncMainContainer`** (`components/containers/MainContainer.tsx`) — plasseres alltid på
rutenivå for uniform bredde, vertikal polstring (`py`) og laste-indikator.

- `MainContainer` — statisk ramme, standard bredde `lg`.
- `AsyncMainContainer` — som over, men med innebygd `Loader` (`color="sage" type="dots"`) når `loading=true`.

**Laste-tilstand og Suspense:** ikke legg `<Suspense>` i enkeltsider. Bruk segmentets `loading.tsx` (f.eks.
`app/admin/loading.tsx`, som dekker alle admin-sider) — Next pakker da siden i en Suspense-grense automatisk. Data som
lastes i selve klientkomponenten (`agentInternal` + `useEffect`) har egen laste-tilstand (`Loader` i panelet). Unngå
`useSearchParams` i sider der det ikke er nødvendig — det er det som tvinger frem en `<Suspense>` rundt siden
(derfor holder katalogsiden fanevalget i lokal state).

**`FormContext.ts`** — Mantines `createFormContext` for en type-sikker skjemakontekst:

```tsx
"use client";
import { createFormContext } from "@mantine/form";
export const [AppFormProvider, useAppFormContext, useAppForm] = createFormContext<unknown>();
```

Dette lar underkomponenter (som `FormField`) hente verdier/feilmeldinger/endringshåndterere uten prop drilling.

**`CreateFormContainer` vs. `EditFormContainer`:**

| Egenskap           | `CreateFormContainer`                   | `EditFormContainer`                                |
| ------------------ | --------------------------------------- | -------------------------------------------------- |
| Primærbruk         | Nyopprettelse, innlogging, registrering | Redigering av profiler, innstillinger, oppskrifter |
| Lagreknapp         | Sender inn skjemaet umiddelbart         | Åpner bekreftelsesdialog (`Modal`) først           |
| Nullstillingsknapp | Ingen                                   | Valgfri `onReset`-knapp                            |
| Bekreftelsesmodal  | Nei                                     | Ja (`confirmTitle`, `confirmMessage`)              |
| Feilmelding        | Rød `Alert` øverst                      | Rød `Alert` øverst                                 |

Begge har en **`bare`**-prop: uten `Paper`-ramme og tittel, for bruk inne i en `Modal` som allerede har sin egen tittel
(feltene, feilmeldingen, knappene og bekreftelsesdialogen er uendret). Brukes av katalogskjemaene
(`components/admin/catalog/`), som også er et godt eksempel på skjemaer i modaler.

**`FormField`** (`components/forms/common/FormField.tsx`) støtter `type`: `text` (standard), `password`, `email`,
`textarea`, **`select`** (med `data`) og **`number`** (med `min`, `max`, `decimalScale`). Tallfeltet bruker norsk
desimalkomma (punktum aksepteres ved inntasting), avviser negative tall og har ingen +/-knapper. Samme oppsett
deles med tallfelt utenfor skjemaer (f.eks. filtre) via `norwegianNumberProps` (`components/forms/common/numberInputProps.ts`). `extra` tar en
`ReactNode` under feltet — brukt til hjelpetekster (f.eks. «1 dl = 100 ml»). Trenger et skjema en ny felttype, legges den
til her (ikke som en engangsløsning i skjemaet).

### A.3 Steg-for-steg: nytt skjema

**Steg 1 — skjemakomponent** i `components/forms/<domene>/`:

```tsx
"use client";
import { useState } from "react";
import { useForm, isNotEmpty } from "@mantine/form";
import { AppFormProvider } from "@/components/forms/common/FormContext";
import { EditFormContainer } from "@/components/forms/common/EditFormContainer";
import { FormField } from "@/components/forms/common/FormField";
import { agentInternal } from "@/lib/agent/agentInternal";

interface ProfileFormValues {
  firstName: string;
  lastName: string;
}

export const ProfileEditForm = ({ initialData }: { initialData: ProfileFormValues }) => {
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | undefined>();

  const form = useForm<ProfileFormValues>({
    mode: "controlled",
    initialValues: initialData,
    validate: {
      firstName: isNotEmpty("Fornavn må fylles ut"),
      lastName: isNotEmpty("Etternavn må fylles ut"),
    },
  });

  const handleSubmit = async (values: ProfileFormValues) => {
    setLoading(true);
    setErrorMessage(undefined);
    try {
      const res = await agentInternal.put("/api/auth/updateProfile", values);
      if (!res.ok) {
        const errorData = await res.json();
        setErrorMessage(errorData.message || "Kunne ikke oppdatere profilen.");
      }
    } catch {
      setErrorMessage("Nettverksfeil oppstod. Vennligst prøv igjen.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppFormProvider form={form}>
      <EditFormContainer
        title="Rediger Profil"
        description="Oppdater dine personopplysninger her"
        onSubmit={form.onSubmit(handleSubmit)}
        onReset={() => form.reset()}
        loading={loading}
        errorMessage={errorMessage}
      >
        <FormField
          name="firstName"
          label="Fornavn"
          placeholder="Ditt fornavn"
          required
          disabled={loading}
        />
        <FormField
          name="lastName"
          label="Etternavn"
          placeholder="Ditt etternavn"
          required
          disabled={loading}
        />
      </EditFormContainer>
    </AppFormProvider>
  );
};
```

**Steg 2 — plasser i siden** (`page.tsx`):

```tsx
import { AsyncMainContainer } from "@/components/containers/MainContainer";
import { ProfileEditForm } from "@/components/forms/auth/ProfileEditForm";

export default async function ProfilePage() {
  const initialData = { firstName: "Ola", lastName: "Nordmann" };
  return (
    <AsyncMainContainer size="sm" py={30}>
      <ProfileEditForm initialData={initialData} />
    </AsyncMainContainer>
  );
}
```

### A.4 Kommunikasjonsflyt

1. Klientkomponent (`*Form.tsx`) kaller interne route handlers via `agentInternal` (f.eks.
   `PUT /api/auth/updateProfile`).
2. Route handler (bygget med `apiRoute`, se [04](./04-api-integration-and-data-models.md#7-mal-slik-legger-du-til-et-nytt-backend-endepunkt))
   videresender kallet til Gatewayen via `agentExternal`, som legger på token fra sesjonscookien.
3. Gatewayen (YARP) validerer JWT lokalt, renser headers, injiserer `X-User-Id`, ruter videre til
   `recipe-authentication-api` (5001) eller `recipe-core-api` (5002).
4. Svaret returneres samme vei tilbake som en `HttpResponse<T>`-konvolutt; skjemaet leser `message` og setter
   `errorMessage` i `CreateFormContainer`/`EditFormContainer` ved feil.

Se [04 – API-integrasjon](./04-api-integration-and-data-models.md) for det tekniske laget under dette.

---

## Del B — Designsystem

### B.1 Visjonsprinsipper & 60-30-10-regelen

Designet skal formidle en varm, innbydende og sunn matopplevelse — lune krem-/mosebaser kombinert med
matrelaterte jordtoner, i motsetning til et kaldt, korporativt admin-preg.

- **60 % Base (bakgrunn/flater):** lys krem/havre (light), varm mørk mose/skoggulv (dark).
- **30 % Merkevare & struktur (primary):** dempede mose-/salviegrønne toner — navigasjon, primærknapper,
  aktive tilstander, overskrifter.
- **10 % Aksent & handlinger (accent):** varm terrakotta/brent jord — CTA-er, kategoritagger, varsler.

### B.2 Mantine `theme.ts`

Mantine v9 krever en 10-trinns fargetuppel per egendefinert farge. `sage` (mose/salvie, primary) og
`terracotta` (accent):

```ts
import { createTheme, MantineColorsTuple } from "@mantine/core";

const sage: MantineColorsTuple = [
  "#f2f6f3",
  "#e3ece5",
  "#c5d9c9",
  "#a4c4ab",
  "#7ca386", // 4 = Dark Mode Primary
  "#5e8869",
  "#4a6b53", // 6 = Light Mode Primary
  "#3a5441",
  "#2a3e30",
  "#18261c",
];

const terracotta: MantineColorsTuple = [
  "#fdf5f3",
  "#f9ebe6",
  "#f1d3ca",
  "#e6b2a2",
  "#dd8a6e", // 4 = Dark Mode Accent
  "#d07052",
  "#c86a4b", // 6 = Light Mode Accent
  "#a34e34",
  "#7e3a25",
  "#4e2114",
];

export const theme = createTheme({
  primaryColor: "sage",
  primaryShade: { light: 6, dark: 4 },
  colors: { sage, terracotta },
  defaultRadius: "md",
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
  headings: { fontFamily: "-apple-system, ...", fontWeight: "700" },
});
```

### B.3 Fargekoder per modus

| Element              | Light     | Dark                    | Beskrivelse                           |
| -------------------- | --------- | ----------------------- | ------------------------------------- |
| Bakgrunn (60%)       | `#f7f6f2` | `#151a16`               | Hovedbakgrunn                         |
| Kort / flate         | `#ffffff` | `#1e241f`               | Card, Paper, Modal                    |
| Border / skillelinje | `#e2e5df` | `#2c352d`               | Myk ramme, ingen hard kontrast        |
| Hovedtekst           | `#222920` | `#e7ece6`               | Unngår ren hvit/svart                 |
| Sekundærtekst        | `#596356` | `#949f93`               | Metadata (tid, kcal, ingredienser)    |
| Primary (30%)        | `#4a6b53` | `#7ca386`               | Knapper, aktive lenker, primær-badges |
| Primary hover        | `#38523f` | `#93b79c`               | Mus-over                              |
| Accent (10%)         | `#c86a4b` | `#dd8a6e`               | Viktige CTA-er, spesielle tagger      |
| Accent bg/light      | `#f9ebe6` | `rgba(221,138,110,.15)` | Bakgrunn for kategorier               |
| Alert bakgrunn       | `#edf2ee` | `rgba(124,163,134,.12)` | Varselbokser                          |

### B.4 Komponentretningslinjer

**Oppskriftskort (`<Card/>`):** `radius="md"`, alltid `withBorder` (ikke tunge `shadow`-er). Bildeområdet får
tynn `border-bottom`. Kategori-badges (Middag, Frokost) → `color="terracotta" variant="light"`. Status/admin-
badges → `color="sage" variant="filled"`.

**Knapper:** Primærhandling ("Se oppskrift", "Lagre") → `color="sage" variant="filled"`. Sekundærhandling
("Legg i plan", "Avbryt") → `color="sage" variant="outline"`/`"light"`. Kritiske handlinger ("Slett",
"Lås konto") → standard `red` eller `terracotta`.

**Varsler:** Info (måltidsplan/tips) → `color="sage"`. Advarsler/feil → `color="terracotta"`.

### B.5 Tilgjengelighet

Utviklet med hensyn til nedsatt fargesyn (deuteranopi, protanopi):

1. **Ingen funksjon basert kun på farge** — knapper/statuser/lenker skal alltid ha tekstetiketter og/eller
   ikoner (`@tabler/icons-react`).
2. **Høy luminanskontrast** — WCAG AA i både light (`#4a6b53` mot `#f7f6f2`) og dark (`#7ca386` mot `#151a16`).
3. **Ingen skrikende neon i dark mode** — lavere metning, varmere undertoner for å unngå halo-effekt.

### B.6 Merkevarekonsistens

- **Logo/favicon:** stilisert oppskriftshylle/gryte i SVG. Header-logo = symbol + "Kjøkkenhylla" i
  `sage.6`/`sage.4`. Favicon = rent symbol (16×16, 32×32, Apple Touch 180×180).
- **E-postmaler** (i `recipe-notification-service`, separat repo) oversetter Mantine-temaet til inline CSS:
  header-banner `#2a3e30` med hvit logo, bakgrunn `#f7f6f2`, kortflate `#ffffff` med border `#e2e5df`,
  knapper `background-color:#4a6b53; color:#fff; border-radius:8px`.

### B.7 Tekstmarkering og markør

Reglene ligger **ett sted** — `app/globals.css` — og gjelder hele appen. Ikke gjenta dem per komponent.

- **Tekst kan ikke markeres.** `user-select: none` på hele dokumentet: markering av kort, knapper, lenker, tabeller og vanlig
  tekst er mer forstyrrende enn nyttig.
- **Unntak, alltid markerbart:** skjemafelt (`input`, `textarea`, `select`, `contenteditable`). Det er ikke valgfritt —
  Safari blokkerer tasting i felt som har `user-select: none`.
- **Unntak, bevisst opt-in:** legg klassen **`selectable`** på et område der brukeren trolig vil kopiere tekst
  (f.eks. en e-postadresse eller id i en admin-tabell, oppskriftsinstruksjoner, juridiske tekster). Bruk den bare der det er
  et bevisst valg — standarden er at ingenting kan markeres. Ingen eksisterende sider bruker den ennå; se
  [10](./10-backlog.md).
- **Markøren er en vanlig pil over tekst.** Pekefinger (`cursor: pointer`) vises kun på interaktive elementer: lenker,
  knapper, faner, menyvalg, `label[for]`, avkrysning/radio. Mantine setter allerede pointer/not-allowed på sine egne
  komponenter; `globals.css` dekker rene ARIA-roller og native elementer uten å overstyre deaktiverte. Tekstfelt beholder
  tekstmarkøren (I-bjelke) fra nettleseren.

### B.8 Lange lister og paginering

Alle store tabeller (`CatalogTable`, `IngredientTable`) bruker de samme byggeklossene i `components/common/`:
`usePagedItems` (state, klemming av side, sidestørrelse) og `TablePagination`.

- **Sidevelger både over og under tabellen.** Øverst: sammendrag («Viser 1–50 av 1 565»), valg av sidestørrelse
  (**25 / 50 / 100 per side**) og sidevelgeren. Nederst: kun sidevelgeren (ingen duplikat av sammendraget). Lister som
  ikke fyller den minste sidestørrelsen (≤ 25 rader) får ingen paginering i det hele tatt.
- **Bytte av side hopper opp til toppen av tabellen** (kun når den er scrollet ut av syne). Uten dette blir man liggende
  nederst på den nye siden etter å ha trykket «neste» i bunnen. `usePagedItems` gir `containerProps` som settes på
  elementet som omslutter tabell og sidevelgere, og `goToPage` (ikke `setPage` direkte) skal brukes ved sidebytte.
- **Endring av sidestørrelse nullstiller til side 1.** Filtre som gir færre treff klemmer siden til et gyldig område.
- **Bevisst valgt bort: lister som fyller høyden på vinduet** (tabell med egen scrolling). Det ødelegger på mobil, zoom og
  delte vinduer, skjuler rader uforutsigbart, og kolliderer med den vannrette scrollingen (`Table.ScrollContainer`) som
  også hindrer en «sticky» tabelloverskrift. Sidestørrelsesvalget gir samme kontroll uten å gjøre layouten skjør.

### B.9 Skuff (Drawer) for utvidet visning og redigering

Store, sammensatte objekter (i dag ingredienser, `components/admin/ingredients/IngredientDrawer.tsx`) åpnes i en bred **skuff** til
høyre i stedet for på en egen side: listen med filtre og side blir stående bak, og forrige/neste går gjennom den filtrerte listen.
Konvensjoner:

- **Tilstand som en tagget union** (`{ mode: "view" | "edit"; id }` / `{ mode: "create"; baseId }` / `null`) eid av siden som viser listen — ikke
  i URL-en (da trengs verken `useSearchParams` eller `<Suspense>`, se B.7/CLAUDE.md).
- **Ulagrede endringer:** gå bort (lukke, bla, bytte modus) via én `guard(action)` som spør om forkasting når skjemaet er «dirty».
- **Gotcha — Escape:** en dialog som åpnes _av_ et Escape-trykk (f.eks. «Forkast endringene?» fra skuffens `onClose`) må ha
  `closeOnEscape={false}`. Ellers fanger dialogens egen Escape-håndtering det samme tastetrykket og lukker seg umiddelbart, så
  Escape med ulagrede endringer gjør ingenting.
- **Handlinger øverst, ikke nederst.** Lange skjemaer i skuffen har en «sticky» handlingslinje (lagre, avbryt, ev. brytere) rett under
  skuffens topplinje, så man slipper å scrolle ned for å lagre eller avbryte. Skuffen måler høyden på topplinjen og deler den som
  CSS-variabelen `--drawer-header-height`, som handlingslinjen bruker som `top`. Destruktive handlinger (slett) hører hjemme i visningen.
- **Låste felt** (kildedata som ikke skal endres) vises deaktivert med lås-ikon, en forklaring øverst i skjemaet og en vei videre
  (f.eks. «Opprett variant»). Verdiene sendes likevel uendret tilbake ved lagring når `PUT` erstatter alt.
- Skjemaer i skuffen bruker `useForm` direkte (ikke `CreateFormContainer`/`EditFormContainer`, som er laget for enkeltfelts-modaler og
  sider) og lagrer uten ekstra bekreftelsesdialog.
- Innholdet beholdes gjennom lukke-animasjonen (sist viste tilstand), ellers tømmes skuffen før den er borte.
