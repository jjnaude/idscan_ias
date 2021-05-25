#!/usr/bin/env python3
from ias.swagger_server import create_app

app = create_app()
app.run(port=8080)

# import connexion
# from swagger_server import encoder


# def main():
#     app = connexion.App(__name__, specification_dir='./swagger/')
#     app.app.json_encoder = encoder.JSONEncoder
#     app.add_api('swagger.yaml', arguments={'title': 'ID-Scan Image Analysis API'}, pythonic_params=True)
#     app.run(debug=True,port=8080)


# if __name__ == '__main__':
#     main()
