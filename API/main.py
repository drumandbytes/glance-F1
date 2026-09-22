import asyncio
import logging
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
import pytz

from API_Endpoints.constructors_cleaner import get_constructors_championship
from API_Endpoints.drivers_cleaner import get_drivers_championship
from API_Endpoints.last_race_cleaner import get_last_race
from API_Endpoints.current_race_cleaner import get_next_race
from API_Endpoints.tyre_usage_cleaner import get_tyre_usage
from API_Endpoints import data_sources

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": "f1-api",
            "message": record.msg,
        }
        if hasattr(record, "extra"):
            log_obj.update(record.__dict__.get("extra", {}))
        return json.dumps(log_obj)

def setup_logging():
    logger = logging.getLogger("f1-api")
    debug = os.getenv("DEBUG", "false").lower() == "true"
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    return logger

logger = setup_logging()

@asynccontextmanager
async def lifespan(app):
    logger.info("server_started", extra={"port": 4463})
    yield
    logger.info("server_shutdown")
    await data_sources.close_http_client()

routes = [
    Route("/f1/drivers_standings/", endpoint=get_drivers_championship, methods=["GET"]),
    Route("/f1/constructors_standings/", endpoint=get_constructors_championship, methods=["GET"]),
    Route("/f1/last_race/", endpoint=get_last_race, methods=["GET"]),
    Route("/f1/next_race/", endpoint=get_next_race, methods=["GET"]),
    Route("/f1/tyre_usage/", endpoint=get_tyre_usage, methods=["GET"]),
]

app = Starlette(routes=routes, lifespan=lifespan)
