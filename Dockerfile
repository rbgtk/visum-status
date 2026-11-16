FROM python:3.13-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY certs/root-ca.crt /usr/local/share/ca-certificates/root-ca.crt
RUN update-ca-certificates

COPY main.py .

RUN useradd --create-home --uid 10001 appuser
USER appuser

CMD ["python", "main.py"]
