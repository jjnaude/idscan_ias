#!/usr/bin/env python3

import connexion


def create_app():
    app = connexion.App(__name__, specification_dir="swagger/")
    app.add_api("idscan.yaml")
    return app
