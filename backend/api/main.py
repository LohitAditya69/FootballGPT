from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn

from backend.api.app import create_app
from backend.api.config import settings

app = create_app(settings)


def main() -> int:
    parser = argparse.ArgumentParser(description="FootballGPT Backend HTTP Service")
    parser.add_argument("--host", type=str, default=settings.host, help="Bind host")
    parser.add_argument("--port", type=int, default=settings.port, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    print(f"Starting FootballGPT API server on http://{args.host}:{args.port}")
    print("API Contract: product_api_contract_v1.md")
    print("Health endpoint: http://{args.host}:{args.port}/health")
    print(f"Ask endpoint: http://{args.host}:{args.port}/api/v1/ask")

    uvicorn.run("backend.api.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
