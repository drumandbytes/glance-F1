FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache /var/lib/apt/lists/*

# glibc's malloc rarely returns freed pages back to the OS, so the one-time
# large pandas/numpy allocation from fastf1's session.load(telemetry=True)
# (see API_Endpoints/map/map_generator.py) leaves RSS permanently elevated
# at that peak even once the data is gone - not a leak, but it looks and
# behaves like one from outside the process. jemalloc actively releases
# freed memory, so RSS comes back down after that peak instead of staying
# there for the container's lifetime. Symlinked to an arch-independent path
# so LD_PRELOAD doesn't need to know the multiarch triplet (amd64 vs arm64).
RUN apt-get update && apt-get install -y --no-install-recommends libjemalloc2 \
    && ln -s "$(dpkg -L libjemalloc2 | grep 'libjemalloc\.so\.2$')" /usr/lib/libjemalloc.so.2 \
    && rm -rf /var/lib/apt/lists/*
ENV LD_PRELOAD=/usr/lib/libjemalloc.so.2

COPY . .

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4463"]
