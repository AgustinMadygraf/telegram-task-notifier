from pyngrok import conf, ngrok


class NgrokService:
    def __init__(self, auth_token: str = "") -> None:
        self._auth_token = auth_token.strip()
        self._tunnel = None

    def start_http_tunnel(self, port: int, domain: str = "") -> str:
        if self._auth_token:
            conf.get_default().auth_token = self._auth_token

        kwargs: dict[str, object] = {
            "addr": str(port),
            "proto": "http",
            "bind_tls": True,
        }
        if domain.strip():
            kwargs["domain"] = domain.strip()

        self._tunnel = ngrok.connect(**kwargs)
        return self._tunnel.public_url.rstrip("/")

    def stop(self) -> None:
        try:
            if self._tunnel is not None:
                ngrok.disconnect(self._tunnel.public_url)
            ngrok.kill()
        except Exception:
            pass
