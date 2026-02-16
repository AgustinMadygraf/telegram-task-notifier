import sys

import httpx

NGROK_API_TUNNELS = "http://127.0.0.1:4040/api/tunnels"


def resolve_ngrok_https_url() -> str:
    try:
        response = httpx.get(NGROK_API_TUNNELS, timeout=5.0)
        response.raise_for_status()
        data = response.json()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            "No se pudo conectar al API local de ngrok en http://127.0.0.1:4040. "
            "Verifica que ngrok este corriendo."
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Error consultando ngrok API: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError("La respuesta de ngrok no es JSON valido.") from exc

    tunnels = data.get("tunnels")
    if not isinstance(tunnels, list):
        raise RuntimeError("Respuesta inesperada de ngrok: falta la lista 'tunnels'.")

    for tunnel in tunnels:
        if not isinstance(tunnel, dict):
            continue
        public_url = tunnel.get("public_url")
        if isinstance(public_url, str) and public_url.startswith("https://"):
            return public_url.rstrip("/")

    raise RuntimeError(
        "ngrok esta corriendo, pero no hay un tunel HTTPS activo. "
        "Ejecuta: ngrok http 8000"
    )


def main() -> None:
    try:
        url = resolve_ngrok_https_url()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(url)


if __name__ == "__main__":
    main()
