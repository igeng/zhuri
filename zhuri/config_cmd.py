"""``zhuri config`` and ``zhuri doctor`` command handlers (§10A, §4.5)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from .config import BANNED_DEPS, Config, ConfigError, config_path, load_config


def _print(obj, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        print(obj)


def config_command(args, *, make_config) -> int:
    action = getattr(args, "action", "path") or "path"
    if action == "path":
        print(config_path(args.config))
        return 0

    if action == "check":
        try:
            cfg = make_config()
        except ConfigError as exc:
            print(f"config error: {exc}", file=sys.stderr)
            return exc.exit_code
        errors = cfg.check()
        banned = _banned_present()
        errors += banned
        if errors:
            for e in errors:
                print(f"FAIL: {e}", file=sys.stderr)
            return 2
        print("config OK")
        return 0

    if action == "get":
        cfg = make_config()
        if getattr(args, "effective", False):
            roles = [args.role] if getattr(args, "role", None) else _all_roles(cfg)
            out = {}
            for role in roles:
                try:
                    out[role] = cfg.resolve_role(role).masked()
                except ConfigError as exc:
                    out[role] = {"error": str(exc)}
            _print(out, args.json)
            return 0
        _print({"providers": list(cfg.providers), "agents": list(cfg.agents)}, args.json)
        return 0

    if action == "set":
        print("config set: edit the TOML file directly at " + str(config_path(args.config)))
        return 0

    print(f"unknown config action: {action}", file=sys.stderr)
    return 2


def _all_roles(cfg: Config) -> list[str]:
    roles = []
    for key, value in cfg.agents.items():
        if isinstance(value, dict) and any(isinstance(v, dict) for v in value.values()):
            for sub in value:
                roles.append(f"{key}.{sub}")
        else:
            roles.append(key)
    return roles


def _banned_present() -> list[str]:
    """A9: ensure no banned agent-framework dependency is declared in pyproject.toml.

    Checks the *declared* dependencies, not the installed environment — a developer
    may have crewai/langgraph/etc. installed for unrelated projects.
    """
    import tomllib as _tomllib

    found: list[str] = []
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if not pyproject.exists():
        return found
    try:
        data = _tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return found
    deps: list[str] = data.get("project", {}).get("dependencies", [])
    dev_deps: list[str] = (
        data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    )
    joined = (" ".join(deps) + " " + " ".join(dev_deps)).lower()
    for banned in BANNED_DEPS:
        if banned.lower() in joined:
            found.append(f"banned dependency declared: {banned}")
    return found


def doctor_command(args, *, make_config, registry_factory=None) -> int:
    """Validate env, provider auth, banned-deps, and config (§4.5)."""
    print("zhuri doctor")
    try:
        cfg = make_config()
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return exc.exit_code

    problems = cfg.check() + _banned_present()
    for p in problems:
        print(f"FAIL: {p}", file=sys.stderr)
    if problems:
        return 2

    if getattr(args, "offline", False):
        print("OK (offline: skipped live auth probe)")
        return 0

    # Live 1-token auth probe per distinct key (skippable with --offline).
    if registry_factory is None:
        print("OK (no provider factory; skipped live probe)")
        return 0
    registry = registry_factory(cfg)
    probed: set[str] = set()
    for role in _all_roles(cfg):
        try:
            provider, eff = registry.provider_for(role)
        except ConfigError as exc:
            print(f"FAIL: {role}: {exc}", file=sys.stderr)
            return exc.exit_code
        if eff.key_source in probed:
            continue
        probed.add(eff.key_source)
        try:
            asyncio.run(provider.complete(
                system="ping", messages=[{"role": "user", "content": "ping"}],
                model=eff.model, max_tokens=1,
            ))
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "exit_code", 3)
            print(f"FAIL: auth probe for {role}: {exc}", file=sys.stderr)
            return code
    print("OK (auth probes passed)")
    return 0
