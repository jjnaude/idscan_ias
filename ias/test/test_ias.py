import uuid

import pytest
import redis

import ias
import ias.tasks.gpu_tasks
from ias.swagger_server import create_app

app = create_app()

testQuery = {
    "index": "d5a43450-2321-40ac-9746-9cf5d7447aca",
    "media": {"points": [{"coordinates": [[0, 0]], "type": "SIFT"}]},
}

validMediaItem = {
    "animalId": "d5a43450-2321-40ac-9746-9cf5d7447aca",
    "media": {
        "points": [
            {"coordinates": [[952, 1620]], "type": "Left Nostril"},
            {"coordinates": [[2896, 1460]], "type": "Right Nostril"},
        ],
        "url": "http://idscan.hopto.org/data/923/IMG_9238.JPG",
    },
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
            "ias.tasks.gpu_tasks.*": {"queue": "test_tasks"},
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


@pytest.fixture()
def patched(monkeypatch):
    r = redis.from_url("redis://localhost/1")
    monkeypatch.setattr(ias.api, "r", r)
    monkeypatch.setattr(ias.tasks.cpu_tasks, "r", r)
    monkeypatch.setattr(ias.tasks.cpu_tasks, "DELAY", 0.1)
    r.flushdb()
    return r


def getResult(client, job):
    # A helper function to implement the often required behaviour of polling for the
    # status of a given jobID until the status changes from 'PENDING' to something else
    # Check that we can query the generated job-id and that if we do so immmediately we
    # get a "PENDING" status
    rv = client.get("/job/" + str(job))
    assert rv.status_code == 200
    assert rv.json["status"] == "PENDING"
    while rv.json["status"] == "PENDING":
        assert rv.status_code == 200
        rv = client.get("/job/" + str(job))
    # This eventually changes to something else (typically SUCCESS, FAILURE or REVOKED),
    #  but inside this helper function we do not know what to expect so we return this
    # value for validation by the caller
    # However if we query it one MORE time we get a 404.
    rv404 = client.get("/job/" + str(job))
    assert rv404.status_code == 404
    return rv


def createMediaItemJob(client):
    rv = client.post("/media", json=validMediaItem)
    assert rv.status_code == 202
    job = uuid.UUID(rv.json["jobId"], version=4)
    return job


def createMediaItem(client):
    # A helper function to implement the often required behaviour of creating a valid
    # media item. The UUID of the created item is returned
    job = createMediaItemJob(client)
    rv = getResult(client, job)
    assert rv.json["status"] == "SUCCESS"
    assert rv.status_code == 200
    media = uuid.UUID(rv.json["result"]["id"], version=4)
    return media


def createIndexJob(client, nitems=1, fromIndex=None):
    items = [createMediaItem(client) for _ in range(nitems)]
    index_def = {"mediaIds": [str(media) for media in items]}
    if fromIndex:
        index_def["fromIndex"] = fromIndex
    rv = client.post("/index", json=index_def)
    assert rv.status_code == 202
    return uuid.UUID(rv.json["jobId"], version=4), items


def createIndex(client, nitems=1, fromIndex=None):
    # A helper function to implement the often required behaviour of creating a valid
    # index. The UUID of the created index as well as the expected composition is returned

    job, items = createIndexJob(client, nitems, fromIndex)
    rv = getResult(client, job)
    assert rv.json["status"] == "SUCCESS"
    assert rv.status_code == 200
    index = uuid.UUID(rv.json["result"]["id"], version=4)
    return index, items


def test_indexing(
    client, monkeypatch, celery_session_worker, celery_session_app, patched
):
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
    rv = client.get("/index/" + str(uuid.uuid4()))
    assert rv.status_code == 404
    # And attempting to delete a nonexistent UUID also returns a 404.
    rv = client.delete("/index/" + str(uuid.uuid4()))
    assert rv.status_code == 404
    # Generate an index and add one nonexistent media ID to it.
    rv = client.post("/index", json={"mediaIds": [str(uuid.uuid4())]})
    assert rv.status_code == 400
    assert rv.json["errorCode"] == -2
    index, composition = createIndex(client, nitems=2)
    # If we now query the indices again, out newly created index show up in the list.
    rv = client.get("/indices")
    assert rv.status_code == 200
    assert rv.json == {"indices": [str(index)]}
    # and if we query the specific index again we get the correct media IDs back.
    rv = client.get("/index/" + str(index))
    assert rv.status_code == 200
    assert rv.json == {"mediaIds": [str(media) for media in composition]}
    # We can create another index using this one as the reference
    index2, _ = createIndex(client, 3, fromIndex=index)
    rv = client.get("/indices")
    assert rv.status_code == 200
    assert str(index) in rv.json["indices"]
    assert str(index2) in rv.json["indices"]
    # But attempting to create an index from a non-existent reference fails immediately
    rv = client.post(
        "/index",
        json={
            "fromIndex": str(uuid.uuid4()),
            "mediaIds": [str(media) for media in composition],
        },
    )
    assert rv.status_code == 400
    assert rv.json["errorCode"] == -1
    # Now let us delete the indices again
    rv = client.delete("/index/" + str(index))
    assert rv.status_code == 200
    # Now let us delete the indices again
    rv = client.delete("/index/" + str(index2))
    assert rv.status_code == 200
    rv = client.get("/index/" + str(index))
    assert rv.status_code == 404
    rv = client.get("/indices")
    assert rv.status_code == 200
    assert rv.json == {"indices": []}


def test_cancel(
    client, monkeypatch, celery_session_worker, celery_session_app, patched
):
    # Start with a blank Redis database for testing and monkeypatch it into the api and cpu_tasks modules.
    r = redis.from_url("redis://localhost/1")
    r.flushdb()
    monkeypatch.setattr(ias.api, "r", r)
    monkeypatch.setattr(ias.tasks.cpu_tasks, "r", r)
    job = createMediaItemJob(client)
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
    client, monkeypatch, celery_session_worker, celery_session_app, patched
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
    media = createMediaItem(client)
    # Now try to delete the media item. It should succeed
    rv = client.delete("/media/" + str(media))
    assert rv.status_code == 200
    # But if we delete yet again, we get a 404 again
    rv = client.delete("/media/" + str(media))
    assert rv.status_code == 404


def test_queries(
    client, monkeypatch, celery_session_worker, celery_session_app, patched
):
    rv = client.post("/query", json=testQuery)
    assert rv.status_code == 400
    assert rv.json["errorCode"] == -1
    index, _ = createIndex(client, nitems=1)
    testQuery["index"] = str(index)
    rv = client.post("/query", json=testQuery)
    assert rv.status_code == 202
    job = uuid.UUID(rv.json["jobId"], version=4)
    rv = getResult(client, job)
    assert rv.json["status"] == "SUCCESS"
    assert rv.status_code == 200


def test_error_handling(
    client, monkeypatch, celery_session_worker, celery_session_app, patched
):
    # In order to test error handling we will replace the Redis object used by the
    # worker with an implementation that raises an error whenever hget is called and
    # verify that the error is reported in the expected manner.
    class buggyRedis:
        def hset(self, b, c):
            raise KeyError

    monkeypatch.setattr(ias.tasks.cpu_tasks, "r", buggyRedis)
    job = createMediaItemJob(client)
    rv = getResult(client, job)
    assert rv.json["status"] == "FAILURE"
    assert rv.status_code == 200
    assert rv.json["errorCode"] == -1
    assert rv.json["errorMessage"] == "An unknown error occurred."


def test_gpu(celery_session_worker, celery_session_app):
    assert ias.tasks.gpu_tasks.CUDA_available.delay().get()["CUDA"]
