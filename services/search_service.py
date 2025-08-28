"""
Search service module
Handles Elasticsearch operations for recipe search with flexible authentication
"""
import logging
import json
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch

from config import Config
from models.recipe import Recipe


class SearchService:
    """Service for search operations using Elasticsearch"""

    def __init__(self):
        self._client: Optional[Elasticsearch] = None
        self.logger = logging.getLogger(__name__)

    def _get_elasticsearch_credentials(self):
        """Get Elasticsearch credentials from Secret Manager with multiple auth methods"""
        if not Config.GOOGLE_CLOUD_PROJECT:
            self.logger.info(
                "No GOOGLE_CLOUD_PROJECT set, skipping Secret Manager")
            return None, None

        try:
            from google.cloud import secretmanager

            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{Config.GOOGLE_CLOUD_PROJECT}/secrets/elasticsearch-credentials/versions/latest"

            response = client.access_secret_version(request={"name": name})
            credentials = json.loads(response.payload.data.decode("UTF-8"))

            # Support different authentication methods
            if "api_key_id" in credentials and "api_key" in credentials:
                self.logger.info(
                    "Using API key authentication for Elasticsearch")
                return "api_key", (credentials["api_key_id"], credentials["api_key"])
            elif "api_key" in credentials:
                # Support single API key format (base64 encoded)
                self.logger.info(
                    "Using single API key authentication for Elasticsearch")
                return "api_key_single", credentials["api_key"]
            elif "username" in credentials and "password" in credentials:
                self.logger.info(
                    "Using basic auth authentication for Elasticsearch")
                return "basic_auth", (credentials["username"], credentials["password"])
            else:
                self.logger.warning(
                    "Elasticsearch credentials found but format not recognized")
                return None, None

        except Exception as e:
            self.logger.info(
                f"Could not get Elasticsearch credentials from Secret Manager: {e}")
            return None, None

    def get_client(self) -> Elasticsearch:
        """Get or create Elasticsearch client (singleton pattern) with flexible authentication"""
        if self._client is None:
            try:
                # Try to get credentials from Secret Manager first
                auth_type, credentials = self._get_elasticsearch_credentials()

                if auth_type == "api_key" and credentials:
                    # API key tuple format (id, key)
                    self._client = Elasticsearch(
                        [Config.ELASTICSEARCH_URL],
                        api_key=credentials
                    )
                    self.logger.info(
                        "Initialized Elasticsearch client with API key (tuple)")

                elif auth_type == "api_key_single" and credentials:
                    # Single API key format (base64 encoded)
                    self._client = Elasticsearch(
                        [Config.ELASTICSEARCH_URL],
                        api_key=credentials
                    )
                    self.logger.info(
                        "Initialized Elasticsearch client with API key (single)")

                elif auth_type == "basic_auth" and credentials:
                    # Basic auth with username/password
                    self._client = Elasticsearch(
                        [Config.ELASTICSEARCH_URL],
                        basic_auth=credentials
                    )
                    self.logger.info(
                        "Initialized Elasticsearch client with basic auth")

                elif Config.ELASTICSEARCH_USERNAME and Config.ELASTICSEARCH_PASSWORD:
                    # Fallback to environment variables
                    self._client = Elasticsearch(
                        [Config.ELASTICSEARCH_URL],
                        basic_auth=(Config.ELASTICSEARCH_USERNAME,
                                    Config.ELASTICSEARCH_PASSWORD)
                    )
                    self.logger.info(
                        "Initialized Elasticsearch client with environment variables")

                else:
                    # No authentication - try without credentials
                    self._client = Elasticsearch([Config.ELASTICSEARCH_URL])
                    self.logger.info(
                        "Initialized Elasticsearch client without authentication")

            except Exception as e:
                self.logger.error(
                    f"Failed to initialize Elasticsearch client: {e}")
                raise

        return self._client

    def is_available(self) -> bool:
        """Check if Elasticsearch is available"""
        try:
            client = self.get_client()
            result = client.ping()
            self.logger.info(f"Elasticsearch ping result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Elasticsearch availability check failed: {e}")
            return False

    def initialize_index(self) -> None:
        """Initialize the recipes index with proper mapping"""
        if not self.is_available():
            raise RuntimeError("Elasticsearch is not available")

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

        try:
            self.get_client().indices.create(
                index=Config.RECIPES_INDEX,
                body=mapping,
                ignore=400  # Ignore if index already exists
            )
            self.logger.info(f"Initialized index: {Config.RECIPES_INDEX}")
        except Exception as e:
            self.logger.error(f"Failed to initialize index: {e}")
            raise

    def index_recipe(self, recipe: Recipe) -> None:
        """Index a single recipe in Elasticsearch"""
        try:
            doc = recipe.to_search_document()
            self.get_client().index(
                index=Config.RECIPES_INDEX,
                id=recipe.id,
                document=doc
            )
            self.logger.debug(f"Indexed recipe: {recipe.id}")
        except Exception as e:
            self.logger.error(f"Failed to index recipe {recipe.id}: {e}")
            raise

    def remove_recipe(self, recipe_id: str) -> None:
        """Remove a recipe from Elasticsearch"""
        try:
            self.get_client().delete(
                index=Config.RECIPES_INDEX,
                id=recipe_id,
                ignore=[404]
            )
            self.logger.debug(f"Removed recipe from index: {recipe_id}")
        except Exception as e:
            self.logger.error(f"Failed to remove recipe {recipe_id}: {e}")
            raise

    def search_recipes(self, q: str = "", ingredients: str = "", limit: int = Config.DEFAULT_LIMIT) -> Optional[Dict[str, Any]]:
        """Search recipes with query and ingredient filters"""
        if not self.is_available():
            self.logger.warning("Elasticsearch is not available for search")
            return None

        # Ensure index exists
        try:
            if not self.get_client().indices.exists(index=Config.RECIPES_INDEX):
                self.logger.info("Creating recipes index...")
                self.initialize_index()
        except Exception as e:
            self.logger.error(f"Failed to check/create index: {e}")
            return None

        limit = Config.validate_limit(limit)

        # Build search query
        query = self._build_search_query(q, ingredients)

        try:
            self.logger.info(f"Executing search with query: {query}")

            response = self.get_client().search(
                index=Config.RECIPES_INDEX,
                query=query,
                size=limit,
                sort=[
                    {"_score": {"order": "desc"}},
                    {"createdAt": {"order": "desc"}}
                ]
            )

            total_hits = response["hits"]["total"]["value"]
            self.logger.info(f"Search returned {total_hits} results")

            # Convert hits to recipe objects
            items = []
            for hit in response["hits"]["hits"]:
                recipe = Recipe.from_elasticsearch_hit(hit)
                recipe_dict = recipe.to_dict()
                items.append(recipe_dict)

            return {
                "items": items,
                "total": total_hits,
                "query": q,
                "ingredients_filter": ingredients,
                "source": "elasticsearch"
            }

        except Exception as e:
            self.logger.error(f"Search query failed: {e}")
            raise

    def _build_search_query(self, q: str, ingredients: str) -> Dict[str, Any]:
        """Build Elasticsearch query based on search parameters"""
        if not q and not ingredients:
            return {"match_all": {}}

        must_clauses = []

        # Add text search clause
        if q:
            must_clauses.append({
                "multi_match": {
                    "query": q,
                    "fields": ["title^2", "ingredients^1.5", "steps", "searchable_text"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            })

        # Add ingredients filter clauses
        if ingredients:
            ingredient_list = [ing.strip().lower()
                               for ing in ingredients.split(",")]
            for ingredient in ingredient_list:
                must_clauses.append({
                    "match": {
                        "ingredients": {
                            "query": ingredient,
                            "fuzziness": "AUTO"
                        }
                    }
                })

        return {"bool": {"must": must_clauses}}
