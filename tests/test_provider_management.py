"""Provider configuration lifecycle, safe deletion, and HTTP API tests.

Only synthetic keys in temporary folders are used. Never open real user data.
"""

import asyncio
import json
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import api_routes
import provider_config


class ProviderManagementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.store = provider_config.ProviderStore(
            config_dir=self.root / "AI_Chat", legacy_config_path=None)

    def test_secret_is_private_and_clear_key_is_persistent(self):
        self.store.upsert_profile({
            "name": "OpenRouter", "base_url": "https://example.test/api/v1",
            "api_key": "sk-synthetic-not-a-real-key", "default_model": "example/model",
            "allow_http": False,
        })
        self.assertTrue(self.store.list_profiles()[0]["has_api_key"])
        self.assertNotIn("api_key", self.store.list_profiles()[0])
        self.assertNotIn("sk-synthetic", json.dumps(self.store.list_profiles()))
        self.store.clear_api_key("OpenRouter")
        self.assertFalse(self.store.list_profiles()[0]["has_api_key"])
        self.assertEqual(self.store.get_profile("OpenRouter")["api_key"], "")
        self.assertNotIn("sk-synthetic", self.store.config_path.read_text(encoding="utf-8"))
        self.assertNotIn("sk-synthetic", (self.store.backup_dir / "providers.redacted.json").read_text(encoding="utf-8"))

    def test_last_profile_deletes_and_does_not_reappear(self):
        self.store.upsert_profile({
            "name": "OpenRouter", "base_url": "https://example.test/api/v1",
            "api_key": "sk-synthetic-last-key", "allow_http": False,
        })
        self.store.delete_profile("OpenRouter")
        self.assertEqual(self.store.list_profiles(), [])
        self.assertEqual(json.loads(self.store.config_path.read_text(encoding="utf-8"))["profiles"], [])
        with self.assertRaises(provider_config.ProviderNotFoundError):
            self.store.get_profile("OpenRouter")
        with mock.patch.object(provider_config, "PROVIDER_STORE", self.store):
            self.assertEqual(provider_config.profile_names(), ["请先配置服务商"])
            self.assertEqual(provider_config.model_choices(), ["手动填写"])
        # Empty persisted profiles must stay empty when the process reloads.
        restarted = provider_config.ProviderStore(config_dir=self.store.config_dir, legacy_config_path=None)
        self.assertEqual(restarted.list_profiles(), [])
        restarted.upsert_profile({
            "name": "New Provider", "base_url": "https://example.test/api/v1",
            "api_key": "sk-new-synthetic-key", "allow_http": False,
        })
        self.assertEqual([item["name"] for item in restarted.list_profiles()], ["New Provider"])

    def test_empty_store_does_not_reimport_legacy_keys(self):
        legacy = self.root / "old-config.json"
        legacy.write_text(json.dumps({"api_keys": {
            "https://old.example.test/v1": "sk-old-synthetic-key"}}), encoding="utf-8")
        store = provider_config.ProviderStore(config_dir=self.store.config_dir,
                                              legacy_config_path=legacy)
        initial = store.list_profiles()
        self.assertTrue(any(p["has_api_key"] for p in initial))
        for name in [p["name"] for p in initial]:
            store.delete_profile(name)
        self.assertEqual(store.list_profiles(), [])
        restarted = provider_config.ProviderStore(config_dir=self.store.config_dir,
                                                  legacy_config_path=legacy)
        self.assertEqual(restarted.list_profiles(), [])
        self.assertNotIn("sk-old-synthetic-key", restarted.config_path.read_text(encoding="utf-8"))
        # The historic file is intentionally untouched; revocation remains
        # the user's responsibility, not an implicit destructive migration.
        self.assertTrue(legacy.exists())

    def test_http_list_clear_delete_never_echoes_key(self):
        from aiohttp import web
        from aiohttp.test_utils import TestClient, TestServer

        self.store.upsert_profile({
            "name": "OpenRouter", "base_url": "https://example.test/api/v1",
            "api_key": "sk-http-synthetic-key", "allow_http": False,
        })
        routes = web.RouteTableDef()
        fake_server = SimpleNamespace(PromptServer=SimpleNamespace(
            instance=SimpleNamespace(routes=routes)))
        saved_registered = api_routes._ROUTES_REGISTERED
        api_routes._ROUTES_REGISTERED = False
        self.addCleanup(setattr, api_routes, "_ROUTES_REGISTERED", saved_registered)
        with mock.patch.dict(sys.modules, {"server": fake_server}), mock.patch.object(
            api_routes, "PROVIDER_STORE", self.store
        ):
            self.assertTrue(api_routes.register_routes())

            app = web.Application()
            app.add_routes(routes)

            async def run():
                async with TestClient(TestServer(app)) as client:
                    response = await client.get("/ai_chat/profiles")
                    self.assertEqual(response.status, 200)
                    raw = await response.text()
                    self.assertNotIn("sk-http-synthetic-key", raw)
                    self.assertTrue(json.loads(raw)["profiles"][0]["has_api_key"])
                    response = await client.post("/ai_chat/profiles/clear-key",
                                                 json={"name": "OpenRouter"})
                    self.assertEqual(response.status, 200)
                    self.assertFalse((await response.json())["profile"]["has_api_key"])
                    response = await client.post("/ai_chat/profiles/delete",
                                                 json={"name": "OpenRouter"})
                    self.assertEqual(response.status, 200)
                    response = await client.get("/ai_chat/profiles")
                    self.assertEqual((await response.json())["profiles"], [])
                    response = await client.post("/ai_chat/profiles",
                                                 json={"name": "Wrong", "base_url":
                                                       "https://example.test/v1", "api_key": "test"},
                                                 headers={"Origin": "https://outside.invalid"})
                    self.assertEqual(response.status, 400)

            asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
