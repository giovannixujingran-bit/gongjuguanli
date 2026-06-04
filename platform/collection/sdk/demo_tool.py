from __future__ import annotations

import argparse
from pathlib import Path

from collection.sdk import PlatformTracker, normalize_token_usage


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo tool for Phase 2A SDK validation.")
    parser.add_argument("--endpoint-url", default="http://127.0.0.1:8000/events")
    parser.add_argument(
        "--entry-source",
        choices=["portal", "direct", "unknown"],
        default="unknown",
    )
    parser.add_argument("--auth-token")
    args = parser.parse_args()

    tracker = PlatformTracker(
        tool_id="demo-tool",
        endpoint_url=args.endpoint_url,
        auth_token=args.auth_token,
        entry_source=args.entry_source,
        auth_method="session_token" if args.auth_token else "none",
        buffer_path=Path(".platform-buffer/demo-tool.jsonl"),
    )
    tracker.record_usage(
        model="demo-model",
        token_usage=normalize_token_usage(
            "openai",
            {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        ),
        metadata={"demo": True},
    )
    flushed = tracker.flush()
    print(f"demo event reported; flushed={flushed}")


if __name__ == "__main__":
    main()
