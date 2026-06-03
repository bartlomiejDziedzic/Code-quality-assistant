import re
import threading
import tkinter as tk
from tkinter import font, messagebox

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
    # Fallback: single file without a "#### File N:" header — grab first code block
    if not files:
        cm = _CODE_BLOCK.search(content)
        if cm:
            files.append(('refactored_code', cm.group(1).rstrip()))
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


# ─────────────────────── Code Canvas ─────────────────────────────────────────

class CodeCanvas(tk.Frame):
    """Code editor panel with line-number gutter."""

    LINENO_BG = '#181825'
    LINENO_FG = '#585b70'

    def __init__(self, parent, app, *, editable=False):
        super().__init__(parent, bg=app.TXT_BG)
        self._app = app
        self._editable = editable
        self._mod_lock = False

        # Gutter with line numbers
        gutter = tk.Frame(self, bg=self.LINENO_BG)
        gutter.pack(side=tk.LEFT, fill=tk.Y)
        self._ln = tk.Text(
            gutter, width=4, bg=self.LINENO_BG, fg=self.LINENO_FG,
            font=app._mf, relief=tk.FLAT, state=tk.DISABLED,
            padx=8, pady=10, spacing1=2, cursor='arrow',
            selectbackground=self.LINENO_BG, selectforeground=self.LINENO_FG,
        )
        self._ln.pack(fill=tk.BOTH, expand=True)

        # Thin separator between gutter and code
        tk.Frame(self, bg='#45475a', width=1).pack(side=tk.LEFT, fill=tk.Y)

        # Code area
        inner = tk.Frame(self, bg=app.TXT_BG)
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._sb_y = tk.Scrollbar(inner, bg='#45475a', troughcolor=app.BG, relief=tk.FLAT)
        self._sb_y.pack(side=tk.RIGHT, fill=tk.Y)
        self._sb_x = tk.Scrollbar(inner, orient=tk.HORIZONTAL, bg='#45475a',
                                   troughcolor=app.BG, relief=tk.FLAT)
        self._sb_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.text = tk.Text(
            inner, font=app._mf, wrap=tk.NONE,
            bg=app.TXT_BG, fg=app.FG, insertbackground='#f5c2e7',
            selectbackground='#45475a', relief=tk.FLAT,
            state=tk.NORMAL if editable else tk.DISABLED,
            yscrollcommand=self._on_yscroll,
            xscrollcommand=self._sb_x.set,
            padx=10, pady=10, spacing1=2,
        )
        self.text.pack(fill=tk.BOTH, expand=True)
        self._sb_y.config(command=self._on_yview)
        self._sb_x.config(command=self.text.xview)

        self.text.bind('<<Modified>>', self._on_modified)
        self.text.bind('<Configure>', lambda _: self.after_idle(self._refresh_linenos))

    def _on_yscroll(self, first, last):
        self._sb_y.set(first, last)
        self._ln.yview_moveto(first)

    def _on_yview(self, *args):
        self.text.yview(*args)
        self._ln.yview(*args)

    def _on_modified(self, _=None):
        if self._mod_lock:
            return
        self._mod_lock = True
        self.text.edit_modified(False)
        self._mod_lock = False
        self.after_idle(self._refresh_linenos)

    def _refresh_linenos(self):
        n = int(self.text.index(tk.END).split('.')[0]) - 1
        nums = '\n'.join(str(i) for i in range(1, max(n, 1) + 1))
        self._ln.config(state=tk.NORMAL)
        self._ln.delete('1.0', tk.END)
        self._ln.insert(tk.END, nums)
        self._ln.config(state=tk.DISABLED)
        self._ln.yview_moveto(self.text.yview()[0])

    def set_code(self, code):
        self.text.config(state=tk.NORMAL)
        self.text.delete('1.0', tk.END)
        if code:
            self.text.insert('1.0', code)
        if not self._editable:
            self.text.config(state=tk.DISABLED)
        self.after_idle(self._refresh_linenos)

    def get_code(self):
        return self.text.get('1.0', tk.END).strip()


# ─────────────────────── App ─────────────────────────────────────────────────

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
        self.geometry('1440x840')
        self.minsize(1000, 600)
        self.configure(bg=self.BG)
        self._uf = font.Font(family='Segoe UI', size=10)
        self._lf = font.Font(family='Segoe UI', size=10, weight='bold')
        self._mf = font.Font(family='Consolas', size=11)
        self._code_files = []
        self._file_var = tk.StringVar()
        self._file_selector = None
        self._build()

    def _lbl(self, parent, text):
        return tk.Label(parent, text=text, bg=self.BG, fg=self.FG, font=self._lf)

    def _prose_tw(self, parent):
        f = tk.Frame(parent, bg=self.TXT_BG)
        f.pack(fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(f, bg='#45475a', troughcolor=self.BG, relief=tk.FLAT)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tw = tk.Text(f, font=self._uf, wrap=tk.WORD,
                     bg=self.TXT_BG, fg=self.FG, insertbackground='#f5c2e7',
                     selectbackground='#45475a', relief=tk.FLAT,
                     state=tk.DISABLED, yscrollcommand=sb.set,
                     padx=10, pady=10, spacing1=2)
        tw.pack(fill=tk.BOTH, expand=True)
        sb.config(command=tw.yview)
        return tw

    def _build(self):
        # Bottom action bar
        bar = tk.Frame(self, bg=self.BG)
        bar.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 12))
        self.btn_analyze = tk.Button(
            bar, text='Analizuj', font=self._uf, cursor='hand2',
            bg=self.ACCENT, fg=self.BG, activebackground='#74c7ec',
            activeforeground=self.BG, relief=tk.FLAT, padx=20, pady=6,
            command=self._start,
        )
        self.btn_analyze.pack(side=tk.LEFT)
        self.lbl_status = tk.Label(bar, text='', bg=self.BG, fg=self.FG2, font=self._uf)
        self.lbl_status.pack(side=tk.LEFT, padx=14)
        self.btn_copy = tk.Button(
            bar, text='Kopiuj kod', font=self._uf, cursor='hand2',
            bg=self.TXT_BG, fg=self.FG, activebackground='#45475a',
            activeforeground=self.FG, relief=tk.FLAT, padx=16, pady=6,
            command=self._copy,
        )
        self.btn_copy.pack(side=tk.RIGHT)

        # ── Three-column horizontal PanedWindow ───────────────────────────────
        h = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=self.BG,
                           sashwidth=6, sashrelief=tk.FLAT, sashpad=2)
        h.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 6))

        # Column 1 — input code
        left = tk.Frame(h, bg=self.BG)
        self._lbl(left, 'Wklej kod do analizy').pack(anchor='w', pady=(0, 4))
        self.inp_canvas = CodeCanvas(left, self, editable=True)
        self.inp_canvas.pack(fill=tk.BOTH, expand=True)
        h.add(left, minsize=250)

        # Column 2 — info panels (analysis + summary stacked)
        mid = tk.Frame(h, bg=self.BG)
        v = tk.PanedWindow(mid, orient=tk.VERTICAL, bg=self.BG,
                           sashwidth=6, sashrelief=tk.FLAT, sashpad=2)
        v.pack(fill=tk.BOTH, expand=True)

        af = tk.Frame(v, bg=self.BG)
        self._lbl(af, 'Analiza architektoniczna').pack(anchor='w', pady=(0, 4))
        self.analysis_tw = self._prose_tw(af)
        _configure_md_tags(self.analysis_tw, self._uf)
        v.add(af, minsize=80)

        sf = tk.Frame(v, bg=self.BG)
        self._lbl(sf, 'Podsumowanie refaktoryzacji').pack(anchor='w', pady=(0, 4))
        self.summary_tw = self._prose_tw(sf)
        _configure_md_tags(self.summary_tw, self._uf)
        v.add(sf, minsize=60)

        h.add(mid, minsize=280)

        # Column 3 — refactored code
        right = tk.Frame(h, bg=self.BG)
        self._code_hdr = tk.Frame(right, bg=self.BG)
        self._code_hdr.pack(fill=tk.X, pady=(0, 4))
        self._lbl(self._code_hdr, 'Refaktoryzowany kod').pack(side=tk.LEFT)

        self.code_canvas = CodeCanvas(right, self, editable=False)
        self.code_canvas.pack(fill=tk.BOTH, expand=True)
        h.add(right, minsize=250)

    # ── File selector (shown above refactored code when > 1 file) ─────────────

    def _update_file_selector(self, names):
        if self._file_selector is not None:
            self._file_selector.destroy()
            self._file_selector = None

        if len(names) > 1:
            self._file_var.set(names[0])
            om = tk.OptionMenu(self._code_hdr, self._file_var, *names,
                               command=self._on_file_select)
            om.configure(bg=self.TXT_BG, fg=self.FG, activebackground='#45475a',
                         activeforeground=self.FG, relief=tk.FLAT,
                         font=font.Font(family='Consolas', size=9),
                         highlightthickness=0)
            om['menu'].configure(bg=self.TXT_BG, fg=self.FG,
                                 activebackground='#45475a', activeforeground=self.FG)
            om.pack(side=tk.LEFT, padx=(8, 0))
            self._file_selector = om
        elif len(names) == 1:
            lbl = tk.Label(self._code_hdr, text=f'— {names[0]}',
                           bg=self.BG, fg=self.FG2,
                           font=font.Font(family='Consolas', size=9))
            lbl.pack(side=tk.LEFT, padx=(6, 0))
            self._file_selector = lbl

    def _on_file_select(self, name):
        for n, code in self._code_files:
            if n == name:
                self.code_canvas.set_code(code)
                break

    # ── Actions ───────────────────────────────────────────────────────────────

    def _status(self, msg, color=None):
        self.lbl_status.config(text=msg, fg=color or self.FG2)

    def _start(self):
        code = self.inp_canvas.get_code()
        if not code:
            messagebox.showwarning('Brak kodu', 'Wklej kod przed analizą.')
            return
        self.btn_analyze.config(state=tk.DISABLED)
        render_md(self.analysis_tw, '')
        render_md(self.summary_tw, '')
        self.code_canvas.set_code('')
        self._update_file_selector([])
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

    def _load_files(self, files):
        self._code_files = files
        self._update_file_selector([name for name, _ in files])
        self.code_canvas.set_code(files[0][1] if files else '')

    def _err(self, msg):
        self._status(f'Błąd: {msg}', self.ERR)
        self.btn_analyze.config(state=tk.NORMAL)

    def _copy(self):
        text = self.code_canvas.get_code()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._status('Skopiowano do schowka.', self.OK)


if __name__ == '__main__':
    App().mainloop()
