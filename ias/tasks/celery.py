from celery import Celery

celeryApp = Celery(
    "idscanApp", backend="redis://localhost", broker="pyamqp://guest@localhost//"
)
celeryApp.config_from_object("ias.tasks.celeryconfig")
# celeryApp.conf.task_routes = {'tasks.gpu_tasks.*': {'queue': 'gpu_tasks'},'tasks.cpu_tasks.*': {'queue': 'cpu_tasks'}}
# celeryApp.conf.result_expires = 60
