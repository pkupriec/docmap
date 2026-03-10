import logging

from services.presentation.backend.api import create_presentation_app

logger = logging.getLogger(__name__)
app = create_presentation_app()

