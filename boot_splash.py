import socket

from config_store import load_config
from display import show_message


def primary_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "0.0.0.0"
    finally:
        sock.close()


def main() -> None:
    port = int(load_config().get("web_port", 8080))
    show_message([
        "Ize Ribbon",
        "[ Booting... ]",
        f"ize-ribbon.local:{port}",
        f"{primary_ip()}:{port}",
    ])


if __name__ == "__main__":
    main()
