#!/usr/bin/env python3
import os
import json
from datetime import datetime
from collections import defaultdict

# ---------------------------------------------------------------------------
# Konfigurasjon og regler
# ---------------------------------------------------------------------------

IGNORE_DIRS = {
    'bin', 'obj', 'node_modules', '.next', '.git', '.vs', '.idea', 
    'dist', 'build', '.vscode', 'coverage', '.venv'
}

IGNORE_FILES = {
    'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', '.DS_Store'
}

EXT_CATEGORY_MAP = {
    '.cs': 'C#',
    '.tsx': 'React TSX',
    '.ts': 'TypeScript',
    '.jsx': 'React JSX',
    '.js': 'JavaScript',
    '.html': 'HTML / Scriban',
    '.scriban': 'HTML / Scriban',
    '.cshtml': 'C# Razor / HTML',
    '.css': 'CSS / SCSS',
    '.scss': 'CSS / SCSS',
    '.json': 'JSON Config',
    '.yaml': 'YAML Config',
    '.yml': 'YAML Config',
    '.csproj': 'Project Config',
    '.md': 'Markdown',
    '.sh': 'Shell Scripts',
    '.sql': 'SQL Scripts',
}

# ---------------------------------------------------------------------------
# Hjelpefunksjoner for linjetelling
# ---------------------------------------------------------------------------

def analyze_file(file_path, ext):
    """Teller totalt antall linjer, blanke linjer, kommentarer og ren kode."""
    total = 0
    blank = 0
    comment = 0
    code = 0
    in_multiline_comment = False

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                total += 1
                stripped = line.strip()

                if not stripped:
                    blank += 1
                    continue

                if ext in ['.cs', '.ts', '.tsx', '.js', '.jsx', '.css', '.scss']:
                    if in_multiline_comment:
                        comment += 1
                        if '*/' in stripped:
                            in_multiline_comment = False
                        continue

                    if stripped.startswith('/*'):
                        comment += 1
                        if '*/' not in stripped or stripped.endswith('/*'):
                            in_multiline_comment = True
                        continue

                    if stripped.startswith('//'):
                        comment += 1
                        continue

                elif ext in ['.html', '.scriban', '.cshtml']:
                    if in_multiline_comment:
                        comment += 1
                        if '-->' in stripped or '}}' in stripped:
                            in_multiline_comment = False
                        continue

                    if stripped.startswith('<!--') or stripped.startswith('{{#'):
                        comment += 1
                        if not (stripped.endswith('-->') or stripped.endswith('#}}')):
                            in_multiline_comment = True
                        continue

                elif ext in ['.sh', '.yaml', '.yml']:
                    if stripped.startswith('#'):
                        comment += 1
                        continue

                code += 1

    except Exception:
        return 0, 0, 0, 0

    return total, code, comment, blank


# ---------------------------------------------------------------------------
# Hovedlogikk
# ---------------------------------------------------------------------------

def run_counter():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    log_dir = os.path.abspath(os.path.join(script_dir, "..", "progress-log"))

    os.makedirs(log_dir, exist_ok=True)

    by_service = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0, 0])) # [filer, total, kode, kommentar, blank]
    by_language = defaultdict(lambda: [0, 0, 0, 0, 0])

    for current_root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        rel_path = os.path.relpath(current_root, project_root)
        service_name = rel_path.split(os.sep)[0] if rel_path != '.' else 'Root'

        for file in files:
            if file in IGNORE_FILES:
                continue

            _, ext = os.path.splitext(file)
            ext = ext.lower()

            if ext in EXT_CATEGORY_MAP:
                lang = EXT_CATEGORY_MAP[ext]
                file_path = os.path.join(current_root, file)

                tot, cod, com, blk = analyze_file(file_path, ext)

                s_stat = by_service[service_name][lang]
                s_stat[0] += 1
                s_stat[1] += tot
                s_stat[2] += cod
                s_stat[3] += com
                s_stat[4] += blk

                l_stat = by_language[lang]
                l_stat[0] += 1
                l_stat[1] += tot
                l_stat[2] += cod
                l_stat[3] += com
                l_stat[4] += blk

    # Regn ut totaler
    grand_files = sum(sum(stats[0] for stats in s.values()) for s in by_service.values())
    grand_total = sum(sum(stats[1] for stats in s.values()) for s in by_service.values())
    grand_code  = sum(sum(stats[2] for stats in s.values()) for s in by_service.values())
    grand_comm  = sum(sum(stats[3] for stats in s.values()) for s in by_service.values())
    grand_blank = sum(sum(stats[4] for stats in s.values()) for s in by_service.values())

    # Finn forrige logg for sammenligning
    history_file = os.path.join(log_dir, ".history.json")
    previous_data = None
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as hf:
                previous_data = json.load(hf)
        except Exception:
            previous_data = None

    # Beregn endring (Delta)
    diff_files = grand_files - previous_data.get('code_files', grand_files) if previous_data else 0
    diff_code = grand_code - previous_data.get('code_lines', grand_code) if previous_data else 0
    diff_comm = grand_comm - previous_data.get('comment_lines', grand_comm) if previous_data else 0
    diff_total = grand_total - previous_data.get('total_lines', grand_total) if previous_data else 0

    now = datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
    date_filename = now.strftime("%Y-%m-%d_LOC.md")

    # ---------------------------------------------------------------------------
    # 1. GENERER REN KONSOLL-UTSKRIFT (Breddejustert og lesbar i terminal)
    # ---------------------------------------------------------------------------
    cli = []
    cli.append("=" * 80)
    cli.append("📊 KODELINJE-STATISTIKK FOR RECIPEPROJECT")
    cli.append("=" * 80)
    cli.append(f"Dato: {timestamp_str}")

    if previous_data:
        cli.append("\n📈 ENDRING SIDEN FORRIGE MÅLING:")
        cli.append(f"  • Filer:       {grand_files:<6} ({'+' if diff_files >= 0 else ''}{diff_files})")
        cli.append(f"  • Ren Kode:    {grand_code:<6} ({'+' if diff_code >= 0 else ''}{diff_code})")
        cli.append(f"  • Kommentarer: {grand_comm:<6} ({'+' if diff_comm >= 0 else ''}{diff_comm})")
        cli.append(f"  • Totalt:      {grand_total:<6} ({'+' if diff_total >= 0 else ''}{diff_total})")

    cli.append("\n📁 KODE FORDELT PER MIKROTJENESTE / PROSJEKT:")
    cli.append("-" * 80)
    cli.append(f"{'Prosjekt / Mappe':<30} | {'Filer':<6} | {'Kode':<8} | {'Kommentarer':<11} | {'Totalt':<8}")
    cli.append("-" * 80)

    for service in sorted(by_service.keys()):
        s_files = sum(stats[0] for stats in by_service[service].values())
        s_tot   = sum(stats[1] for stats in by_service[service].values())
        s_code  = sum(stats[2] for stats in by_service[service].values())
        s_comm  = sum(stats[3] for stats in by_service[service].values())
        cli.append(f"{service:<30} | {s_files:<6} | {s_code:<8} | {s_comm:<11} | {s_tot:<8}")

    cli.append("-" * 80)
    cli.append(f"{'TOTALT':<30} | {grand_files:<6} | {grand_code:<8} | {grand_comm:<11} | {grand_total:<8}")
    cli.append("=" * 80)

    cli.append("\n💻 KODE FORDELT PER SPRÅK / FILTYPE:")
    cli.append("-" * 80)
    cli.append(f"{'Språk / Kategori':<25} | {'Filer':<6} | {'Kode':<8} | {'Kommentarer':<11} | {'Blank':<6} | {'Totalt':<8}")
    cli.append("-" * 80)

    for lang, stats in sorted(by_language.items(), key=lambda x: x[1][2], reverse=True):
        f_count, tot, cod, com, blk = stats
        cli.append(f"{lang:<25} | {f_count:<6} | {cod:<8} | {com:<11} | {blk:<6} | {tot:<8}")

    cli.append("=" * 80)
    cli_content = "\n".join(cli)

    # ---------------------------------------------------------------------------
    # 2. GENERER MARKDOWN-TABELLER (Til lagring i progress-log .md)
    # ---------------------------------------------------------------------------
    md = []
    md.append(f"# 📊 Kodelinje-status for Kjøkkenhylla")
    md.append(f"**Dato:** {timestamp_str}\n")

    if previous_data:
        md.append("### 📈 Endring siden forrige måling")
        md.append(f"* **Filer:** {grand_files} ({'+' if diff_files >= 0 else ''}{diff_files})")
        md.append(f"* **Ren Kode:** {grand_code} ({'+' if diff_code >= 0 else ''}{diff_code})")
        md.append(f"* **Kommentarer:** {grand_comm} ({'+' if diff_comm >= 0 else ''}{diff_comm})")
        md.append(f"* **Totalt (Inkl. blanke):** {grand_total} ({'+' if diff_total >= 0 else ''}{diff_total})\n")

    md.append("## 📁 Fordelt per Mikrotjeneste / Prosjekt")
    md.append("| Prosjekt / Mappe | Filer | Kode | Kommentarer | Totalt |")
    md.append("| :--- | :---: | :---: | :---: | :---: |")

    for service in sorted(by_service.keys()):
        s_files = sum(stats[0] for stats in by_service[service].values())
        s_tot   = sum(stats[1] for stats in by_service[service].values())
        s_code  = sum(stats[2] for stats in by_service[service].values())
        s_comm  = sum(stats[3] for stats in by_service[service].values())
        md.append(f"| `{service}` | {s_files} | {s_code} | {s_comm} | {s_tot} |")

    md.append(f"| **TOTALT** | **{grand_files}** | **{grand_code}** | **{grand_comm}** | **{grand_total}** |\n")

    md.append("## 💻 Fordelt per Språk / Filtype")
    md.append("| Språk / Kategori | Filer | Kode | Kommentarer | Blank | Totalt |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: |")

    for lang, stats in sorted(by_language.items(), key=lambda x: x[1][2], reverse=True):
        f_count, tot, cod, com, blk = stats
        md.append(f"| **{lang}** | {f_count} | {cod} | {com} | {blk} | {tot} |")

    md_content = "\n".join(md)

    # Lagre Markdown-fil
    md_file_path = os.path.join(log_dir, date_filename)
    with open(md_file_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Lagre JSON-data for fremtidige endringsberegninger
    current_data = {
        'timestamp': timestamp_str,
        'code_files': grand_files,
        'code_lines': grand_code,
        'comment_lines': grand_comm,
        'blank_lines': grand_blank,
        'total_lines': grand_total
    }
    with open(history_file, "w", encoding="utf-8") as hf:
        json.dump(current_data, hf, indent=2)

    # Skriv ut den ryddige konsollversjonen i terminalen
    print(cli_content)
    print(f"\n✅ Rapport lagret til: recipe-infrastructure/progress-log/{date_filename}\n")


if __name__ == '__main__':
    run_counter()