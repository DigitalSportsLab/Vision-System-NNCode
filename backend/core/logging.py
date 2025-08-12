import logging

def setup_logging():
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s - %(threadName)s - %(message)s", datefmt="%H:%M:%S")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    app_logger.handlers.clear()
    app_logger.addHandler(ch)

    # dämpfen
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("ultralytics").handlers = []

    return app_logger
