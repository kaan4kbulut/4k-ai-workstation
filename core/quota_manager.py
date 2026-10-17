import json
import os
from typing import Dict

DEFAULT_QUOTAS = {
    "Ollama": {"limit": 1000, "used": 0, "unit": "requests"},
    "Codex": {"limit": 100, "used": 0, "unit": "requests"},
    "Claude": {"limit": 50, "used": 0, "unit": "requests"},
    "Hermes": {"limit": 200, "used": 0, "unit": "requests"},
}


class QuotaManager:
    def __init__(self, quota_file: str = "data/quotas.json"):
        self.quota_file = quota_file
        self.quotas = self._load_quotas()

    def _load_quotas(self) -> Dict:
        if os.path.exists(self.quota_file):
            with open(self.quota_file, "r") as f:
                saved = json.load(f)
            # Kaydedilmiş sayaçları koru, ama dosya yazıldıktan sonra eklenen
            # modelleri (ör. yeni bir wrapper) de al ki kullanımları izlensin.
            merged = dict(DEFAULT_QUOTAS)
            merged.update(saved)
            return merged
        return dict(DEFAULT_QUOTAS)

    def _save_quotas(self):
        os.makedirs(os.path.dirname(self.quota_file), exist_ok=True)
        with open(self.quota_file, "w") as f:
            json.dump(self.quotas, f, indent=4)

    def has_quota(self, model_name: str) -> bool:
        if model_name not in self.quotas:
            return True  # Yerel/bilinmeyen modeller sınırsız kabul edilir
        
        quota = self.quotas[model_name]
        return quota["used"] < quota["limit"]

    def consume_quota(self, model_name: str):
        if model_name in self.quotas:
            self.quotas[model_name]["used"] += 1
            self._save_quotas()

    def get_quota_status(self) -> Dict:
        return self.quotas