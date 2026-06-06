from display import show_message
from network_status import primary_ip, web_url_lines


def main() -> None:
    show_message([
        "Ize Ribbon",
        "[ Booting... ]",
        *web_url_lines(primary_ip()),
    ])


if __name__ == "__main__":
    main()
