# Code Quality Assistant

Asystent analizy kodu oparty na modelu Gemini (Google AI). Wklej fragment kodu, a aplikacja wskaże problemy, zaproponuje refaktoryzację i wygeneruje poprawione pliki.

---

## Wymagania

- Python 3.10 lub nowszy
- Klucz API Gemini (Google AI Studio)

---

## Instalacja

1. **Sklonuj lub pobierz repozytorium**

2. **Utwórz i aktywuj wirtualne środowisko**

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

3. **Zainstaluj zależności**

   ```bash
   pip install google-genai python-dotenv
   ```

---

## Konfiguracja klucza API

Aplikacja odczytuje klucz Gemini z pliku `.env` znajdującego się w głównym katalogu projektu.

1. Utwórz plik `.env` w katalogu `Code-quality-assistant/` (obok folderu `src/`):

   ```
   GEMINI_API_KEY=twój_klucz_tutaj
   ```

2. Klucz API pobierzesz bezpłatnie na stronie **Google AI Studio**:
   `https://aistudio.google.com/app/apikey`

> **Uwaga:** Plik `.env` jest wpisany do `.gitignore` — nigdy nie trafi do repozytorium, więc klucz pozostaje prywatny.

---

## Uruchomienie

### Tryb graficzny (GUI)

Uruchamia okno aplikacji z polem do wklejenia kodu i panelem wyników.

```bash
cd src
python gui.py
```

### Tryb konsolowy

Wklej kod bezpośrednio w terminalu.

```bash
cd src
python main.py
```

Po uruchomieniu wklej kod, a gdy skończysz — wpisz `---` w nowej linii i naciśnij Enter.

---

## Struktura projektu

```
Code-quality-assistant/
├── src/
│   ├── main.py      # logika analizy + tryb konsolowy
│   ├── gui.py       # interfejs graficzny (tkinter)
│   └── promt.md     # systemowy prompt dla modelu
├── .env             # klucz API (nie commituj!)
├── .gitignore
└── README.md
```

---

## Licencja

Projekt dostępny na licencji zawartej w pliku [LICENSE](LICENSE).
