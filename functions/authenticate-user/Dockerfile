FROM ghcr.io/openfaas/of-watchdog:0.10.4 AS watchdog
FROM python:3.12-slim

COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
RUN chmod +x /usr/bin/fwatchdog

RUN addgroup --system --gid 10001 app && adduser --system --ingroup app --uid 10001 app

WORKDIR /home/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py db.py crypto.py ./
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
HEALTHCHECK --interval=5s --timeout=3s CMD wget --quiet --tries=1 --spider http://127.0.0.1:8080/healthz || exit 1

CMD ["fwatchdog"]
