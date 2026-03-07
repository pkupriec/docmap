from services.common.logging import configure_logging


def main() -> None:
    configure_logging()
    print("DocMap bootstrap successful")


if __name__ == "__main__":
    main()
