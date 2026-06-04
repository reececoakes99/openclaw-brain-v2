#!/usr/bin/env python3
"""
ollama_client.py — OpenClaw brain-to-Ollama connector
Connects the OpenClaw-v2 brain to local Ollama inference
"""
import os
import json
import sys
import httpx
from typing import Optional, List, Dict

class OllamaConnector:
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model = model or os.environ.get('OLLAMA_MODEL', 'llama3.3:70b-instruct-q4_K_M')
        self.fallback_model = os.environ.get('OLLAMA_FALLBACK_MODEL', 'llama3.1:8b-instruct-q4_K_M')
        self.timeout = int(os.environ.get('OLLAMA_TIMEOUT', '120'))

    def generate(
        self,
        prompt: str,
        system: str = None,
        model: str = None,
        temperature: float = 0.3,
        num_ctx: int = 8192,
        **kwargs
    ) -> str:
        target_model = model or self.model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
                "stop": ["</s>", "\n\n---", "---END---"],
            }
        }
        if system:
            payload["system"] = system
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                return response.json().get('response', '')
        except httpx.TimeoutException:
            if target_model == self.model and self.fallback_model:
                payload['model'] = self.fallback_model
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(f"{self.base_url}/api/generate", json=payload)
                    response.raise_for_status()
                    return response.json().get('response', '')
            raise
        except httpx.HTTPError as e:
            raise ConnectionError(f"Ollama API error: {e}")

    def chat(self, messages: List[Dict], model: str = None, temperature: float = 0.3, **kwargs) -> str:
        target_model = model or self.model
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature}
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                return response.json()['message']['content']
        except httpx.HTTPError as e:
            raise ConnectionError(f"Ollama chat error: {e}")

    def embeddings(self, text: str, model: str = "nomic-embed-text") -> list:
        payload = {"model": model, "prompt": text}
        with httpx.Client(timeout=30) as client:
            response = client.post(f"{self.base_url}/api/embeddings", json=payload)
            response.raise_for_status()
            return response.json().get('embedding', [])

    def health_check(self) -> dict:
        try:
            with httpx.Client(timeout=5) as client:
                tags = client.get(f"{self.base_url}/api/tags").json()
                model_info = client.post(
                    f"{self.base_url}/api/show",
                    json={"name": self.model}
                ).json()
                return {
                    "status": "healthy",
                    "models": [m['name'] for m in tags.get('models', [])],
                    "primary_model": self.model,
                    "memory_gb": round(model_info.get('size', 0) / (1024**3), 1),
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


def run_with_ollama(prompt: str, context_file: str = None) -> str:
    """Run prompt through Ollama with OpenClaw brain context."""
    ollama = OllamaConnector()
    brain_files = ["SOUL.md", "AGENTS.md", "BOTS.md", "REASONING.md"]
    system_parts = []
    for bf in brain_files:
        path = os.path.join(os.path.dirname(__file__), "..", bf)
        if os.path.exists(path):
            system_parts.append(open(path).read())
    system_prompt = "\n\n".join(system_parts)
    if context_file and os.path.exists(context_file):
        context_data = open(context_file).read()
        prompt = f"{prompt}\n\n## Context Data\n{context_data}"
    return ollama.generate(prompt=prompt, system=system_prompt)


if __name__ == '__main__':
    print("=== Ollama Health Check ===")
    ollama = OllamaConnector()
    health = ollama.health_check()
    print(json.dumps(health, indent=2))
    if health['status'] == 'healthy':
        print("\n=== Testing Generation ===")
        response = ollama.generate(
            prompt="What is ISO8583 field 4? Answer concisely.",
            system="You are a payment systems expert.",
            temperature=0.1
        )
        print(response)
    else:
        print(f"\n⚠️ Ollama not healthy: {health.get('error')}")
        print("Install: curl -fsSL https://ollama.com/install.sh | sh")
        print("Start: ollama serve")
        print("Pull: ollama pull llama3.3:70b-instruct-q4_K_M")
        sys.exit(1)
