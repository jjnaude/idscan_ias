from celery import Celery, shared_task

celery = Celery(
    "ias.tasks.gpu_tasks",
    backend="redis://localhost",
    broker="pyamqp://guest@localhost//",
)

celery.config_from_object("ias.tasks.gpu_tasks.celeryconfig")


@shared_task
def CUDA_available():
    import torch

    return {"CUDA": torch.cuda.is_available()}
