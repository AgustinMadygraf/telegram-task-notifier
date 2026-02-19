from types import SimpleNamespace

import src.infrastructure.pyngrok.ngrok_service as ngrok_module
from src.infrastructure.pyngrok.ngrok_service import NgrokService


class DummyConf:
    def __init__(self) -> None:
        self.default = SimpleNamespace(auth_token=None)

    def get_default(self) -> SimpleNamespace:
        return self.default


class DummyNgrok:
    def __init__(self) -> None:
        self.connect_calls: list[dict[str, object]] = []
        self.disconnect_calls: list[str] = []
        self.kill_calls = 0

    def connect(self, **kwargs: object) -> SimpleNamespace:
        self.connect_calls.append(kwargs)
        return SimpleNamespace(public_url="https://unit-test.ngrok.io/")

    def disconnect(self, url: str) -> None:
        self.disconnect_calls.append(url)

    def kill(self) -> None:
        self.kill_calls += 1


def test_ngrok_service_starts_tunnel_with_domain_and_auth_token(monkeypatch) -> None:
    dummy_conf = DummyConf()
    dummy_ngrok = DummyNgrok()
    monkeypatch.setattr(ngrok_module, "conf", dummy_conf)
    monkeypatch.setattr(ngrok_module, "ngrok", dummy_ngrok)

    service = NgrokService(auth_token="my-token")
    public_url = service.start_http_tunnel(port=8000, domain="api.example.com")

    assert public_url == "https://unit-test.ngrok.io"
    assert dummy_conf.default.auth_token == "my-token"
    assert dummy_ngrok.connect_calls == [
        {
            "addr": "8000",
            "proto": "http",
            "bind_tls": True,
            "domain": "api.example.com",
        }
    ]


def test_ngrok_service_stop_disconnects_and_kills(monkeypatch) -> None:
    dummy_conf = DummyConf()
    dummy_ngrok = DummyNgrok()
    monkeypatch.setattr(ngrok_module, "conf", dummy_conf)
    monkeypatch.setattr(ngrok_module, "ngrok", dummy_ngrok)

    service = NgrokService(auth_token="")
    service.start_http_tunnel(port=9000)
    service.stop()

    assert dummy_ngrok.disconnect_calls == ["https://unit-test.ngrok.io/"]
    assert dummy_ngrok.kill_calls == 1


def test_ngrok_service_stop_swallows_errors(monkeypatch) -> None:
    dummy_conf = DummyConf()
    dummy_ngrok = DummyNgrok()

    def _broken_disconnect(url: str) -> None:
        raise RuntimeError(f"cannot disconnect {url}")

    dummy_ngrok.disconnect = _broken_disconnect  # type: ignore[method-assign]
    monkeypatch.setattr(ngrok_module, "conf", dummy_conf)
    monkeypatch.setattr(ngrok_module, "ngrok", dummy_ngrok)

    service = NgrokService(auth_token="")
    service.start_http_tunnel(port=7000)
    service.stop()
