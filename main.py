import logging

from services.common.logging import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    logger.info("app.bootstrap_successful")


if __name__ == "__main__":
    main()
