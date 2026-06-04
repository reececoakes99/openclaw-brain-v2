# SKILL: ollama-connector

## Identity
- **Name:** ollama-connector
- **Category:** Infrastructure
- **Trigger:** When setting up local model infrastructure, configuring brain-to-model connection, or replacing cloud APIs with local inference
- **Confidence requirement:** 5/10

## Overview

Ollama provides local LLM inference — your own GPU/CPU running models without cloud API calls. This eliminates per-token costs, removes network latency, and keeps data on-prem. The brain connects via HTTP API to `http://localhost:11434`.

**Cost:** $0 API spend (local hardware only)
**Latency:** ~50-500ms depending on hardware
**Privacy:** 100% local — nothing leaves your server

## Installation

### Step 1: Install Ollama

```bash
# Linux (one-liner)
curl -fsSL https://ollama.com/install.sh | sh

# Or via apt
curl -fsSL https://ollama.com/install.sh | sh

# Verify
ollama --version
```

### Step 2: Pull Models

```bash
# Core models (recommended for payment gateway red team)
ollama pull llama3.3:70b-instruct-q4_K_M   # Primary — 70B parameters, 43GB
ollama pull llama3.1:8b-instruct-q4_K_M    # Fast fallback — 8B, 5GB
ollama pull mixtral:8x22b-instruct-q4_K_M # Reasoning tasks — 8x22B, 47GB
ollama pull codellama:13b-instruct         # Code analysis

# Check available space first
df -h /
# Need ~50GB free for full model set

# List installed models
ollama list

# Remove a model
ollama rm llama3.1:8b-instruct-q4_K_M
```

### Step 3: Start Ollama Service

```bash
# Start as systemd service (auto-start on boot)
sudo systemctl enable ollama
sudo systemctl start ollama
sudo systemctl status ollama

# Or run manually (for testing)
ollama serve

# Test connection
curl http://localhost:11434/api/tags
```

### Step 4: Configure .env

Add to your `.env` file (copy from `.env.example`):

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.3:70b-instruct-q4_K_M
OLLAMA_FALLBACK_MODEL=llama3.1:8b-instruct-q4_K_M
OLLAMA_ENABLED=true
OLLAMA_TIMEOUT=120
```

### Step 5: Configure GPU Acceleration

```bash
# NVIDIA GPU (CUDA)
nvidia-smi  # Verify GPU detected
# Ollama auto-detects CUDA — no extra config needed

# AMD GPU (ROCm)
# Set environment before starting Ollama
export HSA_OVERRIDE_GFX_VERSION=11.0.0
export AMD_VULKAN_ICD=RADV
ollama serve

# Apple Silicon (M1/M2/M3/M4)
# Ollama auto-detects Metal — native performance
```

## Usage — Python API

### Basic Completion

```python
#!/usr/bin/env python3
"""
ollama_client.py — OpenClaw brain-to-Ollama connector
"""
import os
import json
import httpx
from typing import Optional

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
        """
        Generate completion via Ollama API

        Args:
            prompt: User prompt
            system: System prompt (e.g., agent instructions)
            model: Override default model
            temperature: Creativity (0.1=precise, 1.0=creative)
            num_ctx: Context window size

        Returns:
            Model response as string
        """
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
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                response.raise_for_status()
                return response.json().get('response', '')

        except httpx.TimeoutException:
            # Try fallback model
            if target_model == self.model and self.fallback_model:
                payload['model'] = self.fallback_model
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        f"{self.base_url}/api/generate",
                        json=payload
                    )
                    response.raise_for_status()
                    return response.json().get('response', '')
            raise

        except httpx.HTTPError as e:
            raise ConnectionError(f"Ollama API error: {e}")

    def chat(
        self,
        messages: list,
        model: str = None,
        temperature: float = 0.3,
        **kwargs
    ) -> str:
        """
        Chat completion (conversational format)

        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}
            model: Override default model
            temperature: Response creativity
        """
        target_model = model or self.model

        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                )
                response.raise_for_status()
                return response.json()['message']['content']
        except httpx.HTTPError as e:
            raise ConnectionError(f"Ollama chat error: {e}")

    def embeddings(self, text: str, model: str = "nomic-embed-text") -> list:
        """
        Generate text embeddings for RAG
        """
        payload = {
            "model": model,
            "prompt": text
        }

        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{self.base_url}/api/embeddings",
                json=payload
            )
            response.raise_for_status()
            return response.json().get('embedding', [])

    def health_check(self) -> dict:
        """
        Check Ollama status and available models
        """
        try:
            with httpx.Client(timeout=5) as client:
                # Check server
                tags = client.get(f"{self.base_url}/api/tags").json()

                # Check specific model
                model_info = client.post(
                    f"{self.base_url}/api/show",
                    json={"name": self.model}
                ).json()

                return {
                    "status": "healthy",
                    "models": [m['name'] for m in tags.get('models', [])],
                    "primary_model": self.model,
                    "memory_used": model_info.get('size', 0) // (1024**3),
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# --- Integration with OpenClaw brain ---

def run_with_ollama(prompt: str, context_file: str = None) -> str:
    """
    Run a prompt through Ollama with OpenClaw brain context.

    Usage:
        result = run_with_ollama("Analyze this target for payment vulnerabilities",
                                  context_file="knowledge/gateway_profiles/target/surface_scan.json")
    """
    ollama = OllamaConnector()

    # Build system prompt from brain files
    system_parts = []

    brain_files = [
        "SOUL.md",
        "AGENTS.md",
        "BOTS.md",
        "REASONING.md",
    ]

    for bf in brain_files:
        path = os.path.join(os.path.dirname(__file__), "..", bf)
        if os.path.exists(path):
            system_parts.append(open(path).read())

    system_prompt = "\n\n".join(system_parts)

    # Append context file if provided
    if context_file:
        if os.path.exists(context_file):
            context_data = open(context_file).read()
            prompt = f"{prompt}\n\n## Context Data\n{context_data}"

    return ollama.generate(prompt=prompt, system=system_prompt)


if __name__ == '__main__':
    import sys

    ollama = OllamaConnector()

    # Health check
    print("=== Ollama Health Check ===")
    health = ollama.health_check()
    print(json.dumps(health, indent=2))

    if health['status'] == 'healthy':
        print(f"\n=== Testing Generation ===")
        response = ollama.generate(
            prompt="What is ISO8583 field 4? Answer concisely.",
            system="You are a payment systems expert. Answer only payment security questions.",
            temperature=0.1
        )
        print(response)
    else:
        print(f"\n⚠️  Ollama not healthy: {health.get('error')}")
        print("\nTo install: curl -fsSL https://ollama.com/install.sh | sh")
        print("To start: ollama serve")
        print("To pull model: ollama pull llama3.3:70b-instruct-q4_K_M")
        sys.exit(1)
```

### Quick test

```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Test via Python
python3 skills/ollama-connector/ollama_client.py
```

## Model Selection Guide

| Model | Size | VRAM | Speed | Best For |
|---|---|---|---|---|
| llama3.3:70b | 43GB | 48GB+ | Slow | Complex reasoning, planning |
| mixtral:8x22b | 47GB | 48GB+ | Slow | Multi-task, agents |
| llama3.1:8b | 5GB | 8GB | Fast | Routine tasks, summaries |
| llama3.1:70b | 40GB | 48GB | Medium | Large context analysis |
| codellama:13b | 8GB | 10GB | Fast | Code review, parsing |

## Troubleshooting

| Problem | Solution |
|---|---|
| `curl: (7) Failed to connect` | `ollama serve` not running — start it |
| `model not found` | `ollama pull llama3.3:70b-instruct-q4_K_M` |
| Out of memory (CUDA) | Use smaller model or reduce `num_ctx` |
| Slow generation | Normal for large models; use 8B for speed |
| Connection refused | Check Ollama listening on correct interface |

## Output

This skill enables the brain to run without cloud API costs. Set `OLLAMA_ENABLED=true` in `.env` and the pipeline will route all model calls through local Ollama first.

## Cross-References

- `COST_GOVERNOR.md` — budget management (set to $0 when Ollama is primary)
- `pipeline/master_pipeline.py` — model routing in pipeline
- `cost-governor` skill — API spend tracking