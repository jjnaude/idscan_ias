backend = "redis://localhost"
broker = "pyamqp://guest@localhost//"
task_routes = {
    "ias.tasks.gpu_tasks.*": {"queue": "gpu_tasks"},
    "ias.tasks.cpu_tasks.*": {"queue": "cpu_tasks"},
}
result_expires = 60
