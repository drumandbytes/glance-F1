#!/usr/bin/env python3
import asyncio
from starlette.servers import Server
from main import app

if __name__ == "__main__":
    server = Server(app, host="0.0.0.0", port=4463)
    asyncio.run(server.serve())
