import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv()

PROMPT_FILE = Path(__file__).parent / "promt.md"


def load_system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


def read_code_from_console() -> str:
    print("Wklej fragment kodu do analizy.")
    print("Kiedy skończysz, wpisz '---' w nowej linii i naciśnij Enter.\n")
    lines = []
    for line in sys.stdin:
        if line.rstrip() == "---":
            break
        lines.append(line)
    return "".join(lines)


def analyze_code(code: str) -> str:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    system_prompt = load_system_prompt()
    full_prompt = f"{system_prompt}\n\n### Code to Analyze\n```\n{code}\n```"

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=full_prompt,
    )
    return response.text


def main():
    code = read_code_from_console()
    if not code.strip():
        print("Nie podano kodu do analizy.")
        return

    print("\nAnalizuję kod...\n")
    result = analyze_code(code)
    print(result)


if __name__ == "__main__":
    main()
