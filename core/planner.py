import asyncio
from typing import List, Dict

class TaskPlanner:
    def __init__(self):
        # In a real version, this would use a high-tier LLM to split the prompt
        pass

    async def decompose(self, prompt: str) -> List[Dict]:
        """
        Splits a complex prompt into smaller, independent sub-tasks.
        """
        print(f"[Planner] Decomposing task: {prompt[:50]}...")
        
        # Simulated decomposition logic for the prototype
        # If the prompt is long or contains keywords, split it.
        if len(prompt) > 50 or "and" in prompt.lower():
            return [
                {"id": 1, "task": f"Analyze and plan: {prompt}", "complexity": 9, "type": "architecture"},
                {"id": 2, "task": f"Implement basic logic for: {prompt}", "complexity": 6, "type": "code"},
                {"id": 3, "task": f"Create documentation for: {prompt}", "complexity": 3, "type": "docs"},
            ]
        
        return [{"id": 1, "task": prompt, "complexity": 5, "type": "general"}]