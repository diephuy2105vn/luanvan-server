import logging

from colorlog import ColoredFormatter

from server.settings import settings

# Tạo formatter cho logging với màu sắc
formatter = ColoredFormatter(
    "%(log_color)sMY_LOG%(reset)s:   %(message)s \n%(cyan)s%(pathname)s",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red,bg_white",
    },
    reset=True,
    style="%",
)


logging.basicConfig(level=settings.log_level.value)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logging.getLogger().handlers = []
logging.getLogger().addHandler(handler)
