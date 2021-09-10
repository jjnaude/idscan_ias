import io
import json
import os

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from dlclive import DLCLive
from PIL import Image, ImageTransform, UnidentifiedImageError
from PIL.ImageDraw import Draw

dlc_live = DLCLive(
    "/workspaces/ias/data/CattleSquare1/CattleSquare1-Hannes-2021-07-25/exported-models/DLC_CattleSquare1_mobilenet_v2_1.0_iteration-0_shuffle-1"
)
rf = cv2.ximgproc.RidgeDetectionFilter_create(ksize=5, out_dtype=cv2.CV_32FC1)
sift = cv2.SIFT_create()
destFolder = "/workspaces/ias/data/PipelineDebug"
subfolders = [
    "annotatedOriginal",
    "extracted",
    "ridgeFiltered",
    "keypoints",
    "all",
    "original",
    "square",
    "normSquare",
    "nostrilCoordinates",
    "nostrilCoordinatesInteractive",
    "qualityInfo",
]
scale = 10

for folder in subfolders:
    os.makedirs(os.path.join(destFolder, folder), exist_ok=True)


def getInputImage(filename):
    tgtName = os.path.join(destFolder, "original", filename)
    if os.path.exists(tgtName):
        im = Image.open(tgtName)
        im.load()
        return im
    data = requests.get(
        "https://idscanprod.blob.core.windows.net/animal/" + filename,
        allow_redirects=True,
    ).content
    with open(tgtName, "wb") as f:
        f.write(data)
        im = Image.open(io.BytesIO(data))
    im.load()
    return im


def getSquareImage(filename):
    tgtName = os.path.join(destFolder, "square", filename.replace(".jpg", ".png"))
    if os.path.exists(tgtName):
        im = Image.open(tgtName)
        im.load()
        return im
    im = getInputImage(filename)
    if im.width > im.height:
        im = im.rotate(-90, expand=True)
    start = int((im.height - im.width) / 2)
    im2 = im.crop([0, start, im.width, start + im.width])
    im2.save(tgtName)
    return im2


def getNormalisedSquare(imageName):
    tgtName = os.path.join(destFolder, "normSquare", imageName.replace(".jpg", ".png"))
    if os.path.exists(tgtName):
        im = Image.open(tgtName)
        im.load()
        return im
    im = getSquareImage(imageName)
    im2 = im.resize([1000, 1000], Image.LANCZOS)
    im2.save(tgtName)
    return im2


def getNostrilCoordinates(imageName):
    tgtName = os.path.join(
        destFolder, "nostrilCoordinates", imageName.replace(".jpg", ".json")
    )
    if os.path.exists(tgtName):
        with open(tgtName, "rt") as f:
            return json.load(f)
    im = getSquareImage(imageName)
    xyp = dlc_live.init_inference(np.asarray(im))
    nostrils = {
        "left": list(xyp[0, 0:2].astype(np.float64)),
        "right": list(xyp[1, 0:2].astype(np.float64)),
    }
    with open(tgtName, "wt") as f:
        json.dump(nostrils, f)
    return nostrils


def getNostrilCoordinatesInteractive(imageName, forceInteractive=False):
    tgtName = os.path.join(
        destFolder, "nostrilCoordinatesInteractive", imageName.replace(".jpg", ".json")
    )
    if os.path.exists(tgtName):
        with open(tgtName, "rt") as f:
            nostrils = json.load(f)
            if not forceInteractive:
                return nostrils
    else:
        nostrils = getNostrilCoordinates(imageName)
    im = getSquareImage(imageName)
    fig = plt.figure()

    def showIm():
        plt.imshow(np.asarray(im))
        plt.scatter(*nostrils["left"], c="blue")
        plt.scatter(*nostrils["right"], c="red")

    showIm()

    def onclick(event):
        ix, iy = event.xdata, event.ydata
        if event.button == 1:
            nostrils["left"] = [ix, iy]
        if event.button == 3:
            nostrils["right"] = [ix, iy]
        print(nostrils)
        showIm()
        plt.show()

    cid = fig.canvas.mpl_connect("button_press_event", onclick)
    plt.show()
    plt.close(fig)
    with open(tgtName, "wt") as f:
        json.dump(nostrils, f)
    return nostrils


def getNormalisedMuzzle(imageName):
    tgtName = os.path.join(destFolder, "extracted", imageName.replace(".jpg", ".png"))
    if os.path.exists(tgtName):
        im = Image.open(tgtName)
        im.load()
        return im
    im = getSquareImage(imageName)
    nostrils = getNostrilCoordinatesInteractive(imageName)
    top_left = np.asarray(nostrils["left"])
    top_right = np.asarray(nostrils["right"])
    right_vector = top_right - top_left
    down_vector = np.cross(right_vector, [0, 0, -1])[0:2].astype(np.float32)
    top_left = top_left - right_vector * 0.25 - down_vector * 0.25
    top_right = top_right + right_vector * 0.25 - down_vector * 0.25
    bottom_left = top_left + down_vector
    bottom_right = top_right + down_vector
    im2 = im.copy()
    imd = Draw(im2)
    imd.line(
        np.hstack([top_left, top_right, bottom_right, bottom_left, top_left]),
        width=3,
        fill="blue",
    )
    im2.save(os.path.join(destFolder, "annotatedOriginal", imageName))
    # try:
    #     os.symlink(tgtName,tgtName.replace('annotatedOriginal','all').replace('.jpg','_0.jpg'))
    # except FileExistsError:
    #     pass
    tf = ImageTransform.QuadTransform(
        np.hstack([top_right, bottom_right, bottom_left, top_left])
    )
    im2 = im.transform((900, 600), tf)
    im2.save(tgtName)
    return im2


def getQualityInfo(imageName, forceInteractive=False):
    global key
    tgtName = os.path.join(
        destFolder, "qualityInfo", imageName.replace(".jpg", ".json")
    )
    quality = {"useAsTemplate": True, "useInLookup": True}
    if os.path.exists(tgtName):
        with open(tgtName, "rt") as f:
            quality = json.load(f)
            if not forceInteractive:
                return quality
    im = getNormalisedSquare(imageName)
    im2 = getRidgeFilteredImage(imageName)
    fig, (ax1, ax2) = plt.subplots(1, 2)
    ax1.imshow(im2)
    ax2.imshow(im)
    key = None
    figManager = plt.get_current_fig_manager()
    figManager.resize(*figManager.window.maxsize())

    def press(event):
        global key
        key = event.key

    fig.canvas.mpl_connect("key_press_event", press)
    while key not in ["1", "2", "0"]:
        k = plt.waitforbuttonpress()
    quality = {"useAsTemplate": key > "1", "useInLookup": key > "0"}
    plt.close(fig)
    with open(tgtName, "wt") as f:
        json.dump(quality, f)
    return quality


def getRidgeFilteredImage(imageName):
    tgtName = os.path.join(
        destFolder, "ridgeFiltered", imageName.replace(".jpg", ".png")
    )
    if os.path.exists(tgtName):
        try:
            im = Image.open(tgtName)
            im.load()
            return im
        except OSError:
            pass
    rfi = rf.getRidgeFilteredImage(np.asarray(getNormalisedMuzzle(imageName)))
    # rfi =rf.getRidgeFilteredImage(np.asarray(getNormalisedSquare(imageName)))
    rfi8 = cv2.normalize(
        rfi, dst=None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U
    )
    im = Image.fromarray(rfi8)
    im.save(tgtName)
    return im


def getKeypoints(imageName):
    srcName = os.path.join(destFolder, "keypoints", imageName.replace(".jpg", ".npz"))
    if os.path.exists(srcName):
        with np.load(srcName, allow_pickle=True) as kp:
            return {"pts": kp["pts"], "des": kp["des"]}
    else:
        quality = getQualityInfo(imageName)
        if quality["useInLookup"]:
            rfi = np.asarray(getRidgeFilteredImage(imageName))
            c = cv2.cornerHarris(rfi, 8, 3, 0.04)
            # Don't allow keypoints in locations where the receptive field of the
            # keypoints would extend outside the image
            blank = int(np.ceil(scale * 4.5))
            c[:blank, :] = 0
            c[-blank:, :] = 0
            c[:, :blank] = 0
            c[:, -blank:] = 0
            kernel = np.ones([7, 7], dtype=np.uint8)
            kernel[3, 3] = 0
            c2 = cv2.dilate(c, kernel)
            i, j = (c > c2).nonzero()
            kps = [
                cv2.KeyPoint(float(x), float(y), size=scale, angle=0)
                for y, x in zip(i, j)
            ]
            kps, desc = sift.compute(rfi, kps)
            kp_loc = np.asarray([kp.pt for kp in kps])
            with open(srcName, "wb") as f:
                np.savez(f, pts=kp_loc, des=desc)
            return {"pts": kp_loc, "des": desc}


def lookup(imageName, herd, tag=None):
    kp = getKeypoints(imageName)
    matches = herd["matcher"].knnMatch(kp["des"], k=1)
    animalVotes = [
        match.imgIdx
        for match, in matches
        if np.linalg.norm(
            kp["pts"][match.queryIdx, :] - herd["pts"][match.imgIdx][match.trainIdx]
        )
        < 150
    ]
    c, e = np.histogram(animalVotes, bins=np.arange(len(herd["tags"]) + 1))
    id = c.argsort()[::-1]
    return id, c[id]


def newHerd():
    return {
        "matcher": cv2.DescriptorMatcher_create(cv2.DESCRIPTOR_MATCHER_BRUTEFORCE),
        "des": [],
        "pts": [],
        "tags": [],
    }


def enroll(imageName, herd, tag):
    kp = getKeypoints(imageName)
    herd["des"].append(np.vstack(kp["des"]))
    herd["pts"].append(np.vstack(kp["pts"]))
    herd["matcher"].add([kp["des"]])
    herd["tags"].append(tag)


def AnimalByTag(herd, tag):
    try:
        return next(animal for animal in herd["tags"] if animal.Tag == tag)
    except StopIteration:
        return None


def AnimalByIndex(herd, index):
    return herd["tags"][index]
