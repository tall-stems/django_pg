"""
Advanced Celery task features including progress tracking and custom task classes.

This module contains:
- Custom task base classes
- Progress tracking utilities
- Task chaining and workflows
- Error handling patterns
"""

import logging
from typing import Dict, Any, List
from celery import shared_task, Task
from celery_progress.backend import ProgressRecorder
from celery import chain, group, chord
from django.core.mail import send_mail
from django.contrib.auth.models import User
from tasks.email import send_welcome_email, send_note_notification
from tasks.reports import generate_user_analytics_report
import time

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Custom task class that supports success and failure callbacks."""

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        logger.info(f"Task {task_id} succeeded with result: {retval}")

        # Execute success callback if provided
        success_callback = kwargs.get('success_callback')
        if success_callback:
            try:
                success_callback(retval, task_id, args, kwargs)
            except Exception as exc:
                logger.error(f"Success callback failed for task {task_id}: {exc}")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        logger.error(f"Task {task_id} failed: {exc}")

        # Execute failure callback if provided
        failure_callback = kwargs.get('failure_callback')
        if failure_callback:
            try:
                failure_callback(exc, task_id, args, kwargs, einfo)
            except Exception as callback_exc:
                logger.error(f"Failure callback failed for task {task_id}: {callback_exc}")

        # Send notification email for critical failures
        if kwargs.get('notify_on_failure', False):
            try:
                send_mail(
                    subject=f"Task Failure: {task_id}",
                    message=f"Task {task_id} failed with error: {exc}\n\nArgs: {args}\nKwargs: {kwargs}",
                    from_email=None,
                    recipient_list=['admin@playground.com'],
                    fail_silently=True
                )
            except Exception:
                pass  # Don't fail on notification failure


@shared_task(bind=True, base=CallbackTask)
def long_running_task_with_progress(self, duration: int = 30, steps: int = 10) -> Dict[str, Any]:
    """
    Demonstration of a long-running task with progress tracking.

    Args:
        duration: Total duration in seconds
        steps: Number of progress steps

    Returns:
        Dict containing task results
    """
    progress_recorder = ProgressRecorder(self)

    step_duration = duration / steps

    for i in range(steps):
        # Simulate work
        time.sleep(step_duration)

        # Update progress
        progress = int((i + 1) * 100 / steps)
        progress_recorder.set_progress(
            progress,
            100,
            description=f"Processing step {i + 1} of {steps}..."
        )

        logger.info(f"Task {self.request.id} progress: {progress}%")

    result = {
        'success': True,
        'duration': duration,
        'steps': steps,
        'task_id': self.request.id,
        'message': f'Completed {steps} steps in {duration} seconds'
    }

    progress_recorder.set_progress(100, 100, description="Task completed!")

    return result


@shared_task(bind=True)
def batch_user_operation(self, user_ids: List[int], operation: str, **kwargs) -> Dict[str, Any]:
    """
    Perform batch operations on multiple users with progress tracking.

    Args:
        user_ids: List of user IDs to process
        operation: Operation to perform ('welcome_email', 'analytics_report', etc.)
        **kwargs: Operation-specific parameters

    Returns:
        Dict containing batch operation results
    """
    progress_recorder = ProgressRecorder(self)

    total_users = len(user_ids)
    results = {
        'total_users': total_users,
        'successful': 0,
        'failed': 0,
        'results': [],
        'errors': []
    }

    progress_recorder.set_progress(0, 100, description=f"Starting batch {operation} for {total_users} users...")

    for i, user_id in enumerate(user_ids):
        progress = int((i * 100) / total_users)
        progress_recorder.set_progress(
            progress,
            100,
            description=f"Processing user {i + 1} of {total_users}..."
        )

        try:
            if operation == 'welcome_email':
                result = send_welcome_email.delay(user_id)
                task_result = result.get(timeout=30)

            elif operation == 'analytics_report':
                result = generate_user_analytics_report.delay(user_id, kwargs.get('format', 'pdf'))
                task_result = result.get(timeout=60)

            else:
                raise ValueError(f"Unknown operation: {operation}")

            if task_result.get('success'):
                results['successful'] += 1
                results['results'].append({
                    'user_id': user_id,
                    'result': task_result
                })
            else:
                results['failed'] += 1
                results['errors'].append({
                    'user_id': user_id,
                    'error': task_result.get('error', 'Unknown error')
                })

        except Exception as exc:
            results['failed'] += 1
            results['errors'].append({
                'user_id': user_id,
                'error': str(exc)
            })
            logger.error(f"Batch operation failed for user {user_id}: {exc}")

    progress_recorder.set_progress(100, 100, description="Batch operation completed!")

    logger.info(f"Batch {operation} completed: {results['successful']} successful, {results['failed']} failed")

    return results


@shared_task
def user_onboarding_workflow(user_id: int) -> Dict[str, Any]:
    """
    Complete user onboarding workflow using task chaining.

    Args:
        user_id: ID of the user to onboard

    Returns:
        Dict containing workflow results
    """
    try:
        # Verify user exists
        user = User.objects.get(id=user_id)

        # Create a workflow chain
        workflow = chain(
            # Step 1: Send welcome email
            send_welcome_email.s(user_id),

            # Step 2: Generate user analytics report
            generate_user_analytics_report.s(user_id, 'pdf'),

            # Step 3: Add to analytics calculation
            # This would be a custom task that adds user to analytics
        )

        # Execute the workflow
        result = workflow.apply_async()

        logger.info(f"Onboarding workflow started for user {user_id}")

        return {
            'success': True,
            'user_id': user_id,
            'workflow_id': result.id,
            'message': 'Onboarding workflow started successfully'
        }

    except User.DoesNotExist:
        return {
            'success': False,
            'error': f'User with ID {user_id} not found'
        }
    except Exception as exc:
        logger.error(f"Failed to start onboarding workflow for user {user_id}: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task
def parallel_report_generation(user_ids: List[int]) -> Dict[str, Any]:
    """
    Generate reports for multiple users in parallel using groups.

    Args:
        user_ids: List of user IDs to generate reports for

    Returns:
        Dict containing parallel processing results
    """
    try:
        # Create a group of parallel tasks
        job = group(generate_user_analytics_report.s(user_id, 'pdf') for user_id in user_ids)

        # Execute in parallel
        result = job.apply_async()

        # Wait for all tasks to complete (in production, you'd handle this asynchronously)
        reports = result.get(timeout=300)  # 5 minute timeout

        # Process results
        successful_reports = [r for r in reports if r.get('success')]
        failed_reports = [r for r in reports if not r.get('success')]

        logger.info(f"Parallel report generation completed: {len(successful_reports)} successful, {len(failed_reports)} failed")

        return {
            'success': True,
            'total_users': len(user_ids),
            'successful_reports': len(successful_reports),
            'failed_reports': len(failed_reports),
            'reports': successful_reports
        }

    except Exception as exc:
        logger.error(f"Failed to generate parallel reports: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task
def conditional_task_workflow(user_id: int, conditions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute conditional workflow based on user data and conditions.

    Args:
        user_id: ID of the user
        conditions: Dict of conditions to check

    Returns:
        Dict containing workflow results
    """
    try:
        user = User.objects.get(id=user_id)
        workflow_steps = []

        # Check conditions and build workflow
        if conditions.get('send_welcome', False):
            workflow_steps.append('welcome_email')

        if conditions.get('generate_report', False):
            workflow_steps.append('analytics_report')

        if conditions.get('note_count_threshold', 0) > 0:
            note_count = user.notes.count()
            if note_count >= conditions['note_count_threshold']:
                workflow_steps.append('achievement_notification')

        # Execute workflow steps
        results = []
        for step in workflow_steps:
            if step == 'welcome_email':
                result = send_welcome_email.delay(user_id)
                results.append({'step': step, 'task_id': result.id})

            elif step == 'analytics_report':
                result = generate_user_analytics_report.delay(user_id)
                results.append({'step': step, 'task_id': result.id})

            elif step == 'achievement_notification':
                result = send_note_notification.delay(
                    user_id=user_id,
                    note_title=f"Achievement: {user.notes.count()} notes!",
                    action='completed'
                )
                results.append({'step': step, 'task_id': result.id})

        logger.info(f"Conditional workflow completed for user {user_id}: {len(workflow_steps)} steps")

        return {
            'success': True,
            'user_id': user_id,
            'workflow_steps': workflow_steps,
            'task_results': results
        }

    except User.DoesNotExist:
        return {
            'success': False,
            'error': f'User with ID {user_id} not found'
        }
    except Exception as exc:
        logger.error(f"Failed to execute conditional workflow for user {user_id}: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task(bind=True, base=CallbackTask)
def monitored_task(self, operation: str, **kwargs) -> Dict[str, Any]:
    """
    A task with comprehensive monitoring and error handling.

    Args:
        operation: Operation to perform
        **kwargs: Operation parameters and monitoring options

    Returns:
        Dict containing task results
    """
    progress_recorder = ProgressRecorder(self)

    # Extract monitoring options
    notify_on_failure = kwargs.pop('notify_on_failure', False)
    timeout = kwargs.pop('timeout', 300)

    try:
        progress_recorder.set_progress(10, 100, description=f"Starting {operation}...")

        # Simulate operation
        if operation == 'data_processing':
            # Simulate data processing with progress updates
            for i in range(5):
                time.sleep(1)  # Simulate work
                progress = 10 + (i * 18)
                progress_recorder.set_progress(progress, 100, description=f"Processing batch {i+1}/5...")

        elif operation == 'file_upload':
            # Simulate file upload with progress
            for i in range(10):
                time.sleep(0.5)  # Simulate upload
                progress = 10 + (i * 9)
                progress_recorder.set_progress(progress, 100, description=f"Uploading... {progress}%")

        else:
            raise ValueError(f"Unknown operation: {operation}")

        progress_recorder.set_progress(100, 100, description="Operation completed successfully!")

        result = {
            'success': True,
            'operation': operation,
            'task_id': self.request.id,
            'message': f'Operation {operation} completed successfully'
        }

        return result

    except Exception as exc:
        # Progress recorder will show the error
        progress_recorder.set_progress(
            0, 100,
            description=f"Task failed: {str(exc)}"
        )

        # Re-raise to trigger failure callback
        raise


# Utility functions for task monitoring
def get_task_progress(task_id: str) -> Dict[str, Any]:
    """Get progress information for a task."""
    from celery_progress.backend import Progress

    progress = Progress(task_id)
    return {
        'task_id': task_id,
        'progress': progress.get_info()
    }


def cancel_task(task_id: str) -> Dict[str, Any]:
    """Cancel a running task."""
    from celery import current_app

    current_app.control.revoke(task_id, terminate=True)

    return {
        'success': True,
        'task_id': task_id,
        'message': 'Task cancellation requested'
    }


@shared_task(bind=True)
def create_task_chain(self, user_ids: List[int]) -> Dict[str, Any]:
    """
    Create a chain of tasks for multiple users.

    Args:
        user_ids: List of user IDs to process

    Returns:
        Dict containing chain execution results
    """
    progress_recorder = ProgressRecorder(self)

    try:
        progress_recorder.set_progress(10, 100, description="Building task chain...")

        # Build chain of tasks
        chain_tasks = []
        for i, user_id in enumerate(user_ids):
            # Add progress tracking task
            chain_tasks.append(long_running_task_with_progress.s(duration=3, steps=2))

            # Add email task
            chain_tasks.append(send_welcome_email.s(user_id))

            # Add report generation
            chain_tasks.append(generate_user_analytics_report.s(user_id, 'pdf'))

            progress = 10 + (i * 30 // len(user_ids))
            progress_recorder.set_progress(progress, 100, description=f"Added tasks for user {i+1}/{len(user_ids)}")

        progress_recorder.set_progress(50, 100, description="Executing task chain...")

        # Create and execute the chain
        workflow = chain(*chain_tasks)
        result = workflow.apply_async()

        progress_recorder.set_progress(100, 100, description="Task chain initiated successfully!")

        return {
            'success': True,
            'chain_id': result.id,
            'user_count': len(user_ids),
            'task_count': len(chain_tasks),
            'message': f'Task chain created and executed for {len(user_ids)} users'
        }

    except Exception as exc:
        logger.error(f"Failed to create task chain: {exc}")
        progress_recorder.set_progress(0, 100, description=f"Chain failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task(bind=True)
def conditional_workflow(self, user_id: int) -> Dict[str, Any]:
    """
    Execute a conditional workflow based on user data.

    Args:
        user_id: ID of the user to process

    Returns:
        Dict containing workflow results
    """
    progress_recorder = ProgressRecorder(self)

    try:
        progress_recorder.set_progress(10, 100, description="Analyzing user data...")

        user = User.objects.get(id=user_id)
        workflow_actions = []

        # Determine actions based on user data
        note_count = user.notes.count() if hasattr(user, 'notes') else 0

        progress_recorder.set_progress(30, 100, description="Determining workflow actions...")

        # Always send welcome email for new users
        workflow_actions.append('welcome_email')

        # Send analytics report if user has notes
        if note_count > 0:
            workflow_actions.append('analytics_report')

        # Send achievement notification if user has many notes
        if note_count >= 5:
            workflow_actions.append('achievement_notification')

        progress_recorder.set_progress(50, 100, description=f"Executing {len(workflow_actions)} workflow actions...")

        # Execute workflow actions
        results = []
        for i, action in enumerate(workflow_actions):
            if action == 'welcome_email':
                result = send_welcome_email.delay(user_id)
                results.append({'action': action, 'task_id': result.id})

            elif action == 'analytics_report':
                result = generate_user_analytics_report.delay(user_id, 'pdf')
                results.append({'action': action, 'task_id': result.id})

            elif action == 'achievement_notification':
                result = send_note_notification.delay(
                    user_id=user_id,
                    note_title=f"Achievement: Created {note_count} notes!",
                    action='completed'
                )
                results.append({'action': action, 'task_id': result.id})

            progress = 50 + ((i + 1) * 50 // len(workflow_actions))
            progress_recorder.set_progress(progress, 100, description=f"Executed {i+1}/{len(workflow_actions)} actions")

        progress_recorder.set_progress(100, 100, description="Conditional workflow completed!")

        return {
            'success': True,
            'user_id': user_id,
            'username': user.username,
            'note_count': note_count,
            'workflow_actions': workflow_actions,
            'task_results': results,
            'message': f'Conditional workflow executed {len(workflow_actions)} actions for user {user.username}'
        }

    except User.DoesNotExist:
        progress_recorder.set_progress(0, 100, description="User not found")
        return {
            'success': False,
            'error': f'User with ID {user_id} not found'
        }
    except Exception as exc:
        logger.error(f"Failed to execute conditional workflow for user {user_id}: {exc}")
        progress_recorder.set_progress(0, 100, description=f"Workflow failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc)
        }
