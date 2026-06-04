import logging
import re
import threading
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, List, Tuple, Dict, Any, Optional
from tkinter import font, messagebox

from pygments import lex
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename, guess_lexer, TextLexer
from pygments.token import Token

# Set up logging for professional error diagnosis
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Domain Models & Configuration (Clean Data Layers)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RefactoredFile:
    name: str
    content: str


@dataclass(frozen=True)
class AnalysisResult:
    analysis: str
    files: List[RefactoredFile]
    summary: str


class Theme:
    """Centralized Theme Palette keeping style variables out of business logic."""
    BG = '#1e1e2e'
    TXT_BG = '#313244'
    FG = '#cdd6f4'
    FG2 = '#a6adc8'
    ACCENT = '#89b4fa'
    OK = '#a6e3a1'
    WARN = '#f9e2af'
    ERR = '#f38ba8'
    GUTTER_BG = '#181825'
    GUTTER_FG = '#585b70'
    BORDER_COLOR = '#45475a'
    CURSOR_COLOR = '#f5c2e7'
    
    # Markdown specific colors
    MD_H3 = '#89dceb'
    MD_H4 = '#cba6f7'
    MD_CODE_BG = '#45475a'
    MD_CODE_FG = '#f38ba8'
    MD_SEP = '#585b70'


# ─────────────────────────────────────────────────────────────────────────────
# 2. Domain Services (Isolated Business Logic, fully testable)
# ─────────────────────────────────────────────────────────────────────────────

class ResponseParser:
    """Pure domain service for extracting structural details from markdown text."""
    
    FILE_HDR_RE = re.compile(
        r'####\s+File\s+\d+:\s+`?([^`\n(]+?)`?(?:\s*\([^)]*\))?\s*\n'
    )
    CODE_BLOCK_RE = re.compile(r'```[\w]*\n(.*?)```', re.DOTALL)
    SECTION_3_RE = re.compile(r'###\s+3\.[^\n]*\n(.*?)(?=###\s+4\.|$)', re.DOTALL)
    SECTION_4_RE = re.compile(r'(###\s+4\.[^\n]*\n.*?)$', re.DOTALL)

    def extract_files(self, content: str) -> List[RefactoredFile]:
        # Exclude positions inside code blocks so that FILE_HDR_RE appearing
        # as a string literal in refactored code doesn't create a spurious
        # file-header match and truncate the extracted output.
        code_ranges = [(m.start(), m.end())
                       for m in re.finditer(r'```[\w]*\n.*?```', content, re.DOTALL)]

        def _in_code(pos: int) -> bool:
            return any(s <= pos < e for s, e in code_ranges)

        headers = [m for m in self.FILE_HDR_RE.finditer(content) if not _in_code(m.start())]
        files: List[RefactoredFile] = []

        for i, match in enumerate(headers):
            name = match.group(1).strip()
            start = match.end()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(content)

            code_match = self.CODE_BLOCK_RE.search(content, start, end)
            if code_match:
                files.append(RefactoredFile(name=name, content=code_match.group(1).rstrip()))

        # Fallback: single file without specific headers
        if not files:
            code_match = self.CODE_BLOCK_RE.search(content)
            if code_match:
                files.append(RefactoredFile(name='refactored_code', content=code_match.group(1).rstrip()))

        return files

    def parse(self, text: str) -> AnalysisResult:
        s3_match = self.SECTION_3_RE.search(text)
        s4_match = self.SECTION_4_RE.search(text)
        
        analysis = text[: s3_match.start() if s3_match else len(text)].strip()
        files = self.extract_files(s3_match.group(1)) if s3_match else []
        summary = s4_match.group(1).strip() if s4_match else ''
        
        return AnalysisResult(analysis=analysis, files=files, summary=summary)


class CodeAnalysisService:
    """Abstraction wrapper for external analyzer dependencies."""
    def __init__(self, analyze_func: Callable[[str], str]) -> None:
        self._analyze_func = analyze_func

    def analyze(self, source_code: str) -> str:
        if not source_code.strip():
            raise ValueError("Input code is empty.")
        return self._analyze_func(source_code)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Presenter & Rendering Utilities
# ─────────────────────────────────────────────────────────────────────────────

class SyntaxHighlighter:
    """Shared pygments→tkinter syntax-highlighting utility.

    Tk text tags are scoped per widget, so the same tag names can carry
    different styling in the Markdown panes (code-block background + margins)
    and in the IDE-style CodeCanvas (plain editor background)."""

    # Maps pygments token base types to tag names
    _TOKEN_MAP: Dict[Any, str] = {
        Token.Keyword:            'syn_keyword',
        Token.Name.Builtin:       'syn_builtin',
        Token.Name.Function:      'syn_function',
        Token.Name.Class:         'syn_class',
        Token.Name.Decorator:     'syn_decorator',
        Token.String:             'syn_string',
        Token.Number:             'syn_number',
        Token.Comment:            'syn_comment',
        Token.Operator:           'syn_operator',
        Token.Punctuation:        'syn_punct',
    }

    # tag name -> (foreground colour, italic?)  — Catppuccin Mocha palette
    _PALETTE: Dict[str, Tuple[str, bool]] = {
        'syn_keyword':   ('#cba6f7', False),
        'syn_builtin':   ('#f38ba8', False),
        'syn_function':  ('#89b4fa', False),
        'syn_class':     ('#f9e2af', False),
        'syn_decorator': ('#fab387', False),
        'syn_string':    ('#a6e3a1', False),
        'syn_number':    ('#fab387', False),
        'syn_comment':   ('#585b70', True),
        'syn_operator':  ('#89dceb', False),
        'syn_punct':     ('#cdd6f4', False),
    }

    @classmethod
    def token_to_tag(cls, ttype: Any) -> Optional[str]:
        while ttype is not Token and ttype:
            if ttype in cls._TOKEN_MAP:
                return cls._TOKEN_MAP[ttype]
            ttype = ttype.parent
        return None

    @classmethod
    def configure_tags(cls, widget: tk.Text, size: int, background: str, **extra: Any) -> None:
        regular = font.Font(family='Consolas', size=size)
        italic = font.Font(family='Consolas', size=size, slant='italic')
        for tag, (color, is_italic) in cls._PALETTE.items():
            widget.tag_configure(
                tag, font=italic if is_italic else regular,
                foreground=color, background=background, **extra
            )

    @staticmethod
    def lexer_for(name: Optional[str] = None, lang: Optional[str] = None, code: str = ''):
        try:
            if lang:
                return get_lexer_by_name(lang, stripall=False)
            if name:
                return get_lexer_for_filename(name, stripall=False)
        except Exception:
            pass
        try:
            if code.strip():
                return guess_lexer(code)
        except Exception:
            pass
        return TextLexer()

    @classmethod
    def insert_highlighted(cls, widget: tk.Text, code: str, lexer,
                           fallback_tag: Optional[str] = None) -> None:
        for ttype, value in lex(code, lexer):
            tag = cls.token_to_tag(ttype) or fallback_tag
            widget.insert(tk.END, value, (tag,) if tag else ())


class MarkdownRenderer:
    """Renders formatted Markdown tags inside tk.Text widgets."""
    INLINE_RE = re.compile(r'(\*\*[^*\n]+?\*\*|\*[^*\n]+?\*|`[^`\n]+?`)')

    @classmethod
    def configure_tags(cls, widget: tk.Text, base_font: font.Font) -> None:
        family = base_font.cget('family')
        size = int(base_font.cget('size'))

        widget.tag_configure(
            'h3',
            font=font.Font(family=family, size=size + 2, weight='bold'),
            foreground=Theme.MD_H3, spacing1=6, spacing3=4
        )
        widget.tag_configure(
            'h4',
            font=font.Font(family=family, size=size + 1, weight='bold'),
            foreground=Theme.MD_H4, spacing1=4, spacing3=2
        )
        widget.tag_configure(
            'bold',
            font=font.Font(family=family, size=size, weight='bold')
        )
        widget.tag_configure(
            'italic',
            font=font.Font(family=family, size=size, slant='italic')
        )
        widget.tag_configure(
            'code',
            font=font.Font(family='Consolas', size=size),
            background=Theme.MD_CODE_BG, foreground=Theme.MD_CODE_FG
        )
        widget.tag_configure(
            'code_block',
            font=font.Font(family='Consolas', size=size),
            background=Theme.MD_CODE_BG, foreground=Theme.FG,
            lmargin1=12, lmargin2=12, spacing1=1, spacing3=1
        )
        widget.tag_configure(
            'code_lang',
            font=font.Font(family='Consolas', size=size - 1, slant='italic'),
            background=Theme.GUTTER_BG, foreground=Theme.GUTTER_FG,
            lmargin1=12, spacing1=4, spacing3=2
        )

        # Syntax-highlight colour tags (code-block background + margins)
        SyntaxHighlighter.configure_tags(
            widget, size, Theme.MD_CODE_BG,
            lmargin1=12, lmargin2=12, spacing1=1, spacing3=1
        )

        widget.tag_configure('sep', foreground=Theme.MD_SEP)
        widget.tag_configure('bullet', lmargin1=6, lmargin2=18)
        widget.tag_configure('nested', lmargin1=22, lmargin2=36)

    @classmethod
    def _highlight_block(cls, widget: tk.Text, code: str, lang: str) -> None:
        lexer = SyntaxHighlighter.lexer_for(lang=lang)
        SyntaxHighlighter.insert_highlighted(widget, code, lexer, fallback_tag='code_block')

    @classmethod
    def _render_inline(cls, widget: tk.Text, text: str, *extra_tags: str) -> None:
        for part in cls.INLINE_RE.split(text):
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

    @classmethod
    def render(cls, widget: tk.Text, text: str) -> None:
        widget.config(state=tk.NORMAL)
        widget.delete('1.0', tk.END)
        in_block = False
        block_lang = ''
        block_lines: List[str] = []

        for line in text.splitlines():
            s = line.strip()
            if s.startswith('```'):
                if not in_block:
                    block_lang = s[3:].strip()
                    block_lines = []
                    widget.insert(tk.END, '\n')
                    label = block_lang if block_lang else 'code'
                    widget.insert(tk.END, f' {label}\n', 'code_lang')
                else:
                    cls._highlight_block(widget, '\n'.join(block_lines) + '\n', block_lang)
                    widget.insert(tk.END, '\n')
                in_block = not in_block
                continue
            if in_block:
                block_lines.append(line)
                continue
            if s.startswith('#### '):
                widget.insert(tk.END, s[5:] + '\n', 'h4')
            elif s.startswith('### '):
                widget.insert(tk.END, s[4:] + '\n', 'h3')
            elif s in ('---', '___', '***'):
                widget.insert(tk.END, '─' * 64 + '\n', 'sep')
            elif re.match(r'^\s{4,}[*-]\s{3}', line):
                widget.insert(tk.END, '      ◦ ')
                cls._render_inline(widget, s.lstrip('*- '), 'nested')
                widget.insert(tk.END, '\n')
            elif re.match(r'^[*-]\s{3}', s):
                widget.insert(tk.END, '  • ')
                cls._render_inline(widget, s[4:], 'bullet')
                widget.insert(tk.END, '\n')
            else:
                cls._render_inline(widget, line)
                widget.insert(tk.END, '\n')

        widget.config(state=tk.DISABLED)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Independent Custom Components (Decoupled from App subclass)
# ─────────────────────────────────────────────────────────────────────────────

class CodeCanvas(tk.Frame):
    """Reusable, decoupled code editor component with custom styling options."""

    def __init__(self, parent: tk.Widget, font_code: font.Font, editable: bool = False) -> None:
        super().__init__(parent, bg=Theme.TXT_BG)
        self._editable = editable
        self._font_code = font_code
        self._mod_lock = False

        self._build_components()
        self._setup_bindings()

    def _build_components(self) -> None:
        # Gutter (Line numbers)
        gutter_frame = tk.Frame(self, bg=Theme.GUTTER_BG)
        gutter_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        self._line_numbers = tk.Text(
            gutter_frame, width=4, bg=Theme.GUTTER_BG, fg=Theme.GUTTER_FG,
            font=self._font_code, relief=tk.FLAT, state=tk.DISABLED,
            padx=8, pady=10, spacing1=2, cursor='arrow',
            selectbackground=Theme.GUTTER_BG, selectforeground=Theme.GUTTER_FG,
        )
        self._line_numbers.pack(fill=tk.BOTH, expand=True)

        # Thin Vertical Separator
        tk.Frame(self, bg=Theme.BORDER_COLOR, width=1).pack(side=tk.LEFT, fill=tk.Y)

        # Main Code Area
        inner_frame = tk.Frame(self, bg=Theme.TXT_BG)
        inner_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._scrollbar_y = tk.Scrollbar(inner_frame, bg=Theme.BORDER_COLOR, troughcolor=Theme.BG, relief=tk.FLAT)
        self._scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self._scrollbar_x = tk.Scrollbar(inner_frame, orient=tk.HORIZONTAL, bg=Theme.BORDER_COLOR,
                                         troughcolor=Theme.BG, relief=tk.FLAT)
        self._scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.text = tk.Text(
            inner_frame, font=self._font_code, wrap=tk.NONE,
            bg=Theme.TXT_BG, fg=Theme.FG, insertbackground=Theme.CURSOR_COLOR,
            selectbackground=Theme.BORDER_COLOR, relief=tk.FLAT,
            state=tk.NORMAL if self._editable else tk.DISABLED,
            yscrollcommand=self._on_yscroll,
            xscrollcommand=self._scrollbar_x.set,
            padx=10, pady=10, spacing1=2,
        )
        self.text.pack(fill=tk.BOTH, expand=True)

        # IDE-style syntax colours on the editor background (no extra margins)
        SyntaxHighlighter.configure_tags(self.text, int(self._font_code.cget('size')), Theme.TXT_BG)

        self._scrollbar_y.config(command=self._on_yview)
        self._scrollbar_x.config(command=self.text.xview)

    def _setup_bindings(self) -> None:
        self.text.bind('<<Modified>>', self._on_modified)
        self.text.bind('<Configure>', lambda _: self.after_idle(self._refresh_line_numbers))

    def _on_yscroll(self, first: float, last: float) -> None:
        self._scrollbar_y.set(first, last)
        self._line_numbers.yview_moveto(first)

    def _on_yview(self, *args: Any) -> None:
        self.text.yview(*args)
        self._line_numbers.yview(*args)

    def _on_modified(self, _: Any = None) -> None:
        if self._mod_lock:
            return
        self._mod_lock = True
        self.text.edit_modified(False)
        self._mod_lock = False
        self.after_idle(self._refresh_line_numbers)

    def _refresh_line_numbers(self) -> None:
        line_count = int(self.text.index(tk.END).split('.')[0]) - 1
        numbers_string = '\n'.join(str(i) for i in range(1, max(line_count, 1) + 1))
        
        self._line_numbers.config(state=tk.NORMAL)
        self._line_numbers.delete('1.0', tk.END)
        self._line_numbers.insert(tk.END, numbers_string)
        self._line_numbers.config(state=tk.DISABLED)
        self._line_numbers.yview_moveto(self.text.yview()[0])

    def set_code(self, code: str, name: Optional[str] = None) -> None:
        self.text.config(state=tk.NORMAL)
        self.text.delete('1.0', tk.END)
        if code:
            lexer = SyntaxHighlighter.lexer_for(name=name, code=code)
            SyntaxHighlighter.insert_highlighted(self.text, code, lexer)
        if not self._editable:
            self.text.config(state=tk.DISABLED)
        self.after_idle(self._refresh_line_numbers)

    def get_code(self) -> str:
        return self.text.get('1.0', tk.END).strip()


# ─────────────────────────────────────────────────────────────────────────────
# 5. Core Window Shell (Presentation and Event bindings only)
# ─────────────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    """Refactored UI container following Clean Architecture principles."""

    def __init__(self, analyzer_service: CodeAnalysisService) -> None:
        super().__init__()
        self._analyzer_service = analyzer_service
        self._parser = ResponseParser()
        self._code_files: List[RefactoredFile] = []
        
        self._setup_window()
        self._initialize_fonts()
        self._build_ui()

    def _setup_window(self) -> None:
        self.title('Code Quality Assistant')
        self.geometry('1440x840')
        self.minsize(1000, 600)
        self.configure(bg=Theme.BG)

    def _initialize_fonts(self) -> None:
        self._font_ui = font.Font(family='Segoe UI', size=10)
        self._font_ui_bold = font.Font(family='Segoe UI', size=10, weight='bold')
        self._font_code = font.Font(family='Consolas', size=11)

    def _build_ui(self) -> None:
        self._file_var = tk.StringVar()
        self._file_selector: Optional[tk.Widget] = None
        
        self._build_action_bar()
        
        # Grid/Pane distribution
        paned_workspace = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=Theme.BG,
                                        sashwidth=6, sashrelief=tk.FLAT, sashpad=2)
        paned_workspace.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 6))

        # Column 1 — Input Panel
        left_column = tk.Frame(paned_workspace, bg=Theme.BG)
        self._create_header_label(left_column, 'Paste code to analyze').pack(anchor='w', pady=(0, 4))
        self.input_canvas = CodeCanvas(left_column, self._font_code, editable=True)
        self.input_canvas.pack(fill=tk.BOTH, expand=True)
        paned_workspace.add(left_column, minsize=250)

        # Column 2 — Middle Split Panel (Analysis + Summary)
        middle_column = tk.Frame(paned_workspace, bg=Theme.BG)
        vertical_workspace = tk.PanedWindow(middle_column, orient=tk.VERTICAL, bg=Theme.BG,
                                            sashwidth=6, sashrelief=tk.FLAT, sashpad=2)
        vertical_workspace.pack(fill=tk.BOTH, expand=True)

        analysis_frame = tk.Frame(vertical_workspace, bg=Theme.BG)
        self._create_header_label(analysis_frame, 'Architectural Analysis').pack(anchor='w', pady=(0, 4))
        self.analysis_text_area = self._create_scrollable_text(analysis_frame)
        MarkdownRenderer.configure_tags(self.analysis_text_area, self._font_ui)
        vertical_workspace.add(analysis_frame, minsize=80)

        summary_frame = tk.Frame(vertical_workspace, bg=Theme.BG)
        self._create_header_label(summary_frame, 'Refactoring Summary').pack(anchor='w', pady=(0, 4))
        self.summary_text_area = self._create_scrollable_text(summary_frame)
        MarkdownRenderer.configure_tags(self.summary_text_area, self._font_ui)
        vertical_workspace.add(summary_frame, minsize=60)

        paned_workspace.add(middle_column, minsize=280)

        # Column 3 — Right Panel (Refactored code output)
        right_column = tk.Frame(paned_workspace, bg=Theme.BG)
        self._header_frame_right = tk.Frame(right_column, bg=Theme.BG)
        self._header_frame_right.pack(fill=tk.X, pady=(0, 4))
        self._create_header_label(self._header_frame_right, 'Refactored Code').pack(side=tk.LEFT)

        self.output_code_canvas = CodeCanvas(right_column, self._font_code, editable=False)
        self.output_code_canvas.pack(fill=tk.BOTH, expand=True)
        paned_workspace.add(right_column, minsize=250)

    def _create_header_label(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(parent, text=text, bg=Theme.BG, fg=Theme.FG, font=self._font_ui_bold)

    def _create_scrollable_text(self, parent: tk.Widget) -> tk.Text:
        frame = tk.Frame(parent, bg=Theme.TXT_BG)
        frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(frame, bg=Theme.BORDER_COLOR, troughcolor=Theme.BG, relief=tk.FLAT)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(
            frame, font=self._font_ui, wrap=tk.WORD,
            bg=Theme.TXT_BG, fg=Theme.FG, insertbackground=Theme.CURSOR_COLOR,
            selectbackground=Theme.BORDER_COLOR, relief=tk.FLAT,
            state=tk.DISABLED, yscrollcommand=scrollbar.set,
            padx=10, pady=10, spacing1=2
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        return text_widget

    def _build_action_bar(self) -> None:
        action_bar = tk.Frame(self, bg=Theme.BG)
        action_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 12))
        
        self.btn_analyze = tk.Button(
            action_bar, text='Analyze', font=self._font_ui, cursor='hand2',
            bg=Theme.ACCENT, fg=Theme.BG, activebackground='#74c7ec',
            activeforeground=Theme.BG, relief=tk.FLAT, padx=20, pady=6,
            command=self._on_analyze_request,
        )
        self.btn_analyze.pack(side=tk.LEFT)
        
        self.lbl_status = tk.Label(action_bar, text='', bg=Theme.BG, fg=Theme.FG2, font=self._font_ui)
        self.lbl_status.pack(side=tk.LEFT, padx=14)
        
        self.btn_copy = tk.Button(
            action_bar, text='Copy Code', font=self._font_ui, cursor='hand2',
            bg=Theme.TXT_BG, fg=Theme.FG, activebackground=Theme.BORDER_COLOR,
            activeforeground=Theme.FG, relief=tk.FLAT, padx=16, pady=6,
            command=self._on_copy_request,
        )
        self.btn_copy.pack(side=tk.RIGHT)

    def _update_file_selector(self, names: List[str]) -> None:
        if self._file_selector is not None:
            self._file_selector.destroy()
            self._file_selector = None

        if len(names) > 1:
            self._file_var.set(names[0])
            option_menu = tk.OptionMenu(
                self._header_frame_right, self._file_var, *names,
                command=self._on_file_select
            )
            option_menu.configure(
                bg=Theme.TXT_BG, fg=Theme.FG, activebackground=Theme.BORDER_COLOR,
                activeforeground=Theme.FG, relief=tk.FLAT,
                font=font.Font(family='Consolas', size=9),
                highlightthickness=0
            )
            option_menu['menu'].configure(
                bg=Theme.TXT_BG, fg=Theme.FG,
                activebackground=Theme.BORDER_COLOR, activeforeground=Theme.FG
            )
            option_menu.pack(side=tk.LEFT, padx=(8, 0))
            self._file_selector = option_menu
        elif len(names) == 1:
            lbl = tk.Label(
                self._header_frame_right, text=f'— {names[0]}',
                bg=Theme.BG, fg=Theme.FG2,
                font=font.Font(family='Consolas', size=9)
            )
            lbl.pack(side=tk.LEFT, padx=(6, 0))
            self._file_selector = lbl

    def _on_file_select(self, target_name: str) -> None:
        for f in self._code_files:
            if f.name == target_name:
                self.output_code_canvas.set_code(f.content, f.name)
                break

    def _set_status(self, msg: str, color: Optional[str] = None) -> None:
        self.lbl_status.config(text=msg, fg=color or Theme.FG2)

    def _on_analyze_request(self) -> None:
        code = self.input_canvas.get_code()
        if not code:
            messagebox.showwarning('No Code', 'Paste code before analyzing.')
            return
            
        self.btn_analyze.config(state=tk.DISABLED)
        MarkdownRenderer.render(self.analysis_text_area, '')
        MarkdownRenderer.render(self.summary_text_area, '')
        self.output_code_canvas.set_code('')
        self._update_file_selector([])
        
        self._set_status('Analyzing...', Theme.WARN)
        
        # Safe thread execution
        threading.Thread(
            target=self._run_analysis_pipeline, 
            args=(code,), 
            daemon=True
        ).start()

    def _run_analysis_pipeline(self, code_to_analyze: str) -> None:
        try:
            raw_response = self._analyzer_service.analyze(code_to_analyze)
            # Marshal GUI changes back to the main thread securely
            self.after(0, self._render_results, raw_response)
        except Exception as exc:
            logging.exception("Error during analysis pipeline processing.")
            self.after(0, self._handle_pipeline_failure, str(exc))

    def _render_results(self, raw_data: str) -> None:
        try:
            parsed = self._parser.parse(raw_data)
            
            logging.info(f"Successfully parsed response. File count: {len(parsed.files)}")

            MarkdownRenderer.render(self.analysis_text_area, parsed.analysis)
            
            self._code_files = parsed.files
            file_names = [f.name for f in parsed.files]
            self._update_file_selector(file_names)
            
            default_file = parsed.files[0] if parsed.files else None
            self.output_code_canvas.set_code(
                default_file.content if default_file else '',
                default_file.name if default_file else None,
            )

            MarkdownRenderer.render(self.summary_text_area, parsed.summary)
            
            self._set_status('Done.', Theme.OK)
        except Exception as exc:
            logging.exception("GUI rendering error.")
            self._handle_pipeline_failure(f"Invalid output format: {exc}")
        finally:
            self.btn_analyze.config(state=tk.NORMAL)

    def _handle_pipeline_failure(self, error_message: str) -> None:
        self._set_status(f'Error: {error_message}', Theme.ERR)
        self.btn_analyze.config(state=tk.NORMAL)

    def _on_copy_request(self) -> None:
        text = self.output_code_canvas.get_code()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._set_status('Copied to clipboard.', Theme.OK)


if __name__ == '__main__':
    # Concrete application bootstrapper:
    # Safely import dependencies only inside initialization contexts.
    try:
        from main import analyze_code as concrete_analyze_code
    except ImportError:
        logging.warning("Main analysis module not found. Falling back to stub analysis execution.")
        def concrete_analyze_code(c: str) -> str: 
            return "### 3. File 1: `mock.py`\n```python\nprint('Test mock output')\n```\n### 4. Summary\nAll clear."

    analyzer_service_instance = CodeAnalysisService(concrete_analyze_code)
    app = App(analyzer_service_instance)
    app.mainloop()