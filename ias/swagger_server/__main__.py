#!/usr/bin/env python3
import os

from celery import Celery
from celery.exceptions import TimeoutError

from ias.swagger_server import create_app
from ias.tasks.gpu_tasks import CUDA_available

celery = Celery(
    "ias.swagger_server",
    backend="redis://localhost",
    broker="pyamqp://guest@localhost//",
)
celery.config_from_object("ias.swagger_server.celeryconfig")

app = create_app()
celery.set_default()
if "IAS_SKIP_GPU_CHECK" not in os.environ:
    res = CUDA_available.delay()
    try:
        res = res.get(timeout=10)
        if not res["CUDA"]:
            print(
                """
            The GPU worker service was detected, but it reports not having CUDA available.
            This likely indicates that:
                - you are running it on hardware where no NVIDIA GPU is present,
                - your GPU is too old
                - your GPU-driver is too old
                - your GPU is too old
                - one of the prerequisites described at https://docs.docker.com/config/containers/resource_constraints/#gpu
                is not installed correctly.
                - you are not passing the right parameters to Docker or docker-compose.
                See instructions for compose:
                (https://docs.docker.com/compose/gpu-support/)
                and for raw Docker:
                (https://docs.docker.com/config/containers/resource_constraints/#gpu)
                and note that for compose you need to specify compute under capabilities to ensure CUDA access.

            If you do not want to debug GPU integration right now, you can bypass this
            start-up check by setting the environment variable IAS_SKIP_GPU_CHECK, but
            you probably shouldn't. You have been warned.
                """
            )
            exit()
    except TimeoutError:
        print(
            """
        The GPU worker service was not detected. If you started with:
        docker-compose up
        this likely indicates that something went wrong on that service and it
        exited. Check the logs to confirm.

        If you launched in some other way, it is possible that you just neglected
        to launch the GPU worker.

        If you do not want to debug GPU integration right now, you can bypass this
        start-up check by setting the environment variable IAS_SKIP_GPU_CHECK, but
        you probably shouldn't. You have been warned."""
        )
        exit()
app.run(port=8080)
# import connexion
# from swagger_server import encoder


# def main():
#     app = connexion.App(__name__, specification_dir='./swagger/')
#     app.app.json_encoder = encoder.JSONEncoder
#     app.add_api('swagger.yaml', arguments={'title': 'ID-Scan Image Analysis API'}, pythonic_params=True)
#     app.run(debug=True,port=8080)


# if __name__ == '__main__':
#     main()
