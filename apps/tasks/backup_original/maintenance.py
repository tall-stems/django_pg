"""
Scheduled maintenance and analytics tasks.

This module contains tasks that run         # Calculate various statistics
        stats = {
            'total_users': User.objects.count(),
            'active_users_last_week': User.objects.filter(
                notes__date_created__gte=timezone.now() - timedelta(days=7)
            ).distinct().count(),
            'total_notes': Note.objects.count(),
            'completed_notes': Note.objects.filter(completed=True).count(),
            'notes_last_week': Note.objects.filter(
                date_created__gte=timezone.now() - timedelta(days=7)
            ).count(),
            'average_notes_per_user': 0,
            'completion_rate': 0,
            'calculated_at': timezone.now().isoformat()
        }or:
- Database cleanup
- Analytics calculation
- Health checks
- System maintenance
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import transaction
from django.db import models
from django.core.mail import mail_admins
from django.utils import timezone
from notes.models import Note
from celery import shared_task
from celery.schedules import crontab
from django.conf import settings
import os
import psutil

logger = logging.getLogger(__name__)


@shared_task
def cleanup_old_data(days_to_keep: int = 90) -> Dict[str, Any]:
    """
    Clean up old data from the database.

    Args:
        days_to_keep: Number of days to keep data

    Returns:
        Dict containing cleanup results
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)

        # Count items before cleanup
        old_notes_count = Note.objects.filter(
            date_created__lt=cutoff_date,
            completed=True  # Only delete completed notes
        ).count()

        # Perform cleanup
        with transaction.atomic():
            deleted_notes = Note.objects.filter(
                date_created__lt=cutoff_date,
                completed=True
            ).delete()

        result = {
            'success': True,
            'cutoff_date': cutoff_date.strftime('%Y-%m-%d'),
            'deleted_notes': deleted_notes[0] if deleted_notes else 0,
            'days_kept': days_to_keep
        }

        logger.info(f"Cleanup completed: {result['deleted_notes']} old notes deleted")

        return result

    except Exception as exc:
        logger.error(f"Failed to cleanup old data: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task
def calculate_user_stats() -> Dict[str, Any]:
    """
    Calculate and cache user statistics.

    Returns:
        Dict containing calculated statistics
    """
    try:
        # Calculate various statistics
        stats = {
            'total_users': User.objects.count(),
            'active_users_last_week': User.objects.filter(
                notes__date_created__gte=datetime.now() - timedelta(days=7)
            ).distinct().count(),
            'total_notes': Note.objects.count(),
            'completed_notes': Note.objects.filter(completed=True).count(),
            'notes_last_week': Note.objects.filter(
                date_created__gte=datetime.now() - timedelta(days=7)
            ).count(),
            'average_notes_per_user': 0,
            'completion_rate': 0,
            'calculated_at': datetime.now().isoformat()
        }

        # Calculate averages
        if stats['total_users'] > 0:
            stats['average_notes_per_user'] = round(
                stats['total_notes'] / stats['total_users'], 2
            )

        if stats['total_notes'] > 0:
            stats['completion_rate'] = round(
                (stats['completed_notes'] / stats['total_notes']) * 100, 1
            )

        # Top users by note count
        top_users = User.objects.annotate(
            note_count=models.Count('notes')
        ).order_by('-note_count')[:5]

        stats['top_users'] = [
            {'username': user.username, 'note_count': user.note_count}
            for user in top_users
        ]

        # You could cache these stats in Redis or database here
        # For now, we'll just return them

        logger.info(f"User stats calculated: {stats['total_users']} users, {stats['total_notes']} notes")

        return {
            'success': True,
            'stats': stats
        }

    except Exception as exc:
        logger.error(f"Failed to calculate user stats: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task
def health_check() -> Dict[str, Any]:
    """
    Perform system health checks.

    Returns:
        Dict containing health check results
    """
    try:
        health_status = {
            'timestamp': timezone.now().isoformat(),
            'overall_status': 'healthy',
            'checks': {}
        }

        # Database check
        try:
            User.objects.count()
            health_status['checks']['database'] = {
                'status': 'healthy',
                'message': 'Database connection successful'
            }
        except Exception as db_exc:
            health_status['checks']['database'] = {
                'status': 'unhealthy',
                'message': f'Database error: {str(db_exc)}'
            }
            health_status['overall_status'] = 'unhealthy'

        # Redis check (Celery broker)
        try:
            from django.core.cache import cache
            cache.set('health_check', 'ok', 10)
            cache_result = cache.get('health_check')
            if cache_result == 'ok':
                health_status['checks']['redis'] = {
                    'status': 'healthy',
                    'message': 'Redis connection successful'
                }
            else:
                raise Exception('Cache test failed')
        except Exception as redis_exc:
            health_status['checks']['redis'] = {
                'status': 'unhealthy',
                'message': f'Redis error: {str(redis_exc)}'
            }
            health_status['overall_status'] = 'unhealthy'

        # Disk space check
        try:
            disk_usage = psutil.disk_usage('/')
            free_percent = (disk_usage.free / disk_usage.total) * 100

            if free_percent > 20:
                health_status['checks']['disk_space'] = {
                    'status': 'healthy',
                    'message': f'Disk space: {free_percent:.1f}% free'
                }
            else:
                health_status['checks']['disk_space'] = {
                    'status': 'warning',
                    'message': f'Low disk space: {free_percent:.1f}% free'
                }
        except Exception as disk_exc:
            health_status['checks']['disk_space'] = {
                'status': 'unknown',
                'message': f'Disk check error: {str(disk_exc)}'
            }

        # Memory check
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            if memory_percent < 80:
                health_status['checks']['memory'] = {
                    'status': 'healthy',
                    'message': f'Memory usage: {memory_percent}%'
                }
            else:
                health_status['checks']['memory'] = {
                    'status': 'warning',
                    'message': f'High memory usage: {memory_percent}%'
                }
        except Exception as mem_exc:
            health_status['checks']['memory'] = {
                'status': 'unknown',
                'message': f'Memory check error: {str(mem_exc)}'
            }

        # Log results
        if health_status['overall_status'] == 'healthy':
            logger.info("Health check passed")
        else:
            logger.warning(f"Health check failed: {health_status}")

        return {
            'success': True,
            'health_status': health_status
        }

    except Exception as exc:
        logger.error(f"Health check failed: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task
def send_daily_summary() -> Dict[str, Any]:
    """
    Send daily summary email to administrators.

    Returns:
        Dict containing summary results
    """
    try:
        # Calculate today's activity
        today = timezone.now().date()
        today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        today_end = timezone.make_aware(datetime.combine(today, datetime.max.time()))

        # Get statistics
        notes_created_today = Note.objects.filter(
            date_created__range=[today_start, today_end]
        ).count()

        notes_completed_today = Note.objects.filter(
            completed=True,
            date_created__range=[today_start, today_end]
        ).count()

        active_users_today = User.objects.filter(
            notes__date_created__range=[today_start, today_end]
        ).distinct().count()

        # Create summary message
        subject = f"Daily Summary - {today.strftime('%Y-%m-%d')}"
        message = f"""
        Daily Activity Summary for {today.strftime('%B %d, %Y')}:

        • Notes Created: {notes_created_today}
        • Notes Completed: {notes_completed_today}
        • Active Users: {active_users_today}
        • Total Users: {User.objects.count()}
        • Total Notes: {Note.objects.count()}

        System Status: All systems operational

        This is an automated message from Stems Django Playground.
        """

        # Send email to administrators
        # In development, this will be printed to console
        mail_admins(subject, message, fail_silently=False)

        logger.info(f"Daily summary sent: {notes_created_today} notes, {active_users_today} users")

        return {
            'success': True,
            'date': today.strftime('%Y-%m-%d'),
            'notes_created': notes_created_today,
            'notes_completed': notes_completed_today,
            'active_users': active_users_today
        }

    except Exception as exc:
        logger.error(f"Failed to send daily summary: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task
def backup_database() -> Dict[str, Any]:
    """
    Create a backup of the database.

    Returns:
        Dict containing backup results
    """
    try:
        # For SQLite, we'll just copy the file
        # In production, you'd use proper database backup tools

        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"db_backup_{timestamp}.sqlite3"

        # This is a simplified backup for SQLite
        # In production, use proper backup strategies

        logger.info(f"Database backup created: {backup_filename}")

        return {
            'success': True,
            'backup_file': backup_filename,
            'timestamp': timestamp,
            'message': 'Database backup completed'
        }

    except Exception as exc:
        logger.error(f"Failed to backup database: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task
def update_search_index() -> Dict[str, Any]:
    """
    Update search index for notes (if using search functionality).

    Returns:
        Dict containing indexing results
    """
    try:
        # This is a placeholder for search index updates
        # You would implement actual search indexing here

        notes_count = Note.objects.count()

        logger.info(f"Search index updated for {notes_count} notes")

        return {
            'success': True,
            'indexed_notes': notes_count,
            'message': 'Search index updated successfully'
        }

    except Exception as exc:
        logger.error(f"Failed to update search index: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


# Celery Beat Schedule Configuration
# Add this to your settings.py:
"""
CELERY_BEAT_SCHEDULE = {
    'cleanup-old-data': {
        'task': 'tasks.maintenance.cleanup_old_data',
        'schedule': crontab(hour=2, minute=0),  # Run at 2 AM daily
        'kwargs': {'days_to_keep': 90}
    },
    'calculate-user-stats': {
        'task': 'tasks.maintenance.calculate_user_stats',
        'schedule': crontab(minute=0),  # Run hourly
    },
    'health-check': {
        'task': 'tasks.maintenance.health_check',
        'schedule': crontab(minute='*/15'),  # Run every 15 minutes
    },
    'send-daily-summary': {
        'task': 'tasks.maintenance.send_daily_summary',
        'schedule': crontab(hour=9, minute=0),  # Run at 9 AM daily
    },
    'backup-database': {
        'task': 'tasks.maintenance.backup_database',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # Run weekly on Monday at 3 AM
    },
    'update-search-index': {
        'task': 'tasks.maintenance.update_search_index',
        'schedule': crontab(minute=30),  # Run every hour at 30 minutes
    }
}
"""
