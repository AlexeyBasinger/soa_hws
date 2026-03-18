from concurrent import futures
import logging

import grpc

import flight_service_pb2_grpc as pb2_grpc
from app.config import settings
from app.service import FlightService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_FlightServiceServicer_to_server(FlightService(), server)
    server.add_insecure_port(f"[::]:{settings.grpc_port}")
    server.start()
    print(f"Flight Service started on port {settings.grpc_port}")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
