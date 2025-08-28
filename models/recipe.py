"""
Recipe data models
Defines the structure and validation for recipe data
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.cloud import firestore


@dataclass
class RecipeInput:
    """Input model for creating/updating recipes"""
    title: str
    ingredients: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RecipeInput':
        """Create RecipeInput from dictionary with validation"""
        title = data.get("title", "").strip()
        if not title:
            raise ValueError("'title' is required and cannot be empty")

        return cls(
            title=title,
            ingredients=data.get("ingredients", []),
            steps=data.get("steps", [])
        )


@dataclass
class Recipe:
    """Complete recipe model"""
    id: str
    title: str
    ingredients: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    score: Optional[float] = None  # For search results

    @classmethod
    def from_firestore_doc(cls, doc: firestore.DocumentSnapshot) -> 'Recipe':
        """Create Recipe from Firestore document"""
        data = doc.to_dict() or {}

        return cls(
            id=doc.id,
            title=data.get("title", ""),
            ingredients=data.get("ingredients", []),
            steps=data.get("steps", []),
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt")
        )

    @classmethod
    def from_elasticsearch_hit(cls, hit: Dict[str, Any]) -> 'Recipe':
        """Create Recipe from Elasticsearch hit"""
        source = hit["_source"]

        return cls(
            id=hit["_id"],
            title=source.get("title", ""),
            ingredients=source.get("ingredients", []),
            steps=source.get("steps", []),
            created_at=source.get("createdAt"),
            updated_at=source.get("updatedAt"),
            score=hit.get("_score")
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert Recipe to dictionary for JSON serialization"""
        result = {
            "id": self.id,
            "title": self.title,
            "ingredients": self.ingredients,
            "steps": self.steps
        }

        # Convert datetime objects to ISO format strings
        if self.created_at:
            result["createdAt"] = (
                self.created_at.isoformat()
                if hasattr(self.created_at, 'isoformat')
                else self.created_at
            )

        if self.updated_at:
            result["updatedAt"] = (
                self.updated_at.isoformat()
                if hasattr(self.updated_at, 'isoformat')
                else self.updated_at
            )

        # Include search score if present
        if self.score is not None:
            result["_score"] = self.score

        return result

    def to_search_document(self) -> Dict[str, Any]:
        """Convert Recipe to Elasticsearch document format"""
        searchable_text = f"{self.title} {' '.join(self.ingredients)} {' '.join(self.steps)}"

        return {
            "title": self.title,
            "ingredients": self.ingredients,
            "steps": self.steps,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "searchable_text": searchable_text
        }
