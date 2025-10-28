"""
Email-related Celery tasks.

This module contains tasks for sending emails asynchronously.
Tasks include welcome emails, notifications, and password reset emails.
"""

import logging
from typing import List, Dict, Any
from django.core.mail import send_mail, send_mass_mail
from django.contrib.auth.models import User
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_welcome_email(self, user_id: int) -> Dict[str, Any]:
    """
    Send a welcome email to a newly registered user.

    Args:
        user_id: The ID of the user to send the welcome email to

    Returns:
        Dict containing success status and message

    Raises:
        Retry: If email sending fails and retries are available
    """
    try:
        user = User.objects.get(id=user_id)

        # Email subject
        subject = 'Welcome to Stems\' Django Playground!'

        # For now, we'll use a simple text email
        # In Phase 2, we'll add HTML templates
        message = f"""
        Hello {user.get_full_name() or user.username},

        Welcome to Stems' Django Playground! We're excited to have you on board.

        You can now:
        - Create and manage your notes
        - Use our REST API
        - Explore all the features we have to offer

        If you have any questions, feel free to reach out to our support team.

        Best regards,
        Stems' Django Playground Team
        """

        # Send the email
        success = send_mail(
            subject=subject,
            message=message.strip(),
            from_email=None,  # Uses DEFAULT_FROM_EMAIL
            recipient_list=[user.email],
            fail_silently=False,
        )

        if success:
            logger.info(f"Welcome email sent successfully to user {user.email}")
            return {
                'success': True,
                'message': f'Welcome email sent to {user.email}',
                'user_id': user_id
            }
        else:
            raise Exception("Email sending returned False")

    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} does not exist")
        return {
            'success': False,
            'message': f'User with ID {user_id} not found',
            'user_id': user_id
        }

    except Exception as exc:
        logger.error(f"Failed to send welcome email to user {user_id}: {exc}")

        # Retry the task if we have retries left
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying welcome email task for user {user_id} (attempt {self.request.retries + 1})")
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

        # No more retries, return failure
        return {
            'success': False,
            'message': f'Failed to send welcome email after {self.max_retries} attempts: {str(exc)}',
            'user_id': user_id
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_note_notification(self, user_id: int, note_title: str, action: str) -> Dict[str, Any]:
    """
    Send a notification email when a user creates or completes a note.

    Args:
        user_id: The ID of the user
        note_title: The title of the note
        action: The action performed ('created' or 'completed')

    Returns:
        Dict containing success status and message
    """
    try:
        user = User.objects.get(id=user_id)

        # Validate action
        if action not in ['created', 'completed']:
            raise ValueError(f"Invalid action: {action}")

        # Email subject and message
        action_past = 'created' if action == 'created' else 'completed'
        subject = f'Note {action_past}: {note_title}'

        message = f"""
        Hello {user.get_full_name() or user.username},

        Your note "{note_title}" has been {action_past}.

        {'Great job on completing your note!' if action == 'completed' else 'Your new note has been saved successfully.'}

        Log in to your account to view all your notes.

        Best regards,
        Stems' Django Playground Team
        """

        # Send the email
        success = send_mail(
            subject=subject,
            message=message.strip(),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )

        if success:
            logger.info(f"Note {action} notification sent to user {user.email}")
            return {
                'success': True,
                'message': f'Notification sent to {user.email}',
                'user_id': user_id,
                'note_title': note_title,
                'action': action
            }
        else:
            raise Exception("Email sending returned False")

    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} does not exist")
        return {
            'success': False,
            'message': f'User with ID {user_id} not found',
            'user_id': user_id
        }

    except Exception as exc:
        logger.error(f"Failed to send note notification to user {user_id}: {exc}")

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying note notification task for user {user_id}")
            raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))

        return {
            'success': False,
            'message': f'Failed to send notification after {self.max_retries} attempts: {str(exc)}',
            'user_id': user_id
        }


@shared_task
def send_bulk_notification(user_ids: List[int], subject: str, message: str) -> Dict[str, Any]:
    """
    Send bulk email notifications to multiple users.

    Args:
        user_ids: List of user IDs to send emails to
        subject: Email subject
        message: Email message

    Returns:
        Dict containing results summary
    """
    results = {
        'total_users': len(user_ids),
        'successful': 0,
        'failed': 0,
        'failed_users': []
    }

    # Prepare messages for mass email
    messages = []
    failed_users = []

    for user_id in user_ids:
        try:
            user = User.objects.get(id=user_id)

            # Personalize the message
            personalized_message = f"Hello {user.get_full_name() or user.username},\n\n{message}"

            messages.append((
                subject,
                personalized_message,
                None,  # from_email (uses DEFAULT_FROM_EMAIL)
                [user.email]
            ))

        except User.DoesNotExist:
            logger.warning(f"User with ID {user_id} does not exist")
            failed_users.append(user_id)

    # Send mass emails
    try:
        sent_count = send_mass_mail(messages, fail_silently=False)
        results['successful'] = sent_count
        results['failed'] = len(failed_users)
        results['failed_users'] = failed_users

        logger.info(f"Bulk email sent to {sent_count} users successfully")

    except Exception as exc:
        logger.error(f"Failed to send bulk emails: {exc}")
        results['failed'] = len(user_ids)
        results['successful'] = 0
        results['error'] = str(exc)

    return results
