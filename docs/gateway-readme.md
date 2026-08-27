# 🚪 Recipe Gateway API (`recipe-gateway-api`)

Sentral API Gateway og Reverse Proxy for **Kjøkkenhylla**-økosystemet, bygget med .NET 10 og [YARP (Yet Another Reverse Proxy)](https://www.google.com/search?q=https://microsoft.github.io/reverse-proxy/).

Gateway-en fungerer som systemets primære inngangsdør, og håndterer CORS-retningslinjer, JWT-validering, oversetting av identitet til interne HTTP-headers, samt ruting av REST- og WebSocket/SignalR-trafikk.

---

## 🔑 Hovedfunksjoner

* **Reverse Proxy (YARP)**: Dynamisk ruting av innkommende forespørsler til interne mikrotjenester.
* **Lokal JWT-validering**: Validerer innkommende Bearer-tokens i minnet med en symmetrisk nøkkel (`JWT__KEY`) uten ekstra nettverkskall mot Auth API.
* **Header Sanitization & Injection (Anti-Spoofing)**: Renser innkommende forespørsler for `X-User-Id` og `X-User-Roles` fra klienten, og injiserer verifiserte identitetsverdier fra JWT-claims før videre ruting.
* **WebSocket / SignalR Handshake**: Ekstraherer JWT fra Query String (`?access_token=...`) for sanntidsforbindelser mot `/hubs`.
* **Sentralisert Logging**: Integrert med Serilog for strukturert request-logging til console og **Seq** dashboard (`http://localhost:5341`).

---

## 🛣️ Rute- og Sikkerhetsoversikt

| Rute (Path) | Mål-Cluster | Standard Adresse | Sikkerhetspolicy | Beskrivelse |
| --- | --- | --- | --- | --- |
| `/api/auth/{**catch-all}` | `auth-cluster` | `http://localhost:5001` | *Ingen (Anonym)* | Innlogging, registrering og token-utstedelse. |
| `/api/public/{**catch-all}` | `core-cluster` | `http://localhost:5002` | *Ingen (Anonym)* | Offentlige oppskrifter og søk. |
| `/api/user/{**catch-all}` | `core-cluster` | `http://localhost:5002` | `AuthenticatedUser` | Brukerspesifikke oppskrifter og favoritter. |
| `/api/admin/{**catch-all}` | `core-cluster` | `http://localhost:5002` | `AdminUser` | Administrativ styring av systemet. |
| `/hubs/{**catch-all}` | `core-cluster` | `http://localhost:5002` | `AuthenticatedUser` | SignalR WebSocket-forbindelser for sanntid. |

---


## ⚙️ Konfigurasjon (`appsettings.Development.json`)

Påkrevde innstillinger for at Gateway-en skal starte og rute korrekt:

```json
{
  "Cors": {
    "AllowedOrigins": [ "http://localhost:3000" ]
  },
  "Jwt": {
    "Issuer": "recipe-auth-app",
    "Audience": "recipe-frontend",
    "Key": "din-super-hemmelige-og-lange-dev-nokkel-her-12345!"
  },
  "ReverseProxy": {
    "Routes": { ... },
    "Clusters": { ... }
  },
  "Serilog": {
    "WriteTo": [
      { "Name": "Console" },
      {
        "Name": "Seq",
        "Args": { "serverUrl": "http://localhost:5341" }
      }
    ]
  }
}

```

---

## 🚀 Kjøre applikasjonen lokalt

### Forutsetninger

* [.NET 10.0 SDK](https://dotnet.microsoft.com/)
* `recipe-infrastructure` kjørende (`docker compose up -d` for Seq på port `5341`)

### Oppstart

Naviger til `API`-mappen og kjør med `dotnet watch` for automatisk hot-reload:

```bash
cd API
dotnet watch

```

Gateway-en vil lytte på **`http://localhost:5000`**.

---

## 🛡️ Header Transformation Behavior

Når en beskyttet forespørsel passerer gateway-en, skjer følgende transformasjon automatisk i `ReverseProxyExtensions`:

1. **Rensing**: `X-User-Id` og `X-User-Roles` fjernes fra den innkommende requesten.
2. **Ekstrahering**: `NameIdentifier` (User ID) og `Role` leses fra det validerte JWT tokenet.
3. **Injisering**:
* `X-User-Id: <guid>` legges til på proxy-requesten.
* `X-User-Roles: User,Admin` legges til som en kommaseparert streng.