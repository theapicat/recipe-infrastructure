#!/usr/bin/env python3
import os
import json
from datetime import datetime
from collections import defaultdict

# ---------------------------------------------------------------------------
# Konfigurasjon og katalogregler
# ---------------------------------------------------------------------------

IGNORE_DIRS = {
    'bin', 'obj', 'node_modules', '.next', '.git', '.vs', '.idea', 
    'dist', 'build', '.vscode', 'coverage', '.venv'
}

IGNORE_FILES = {
    'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', '.DS_Store'
}

# Eksakte filnavn uten filending
EXACT_FILENAME_MAP = {
    'dockerfile': ('Konfigurasjon', 'Docker Config'),
    '.dockerignore': ('Konfigurasjon', 'Docker Config'),
    '.env': ('Konfigurasjon', 'Environment Config'),
    '.env.example': ('Konfigurasjon', 'Environment Config'),
}

# Kartlegging basert på filending: (Hovedkategori, Språk / Beskrivelse)
EXT_MAP = {
    # --- REN KODE ---
    '.cs': ('Ren Kode', 'C#'),
    '.tsx': ('Ren Kode', 'React TSX'),
    '.ts': ('Ren Kode', 'TypeScript'),
    '.jsx': ('Ren Kode', 'React JSX'),
    '.js': ('Ren Kode', 'JavaScript'),
    '.py': ('Ren Kode', 'Python'),
    '.html': ('Ren Kode', 'HTML / Scriban'),
    '.scriban': ('Ren Kode', 'HTML / Scriban'),
    '.cshtml': ('Ren Kode', 'C# Razor / HTML'),
    '.css': ('Ren Kode', 'CSS / SCSS'),
    '.scss': ('Ren Kode', 'CSS / SCSS'),
    '.sql': ('Ren Kode', 'SQL Scripts'),
    '.sh': ('Ren Kode', 'Shell Scripts'),

    # --- KONFIGURASJON ---
    '.json': ('Konfigurasjon', 'JSON Config'),
    '.yaml': ('Konfigurasjon', 'YAML Config'),
    '.yml': ('Konfigurasjon', 'YAML Config'),
    '.csproj': ('Konfigurasjon', 'Project Config'),
    '.props': ('Konfigurasjon', 'Project Config'),
    '.targets': ('Konfigurasjon', 'Project Config'),
    '.xml': ('Konfigurasjon', 'XML Config'),
    '.config': ('Konfigurasjon', 'App Config'),

    # --- DOKUMENTASJON ---
    '.md': ('Dokumentasjon', 'Markdown'),
    '.txt': ('Dokumentasjon', 'Text Docs'),
}

# ---------------------------------------------------------------------------
# Hjelpefunksjoner for analysering
# ---------------------------------------------------------------------------

def get_file_info(filename):
    """Returnerer (Kategori, Språk, Ext) basert på filnavn eller filending."""
    lower_name = filename.lower()
    if lower_name in EXACT_FILENAME_MAP:
        cat, lang = EXACT_FILENAME_MAP[lower_name]
        return cat, lang, ''

    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext in EXT_MAP:
        cat, lang = EXT_MAP[ext]
        return cat, lang, ext

    return None, None, None


def analyze_file(file_path, ext, filename):
    """Teller totalt antall linjer, blanke linjer, kommentarer og linjer med innhold."""
    total = 0
    blank = 0
    comment = 0
    content = 0
    in_multiline_comment = False

    lower_name = filename.lower()

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                total += 1
                stripped = line.strip()

                if not stripped:
                    blank += 1
                    continue

                # C-stil kommentarer (C#, JS, TS, CSS, SCSS)
                if ext in ['.cs', '.ts', '.tsx', '.js', '.jsx', '.css', '.scss']:
                    if in_multiline_comment:
                        comment += 1
                        if '*/' in stripped:
                            in_multiline_comment = False
                        continue

                    if stripped.startswith('/*'):
                        comment += 1
                        if not (stripped.endswith('*/') and len(stripped) > 2):
                            in_multiline_comment = True
                        continue

                    if stripped.startswith('//'):
                        comment += 1
                        continue

                # Python kommentarer & docstrings
                elif ext == '.py':
                    if in_multiline_comment:
                        comment += 1
                        if "'''" in stripped or '"""' in stripped:
                            in_multiline_comment = False
                        continue

                    if stripped.startswith("'''") or stripped.startswith('"""'):
                        comment += 1
                        quotes = "'''" if stripped.startswith("'''") else '"""'
                        if stripped.count(quotes) < 2:
                            in_multiline_comment = True
                        continue

                    if stripped.startswith('#'):
                        comment += 1
                        continue

                # HTML / XML / Scriban / Razor
                elif ext in ['.html', '.scriban', '.cshtml', '.xml', '.config']:
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

                # Shell, YAML, Dockerfile, Env
                elif ext in ['.sh', '.yaml', '.yml'] or lower_name in ['dockerfile', '.dockerignore', '.env', '.env.example']:
                    if stripped.startswith('#'):
                        comment += 1
                        continue

                content += 1

    except Exception:
        return 0, 0, 0, 0

    return total, content, comment, blank


# ---------------------------------------------------------------------------
# Hovedlogikk
# ---------------------------------------------------------------------------

def run_counter():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    log_dir = os.path.abspath(os.path.join(script_dir, "..", "progress-log"))

    os.makedirs(log_dir, exist_ok=True)

    # Datastrukturer
    # by_service[service_name] = {'code': 0, 'config': 0, 'doc': 0, 'comm': 0, 'blank': 0, 'files': 0, 'total': 0}
    by_service = defaultdict(lambda: {'code': 0, 'config': 0, 'doc': 0, 'comm': 0, 'blank': 0, 'files': 0, 'total': 0})
    
    # by_category[category] = {'files': 0, 'content': 0, 'comm': 0, 'blank': 0, 'total': 0}
    by_category = defaultdict(lambda: {'files': 0, 'content': 0, 'comm': 0, 'blank': 0, 'total': 0})

    # by_language[lang] = {'category': cat, 'files': 0, 'content': 0, 'comm': 0, 'blank': 0, 'total': 0}
    by_language = defaultdict(lambda: {'category': '', 'files': 0, 'content': 0, 'comm': 0, 'blank': 0, 'total': 0})

    for current_root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        rel_path = os.path.relpath(current_root, project_root)
        service_name = rel_path.split(os.sep)[0] if rel_path != '.' else 'Root'

        for file in files:
            if file in IGNORE_FILES:
                continue

            category, lang, ext = get_file_info(file)

            if category and lang:
                file_path = os.path.join(current_root, file)
                tot, cnt, com, blk = analyze_file(file_path, ext, file)

                # Oppdater per service
                s_stat = by_service[service_name]
                s_stat['files'] += 1
                s_stat['total'] += tot
                s_stat['comm'] += com
                s_stat['blank'] += blk

                if category == 'Ren Kode':
                    s_stat['code'] += cnt
                elif category == 'Konfigurasjon':
                    s_stat['config'] += cnt
                elif category == 'Dokumentasjon':
                    s_stat['doc'] += cnt

                # Oppdater per kategori
                c_stat = by_category[category]
                c_stat['files'] += 1
                c_stat['content'] += cnt
                c_stat['comm'] += com
                c_stat['blank'] += blk
                c_stat['total'] += tot

                # Oppdater per språk
                l_stat = by_language[lang]
                l_stat['category'] = category
                l_stat['files'] += 1
                l_stat['content'] += cnt
                l_stat['comm'] += com
                l_stat['blank'] += blk
                l_stat['total'] += tot

    # Totalsum
    grand_files = sum(s['files'] for s in by_service.values())
    grand_code = sum(s['code'] for s in by_service.values())
    grand_config = sum(s['config'] for s in by_service.values())
    grand_doc = sum(s['doc'] for s in by_service.values())
    grand_comm = sum(s['comm'] for s in by_service.values())
    grand_blank = sum(s['blank'] for s in by_service.values())
    grand_total = sum(s['total'] for s in by_service.values())

    # Hent forrige måling for sammenligning
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
    diff_config = grand_config - previous_data.get('config_lines', grand_config) if previous_data else 0
    diff_doc = grand_doc - previous_data.get('doc_lines', grand_doc) if previous_data else 0
    diff_comm = grand_comm - previous_data.get('comment_lines', grand_comm) if previous_data else 0
    diff_total = grand_total - previous_data.get('total_lines', grand_total) if previous_data else 0

    now = datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
    date_filename = now.strftime("%Y-%m-%d_LOC.md")

    # ---------------------------------------------------------------------------
    # 1. GENERER KONSOLL-UTSKRIFT
    # ---------------------------------------------------------------------------
    cli = []
    cli.append("=" * 88)
    cli.append("📊 KODELINJE-STATISTIKK FOR KJØKKENHYLLA")
    cli.append("=" * 88)
    cli.append(f"Dato: {timestamp_str}")

    if previous_data:
        cli.append("\n📈 ENDRING SIDEN FORRIGE MÅLING:")
        cli.append(f"  • Filer:          {grand_files:<6} ({'+' if diff_files >= 0 else ''}{diff_files})")
        cli.append(f"  • Ren Kode:       {grand_code:<6} ({'+' if diff_code >= 0 else ''}{diff_code})")
        cli.append(f"  • Konfigurasjon:  {grand_config:<6} ({'+' if diff_config >= 0 else ''}{diff_config})")
        cli.append(f"  • Dokumentasjon:  {grand_doc:<6} ({'+' if diff_doc >= 0 else ''}{diff_doc})")
        cli.append(f"  • Kommentarer:    {grand_comm:<6} ({'+' if diff_comm >= 0 else ''}{diff_comm})")
        cli.append(f"  • Totalt:         {grand_total:<6} ({'+' if diff_total >= 0 else ''}{diff_total})")

    cli.append("\n🏷️ OVERORDNET FORDELING (KODE vs KONFIG vs DOK):")
    cli.append("-" * 88)
    cli.append(f"{'Hovedkategori':<22} | {'Filer':<6} | {'Innhold/Linjer':<14} | {'Kommentarer':<11} | {'Totalt':<8}")
    cli.append("-" * 88)
    for cat in ['Ren Kode', 'Konfigurasjon', 'Dokumentasjon']:
        c = by_category[cat]
        cli.append(f"{cat:<22} | {c['files']:<6} | {c['content']:<14} | {c['comm']:<11} | {c['total']:<8}")

    cli.append("\n📁 FORDELING PER MIKROTJENESTE / PROSJEKT:")
    cli.append("-" * 88)
    cli.append(f"{'Prosjekt / Mappe':<28} | {'Filer':<5} | {'Ren Kode':<8} | {'Konfig':<8} | {'Dok':<6} | {'Komm':<6} | {'Totalt':<8}")
    cli.append("-" * 88)

    for service in sorted(by_service.keys()):
        s = by_service[service]
        cli.append(f"{service:<28} | {s['files']:<5} | {s['code']:<8} | {s['config']:<8} | {s['doc']:<6} | {s['comm']:<6} | {s['total']:<8}")

    cli.append("-" * 88)
    cli.append(f"{'TOTALT':<28} | {grand_files:<5} | {grand_code:<8} | {grand_config:<8} | {grand_doc:<6} | {grand_comm:<6} | {grand_total:<8}")
    cli.append("=" * 88)

    cli.append("\n💻 FORDELING PER SPRÅK / FILTYPE:")
    cli.append("-" * 88)
    cli.append(f"{'Språk / Filtype':<22} | {'Kategori':<14} | {'Filer':<5} | {'Linjer':<7} | {'Komm':<6} | {'Blank':<5} | {'Totalt':<7}")
    cli.append("-" * 88)

    for lang, stats in sorted(by_language.items(), key=lambda x: x[1]['content'], reverse=True):
        cli.append(f"{lang:<22} | {stats['category']:<14} | {stats['files']:<5} | {stats['content']:<7} | {stats['comm']:<6} | {stats['blank']:<5} | {stats['total']:<7}")

    cli.append("=" * 88)
    cli_content = "\n".join(cli)

    # ---------------------------------------------------------------------------
    # 2. GENERER MARKDOWN-DOKUMENT
    # ---------------------------------------------------------------------------
    md = []
    md.append(f"# 📊 Kodelinje-status for Kjøkkenhylla")
    md.append(f"**Dato:** {timestamp_str}\n")

    if previous_data:
        md.append("### 📈 Endring siden forrige måling")
        md.append(f"* **Filer:** {grand_files} ({'+' if diff_files >= 0 else ''}{diff_files})")
        md.append(f"* **Ren Kode:** {grand_code} ({'+' if diff_code >= 0 else ''}{diff_code})")
        md.append(f"* **Konfigurasjon:** {grand_config} ({'+' if diff_config >= 0 else ''}{diff_config})")
        md.append(f"* **Dokumentasjon:** {grand_doc} ({'+' if diff_doc >= 0 else ''}{diff_doc})")
        md.append(f"* **Kommentarer:** {grand_comm} ({'+' if diff_comm >= 0 else ''}{diff_comm})")
        md.append(f"* **Totalt (Inkl. blanke):** {grand_total} ({'+' if diff_total >= 0 else ''}{diff_total})\n")

    md.append("## 🏷️ Overordnet Fordeling")
    md.append("| Hovedkategori | Filer | Innhold/Linjer | Kommentarer | Blank | Totalt |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
    for cat in ['Ren Kode', 'Konfigurasjon', 'Dokumentasjon']:
        c = by_category[cat]
        md.append(f"| **{cat}** | {c['files']} | {c['content']} | {c['comm']} | {c['blank']} | {c['total']} |")

    md.append("\n## 📁 Fordeling per Mikrotjeneste / Prosjekt")
    md.append("| Prosjekt / Mappe | Filer | Ren Kode | Konfigurasjon | Dokumentasjon | Kommentarer | Totalt |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")

    for service in sorted(by_service.keys()):
        s = by_service[service]
        md.append(f"| `{service}` | {s['files']} | {s['code']} | {s['config']} | {s['doc']} | {s['comm']} | {s['total']} |")

    md.append(f"| **TOTALT** | **{grand_files}** | **{grand_code}** | **{grand_config}** | **{grand_doc}** | **{grand_comm}** | **{grand_total}** |\n")

    md.append("## 💻 Fordeling per Språk / Filtype")
    md.append("| Språk / Filtype | Kategori | Filer | Linjer | Kommentarer | Blank | Totalt |")
    md.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: |")

    for lang, stats in sorted(by_language.items(), key=lambda x: x[1]['content'], reverse=True):
        md.append(f"| **{lang}** | {stats['category']} | {stats['files']} | {stats['content']} | {stats['comm']} | {stats['blank']} | {stats['total']} |")

    md_content = "\n".join(md)

    # Lagre Markdown-rapport
    md_file_path = os.path.join(log_dir, date_filename)
    with open(md_file_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Lagre JSON for historikk
    current_data = {
        'timestamp': timestamp_str,
        'code_files': grand_files,
        'code_lines': grand_code,
        'config_lines': grand_config,
        'doc_lines': grand_doc,
        'comment_lines': grand_comm,
        'blank_lines': grand_blank,
        'total_lines': grand_total
    }
    with open(history_file, "w", encoding="utf-8") as hf:
        json.dump(current_data, hf, indent=2)

    # Skriv ut i terminalen
    print(cli_content)
    print(f"\n✅ Rapport lagret til: recipe-infrastructure/progress-log/{date_filename}\n")


if __name__ == '__main__':
    run_counter()