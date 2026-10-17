import asyncio
from .base_wrapper import BaseWrapper

class OllamaWrapper(BaseWrapper):
    def __init__(self, model_name: str = "llama3"):
        super().__init__("Ollama")
        self.model_name = model_name

    async def execute(self, prompt: str) -> str:
        # Simulating a CLI call to Ollama: ollama run llama3 "prompt"
        process = await asyncio.create_subprocess_exec(
            'ollama', 'run', self.model_name, prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            return stdout.decode().strip()
        else:
            return f"Error running Ollama: {stderr.decode().strip()}"

    async def check_quota(self) -> float:
        # Local models have unlimited quota
        return 1.0