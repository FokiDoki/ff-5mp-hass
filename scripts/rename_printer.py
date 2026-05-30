"""One-shot test of the FlashForge HTTP /control reName_cmd endpoint.

Usage (from repo root, in any venv with aiohttp):
    python scripts/rename_printer.py
"""
import asyncio
import json

import aiohttp

IP = "192.168.1.102"
SERIAL = "SNMOMC9900728"
CHECK_CODE = "e5c2bf77"
NEW_NAME = "Adventurer 5M Pro"
PORT = 8898


async def main() -> None:
    url = f"http://{IP}:{PORT}/control"
    payload = {
        "serialNumber": SERIAL,
        "checkCode": CHECK_CODE,
        "payload": {
            "cmd": "reName_cmd",
            "args": {"name": NEW_NAME},
        },
    }

    print(f"POST {url}")
    print(f"Body: {json.dumps(payload, indent=2)}")

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
        async with s.post(url, json=payload) as resp:
            print(f"\nStatus: {resp.status}")
            print(f"Body:   {await resp.text()}")

    # Verify by reading /detail back
    print("\nVerifying via /detail...")
    detail_url = f"http://{IP}:{PORT}/detail"
    detail_body = {"serialNumber": SERIAL, "checkCode": CHECK_CODE}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
        async with s.post(detail_url, json=detail_body) as resp:
            # Firmware returns mimetype "appliation/json" (typo) — bypass strict check.
            data = await resp.json(content_type=None)
            print(f"name = {data.get('detail', {}).get('name')}")
            print(f"pid  = {data.get('detail', {}).get('pid')}")


if __name__ == "__main__":
    asyncio.run(main())
