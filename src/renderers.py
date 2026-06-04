import re
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple
from tkinter import font

from pygments import lex
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename, guess_lexer, TextLexer
from pygments.token import Token

from models import Theme


class SyntaxHighlighter:
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
    INLINE_RE = re.compile(r'(\*\*[^*\n]+?\*\*|\*[^*\n]+?\*|`[^`\n]+?`)')

    @classmethod
    def configure_tags(cls, widget: tk.Text, base_font: font.Font) -> None:
        family = base_font.cget('family')
        size = int(base_font.cget('size'))

        widget.tag_configure('h3', font=font.Font(family=family, size=size + 2, weight='bold'),
                             foreground=Theme.MD_H3, spacing1=6, spacing3=4)
        widget.tag_configure('h4', font=font.Font(family=family, size=size + 1, weight='bold'),
                             foreground=Theme.MD_H4, spacing1=4, spacing3=2)
        widget.tag_configure('bold', font=font.Font(family=family, size=size, weight='bold'))
        widget.tag_configure('italic', font=font.Font(family=family, size=size, slant='italic'))
        widget.tag_configure('code', font=font.Font(family='Consolas', size=size),
                             background=Theme.MD_CODE_BG, foreground=Theme.MD_CODE_FG)
        widget.tag_configure('code_block', font=font.Font(family='Consolas', size=size),
                             background=Theme.MD_CODE_BG, foreground=Theme.FG,
                             lmargin1=12, lmargin2=12, spacing1=1, spacing3=1)
        widget.tag_configure('code_lang', font=font.Font(family='Consolas', size=size - 1, slant='italic'),
                             background=Theme.GUTTER_BG, foreground=Theme.GUTTER_FG,
                             lmargin1=12, spacing1=4, spacing3=2)

        SyntaxHighlighter.configure_tags(widget, size, Theme.MD_CODE_BG,
                                         lmargin1=12, lmargin2=12, spacing1=1, spacing3=1)

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
