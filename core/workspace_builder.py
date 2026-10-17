"""
4K AI WORKSTATION - Proje ve Çalışma Alanı Oluşturucu (WorkspaceBuilder)
LLM çıktılarından çoklu dosya bloklarını ayrıştırır ve hedef çalışma alanına güvenli şekilde yazar.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


class WorkspaceBuilder:
    """
    Kullanıcının verdiği görevden veya LLM çıktısından çoklu dosya bloklarını
    (örn: ### FILE: dosya_yolu, ```dil:dosya_yolu veya JSON) ayrıştırıp
    hedef proje klasörüne güvenli şekilde yazan sınıf.
    """

    @staticmethod
    def build_project_prompt(user_prompt: str) -> str:
        """
        LLM'den dosyaları `### FILE: <relative_path>` ardından kod bloğu formatında
        üretmesini isteyen standartlaştırılmış proje üretim şablonu.
        """
        return f"""You are an elite software architect and full-stack developer in 4K AI WORKSTATION.
Your task is to build a complete, runnable, production-quality project based on the following request:

\"\"\"{user_prompt}\"\"\"

CRITICAL INSTRUCTIONS FOR FILE GENERATION:
1. Output every file using this exact header format:
### FILE: <relative_path_to_file>
```<language>
<complete file content here>
```

Examples:
### FILE: app/main.py
```python
def main():
    print("Nexus Workstation")

if __name__ == "__main__":
    main()
```

### FILE: requirements.txt
```
fastapi>=0.100.0
uvicorn>=0.20.0
```

2. Generate ALL required files (source code, configuration, README.md, dependencies).
3. Do NOT use placeholders, ellipsis (...), or comments like "// TODO implement later".
4. Provide full, working implementation ready to run in the target workspace.
"""

    @staticmethod
    def extract_files_from_response(response_text: str) -> list[dict]:
        """
        LLM yanıt metninden dosya listesini ayrıştırır.
        Desteklenen formatlar:
        1. JSON liste veya {"files": [...]}
        2. `### FILE: <path>` ardından gelen kod blokları
        3. ````<lang>:<path> ... ```` blokları

        Döndürür: [{"path": "relative/path.ext", "content": "..."}]
        """
        if not response_text:
            return []

        files: list[dict] = []
        seen_paths: set[str] = set()

        def _clean_path(p: str) -> str:
            p = p.strip().strip("`'\" \t\r\n")
            # ./ veya .\ ile başlıyorsa temizle
            p = re.sub(r"^(\.[/\\])+", "", p)
            # Slash'ları düzelt
            p = p.replace("\\", "/")
            return p

        # 1. JSON kontrolü
        json_candidates: list[str] = []
        trimmed = response_text.strip()
        if (trimmed.startswith("{") and trimmed.endswith("}")) or (
            trimmed.startswith("[") and trimmed.endswith("]")
        ):
            json_candidates.append(trimmed)

        for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", response_text, re.IGNORECASE):
            json_candidates.append(match.group(1).strip())

        for cand in json_candidates:
            try:
                data = json.loads(cand)
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    if "files" in data and isinstance(data["files"], list):
                        items = data["files"]
                    elif "project" in data and isinstance(data["project"], list):
                        items = data["project"]

                parsed_json_files: list[dict] = []
                for item in items:
                    if isinstance(item, dict) and "path" in item and "content" in item:
                        c_path = _clean_path(str(item["path"]))
                        if c_path:
                            parsed_json_files.append({
                                "path": c_path,
                                "content": str(item["content"]),
                            })

                if parsed_json_files:
                    return parsed_json_files
            except Exception:
                pass

        # 2. `### FILE: <path>` veya `FILE: <path>` formatı
        file_header_pattern = re.compile(
            r"(?:###|##|#)?\s*(?:FILE|File|Dosya)\s*:\s*([^\r\n`]+)",
            re.IGNORECASE,
        )

        header_matches = list(file_header_pattern.finditer(response_text))
        if header_matches:
            for i, match in enumerate(header_matches):
                raw_path = match.group(1)
                clean_p = _clean_path(raw_path)
                if not clean_p:
                    continue

                start_pos = match.end()
                end_pos = (
                    header_matches[i + 1].start()
                    if i + 1 < len(header_matches)
                    else len(response_text)
                )
                section = response_text[start_pos:end_pos].strip()

                # Bu bölümün içinde ```lang ... ``` kod bloğu var mı?
                cb_match = re.search(
                    r"```[a-zA-Z0-9_\-+.]*\r?\n([\s\S]*?)\r?\n```",
                    section,
                )
                if cb_match:
                    content = cb_match.group(1)
                else:
                    # Kod bloğu etiketi yoksa veya tek taraflıysa
                    content = re.sub(r"^```[a-zA-Z0-9_\-+.]*\r?\n", "", section)
                    content = re.sub(r"\r?\n```\s*$", "", content)

                if clean_p not in seen_paths:
                    files.append({"path": clean_p, "content": content})
                    seen_paths.add(clean_p)

        # 3. ````<lang>:<path>\n<content>\n```` formatı (örn: ```python:src/main.py)
        if not files:
            lang_path_pattern = re.compile(
                r"```[a-zA-Z0-9_\-+]*[:=]([^\r\n`]+)\r?\n([\s\S]*?)```"
            )
            for match in lang_path_pattern.finditer(response_text):
                raw_path = match.group(1)
                content = match.group(2)

                clean_p = _clean_path(raw_path)
                if clean_p and clean_p not in seen_paths:
                    files.append({"path": clean_p, "content": content})
                    seen_paths.add(clean_p)

        return files

    @staticmethod
    def apply_files(workspace_dir: str, files: list[dict]) -> list[str]:
        """
        Dosyaları workspace_dir altına güvenli şekilde yazar.
        Dizin dışına çıkmayı ('..', sürücü harfleri, kök mutlak yollar vb.) engeller.
        Yazılan dosyaların göreceli yollarını döndürür.
        """
        if not workspace_dir or not files:
            return []

        base_path = Path(workspace_dir).resolve()
        base_path.mkdir(parents=True, exist_ok=True)

        written_files: list[str] = []

        for item in files:
            rel_path_str = str(item.get("path", "")).strip()
            content = str(item.get("content", ""))

            if not rel_path_str:
                continue

            # Sürücü harfli mutlak yolları (örn: C:\Windows...) engelle
            if re.match(r"^[a-zA-Z]:", rel_path_str):
                continue

            # Baştaki slash veya ./ işaretlerini temizle
            cleaned_rel = rel_path_str.lstrip("/\\")
            cleaned_rel = re.sub(r"^(\.[/\\])+", "", cleaned_rel)

            target_file = (base_path / cleaned_rel).resolve()

            # Güvenlik Kontrolü: target_file kesinlikle base_path altında olmalıdır
            try:
                target_file.relative_to(base_path)
            except ValueError:
                # Dizin dışına taşma engellendi ('..' vb.)
                continue

            # Hedefin base_path'in kendisi olmasını engelle
            if target_file == base_path:
                continue

            # Üst dizinleri oluştur
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Dosyayı yaz
            target_file.write_text(content, encoding="utf-8")

            written_rel = target_file.relative_to(base_path).as_posix()
            written_files.append(written_rel)

        return written_files
