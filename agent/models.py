"""
Model loading — zero-shot classifier (BART) and text generator (flan-t5).
Auto-detects GPU/CPU. Lazy-loads on first call.
"""

import torch
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM

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
        dev = _device()
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        if dev >= 0:
            model = model.to("cuda")
        _generator = (model, tokenizer, dev)
        print("[models] Generator ready.")
    return _generator


def generate_text(prompt: str, max_new_tokens: int = 200) -> str:
    model, tokenizer, dev = get_generator()
    device = "cuda" if dev >= 0 else "cpu"
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    outputs = model.generate(**inputs, max_new_tokens=max_new_tokens)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)
