# 🎨 E-postmaler, layout og design

## Malmotor

Malene er Scriban HTML-filer under `Infrastructure/TemplateService/Templates/{Domain}/`, kopiert til
byggets output-mappe via wildcard i `Infrastructure.csproj`:

```xml
<Content Include="TemplateService\Templates\**\*.html">
    <CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory>
</Content>
```

`TemplateRenderService` (`Infrastructure/TemplateService/TemplateRenderService.cs`):

1. Leser malfilen fra disk. Finnes den ikke → `TemplateRenderException` (fail-fast).
2. Parser med Scriban. Syntaksfeil → `TemplateRenderException`.
3. Bygger en `TemplateContext` med modellen importert via `ScriptObject.Import(...)` og en
   `TemplateFileSystemLoader` satt som `TemplateLoader` (nødvendig for at `{{ include ... }}` skal
   fungere - uten en registrert loader kaster Scriban et unntak ved `include`).
4. Rendrer. Kjøretidsfeil (f.eks. manglende modellvariabel) → `TemplateRenderException`.

Se [04-error-handling-and-resilience.md](04-error-handling-and-resilience.md) for hvorfor dette er
fail-fast og ikke fanges/gjenforsøkes.

## Delt layout (`_Layout.html`)

Header, footer, kokkelue-logo og selve HTML-skallet (DOCTYPE, `<head>`, ytre tabell-wrapper) ligger i
**én** delt fil: `Infrastructure/TemplateService/Templates/_Layout.html`. Dette fjernet duplisering av
identisk boilerplate-HTML som tidligere fantes i alle 20 malene.

En vanlig mal inneholder **kun** en tittel og selve innholdsblokken:

```scriban
{{ title = "Velkommen til Kjøkkenhylla!" }}
{{ capture content }}
    <h1 style="...">Velkommen til Kjøkkenhylla!</h1>
    <p style="...">Hei {{ name }},</p>
    ...
{{ end }}
{{ include "_Layout" }}
```

`_Layout.html` bruker `{{ title }}` i `<title>`-taggen og skriver ut `{{ content }}` inne i
innholdsområdet i hovedkortet.

### Footer-override

Standard-footeren ("Med vennlig hilsen, Kjøkkenhylla-teamet") vises med mindre malen setter
`footer_note` **før** `{{ capture content }}`:

```scriban
{{ footer_note = "Denne e-posten ble automatisk generert fra kontaktskjemaet på Kjøkkenhylla." }}
```

Dette brukes i dag av `UserActions/ContactFormAdminNotification.html` og
`AdminActions/PendingEmailAlert.html`.

### Dynamisk tittel

`AdminActions/AdminCustomEmail.html` setter `{{ title = subject }}` i stedet for en statisk streng, siden
emnefeltet kommer fra `AdminCustomEmailRequestedEvent.Subject`.

## Legge til en ny mal

Se sjekklisten i [02-events-and-messaging.md](02-events-and-messaging.md). For selve mal-filen:

1. Opprett `Templates/{Domain}/{TemplateName}.html` med `title`-tildeling +
   `{{ capture content }} ... {{ end }} {{ include "_Layout" }}`-mønsteret over.
2. Sett `footer_note` kun hvis footeren skal avvike fra standarden.
3. Ingen `.csproj`-endring nødvendig - wildcard-mønsteret dekker nye filer automatisk.

## Fargepalett brukt i e-postene

E-postene følger samme merkevarefarger som resten av Kjøkkenhylla-plattformen (definert i sin helhet i
`recipe-webapp`), begrenset til det som faktisk brukes i Scriban-malene:

| Element | Hex | Bruk |
| --- | --- | --- |
| Header-banner | `#2a3e30` | Bakgrunn på logo-banneret i `_Layout.html`. |
| Bakgrunn (e-post) | `#f7f6f2` | Ytre bakgrunn utenfor hovedkortet. |
| Kortflate | `#ffffff` | Bakgrunn på selve e-postkortet, med `#e2e5df`-ramme. |
| Primærknapp | `#4a6b53` | Call-to-action-knapper (bekreft e-post, tilbakestill passord, osv.). |
| Varselboks (tidsfrister/feil) | Bakgrunn `#f9ebe6`, venstre ramme `#c86a4b` | Brukes ved sperre-/slette-/feilvarsler. |
| Infoboks (nøytral) | Bakgrunn `#f2f6f3`, venstre ramme `#4a6b53` | Nøytral tilleggsinformasjon. |
| Hovedtekst | `#222920` | |
| Sekundærtekst / footer | `#596356` | |

> Selve Mantine-temaet, tilgjengelighetsregler og komponentretningslinjer for frontend (`recipe-webapp`)
> vedlikeholdes i det prosjektet, ikke her - denne tabellen er bare oversettelsen til inline CSS som
> trengs for at e-postklienter skal rendre riktig.
