FROM ghcr.io/openfaas/of-watchdog:0.10.4 AS watchdog
FROM python:3.12-slim

COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
RUN chmod +x /usr/bin/fwatchdog

# Lie l'image GHCR au dépôt GitHub (section "Packages" du repo) + licence.
LABEL org.opencontainers.image.source="https://github.com/COFRAP-EPSI-2026/cofrap-backend" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.title="cofrap-generate-password"

RUN addgroup --system --gid 10001 app && adduser --system --ingroup app --uid 10001 app

WORKDIR /home/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py db.py crypto.py qr.py ./
RUN chown -R app:app /home/app

USER 10001

ENV fprocess="uvicorn main:app --host 127.0.0.1 --port 5000"
ENV upstream_url="http://127.0.0.1:5000"
ENV mode="http"
ENV cgi_headers="true"
ENV exec_timeout="30s"
ENV write_timeout="30s"
ENV read_timeout="30s"

EXPOSE 8080
# Sonde de santé en Python : l'image python:3.12-slim n'embarque ni wget ni curl.
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).status == 200 else 1)" || exit 1

CMD ["fwatchdog"]
