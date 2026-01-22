# AI Coding Instructions - Django Playground

## Project Overview

This is a Django 5.2.7 experimental playground designed for **modular exploration** of backend concepts and patterns. The project uses a **custom app-based architecture** where all business logic lives in the `apps/` directory, making it easy to add, test, and iterate on different Django features independently.

## Architecture Patterns

### Custom App Structure
- **All apps live in `apps/` directory** - configured in `settings.py` with `sys.path.insert(0, APPS_DIR)`
- **Import directly by app name** - use `from <app>.models import <Model>`, not `from apps.<app>.models import <Model>`
- **Dual URL patterns** - each app has separate web views (`urls.py`) and API endpoints (`api_urls.py`)

### Key Apps & Their Responsibilities
- **`home/`** - Authentication, landing pages, basic views
- **`notes/`** - Core CRUD with both web views and REST API (`/api/v1/notes/`)
- **`tasks/`** - Celery async task processing (simplified, production-ready)

### Service Integration
```
Django View → Celery Task → Redis Queue → Worker → Database
     ↓                           ↓
  REST API              Background Processing
```

## Development Workflows

### Startup Commands (Run First)
```bash
# Environment setup (uses venv/)
source venv/bin/activate  # or alias: activate

# Services (via Docker)
docker compose up -d db    # Required for database connections (including tests)
docker compose up -d redis # Required for Celery - can ignore if not dealing with async tasks
```

### Essential Commands
```bash
# Development server
python manage.py runserver  # http://localhost:8000

# Celery worker (custom management command)
python manage.py start_worker --loglevel debug

# Database operations
python manage.py migrate
python manage.py makemigrations

# Testing
pytest
```

### Testing Patterns
- **pytest + factory_boy** - if tests need factories, create or modify them in `/<app>/tests/factories.py`
- **Fixtures with authentication** - use `logged_user` fixture pattern
- **Database isolation** - `@pytest.mark.django_db` on all database tests

## Project-Specific Conventions

### API Development
- **Dual API structure** - `/<app>/` for web, `/api/v1/<app>/` for REST
- **Custom pagination** - app-specific pagination with `default_limit=10, max_limit=100`
- **Built-in filtering** - `DjangoFilterBackend` + `SearchFilter` on relevant fields

### Celery Tasks
- **Shared tasks pattern** - use `@shared_task` decorator, never bind to app instance
- **Type hints required** - all tasks use `typing.Dict[str, Any]` return patterns
- **Custom management commands** - `start_worker.py` provides dev-friendly worker startup

### Database
- **User-centric models** - all models relate to Django's `User` with `related_name`
- **Simple timestamp pattern** - `date_created = DateTimeField(auto_now_add=True)`

## Critical Integration Points

### Celery Configuration (`playground/celery.py`)
- **Redis backend** - both broker and result store on port 6380 (custom)
- **Auto-discovery** - tasks auto-loaded from all registered Django apps
- **Namespace pattern** - settings prefixed with `CELERY_`

### Settings Structure
- **Environment-based** - `.env` file with `dotenv` loading
- **Database URL pattern** - uses `dj_database_url` for PostgreSQL config
- **CORS enabled** - configured for frontend development on port 5173

## Key Files to Reference

- [playground/settings.py](playground/settings.py) - Custom apps directory setup
- [apps/tasks/tasks.py](apps/tasks/tasks.py) - Celery task patterns
- [apps/tasks/management/commands/start_worker.py](apps/tasks/management/commands/start_worker.py) - Development Celery workflow
- [apps/notes/api_views.py](apps/notes/api_views.py) - REST API patterns with filtering/pagination (example)
- [apps/notes/tests/factories.py](apps/notes/tests/factories.py) - Test data factory patterns (example)

## Quick Start for New Features

1. **New app**: Create in `apps/`, add to `INSTALLED_APPS`, create `urls.py` and/or `api_urls.py` as needed
2. **New API endpoint**: Use DRF views with pagination/filtering when appropriate (see existing app examples)
3. **New async task**: Use `@shared_task` with type hints, test with `python manage.py check_task`
4. **New model**: Consider user relationships and timestamps based on your feature needs
5. **New tests**: Create factory in `/apps/<app_name>/tests/factories.py`, use `@pytest.mark.django_db`