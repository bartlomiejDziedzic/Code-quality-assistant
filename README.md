# Code Quality Assistant

A code analysis assistant powered by the Gemini (Google AI) model. Paste a code snippet into the GUI, and the app will identify issues, suggest refactoring, and generate improved files.

---

## Requirements

- Python 3.10 or newer
- Gemini API key (Google AI Studio)

---

## Installation

1. **Clone or download the repository**

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   ```

   Windows (PowerShell):
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   Windows (CMD):
   ```cmd
   .venv\Scripts\activate.bat
   ```

3. **Install dependencies**

   ```bash
   pip install google-genai python-dotenv
   ```

---

## API Key Configuration

The app reads the Gemini key from a `.env` file located in the project root.

1. Create a `.env` file in the `Code-quality-assistant/` directory (next to the `src/` folder):

   ```
   GEMINI_API_KEY=your_key_here
   ```

2. You can get a free API key at **[Google AI Studio](https://aistudio.google.com/app/apikey)**

---

## Running the App

```bash
cd src
python main.py
```

This opens the GUI window where you can paste code and view the analysis results.

---

## Project Structure

```
Code-quality-assistant/
├── src/
│   ├── main.py      # analysis logic + GUI entry point
│   ├── gui.py       # graphical interface (tkinter)
│   └── promt.md     # system prompt for the model
├── .env             # API key (do not commit!)
├── .gitignore
└── README.md
```

---

## License

This project is available under the license found in the [LICENSE](LICENSE) file.
