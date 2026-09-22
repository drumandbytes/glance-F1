FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --user --no-cache-dir -r requirements.txt

FROM gcr.io/distroless/python3

WORKDIR /app

COPY --from=builder /root/.local /root/.local .

ENV PYTHONPATH=/root/.local/lib/python3.12/site-packages

COPY main.py run.py ./
COPY API_Endpoints ./API_Endpoints

EXPOSE 4463

ENTRYPOINT ["python", "run.py"]
