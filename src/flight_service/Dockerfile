FROM python:3.12-slim

WORKDIR /app

COPY src/flight_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/proto /app/proto
RUN mkdir -p /app/generated && python -m grpc_tools.protoc \
    -I/app/proto \
    --python_out=/app/generated \
    --grpc_python_out=/app/generated \
    /app/proto/flight_service.proto

COPY src/flight_service/app /app/app

ENV PYTHONPATH=/app:/app/generated
CMD ["python", "-m", "app.main"]
