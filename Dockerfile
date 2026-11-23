# SPDX-License-Identifier: AGPL-3.0-or-later
FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 EDGEMARK_DB=/data/edgemark.db
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY entrypoint.py .
RUN useradd -u 10001 -m edgemark && mkdir /data && chown edgemark /data
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/api/state')" || exit 1
# Starts as root only long enough to give /data to PUID:PGID (default
# 10001), then runs the server as that user. See entrypoint.py.
ENTRYPOINT ["python", "/srv/entrypoint.py"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
