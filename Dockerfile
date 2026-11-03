FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TRACKER_STATE_DIR=/data TRACKER_BIND_HOST=0.0.0.0
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home tracker && mkdir /data /app/staticfiles && chown tracker:tracker /data /app /app/staticfiles
COPY --chown=tracker:tracker . .
USER tracker
CMD ["python", "boot.py"]
