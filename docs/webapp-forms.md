# internal_docs/webapp-forms.md

## 🏗️ Skjemabygging og Form-Arkitektur i Kjøkkenhylla Web App

Dette dokumentet beskriver den standardiserte skjemastrukturen i `recipe-webapp`. Arkitekturen bygger på prinsipper om moduler, innkapsling, gjenbrukbare layout-containere og type-sikker tilstandshåndtering via Mantine Form.

---

## 1. Overordnet Arkitekturprinsipp

For å sikre at alle sider i applikasjonen oppleves identiske for brukeren og er lette å vedlikeholde, skiller vi skarpt mellom tre ansvarsområder:

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

1. **Rute-sider (`page.tsx`)**: Skal være så rene som mulig. Deres oppgave er å sette rammen rundt siden ved hjelp av `AsyncMainContainer` eller `MainContainer`, samt hente eventuelle data server-side eller håndtere overordnede sidetitler.
2. **Skjemakomponenter (`*Form.tsx`)**: Isolerte klientkomponenter (`"use client"`) som eier skjematilstanden (`useForm`), håndterer API-kall via `agentInternal`, og håndterer validering.
3. **Form-containere (`CreateFormContainer` & `EditFormContainer`)**: Universelle visualiseringselementer som leverer overskrifter, knapper, feil-meldinger (`Alert`), laste-tilstander og bekreftelses-modaler.
4. **Feltkomponenter (`FormField`)**: Gjenbrukbare feltinnkapslinger koblet mot skjemakonteksten.

---

## 2. Sentrale Komponenter og Verktøy

### A. MainContainer og AsyncMainContainer

Plasseres alltid på rutenivå (`page.tsx`) for å sikre at bredde, vertikal polstring (`py`) og laste-indikatorer er 100 % uniform på tvers av applikasjonen.

* **`MainContainer`**: Statisk ramme med standard bredde (`lg`) og vertikal margin.
* **`AsyncMainContainer`**: Utvider `MainContainer` med en innebygd `Loader` når siden eller underliggende data er i en asynkron lastefase.

---

### B. FormContext (`FormContext.ts`)

Vi bruker Mantines `createFormContext` for å opprette en type-sikker skjemakontekst:

```tsx
"use client";

import { createFormContext } from "@mantine/form";

export const [AppFormProvider, useAppFormContext, useAppForm] =
  createFormContext<unknown>();

```

Dette gjør det mulig for underkomponenter (som `FormField`) å hente verdier, feilmeldinger og endringshåndterere uten at vi må sende props manuelt nedover i treet (*prop drilling*).

---

### C. Layout-containere (`CreateFormContainer` vs. `EditFormContainer`)

Vi skiller mellom opprettelse og redigering for å gi brukeren tilpasset interaksjon.

| Egenskap | `CreateFormContainer` | `EditFormContainer` |
| --- | --- | --- |
| **Primærbruk** | Nyopprettelse, innlogging, registrering | Redigering av profiler, innstillinger, oppskrifter |
| **Lagreknapp** | Sender inn skjemaet umiddelbart ved klikk | Åpner først en bekreftelsesdialog (`Modal`) |
| **Nullstillingsknapp** | Ingen | Valgfri `onReset`-knapp for å tilbakestille felter |
| **Bekreftelsesmodal** | Nei | Ja (`confirmTitle` og `confirmMessage`) |
| **Feilmelding** | Viser rød `Alert` øverst ved feil | Viser rød `Alert` øverst ved feil |

---

## 3. Steg-for-steg: Hvordan bygge et nytt skjema

### Steg 1: Lag skjemakomponenten (`*Form.tsx`)

Opprett skjemakomponenten i riktig mappenivå i `components/forms/`.

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

---

### Steg 2: Plasser skjemakomponenten i Siden (`page.tsx`)

Siden skal kun omkranses av `AsyncMainContainer` eller `MainContainer` og rendere skjemakomponenten.

```tsx
import { AsyncMainContainer } from "@/components/containers/MainContainer";
import { ProfileEditForm } from "@/components/forms/account/ProfileEditForm";

export default async function ProfilePage() {
  // Eventuell server-side datahenting kan gjøres her
  const initialData = { firstName: "Ola", lastName: "Nordmann" };

  return (
    <AsyncMainContainer size="sm" py={30}>
      <ProfileEditForm initialData={initialData} />
    </AsyncMainContainer>
  );
}

```

---

## 4. Kommunikasjonsflyt for Skjemaer

Når et skjema sendes inn, følger dataene denne strukturerte løypen i henhold til systemets mikrotjeneste-arkitektur:

1. **Klientkomponent (`*Form.tsx`)**: Kaller interne Route Handlers i Next.js via `agentInternal` (f.eks. `PUT /api/auth/updateProfile`).


2. **Next.js Route Handler (`app/api/.../route.ts`)**: Ekstraherer session/cookies og videresender kallet over HTTP til **Recipe Gateway API** (`http://localhost:5000/api/...`).


3. **Recipe Gateway API (YARP)**: Validerer JWT tokenet lokalt, renser headers, injiserer verifisert `X-User-Id`, og ruter forespørselen videre til bakend-tjenesten (`recipe-authentication-api` på port 5001 eller `recipe-core-api` på port 5002).


4. **Respons**: Svaret returneres samme vei tilbake til klienten, hvor enten en sukksess-melding eller `errorMessage` i `CreateFormContainer`/`EditFormContainer` oppdateres automatisk.