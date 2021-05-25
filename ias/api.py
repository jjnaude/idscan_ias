import json

import flask
import redis

from ias.tasks.celery import celeryApp
from ias.tasks.cpu_tasks import buildIndex, createMedia, query

r = redis.from_url("redis://localhost/0")


def postMedia(body):  # noqa: E501
    jobId = str(createMedia.delay(body))
    r.set(jobId, 1)
    return {"jobId": jobId}, 202


def deleteMedia(mediaId):  # noqa: E501
    if r.hexists("media", mediaId):
        r.hdel("media", mediaId)
        return flask.Response(status=200)
    else:
        return flask.Response(status=404)


def postQuery(body):  # noqa: E501
    jobId = str(query.delay(body))
    r.set(jobId, 1)
    return {"jobId": jobId}, 202


def deleteIndex(indexId):  # noqa: E501
    if r.hdel("indices", indexId):
        return flask.Response(status=200)
    else:
        return flask.Response(status=404)


def getIndex(indexId):  # noqa: E501
    index = r.hget("indices", indexId)
    if index:
        return json.loads(index), 200
    else:
        return flask.Response(status=404)


def postIndex(body):  # noqa: E501
    """Request the (re)building of an index to provide fast lookups within a defined subset of animals.

    &lt;p&gt;It is anticipated that initially indexes will correspond to herds, to allow for fast lookup of a cow within a known herd, but in the longer term the application may choose to define an index for any subset of animals that will often be the target of a query (i.e. the subset of all animals reported stolen, or the subset of all animals from a given province).&lt;/p&gt; &lt;p&gt;Index building is potentially an expensive operation, so the workflow should be designed to avoid excessive rebuilding. When a herd is initially defined, all animals should be enrolled before building the index for the herd, rather than rebuilding after every addition. However, it is not required to wait for all enrollments to complete before initiating the index build, as the Image analysis server will enforce this constraint via job-scheduling.&lt;/p&gt; # noqa: E501

    :param body:
    :type body: List[]
    :param index_id: ID of the index that should be (re)built.
    :type index_id: int

    :rtype: InlineResponse2023
    """
    jobId = str(buildIndex.delay(body))
    r.set(jobId, 1)
    return {"jobId": jobId}, 202


def getIndices():  # noqa: E501
    """Get a list of currently defined indices.

     # noqa: E501


    :rtype: InlineResponse2001
    """
    return {"indices": [x.decode("utf-8") for x in r.hkeys("indices")]}, 200


def cancelJob(jobId):  # noqa: E501
    """Cancel a job.

    Cancel a job. Useful if the user initiates an expensive operation like a global lookup and then closes the app before it is complete or if an index rebuild is requested before the previous index build has completed. # noqa: E501

    :param job_id: Job-id that is being cancelled.
    :type job_id: str

    :rtype: str
    """
    if r.get(jobId):
        res = celeryApp.AsyncResult(jobId)
        res.revoke()
        r.delete(jobId)
        return flask.Response(status=200)
    else:
        return flask.Response(status=404)


def getJob(jobId):  # noqa: E501
    """Query the status of an enrollment, index-building or query task.

    This endpoint will report on the status of the enrollment, index-build or query that is referred to by the supplied job-id. # noqa: E501

    :param job_id: Job-id for which the task status is being requested.
    :type job_id: str

    :rtype: InlineResponse2002
    """
    if r.get(jobId):
        res = celeryApp.AsyncResult(jobId)
        result = {}
        result["status"] = res.state
        if result["status"] in ["SUCCESS", "FAILURE"]:
            r.delete(jobId)
            try:
                jobresult = res.get()
                result["result"] = jobresult
            except Exception:
                result["errorCode"] = -1
                result["errorMessage"] = "An unknown error occurred."
        return result, 200
    else:
        return flask.Response(status=404)
