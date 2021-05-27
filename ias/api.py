import json

import flask
import redis
from celery import current_app

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
    if not r.hget("indices", body["index"]):
        return {
            "errorCode": -1,
            "errorMessage": f"Index {body['index']} does not exist",
        }, 400
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
    if "fromIndex" in body.keys():
        if not r.hget("indices", body["fromIndex"]):
            return {
                "errorCode": -1,
                "errorMessage": f"Index {body['fromIndex']}, that was provided as fromIndex does not exist",
            }, 400
    for mediaId in body["mediaIds"]:
        if not r.hget("media", mediaId):
            return {
                "errorCode": -2,
                "errorMessage": f"MediaItem {mediaId}, does not exist",
            }, 400
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
        res = current_app.AsyncResult(jobId)
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
        res = current_app.AsyncResult(jobId)
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
