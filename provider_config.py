"""Persistent provider profiles for OpenAI-compatible relay services.

Secrets are stored server-side and are never returned by the public/sanitized
methods.  Workflows only retain a profile name, not the API key itself.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit


CONFIG_VERSION = 1
MANUAL_MODEL_OPTION = "手动填写"
DEFAULT_PROFILE = {
    "name": "OpenRouter",
    "base_url": "https://openrouter.ai/api/v1",
    "api_key": "",
    "default_model": "google/gemini-2.5-flash-image",
    "allow_http": False,
    "models": ["google/gemini-2.5-flash-image"],
    "models_updated_at": "",
}

_PLACEHOLDER_SECRETS = {
    "your_key_here",
    "your_api_key_here",
    "your_session_id_here",
    "8888888888",
}


class ProviderConfigError(RuntimeError):
    """Base error for provider configuration operations."""


class ProviderValidationError(ProviderConfigError, ValueError):
    """Raised when a provider profile contains invalid data."""


class ProviderNotFoundError(ProviderConfigError, KeyError):
    """Raised when a requested provider profile does not exist."""


class ModelDiscoveryError(ProviderConfigError):
    """Raised when a provider does not return a usable model list."""


def is_placeholder_secret(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    return normalized in _PLACEHOLDER_SECRETS or normalized.startswith("your_")


def redact_secret(message: str, secret: str | None) -> str:
    text = str(message)
    value = (secret or "").strip()
    return text.replace(value, "********") if value else text


def _default_config_dir() -> Path:
    override = os.environ.get("AI_CHAT_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    try:
        import folder_paths  # type: ignore

        user_dir = Path(folder_paths.get_user_directory())
    except Exception:
        user_dir = Path.home() / ".comfyui"
    return user_dir / "AI_Chat"


def normalize_base_url(value: str, allow_http: bool) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ProviderValidationError("Base URL 不能为空。")
    if len(raw) > 2048:
        raise ProviderValidationError("Base URL 不能超过 2048 个字符。")

    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ProviderValidationError("Base URL 只允许 HTTP 或 HTTPS。")
    if not parsed.hostname:
        raise ProviderValidationError("Base URL 缺少有效主机名。")
    if parsed.username or parsed.password:
        raise ProviderValidationError("Base URL 不允许嵌入用户名或密码。")
    if parsed.query or parsed.fragment:
        raise ProviderValidationError("Base URL 不允许包含查询参数或锚点。")
    if parsed.scheme == "http" and not allow_http:
        raise ProviderValidationError("HTTP 会明文传输 API Key；请显式启用“允许 HTTP”。")

    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _validate_name(value: str) -> str:
    name = (value or "").strip()
    if not name:
        raise ProviderValidationError("配置名称不能为空。")
    if len(name) > 80:
        raise ProviderValidationError("配置名称不能超过 80 个字符。")
    if any(char in name for char in ("/", "\\", "\0", "\r", "\n")):
        raise ProviderValidationError("配置名称包含不允许的字符。")
    return name


def _normalize_models(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized = {
        str(value).strip()
        for value in values
        if isinstance(value, (str, int, float)) and str(value).strip()
    }
    return sorted(normalized, key=str.casefold)[:2000]


class ProviderStore:
    def __init__(
        self,
        config_dir: Path | str | None = None,
        legacy_config_path: Path | str | None = Path(__file__).with_name("config.json"),
    ) -> None:
        self.config_dir = Path(config_dir) if config_dir is not None else _default_config_dir()
        self.config_path = self.config_dir / "providers.json"
        self.backup_dir = self.config_dir / "backups"
        self.legacy_config_path = Path(legacy_config_path) if legacy_config_path else None
        self._lock = threading.RLock()

    @staticmethod
    def _default_data() -> dict[str, Any]:
        return {"version": CONFIG_VERSION, "profiles": [deepcopy(DEFAULT_PROFILE)]}

    def _legacy_profiles(self) -> list[dict[str, Any]]:
        path = self.legacy_config_path
        if path is None or not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        api_keys = data.get("api_keys", {})
        if not isinstance(api_keys, dict):
            return []

        profiles = []
        for base_url, api_key in api_keys.items():
            if not isinstance(base_url, str) or not isinstance(api_key, str):
                continue
            if not api_key.strip() or is_placeholder_secret(api_key):
                continue
            try:
                normalized_url = normalize_base_url(base_url, allow_http=True)
            except ProviderValidationError:
                continue
            hostname = urlsplit(normalized_url).hostname or "Legacy"
            name = "OpenRouter" if "openrouter.ai" in hostname else hostname[:60]
            profiles.append(
                {
                    "name": name,
                    "base_url": normalized_url,
                    "api_key": api_key.strip(),
                    "default_model": (
                        "google/gemini-2.5-flash-image" if name == "OpenRouter" else ""
                    ),
                    "allow_http": normalized_url.startswith("http://"),
                    "models": [],
                    "models_updated_at": "",
                }
            )
        return profiles

    def _read_data(self) -> dict[str, Any]:
        has_persisted_config = self.config_path.is_file()
        if has_persisted_config:
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ProviderConfigError(f"服务商配置文件 JSON 格式错误：{exc}") from exc
            except OSError as exc:
                raise ProviderConfigError(f"无法读取服务商配置文件：{exc}") from exc
            if not isinstance(data, dict) or not isinstance(data.get("profiles"), list):
                raise ProviderConfigError("服务商配置文件结构无效。")
        else:
            data = self._default_data()

        profiles = data.get("profiles", [])
        legacy_profiles = [] if has_persisted_config else self._legacy_profiles()
        for legacy in legacy_profiles:
            existing = next(
                (
                    profile
                    for profile in profiles
                    if isinstance(profile, dict)
                    and str(profile.get("base_url", "")).rstrip("/") == legacy["base_url"]
                ),
                None,
            )
            if existing is None:
                used_names = {
                    str(profile.get("name", ""))
                    for profile in profiles
                    if isinstance(profile, dict)
                }
                base_name = legacy["name"]
                suffix = 2
                while legacy["name"] in used_names:
                    legacy["name"] = f"{base_name} (Legacy {suffix})"
                    suffix += 1
                profiles.append(legacy)
            else:
                if not str(existing.get("api_key", "")).strip():
                    existing["api_key"] = legacy["api_key"]
                if not str(existing.get("default_model", "")).strip():
                    existing["default_model"] = legacy["default_model"]

        normalized_profiles = []
        for raw_profile in profiles:
            if not isinstance(raw_profile, dict):
                continue
            profile = deepcopy(raw_profile)
            profile.setdefault("api_key", "")
            profile.setdefault("default_model", "")
            profile.setdefault("allow_http", str(profile.get("base_url", "")).startswith("http://"))
            profile["models"] = _normalize_models(profile.get("models", []))
            profile.setdefault("models_updated_at", "")
            normalized_profiles.append(profile)
        if not normalized_profiles:
            normalized_profiles.append(deepcopy(DEFAULT_PROFILE))
        return {"version": CONFIG_VERSION, "profiles": normalized_profiles}

    def _write_data(self, data: dict[str, Any]) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if self.config_path.exists():
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            previous = json.loads(self.config_path.read_text(encoding="utf-8"))
            fields = ("name", "base_url", "default_model", "allow_http", "models", "models_updated_at")
            backup = {
                "version": CONFIG_VERSION,
                "profiles": [
                    {key: profile[key] for key in fields if key in profile}
                    for profile in previous.get("profiles", []) if isinstance(profile, dict)
                ],
            }
            backup_path = self.backup_dir / "providers.redacted.json"
            backup_path.write_text(json.dumps(backup, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            try:
                os.chmod(backup_path, 0o600)
            except OSError:
                pass

        temp_path = self.config_dir / f".providers.{os.getpid()}.{threading.get_ident()}.tmp"
        try:
            temp_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            try:
                os.chmod(temp_path, 0o600)
            except OSError:
                pass
            os.replace(temp_path, self.config_path)
        finally:
            if temp_path.exists():
                try:
                    self.backup_dir.mkdir(parents=True, exist_ok=True)
                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    shutil.move(temp_path, self.backup_dir / f"failed_write_{stamp}.tmp")
                except OSError:
                    # Preserve the failed temporary file for recovery and keep the original error.
                    pass

    def list_profiles(self) -> list[dict[str, Any]]:
        with self._lock:
            profiles = self._read_data()["profiles"]
            return [self._sanitize(profile) for profile in profiles]

    @staticmethod
    def _sanitize(profile: dict[str, Any]) -> dict[str, Any]:
        public = {key: deepcopy(value) for key, value in profile.items() if key != "api_key"}
        secret = str(profile.get("api_key", "")).strip()
        public["has_api_key"] = bool(secret and not is_placeholder_secret(secret))
        return public

    def get_profile(self, name: str) -> dict[str, Any]:
        normalized_name = _validate_name(name)
        with self._lock:
            for profile in self._read_data()["profiles"]:
                if profile.get("name") == normalized_name:
                    validated = deepcopy(profile)
                    validated["name"] = _validate_name(str(validated.get("name", "")))
                    if not isinstance(validated.get("allow_http", False), bool):
                        raise ProviderConfigError(
                            f"服务商“{normalized_name}”的 allow_http 必须是布尔值。"
                        )
                    validated["allow_http"] = validated.get("allow_http", False)
                    validated["base_url"] = normalize_base_url(
                        str(validated.get("base_url", "")),
                        validated["allow_http"],
                    )
                    validated["api_key"] = str(validated.get("api_key", "")).strip()
                    validated["default_model"] = str(validated.get("default_model", "")).strip()
                    validated["models"] = _normalize_models(validated.get("models", []))
                    return validated
        raise ProviderNotFoundError(f"未找到服务商配置：{normalized_name}")

    def upsert_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ProviderValidationError("服务商配置必须是 JSON 对象。")

        name = _validate_name(str(payload.get("name", "")))
        raw_allow_http = payload.get("allow_http", False)
        if not isinstance(raw_allow_http, bool):
            raise ProviderValidationError("allow_http 必须是布尔值。")
        allow_http = raw_allow_http
        base_url = normalize_base_url(str(payload.get("base_url", "")), allow_http)
        api_key = str(payload.get("api_key", "")).strip()
        if api_key and is_placeholder_secret(api_key):
            raise ProviderValidationError("API Key 仍是示例占位符，请填写真实密钥或留空。")
        default_model = str(payload.get("default_model", "")).strip()
        if len(default_model) > 300:
            raise ProviderValidationError("默认模型名称过长。")

        with self._lock:
            data = self._read_data()
            existing = next(
                (profile for profile in data["profiles"] if profile.get("name") == name),
                None,
            )
            if existing is not None and not api_key:
                if (str(existing.get("api_key", "")).strip()
                        and str(existing.get("base_url", "")).rstrip("/") != base_url):
                    raise ProviderValidationError("修改 Base URL 后请重新输入 API Key，避免将已保存的密钥发送到新地址。")
                api_key = str(existing.get("api_key", "")).strip()

            profile = {
                "name": name,
                "base_url": base_url,
                "api_key": api_key,
                "default_model": default_model,
                "allow_http": allow_http,
                "models": _normalize_models(
                    payload.get("models", existing.get("models", []) if existing else [])
                ),
                "models_updated_at": str(
                    payload.get(
                        "models_updated_at",
                        existing.get("models_updated_at", "") if existing else "",
                    )
                ),
            }
            if existing is None:
                data["profiles"].append(profile)
            else:
                existing.clear()
                existing.update(profile)
            self._write_data(data)
            return self._sanitize(profile)

    def delete_profile(self, name: str) -> None:
        normalized_name = _validate_name(name)
        with self._lock:
            data = self._read_data()
            retained = [
                profile for profile in data["profiles"] if profile.get("name") != normalized_name
            ]
            if len(retained) == len(data["profiles"]):
                raise ProviderNotFoundError(f"未找到服务商配置：{normalized_name}")
            if not retained:
                raise ProviderValidationError("至少需要保留一个服务商配置。")
            data["profiles"] = retained
            self._write_data(data)

    def clear_api_key(self, name: str) -> dict[str, Any]:
        normalized_name = _validate_name(name)
        with self._lock:
            data = self._read_data()
            for profile in data["profiles"]:
                if profile.get("name") == normalized_name:
                    profile["api_key"] = ""
                    self._write_data(data)
                    return self._sanitize(profile)
            raise ProviderNotFoundError(f"未找到服务商配置：{normalized_name}")

    def refresh_models(
        self,
        name: str,
        client_factory: Callable[..., Any] | None = None,
    ) -> list[str]:
        name = _validate_name(name)
        profile = self.get_profile(name)
        api_key = str(profile.get("api_key", "")).strip()
        if not api_key or is_placeholder_secret(api_key):
            raise ProviderValidationError("请先为该服务商保存有效的 API Key。")

        if client_factory is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ModelDiscoveryError("未安装 openai 依赖，无法检测模型。") from exc
            client_factory = OpenAI

        try:
            client = client_factory(
                api_key=api_key,
                base_url=profile["base_url"],
                timeout=30.0,
                max_retries=1,
            )
            try:
                response = client.models.list(extra_query={"output_modalities": "all"})
            except Exception as filtered_exc:
                # Many relays expose /models but reject unknown query parameters.
                try:
                    response = client.models.list()
                except Exception as plain_exc:
                    raise plain_exc from filtered_exc
        except Exception as exc:
            safe_message = redact_secret(str(exc), api_key)
            raise ModelDiscoveryError(f"模型检测失败：{safe_message}") from None
        finally:
            if "client" in locals():
                close = getattr(client, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass

        raw_models = getattr(response, "data", None)
        if raw_models is None and isinstance(response, dict):
            raw_models = response.get("data")
        if not isinstance(raw_models, (list, tuple)):
            raise ModelDiscoveryError("服务商的 /models 响应缺少 data 列表。")

        model_ids = []
        for item in raw_models:
            model_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
            if isinstance(model_id, str) and model_id.strip():
                model_ids.append(model_id.strip())
        models = sorted(set(model_ids), key=str.casefold)[:2000]
        if not models:
            raise ModelDiscoveryError("服务商没有返回可用模型。")

        with self._lock:
            data = self._read_data()
            for stored in data["profiles"]:
                if stored.get("name") == name:
                    stored["models"] = models
                    stored["models_updated_at"] = datetime.now(timezone.utc).isoformat()
                    break
            else:
                raise ProviderNotFoundError(f"未找到服务商配置：{name}")
            self._write_data(data)
        return models



PROVIDER_STORE = ProviderStore()

def profile_names() -> list[str]:
    try:
        names = [profile["name"] for profile in PROVIDER_STORE.list_profiles()]
    except ProviderConfigError as exc:
        print(f"[AI Chat] 读取服务商配置失败：{exc}")
        names = []
    return names or [DEFAULT_PROFILE["name"]]


def model_choices(profile_name: str | None = None) -> list[str]:
    models: list[str] = []
    try:
        profiles = PROVIDER_STORE.list_profiles()
        selected = next(
            (profile for profile in profiles if profile["name"] == profile_name),
            profiles[0] if profiles else None,
        )
        if selected:
            models.extend(selected.get("models", []))
            default_model = selected.get("default_model", "")
            if default_model:
                models.append(default_model)
    except ProviderConfigError as exc:
        print(f"[AI Chat] 读取模型缓存失败：{exc}")
    choices = sorted(set(models), key=str.casefold)
    return choices + [MANUAL_MODEL_OPTION]


def resolve_provider_and_model(
    profile_name: str,
    selected_model: str,
    manual_model: str,
) -> tuple[dict[str, Any], str]:
    profile = PROVIDER_STORE.get_profile(profile_name)
    api_key = str(profile.get("api_key", "")).strip()
    if not api_key or is_placeholder_secret(api_key):
        raise ProviderValidationError(f"服务商“{profile_name}”尚未保存有效 API Key。")

    model = (
        (manual_model or "").strip()
        if selected_model == MANUAL_MODEL_OPTION
        else (selected_model or "").strip()
    )
    if not model:
        model = str(profile.get("default_model", "")).strip()
    if not model:
        raise ProviderValidationError("请选择模型或填写手动模型名称。")
    if len(model) > 300:
        raise ProviderValidationError("模型名称不能超过 300 个字符。")
    return profile, model
