FROM python:3.10-slim-bookworm@sha256:68d914ec641a0b69267ce65184d000a2bc3a9ee2590ab702b82250ab2385735a

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sim_base.py .
COPY simulator.py .
COPY bacnet_server.py .

CMD ["python", "-u", "simulator.py"]
