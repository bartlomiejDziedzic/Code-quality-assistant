import re
import threading
import tkinter as tk
from tkinter import font, messagebox, ttk

from main import analyze_code


# ─────────────────────── Response parser ─────────────────────────────────────

_FILE_HDR = re.compile(
    r'####\s+File\s+\d+:\s+`?([^`\n(]+?)`?(?:\s*\([^)]*\))?\s*\n'
)
_CODE_BLOCK = re.compile(r'```[\w]*\n(.*?)```', re.DOTALL)


def _extract_files(content):
    headers = list(_FILE_HDR.finditer(content))
    files = []
    for i, m in enumerate(headers):
        name = m.group(1).strip()
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
        cm = _CODE_BLOCK.search(content, start, end)
        if cm:
            files.append((name, cm.group(1).rstrip()))
    return files


def parse_response(text):
    s3 = re.search(r'###\s+3\.[^\n]*\n(.*?)(?=###\s+4\.|$)', text, re.DOTALL)
    s4 = re.search(r'(###\s+4\.[^\n]*\n.*?)$', text, re.DOTALL)
    analysis = text[: s3.start() if s3 else len(text)].strip()
    files = _extract_files(s3.group(1)) if s3 else []
    summary = s4.group(1).strip() if s4 else ''
    return {'analysis': analysis, 'files': files, 'summary': summary}


# ─────────────────────── Markdown renderer ───────────────────────────────────

_INLINE_RE = re.compile(r'(\*\*[^*\n]+?\*\*|\*[^*\n]+?\*|`[^`\n]+?`)')


def _configure_md_tags(widget, base_font):
    fam = base_font.cget('family')
    sz = base_font.cget('size')
    widget.tag_configure('h3',
        font=font.Font(family=fam, size=sz + 2, weight='bold'),
        foreground='#89dceb', spacing1=6, spacing3=4)
    widget.tag_configure('h4',
        font=font.Font(family=fam, size=sz + 1, weight='bold'),
        foreground='#cba6f7', spacing1=4, spacing3=2)
    widget.tag_configure('bold',
        font=font.Font(family=fam, size=sz, weight='bold'))
    widget.tag_configure('italic',
        font=font.Font(family=fam, size=sz, slant='italic'))
    widget.tag_configure('code',
        font=font.Font(family='Consolas', size=sz),
        background='#45475a', foreground='#f38ba8')
    widget.tag_configure('sep', foreground='#585b70')
    widget.tag_configure('bullet', lmargin1=6, lmargin2=18)
    widget.tag_configure('nested', lmargin1=22, lmargin2=36)


def _inline(widget, text, *extra_tags):
    for part in _INLINE_RE.split(text):
        if part.startswith('**') and part.endswith('**') and len(part) > 4:
            widget.insert(tk.END, part[2:-2], extra_tags + ('bold',))
        elif part.startswith('*') and part.endswith('*') and len(part) > 2:
            widget.insert(tk.END, part[1:-1], extra_tags + ('italic',))
        elif part.startswith('`') and part.endswith('`') and len(part) > 2:
            widget.insert(tk.END, part[1:-1], extra_tags + ('code',))
        elif extra_tags:
            widget.insert(tk.END, part, extra_tags)
        else:
            widget.insert(tk.END, part)


def render_md(widget, text):
    widget.config(state=tk.NORMAL)
    widget.delete('1.0', tk.END)
    in_block = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('```'):
            in_block = not in_block
            widget.insert(tk.END, '\n')
            continue
        if in_block:
            widget.insert(tk.END, line + '\n', 'code')
            continue
        if s.startswith('#### '):
            widget.insert(tk.END, s[5:] + '\n', 'h4')
        elif s.startswith('### '):
            widget.insert(tk.END, s[4:] + '\n', 'h3')
        elif s in ('---', '___', '***'):
            widget.insert(tk.END, '─' * 64 + '\n', 'sep')
        elif re.match(r'^\s{4,}[*-]\s{3}', line):
            widget.insert(tk.END, '      ◦ ')
            _inline(widget, s.lstrip('*- '), 'nested')
            widget.insert(tk.END, '\n')
        elif re.match(r'^[*-]\s{3}', s):
            widget.insert(tk.END, '  • ')
            _inline(widget, s[4:], 'bullet')
            widget.insert(tk.END, '\n')
        else:
            _inline(widget, line)
            widget.insert(tk.END, '\n')
    widget.config(state=tk.DISABLED)


# ─────────────────────── App ──────────────────────────────────────────────────

class App(tk.Tk):
    BG = '#1e1e2e'
    TXT_BG = '#313244'
    FG = '#cdd6f4'
    FG2 = '#a6adc8'
    ACCENT = '#89b4fa'
    OK = '#a6e3a1'
    WARN = '#f9e2af'
    ERR = '#f38ba8'

    def __init__(self):
        super().__init__()
        self.title('Code Quality Assistant')
        self.geometry('1200x820')
        self.minsize(900, 600)
        self.configure(bg=self.BG)
        self._uf = font.Font(family='Segoe UI', size=10)
        self._lf = font.Font(family='Segoe UI', size=10, weight='bold')
        self._mf = font.Font(family='Consolas', size=11)
        self._notebook = None
        self._single_tw = None
        self._tab_tws = []
        self._build()

    def _build(self):
        # Bar must be packed FIRST with side=BOTTOM so PanedWindow's
        # expand=True doesn't swallow all vertical space.
        bar = tk.Frame(self, bg=self.BG)
        bar.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 12))
        self.btn_analyze = tk.Button(
            bar, text='Analizuj', font=self._uf, cursor='hand2',
            bg=self.ACCENT, fg=self.BG, activebackground='#74c7ec',
            activeforeground=self.BG, relief=tk.FLAT, padx=20, pady=6,
            command=self._start,
        )
        self.btn_analyze.pack(side=tk.LEFT)
        self.lbl_status = tk.Label(bar, text='', bg=self.BG, fg=self.FG2,
                                   font=self._uf)
        self.lbl_status.pack(side=tk.LEFT, padx=14)
        self.btn_copy = tk.Button(
            bar, text='Kopiuj aktywny plik', font=self._uf, cursor='hand2',
            bg=self.TXT_BG, fg=self.FG, activebackground='#45475a',
            activeforeground=self.FG, relief=tk.FLAT, padx=16, pady=6,
            command=self._copy,
        )
        self.btn_copy.pack(side=tk.RIGHT)

        # Main horizontal split
        h = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=self.BG,
                           sashwidth=6, sashrelief=tk.FLAT, sashpad=2)
        h.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 6))

        # Left — input
        left = tk.Frame(h, bg=self.BG)
        tk.Label(left, text='Wklej kod do analizy', bg=self.BG,
                 fg=self.FG, font=self._lf).pack(anchor='w', pady=(0, 4))
        self.inp = self._tw(left, editable=True)
        h.add(left, minsize=300)

        # Right — vertical 3-way split
        v = tk.PanedWindow(h, orient=tk.VERTICAL, bg=self.BG,
                           sashwidth=6, sashrelief=tk.FLAT, sashpad=2)
        h.add(v, minsize=500)

        # Top: analysis
        af = tk.Frame(v, bg=self.BG)
        tk.Label(af, text='Analiza architektoniczna', bg=self.BG,
                 fg=self.FG, font=self._lf).pack(anchor='w', pady=(0, 4))
        self.analysis_tw = self._tw(af, prose=True)
        _configure_md_tags(self.analysis_tw, self._uf)
        v.add(af, minsize=80)

        # Middle: code files
        cf = tk.Frame(v, bg=self.BG)
        tk.Label(cf, text='Pliki kodu', bg=self.BG,
                 fg=self.FG, font=self._lf).pack(anchor='w', pady=(0, 4))
        self.code_area = tk.Frame(cf, bg=self.BG)
        self.code_area.pack(fill=tk.BOTH, expand=True)
        self._placeholder('Wynik analizy pojawi się tutaj.')
        v.add(cf, minsize=80)

        # Bottom: summary
        sf = tk.Frame(v, bg=self.BG)
        tk.Label(sf, text='Podsumowanie refaktoryzacji', bg=self.BG,
                 fg=self.FG, font=self._lf).pack(anchor='w', pady=(0, 4))
        self.summary_tw = self._tw(sf, prose=True)
        _configure_md_tags(self.summary_tw, self._uf)
        v.add(sf, minsize=60)

    # ── Widget helpers ────────────────────────────────────────────────────────

    def _tw(self, parent, *, prose=False, editable=False):
        """Scrolled Text widget packed into parent. Returns the Text widget."""
        f = tk.Frame(parent, bg=self.TXT_BG)
        f.pack(fill=tk.BOTH, expand=True)
        sb_y = tk.Scrollbar(f, bg='#45475a', troughcolor=self.BG, relief=tk.FLAT)
        sb_y.pack(side=tk.RIGHT, fill=tk.Y)
        kw = dict(
            font=self._uf if prose else self._mf,
            wrap=tk.WORD if prose else tk.NONE,
            bg=self.TXT_BG, fg=self.FG, insertbackground='#f5c2e7',
            selectbackground='#45475a', relief=tk.FLAT,
            state=tk.NORMAL if editable else tk.DISABLED,
            yscrollcommand=sb_y.set, padx=10, pady=10, spacing1=2,
        )
        if not prose:
            sb_x = tk.Scrollbar(f, orient=tk.HORIZONTAL, bg='#45475a',
                                 troughcolor=self.BG, relief=tk.FLAT)
            sb_x.pack(side=tk.BOTTOM, fill=tk.X)
            kw['xscrollcommand'] = sb_x.set
        tw = tk.Text(f, **kw)
        tw.pack(fill=tk.BOTH, expand=True)
        sb_y.config(command=tw.yview)
        if not prose:
            sb_x.config(command=tw.xview)
        return tw

    def _code_tw_in(self, parent):
        """Code Text widget without outer frame packing (caller owns layout)."""
        sb_y = tk.Scrollbar(parent, bg='#45475a', troughcolor=self.BG, relief=tk.FLAT)
        sb_y.pack(side=tk.RIGHT, fill=tk.Y)
        sb_x = tk.Scrollbar(parent, orient=tk.HORIZONTAL, bg='#45475a',
                             troughcolor=self.BG, relief=tk.FLAT)
        sb_x.pack(side=tk.BOTTOM, fill=tk.X)
        tw = tk.Text(parent, font=self._mf, wrap=tk.NONE,
                     bg=self.TXT_BG, fg=self.FG, insertbackground='#f5c2e7',
                     selectbackground='#45475a', relief=tk.FLAT,
                     state=tk.DISABLED,
                     yscrollcommand=sb_y.set, xscrollcommand=sb_x.set,
                     padx=10, pady=10)
        tw.pack(fill=tk.BOTH, expand=True)
        sb_y.config(command=tw.yview)
        sb_x.config(command=tw.xview)
        return tw

    # ── Code area management ─────────────────────────────────────────────────

    def _clear_code_area(self):
        for w in self.code_area.winfo_children():
            w.destroy()
        self._notebook = None
        self._single_tw = None
        self._tab_tws = []

    def _placeholder(self, msg):
        self._clear_code_area()
        tk.Label(self.code_area, text=msg, bg=self.TXT_BG, fg=self.FG2,
                 font=self._uf).pack(fill=tk.BOTH, expand=True, padx=10, pady=20)

    def _load_files(self, files):
        self._clear_code_area()
        if not files:
            self._placeholder('Brak plików kodu w odpowiedzi.')
            return

        if len(files) == 1:
            name, code = files[0]
            tk.Label(self.code_area, text=name, bg=self.BG, fg=self.FG2,
                     font=font.Font(family='Consolas', size=9)
                     ).pack(anchor='w', pady=(0, 2))
            frame = tk.Frame(self.code_area, bg=self.TXT_BG)
            frame.pack(fill=tk.BOTH, expand=True)
            tw = self._code_tw_in(frame)
            tw.config(state=tk.NORMAL)
            tw.insert('1.0', code)
            tw.config(state=tk.DISABLED)
            self._single_tw = tw
        else:
            style = ttk.Style()
            style.theme_use('default')
            style.configure('D.TNotebook', background=self.BG, borderwidth=0)
            style.configure('D.TNotebook.Tab', background=self.TXT_BG,
                            foreground=self.FG2, padding=[10, 4],
                            font=('Consolas', 9))
            style.map('D.TNotebook.Tab',
                      background=[('selected', '#45475a')],
                      foreground=[('selected', self.FG)])
            nb = ttk.Notebook(self.code_area, style='D.TNotebook')
            nb.pack(fill=tk.BOTH, expand=True)
            self._notebook = nb
            for name, code in files:
                tab = tk.Frame(nb, bg=self.TXT_BG)
                tw = self._code_tw_in(tab)
                tw.config(state=tk.NORMAL)
                tw.insert('1.0', code)
                tw.config(state=tk.DISABLED)
                nb.add(tab, text=f'  {name}  ')
                self._tab_tws.append(tw)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _status(self, msg, color=None):
        self.lbl_status.config(text=msg, fg=color or self.FG2)

    def _start(self):
        code = self.inp.get('1.0', tk.END).strip()
        if not code:
            messagebox.showwarning('Brak kodu', 'Wklej kod przed analizą.')
            return
        self.btn_analyze.config(state=tk.DISABLED)
        render_md(self.analysis_tw, '')
        render_md(self.summary_tw, '')
        self._placeholder('Analizuję...')
        self._status('Analizuję...', self.WARN)
        threading.Thread(target=self._run, args=(code,), daemon=True).start()

    def _run(self, code):
        try:
            result = analyze_code(code)
            self.after(0, self._show, result)
        except Exception as exc:
            self.after(0, self._err, str(exc))

    def _show(self, raw):
        parsed = parse_response(raw)
        render_md(self.analysis_tw, parsed['analysis'])
        self._load_files(parsed['files'])
        render_md(self.summary_tw, parsed['summary'])
        self._status('Gotowe.', self.OK)
        self.btn_analyze.config(state=tk.NORMAL)

    def _err(self, msg):
        self._status(f'Błąd: {msg}', self.ERR)
        self.btn_analyze.config(state=tk.NORMAL)
        self._placeholder('Wystąpił błąd podczas analizy.')

    def _copy(self):
        text = ''
        if self._notebook is not None:
            try:
                idx = self._notebook.index('current')
                text = self._tab_tws[idx].get('1.0', tk.END).strip()
            except tk.TclError:
                pass
        elif self._single_tw is not None:
            text = self._single_tw.get('1.0', tk.END).strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._status('Skopiowano do schowka.', self.OK)


if __name__ == '__main__':
    App().mainloop()
