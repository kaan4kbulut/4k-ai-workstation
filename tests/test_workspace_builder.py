"""
Tests for core.workspace_builder.WorkspaceBuilder
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.workspace_builder import WorkspaceBuilder


class TestWorkspaceBuilder(unittest.TestCase):
    def test_extract_files_from_response_markdown_header(self):
        sample_llm_response = """
Here is the project setup:

### FILE: src/main.py
```python
import sys

def main():
    print("Hello from Nexus!")

if __name__ == "__main__":
    main()
```

### FILE: requirements.txt
```text
pytest>=7.0.0
```
"""
        files = WorkspaceBuilder.extract_files_from_response(sample_llm_response)
        self.assertIsInstance(files, list)
        self.assertEqual(len(files), 2)

        self.assertEqual(files[0]["path"], "src/main.py")
        self.assertIn('print("Hello from Nexus!")', files[0]["content"])
        self.assertEqual(files[1]["path"], "requirements.txt")
        self.assertIn("pytest>=7.0.0", files[1]["content"])

    def test_extract_files_from_json_response(self):
        json_response = """
```json
[
    {"path": "config/settings.json", "content": "{\\"debug\\": true}"},
    {"path": "README.md", "content": "# Readme"}
]
```
"""
        files = WorkspaceBuilder.extract_files_from_response(json_response)
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]["path"], "config/settings.json")
        self.assertIn('"debug": true', files[0]["content"])
        self.assertEqual(files[1]["path"], "README.md")

    def test_extract_files_empty_or_invalid(self):
        self.assertEqual(WorkspaceBuilder.extract_files_from_response(""), [])
        self.assertEqual(WorkspaceBuilder.extract_files_from_response("Just chatting, no code."), [])

    def test_apply_files_creates_files_and_directories(self):
        files_to_write = [
            {"path": "src/app/core.py", "content": "print('core running')\n"},
            {"path": "docs/README.md", "content": "# Documentation\n"},
            {"path": "run.py", "content": "import src.app.core\n"},
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            written = WorkspaceBuilder.apply_files(tmp_dir, files_to_write)
            self.assertEqual(len(written), 3)

            for item in files_to_write:
                file_path = Path(tmp_dir) / item["path"]
                self.assertTrue(file_path.exists())
                self.assertTrue(file_path.is_file())
                self.assertEqual(file_path.read_text(encoding="utf-8"), item["content"])

    def test_apply_files_path_traversal_security(self):
        malicious_files = [
            {"path": "../evil.py", "content": "import os; os.system('echo hacked')"},
            {"path": "../../outside.txt", "content": "escape"},
            {"path": "nested/../../another_evil.py", "content": "escape 2"},
            {"path": "safe.py", "content": "print('safe')"},
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            written = WorkspaceBuilder.apply_files(tmp_dir, malicious_files)
            # Yalnızca safe.py yazılmalıdır
            self.assertIn("safe.py", written)
            self.assertNotIn("../evil.py", written)
            self.assertNotIn("evil.py", written)
            self.assertNotIn("outside.txt", written)
            self.assertNotIn("another_evil.py", written)

            # tmp_dir dışına dosya yazılmadığını garanti et
            parent_dir = Path(tmp_dir).parent
            evil_target = parent_dir / "evil.py"
            self.assertFalse(evil_target.exists())

            # tmp_dir içinde safe.py olduğunu kontrol et
            safe_file = Path(tmp_dir) / "safe.py"
            self.assertTrue(safe_file.exists())
            self.assertEqual(safe_file.read_text(encoding="utf-8"), "print('safe')")

    def test_build_project_prompt_includes_user_request(self):
        prompt_request = "Create a FastAPI real-time chat application with WebSockets"
        prompt = WorkspaceBuilder.build_project_prompt(prompt_request)
        self.assertIn(prompt_request, prompt)
        self.assertIn("### FILE:", prompt)
        self.assertIn("4K AI WORKSTATION", prompt)


if __name__ == "__main__":
    unittest.main()
