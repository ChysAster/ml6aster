"""
Recipe service module
Handles all recipe-related business logic
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from google.cloud import firestore
from elasticsearch import Elasticsearch

from config import Config
from models.recipe import Recipe, RecipeInput
from services.database_service import DatabaseService
from services.search_service import SearchService


class RecipeService:
    """Service for recipe operations"""

    def __init__(self):
        self.db = DatabaseService()
        self.search = SearchService()
        self.logger = logging.getLogger(__name__)

    def list_recipes(self, limit: int = Config.DEFAULT_LIMIT) -> Dict[str, List[Dict[str, Any]]]:
        """List recipes with pagination"""
        limit = Config.validate_limit(limit)

        docs = (
            self.db.get_client()
            .collection(Config.RECIPES_COLLECTION)
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )

        items = [Recipe.from_firestore_doc(doc).to_dict() for doc in docs]
        return {"items": items}

    def search_recipes(self, q: str = "", ingredients: str = "", limit: int = Config.DEFAULT_LIMIT) -> Dict[str, Any]:
        """Search recipes using Elasticsearch with fallback to list"""
        limit = Config.validate_limit(limit)

        try:
            results = self.search.search_recipes(q, ingredients, limit)
            if results:
                return results
        except Exception as e:
            self.logger.error(f"Search failed, falling back to list: {e}")

        # Fallback to basic listing
        fallback_results = self.list_recipes(limit)
        fallback_results.update({
            "error": "Search service unavailable",
            "fallback": "Using basic listing",
            "source": "firestore_fallback",
            "query": q,
            "ingredients_filter": ingredients,
            "total": len(fallback_results["items"])
        })
        return fallback_results

    def create_recipe(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new recipe"""
        recipe_input = RecipeInput.from_dict(data)

        now = datetime.now(timezone.utc)
        recipe_data = {
            "title": recipe_input.title,
            "ingredients": recipe_input.ingredients,
            "steps": recipe_input.steps,
            "createdAt": now,
            "updatedAt": now,
        }

        # Save to Firestore
        ref = self.db.get_client().collection(Config.RECIPES_COLLECTION).document()
        ref.set(recipe_data)

        # Get the created document
        doc = ref.get()
        recipe = Recipe.from_firestore_doc(doc)

        # Index in Elasticsearch
        try:
            self.search.index_recipe(recipe)
        except Exception as e:
            self.logger.error(f"Failed to index recipe in search: {e}")

        return recipe.to_dict()

    def get_recipe(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """Get a recipe by ID"""
        doc = self.db.get_client().collection(
            Config.RECIPES_COLLECTION).document(recipe_id).get()

        if not doc.exists:
            return None

        recipe = Recipe.from_firestore_doc(doc)
        return recipe.to_dict()

    def update_recipe(self, recipe_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing recipe"""
        ref = self.db.get_client().collection(
            Config.RECIPES_COLLECTION).document(recipe_id)

        if not ref.get().exists:
            return None

        # Validate and filter updates
        updates = {}
        for field in ("title", "ingredients", "steps"):
            if field in data:
                updates[field] = data[field]

        if not updates:
            raise ValueError("Nothing to update")

        # Add timestamp
        updates["updatedAt"] = datetime.now(timezone.utc)

        # Update in Firestore
        ref.update(updates)

        # Get updated document
        recipe = Recipe.from_firestore_doc(ref.get())

        # Update in Elasticsearch
        try:
            self.search.index_recipe(recipe)
        except Exception as e:
            self.logger.error(f"Failed to update recipe in search: {e}")

        return recipe.to_dict()

    def delete_recipe(self, recipe_id: str) -> bool:
        """Delete a recipe"""
        ref = self.db.get_client().collection(
            Config.RECIPES_COLLECTION).document(recipe_id)

        if not ref.get().exists:
            return False

        # Delete from Firestore
        ref.delete()

        # Remove from Elasticsearch
        try:
            self.search.remove_recipe(recipe_id)
        except Exception as e:
            self.logger.error(f"Failed to remove recipe from search: {e}")

        return True

    def reindex_all_recipes(self) -> Dict[str, str]:
        """Reindex all recipes in Elasticsearch"""
        try:
            # Initialize search index
            self.search.initialize_index()

            # Get all recipes from Firestore
            docs = self.db.get_client().collection(Config.RECIPES_COLLECTION).stream()

            indexed_count = 0
            for doc in docs:
                recipe = Recipe.from_firestore_doc(doc)
                self.search.index_recipe(recipe)
                indexed_count += 1

            return {"message": f"Reindexed {indexed_count} recipes"}

        except Exception as e:
            self.logger.error(f"Reindexing failed: {e}")
            raise
