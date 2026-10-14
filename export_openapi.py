"""Writes the OpenAPI 3.0 spec to openapi.json (paste this into Microsoft Foundry's OpenAPI tool)."""
import json
from pathlib import Path

from main import app

out = Path(__file__).parent / "openapi.json"
out.write_text(json.dumps(app.openapi(), indent=2))
print(f"Wrote {out} (servers: {app.servers[0]['url']})")
