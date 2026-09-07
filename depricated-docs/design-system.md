# 🎨 Designdokument: Kjøkkenhylla (Naturlig & Organisk)

## 1. Visjonsprinsipper & 60-30-10 Regelen

Designet til Kjøkkenhylla skal formidle en **varm, innbydende og sunn matopplevelse**. Vi unngår det kalde, korporative «admin-preg-uttrykket» ved å bruke lune krem- og mosebaser kombinert med matrelaterte jordtoner.

Vi følger **60-30-10-regelen** for fargefordeling for å sikre visuell balanse:

* **60 % Base (Bakgrunn & Flater):** Lys krem/havre i Light Mode, varm mørk mose/skoggulv i Dark Mode. Skaper en behagelig bakgrunn som lar matbildene skinne.
* **30 % Merkevare & Struktur (Primary):** Dempede mose- og salviegrønne toner. Brukes på navigasjon, primærknapper, aktive tilstander og overskrifter.
* **10 % Aksent & Handlinger (Accent):** Varm terrakotta og brent jord. Brukes sparsommelig på viktige oppfordringer, kategoritagger (badges), varsler og interaktive høydepunkter.

---

## 2. Fargepalett & Mantine UI Konfigurasjon

Mantine v9 krever en array med 10 nyanser (index 0–9) for hver egendefinerte farge. Nedenfor er de eksakte fargetuplene for `sage` (mose/salvie) og `terracotta` (terrakotta/brent jord).

### 2.1 Mantine `theme.ts` Oppsett

```typescript
import { createTheme, MantineColorsTuple } from "@mantine/core";

// 10-stegs fargepalett for Mosegrønn / Salvie
const sage: MantineColorsTuple = [
  "#f2f6f3", // 0
  "#e3ece5", // 1
  "#c5d9c9", // 2
  "#a4c4ab", // 3
  "#7ca386", // 4 - Dark Mode Primary
  "#5e8869", // 5
  "#4a6b53", // 6 - Light Mode Primary
  "#3a5441", // 7
  "#2a3e30", // 8
  "#18261c", // 9
];

// 10-stegs fargepalett for Terrakotta / Brent Jord
const terracotta: MantineColorsTuple = [
  "#fdf5f3", // 0
  "#f9ebe6", // 1 - Light Mode Accent Bg
  "#f1d3ca", // 2
  "#e6b2a2", // 3
  "#dd8a6e", // 4 - Dark Mode Accent
  "#d07052", // 5
  "#c86a4b", // 6 - Light Mode Accent
  "#a34e34", // 7
  "#7e3a25", // 8
  "#4e2114", // 9
];

export const theme = createTheme({
  primaryColor: "sage",
  primaryShade: { light: 6, dark: 4 },
  colors: {
    sage,
    terracotta,
  },
  defaultRadius: "md",
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
  headings: {
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    fontWeight: "700",
  },
});

```

---

### 2.2 Fargekoder Per Modus (Light vs Dark)

| Element | Light Mode HEX | Dark Mode HEX | Beskrivelse |
| --- | --- | --- | --- |
| **Bakgrunn (60%)** | `#f7f6f2` | `#151a16` | Hovedbakgrunn for hele siden |
| **Kort / Flate** | `#ffffff` | `#1e241f` | Bakgrunn for kort, paper, modals |
| **Bordere / Skillelinjer** | `#e2e5df` | `#2c352d` | Myke rammer uten hard kontrast |
| **Hovedtekst** | `#222920` | `#e7ece6` | Svært god lesbarhet, unngår ren hvit/svart |
| **Sekundærtekst** | `#596356` | `#949f93` | Metadata (tid, kcal, ingredienser) |
| **Primary (30%)** | `#4a6b53` | `#7ca386` | Knapper, aktive lenker, primær-badges |
| **Primary Hover** | `#38523f` | `#93b79c` | Interaktiv tilstand ved mus-over |
| **Accent (10%)** | `#c86a4b` | `#dd8a6e` | Viktige oppfordringer, spesielle tagger |
| **Accent Bg / Light** | `#f9ebe6` | `rgba(221, 138, 110, 0.15)` | Bakgrunn for oppskriftskategorier |
| **Alert Bakgrunn** | `#edf2ee` | `rgba(124, 163, 134, 0.12)` | Varselbokser og meldinger |

---

## 3. Komponentretningslinjer for Mantine UI

### 3.1 Oppskriftskort (`<Card/>`)

* **Hjørner:** `radius="md"` for et mykt og innbydende uttrykk.
* **Ramme:** Bruk alltid `withBorder` med den tilpassede border-fargen i stedet for tunge skygger (`shadow`).
* **Bilder:** Bildeområdet i kortet bør ha en tynn border under (`border-bottom`) og fylle toppen.
* **Badges:**
* Kategori (Middag, Frokost): Bruk Terrakotta (`color="terracotta"`, `variant="light"`).
* Status/Admin: Bruk Salviegrønn (`color="sage"`, `variant="filled"`).



### 3.2 Knapper (`<Button/>`)

* **Primærhandling ("Se oppskrift", "Lagre"):** `color="sage"`, `variant="filled"`.
* **Sekundærhandling ("Legg i plan", "Avbryt"):** `color="sage"`, `variant="outline"` eller `variant="light"`.
* **Kritiske handlinger ("Slett", "Lås konto"):** Standard Mantine `red` eller `terracotta`.

### 3.3 Varsler & Meldinger (`<Alert/>` / `<Notification/>`)

* Informasjon om måltidsplaner eller tips bruker `color="sage"`.
* Advarsler om inaktivitet eller feilmeldinger bruker `color="terracotta"`.

---

## 4. Tilgjengelighet & Fargesyn (Accessibility)

Siden Kjøkkenhylla er utviklet med spesiell hensyntagen til **nedsatt fargesyn (fargeblindhet som deuteranopi og protanopi)**, gjelder følgende regler strengt:

1. **Ingen funksjon basert kun på farge:** Alle knapper, statuser og lenker skal ledsages av tydelige tekstetiketter og/eller ikoner (f.eks. fra `@tabler/icons-react`).
2. **Høy luminanskontrast:** Fargevalgene i både Light Mode (`#4a6b53` mot `#f7f6f2`) og Dark Mode (`#7ca386` mot `#151a16`) oppfyller WCAG AA-standarden for kontrastforhold på tekst.
3. **Ingen skrikende neon-effekter i Dark Mode:** Dark Mode-fargene har lavere mitting og varmere undertoner for å forhindre "halo-effekt" og visuell tretthet ved kveldslesing.

---

## 5. Merkevarekonsistens: Logo, Favicon & E-post

For å skape en rød tråd mellom frontend (`recipe-webapp`) og e-postene som sendes fra `recipe-notification-service`:

### 5.1 Logo & Favicon Standard

* **Symbol:** En minimalistisk, stilisert oppskriftshylle / gryte i SVG-format.
* **Header Logo:** Symbol + teksten "Kjøkkenhylla" i `sage.6` / `sage.4` farge.
* **Favicon:** Rent symbol uten tekst, tilpasset 16x16, 32x32 og Apple Touch Icon (180x180).

### 5.2 E-postmaler i `recipe-notification-service`

E-postmalene (Scriban HTML) skal oversette Mantine-temaet til rene inline CSS-stiler for maksimal e-postklient-støtte:

```html
<!-- Eksempel på e-postknapp som matcher webappen -->
<a href="{{ action_url }}" 
   style="background-color: #4a6b53; color: #ffffff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block;">
  {{ button_text }}
</a>

```

* **Header-banner i e-post:** Mørk grønn bakgrunn (`#2a3e30`) med hvit logo.
* **Bakgrunn i e-post:** `#f7f6f2` (Light Mode krem).
* **Kortflate i e-post:** `#ffffff` med tynn border `#e2e5df`.