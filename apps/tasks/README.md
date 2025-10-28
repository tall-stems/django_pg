# Celery Tasks

A simplified, production-ready Celery implementation focused on learning fundamentals and building practical async task processing.

## 📋 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [What's Included](#whats-included)
- [Usage Guide](#usage-guide)
- [Task Examples](#task-examples)
- [Management Commands](#management-commands)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Advanced Examples](#advanced-examples)

---

## Overview

This is a simplified Celery setup designed for:
- ✅ **Learning** - Understand async task processing fundamentals
- ✅ **Building** - Production-ready patterns you can extend
- ✅ **Testing** - Full test coverage with examples

### Architecture

```
Django View → Task.delay() → Redis Queue → Celery Worker → Execute Task → Store Result
     ↓                                              ↓
 Returns immediately                          Runs in background
```

---

## Quick Start

### 1. Start Redis

```bash
docker compose up -d redis
```

### 2. Start Celery Worker

**Option A: Management Command (Recommended)**
```bash
python manage.py start_worker
```

**Option B: Docker Compose**
```bash
docker compose --profile celery up
```

**Option C: Manual Command**
```bash
celery -A playground worker --loglevel=info
```

### 3. Run Your First Task

```bash
# Create a note asynchronously
python manage.py run_task --user-id 1

# Create a note synchronously (immediate)
python manage.py run_task --user-id 1 --sync
```

---

## What's Included

### Tasks (`tasks.py`)

1. **`create_note_task(user_id, title, text)`**
   - Creates a note for a user asynchronously
   - Returns: `{'success': True/False, 'note_id': id, 'message': str}`

2. **`delete_completed_notes(user_id=None)`**
   - Bulk deletes completed notes
   - Can delete for specific user or all users
   - Returns: `{'success': True/False, 'count': number, 'message': str}`

### Management Commands

Located in `management/commands/`:

- **`run_task`** - Execute tasks with options (sync/async)
- **`check_task`** - Check status of queued tasks
- **`start_worker`** - Start Celery worker easily

### Tests (`test_tasks.py`)

- 8 comprehensive tests covering all scenarios
- Run with: `pytest apps/tasks/test_tasks.py -v`

### Archived Examples (`backup_original/`)

Complex production examples for reference:
- `email.py` - Email sending tasks
- `reports.py` - PDF/CSV generation
- `maintenance.py` - Health checks, cleanup
- `media.py` - Image processing
- `advanced.py` - Progress tracking, workflows
- `api_integration.py` - External API calls

---

## Usage Guide

### Calling Tasks in Your Code

#### Synchronous (Immediate Execution)
```python
from tasks.tasks import create_note_task

# Runs immediately, blocks until complete
result = create_note_task(user_id=1, title="Todo", text="Buy milk")
print(result)  # {'success': True, 'note_id': 123, ...}
```

#### Asynchronous (Background Execution)
```python
from tasks.tasks import create_note_task

# Queues task, returns immediately
task = create_note_task.delay(user_id=1, title="Todo", text="Buy milk")

# Get task ID (store this to check status later)
task_id = task.id

# Wait for result (blocks until complete)
result = task.get()

# Check status without waiting
status = task.state  # 'PENDING', 'STARTED', 'SUCCESS', 'FAILURE'
```

### In Django Views

```python
from django.http import JsonResponse
from tasks.tasks import create_note_task

def create_note_view(request):
    user_id = request.user.id
    title = request.POST.get('title')
    text = request.POST.get('text')

    # Queue the task
    task = create_note_task.delay(user_id, title, text)

    # Return immediately
    return JsonResponse({
        'task_id': task.id,
        'status': 'queued',
        'message': 'Note creation started'
    })

def check_task_view(request, task_id):
    from celery.result import AsyncResult

    task = AsyncResult(task_id)

    if task.ready():
        return JsonResponse({
            'status': 'completed',
            'result': task.result
        })
    else:
        return JsonResponse({
            'status': task.state,
            'message': 'Task still processing'
        })
```

---

## Task Examples

### Example 1: Create Note Task

```python
from tasks.tasks import create_note_task

# Async execution
task = create_note_task.delay(
    user_id=1,
    title="Shopping List",
    text="Eggs, milk, bread"
)

print(f"Task ID: {task.id}")
# Task ID: 550e8400-e29b-41d4-a716-446655440000

# Check result later
result = task.get(timeout=10)
print(result)
# {'success': True, 'note_id': 42, 'message': 'Note created successfully'}
```

### Example 2: Delete Completed Notes

```python
from tasks.tasks import delete_completed_notes

# Delete completed notes for user 1
task = delete_completed_notes.delay(user_id=1)
result = task.get()
# {'success': True, 'count': 5, 'message': 'Deleted 5 completed notes'}

# Delete all completed notes (all users)
task = delete_completed_notes.delay()
result = task.get()
# {'success': True, 'count': 23, 'message': 'Deleted 23 completed notes'}
```

### Example 3: Error Handling

```python
from tasks.tasks import create_note_task
from celery.exceptions import TimeoutError

try:
    task = create_note_task.delay(user_id=999, title="Test")
    result = task.get(timeout=5)

    if result['success']:
        print(f"Created note {result['note_id']}")
    else:
        print(f"Error: {result['error']}")

except TimeoutError:
    print("Task took too long")
except Exception as e:
    print(f"Task failed: {e}")
```

---

## Management Commands

### `run_task` - Execute Tasks

```bash
# Show help
python manage.py run_task

# Create note (async)
python manage.py run_task --user-id 1

# Create note (sync - immediate)
python manage.py run_task --user-id 1 --sync

# Custom content
python manage.py run_task --user-id 1 --title "Todo" --text "Buy milk"

# Delete completed notes (specific user)
python manage.py run_task --user-id 1 --delete

# Delete all completed notes
python manage.py run_task --delete
```

### `check_task` - Check Status

```bash
# Check task status by ID
python manage.py check_task <task-id>

# Example
python manage.py check_task 550e8400-e29b-41d4-a716-446655440000
```

### `start_worker` - Start Celery Worker

```bash
# Start with defaults
python manage.py start_worker

# With custom options
python manage.py start_worker --loglevel debug --concurrency 4
```

---

## Testing

### Run All Tests

```bash
# With pytest
pytest apps/tasks/test_tasks.py -v

# With Django's test runner
python manage.py test tasks.test_tasks
```

### Run Specific Tests

```bash
# Test create_note_task
pytest apps/tasks/test_tasks.py::test_create_note_task_success -v

# Test delete_completed_notes
pytest apps/tasks/test_tasks.py::test_delete_completed_notes_specific_user -v
```

### Example Test Output

```
tests/test_tasks.py::test_create_note_task_success PASSED           [ 12%]
tests/test_tasks.py::test_create_note_task_invalid_user PASSED      [ 25%]
tests/test_tasks.py::test_create_note_task_missing_params PASSED    [ 37%]
tests/test_tasks.py::test_create_note_task_database_error PASSED    [ 50%]
tests/test_tasks.py::test_delete_completed_notes_specific_user PASSED [ 62%]
tests/test_tasks.py::test_delete_completed_notes_all_users PASSED   [ 75%]
tests/test_tasks.py::test_delete_completed_notes_no_completed PASSED [ 87%]
tests/test_tasks.py::test_delete_completed_notes_invalid_user PASSED [100%]

===================== 8 passed in 0.30s =====================
```

---

## Troubleshooting

### Redis Not Running

```bash
# Check if Redis is running
nc -z localhost 6380

# If not, start it
docker compose up -d redis

# Check logs
docker compose logs redis
```

### Worker Not Running

```bash
# Check if worker is running
ps aux | grep celery

# Start worker
python manage.py start_worker

# Or with Docker
docker compose --profile celery up
```

### Tasks Not Found

If you get "Task not found" errors:

```bash
# Restart the worker after code changes
# Press Ctrl+C to stop, then:
python manage.py start_worker
```

### Task Stuck in Pending

```bash
# Check queue length
redis-cli -p 6380 LLEN celery

# View queued tasks
redis-cli -p 6380 LRANGE celery 0 -1

# Clear queue (careful!)
redis-cli -p 6380 DEL celery
```

### View Task Results in Redis

```bash
# Connect to Redis
redis-cli -p 6380

# List all keys
KEYS *

# Get task result
GET celery-task-meta-<task-id>
```

---

## Advanced Examples

For more complex use cases, see `backup_original/`:

### Email Tasks (`backup_original/email.py`)
- Welcome emails
- Password reset emails
- Notification emails
- Email templates

### Report Generation (`backup_original/reports.py`)
- PDF reports with ReportLab
- CSV exports
- Analytics reports
- Chart generation

### Maintenance Tasks (`backup_original/maintenance.py`)
- Health checks
- Database cleanup
- User statistics
- Search index updates
- Scheduled backups

### Image Processing (`backup_original/media.py`)
- Image resizing
- Thumbnail generation
- Watermarking
- Format conversion
- S3 uploads

### Advanced Patterns (`backup_original/advanced.py`)
- Progress tracking
- Task workflows (chains, groups)
- Retry strategies
- Custom error handling
- Rate limiting

### API Integration (`backup_original/api_integration.py`)
- External API calls
- Batch processing
- Webhook handling
- Data synchronization

---

## Common Patterns

### Pattern 1: Task Chaining

```python
from celery import chain

# Execute tasks in sequence
workflow = chain(
    create_note_task.s(user_id=1, title="Step 1"),
    create_note_task.s(user_id=1, title="Step 2"),
)
result = workflow.apply_async()
```

### Pattern 2: Scheduled Tasks

```python
# In playground/settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'cleanup-daily': {
        'task': 'tasks.tasks.delete_completed_notes',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
}
```

### Pattern 3: Task Retries

```python
from celery import shared_task

@shared_task(bind=True, max_retries=3)
def create_note_with_retry(self, user_id, title, text):
    try:
        # Your code here
        pass
    except Exception as exc:
        # Retry after 5 seconds
        raise self.retry(exc=exc, countdown=5)
```

---

## Configuration

### Settings (`playground/settings.py`)

```python
# Broker and result backend
CELERY_BROKER_URL = 'redis://localhost:6380/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6380/0'

# Serialization
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']

# Worker settings
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Task expiration
CELERY_RESULT_EXPIRES = 3600  # 1 hour

# Task limits
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes
CELERY_TASK_TIME_LIMIT = 600       # 10 minutes
CELERY_TASK_MAX_RETRIES = 3
```

---

## Resources

- **Official Docs**: https://docs.celeryproject.org/
- **Django + Celery**: https://docs.celeryproject.org/en/stable/django/
- **Redis**: https://redis.io/docs/
- **Best Practices**: https://docs.celeryproject.org/en/stable/userguide/tasks.html#best-practices

---

## Questions?

- Check `backup_original/` for complex examples
- Review `test_tasks.py` for usage patterns
- See main project `ENV_VARIABLES.md` for configuration

**Happy task processing! 🚀**
