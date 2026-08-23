from __future__ import annotations

import json
import logging
from typing import Optional

import litellm
from pydantic import ValidationError

from .models import ClassificationResult

logger = logging.getLogger(__name__)

litellm.suppress_debug_info = True
for _litellm_logger in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    logging.getLogger(_litellm_logger).setLevel(logging.WARNING)

SYSTEM_PROMPT = (
    "You are a professional document classifier. Analyze the provided text and "
    "return a JSON object with these exact keys:\n\n"
    "{\n"
    '  "title": "Main topic or title of the document",\n'
    '  "document_type": "One of: report, article, letter, contract, invoice, '
    'resume, research, manual, other",\n'
    '  "main_category": "One of: Keuangan, Surat_Menyurat, Laporan, Kontrak, SDM, '
    'Penelitian, Teknis, Legal, Lainnya",\n'
    '  "document_date": "Extracted date in YYYY-MM-DD format if found, otherwise null",\n'
    '  "suggested_filename": "A clean descriptive filename without extension, use '
    'underscores for spaces",\n'
    '  "confidence": 0.85,\n'
    '  "summary": "One sentence summary of the document content"\n'
    "}\n\n"
    "Rules:\n"
    "- Return ONLY valid JSON, no markdown fences, no extra text.\n"
    "- suggested_filename must be safe for all OS (no special chars except "
    "underscore/hyphen).\n"
    "- confidence is a float between 0.0 and 1.0.\n"
    "- If the text is in Indonesian, keep category names as listed above.\n"
)


def classify_text(
    text: str,
    model: str = "ollama/llama3:8b",
    temperature: float = 0.1,
    local_only: bool = True,
) -> Optional[ClassificationResult]:
    if not text or not text.strip():
        logger.warning("Empty text provided for classification")
        return None

    if local_only and not model.startswith("ollama/"):
        logger.error("local_only=True but model '%s' is not an Ollama model", model)
        return None

    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Classify this document:\n\n{text}"},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content
        if not raw_content:
            logger.error("Empty response from LLM")
            return None

        raw_content = raw_content.strip()
        if raw_content.startswith("```"):
            lines = raw_content.split("\n")
            raw_content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        data = json.loads(raw_content)
        result = ClassificationResult(**data)
        return result

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM JSON response: %s", exc)
        return None
    except ValidationError as exc:
        logger.error("LLM response validation failed: %s", exc)
        return None
    except Exception as exc:
        logger.error("Classification error: %s", exc)
        return None


def check_ollama_connection(model: str = "ollama/llama3:8b") -> bool:
    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        return bool(response.choices)
    except Exception:
        return False
