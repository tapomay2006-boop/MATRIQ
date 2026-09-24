"""
pipeline-one: CPSE Material Master Attribute Extraction API & Review Studio.
Powered by fine-tuned Qwen2.5-3B LoRA (qwen2.5-3b-cpse-lora-v2).
"""

import sys
import os

# Ensure pipeline-one directory is on sys.path for direct module resolution
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from inference_engine import QwenLoraEngine, resolve_canonical_dict, CANONICAL_FIELDS
from session_store import SessionStore
from forwarder import PipelineForwarder

__all__ = [
    "QwenLoraEngine",
    "resolve_canonical_dict",
    "CANONICAL_FIELDS",
    "SessionStore",
    "PipelineForwarder",
]
