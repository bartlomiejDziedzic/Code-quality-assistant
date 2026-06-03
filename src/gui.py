import threading
import tkinter as tk
from tkinter import font, messagebox

from main import analyze_code


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Code Quality Assistant")
        self.geometry("1000x700")
        self.minsize(700, 500)
        self.configure(bg="#1e1e2e")
        self._build_ui()

    def _build_ui(self):
        mono = font.Font(family="Consolas", size=11)
        label_font = font.Font(family="Segoe UI", size=10, weight="bold")
        btn_font = font.Font(family="Segoe UI", size=10)

        # ── top: two panes ──────────────────────────────────────────────────
        panes = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg="#1e1e2e",
                               sashwidth=6, sashrelief=tk.FLAT)
        panes.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 6))

        # ── left pane ───────────────────────────────────────────────────────
        left = tk.Frame(panes, bg="#1e1e2e")
        tk.Label(left, text="Wklej kod do analizy", bg="#1e1e2e",
                 fg="#cdd6f4", font=label_font).pack(anchor="w", pady=(0, 4))

        self.input_text = self._make_text(left, mono)
        self.input_text.pack(fill=tk.BOTH, expand=True)
        panes.add(left, minsize=300)

        # ── right pane ──────────────────────────────────────────────────────
        right = tk.Frame(panes, bg="#1e1e2e")
        tk.Label(right, text="Poprawiony kod", bg="#1e1e2e",
                 fg="#cdd6f4", font=label_font).pack(anchor="w", pady=(0, 4))

        self.output_text = self._make_text(right, mono, editable=False)
        self.output_text.pack(fill=tk.BOTH, expand=True)
        panes.add(right, minsize=300)

        # ── bottom bar ──────────────────────────────────────────────────────
        bar = tk.Frame(self, bg="#1e1e2e")
        bar.pack(fill=tk.X, padx=12, pady=(0, 12))

        self.analyze_btn = tk.Button(
            bar, text="Analizuj", font=btn_font, cursor="hand2",
            bg="#89b4fa", fg="#1e1e2e", activebackground="#74c7ec",
            activeforeground="#1e1e2e", relief=tk.FLAT, padx=20, pady=6,
            command=self._start_analysis,
        )
        self.analyze_btn.pack(side=tk.LEFT)

        self.status_label = tk.Label(
            bar, text="", bg="#1e1e2e", fg="#a6adc8", font=btn_font
        )
        self.status_label.pack(side=tk.LEFT, padx=14)

        self.copy_btn = tk.Button(
            bar, text="Kopiuj wynik", font=btn_font, cursor="hand2",
            bg="#313244", fg="#cdd6f4", activebackground="#45475a",
            activeforeground="#cdd6f4", relief=tk.FLAT, padx=16, pady=6,
            command=self._copy_output,
        )
        self.copy_btn.pack(side=tk.RIGHT)

    # ── helpers ─────────────────────────────────────────────────────────────

    def _make_text(self, parent, mono_font, *, editable=True):
        frame = tk.Frame(parent, bg="#313244", bd=1, relief=tk.FLAT)
        frame.pack(fill=tk.BOTH, expand=True)

        sb = tk.Scrollbar(frame, bg="#45475a", troughcolor="#1e1e2e",
                          relief=tk.FLAT)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        state = tk.NORMAL if editable else tk.DISABLED
        widget = tk.Text(
            frame, font=mono_font, wrap=tk.NONE,
            bg="#313244", fg="#cdd6f4", insertbackground="#f5c2e7",
            selectbackground="#45475a", relief=tk.FLAT,
            state=state, yscrollcommand=sb.set, padx=8, pady=8,
        )
        widget.pack(fill=tk.BOTH, expand=True)
        sb.config(command=widget.yview)
        return widget

    def _set_status(self, text, color="#a6adc8"):
        self.status_label.config(text=text, fg=color)

    # ── actions ─────────────────────────────────────────────────────────────

    def _start_analysis(self):
        code = self.input_text.get("1.0", tk.END).strip()
        if not code:
            messagebox.showwarning("Brak kodu", "Wklej kod przed analizą.")
            return

        self.analyze_btn.config(state=tk.DISABLED)
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state=tk.DISABLED)
        self._set_status("Analizuję...", "#f9e2af")

        threading.Thread(target=self._run_analysis, args=(code,),
                         daemon=True).start()

    def _run_analysis(self, code: str):
        try:
            result = analyze_code(code)
            self.after(0, self._show_result, result)
        except Exception as exc:
            self.after(0, self._show_error, str(exc))

    def _show_result(self, result: str):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert("1.0", result)
        self.output_text.config(state=tk.DISABLED)
        self._set_status("Gotowe.", "#a6e3a1")
        self.analyze_btn.config(state=tk.NORMAL)

    def _show_error(self, message: str):
        self._set_status(f"Błąd: {message}", "#f38ba8")
        self.analyze_btn.config(state=tk.NORMAL)

    def _copy_output(self):
        text = self.output_text.get("1.0", tk.END).strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("Skopiowano do schowka.", "#a6e3a1")


if __name__ == "__main__":
    App().mainloop()
