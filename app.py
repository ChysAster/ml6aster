"""
Recipe API - Main application module
Handles HTTP endpoints and request/response logic
"""
import connexion
import logging
from typing import Any, Dict
from connexion import NoContent

from services.recipe_service import RecipeService
from services.auth_service import AuthService
from config import Config


def create_app():
    """Application factory pattern"""
    app = connexion.App(__name__, specification_dir='spec')
    app.add_api('openapi.yaml', pythonic_params=True)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    return app


# Initialize services
auth_service = AuthService()
recipe_service = RecipeService()


def basic_auth(username: str, password: str):
    """Basic authentication handler"""
    return auth_service.authenticate(username, password)


def root():
    """Root endpoint"""
    return "Connected", 200


def health():
    """Health check endpoint"""
    return NoContent, 204


def list_recipes(limit: int = 50):
    """List recipes with pagination"""
    try:
        return recipe_service.list_recipes(limit)
    except Exception as e:
        logging.error(f"Failed to list recipes: {e}")
        return {"error": "Failed to retrieve recipes"}, 500


def search_recipes(q: str = "", ingredients: str = "", limit: int = 50):
    """Search recipes using Elasticsearch"""
    try:
        return recipe_service.search_recipes(q, ingredients, limit)
    except Exception as e:
        logging.error(f"Search failed: {e}")
        return {"error": "Search service unavailable"}, 500


def create_recipe(body: Dict[str, Any]):
    """Create a new recipe"""
    try:
        recipe = recipe_service.create_recipe(body)
        return recipe, 201
    except ValueError as e:
        return {"error": str(e)}, 400
    except Exception as e:
        logging.error(f"Failed to create recipe: {e}")
        return {"error": "Failed to create recipe"}, 500


def get_recipe(id: str):
    """Get a specific recipe by ID"""
    try:
        recipe = recipe_service.get_recipe(id)
        if not recipe:
            return {"error": "Recipe not found"}, 404
        return recipe
    except Exception as e:
        logging.error(f"Failed to get recipe {id}: {e}")
        return {"error": "Failed to retrieve recipe"}, 500


def update_recipe(id: str, body: Dict[str, Any]):
    """Update an existing recipe"""
    try:
        recipe = recipe_service.update_recipe(id, body)
        if not recipe:
            return {"error": "Recipe not found"}, 404
        return recipe
    except ValueError as e:
        return {"error": str(e)}, 400
    except Exception as e:
        logging.error(f"Failed to update recipe {id}: {e}")
        return {"error": "Failed to update recipe"}, 500


def delete_recipe(id: str):
    """Delete a recipe"""
    try:
        if not recipe_service.delete_recipe(id):
            return {"error": "Recipe not found"}, 404
        return NoContent, 204
    except Exception as e:
        logging.error(f"Failed to delete recipe {id}: {e}")
        return {"error": "Failed to delete recipe"}, 500


def reindex_all_recipes():
    """Reindex all recipes in Elasticsearch"""
    try:
        result = recipe_service.reindex_all_recipes()
        return result, 200
    except Exception as e:
        logging.error(f"Reindexing failed: {e}")
        return {"error": "Reindexing failed"}, 500


app = create_app()
application = app.app

if __name__ == '__main__':
    app.run(port=Config.PORT)
