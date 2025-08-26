# Greeting + Recipes API — Routes & Usage

This document describes all available routes, authentication, request/response formats, and example calls for the **Recipes API**.

## Base URL

All routes are served under:

```
https://recipe-app-386608517597.europe-west1.run.app/api
```

## Authentication

- **Scheme:** HTTP Basic Auth  
- **Where required:** Enabled globally; endpoints can override this and be public.

### Public (no auth) endpoints
- `GET /health`  
- `GET /recipes`  
- `GET /recipes/search`  
- `GET /recipes/{id}`  

### Auth-required endpoints
- `GET /`  
- `POST /recipes`  
- `PUT /recipes/{id}`  
- `DELETE /recipes/{id}`  
- `POST /recipes/reindex`  

## Schemas

### `Recipe`
```json
{
  "id": "string",
  "title": "string",
  "ingredients": ["string"],
  "steps": ["string"],
  "createdAt": "date-time",
  "updatedAt": "date-time"
}
```

### `RecipeInput`
```json
{
  "title": "string",
  "ingredients": ["string"],
  "steps": ["string"]
}
```

---

## Endpoints

### `GET /` — Root
**Response**
- `200 OK`: Root response (no body schema specified).

**Example**
```bash
curl -u user:pass https://recipe-app-386608517597.europe-west1.run.app/api/
```

---

### `GET /health` — Health Check
**Auth:** None  
**Response**
- `204 No Content`: OK.

**Example**
```bash
curl -i https://recipe-app-386608517597.europe-west1.run.app/api/health
```

---

### `GET /recipes` — List Recipes
**Auth:** None  
**Query params**
- `limit` (integer, min:1, max:200, default:50) — Max number of items to return.

**Response**
- `200 OK` with body:
```json
{
  "items": [ { /* Recipe */ } ]
}
```

**Example**
```bash
curl "https://recipe-app-386608517597.europe-west1.run.app/api/recipes?limit=25"
```

---

### `POST /recipes` — Create Recipe
**Auth:** Basic  
**Request body:** `RecipeInput` (JSON). Required.  
**Responses**
- `201 Created` with `Recipe` in body  
- `400 Bad Request` on validation errors.

**Example**
```bash
curl -u user:pass -X POST https://recipe-app-386608517597.europe-west1.run.app/api/recipes   -H "Content-Type: application/json"   -d '{
    "title": "Pasta Primavera",
    "ingredients": ["pasta","vegetables","olive oil","garlic"],
    "steps": ["Boil pasta","Sauté veg","Combine"]
  }'
```

---

### `GET /recipes/search` — Search Recipes
**Auth:** None  
**Query params**
- `q` (string, default: `""`) — Full-text search over title, ingredients, or steps  
- `ingredients` (string, default: `""`) — Comma-separated list to filter by ingredients  
- `limit` (integer, min:1, max:200, default:50) — Result size.

**Response**
- `200 OK` with body:
```json
{
  "items": [
    {
      /* Recipe fields... */,
      "_score": 0.87
    }
  ],
  "total": 123,
  "query": "your query",
  "ingredients_filter": "tomato,garlic"
}
```

**Example**
```bash
curl "https://recipe-app-386608517597.europe-west1.run.app/api/recipes/search?q=pasta&ingredients=tomato,garlic&limit=10"
```

---

### `POST /recipes/reindex` — Reindex All Recipes
**Auth:** Basic  
**Description:** Reindex all recipes in Elasticsearch.  
**Responses**
- `200 OK` with `{ "message": "..." }`  
- `500 Internal Server Error` with `{ "error": "..." }`.

**Example**
```bash
curl -u user:pass -X POST https://recipe-app-386608517597.europe-west1.run.app/api/recipes/reindex
```

---

### `GET /recipes/{id}` — Get Recipe by ID
**Auth:** None  
**Path params**
- `id` (string, required) — Recipe identifier.

**Responses**
- `200 OK` with `Recipe`  
- `404 Not Found`.

**Example**
```bash
curl https://recipe-app-386608517597.europe-west1.run.app/api/recipes/abc123
```

---

### `PUT /recipes/{id}` — Update Recipe
**Auth:** Basic  
**Path params**
- `id` (string, required)  
**Request body:** `RecipeInput` (JSON). Required.  
**Responses**
- `200 OK` with updated `Recipe`  
- `400 Bad Request`  
- `404 Not Found`.

**Example**
```bash
curl -u user:pass -X PUT https://recipe-app-386608517597.europe-west1.run.app/api/recipes/abc123   -H "Content-Type: application/json"   -d '{
    "title": "Pasta Primavera (updated)",
    "ingredients": ["pasta","veg","olive oil","garlic","basil"],
    "steps": ["Boil pasta","Sauté veg","Combine","Garnish with basil"]
  }'
```

---

### `DELETE /recipes/{id}` — Delete Recipe
**Auth:** Basic  
**Path params**
- `id` (string, required)  
**Responses**
- `204 No Content`  
- `404 Not Found`.

**Example**
```bash
curl -u user:pass -X DELETE https://recipe-app-386608517597.europe-west1.run.app/api/recipes/abc123 -i
```

---

## Status Codes Overview
- `200 OK` — Successful GET/PUT/POST (non-create)  
- `201 Created` — Successfully created resource  
- `204 No Content` — Health check OK; successful delete  
- `400 Bad Request` — Invalid input  
- `404 Not Found` — Resource doesn’t exist  
- `500 Internal Server Error` — Reindexing failure

## Notes
- Numeric query constraints like `limit` (min:1, max:200) are enforced by the API.  
- Timestamp fields use ISO 8601 `date-time` format.
