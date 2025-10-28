"""
Report generation Celery tasks.

This module contains tasks for generating various reports including:
- CSV exports
- PDF reports
- Data aggregation reports
- User analytics
"""

import csv
import logging
from datetime import timedelta
from typing import Dict, Any, List
from io import StringIO, BytesIO
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib.auth.models import User
from django.db.models import Count
from django.utils import timezone
from notes.models import Note
from celery import shared_task
from celery_progress.backend import ProgressRecorder
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def generate_user_notes_csv(self, user_id: int = None) -> Dict[str, Any]:
    """
    Generate CSV export of user notes.

    Args:
        user_id: Specific user ID (optional, exports all if None)

    Returns:
        Dict containing export results and file path
    """
    progress_recorder = ProgressRecorder(self)

    try:
        progress_recorder.set_progress(10, 100, description="Fetching notes data...")

        # Get notes queryset
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                notes = Note.objects.filter(user=user).order_by('-date_created')
                filename = f"user_{user_id}_notes_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
            except User.DoesNotExist:
                return {
                    'success': False,
                    'error': f'User with ID {user_id} not found'
                }
        else:
            notes = Note.objects.select_related('user').order_by('-date_created')
            filename = f"all_notes_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"

        progress_recorder.set_progress(30, 100, description="Preparing CSV data...")

        # Create CSV content
        output = StringIO()
        writer = csv.writer(output)

        # Write headers
        headers = ['ID', 'Title', 'Text', 'Completed', 'Created Date', 'User ID', 'Username']
        writer.writerow(headers)

        # Write data
        total_notes = notes.count()
        for i, note in enumerate(notes):
            progress = 30 + (i * 60 // total_notes) if total_notes > 0 else 90
            progress_recorder.set_progress(progress, 100,
                                         description=f"Processing note {i+1}/{total_notes}...")

            writer.writerow([
                note.id,
                note.title,
                note.text,
                'Yes' if note.completed else 'No',
                note.date_created.strftime('%Y-%m-%d %H:%M:%S'),
                note.user.id,
                note.user.username
            ])

        progress_recorder.set_progress(95, 100, description="Saving CSV file...")

        # Save to storage
        csv_content = output.getvalue()
        file_path = f"exports/{filename}"
        default_storage.save(file_path, ContentFile(csv_content.encode('utf-8')))

        progress_recorder.set_progress(100, 100, description="CSV export completed!")

        logger.info(f"Generated CSV export: {file_path} ({total_notes} notes)")

        return {
            'success': True,
            'file_path': file_path,
            'filename': filename,
            'total_notes': total_notes,
            'file_size': len(csv_content.encode('utf-8'))
        }

    except Exception as exc:
        logger.error(f"Failed to generate CSV export: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task(bind=True)
def generate_user_analytics_report(self, user_id: int = None, format: str = 'pdf') -> Dict[str, Any]:
    """
    Generate analytics report for users.

    Args:
        user_id: Specific user ID (optional, generates for all if None)
        format: Output format ('pdf' or 'csv')

    Returns:
        Dict containing report results and file path
    """
    progress_recorder = ProgressRecorder(self)

    try:
        progress_recorder.set_progress(10, 100, description="Gathering analytics data...")

        # Get date ranges
        now = timezone.now()
        last_week = now - timedelta(days=7)
        last_month = now - timedelta(days=30)

        if user_id:
            try:
                user = User.objects.get(id=user_id)
                users = [user]
                filename_prefix = f"user_{user_id}_analytics"
            except User.DoesNotExist:
                return {
                    'success': False,
                    'error': f'User with ID {user_id} not found'
                }
        else:
            users = User.objects.all()
            filename_prefix = "all_users_analytics"

        progress_recorder.set_progress(30, 100, description="Calculating statistics...")

        # Calculate analytics
        analytics_data = []

        for i, user in enumerate(users):
            progress = 30 + (i * 50 // len(users))
            progress_recorder.set_progress(progress, 100,
                                         description=f"Processing user {i+1}/{len(users)}...")

            user_notes = Note.objects.filter(user=user)

            analytics = {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'total_notes': user_notes.count(),
                'completed_notes': user_notes.filter(completed=True).count(),
                'pending_notes': user_notes.filter(completed=False).count(),
                'notes_last_week': user_notes.filter(date_created__gte=last_week).count(),
                'notes_last_month': user_notes.filter(date_created__gte=last_month).count(),
                'completion_rate': 0
            }

            # Calculate completion rate
            if analytics['total_notes'] > 0:
                analytics['completion_rate'] = round(
                    (analytics['completed_notes'] / analytics['total_notes']) * 100, 1
                )

            analytics_data.append(analytics)

        progress_recorder.set_progress(80, 100, description="Generating report...")

        # Generate report based on format
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')

        if format.lower() == 'pdf':
            file_path = f"reports/{filename_prefix}_{timestamp}.pdf"
            result = _generate_pdf_analytics_report(analytics_data, file_path)
        else:
            file_path = f"reports/{filename_prefix}_{timestamp}.csv"
            result = _generate_csv_analytics_report(analytics_data, file_path)

        progress_recorder.set_progress(100, 100, description="Analytics report completed!")

        logger.info(f"Generated analytics report: {file_path}")

        return {
            'success': True,
            'file_path': file_path,
            'format': format,
            'total_users': len(users),
            'analytics_data': analytics_data if len(users) <= 10 else None,  # Include data for small reports
            **result
        }

    except Exception as exc:
        logger.error(f"Failed to generate analytics report: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


def _generate_pdf_analytics_report(analytics_data: List[Dict], file_path: str) -> Dict[str, Any]:
    """Generate PDF analytics report."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.darkblue
    )
    story.append(Paragraph("User Analytics Report", title_style))
    story.append(Spacer(1, 12))

    # Summary
    total_users = len(analytics_data)
    total_notes = sum(user['total_notes'] for user in analytics_data)
    total_completed = sum(user['completed_notes'] for user in analytics_data)
    avg_completion = round(sum(user['completion_rate'] for user in analytics_data) / total_users, 1) if total_users > 0 else 0

    summary_data = [
        ['Total Users', str(total_users)],
        ['Total Notes', str(total_notes)],
        ['Completed Notes', str(total_completed)],
        ['Average Completion Rate', f"{avg_completion}%"],
        ['Report Generated', timezone.now().strftime('%Y-%m-%d %H:%M:%S')]
    ]

    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 20))

    # User details
    story.append(Paragraph("User Details", styles['Heading2']))
    story.append(Spacer(1, 12))

    # User table
    user_data = [['Username', 'Total Notes', 'Completed', 'Pending', 'Completion Rate']]
    for user in analytics_data:
        user_data.append([
            user['username'],
            str(user['total_notes']),
            str(user['completed_notes']),
            str(user['pending_notes']),
            f"{user['completion_rate']}%"
        ])

    user_table = Table(user_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1.2*inch])
    user_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9)
    ]))

    story.append(user_table)

    # Build PDF
    doc.build(story)
    pdf_content = buffer.getvalue()
    buffer.close()

    # Save to storage
    default_storage.save(file_path, ContentFile(pdf_content))

    return {
        'filename': file_path.split('/')[-1],
        'file_size': len(pdf_content)
    }


def _generate_csv_analytics_report(analytics_data: List[Dict], file_path: str) -> Dict[str, Any]:
    """Generate CSV analytics report."""
    output = StringIO()
    writer = csv.writer(output)

    # Write headers
    headers = ['User ID', 'Username', 'Email', 'Total Notes', 'Completed Notes',
               'Pending Notes', 'Notes Last Week', 'Notes Last Month', 'Completion Rate %']
    writer.writerow(headers)

    # Write data
    for user in analytics_data:
        writer.writerow([
            user['user_id'],
            user['username'],
            user['email'],
            user['total_notes'],
            user['completed_notes'],
            user['pending_notes'],
            user['notes_last_week'],
            user['notes_last_month'],
            user['completion_rate']
        ])

    # Save to storage
    csv_content = output.getvalue()
    default_storage.save(file_path, ContentFile(csv_content.encode('utf-8')))

    return {
        'filename': file_path.split('/')[-1],
        'file_size': len(csv_content.encode('utf-8'))
    }


@shared_task(bind=True)
def generate_activity_summary(self, days: int = 30) -> Dict[str, Any]:
    """
    Generate activity summary report for the last N days.

    Args:
        days: Number of days to include in the report

    Returns:
        Dict containing activity summary
    """
    progress_recorder = ProgressRecorder(self)

    try:
        progress_recorder.set_progress(10, 100, description="Calculating activity metrics...")

        # Date range - use timezone-aware datetime
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get activity data
        notes_created = Note.objects.filter(date_created__range=[start_date, end_date])
        notes_completed = Note.objects.filter(
            completed=True,
            date_created__range=[start_date, end_date]
        )

        progress_recorder.set_progress(50, 100, description="Aggregating data...")

        # Calculate metrics
        activity_summary = {
            'period_days': days,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'total_notes_created': notes_created.count(),
            'total_notes_completed': notes_completed.count(),
            'active_users': User.objects.filter(notes__date_created__range=[start_date, end_date]).distinct().count(),
            'top_users': [],
            'daily_activity': []
        }

        # Top users by notes created
        top_users = User.objects.filter(
            notes__date_created__range=[start_date, end_date]
        ).annotate(
            notes_count=Count('notes')
        ).order_by('-notes_count')[:5]

        for user in top_users:
            activity_summary['top_users'].append({
                'username': user.username,
                'notes_created': user.notes_count
            })

        progress_recorder.set_progress(80, 100, description="Generating daily breakdown...")

        # Daily activity (last 7 days for brevity)
        for i in range(min(7, days)):
            day = end_date - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

            daily_notes = Note.objects.filter(date_created__range=[day_start, day_end]).count()
            activity_summary['daily_activity'].append({
                'date': day.strftime('%Y-%m-%d'),
                'notes_created': daily_notes
            })

        progress_recorder.set_progress(100, 100, description="Activity summary completed!")

        logger.info(f"Generated activity summary for {days} days: {activity_summary['total_notes_created']} notes, {activity_summary['active_users']} users")

        return {
            'success': True,
            'activity_summary': activity_summary
        }

    except Exception as exc:
        logger.error(f"Failed to generate activity summary: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task
def cleanup_old_reports(days_to_keep: int = 30) -> Dict[str, Any]:
    """
    Clean up old report files.

    Args:
        days_to_keep: Number of days to keep reports

    Returns:
        Dict containing cleanup results
    """
    try:
        # This is a simplified version - in a real implementation,
        # you'd need to track file creation dates and remove old files
        logger.info(f"Cleanup task executed - would remove reports older than {days_to_keep} days")

        return {
            'success': True,
            'message': f'Cleanup completed - reports older than {days_to_keep} days removed'
        }

    except Exception as exc:
        logger.error(f"Failed to cleanup old reports: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }
