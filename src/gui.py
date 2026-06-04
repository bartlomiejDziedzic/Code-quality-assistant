import logging
import threading
import tkinter as tk
from typing import List, Optional
from tkinter import font, messagebox

from models import Theme, RefactoredFile, CodeAnalysisService, ResponseParser
from renderers import MarkdownRenderer
from widgets import CodeCanvas

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class App(tk.Tk):
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

        paned_workspace = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=Theme.BG,
                                         sashwidth=6, sashrelief=tk.FLAT, sashpad=2)
        paned_workspace.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 6))

        left_column = tk.Frame(paned_workspace, bg=Theme.BG)
        self._create_header_label(left_column, 'Paste code to analyze').pack(anchor='w', pady=(0, 4))
        self.input_canvas = CodeCanvas(left_column, self._font_code, editable=True)
        self.input_canvas.pack(fill=tk.BOTH, expand=True)
        paned_workspace.add(left_column, minsize=250)

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
        threading.Thread(target=self._run_analysis_pipeline, args=(code,), daemon=True).start()

    def _run_analysis_pipeline(self, code_to_analyze: str) -> None:
        try:
            raw_response = self._analyzer_service.analyze(code_to_analyze)
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
    try:
        from main import analyze_code as concrete_analyze_code
    except ImportError:
        logging.warning("Main analysis module not found. Falling back to stub.")
        def concrete_analyze_code(_: str) -> str:
            return "### 3. File 1: `mock.py`\n```python\nprint('Test mock output')\n```\n### 4. Summary\nAll clear."

    analyzer_service_instance = CodeAnalysisService(concrete_analyze_code)
    app = App(analyzer_service_instance)
    app.mainloop()
