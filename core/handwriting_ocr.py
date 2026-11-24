"""
Handwriting OCR & Image Enhancement Module.

Provides:
- High-contrast handwriting image preprocessing (auto-contrast, stroke darkening, sharpening)
- Specialized Handwriting Text Recognition (HTR) transcription prompts for cursive, messy, and faint student handwriting
- Formula & mathematical symbol preservation
"""
import io
from typing import List, Optional
from PIL import Image, ImageEnhance, ImageOps
from google import genai
from google.genai import types
from core.ai_client import generate_content_with_fallback


def enhance_handwriting_image(
    img_bytes: bytes,
    contrast_boost: float = 1.4,
    sharpness_boost: float = 1.6,
    auto_contrast_cutoff: int = 1,
) -> bytes:
    """
    Enhances scanned student answer sheet images to make handwritten pen/pencil strokes
    darker, crisper, and higher contrast against paper backgrounds.
    """
    try:
        img = Image.open(io.BytesIO(img_bytes))
        
        # Ensure RGB mode
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # 1. Dynamic range stretching (makes light paper white and faint ink dark)
        img = ImageOps.autocontrast(img, cutoff=auto_contrast_cutoff)

        # 2. Contrast boost (darkens ink strokes)
        enhancer_contrast = ImageEnhance.Contrast(img)
        img = enhancer_contrast.enhance(contrast_boost)

        # 3. Sharpness boost (clarifies cursive loops and fine math strokes)
        enhancer_sharp = ImageEnhance.Sharpness(img)
        img = enhancer_sharp.enhance(sharpness_boost)

        # Output high-quality JPEG
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=95, optimize=True)
        return out.getvalue()
    except Exception as e:
        from core.ai_client import _safe_log
        _safe_log(f"[HANDWRITING_ENHANCER] Error enhancing image: {e}")
        return img_bytes  # Return original if enhancement fails


def transcribe_handwritten_sheet(
    page_images: List[bytes],
    api_key: str,
    model_name: Optional[str] = None,
    workspace_id: Optional[str] = None,
    provider: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> str:
    """
    Transcribes handwritten student answer sheets with specialized HTR prompting.
    Reads cursive handwriting, equations, math derivations, and MCQ selections using Claude, Gemini, or Local Ollama.
    """
    import os
    from core.ai_client import is_claude_key, is_local_provider, DEFAULT_OLLAMA_ENDPOINT, _safe_log
    import base64

    prompt = (
        "You are an expert Handwriting Recognition (HTR) and academic transcription specialist.\n"
        "The attached images are scanned pages of a student's real handwritten exam answer sheet.\n\n"
        "### Instructions:\n"
        "1. Carefully examine all handwritten text, cursive words, numbers, and symbols on every page.\n"
        "2. Identify each question attempt (e.g., 'Q1', 'Question 1', 'Ans 1', '1.', '(a)', '(i)').\n"
        "3. Transcribe the student's handwritten answers VERBATIM, line by line.\n"
        "4. For mathematical formulas, equations, or calculations, transcribe every intermediate step in clear notation or LaTeX.\n"
        "5. For Multiple Choice Questions (MCQ), record the letter chosen (A, B, C, D) or ticked option.\n"
        "6. If handwriting is cursive, slanted, or faint, use surrounding context and stroke geometry to transcribe accurately.\n"
        "7. Note any crossed-out answers or rough work if relevant.\n\n"
        "Format your output cleanly grouped by Question Number with full transcribed text under each."
    )

    enhanced_images = [enhance_handwriting_image(img) for img in page_images]

    # 1. Local Offline (Ollama / Local ML)
    if is_local_provider(provider, api_key):
        import urllib.request
        import json
        clean_endpoint = (endpoint or DEFAULT_OLLAMA_ENDPOINT).rstrip("/")
        ollama_model = model_name if model_name and not any(k in model_name for k in ["claude", "gemini"]) else "qwen2.5-vl:7b"
        b64_imgs = [base64.b64encode(img).decode("utf-8") for img in enhanced_images]
        payload = {
            "model": ollama_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": b64_imgs,
                }
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        try:
            req = urllib.request.Request(
                f"{clean_endpoint}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                return res_data.get("message", {}).get("content", "No transcription returned.")
        except Exception as e:
            return f"Local Ollama transcription error: {e}"

    # 2. Anthropic Claude
    elif is_claude_key(api_key, provider):
        import anthropic
        resolved_ws = (workspace_id or "").strip() or os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
        client_kwargs = {"api_key": api_key}
        if resolved_ws:
            client_kwargs["default_headers"] = {"anthropic-workspace-id": resolved_ws}
        client = anthropic.Anthropic(**client_kwargs)
        claude_model = model_name if model_name and "claude" in model_name else "claude-sonnet-5-5"

        content_blocks = []
        for img_bytes in enhanced_images:
            b64_data = base64.b64encode(img_bytes).decode("utf-8")
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": b64_data,
                }
            })
        content_blocks.append({"type": "text", "text": prompt})

        try:
            create_kwargs = {
                "model": claude_model,
                "max_tokens": 16384,
                "messages": [{"role": "user", "content": content_blocks}],
            }
            if any(legacy in claude_model for legacy in ["claude-3-", "claude-2"]):
                create_kwargs["temperature"] = 0.1
            try:
                msg = client.messages.create(**create_kwargs)
            except Exception as call_err:
                if "temperature" in str(call_err).lower() and "deprecated" in str(call_err).lower():
                    create_kwargs.pop("temperature", None)
                    msg = client.messages.create(**create_kwargs)
                else:
                    raise call_err
            return "".join(b.text for b in msg.content if hasattr(b, "text"))
        except Exception as e:
            return f"Claude transcription error: {e}"

    # 3. Google Gemini
    else:
        client = genai.Client(api_key=api_key)
        gemini_model = model_name if model_name and "gemini" in model_name else "gemini-2.5-flash"

        contents = [prompt]
        for img_bytes in enhanced_images:
            contents.append(
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
            )

        try:
            response = client.models.generate_content(
                model=gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(temperature=0.1),
            )
            if response and response.text:
                return response.text
            return "No transcription could be extracted."
        except Exception as e:
            return f"Gemini transcription error: {e}"
