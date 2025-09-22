FROM python:3.11-slim
WORKDIR /app
COPY server.py /app/server.py
RUN pip install --no-cache-dir flask prometheus-client
ENV PORT=5055
ENV HOST=0.0.0.0
EXPOSE 5055
CMD ["python", "/app/server.py"]
