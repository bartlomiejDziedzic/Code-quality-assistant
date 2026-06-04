import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv()

PROMPT_FILE = Path(__file__).parent / "promt.md"


def load_system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


def analyze_code(code: str) -> str:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    system_prompt = load_system_prompt()
    full_prompt = f"{system_prompt}\n\n### Code to Analyze\n```\n{code}\n```"

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=full_prompt,
        config={"max_output_tokens": 65536},
    )
    text = response.text
    print(f"[API] response length: {len(text)} chars")
    print("[API] raw response:\n" + "=" * 60)
    print(text)
    print("=" * 60)
    return text


if __name__ == "__main__":
    from gui import App, CodeAnalysisService
    App(CodeAnalysisService(analyze_code)).mainloop()
