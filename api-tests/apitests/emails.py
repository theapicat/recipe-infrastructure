"""Sjekkliste over e-poster testene skal ha utløst, til manuell kontroll i Mailpit.

Testene verifiserer ikke levering selv (bevisst: e-post sjekkes manuelt). I stedet registrerer de hver e-post
som SKAL ha blitt sendt, og suiten skriver en avkrysningsliste til `reports/email-checklist-*.md`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import REPORTS_DIR, Settings


@dataclass
class ExpectedEmail:
    recipient: str
    what: str
    trigger: str
    cleanup: bool = False


@dataclass
class EmailChecklist:
    settings: Settings
    items: list[ExpectedEmail] = field(default_factory=list)
    path: Path | None = None

    def expect(self, recipient: str, what: str, trigger: str) -> None:
        self.items.append(ExpectedEmail(recipient, what, trigger))

    def expect_cleanup(self, recipient: str, what: str, trigger: str) -> None:
        self.items.append(ExpectedEmail(recipient, what, trigger, cleanup=True))

    def write(self) -> Path | None:
        if not self.items:
            return None
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = REPORTS_DIR / f"email-checklist-{stamp}.md"
        regular = [i for i in self.items if not i.cleanup]
        cleanup = [i for i in self.items if i.cleanup]

        lines = [
            f"# E-postsjekkliste — kjøring `{self.settings.run_id}` ({stamp.replace('_', ' ')})",
            "",
            f"Åpne Mailpit: <{self.settings.mailpit_url}> og søk på `{self.settings.run_id}` "
            "(alle testadresser inneholder kjøre-ID-en). Kryss av for hver e-post som faktisk kom.",
            "",
            "Forutsetter at `recipe-notification-service` kjørte under testen. Innholdet vurderes manuelt.",
            "",
            f"## Utløst av testene ({len(regular)})",
            "",
        ]
        for item in regular:
            lines.append(f"- [ ] **{item.what}** → `{item.recipient}` *(utløst av: {item.trigger})*")
        if cleanup:
            lines += [
                "",
                f"## Varsler fra oppryddingen ({len(cleanup)})",
                "",
                "Testbrukerne slettes til slutt via admin-API-et, og det gir hver et «konto slettet»-varsel.",
                "",
            ]
            for item in cleanup:
                lines.append(f"- [ ] **{item.what}** → `{item.recipient}`")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.path = path
        return path
