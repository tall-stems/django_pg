# Django Playground

A personal playground project for experimenting with Django and Python web backend development.

## What Is This?

This is a learning and testing environment for exploring:
- Django web framework fundamentals
- RESTful API development with Django REST Framework
- Asynchronous task processing with Celery
- Docker containerization
- PostgreSQL database integration
- Redis caching and message queuing

## Tech Stack

- **Django 5.2.7** - Web framework
- **Python 3.10** - Programming language
- **PostgreSQL** - Database (Docker)
- **Redis** - Cache and Celery broker (Docker)
- **Celery** - Async task queue
- **Docker** - Containerization

## Quick Start

### Local Development (Recommended)

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment file
cp .env.example .env

# 4. Start Redis
docker compose up -d redis

# 5. Run migrations
python manage.py migrate

# 6. Create superuser
python manage.py createsuperuser

# 7. Start Django
python manage.py runserver
```

Visit http://localhost:8000

### Docker Development

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start all services
docker compose up --build

# 3. Run migrations (in another terminal)
docker compose exec web python manage.py migrate

# 4. Create superuser
docker compose exec web python manage.py createsuperuser
```

Visit http://localhost:8000

## Project Structure

```
django_pg/
├── apps/
│   ├── home/          # Home page and user auth
│   ├── notes/         # Notes app with REST API
│   └── tasks/         # Celery async tasks
├── playground/        # Django settings and config
├── static/            # CSS, images, templates
├── media/             # User uploads
└── docker-compose.yml # Docker services
```

## Apps Included

### Notes App
- CRUD operations for notes
- REST API endpoints
- User authentication
- Completed/incomplete status

### Celery Tasks
- Create notes asynchronously
- Bulk delete completed notes
- Management commands for task execution
- See `apps/tasks/README.md` for details

## Development Commands

```bash
# Run development server
python manage.py runserver

# Run tests
pytest

# Start Celery worker
python manage.py start_worker

# Run migrations
python manage.py migrate

# Create migrations
python manage.py makemigrations
```

## Documentation

- **`apps/tasks/README.md`** - Celery task documentation

## Environment Variables

Key settings in `.env`:

```env
SECRET_KEY=your-secret-key
DEBUG=True
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
CELERY_BROKER_URL=redis://localhost:6380/0
```

See `.env.example` for all available options.

## Services

### Redis (Port 6380)
```bash
docker compose up -d redis
```

### PostgreSQL (Port 5432)
```bash
docker compose up -d db
```

### Celery Worker
```bash
python manage.py start_worker
# or
docker compose --profile celery up
```

## Testing

```bash
# Run all tests
pytest

# Run specific app tests
pytest apps/notes/tests/
pytest apps/tasks/test_tasks.py

# With coverage
pytest --cov=apps
```

## Useful URLs

- **Django Admin**: http://localhost:8000/admin/
- **Notes API**: http://localhost:8000/api/notes/
- **Home**: http://localhost:8000/

## Notes

- This is a **personal playground** for learning and experimentation
- Not intended for production use
- Feel free to break things and try new ideas!
- Database and media files are gitignored

## License

MIT License - See `LICENSE` file
