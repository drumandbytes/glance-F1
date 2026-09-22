FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /root/.local /root/.local .

ENV PATH=/root/.local/bin:$PATH

COPY main.py run.py ./
COPY API_Endpoints ./API_Endpoints

EXPOSE 4463

CMD ["python", "run.py"]
