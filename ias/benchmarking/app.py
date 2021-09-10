import datetime
import glob
import os

import muzzleMatching
from flask import Flask, redirect, render_template, request, url_for
from muzzleMatching import *

files = glob.glob("/workspaces/ias/data/IDScanPhotos_*.xlsx")
files.sort()
file = files[-1]
print(f"Latest IDScanPhotos file appears to be : {file}")
df = pd.read_excel(file, header=2)
print(f"It has {len(df)} entries, of which {df.Url.count()} have valid URLs associated")
# Drop all images that don't have URLs
df = df[df["Url"] > ""]
# And set the fileName column to be the index.
df = df.set_index("FileName")
# Now some cleanup lines to sort out shit in the DB. This should not be required
# in production, but some animals were enrolled twice and in some of these cases
# the tag was entered inconsistently. So until such time as Silverbridge cleans
# this up in the database or we switch to a clean production database where
# identity is checked against the db before an animal is allowed to be enrolled,
# I have to do this.

# Normalise all tags to be uppercase
df.Tag = df.Tag.transform(lambda x: str(x).upper())
# Now load the list of  manual changes to the dataframe
dfPatch = pd.read_excel("/workspaces/ias/data/patchlist.xlsx")
# And set the fileName column to be the index.
dfPatch = dfPatch.set_index("FileName")
# and monkeypatch
df.update(dfPatch)
# Add a clean column that we
df["useInLookup"] = [pd.NA for i in range(len(df))]
df["useAsTemplate"] = [pd.NA for i in range(len(df))]
for index, row in df.iterrows():
    try:
        q = getQualityInfo(index)
        df.loc[index, "useInLookup"] = q["useInLookup"]
        df.loc[index, "useAsTemplate"] = q["useAsTemplate"]
    except UnidentifiedImageError:
        df.loc[index, "useInLookup"] = False
        df.loc[index, "useAsTemplate"] = False
        print(f"Could not parse {index}")

tags = df.Tag.unique()
print(f"It contains {tags.size} unique animals (with at least one image).")
print(
    f"{df.useAsTemplate.sum()} of the images have been marked as usable as templates."
)
print(
    f"{df.useInLookup.sum()} of the images have been marked as potentially usable in lookups."
)
# # Filter out unuseable images.
df = df[df.useInLookup]
tags = df.Tag.unique()
print(
    f"Once the unusable images have been removed, we are left with {tags.size} unique animals."
)
df["session"] = [0 for i in range(len(df))]
for tag in tags:
    prev = None
    sessions = 1
    delta = 0
    for index, row in df[df.Tag == tag].sort_values(["CreatedDate"]).iterrows():
        timestamp = row.CreatedDate
        if prev:
            delta = timestamp - prev
            assert delta.total_seconds() >= 0
            if delta.total_seconds() > 3600:
                sessions += 1
            df.loc[index, "session"] = sessions - 1
        prev = timestamp
print(
    f"Of these {len(df[df.session>0].Tag.unique())} tags are seen in more than one session"
)

destFolder = "/workspaces/ias/data/PipelineDebug"
herd = newHerd()
for tag in tags:
    for index, row in df[(df.Tag == tag) & (df.useAsTemplate)].iterrows():
        enroll(index, herd, row)
        break

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/", methods=["POST"])
def upload_file():
    uploaded_file = request.files["file"]
    if uploaded_file.filename != "":
        uploaded_file.save(
            "/workspaces/ias/data/PipelineDebug/original/" + uploaded_file.filename
        )
        matchIndexes, counts = lookup(uploaded_file.filename, herd)
        match = AnimalByIndex(herd, matchIndexes[0])
        print(match.Tag)
    return redirect(url_for("index"))
