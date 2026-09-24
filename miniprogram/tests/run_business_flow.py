"""Exercise native page controllers against an isolated real HTTP API, with test providers."""

import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app import media  # noqa: E402
from backend.app.config import Settings  # noqa: E402
from backend.app.main import create_app  # noqa: E402
from backend.app.schemas import ProviderCandidate, ProviderResult  # noqa: E402


class FixtureProvider:
    name = "native-flow-test-fixture"
    configured = True

    async def recognize(self, image, media_type, characters):
        return ProviderResult(
            model_version="test-only",
            candidates=[ProviderCandidate(character_id="TEST_NATIVE", score=0.75)],
        )


async def unavailable_test_share_code(settings, scene):
    return None


def main():
    media.wechat_share_code = unavailable_test_share_code
    with tempfile.TemporaryDirectory(prefix="dongba-native-flow-") as temporary:
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        settings = Settings(
            _env_file=None,
            environment="test",
            database_url=f"sqlite:///{Path(temporary).as_posix()}/business.sqlite",
            auto_create_schema=True,
            setup_enabled=True,
            public_base_url=origin,
            media_directory=Path(temporary) / "media",
            request_limit_per_minute=10000,
            recognition_limit_per_minute=120,
            quality_checks_enabled=False,
            privacy_policy_published=True,
            privacy_contact="test-only@example.invalid",
            wechat_app_id="test-only-appid",
            wechat_app_secret="test-only-secret",
        )
        app = create_app(settings=settings, provider=FixtureProvider())
        app.state.wechat_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"openid": "test-native-visitor"})
        )
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started:
                if time.monotonic() > deadline:
                    raise RuntimeError("Isolated HTTP test service did not start")
                time.sleep(0.05)
            environment = {**os.environ, "DONGBA_NATIVE_TEST_URL": origin}
            result = subprocess.run(
                ["node", str(Path(__file__).with_name("business-flow.js"))],
                cwd=ROOT,
                env=environment,
                check=False,
                timeout=90,
            )
            return result.returncode
        finally:
            server.should_exit = True
            worker.join(timeout=10)
            listener.close()


if __name__ == "__main__":
    raise SystemExit(main())
