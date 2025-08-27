import connexion
import logging
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    logging.info("Loaded environment variables from .env file")
except ImportError:
    logging.info("python-dotenv not installed, skipping .env file loading")

from connexion import NoContent
from google.cloud import firestore
from google.cloud import secretmanager
from elasticsearch import Elasticsearch

_passwords: Optional[Dict[str, str]] = None


def get_passwords() -> Dict[str, str]:
    """Retrieve passwords from Google Cloud Secret Manager"""
    global _passwords

    if _passwords is not None:
        return _passwords

    try:
        client = secretmanager.SecretManagerServiceClient()

        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        if not project_id:
            logging.warning(
                "GOOGLE_CLOUD_PROJECT not set, falling back to hardcoded passwords")
            _passwords = {"test": "test"}
            return _passwords

        logging.info(f"Using project ID: {project_id}")

        secret_name = f"projects/{project_id}/secrets/basic-auth/versions/latest"

        response = client.access_secret_version(request={"name": secret_name})

        secret_value = response.payload.data.decode("UTF-8")
        _passwords = json.loads(secret_value)

        logging.info("Successfully loaded passwords from Secret Manager")
        return _passwords

    except Exception as e:
        logging.error(f"Failed to load passwords from Secret Manager: {e}")
        _passwords = {"test": "test"}
        return _passwords


# Rest of your code remains the same...
def basic_auth(username, password):
    passwords = get_passwords()
    if passwords.get(username) == password:
        return {"sub": username}
    return None


_db: Optional[firestore.Client] = None


def db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


_es: Optional[Elasticsearch] = None


def es() -> Elasticsearch:
    global _es
    if _es is None:
        es_url = os.getenv('ELASTICSEARCH_URL', 'http://localhost:9200')
        es_username = os.getenv('ELASTICSEARCH_USERNAME')
        es_password = os.getenv('ELASTICSEARCH_PASSWORD')

        if es_username and es_password:
            _es = Elasticsearch(
                [es_url], basic_auth=(es_username, es_password))
        else:
            _es = Elasticsearch([es_url])
    return _es


RECIPES = "recipes"
RECIPES_INDEX = "recipes"


def root():
    return "Connected", 200


def health():
    return NoContent, 204


def _recipe_from_doc(doc: firestore.DocumentSnapshot) -> Dict[str, Any]:
    d = doc.to_dict() or {}
    d["id"] = doc.id
    for k in ("createdAt", "updatedAt"):
        if k in d and hasattr(d[k], "isoformat"):
            d[k] = d[k].isoformat()
    return d


def _index_recipe_in_elasticsearch(recipe: Dict[str, Any]):
    """Index a recipe in Elasticsearch for search"""
    try:
        doc = {
            "title": recipe.get("title", ""),
            "ingredients": recipe.get("ingredients", []),
            "steps": recipe.get("steps", []),
            "createdAt": recipe.get("createdAt"),
            "updatedAt": recipe.get("updatedAt"),
            "searchable_text": f"{recipe.get('title', '')} {' '.join(recipe.get('ingredients', []))} {' '.join(recipe.get('steps', []))}"
        }

        es().index(index=RECIPES_INDEX, id=recipe["id"], document=doc)
    except Exception as e:
        logging.error(
            f"Failed to index recipe {recipe.get('id')} in Elasticsearch: {e}")


def _remove_recipe_from_elasticsearch(recipe_id: str):
    """Remove a recipe from Elasticsearch"""
    try:
        es().delete(index=RECIPES_INDEX, id=recipe_id, ignore=[404])
    except Exception as e:
        logging.error(
            f"Failed to remove recipe {recipe_id} from Elasticsearch: {e}")


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


def search_recipes(q: str = "", ingredients: str = "", limit: int = 50):
    """Search recipes using Elasticsearch"""
    try:
        if not es().ping():
            logging.error("Elasticsearch is not available")
            return {
                "error": "Search service unavailable",
                "fallback": "Using basic listing",
                **list_recipes(limit)
            }

        if not es().indices.exists(index=RECIPES_INDEX):
            logging.info("Recipes index doesn't exist, creating it...")
            mapping = {
                "mappings": {
                    "properties": {
                        "title": {"type": "text", "analyzer": "standard"},
                        "ingredients": {"type": "text", "analyzer": "standard"},
                        "steps": {"type": "text", "analyzer": "standard"},
                        "searchable_text": {"type": "text", "analyzer": "standard"},
                        "createdAt": {"type": "date"},
                        "updatedAt": {"type": "date"}
                    }
                }
            }
            es().indices.create(index=RECIPES_INDEX, body=mapping)

            docs = db().collection(RECIPES).stream()
            indexed_count = 0
            for doc in docs:
                recipe = _recipe_from_doc(doc)
                _index_recipe_in_elasticsearch(recipe)
                indexed_count += 1
            logging.info(f"Auto-indexed {indexed_count} existing recipes")

        limit = max(1, min(200, int(limit)))

        query = {"bool": {"must": []}}

        if q:
            query["bool"]["must"].append({
                "multi_match": {
                    "query": q,
                    "fields": ["title^2", "ingredients^1.5", "steps", "searchable_text"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            })

        if ingredients:
            ingredient_list = [ing.strip().lower()
                               for ing in ingredients.split(",")]
            for ingredient in ingredient_list:
                query["bool"]["must"].append({
                    "match": {
                        "ingredients": {
                            "query": ingredient,
                            "fuzziness": "AUTO"
                        }
                    }
                })

        if not q and not ingredients:
            query = {"match_all": {}}

        logging.info(f"Executing search with query: {query}")

        response = es().search(
            index=RECIPES_INDEX,
            query=query,
            size=limit,
            sort=[{"_score": {"order": "desc"}},
                  {"createdAt": {"order": "desc"}}]
        )

        logging.info(
            f"Elasticsearch response: {response['hits']['total']['value']} results")

        items = []
        for hit in response["hits"]["hits"]:
            recipe = hit["_source"].copy()
            recipe["id"] = hit["_id"]
            recipe["_score"] = hit["_score"]
            recipe.pop("searchable_text", None)
            items.append(recipe)

        return {
            "items": items,
            "total": response["hits"]["total"]["value"],
            "query": q,
            "ingredients_filter": ingredients,
            "source": "elasticsearch"
        }

    except Exception as e:
        logging.error(f"Search failed: {e}")
        return {
            "error": f"Search failed: {str(e)}",
            "fallback": "Using basic listing",
            "source": "firestore_fallback",
            **list_recipes(limit)
        }


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
    recipe = _recipe_from_doc(doc)

    _index_recipe_in_elasticsearch(recipe)

    return recipe, 201


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
    recipe = _recipe_from_doc(ref.get())

    _index_recipe_in_elasticsearch(recipe)

    return recipe


def delete_recipe(id: str):
    ref = db().collection(RECIPES).document(id)
    if not ref.get().exists:
        return {"error": "Recipe not found"}, 404

    ref.delete()

    _remove_recipe_from_elasticsearch(id)

    return NoContent, 204


def reindex_all_recipes():
    try:
        mapping = {
            "mappings": {
                "properties": {
                    "title": {"type": "text", "analyzer": "standard"},
                    "ingredients": {"type": "text", "analyzer": "standard"},
                    "steps": {"type": "text", "analyzer": "standard"},
                    "searchable_text": {"type": "text", "analyzer": "standard"},
                    "createdAt": {"type": "date"},
                    "updatedAt": {"type": "date"}
                }
            }
        }

        es().indices.create(index=RECIPES_INDEX, body=mapping, ignore=400)

        docs = db().collection(RECIPES).stream()
        indexed_count = 0

        for doc in docs:
            recipe = _recipe_from_doc(doc)
            _index_recipe_in_elasticsearch(recipe)
            indexed_count += 1

        return {"message": f"Reindexed {indexed_count} recipes"}, 200

    except Exception as e:
        logging.error(f"Reindexing failed: {e}")
        return {"error": "Reindexing failed"}, 500


app = connexion.App(__name__, specification_dir='spec')
app.add_api('openapi.yaml', pythonic_params=True)

application = app.app

if __name__ == '__main__':
    app.run(port=8080)
