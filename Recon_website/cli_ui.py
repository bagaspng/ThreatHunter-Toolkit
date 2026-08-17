import re
import sys
import itertools
import threading
import time
from contextlib import contextmanager

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.rule import Rule
    from rich import box
    HAS_RICH = True
    console = Console(highlight=False)
except ImportError:
    HAS_RICH = False
    console = None


class _Ansi:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    BOLD_RED = '\033[1;31m'


_SUPPORTS_COLOR = sys.stdout.isatty()


def _c(text, code):
    if HAS_RICH or not _SUPPORTS_COLOR:
        return text
    return f'{code}{text}{_Ansi.RESET}'


_PREFIX_PATTERNS = [
    (re.compile(r'^(\s*)\[!!\]\s*(.*)$'), 'critical'),
    (re.compile(r'^(\s*)\[!\]\s*(.*)$'), 'warn'),
    (re.compile(r'^(\s*)\[\+\]\s*(.*)$'), 'ok'),
    (re.compile(r'^(\s*)\[\*\]\s*(.*)$'), 'step'),
    (re.compile(r'^(\s*)\[i\]\s*(.*)$'), 'info'),
]

_ICON = {'critical': '‼', 'warn': '⚠', 'ok': '✓', 'step': '›', 'info': 'ℹ'}
_RICH_STYLE = {'critical': 'bold red', 'warn': 'yellow', 'ok': 'green', 'step': 'cyan', 'info': 'bright_black'}
_ANSI_STYLE = {'critical': _Ansi.BOLD_RED, 'warn': _Ansi.YELLOW, 'ok': _Ansi.GREEN, 'step': _Ansi.CYAN, 'info': _Ansi.DIM}

_TARGET_HEADER = re.compile(r'^===\s*(.*?)\s*===$')
_STAGE_HEADER = re.compile(r'^---\s*(.*?)\s*---$')


def _print_rule(title, color):
    if HAS_RICH:
        console.print(Rule(f'[bold {color}]{title}[/bold {color}]', style=color))
    else:
        code = {'magenta': _Ansi.MAGENTA, 'blue': _Ansi.BLUE}.get(color, _Ansi.BLUE)
        width = 62
        print(_c('─' * width, code))
        print(_c(f' {title}', _Ansi.BOLD + code))
        print(_c('─' * width, code))


def pretty_print(msg):
    if msg is None:
        return
    for line in msg.split('\n'):
        stripped = line.strip()
        if stripped == '':
            print()
            continue
        m = _TARGET_HEADER.match(stripped)
        if m:
            _print_rule(m.group(1), 'magenta')
            continue
        m = _STAGE_HEADER.match(stripped)
        if m:
            _print_rule(m.group(1), 'blue')
            continue
        matched = False
        for pattern, level in _PREFIX_PATTERNS:
            m = pattern.match(line)
            if m:
                indent, content = m.group(1), m.group(2)
                icon = _ICON[level]
                if HAS_RICH:
                    style = _RICH_STYLE[level]
                    console.print(f'{indent}[{style}]{icon} {content}[/{style}]')
                else:
                    print(f'{indent}{_c(icon + " " + content, _ANSI_STYLE[level])}')
                matched = True
                break
        if not matched:
            print(line)


class _AnsiSpinner:
    def __init__(self, text):
        self.text = text
        self._stop = threading.Event()
        self._thread = None

    def _animate(self):
        frames = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
        while not self._stop.is_set():
            frame = next(frames)
            sys.stdout.write(f'\r{_c(frame, _Ansi.CYAN)} {self.text}   ')
            sys.stdout.flush()
            time.sleep(0.08)
        sys.stdout.write('\r' + ' ' * (len(self.text) + 6) + '\r')
        sys.stdout.flush()

    def start(self):
        if not _SUPPORTS_COLOR:
            print(f'... {self.text}')
            return
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self):
        if self._thread is not None:
            self._stop.set()
            self._thread.join()


@contextmanager
def spinner(text):
    if HAS_RICH:
        with console.status(f'[cyan]{text}[/cyan]', spinner='dots'):
            yield
    else:
        s = _AnsiSpinner(text)
        s.start()
        try:
            yield
        finally:
            s.stop()


def run_banner(total, filename):
    if HAS_RICH:
        console.print(Panel(f'[bold]{total}[/bold] target dari [bold]{filename}[/bold]',
                             title='[bold green]RECON WEBSITE[/bold green]',
                             border_style='green', box=box.ROUNDED))
    else:
        print(_c(f'=== Bulk recon: {total} target dari {filename} ===\n', _Ansi.BOLD + _Ansi.GREEN))


def target_banner(current, total, url):
    print()
    if HAS_RICH:
        console.print(Panel(f'[bold white]{url}[/bold white]',
                             title=f'[bold yellow]TARGET {current}/{total}[/bold yellow]',
                             border_style='bright_blue', box=box.DOUBLE))
    else:
        line = '#' * 62
        print(_c(line, _Ansi.BLUE))
        print(_c(f'# Target {current}/{total}: {url}', _Ansi.BOLD + _Ansi.BLUE))
        print(_c(line, _Ansi.BLUE))


def summary_table(all_results):
    print()
    if HAS_RICH:
        table = Table(title='Ringkasan Hasil Recon', box=box.ROUNDED, show_lines=False, title_style='bold')
        table.add_column('Target', style='bold white', overflow='fold')
        table.add_column('Email', justify='right')
        table.add_column('Telepon', justify='right')
        table.add_column('Tech', justify='right')
        table.add_column('Subdomain', justify='right')
        table.add_column('Error', justify='right')
        for r in all_results:
            n_err = len(r.get('errors', []))
            err_txt = f'[red]{n_err}[/red]' if n_err else f'[green]{n_err}[/green]'
            table.add_row(
                r.get('target', '-'),
                str(len(r.get('emails', []))),
                str(len(r.get('phones', []))),
                str(len(r.get('technologies', []))),
                str(len(r.get('subdomains', []))),
                err_txt,
            )
        console.print(table)
    else:
        print(_c('=== Ringkasan Hasil Recon ===', _Ansi.BOLD))
        header = f"{'Target':<38}{'Email':>7}{'Telp':>6}{'Tech':>6}{'Subdom':>8}{'Error':>7}"
        print(header)
        print('-' * len(header))
        for r in all_results:
            target = r.get('target', '-')
            target = target if len(target) <= 38 else target[:35] + '...'
            n_err = len(r.get('errors', []))
            err_str = _c(str(n_err), _Ansi.RED if n_err else _Ansi.GREEN)
            print(f"{target:<38}{len(r.get('emails', [])):>7}{len(r.get('phones', [])):>6}"
                  f"{len(r.get('technologies', [])):>6}{len(r.get('subdomains', [])):>8}{err_str:>7}")


def done_banner(json_file, log_file):
    print()
    if HAS_RICH:
        console.print(Panel(f'[green]JSON[/green]  -> {json_file}\n[green]Log[/green]   -> {log_file}',
                             title='[bold green]✓ SELESAI[/bold green]', border_style='green'))
    else:
        print(_c(f'[✓] Hasil recon (JSON) disimpan ke: {json_file}', _Ansi.GREEN))
        print(_c(f'[✓] Log proses lengkap disimpan (append) ke file: {log_file}', _Ansi.GREEN))
