"""Opt-in, evaluation-only Qwen thinking profile for Cloudflare Workers AI."""
from contextlib import contextmanager

from triallens import cloudflare


SUPPORTED_MODEL = "@cf/qwen/qwen3.8-27b"


@contextmanager
def disabled_thinking(enabled: bool = False):
    """Temporarily disable Qwen thinking in the exact native chat request.

    The reservation seam runs before HTTP capture, so injecting the option
    there makes the quota reservation account for the same payload sent.
    """
    if not enabled:
        yield
        return
    if cloudflare.MODEL != SUPPORTED_MODEL:
        raise ValueError(f"disabled_thinking requires {SUPPORTED_MODEL}")

    original_reserve = cloudflare._reserve

    def reserve_with_thinking_disabled(payload: dict) -> str:
        if cloudflare.MODEL != SUPPORTED_MODEL:
            raise ValueError(f"disabled_thinking requires {SUPPORTED_MODEL}")
        if not isinstance(payload, dict) or not isinstance(payload.get("messages"), list) or "input" in payload:
            raise ValueError("disabled_thinking requires a native chat messages request")
        kwargs = payload.get("chat_template_kwargs", {})
        if not isinstance(kwargs, dict):
            raise ValueError("chat_template_kwargs must be an object")
        payload["chat_template_kwargs"] = {**kwargs, "enable_thinking": False}
        return original_reserve(payload)

    cloudflare._reserve = reserve_with_thinking_disabled
    try:
        yield
    finally:
        cloudflare._reserve = original_reserve
