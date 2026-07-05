"""Two-tier configuration: ``[providers.*]`` + ``[agents.*]`` (§10, §10A).

Resolution for a role's effective (provider, model, key):
``[agents.<role>]`` → ``[agents.default]`` → error. Sub-roles such as
``subagent.verification`` inherit from their parent role when unset. Env-var
interpolation expands ``${VAR}`` in any string value.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib

BANNED_DEPS = (
    "crewai",
    "langgraph",
    "langchain-agents",
    "langchain_agents",
    "autogen",
    "llama-index",
    "llama_index",
)

# Developer-convenience provider presets (§10.4).
PRESETS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "auth_env": "DEEPSEEK_API_KEY",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "auth_env": "QWEN_API_KEY",
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "auth_env": "MOONSHOT_API_KEY",
    },
}

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(Exception):
    """Configuration error → exit code 2 (or 3 for auth/env resolution)."""

    def __init__(self, message: str, *, exit_code: int = 2):
        super().__init__(message)
        self.exit_code = exit_code


@dataclass
class EffectiveAgent:
    """Fully-resolved routing for one agent role."""

    role: str
    provider: str
    model: str
    base_url: str
    api_key: str
    key_source: str
    models: list[str] = field(default_factory=list)

    def masked(self) -> dict:
        key = self.api_key or ""
        if len(key) <= 4:
            shown = "****"
        else:
            shown = key[:2] + "*" * (len(key) - 4) + key[-2:]
        return {
            "role": self.role,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "key_source": self.key_source,
            "api_key": shown,
            "models": list(self.models),
        }


def _resolve_env(value):
    """Recursively expand ``${VAR}`` — raises ConfigError on missing vars."""
    if isinstance(value, str):
        def repl(match: re.Match) -> str:
            name = match.group(1)
            if name not in os.environ:
                raise ConfigError(
                    f"environment variable {name} is not set", exit_code=3
                )
            return os.environ[name]

        return _ENV_RE.sub(repl, value)
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(v) for v in value]
    return value


def _interpolate_lenient(value):
    """Recursively expand ``${VAR}`` — missing vars silently become ``""``."""
    if isinstance(value, str):
        def repl(match: re.Match) -> str:
            name = match.group(1)
            return os.environ.get(name, "")
        return _ENV_RE.sub(repl, value)
    if isinstance(value, dict):
        return {k: _interpolate_lenient(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_lenient(v) for v in value]
    return value


class Config:
    """Parsed, interpolation-aware configuration object."""

    def __init__(self, data: dict, *, source: str = "<memory>"):
        self.source = source
        self.providers: dict = data.get("providers", {}) or {}
        self.agents: dict = data.get("agents", {}) or {}
        self.settings: dict = data.get("settings", {}) or {}

    # -- provider helpers ----------------------------------------------------
    def provider_base_url(self, name: str) -> str:
        prov = self.providers.get(name, {})
        if prov.get("base_url"):
            return _interpolate_lenient(prov["base_url"])
        if name in PRESETS:
            return PRESETS[name]["base_url"]
        return ""

    def provider_models(self, name: str) -> list[str]:
        return list(self.providers.get(name, {}).get("models", []))

    def _provider_key(self, name: str) -> tuple[str, str]:
        prov = self.providers.get(name, {})
        raw = prov.get("api_key")
        if raw is not None:
            m = _ENV_RE.fullmatch(raw.strip()) if isinstance(raw, str) else None
            source = f"${{{m.group(1)}}}" if m else "inline"
            return _resolve_env(raw), source
        if name in PRESETS:
            env = PRESETS[name]["auth_env"]
            if env in os.environ:
                return os.environ[env], f"env:{env}"
            raise ConfigError(f"environment variable {env} is not set", exit_code=3)
        raise ConfigError(f"provider {name!r} has no api_key", exit_code=3)

    # -- role resolution -----------------------------------------------------
    def _role_table(self, role: str) -> dict | None:
        if role in self.agents:
            return self.agents[role]
        # Dotted sub-role e.g. "subagent.verification".
        if "." in role:
            parent, _, child = role.partition(".")
            section = self.agents.get(parent, {})
            if isinstance(section, dict) and child in section:
                return section[child]
        return None

    def _parent_role(self, role: str) -> str | None:
        if role.startswith("subagent.") or role.startswith("subagent"):
            return "work"
        return "default"

    def has_explicit_role(self, role: str) -> bool:
        """True if ``role`` is configured directly (not just via fallback)."""
        return self._role_table(role) is not None

    def resolve_role(self, role: str, *, _seen: set | None = None) -> EffectiveAgent:
        """Resolve a role to an :class:`EffectiveAgent`, applying inheritance."""
        _seen = _seen or set()
        if role in _seen:
            raise ConfigError(f"cyclic agent inheritance at {role!r}")
        _seen.add(role)

        table = self._role_table(role)
        if table is None:
            if role == "default":
                raise ConfigError("no [agents.default] configured")
            parent = self._parent_role(role)
            if parent is None:
                raise ConfigError(f"cannot resolve agent role {role!r}")
            return self.resolve_role(parent, _seen=_seen)

        if "model" in table and "models" in table:
            raise ConfigError(
                f"agent role {role!r} sets both 'model' and 'models'"
            )

        provider = table.get("provider")
        if not provider:
            parent = self._parent_role(role)
            base = self.resolve_role(parent, _seen=_seen) if parent else None
            provider = base.provider if base else None
        if not provider:
            raise ConfigError(f"agent role {role!r} has no provider")

        models = list(table.get("models", []))
        model = table.get("model") or (models[0] if models else None)
        if model is None:
            # Inherit model from provider default list.
            prov_models = self.provider_models(provider)
            model = prov_models[0] if prov_models else None
        if model is None:
            raise ConfigError(f"agent role {role!r} has no model")

        base_url = self.provider_base_url(provider)
        api_key, key_source = self._provider_key(provider)
        return EffectiveAgent(
            role=role,
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
            key_source=key_source,
            models=models or [model],
        )

    # -- validation (§10A.4) -------------------------------------------------
    def check(self) -> list[str]:
        """Return a list of human-readable problems; empty means valid."""
        errors: list[str] = []
        for role, table in _iter_agent_roles(self.agents):
            if not isinstance(table, dict):
                continue
            if "model" in table and "models" in table:
                errors.append(f"agents.{role}: sets both 'model' and 'models'")
            provider = table.get("provider")
            if provider and provider not in self.providers and provider not in PRESETS:
                errors.append(f"agents.{role}: unknown provider {provider!r}")
                continue
            if provider:
                listed = set(self.provider_models(provider))
                wanted = [table.get("model")] if table.get("model") else table.get("models", [])
                for m in wanted:
                    if listed and m not in listed:
                        errors.append(
                            f"agents.{role}: model {m!r} not listed under provider {provider!r}"
                        )
        for name in self.providers:
            try:
                self._provider_key(name)
            except ConfigError as exc:
                errors.append(f"providers.{name}: {exc}")
        return errors


def _iter_agent_roles(agents: dict, prefix: str = ""):
    """Yield (dotted_role, table) for every agent role, recursing one level."""
    for key, value in agents.items():
        role = f"{prefix}{key}"
        if isinstance(value, dict) and any(
            isinstance(v, dict) for v in value.values()
        ):
            yield from _iter_agent_roles(value, prefix=f"{role}.")
        else:
            yield role, value


def config_path(explicit: str | None = None) -> Path:
    """Resolve the active config path (§10A.1 precedence)."""
    if explicit:
        return Path(explicit)
    if os.environ.get("ZHURI_CONFIG"):
        return Path(os.environ["ZHURI_CONFIG"])
    project = Path.cwd() / ".zhuri" / "config.toml"
    if project.exists():
        return project
    home = Path(os.path.expanduser("~")) / ".config" / "zhuri" / "config.toml"
    return home


def load_config(explicit: str | None = None) -> Config:
    """Load configuration from disk following §10A.1 precedence."""
    path = config_path(explicit)
    if not path.exists():
        raise ConfigError(f"config file not found: {path}", exit_code=2)
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    return Config(data, source=str(path))


def load_config_str(text: str, *, source: str = "<string>") -> Config:
    """Load configuration from a TOML string (tests / project overrides)."""
    return Config(tomllib.loads(text), source=source)
