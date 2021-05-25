import uuid

import pytest
import redis

import ias
from ias.swagger_server import create_app

app = create_app()


testQuery = {
    "index": "d5a43450-2321-40ac-9746-9cf5d7447aca",
    "media": {"points": [{"coordinates": [[0, 0]], "type": "SIFT"}]},
}


@pytest.fixture
def client():
    with app.app.test_client() as client:
        yield client


@pytest.fixture(scope="session")
def celery_config():
    return {
        "broker_url": "amqp://",
        "result_backend": "redis://",
        "task_routes": {
            "ias.tasks.gpu_tasks.*": {"queue": "gpu_tasks"},
            "ias.tasks.cpu_tasks.*": {"queue": "test_tasks"},
        },
    }


@pytest.fixture(scope="session")
def celery_includes():
    return ["ias.tasks.cpu_tasks"]


@pytest.fixture(scope="session")
def celery_worker_parameters():
    return {
        "queues": ("test_tasks"),
        "perform_ping_check": False,  # https://github.com/celery/celery/issues/3642#issuecomment-457773294
    }


@pytest.fixture(scope="session")
def celery_enable_logging():
    return True


def test_indexing(client, monkeypatch, celery_session_worker, celery_session_app):
    # Start with a blank Redis database for testing and monkeypatch it into the api and cpu_tasks modules.
    r = redis.from_url("redis://localhost/1")
    r.flushdb()
    monkeypatch.setattr(ias.api, "r", r)
    monkeypatch.setattr(ias.tasks.cpu_tasks, "r", r)
    # mocker.patch.object(ias.api,'r',r)
    # Check that /indices returns an empty set initially.
    rv = client.get("/indices")
    assert rv.status_code == 200
    assert rv.json == {"indices": []}

    # Generate an arbitrary UUID and check that querying for it returns a 404
    media = uuid.uuid4()
    rv = client.get("/index/" + str(media))
    assert rv.status_code == 404
    # And attempting to delete a nonexistent UUID also returns a 404.
    media = uuid.uuid4()
    rv = client.delete("/index/" + str(media))
    assert rv.status_code == 404
    # Generate an index and add one media ID to it.
    rv = client.post("/index", json={"mediaIds": [str(media)]})
    assert rv.status_code == 202
    job = uuid.UUID(rv.json["jobId"], version=4)
    # Check that we can query the generated job-id and that if we do so immmediately we get a "PENDING" status
    rv = client.get("/job/" + str(job))
    assert rv.status_code == 200
    assert rv.json["status"] == "PENDING"
    while rv.json["status"] == "PENDING":
        assert rv.status_code == 200
        rv = client.get("/job/" + str(job))
    # Which eventually turns to "SUCCESS" and has an associated result:id field that contains a UUID4
    assert rv.json["status"] == "SUCCESS"
    assert rv.status_code == 200
    index = uuid.UUID(rv.json["result"]["id"], version=4)
    # But if we query the job ID one more time, we get a 404 again.
    rv = client.get("/job/" + str(job))
    assert rv.status_code == 404
    # If we now query the indices again, out newly created index show up in the list.
    rv = client.get("/indices")
    assert rv.status_code == 200
    assert rv.json == {"indices": [str(index)]}
    # and if we query the specific index again we get the correct media ID back.
    rv = client.get("/index/" + str(index))
    assert rv.status_code == 200
    assert rv.json == {"mediaIds": [str(media)]}
    # Now let us delete the index again
    rv = client.delete("/index/" + str(index))
    assert rv.status_code == 200
    rv = client.get("/index/" + str(index))
    assert rv.status_code == 404
    rv = client.get("/indices")
    assert rv.status_code == 200
    assert rv.json == {"indices": []}


def test_cancel(client, monkeypatch, celery_session_worker, celery_session_app):
    # Start with a blank Redis database for testing and monkeypatch it into the api and cpu_tasks modules.
    r = redis.from_url("redis://localhost/1")
    r.flushdb()
    monkeypatch.setattr(ias.api, "r", r)
    monkeypatch.setattr(ias.tasks.cpu_tasks, "r", r)
    # mocker.patch.object(ias.api,'r',r)
    # Check that /indices returns an empty set initially.
    # Generate an index and add one media ID to it.
    media = uuid.uuid4()
    rv = client.post("/index", json={"mediaIds": [str(media)]})
    assert rv.status_code == 202
    job = uuid.UUID(rv.json["jobId"], version=4)
    # Check that we can query the generated job-id and that if we do so immmediately we get a "PENDING" status
    rv = client.get("/job/" + str(job))
    assert rv.status_code == 200
    assert rv.json["status"] == "PENDING"
    # Now immediately cancel the job.
    rv = client.delete("/job/" + str(job))
    assert rv.status_code == 200
    # If we recheck job status we a 404
    rv = client.get("/job/" + str(job))
    assert rv.status_code == 404
    # And attempting to cancel the job a second time also results in a 404.
    rv = client.delete("/job/" + str(job))
    assert rv.status_code == 404


def test_media_management(
    client, monkeypatch, celery_session_worker, celery_session_app
):
    # Start with a blank Redis database for testing and monkeypatch it into the api and cpu_tasks modules.
    r = redis.from_url("redis://localhost/1")
    r.flushdb()
    monkeypatch.setattr(ias.api, "r", r)
    monkeypatch.setattr(ias.tasks.cpu_tasks, "r", r)
    # mocker.patch.object(ias.api,'r',r)
    # Generate an arbitrary UUID and check that deleting it returns a 404
    t1 = uuid.uuid4()
    rv = client.delete("/media/" + str(t1))
    assert rv.status_code == 404
    rv = client.post(
        "/media",
        json={
            "animalId": "d5a43450-2321-40ac-9746-9cf5d7447aca",
            "media": {
                "points": [
                    {"coordinates": [[952, 1620]], "type": "Left Nostril"},
                    {"coordinates": [[2896, 1460]], "type": "Right Nostril"},
                ],
                "url": "http://idscan.hopto.org/data/923/IMG_9238.JPG",
            },
        },
    )
    assert rv.status_code == 202
    job = uuid.UUID(rv.json["jobId"], version=4)
    # Check that we can query the generated job-id and that if we do so immmediately we get a "PENDING" status
    rv = client.get("/job/" + str(job))
    assert rv.status_code == 200
    assert rv.json["status"] == "PENDING"
    while rv.json["status"] == "PENDING":
        assert rv.status_code == 200
        rv = client.get("/job/" + str(job))
    # Which eventually turns to "SUCCESS"
    assert rv.json["status"] == "SUCCESS"
    assert rv.status_code == 200
    media = uuid.UUID(rv.json["result"]["id"], version=4)
    # But if we query the job ID one more time, we get a 404 again.
    rv = client.get("/job/" + str(job))
    assert rv.status_code == 404
    # Now try to delete the media item. It should succeed
    rv = client.delete("/media/" + str(media))
    assert rv.status_code == 200
    # But if we delete yet again, we get a 404 again
    rv = client.delete("/media/" + str(media))
    assert rv.status_code == 404


def test_queries(client, monkeypatch, celery_session_worker, celery_session_app):
    rv = client.post("/query", json=testQuery)
    assert rv.status_code == 202
    job = uuid.UUID(rv.json["jobId"], version=4)
    # Check that we can query the generated job-id and that if we do so immmediately we get a "PENDING" status
    rv = client.get("/job/" + str(job))
    assert rv.status_code == 200
    assert rv.json["status"] == "PENDING"
    while rv.json["status"] == "PENDING":
        assert rv.status_code == 200
        rv = client.get("/job/" + str(job))
    # Which eventually turns to "SUCCESS"
    assert rv.json["status"] == "SUCCESS"
    assert rv.status_code == 200
    # But if we query the job ID one more time, we get a 404 again.
    rv = client.get("/job/" + str(job))
    assert rv.status_code == 404


def test_error_handling(client, monkeypatch, celery_session_worker, celery_session_app):
    # In order to test error handling we will replace the Redis object used by the
    # worker with an implementation that raises an error whenever hget is called and
    # verify that the error is reported in the expected manner.
    class buggyRedis:
        def hset(self, b, c):
            raise KeyError

    r = redis.from_url("redis://localhost/1")
    r.flushdb()
    monkeypatch.setattr(ias.api, "r", r)
    monkeypatch.setattr(ias.tasks.cpu_tasks, "r", buggyRedis)
    rv = client.post("/index", json=testQuery)
    assert rv.status_code == 202
    job = uuid.UUID(rv.json["jobId"], version=4)
    # Check that we can query the generated job-id and that if we do so immmediately we get a "PENDING" status
    rv = client.get("/job/" + str(job))
    assert rv.status_code == 200
    assert rv.json["status"] == "PENDING"
    while rv.json["status"] == "PENDING":
        assert rv.status_code == 200
        rv = client.get("/job/" + str(job))
    # Which eventually turns to "FAILURE"
    assert rv.json["status"] == "FAILURE"
    assert rv.status_code == 200
    assert rv.json["errorCode"] == -1
    assert rv.json["errorMessage"] == "An unknown error occurred."
