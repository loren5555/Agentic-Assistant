"""Authenticated AMiner Open Platform transport shared by research and discovery."""

import httpx


def configured_key(options) -> str:
    """Read the optional platform token from the active local configuration."""
    value = options.get("api_key")
    return value.strip() if isinstance(value, str) else ""


async def post(path: str, payload: dict, *, api_key: str, timeout: float, headers=None):
    if not api_key:
        raise RuntimeError("Configure aminer.api_key in the local configuration")
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            "https://datacenter.aminer.cn/gateway/open_platform/api/" + path,
            headers={"Authorization": api_key, **(headers or {})}, json=payload,
        )
        response.raise_for_status()
        body = response.json()
    if not isinstance(body, dict) or body.get("success") is False or body.get("code") != 200:
        code = body.get("code") if isinstance(body, dict) else None
        raise ValueError(f"AMiner {path} returned an unsuccessful response (code={code})")
    return body["data"]
