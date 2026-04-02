FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir flask gunicorn requests
COPY app.py .
COPY templates/ templates/
EXPOSE 8090
CMD ["gunicorn", "--bind", "0.0.0.0:8090", "--workers", "2", "--threads", "4", "--timeout", "30", "app:app"]
