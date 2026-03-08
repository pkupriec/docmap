import logging

from services.common.logging import configure_logging
from services.control.api import create_app

logger = logging.getLogger(__name__)
app = create_app()


def main() -> None:
    configure_logging()
    logger.info("app.bootstrap_successful control_api_enabled=true")


if __name__ == "__main__":
    main()
