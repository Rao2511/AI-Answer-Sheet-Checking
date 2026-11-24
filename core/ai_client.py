"""
Unified Multi-Provider AI Caller (Anthropic Claude & Google Gemini).
Supports automatic key detection, multimodal vision grading, exponential backoff, and fallback models.
"""
import json
import time
import random
import base64
from typing import List, Type, Any, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types

# Supported Claude Models
CLAUDE_MODELS = [
    "claude-sonnet-5-5",
    "claude-haiku-5-5",
    "claude-opus-5-5",
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "claude-sonnet-5",
    "claude-opus-5",
    "claude-3-5-sonnet-latest",
    "claude-3-5-sonnet-20241022",
]

# Default Gemini Models
GEMINI_DEFAULT_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-2.5-pro",
    "gemini-1.5-pro",
]

# Default Local Ollama Vision Models (Metal Apple Silicon accelerated)
OLLAMA_DEFAULT_MODELS = [
    "qwen2.5vl:7b",
    "qwen2.5vl:3b",
    "qwen2.5vl:latest",
    "llama3.2-vision:11b",
    "llama3.2-vision:latest",
    "llava:latest",
    "qwen2.5-vl:7b",
    "minicpm-v:latest",
]

DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434"


def is_local_provider(provider: Optional[str] = None, api_key: Optional[str] = None) -> bool:
    """Detects whether Local Offline (Ollama / Local ML) is the active engine."""
    if provider in ("Local Offline (Ollama)", "Local ML (Ollama)"):
        return True
    if api_key and api_key.strip().lower() in ("local", "ollama", "offline"):
        return True
    return False


def is_claude_key(api_key: str, provider: Optional[str] = None) -> bool:
    """Detects whether an API key belongs to Anthropic Claude or Google Gemini."""
    if is_local_provider(provider, api_key):
        return False
    if provider == "Anthropic Claude":
        return True
    if provider == "Google Gemini":
        return False
    clean = api_key.strip()
    return clean.startswith("sk-ant-")


def get_available_models(
    api_key: str,
    provider: Optional[str] = None,
    workspace_id: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> List[str]:
    """Returns available models based on active provider / API key."""
    # 1. Local Offline (Ollama)
    if is_local_provider(provider, api_key):
        clean_endpoint = (endpoint or DEFAULT_OLLAMA_ENDPOINT).rstrip("/")
        try:
            import urllib.request
            import json
            req = urllib.request.Request(f"{clean_endpoint}/api/tags", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                remote = [m["name"] for m in data.get("models", []) if "name" in m]
                if remote:
                    vision = [m for m in remote if any(v in m.lower() for v in ["vl", "vision", "llava", "minicpm"])]
                    others = [m for m in remote if m not in vision]
                    return vision + others
        except Exception as e:
            _safe_log(f"[AI_CLIENT] Could not dynamically list Ollama models: {e}")
        return OLLAMA_DEFAULT_MODELS

    # 2. Anthropic Claude
    if is_claude_key(api_key, provider):
        # Query Anthropic API dynamically
        try:
            import os, anthropic
            resolved_ws = (workspace_id or "").strip() or os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
            client_kwargs = {"api_key": api_key.strip()}
            if resolved_ws:
                client_kwargs["default_headers"] = {"anthropic-workspace-id": resolved_ws}
            client = anthropic.Anthropic(**client_kwargs)
            remote = [m.id for m in client.models.list()]
            if remote:
                # Rank: Sonnet, Haiku, Opus
                sonnets = [m for m in remote if "sonnet" in m]
                haikus = [m for m in remote if "haiku" in m]
                others = [m for m in remote if "sonnet" not in m and "haiku" not in m]
                return sonnets + haikus + others
        except Exception as e:
            _safe_log(f"[AI_CLIENT] Could not dynamically list Claude models: {e}")
        return CLAUDE_MODELS

    # 3. Google Gemini
    try:
        client = genai.Client(api_key=api_key)
        models = []
        for m in client.models.list():
            actions = getattr(m, 'supported_actions', []) or []
            if 'generateContent' in actions:
                clean_name = m.name.replace('models/', '')
                if 'gemini' in clean_name and not clean_name.endswith('-embedding'):
                    models.append(clean_name)
        flash_models = [m for m in models if 'flash' in m]
        other_models = [m for m in models if 'flash' not in m]
        return flash_models + other_models if models else GEMINI_DEFAULT_MODELS
    except Exception as e:
        _safe_log(f"[AI_CLIENT] Could not list Gemini models: {e}")
        return GEMINI_DEFAULT_MODELS


def _safe_log(msg: str) -> None:
    """Safely log to stdout/stderr without raising OSError if terminal pty is broken."""
    try:
        import sys
        sys.stdout.write(f"{msg}\n")
        sys.stdout.flush()
    except Exception:
        try:
            import sys
            sys.stderr.write(f"{msg}\n")
            sys.stderr.flush()
        except Exception:
            pass


def repair_truncated_json(text: str, validator=None) -> str:
    """
    Repairs truncated or malformed JSON output from LLMs by:
    1. Stripping markdown fences and locating the opening brace.
    2. Auto-closing unclosed string literals, lists, and objects.
    3. Trimming incomplete trailing elements until the JSON validates.
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    start = text.find("{")
    if start == -1:
        return text
    text = text[start:]

    def build_closed(s: str) -> str:
        stack = []
        in_str = False
        esc = False
        for ch in s:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == "\"":
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                if stack:
                    cur = stack[-1]
                    if (ch == "}" and cur == "{") or (ch == "]" and cur == "["):
                        stack.pop()

        closers = []
        for opener in reversed(stack):
            if opener == "{":
                closers.append("}")
            elif opener == "[":
                closers.append("]")
        return s + "".join(closers)

    def test_candidate(s: str) -> bool:
        try:
            cand = build_closed(s)
            json.loads(cand)
            if validator:
                validator(cand)
            return True
        except Exception:
            return False

    # Check direct
    if test_candidate(text):
        return build_closed(text)

    # Iteratively back up to previous comma, bracket, or brace
    cur = text
    for _ in range(200):
        idx = max(cur.rfind(","), cur.rfind("}"), cur.rfind("]"))
        if idx == -1:
            break
        cur = cur[:idx].rstrip()
        if test_candidate(cur):
            return build_closed(cur)

    # Fallback to direct closing
    try:
        return build_closed(text)
    except Exception:
        return text


def _clean_json_str(text: str, validator=None) -> str:
    """Extracts raw JSON substring from markdown fenced code blocks and repairs if truncated."""
    return repair_truncated_json(text, validator=validator)


def _call_claude_multimodal(
    api_key: str,
    prompt: str,
    images: List[bytes],
    response_schema: Type[BaseModel],
    preferred_model: str = "claude-sonnet-5-5",
    max_retries: int = 3,
    workspace_id: Optional[str] = None,
) -> str:
    """Invokes Anthropic Claude with multimodal image vision and JSON schema output."""
    import os
    import anthropic

    resolved_ws = (workspace_id or "").strip() or os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
    client_kwargs = {"api_key": api_key}
    if resolved_ws:
        client_kwargs["default_headers"] = {"anthropic-workspace-id": resolved_ws}
    client = anthropic.Anthropic(**client_kwargs)

    content_blocks = []
    # Add page images
    for img_bytes in images:
        b64_data = base64.b64encode(img_bytes).decode("utf-8")
        mime = "image/jpeg" if img_bytes[:2] == b"\xff\xd8" else "image/png"
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime,
                "data": b64_data,
            }
        })

    schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
    instructions = (
        f"{prompt}\n\n"
        "### STRICT OUTPUT FORMAT INSTRUCTION:\n"
        "You must respond with a single valid JSON object that strictly adheres to the following JSON Schema:\n"
        f"```json\n{schema_json}\n```\n"
        "Do not include any greeting, preamble, explanation outside JSON, or conversational markdown. "
        "Output ONLY the JSON object starting with '{' and ending with '}'."
    )
    content_blocks.append({
        "type": "text",
        "text": instructions,
    })

    # Fetch available models if possible or use fallback list
    available_remotes = []
    try:
        available_remotes = [m.id for m in client.models.list()]
    except Exception as e:
        _safe_log(f"[AI_CLIENT] Could not fetch remote models in _call_claude_multimodal: {e}")

    models_to_try = [preferred_model]
    if available_remotes:
        sonnets = [m for m in available_remotes if "sonnet" in m]
        opus = [m for m in available_remotes if "opus" in m]
        haikus = [m for m in available_remotes if "haiku" in m]
        ordered_remotes = sonnets + opus + haikus + [m for m in available_remotes if m not in sonnets + opus + haikus]
        for m in ordered_remotes:
            if m not in models_to_try:
                models_to_try.append(m)
    for m in CLAUDE_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)

    model_errors = {}
    for model_name in models_to_try:
        for attempt in range(1, max_retries + 1):
            try:
                create_kwargs = {
                    "model": model_name,
                    "max_tokens": 16384,
                    "messages": [
                        {
                            "role": "user",
                            "content": content_blocks,
                        }
                    ],
                }
                # Temperature is deprecated on Claude 5/4.5+ adaptive models. Only pass for legacy models if not deprecated.
                if any(legacy in model_name for legacy in ["claude-3-", "claude-2"]):
                    create_kwargs["temperature"] = 0.1

                try:
                    message = client.messages.create(**create_kwargs)
                except Exception as call_err:
                    if "temperature" in str(call_err).lower() and "deprecated" in str(call_err).lower():
                        # Retry immediately without temperature
                        create_kwargs.pop("temperature", None)
                        message = client.messages.create(**create_kwargs)
                    else:
                        raise call_err

                if message and message.content:
                    full_text = "".join(
                        block.text for block in message.content if hasattr(block, "text")
                    )
                    stop_reason = getattr(message, "stop_reason", "")
                    if stop_reason == "max_tokens":
                        _safe_log(f"[AI_CLIENT] Notice: Model '{model_name}' reached max_tokens limit. Auto-repairing JSON...")

                    clean_json = _clean_json_str(full_text, validator=response_schema.model_validate_json)
                    try:
                        response_schema.model_validate_json(clean_json)
                        return clean_json
                    except Exception as val_err:
                        _safe_log(f"[AI_CLIENT] Model '{model_name}' schema parse warning ({val_err}). Applying aggressive repair...")
                        repaired = repair_truncated_json(full_text, validator=response_schema.model_validate_json)
                        response_schema.model_validate_json(repaired)
                        return repaired

                raise RuntimeError("Claude returned an empty response.")
            except Exception as e:
                err_str = str(e)
                model_errors[model_name] = err_str
                _safe_log(f"[AI_CLIENT] Claude model '{model_name}' (attempt {attempt}/{max_retries}) error: {err_str}")

                # Immediate halts:
                # 1. Workspace header required error
                if "anthropic-workspace-id" in err_str.lower() or ("workspace" in err_str.lower() and "header" in err_str.lower()):
                    raise RuntimeError(
                        f"Anthropic Workspace ID is required: {err_str}\n\n"
                        "💡 To fix this:\n"
                        "Use a Workspace-scoped API key created in Anthropic Console (Workspaces > Select Workspace > API Keys)."
                    )

                # 2. Credit balance too low error
                if any(k in err_str.lower() for k in ["credit balance", "balance is too low", "purchase credits", "plans & billing", "insufficient_quota"]):
                    raise RuntimeError(
                        f"Anthropic Account Balance Error: Your Anthropic credit balance is too low to use Claude.\n"
                        f"Details: {err_str}\n\n"
                        "💡 To fix this: Add API credits in your Anthropic Console at https://console.anthropic.com/settings/plans"
                    )

                # 3. Invalid auth error
                if any(k in err_str.lower() for k in ["authentication_error", "status_code: 401", "error code: 401", "invalid x-api-key"]):
                    raise RuntimeError(f"Anthropic Claude API Key is invalid: {e}")

                # 4. Actual Permission Denied (403 status code, NOT model dates like 20240307)
                if "permission_denied" in err_str.lower() or "status_code: 403" in err_str.lower() or "error code: 403" in err_str.lower():
                    raise RuntimeError(f"Anthropic Permission Denied: Your API key does not have permission for this workspace/resource. ({err_str})")

                is_transient = any(
                    token in err_str.lower()
                    for token in ["429", "rate_limit", "529", "overloaded", "timeout", "temporarily"]
                )
                if is_transient and attempt < max_retries:
                    time.sleep(2 ** attempt + random.uniform(0.5, 1.5))
                    continue
                else:
                    break

    # Format helpful breakdown of all model attempts
    error_summary = "\n".join([f"• [{m}]: {err}" for m, err in model_errors.items()])
    raise RuntimeError(
        f"Claude evaluation failed across all models ({len(models_to_try)} attempted):\n{error_summary}\n\n"
        "💡 Tip: Use the '🔌 Test API Connection' button in the sidebar to verify which models are available on your Anthropic account."
    )


def _call_gemini_multimodal(
    api_key: str,
    prompt: str,
    images: List[bytes],
    response_schema: Type[BaseModel],
    preferred_model: str = "gemini-2.5-flash",
    max_retries_per_model: int = 3,
    temperature: float = 0.1,
) -> str:
    """Invokes Google Gemini with multimodal vision and response_schema."""
    client = genai.Client(api_key=api_key)

    contents = [prompt]
    for img_bytes in images:
        mime = "image/jpeg" if img_bytes[:2] == b"\xff\xd8" else "image/png"
        contents.append(
            types.Part.from_bytes(data=img_bytes, mime_type=mime)
        )

    # Dynamic model discovery
    available = get_available_models(api_key, provider="Google Gemini")
    models_to_try = [preferred_model]
    for m in available:
        if m not in models_to_try:
            models_to_try.append(m)

    model_errors = {}
    for model_name in models_to_try:
        for attempt in range(1, max_retries_per_model + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=response_schema,
                        temperature=temperature,
                    ),
                )
                # Extract text safely
                text = None
                if hasattr(response, "text") and response.text:
                    text = response.text
                elif hasattr(response, "candidates") and response.candidates:
                    parts = response.candidates[0].content.parts
                    text = "".join(p.text for p in parts if hasattr(p, "text") and p.text)

                if text:
                    clean_json = _clean_json_str(text)
                    response_schema.model_validate_json(clean_json)
                    return clean_json
                raise RuntimeError(f"Model {model_name} returned an empty response body.")
            except Exception as e:
                err_str = str(e)
                model_errors[model_name] = err_str

                if any(k in err_str.lower() for k in ["invalid api key", "unauthenticated", "401"]):
                    raise RuntimeError(f"Gemini API Key is invalid: {e}")

                is_transient = any(
                    k in err_str.lower()
                    for k in ["503", "unavailable", "high demand", "429", "resource_exhausted", "rate limit", "timeout"]
                )
                if is_transient and attempt < max_retries_per_model:
                    time.sleep(2 ** attempt + random.uniform(0.5, 1.5))
                    continue
                else:
                    break

    error_summary = "; ".join([f"[{m}]: {err[:100]}" for m, err in model_errors.items()])
    raise RuntimeError(f"All Gemini models failed. Errors: {error_summary}")


def _call_ollama_multimodal(
    prompt: str,
    images: List[bytes],
    response_schema: Type[BaseModel],
    preferred_model: str = "qwen2.5-vl:7b",
    endpoint: str = "http://127.0.0.1:11434",
    max_retries: int = 2,
) -> str:
    """
    Invokes local Ollama Vision model (e.g., Qwen2.5-VL, Llama3.2-Vision, LLaVA) via local REST API.
    Runs 100% offline with zero cloud API keys.
    """
    import urllib.request
    import urllib.error

    clean_endpoint = (endpoint or DEFAULT_OLLAMA_ENDPOINT).rstrip("/")

    # Prepare base64 images
    b64_images = []
    for img_bytes in images:
        b64_str = base64.b64encode(img_bytes).decode("utf-8")
        b64_images.append(b64_str)

    schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
    instructions = (
        f"{prompt}\n\n"
        "### STRICT OUTPUT FORMAT INSTRUCTION:\n"
        "You must respond with a single valid JSON object that strictly adheres to the following JSON Schema:\n"
        f"```json\n{schema_json}\n```\n"
        "Do not include any greeting, preamble, commentary, or text outside the JSON object. "
        "Output ONLY the JSON object starting with '{' and ending with '}'."
    )

    message_item = {
        "role": "user",
        "content": instructions,
    }
    if b64_images:
        message_item["images"] = b64_images

    payload = {
        "model": preferred_model,
        "messages": [message_item],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
        },
    }

    url = f"{clean_endpoint}/api/chat"
    data_bytes = json.dumps(payload).encode("utf-8")

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as response:
                res_raw = response.read().decode("utf-8")
                res_json = json.loads(res_raw)
                content = res_json.get("message", {}).get("content", "")
                if not content:
                    raise RuntimeError(f"Ollama model '{preferred_model}' returned empty content.")

                clean_json = _clean_json_str(content, validator=response_schema.model_validate_json)
                try:
                    response_schema.model_validate_json(clean_json)
                    return clean_json
                except Exception as val_err:
                    _safe_log(f"[AI_CLIENT] Ollama JSON repair: {val_err}")
                    repaired = repair_truncated_json(content, validator=response_schema.model_validate_json)
                    response_schema.model_validate_json(repaired)
                    return repaired

        except urllib.error.URLError as url_err:
            reason = str(getattr(url_err, "reason", url_err))
            if "connection refused" in reason.lower() or "111" in reason or "61" in reason:
                raise RuntimeError(
                    f"Cannot connect to local Ollama server at {clean_endpoint}.\n\n"
                    "💡 How to start Ollama:\n"
                    "1. Make sure Ollama is installed: brew install ollama (or visit https://ollama.com)\n"
                    "2. Start Ollama: run `ollama serve` or open the Ollama application\n"
                    "3. Download model: run `ollama run qwen2.5-vl` in your Terminal."
                )
            if attempt < max_retries:
                time.sleep(2)
                continue
            raise RuntimeError(f"Ollama network error connecting to {clean_endpoint}: {url_err}")
        except Exception as e:
            if attempt < max_retries:
                time.sleep(2)
                continue
            raise RuntimeError(f"Ollama inference error with model '{preferred_model}': {e}")


def generate_content_with_fallback(
    api_key: str,
    prompt: str,
    response_schema: Type[BaseModel],
    images: Optional[List[bytes]] = None,
    preferred_model: Optional[str] = None,
    provider: Optional[str] = None,
    workspace_id: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> str:
    """
    Main entry point for AI evaluation. Automatically selects between Anthropic Claude,
    Google Gemini, or Local Offline (Ollama) based on provider setting or API key.
    """
    images = images or []

    # 1. Local Offline (Ollama / Local ML)
    if is_local_provider(provider, api_key):
        model = preferred_model or "qwen2.5-vl:7b"
        if "claude" in model.lower() or "gemini" in model.lower():
            model = "qwen2.5-vl:7b"
        return _call_ollama_multimodal(
            prompt=prompt,
            images=images,
            response_schema=response_schema,
            preferred_model=model,
            endpoint=endpoint or DEFAULT_OLLAMA_ENDPOINT,
        )

    # 2. Anthropic Claude
    if is_claude_key(api_key, provider):
        model = preferred_model or "claude-sonnet-5-5"
        if "gemini" in model.lower() or "qwen" in model.lower() or "llama" in model.lower():
            model = "claude-sonnet-5-5"
        return _call_claude_multimodal(
            api_key=api_key,
            prompt=prompt,
            images=images,
            response_schema=response_schema,
            preferred_model=model,
            workspace_id=workspace_id,
        )

    # 3. Google Gemini
    else:
        model = preferred_model or "gemini-2.5-flash"
        if "claude" in model.lower() or "qwen" in model.lower() or "llama" in model.lower():
            model = "gemini-2.5-flash"
        return _call_gemini_multimodal(
            api_key=api_key,
            prompt=prompt,
            images=images,
            response_schema=response_schema,
            preferred_model=model,
        )


def test_api_connection(
    api_key: str,
    model_name: Optional[str] = None,
    workspace_id: Optional[str] = None,
    provider: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> tuple[bool, str, List[str]]:
    """
    Tests whether the selected provider (Claude, Gemini, or Local Ollama) is reachable and operational.
    Returns: (is_success, status_message, list_of_available_models)
    """
    # 1. Local Offline (Ollama)
    if is_local_provider(provider, api_key):
        clean_endpoint = (endpoint or DEFAULT_OLLAMA_ENDPOINT).rstrip("/")
        # Candidates for loopback addressing on macOS
        candidates = [clean_endpoint]
        if "localhost" in clean_endpoint:
            candidates.append(clean_endpoint.replace("localhost", "127.0.0.1"))
        elif "127.0.0.1" in clean_endpoint:
            candidates.append(clean_endpoint.replace("127.0.0.1", "localhost"))

        import urllib.request
        import urllib.error
        import json

        last_err = None
        for cand in candidates:
            try:
                req = urllib.request.Request(
                    f"{cand}/api/tags",
                    headers={"Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    remote_models = [m["name"] for m in data.get("models", []) if "name" in m]
                    vision = [m for m in remote_models if any(v in m.lower() for v in ["vl", "vision", "llava", "minicpm"])]
                    others = [m for m in remote_models if m not in vision]
                    all_local = vision + others if remote_models else OLLAMA_DEFAULT_MODELS

                    if remote_models:
                        model_list_preview = ", ".join(remote_models[:4])
                        return (
                            True,
                            f"Connected to Local Ollama at {cand}! Found {len(remote_models)} installed model(s) ({model_list_preview}).",
                            all_local,
                        )
                    else:
                        return (
                            True,
                            f"Connected to Local Ollama at {cand}, but no models are downloaded yet. Run `ollama run qwen2.5-vl` in your Terminal to download a model.",
                            OLLAMA_DEFAULT_MODELS,
                        )
            except urllib.error.URLError as e:
                last_err = e
                continue
            except Exception as e:
                last_err = e
                continue

        reason = str(getattr(last_err, "reason", last_err)) if last_err else "Connection failed"
        return (
            False,
            f"Cannot connect to Local Ollama at {clean_endpoint} ({reason}).\n\n"
            "💡 How to setup Local Offline ML on your Mac:\n"
            "1. Download Ollama: https://ollama.com/download (or run in Terminal: `curl -fsSL https://ollama.com/install.sh | sh`)\n"
            "2. Open the Ollama App from Applications (or run `ollama serve`)\n"
            "3. In Terminal, pull a Vision model: `ollama run qwen2.5-vl` (or `ollama run llama3.2-vision`)\n\n"
            "💡 Or Use Google Gemini (100% Free, Zero Setup):\n"
            "Switch to '🟢 Google Gemini' above. Google provides 1,500 free evaluations per day at https://aistudio.google.com/apikey without installing anything locally.",
            OLLAMA_DEFAULT_MODELS,
        )

    if not api_key or not api_key.strip():
        return False, "API key is empty.", []

    if is_claude_key(api_key, provider):
        import os
        import anthropic

        resolved_ws = (workspace_id or "").strip() or os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
        client_kwargs = {"api_key": api_key.strip()}
        if resolved_ws:
            client_kwargs["default_headers"] = {"anthropic-workspace-id": resolved_ws}

        client = anthropic.Anthropic(**client_kwargs)

        # 1. Fetch available models from account
        remote_models = []
        try:
            remote_models = [m.id for m in client.models.list()]
        except Exception as e:
            err_s = str(e)
            if "anthropic-workspace-id" in err_s.lower() or ("workspace" in err_s.lower() and "header" in err_s.lower()):
                return False, f"Anthropic Workspace ID is required: {err_s}. Please enter your Workspace ID in the sidebar.", []
            if any(k in err_s.lower() for k in ["authentication_error", "401", "invalid x-api-key"]):
                return False, f"Invalid API Key: {err_s}", []
            _safe_log(f"[AI_CLIENT] test_api_connection models.list notice: {e}")

        # Choose model to ping
        chosen_model = model_name
        if not chosen_model or (chosen_model not in remote_models and remote_models):
            chosen_model = remote_models[0] if remote_models else "claude-sonnet-5-5"

        # 2. Test minimal ping
        try:
            client.messages.create(
                model=chosen_model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Respond with OK"}],
            )
            return True, f"Connected to Anthropic Claude! Model '{chosen_model}' responded successfully.", remote_models or CLAUDE_MODELS
        except Exception as e:
            err_s = str(e)
            if "anthropic-workspace-id" in err_s.lower() or ("workspace" in err_s.lower() and "header" in err_s.lower()):
                return False, f"Workspace ID required: {err_s}. Please enter your Workspace ID in the sidebar.", remote_models
            if any(k in err_s.lower() for k in ["credit balance", "balance is too low", "purchase credits", "plans & billing"]):
                return False, f"Credit balance is too low: {err_s}\nAdd API credits at https://console.anthropic.com/settings/plans", remote_models
            if "not_found_error" in err_s.lower() or "404" in err_s:
                available_str = ", ".join(remote_models) if remote_models else "None listed"
                return False, f"Model '{chosen_model}' is not accessible on your account (404 Not Found).\nAvailable models: {available_str}", remote_models
            return False, f"Connection failed: {err_s}", remote_models

    else:
        # Gemini ping
        try:
            client = genai.Client(api_key=api_key.strip())
            models = get_available_models(api_key, provider="Google Gemini")
            test_m = model_name if (model_name and "gemini" in model_name) else (models[0] if models else "gemini-2.5-flash")
            client.models.generate_content(
                model=test_m,
                contents="Respond with OK",
            )
            return True, f"Connected to Google Gemini! Model '{test_m}' responded successfully.", models
        except Exception as e:
            return False, f"Gemini connection failed: {e}", []
