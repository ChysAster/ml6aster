# Local Setup & Testing Guide

This guide explains how to run the project locally, set up Elasticsearch in Docker on `localhost:9200`, and test **all endpoints** with example data.

---

## 1) Prerequisites

- **Python 3.10+**
- **pip**
- **Docker**

> The API base path is `/api` as defined in the spec.

---

## 2) Install Python dependencies & run the app

```bash
# From the project root:
pip install -r requirements.txt

# Start the API
python app.py
```

The app should now be running locally (commonly on `http://localhost:8080`).

---

## 3) Run Elasticsearch in Docker (localhost:9200)

### Option A — one-liner (Docker run)

```bash
docker run --name recipes-es -p 9200:9200 -e discovery.type=single-node -e xpack.security.enabled=false docker.elastic.co/elasticsearch/elasticsearch:8.14.1
```

- Exposes **http://localhost:9200** to the host.

---

## 4) Authentication model

The API defines **HTTP Basic Auth** globally, with some public endpoints explicitly marked to **not require auth**. Specifically:

- Public (no auth): `GET /`, `GET /health`, `GET /recipes`, `GET /recipes/{id}`, `GET /recipes/search`.
- Protected (Basic Auth required): `POST /recipes`, `PUT /recipes/{id}`, `DELETE /recipes/{id}`, `POST /recipes/reindex`.

> If your server enforces Basic Auth, add `-u <username>:<password>` to protected calls (examples show both forms).

---

## 5) Base URL

All examples below assume the app is running on `http://localhost:8080` and the API is served under `/api` (e.g., `http://localhost:8080/api/...`).

You can adapt the host/port if your app binds differently.

---

## 6) Endpoints & example calls

### Root

**Spec**: `GET /` → 200 OK (root response) fileciteturn0file0

```bash
curl -i http://localhost:8080/api/
```

---

### Health

**Spec**: `GET /health` → 204 No Content (public) fileciteturn0file0

```bash
curl -i http://localhost:8080/api/health
```

---

### List recipes

**Spec**: `GET /recipes?limit={1..200}` (default 50, public) → 200 with `{ items: Recipe[] }` fileciteturn0file0

```bash
curl -s "http://localhost:8080/api/recipes?limit=50" | jq .
```

---

### Create recipe

**Spec**: `POST /recipes` (protected) with body `RecipeInput` → 201 with `Recipe` fileciteturn0file0

```bash
# Without auth (if your server allows it in local dev)
curl -i -H "Content-Type: application/json"   -d '{
    "title": "Classic Pancakes",
    "ingredients": ["flour", "milk", "eggs", "sugar", "baking powder", "salt"],
    "steps": [
      "Whisk dry ingredients.",
      "Add milk and eggs; whisk until smooth.",
      "Cook on a hot griddle until bubbles form; flip and finish."
    ]
  }'   http://localhost:8080/api/recipes

# With Basic Auth
curl -i -u admin:admin -H "Content-Type: application/json"   -d '{
    "title": "Tomato Basil Soup",
    "ingredients": ["tomatoes", "onion", "garlic", "basil", "olive oil", "salt", "pepper"],
    "steps": [
      "Sauté onion and garlic in olive oil.",
      "Add tomatoes and simmer.",
      "Blend smooth; season and finish with basil."
    ]
  }'   http://localhost:8080/api/recipes
```

**Recipe schema** (response): fields include `id`, `title`, `ingredients[]`, `steps[]`, `createdAt`, `updatedAt` (required: `id`, `title`). **RecipeInput** (request): `title` (required), optional `ingredients[]`, `steps[]`. fileciteturn0file0

---

### Get a recipe by id

**Spec**: `GET /recipes/{id}` (public) → 200 with `Recipe` or 404 if not found fileciteturn0file0

```bash
RECIPE_ID="<paste-from-create-response>"
curl -s http://localhost:8080/api/recipes/$RECIPE_ID | jq .
```

---

### Update a recipe

**Spec**: `PUT /recipes/{id}` (protected) with body `RecipeInput` → 200 with `Recipe` (or 400/404) fileciteturn0file0

```bash
curl -i -u admin:admin -H "Content-Type: application/json"   -X PUT   -d '{
    "title": "Classic Pancakes (Buttermilk)",
    "ingredients": ["flour", "buttermilk", "eggs", "sugar", "baking powder", "salt"],
    "steps": [
      "Whisk dry ingredients.",
      "Add buttermilk and eggs; whisk until smooth.",
      "Cook on a hot griddle; flip when bubbles form."
    ]
  }'   http://localhost:8080/api/recipes/$RECIPE_ID
```

---

### Delete a recipe

**Spec**: `DELETE /recipes/{id}` (protected) → 204 or 404 fileciteturn0file0

```bash
curl -i -u admin:admin -X DELETE http://localhost:8080/api/recipes/$RECIPE_ID
```

---

### Search recipes (Elasticsearch-backed)

**Spec**: `GET /recipes/search` (public) with query params:

- `q` — free-text over title/ingredients/steps (default `""`)
- `ingredients` — comma-separated list (default `""`)
- `limit` — 1..200 (default 50)

Returns `{ items: (Recipe & {_score})[], total, query, ingredients_filter }`. fileciteturn0file0

```bash
# Simple text search
curl -s "http://localhost:8080/api/recipes/search?q=soup&limit=10" | jq .

# Filter by ingredients (comma-separated)
curl -s "http://localhost:8080/api/recipes/search?ingredients=tomatoes,basil" | jq .
```

---

### Reindex all recipes (into Elasticsearch)

**Spec**: `POST /recipes/reindex` (protected) → 200 `{ "message": "..." }` or 500 `{ "error": "..." }`. fileciteturn0file0

```bash
curl -s -u admin:admin -X POST http://localhost:8080/api/recipes/reindex | jq .
```

> Run this after creating/editing recipes to refresh the search index.

---

## 7) Quick start script (optional)

Use this snippet to **seed data** and **reindex** quickly:

```bash
# 1) Create example recipes
curl -s -u admin:admin -H "Content-Type: application/json"   -d '{"title":"Avocado Toast","ingredients":["bread","avocado","lemon","salt","pepper"],"steps":["Toast bread","Mash avocado with lemon and salt","Spread and finish with pepper"]}'   http://localhost:8080/api/recipes > /dev/null

curl -s -u admin:admin -H "Content-Type: application/json"   -d '{"title":"Garlic Butter Shrimp","ingredients":["shrimp","garlic","butter","parsley","salt","pepper"],"steps":["Melt butter and sauté garlic","Add shrimp and cook until pink","Finish with parsley"]}'   http://localhost:8080/api/recipes > /dev/null

curl -s -u admin:admin -H "Content-Type: application/json"   -d '{"title":"Tomato Basil Soup","ingredients":["tomatoes","onion","garlic","basil","olive oil","salt","pepper"],"steps":["Sauté aromatics","Simmer tomatoes","Blend and season"]}'   http://localhost:8080/api/recipes > /dev/null

# 2) Reindex for search
curl -s -u admin:admin -X POST http://localhost:8080/api/recipes/reindex | jq .

# 3) Try a search
curl -s "http://localhost:8080/api/recipes/search?q=tomato&ingredients=basil" | jq .
```

---

## 8) Troubleshooting

- **Elasticsearch connection errors**: ensure the container is up and responding at `http://localhost:9200`.
- **Auth failures** on protected routes: add `-u <username>:<password>` or adjust your local auth config if you’ve disabled it for dev.
- **CORS**: if calling from a browser app, verify the server’s CORS config.
- **Port conflicts**: change either your API port or ES port mapping if those ports are in use.

---

## 9) Data models (from OpenAPI)

```yaml
Recipe:
  type: object
  properties:
    id: string
    title: string
    ingredients: string[]
    steps: string[]
    createdAt: date-time
    updatedAt: date-time
  required: [id, title]

RecipeInput:
  type: object
  properties:
    title: string
    ingredients: string[]
    steps: string[]
  required: [title]
```
