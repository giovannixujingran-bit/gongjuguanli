from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_PLATFORM_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INTEGRATIONS_DIR = _PLATFORM_ROOT / "integrations"
sys.path.insert(0, str(_PLATFORM_ROOT))


def main() -> None:
    from backend.storage.registry import apply_configs, load_tool_configs

    parser = argparse.ArgumentParser(
        description="Sync integrations/<tool_id>/tool.toml declarations into tool_registry."
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL URL. Defaults to DATABASE_URL.",
    )
    parser.add_argument(
        "--integrations-dir",
        type=Path,
        default=DEFAULT_INTEGRATIONS_DIR,
        help="Integrations directory. Defaults to platform/integrations.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only validate tool.toml files; do not connect to the database.",
    )
    args = parser.parse_args()

    configs = load_tool_configs(args.integrations_dir)
    if not configs:
        print(f"No tool.toml files found under {args.integrations_dir}/*/tool.toml")
        return

    if args.check:
        print(f"Validated {len(configs)} tool.toml file(s).")
        for config in configs:
            print(f"  - {config.tool_id} ({config.name})")
        return

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required. Set it or pass --database-url.")

    applied = apply_configs(args.database_url, configs)
    print(f"Synced {len(applied)} tool(s) into tool_registry.")
    for tool_id in applied:
        print(f"  - {tool_id}")


if __name__ == "__main__":
    main()
