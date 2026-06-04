import re
from dataclasses import dataclass
from typing import Callable, List, Optional


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

    MD_H3 = '#89dceb'
    MD_H4 = '#cba6f7'
    MD_CODE_BG = '#45475a'
    MD_CODE_FG = '#f38ba8'
    MD_SEP = '#585b70'


class ResponseParser:
    FILE_HDR_RE = re.compile(
        r'####\s+File\s+\d+:\s+`?([^`\n(]+?)`?(?:\s*\([^)]*\))?\s*\n'
    )
    CODE_BLOCK_RE = re.compile(r'```[\w]*\n(.*?)```', re.DOTALL)
    SECTION_3_RE = re.compile(r'###\s+3\.[^\n]*\n(.*?)(?=###\s+4\.|$)', re.DOTALL)
    SECTION_4_RE = re.compile(r'(###\s+4\.[^\n]*\n.*?)$', re.DOTALL)

    def extract_files(self, content: str) -> List[RefactoredFile]:
        # Skip FILE_HDR_RE matches that appear inside code blocks to avoid
        # treating string literals in refactored code as file headers.
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
    def __init__(self, analyze_func: Callable[[str], str]) -> None:
        self._analyze_func = analyze_func

    def analyze(self, source_code: str) -> str:
        if not source_code.strip():
            raise ValueError("Input code is empty.")
        return self._analyze_func(source_code)
