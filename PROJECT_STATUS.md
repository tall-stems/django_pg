# Project Status - Quick Reference

**Last Updated:** October 28, 2025
**Status:** Active Development
**Python:** 3.10.12 | **Django:** 5.2.7

---

## 🚀 Quick Start (After Being Away)

```bash
# 1. Activate environment
source venv/bin/activate  # or `activate` alias

# 2. Start services
docker compose up -d redis  # or `dcupd redis`

# 3. Run Django
python manage.py runserver  # Visit http://localhost:8000

# 4. Start Celery (if needed)
python manage.py start_worker
```

---

## 📱 What's Working

### Apps
- **Notes** - Full CRUD + REST API (`/api/notes/`)
- **Home** - Basic pages + user auth
- **Tasks** - Celery async processing (simplified)

### Services
- ✅ **Django** - Development server
- ✅ **PostgreSQL** - Docker (port 5432)
- ✅ **Redis** - Docker (port 6380)
- ✅ **Celery** - Async task worker

### Key URLs
- Admin: http://localhost:8000/admin/
- Notes API: http://localhost:8000/api/notes/
- Home: http://localhost:8000/

---

## 🔧 Common Tasks

### Development
```bash
# Migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run tests
pytest
pytest apps/notes/tests/ -v
pytest apps/tasks/test_tasks.py -v

# Shell
python manage.py shell
```

### Docker
```bash
# All services
docker compose up

# With Celery worker
docker compose --profile celery up

# Check status
docker compose ps
docker compose logs web
```

### Celery
```bash
# Run tasks
python manage.py run_task --user-id 1
python manage.py run_task --user-id 1 --sync
python manage.py run_task --user-id 1 --delete

# Check task status
python manage.py check_task <task-id>

# Start worker
python manage.py start_worker
celery -A playground worker --loglevel=info
```

---

## 📂 Key Files & Locations

### Configuration
- `playground/settings.py` - Django settings (uses .env)
- `playground/celery.py` - Celery configuration
- `docker-compose.yml` - Service definitions

### Apps
- `apps/notes/` - Notes CRUD + API
- `apps/tasks/` - Celery tasks (see `apps/tasks/README.md`)
- `apps/home/` - Home pages + auth

### Documentation
- `README.md` - Getting started guide
- `apps/tasks/README.md` - Celery guide

---

## 🎯 Recent Changes

### October 28, 2025
- ✅ Simplified Celery to 2 basic tasks (learning-focused)
- ✅ Added Docker Compose with PostgreSQL
- ✅ Configured environment variables properly
- ✅ Added security headers and HTTPS settings (production-ready)
- ✅ Created comprehensive documentation
- ✅ Cleaned up old files and dependencies
- ✅ Consolidated Celery docs into `apps/tasks/README.md`

### Archived (July 2024)
- Complex Celery tasks moved to `apps/tasks/backup_original/`
  - Email tasks, reports, media processing, API integration
  - Available as reference examples

---

## ⚠️ Important Notes

### Environment Setup
- **`.env`** - For local development (SQLite, localhost)
- **`.env.docker`** - For Docker (PostgreSQL, service names)
- Both are gitignored - use `.env.example` as template

### Database
- **Local:** SQLite (`db.sqlite3`)
- **Docker:** PostgreSQL (credentials in `.env.docker`)
- Migrations are shared between both

### Celery Tasks
- Simplified to 2 tasks: `create_note_task`, `delete_completed_notes`
- Complex examples in `apps/tasks/backup_original/`
- Full guide: `apps/tasks/README.md`

### Tests
- All passing: 8 Celery tests, Notes app tests
- Run with: `pytest` or `pytest -v`

---

## 🛠️ Troubleshooting

### Service Issues
```bash
# Redis not running?
docker compose up -d redis
nc -z localhost 6380  # Test connection

# PostgreSQL not connecting?
docker compose up -d db
docker compose logs db

# Celery worker not picking up tasks?
# Restart worker after code changes
python manage.py start_worker
```

### Common Errors
```bash
# Port already in use
# Check: lsof -i :8000
# Kill: kill -9 <PID>
```