import connexion
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from connexion import NoContent
from google.cloud import firestore

PASSWD = {"test": "test"}


def basic_auth(username, password):
    if PASSWD.get(username) == password:
        return {"sub": username}
    return None


# Firestore setup
_db: Optional[firestore.Client] = None


def db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


def root():
    return "Connected", 200


def health():
    return NoContent, 204


RECIPES = "recipes"


def _recipe_from_doc(doc: firestore.DocumentSnapshot) -> Dict[str, Any]:
    d = doc.to_dict() or {}
    d["id"] = doc.id
    for k in ("createdAt", "updatedAt"):
        if k in d and hasattr(d[k], "isoformat"):
            d[k] = d[k].isoformat()
    return d


def list_recipes(limit: int = 50):
    limit = max(1, min(200, int(limit)))
    docs = (
        db()
        .collection(RECIPES)
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    items = [_recipe_from_doc(d) for d in docs]
    return {"items": items}


def create_recipe(body: Dict[str, Any]):
    now = datetime.now(timezone.utc)
    data = {
        "title": body.get("title", "").strip(),
        "ingredients": body.get("ingredients", []),
        "steps": body.get("steps", []),
        "createdAt": now,
        "updatedAt": now,
    }
    if not data["title"]:
        return {"error": "'title' is required"}, 400
    ref = db().collection(RECIPES).document()
    ref.set(data)
    doc = ref.get()
    return _recipe_from_doc(doc), 201


def get_recipe(id: str):
    doc = db().collection(RECIPES).document(id).get()
    if not doc.exists:
        return {"error": "Recipe not found"}, 404
    return _recipe_from_doc(doc)


def update_recipe(id: str, body: Dict[str, Any]):
    ref = db().collection(RECIPES).document(id)
    if not ref.get().exists:
        return {"error": "Recipe not found"}, 404
    updates: Dict[str, Any] = {}
    for k in ("title", "ingredients", "steps"):
        if k in body:
            updates[k] = body[k]
    if not updates:
        return {"error": "Nothing to update"}, 400
    updates["updatedAt"] = datetime.now(timezone.utc)
    ref.update(updates)
    return _recipe_from_doc(ref.get())


def delete_recipe(id: str):
    ref = db().collection(RECIPES).document(id)
    if not ref.get().exists:
        return {"error": "Recipe not found"}, 404
    ref.delete()
    return NoContent, 204


app = connexion.App(
    __name__,
    specification_dir='spec'
)
app.add_api('openapi.yaml', pythonic_params=True)

application = app.app

if __name__ == '__main__':
    app.run(port=8080)
