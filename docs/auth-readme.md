# 🔑 recipe-authentication-api

Identitets- og autentiseringstjeneste for **Kjøkkenhylla**-økosystemet, bygget med .NET, ASP.NET Core Identity og **OpenIddict**. Tjenesten eier `recipe_auth_db` (PostgreSQL på port 5432) og håndterer brukerregistrering, profiladministrasjon, e-postverifisering samt utstedelse og fornyelse av OAuth2/OIDC JWT-tokens.

---

## 🛠️ Arkitektur og Ruting

Auth API-et kjører lokalt på **port 5001**. Klienter kommuniserer med tjenesten gjennom **recipe-gateway-api** (port 5000), som ruter alle `/api/auth/*`-forespørsler videre til auth-tjenesten.

| Endepunkt (Gjennom Gateway) | Metode | Content-Type | Autentisering | Beskrivelse |
| --- | --- | --- | --- | --- |
| `/api/auth/connect/token` | `POST` | `application/x-www-form-urlencoded` | Anonym | Utsteder og fornyer JWT access tokens og refresh tokens via OpenIddict. Oppdaterer `LastLoginAt`. |
| `/api/auth/account/register` | `POST` | `application/x-www-form-urlencoded` / `application/json` | Anonym | Registrerer ny bruker og returnerer `UserProfileResponse` med bekreftelsestoken. |
| `/api/auth/account/me` | `GET` | *Ingen* | Bearer Token | Henter profilinformasjon for den innloggede brukeren (`UserProfileResponse`). |
| `/api/auth/account/profile` | `PUT` | `application/json` | Bearer Token | Oppdaterer fornavn og etternavn. Returnerer oppdatert `UserProfileResponse`. |
| `/api/auth/account/change-password` | `POST` | `application/json` | Bearer Token | Endrer passord for innlogget bruker med eksisterende passord. |
| `/api/auth/account/set-password` | `POST` | `application/json` | Bearer Token | Oppretter lokalt passord for innloggede brukere som opprinnelig registrert via Google. |
| `/api/auth/account/complete-welcome` | `GET` | *Ingen* | Bearer Token | Merker velkomstsiden som fullført (`WelcomeCompleted = true`). |
| `/api/auth/account/resend-confirmation` | `POST` | *Ingen* | Bearer Token | Trigger ny bekreftelsese-post for den innloggede brukeren. |
| `/api/auth/account/confirm-email` | `POST` | `application/json` | Anonym | Bekrefter e-postadresse via `UserId` og token mottatt i e-postlenke. |
| `/api/auth/account/recover` | `POST` | `application/json` | Anonym | Genererer token for tilbakestilling av passord for uinnloggede brukere. |
| `/api/auth/account/reset-password` | `POST` | `application/json` | Anonym | Tilbakestiller passord ved hjelp av mottatt token fra e-post. |
| `/api/auth/account/me` | `DELETE` | *Ingen* | Bearer Token | Permanent sletting av den innloggede brukerens konto og data. |

---

## 📋 DTO-Spesifikasjoner

### 1. `RegisterRequest`

Brukes ved brukerregistrering på `POST /api/auth/account/register`. Endepunktet godtar både JSON og `application/x-www-form-urlencoded`.

```csharp
public class RegisterRequest
{
    [Required, EmailAddress]
    public string Email { get; set; } = string.Empty;

    [Required, MinLength(8)]
    public string Password { get; set; } = string.Empty;

    [Required]
    public string FirstName { get; set; } = string.Empty;

    [Required]
    public string LastName { get; set; } = string.Empty;
}

```

---

### 2. `UserProfileResponse`

Standard respons som returneres ved registrering, profilhenting (`GET /account/me`), profiloppdatering (`PUT /account/profile`) og velkomstfullføring.

```csharp
public class UserProfileResponse
{
    public string UserId { get; set; } = string.Empty;
    public string UserName { get; set; } = string.Empty;
    public string Email { get; set; } = string.Empty;
    public string FirstName { get; set; } = string.Empty;
    public string LastName { get; set; } = string.Empty;
    public string Role { get; set; } = string.Empty;

    // Google- & Passord-flagg
    public bool HasPassword { get; set; }
    public bool IsGoogleAccount { get; set; }

    // Status & Metadata
    public bool IsEmailConfirmed { get; set; }
    public bool WelcomeCompleted { get; set; }
    public bool IsLocked { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? LastModifiedAt { get; set; }
    public DateTime? LastLoginAt { get; set; }
}

```

---

### 3. Skjema- og Sikkerhets-DTO-er

```csharp
// PUT /api/auth/account/profile
public class UpdateProfileRequest
{
    [Required(ErrorMessage = "Fornavn er påkrevd.")]
    public string FirstName { get; set; } = string.Empty;

    [Required(ErrorMessage = "Etternavn er påkrevd.")]
    public string LastName { get; set; } = string.Empty;
}

// POST /api/auth/account/change-password
public class ChangePasswordRequest
{
    [Required]
    public string CurrentPassword { get; set; } = string.Empty;

    [Required, MinLength(8)]
    public string NewPassword { get; set; } = string.Empty;
}

// POST /api/auth/account/set-password (for Google-brukere utan eksisterende passord)
public record SetPasswordRequest(
    [Required, MinLength(8)] string NewPassword
);

// POST /api/auth/account/confirm-email (fra lenke i e-post)
public record ConfirmEmailRequest(
    [Required] string UserId,
    [Required] string Token
);

// POST /api/auth/account/recover
public record RecoverPasswordRequest(
    [Required, EmailAddress] string Email
);

// POST /api/auth/account/reset-password
public record ResetPasswordRequest(
    [Required, EmailAddress] string Email,
    [Required] string Token,
    [Required, MinLength(8)] string NewPassword
);

```

---

## 🔑 OAuth2 Token Exchange (`/connect/token`)

OpenIddict håndterer token-utstedelse og fornyelse på endepunktet `/connect/token`. Forespørsler **må** sendes som `application/x-www-form-urlencoded`.

Gyldige klient-ID-er:

* `recipe-web-app`
* `recipe-mobile-app`

### A. Innlogging (Password Grant)

* **URL**: `POST /connect/token`
* **Header**: `Content-Type: application/x-www-form-urlencoded`
* **Body**:
* `grant_type`: `password`
* `username`: `bruker@example.com`
* `password`: `DittPassord123!`
* `client_id`: `recipe-web-app`



### B. Fornyelse av Token (Refresh Token Grant)

* **URL**: `POST /connect/token`
* **Header**: `Content-Type: application/x-www-form-urlencoded`
* **Body**:
* `grant_type`: `refresh_token`
* `refresh_token`: `<Mottatt refresh_token>`
* `client_id`: `recipe-web-app`



### C. Sikkerhet og Inaktivitetshåndtering

Ved alle vellykkede kall til `/connect/token` (både `password` og `refresh_token` grants), utfører API-et følgende operasjoner i bakgrunnen:

1. **Oppdaterer aktivitet:** Setter `LastLoginAt = DateTime.UtcNow` i databasen for å forhindre at aktive brukere flagges for inaktivitet (f.eks. ved 6-måneders grensen).
2. **Sjekker kontostatus:** Verifiserer at kontoen ikke er manuelt eller automatisk sperret (`userManager.IsLockedOutAsync`). Sperrede brukere vil umiddelbart få avvist sin token-fornyelse.
3. **Oppdaterer Claims:** Ved fornyelse opprettes `ClaimsPrincipal` på nytt, slik at eventuelle oppdaterte roller, fornavn eller etternavn gjenspeiles i det nye access-tokenet.

### D. Vellykket Respons (`200 OK`)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "eyJhbGciOiJIUzI1...",
  "scope": "openid profile roles offline_access"
}

```

### E. Feilrespons fra OpenIddict (`400 Bad Request` / `401 Unauthorized`)

```json
{
  "error": "invalid_grant",
  "error_description": "Ugyldig e-post eller passord."
}

```

Standard `error`-koder:

* `invalid_grant`: Feil brukernavn/passord, kontoen er sperret, eller utløpt/ugyldig refresh token.
* `unsupported_grant_type`: Ugyldig `grant_type` (må være `password` eller `refresh_token`).
* `invalid_client`: Ugyldig eller manglende `client_id`.

---

## 💻 Frontend Integration (JavaScript / Next.js)

### 1. Registrering med `application/x-www-form-urlencoded`

```typescript
export async function registerUser(formData: { email: string; password: string; firstName: string; lastName: string }) {
  const body = new URLSearchParams();
  body.append('Email', formData.email);
  body.append('Password', formData.password);
  body.append('FirstName', formData.firstName);
  body.append('LastName', formData.lastName);

  const response = await fetch('http://localhost:5000/api/auth/account/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: body.toString(),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.message || 'Registrering mislyktes');
  }

  return await response.json(); // Returnerer { user: UserProfileResponse, confirmationToken: string }
}

```

### 2. Innlogging & Feilhåndtering mot `/connect/token`

```typescript
export async function loginUser(email: string, password: string) {
  const body = new URLSearchParams();
  body.append('grant_type', 'password');
  body.append('username', email);
  body.append('password', password);
  body.append('client_id', 'recipe-web-app');

  const response = await fetch('http://localhost:5000/api/auth/connect/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: body.toString(),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error_description || data.error || 'Innlogging mislyktes');
  }

  return data; // Returnerer access_token og refresh_token
}

```

---

## ⚙️ Utvikleroppsett & Kjøring

1. **Infrastruktur**: Sørg for at PostgreSQL kjører i Docker via `recipe-infrastructure` (`recipe-auth-db` på port 5432).
2. **Databasemigrasjoner**:

```bash
dotnet ef database update

```

3. **Kjør applikasjonen**:

```bash
dotnet watch

```

API-et lytter på **`http://localhost:5001`** og er tilgjengelig via Gateway på **`http://localhost:5000/api/auth/*`**.

---

## 🚧 Work in Progress (Planlagte Funksjoner)

Følgende funksjonalitet og endepunkter er under utrulling for Google OAuth2 og e-postutsending:

| Endepunkt (Gjennom Gateway) | Metode | Status | Beskrivelse |
| --- | --- | --- | --- |
| `/api/auth/account/google-login` | `GET` | 🚧 Planlagt | Initiere OAuth2-innloggingsflyt mot Google. |
| `/api/auth/account/google-callback` | `GET` | 🚧 Planlagt | Håndterer retursvar fra Google, oppretter/kobler `ApplicationUser` og utsteder JWT-tokens via OpenIddict. |
| **E-posttjeneste (`IEmailService`)** | - | 🚧 Planlagt | Integrasjon mot SMTP/Mail-provider for automatisk utsending av e-postbekreftelser og passordtilbakestilling. |