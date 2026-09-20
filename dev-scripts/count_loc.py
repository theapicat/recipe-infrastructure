#!/usr/bin/env python3
"""Teller kodelinjer for Kjøkkenhylla-prosjektet og logger progresjonen over tid."""
import argparse
import json
import math
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Konfigurasjon og katalogregler
# ---------------------------------------------------------------------------

IGNORE_DIRS = {
    'bin', 'obj', 'node_modules', '.next', '.git', '.vs', '.idea',
    'dist', 'build', '.vscode', 'coverage', '.venv', '__pycache__', '.pytest_cache'
}

IGNORE_FILES = {
    'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', '.DS_Store'
}

# Hele undertrær som skal hoppes over fullstendig (relativt til prosjektroten).
# recipe-infrastructure/documentation/ er en SPEILING av Documentation/-mappene
# i de andre tjenestene (se hovedreadme sitt vedlikeholdsavsnitt) - uten dette
# unntaket ville alt innholdet der blitt telt to ganger.
IGNORE_PATH_PREFIXES = {
    os.path.join('recipe-infrastructure', 'documentation'),
    # Genererte kjørerapporter fra API-testene (e-postsjekklister), ikke kode.
    os.path.join('recipe-infrastructure', 'api-tests', 'reports'),
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

# Kode som ligger i en av disse mappene, eller har et av disse filnavnmønstrene, telles som «Tester» i stedet for
# «Ren Kode» (den FLYTTES, så ingenting telles to ganger). Dokumentasjon og konfigurasjon i samme mapper beholder sin
# egen kategori.
TEST_DIR_NAMES = {'tests', 'test', '__tests__', 'api-tests'}
TEST_FILE_SUFFIXES = ('.test.ts', '.test.tsx', '.spec.ts', '.spec.tsx')

SPARK_CHARS = '▁▂▃▄▅▆▇█'

CYAN = '\033[0;36m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
LOG_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', 'progress-log'))
HISTORY_PATH = os.path.join(LOG_DIR, 'history.jsonl')
DASHBOARD_PATH = os.path.join(LOG_DIR, 'dashboard.md')


# ---------------------------------------------------------------------------
# Filanalyse (uendret logikk fra forrige versjon)
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


def is_test_file(rel_dir, filename):
    """True hvis filen er testkode: ligger under en testmappe (Tests/, tests/, api-tests/, *.Tests/) eller matcher et testnavn."""
    lower_name = filename.lower()
    if lower_name.endswith(TEST_FILE_SUFFIXES) or lower_name.startswith('test_') or lower_name == 'conftest.py':
        return True
    parts = [p.lower() for p in rel_dir.split(os.sep) if p and p != '.']
    return any(p in TEST_DIR_NAMES or p.endswith('.tests') for p in parts)


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

                elif ext in ['.sh', '.yaml', '.yml'] or lower_name in ['dockerfile', '.dockerignore', '.env', '.env.example']:
                    if stripped.startswith('#'):
                        comment += 1
                        continue

                content += 1

    except Exception:
        return 0, 0, 0, 0

    return total, content, comment, blank


# ---------------------------------------------------------------------------
# Prosjektskanning
# ---------------------------------------------------------------------------

def scan_project():
    by_service = defaultdict(lambda: {'code': 0, 'test': 0, 'config': 0, 'doc': 0, 'comments': 0, 'blank': 0, 'files': 0, 'total': 0})
    by_category = defaultdict(lambda: {'files': 0, 'content': 0, 'comments': 0, 'blank': 0, 'total': 0})
    by_language = defaultdict(lambda: {'category': '', 'files': 0, 'content': 0, 'comments': 0, 'blank': 0, 'total': 0})

    for current_root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        rel_path = os.path.relpath(current_root, PROJECT_ROOT)

        if any(rel_path == p or rel_path.startswith(p + os.sep) for p in IGNORE_PATH_PREFIXES):
            dirs[:] = []
            continue

        service_name = rel_path.split(os.sep)[0] if rel_path != '.' else 'Root'

        for file in files:
            if file in IGNORE_FILES:
                continue

            category, lang, ext = get_file_info(file)
            if not (category and lang):
                continue

            if category == 'Ren Kode' and is_test_file(rel_path, file):
                category, lang = 'Tester', f'{lang} (tester)'

            file_path = os.path.join(current_root, file)
            tot, cnt, com, blk = analyze_file(file_path, ext, file)

            s = by_service[service_name]
            s['files'] += 1
            s['total'] += tot
            s['comments'] += com
            s['blank'] += blk
            if category == 'Ren Kode':
                s['code'] += cnt
            elif category == 'Tester':
                s['test'] += cnt
            elif category == 'Konfigurasjon':
                s['config'] += cnt
            elif category == 'Dokumentasjon':
                s['doc'] += cnt

            c = by_category[category]
            c['files'] += 1
            c['content'] += cnt
            c['comments'] += com
            c['blank'] += blk
            c['total'] += tot

            l = by_language[lang]
            l['category'] = category
            l['files'] += 1
            l['content'] += cnt
            l['comments'] += com
            l['blank'] += blk
            l['total'] += tot

    totals = {
        'files': sum(s['files'] for s in by_service.values()),
        'code_lines': sum(s['code'] for s in by_service.values()),
        'test_lines': sum(s['test'] for s in by_service.values()),
        'config_lines': sum(s['config'] for s in by_service.values()),
        'doc_lines': sum(s['doc'] for s in by_service.values()),
        'comment_lines': sum(s['comments'] for s in by_service.values()),
        'blank_lines': sum(s['blank'] for s in by_service.values()),
    }
    totals['total_lines'] = (totals['code_lines'] + totals['test_lines'] + totals['config_lines'] + totals['doc_lines']
                              + totals['comment_lines'] + totals['blank_lines'])

    return {
        'totals': totals,
        'by_category': dict(by_category),
        'by_service': dict(by_service),
        'by_language': dict(by_language),
    }


# ---------------------------------------------------------------------------
# Historikk (progress-log/history.jsonl - én linje per måling)
# ---------------------------------------------------------------------------

def load_history():
    entries = []
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    entries.sort(key=lambda e: e.get('timestamp', ''))
    return entries


def append_history(entry):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(HISTORY_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def measured_days_last_n(entries, now, n=7):
    cutoff = now.date() - timedelta(days=n - 1)
    dates = set()
    for e in entries:
        try:
            ts = datetime.fromisoformat(e['timestamp'])
        except Exception:
            continue
        if ts.date() >= cutoff:
            dates.add(ts.date())
    return len(dates), n


# ---------------------------------------------------------------------------
# Git-commit-aktivitet på tvers av alle tjeneste-repoer
# ---------------------------------------------------------------------------

def get_commit_activity(service_names, days=14, reference_date=None):
    """reference_date (en date) lar oss regne ut historisk commit-aktivitet
    som den så ut på et gitt tidspunkt - brukt av migreringsskriptet for å
    gjenskape gamle rapporter korrekt."""
    ref = reference_date or datetime.now().date()
    since = (ref - timedelta(days=days - 1)).strftime('%Y-%m-%d')
    until = ref.strftime('%Y-%m-%d')
    counts = defaultdict(int)

    for svc in service_names:
        svc_dir = os.path.join(PROJECT_ROOT, svc)
        if not os.path.isdir(os.path.join(svc_dir, '.git')):
            continue
        try:
            result = subprocess.run(
                ['git', '-C', svc_dir, 'log', f'--since={since}', f'--until={until} 23:59:59', '--pretty=format:%ad', '--date=short'],
                capture_output=True, text=True, timeout=10
            )
        except Exception:
            continue
        for line in result.stdout.splitlines():
            line = line.strip()
            if line:
                counts[line] += 1

    ordered = []
    for i in range(days - 1, -1, -1):
        d = ref - timedelta(days=i)
        ordered.append((d.strftime('%m-%d'), counts.get(d.strftime('%Y-%m-%d'), 0)))
    return ordered


# ---------------------------------------------------------------------------
# Sparklines og Mermaid-diagrammer
# ---------------------------------------------------------------------------

def sparkline(values):
    if not values:
        return ''
    lo, hi = min(values), max(values)
    if hi == lo:
        return SPARK_CHARS[3] * len(values)
    span = hi - lo
    return ''.join(SPARK_CHARS[min(7, int((v - lo) / span * 7))] for v in values)


def nice_ceiling(value):
    """Runder opp til et 'pent' tall (10, 30, 200, 51000, ...) tilpasset
    størrelsesordenen - en fast avrunding til nærmeste 1000 ser fin ut for
    linjetall i titusenvis, men gjør et commit-diagram (maks noen titalls)
    helt uleselig med en 0-1000 y-akse."""
    value = max(1, value)
    magnitude = 10 ** (len(str(int(value))) - 1)
    return int(math.ceil(value / magnitude) * magnitude)


def mermaid_line_chart(title, y_label, labels, values):
    if len(values) < 2:
        return None
    y_max = nice_ceiling(max(values) * 1.15)
    labels_str = ', '.join(f'"{l}"' for l in labels)
    values_str = ', '.join(str(v) for v in values)
    return (
        '```mermaid\n'
        'xychart-beta\n'
        f'    title "{title}"\n'
        f'    x-axis [{labels_str}]\n'
        f'    y-axis "{y_label}" 0 --> {y_max}\n'
        f'    line [{values_str}]\n'
        '```'
    )


def mermaid_pie_chart(title, items, max_slices=9):
    items = sorted(items, key=lambda x: x[1], reverse=True)
    if not items or sum(v for _, v in items) == 0:
        return None
    if len(items) > max_slices:
        head = items[:max_slices]
        other = sum(v for _, v in items[max_slices:])
        items = head + [('Annet', other)]
    lines = ['```mermaid', f'pie title {title}']
    for label, value in items:
        safe_label = label.replace('"', "'")
        lines.append(f'    "{safe_label}" : {value}')
    lines.append('```')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Rapportgenerering (delt mellom terminal- og Markdown-visning)
# ---------------------------------------------------------------------------

def build_report(stats, history_entries, commit_activity, now, only_service=None):
    """history_entries skal IKKE inkludere dagens måling ennå - den brukes til
    å beregne diff og til trendene, og dagens punkt legges på i tillegg."""
    totals = stats['totals']
    by_category = stats['by_category']
    by_service = stats['by_service']
    by_language = stats['by_language']

    timestamp_str = now.strftime('%Y-%m-%d %H:%M:%S')
    previous = history_entries[-1] if history_entries else None

    measured, window = measured_days_last_n(history_entries + [{'timestamp': now.isoformat()}], now)

    cli = []
    md = []

    def add(cli_line=None, md_line=None):
        if cli_line is not None:
            cli.append(cli_line)
        if md_line is not None:
            md.append(md_line)

    add(f'{"=" * 88}', None)
    add(f'{CYAN}📊 KODELINJE-STATISTIKK FOR KJØKKENHYLLA{NC}', '# 📊 Kodelinje-status for Kjøkkenhylla')
    add(f'{"=" * 88}', None)
    add(f'Dato: {timestamp_str}', f'**Dato:** {timestamp_str}  ')
    add(f'Målt {measured} av siste {window} dager 🔥', f'**Målt {measured} av siste {window} dager** 🔥\n')

    if previous:
        pt = previous['totals']
        diffs = {k: totals[k] - pt.get(k, totals[k]) for k in totals}
        add('\n📈 ENDRING SIDEN FORRIGE MÅLING:', '### 📈 Endring siden forrige måling')
        labels = [('files', 'Filer'), ('code_lines', 'Ren Kode'), ('test_lines', 'Tester'), ('config_lines', 'Konfigurasjon'),
                  ('doc_lines', 'Dokumentasjon'), ('comment_lines', 'Kommentarer'), ('total_lines', 'Totalt (inkl. blanke)')]
        for key, label in labels:
            d = diffs[key]
            sign = '+' if d >= 0 else ''
            add(f'  • {label + ":":<22} {totals[key]:<6} ({sign}{d})',
                f'* **{label}:** {totals[key]} ({sign}{d})')
        md.append('')

    # --- Trend over tid ---
    series = history_entries + [{'timestamp': now.isoformat(), 'totals': totals}]
    trend_labels = [datetime.fromisoformat(e['timestamp']).strftime('%m-%d') for e in series]
    trend_values = [e['totals']['total_lines'] for e in series]

    add(f'\n📉 Sparkline (totalt antall linjer, {trend_values[0]} → {trend_values[-1]}):',
        '## 📉 Utvikling over tid')
    add(f'  {sparkline(trend_values)}', None)

    chart = mermaid_line_chart('Totalt antall linjer over tid', 'Linjer', trend_labels, trend_values)
    if chart:
        md.append(f'`{sparkline(trend_values)}`  ({trend_values[0]} → {trend_values[-1]})\n')
        md.append(chart)
        md.append('')

    # --- Overordnet fordeling ---
    add('\n🏷️ OVERORDNET FORDELING (KODE vs TESTER vs KONFIG vs DOK):', '## 🏷️ Overordnet Fordeling')
    add('-' * 88, None)
    add(f"{'Hovedkategori':<22} | {'Filer':<6} | {'Innhold/Linjer':<14} | {'Kommentarer':<11} | {'Totalt':<8}", None)
    add('-' * 88, None)
    md.append('| Hovedkategori | Filer | Innhold/Linjer | Kommentarer | Blank | Totalt |')
    md.append('| :--- | :---: | :---: | :---: | :---: | :---: |')
    for cat in ['Ren Kode', 'Tester', 'Konfigurasjon', 'Dokumentasjon']:
        c = by_category.get(cat, {'files': 0, 'content': 0, 'comments': 0, 'blank': 0, 'total': 0})
        add(f"{cat:<22} | {c['files']:<6} | {c['content']:<14} | {c['comments']:<11} | {c['total']:<8}",
            f"| **{cat}** | {c['files']} | {c['content']} | {c['comments']} | {c['blank']} | {c['total']} |")

    # --- Per tjeneste, med trend-sparkline ---
    add('\n📁 FORDELING PER MIKROTJENESTE / PROSJEKT:', '\n## 📁 Fordeling per Mikrotjeneste / Prosjekt')
    add('-' * 108, None)
    add(f"{'Prosjekt / Mappe':<28} | {'Filer':<5} | {'Ren Kode':<8} | {'Tester':<8} | {'Konfig':<8} | {'Dok':<6} | {'Komm':<6} | {'Totalt':<8} | Trend", None)
    add('-' * 108, None)
    md.append('| Prosjekt / Mappe | Filer | Ren Kode | Tester | Konfigurasjon | Dokumentasjon | Kommentarer | Totalt | Trend |')
    md.append('| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |')

    for service in sorted(by_service.keys()):
        s = by_service[service]
        svc_series = [e['by_service'][service]['total'] for e in history_entries if service in e.get('by_service', {})]
        svc_series.append(s['total'])
        trend = sparkline(svc_series) if len(svc_series) >= 2 else '-'
        add(f"{service:<28} | {s['files']:<5} | {s['code']:<8} | {s['test']:<8} | {s['config']:<8} | {s['doc']:<6} | {s['comments']:<6} | {s['total']:<8} | {trend}",
            f"| `{service}` | {s['files']} | {s['code']} | {s['test']} | {s['config']} | {s['doc']} | {s['comments']} | {s['total']} | {trend} |")

    add('-' * 108, None)
    add(f"{'TOTALT':<28} | {totals['files']:<5} | {totals['code_lines']:<8} | {totals['test_lines']:<8} | {totals['config_lines']:<8} | {totals['doc_lines']:<6} | {totals['comment_lines']:<6} | {totals['total_lines']:<8} |", None)
    add('=' * 88, None)
    md.append(f"| **TOTALT** | **{totals['files']}** | **{totals['code_lines']}** | **{totals['test_lines']}** | **{totals['config_lines']}** | **{totals['doc_lines']}** | **{totals['comment_lines']}** | **{totals['total_lines']}** | |\n")

    # --- Per språk/filtype ---
    add('\n💻 FORDELING PER SPRÅK / FILTYPE:', '## 💻 Fordeling per Språk / Filtype')
    add('-' * 88, None)
    add(f"{'Språk / Filtype':<22} | {'Kategori':<14} | {'Filer':<5} | {'Linjer':<7} | {'Komm':<6} | {'Blank':<5} | {'Totalt':<7}", None)
    add('-' * 88, None)
    md.append('| Språk / Filtype | Kategori | Filer | Linjer | Kommentarer | Blank | Totalt |')
    md.append('| :--- | :--- | :---: | :---: | :---: | :---: | :---: |')

    lang_items = sorted(by_language.items(), key=lambda x: x[1]['content'], reverse=True)
    for lang, s in lang_items:
        add(f"{lang:<22} | {s['category']:<14} | {s['files']:<5} | {s['content']:<7} | {s['comments']:<6} | {s['blank']:<5} | {s['total']:<7}",
            f"| **{lang}** | {s['category']} | {s['files']} | {s['content']} | {s['comments']} | {s['blank']} | {s['total']} |")
    add('=' * 88, None)

    pie = mermaid_pie_chart('Språkfordeling (linjer)', [(lang, s['content']) for lang, s in lang_items])
    if pie:
        md.append('\n' + pie)

    # --- Commit-aktivitet ---
    if commit_activity:
        commit_labels = [d for d, _ in commit_activity]
        commit_values = [c for _, c in commit_activity]
        total_commits = sum(commit_values)
        add(f'\n🔥 COMMIT-AKTIVITET (siste {len(commit_activity)} dager, alle repoer): {total_commits} commits',
            f'\n## 🔥 Commit-aktivitet (siste {len(commit_activity)} dager, alle repoer)')
        add(f'  {sparkline(commit_values)}', f'`{sparkline(commit_values)}`  ({total_commits} commits totalt)')
        cmt_chart = mermaid_line_chart('Commits per dag (alle repoer)', 'Commits', commit_labels, commit_values)
        if cmt_chart:
            md.append('')
            md.append(cmt_chart)

    # --- Dypdykk for én tjeneste ---
    if only_service and only_service in by_service:
        s = by_service[only_service]
        svc_series = [e['by_service'][only_service]['total'] for e in history_entries if only_service in e.get('by_service', {})]
        svc_series.append(s['total'])
        add(f'\n🔍 DYPDYKK: {only_service}', None)
        add(f'  Filer: {s["files"]}  Kode: {s["code"]}  Tester: {s["test"]}  Konfig: {s["config"]}  Dok: {s["doc"]}  Kommentarer: {s["comments"]}  Totalt: {s["total"]}', None)
        add(f'  Trend: {sparkline(svc_series)}  ({svc_series[0]} → {svc_series[-1]})' if len(svc_series) >= 2 else '  (Ikke nok historikk for trend ennå)', None)
        svc_commits = get_commit_activity([only_service], days=14)
        svc_commit_values = [c for _, c in svc_commits]
        add(f'  Commits (14d): {sparkline(svc_commit_values)}  ({sum(svc_commit_values)} totalt)', None)

    return '\n'.join(cli), '\n'.join(md)


# ---------------------------------------------------------------------------
# Hovedlogikk
# ---------------------------------------------------------------------------

def run(no_report=False, only_service=None):
    os.makedirs(LOG_DIR, exist_ok=True)
    now = datetime.now()

    stats = scan_project()
    history_entries = load_history()

    service_names = sorted(n for n in stats['by_service'].keys() if n != 'Root')
    commit_activity = get_commit_activity(service_names, days=14)

    cli_text, md_text = build_report(stats, history_entries, commit_activity, now, only_service=only_service)
    print(cli_text)

    if no_report:
        print(f'\n({YELLOW}--no-report: ingen filer skrevet{NC})')
        return

    entry = {
        'timestamp': now.isoformat(timespec='seconds'),
        'totals': stats['totals'],
        'by_category': stats['by_category'],
        'by_service': stats['by_service'],
        'by_language': stats['by_language'],
    }
    append_history(entry)

    filename = now.strftime('%Y-%m-%d_%H-%M-%S') + '_LOC.md'
    filepath = os.path.join(LOG_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(md_text)

    dashboard_header = (
        f'_(Alltid oppdatert til siste måling - se `progress-log/` for historiske '
        f'enkeltmålinger, f.eks. denne: `{filename}`.)_\n\n'
    )
    with open(DASHBOARD_PATH, 'w', encoding='utf-8') as f:
        f.write(dashboard_header + md_text)

    print(f'\n{GREEN}✅ Rapport lagret til: recipe-infrastructure/progress-log/{filename}{NC}')
    print(f'{GREEN}✅ Dashboard oppdatert: recipe-infrastructure/progress-log/dashboard.md{NC}\n')


def main():
    parser = argparse.ArgumentParser(description='Tell kodelinjer for Kjøkkenhylla-prosjektet.')
    parser.add_argument('--no-report', action='store_true', help='Ikke skriv rapport-/historikkfiler, bare skriv til terminalen.')
    parser.add_argument('--service', metavar='NAVN', help='Vis et dypdykk for én tjeneste, f.eks. recipe-auth-api.')
    args = parser.parse_args()
    run(no_report=args.no_report, only_service=args.service)


if __name__ == '__main__':
    main()
