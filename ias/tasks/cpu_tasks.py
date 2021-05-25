import json
import time
import uuid

import redis
from celery import shared_task

r = redis.Redis()

DELAY = 1


@shared_task
def createMedia(media):
    time.sleep(DELAY)
    id = str(uuid.uuid4())
    r.hset("media", id, json.dumps(media))
    return {"id": id}


@shared_task
def buildIndex(body):
    time.sleep(DELAY)
    id = str(uuid.uuid4())
    r.hset("indices", id, json.dumps(body))
    return {"id": id}


@shared_task
def query(body):
    time.sleep(DELAY)
    return {
        "matches": [
            {
                "dst": {
                    "points": [
                        {
                            "coordinates": [[0]],
                            "descriptors": [[1.34, 2.34, -512]],
                            "orientations": [1.8],
                            "scales": [1],
                            "type": "Left Nostril",
                        }
                    ],
                    "url": "https://idscan.s3.af-south-1.amazonaws.com/17-007/17-007 (1).jpg",
                },
                "matchID": 0,
                "matchScore": 0.97,
                "matches": [[0]],
                "src": {
                    "points": [
                        {
                            "coordinates": [[0]],
                            "descriptors": [[1.34, 2.34, -512]],
                            "orientations": [1.8],
                            "scales": [1],
                            "type": "Left Nostril",
                        }
                    ]
                },
            }
        ]
    }
