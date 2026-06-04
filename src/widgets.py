import tkinter as tk
from typing import Any, Optional
from tkinter import font

from models import Theme
from renderers import SyntaxHighlighter


class CodeCanvas(tk.Frame):
    """Reusable code editor component with line numbers and syntax highlighting."""

    def __init__(self, parent: tk.Widget, font_code: font.Font, editable: bool = False) -> None:
        super().__init__(parent, bg=Theme.TXT_BG)
        self._editable = editable
        self._font_code = font_code
        self._mod_lock = False

        self._build_components()
        self._setup_bindings()

    def _build_components(self) -> None:
        gutter_frame = tk.Frame(self, bg=Theme.GUTTER_BG)
        gutter_frame.pack(side=tk.LEFT, fill=tk.Y)

        self._line_numbers = tk.Text(
            gutter_frame, width=4, bg=Theme.GUTTER_BG, fg=Theme.GUTTER_FG,
            font=self._font_code, relief=tk.FLAT, state=tk.DISABLED,
            padx=8, pady=10, spacing1=2, cursor='arrow',
            selectbackground=Theme.GUTTER_BG, selectforeground=Theme.GUTTER_FG,
        )
        self._line_numbers.pack(fill=tk.BOTH, expand=True)

        tk.Frame(self, bg=Theme.BORDER_COLOR, width=1).pack(side=tk.LEFT, fill=tk.Y)

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
