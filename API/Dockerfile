FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --user --no-cache-dir -r requirements.txt && \
    find /root/.local -type f -name "*.pyc" -delete && \
    find /root/.local -type d -name "__pycache__" -delete && \
    find /root/.local -type d -name "tests" -delete && \
    find /root/.local -type d -name "*.dist-info" -not -name "*.dist-info/RECORD" -exec rm -rf {} + 2>/dev/null; \
    rm -rf /root/.local/pycountry/locales/* && \
    rm -rf /root/.local/lib/python*/site-packages/*/tests && \
    rm -rf /root/.local/lib/python*/site-packages/*/test

FROM gcr.io/distroless/python3

WORKDIR /app

COPY --from=builder /root/.local /root/.local .

ENV PYTHONPATH=/root/.local/lib/python3.12/site-packages \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY main.py run.py ./
COPY API_Endpoints ./API_Endpoints

EXPOSE 4463

ENTRYPOINT ["python", "run.py"]
