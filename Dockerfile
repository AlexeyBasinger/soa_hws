FROM openapitools/openapi-generator-cli:v7.8.0 AS codegen
WORKDIR /work

COPY src/openapi/openapi.yaml /work/openapi.yaml

RUN rm -rf /work/generated && \
     /usr/local/bin/docker-entrypoint.sh generate \
      -i /work/openapi.yaml \
      -g python-fastapi \
      -o /work/generated \
      --additional-properties=packageName=openapi_server


FROM python:3.12-slim
WORKDIR /app


COPY src/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/server /app/server

COPY --from=codegen /work/generated /app/generated

COPY src/server/impl /app/generated/src/openapi_server/impl


ENV PYTHONPATH=/app:/app/generated/src

EXPOSE 8080
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8080"]
