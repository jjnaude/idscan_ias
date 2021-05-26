from celery import Celery

celeryApp = Celery(
    "ias.tasks", backend="redis://localhost", broker="pyamqp://guest@localhost//"
)
celeryApp.config_from_object("ias.tasks.celeryconfig")
celeryApp.conf.task_routes = {
    "ias.tasks.gpu_tasks.*": {"queue": "gpu_tasks"},
    "ias.tasks.cpu_tasks.*": {"queue": "cpu_tasks"},
}
# celeryApp.conf.result_expires = 60
