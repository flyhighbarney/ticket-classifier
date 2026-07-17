"""
Model loading — zero-shot classifier (BART) and text generator (flan-t5).
Auto-detects GPU/CPU. Lazy-loads on first call.
"""

import torch
from transformers import pipeline

_classifier = None
_generator = None


def _device():
    if torch.cuda.is_available():
        return 0
    return -1


def get_classifier():
    global _classifier
    if _classifier is None:
        print("[models] Loading facebook/bart-large-mnli ...")
        _classifier = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=_device(),
        )
        print("[models] Classifier ready.")
    return _classifier


def get_generator():
    global _generator
    if _generator is None:
        model_name = "google/flan-t5-base"
        print("[models] Loading {} ...".format(model_name))
        _generator = pipeline(
            "text-generation",
            model=model_name,
            device=_device(),
            max_new_tokens=200,
        )
        print("[models] Generator ready.")
    return _generator
