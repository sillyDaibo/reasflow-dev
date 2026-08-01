#!/usr/bin/env python3
"""Minimal text-generation client for Codex-configured API providers."""

from __future__ import annotations

import json
import os
import tomllib
import urllib.request
from pathlib import Path


def provider_defaults() -> tuple[str, str, str]:
    fallback = ("https://api.openai.com/v1", "gpt-5.4", "chat_completions")
    config_path = Path.home() / ".codex" / "config.toml"
    try:
        with config_path.open("rb") as handle:
            config = tomllib.load(handle)
        provider_name = str(config.get("model_provider") or "")
        provider = config.get("model_providers", {}).get(provider_name, {})
        return (
            str(provider.get("base_url") or fallback[0]),
            str(config.get("model") or fallback[1]),
            str(provider.get("wire_api") or fallback[2]),
        )
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        return fallback


def configured_defaults() -> tuple[str, str, str, str]:
    base_url, model, wire_api = provider_defaults()
    return (
        os.getenv("OPENAI_BASE_URL", base_url),
        os.getenv("OPENAI_API_KEY", ""),
        os.getenv("OPENAI_MODEL", model),
        os.getenv("OPENAI_WIRE_API", wire_api),
    )


def call_text(
    *,
    system: str,
    user: str,
    base_url: str,
    api_key: str,
    model: str,
    wire_api: str,
    timeout: int,
    temperature: float,
) -> str:
    if wire_api == "responses":
        endpoint = "responses"
        payload = {
            "model": model,
            "instructions": system,
            "input": user,
            "stream": True,
        }
    else:
        endpoint = "chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": True,
            "temperature": temperature,
        }

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "openai-python/1.0",
        },
        method="POST",
    )
    chunks: list[str] = []
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            if wire_api == "responses":
                if event.get("type") == "error":
                    raise RuntimeError(str(event.get("error") or event))
                if event.get("type") == "response.output_text.delta":
                    chunks.append(str(event.get("delta") or ""))
                continue
            try:
                chunks.append(str(event["choices"][0]["delta"].get("content", "")))
            except (KeyError, IndexError):
                continue
    return "".join(chunks)
