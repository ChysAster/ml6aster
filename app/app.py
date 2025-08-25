import connexion
import datetime
import logging

from connexion import NoContent

PASSWD = {"test": "test"}


def basic_auth(username, password):
    if PASSWD.get(username) == password:
        return {"sub": username}
    return None


def root():
    return "Connected", 200


def health():
    return NoContent, 204


app = connexion.App(
    __name__,
    specification_dir='spec'
)
app.add_api('openapi.yaml', pythonic_params=True)

application = app.app

if __name__ == '__main__':
    app.run(port=8080)
