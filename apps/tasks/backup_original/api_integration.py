"""
External API integration tasks with retry logic and exponential backoff.

This module demonstrates:
- External API communication patterns
- Exponential backoff retry strategies
- Error handling and recovery
- Realistic API response simulation
"""

import logging
import random
import time
from typing import Dict, Any, Optional
from django.utils import timezone
from celery import shared_task

logger = logging.getLogger(__name__)


class MockAPIError(Exception):
    """Custom exception for API errors"""
    def __init__(self, message: str, error_code: int, retry_after: Optional[int] = None):
        self.message = message
        self.error_code = error_code
        self.retry_after = retry_after
        super().__init__(self.message)


class MockExternalAPI:
    """
    Mock external API that simulates realistic behavior including:
    - Random success/failure responses
    - Variable response times
    - Different types of errors
    - Rate limiting with retry-after headers
    """

    def __init__(self):
        self.base_url = "https://api.example.com"
        self.api_key = "mock_api_key_12345"

    def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """
        Mock API endpoint to fetch user data
        Simulates various response scenarios
        """
        # Simulate network delay (50ms to 2 seconds)
        delay = random.uniform(0.05, 2.0)
        time.sleep(delay)

        # Simulate different response scenarios
        scenario = random.choices(
            ['success', 'server_error', 'rate_limit', 'not_found', 'timeout'],
            weights=[70, 10, 10, 5, 5]  # 70% success rate
        )[0]

        logger.info(f"Mock API call for user {user_id}: scenario={scenario}, delay={delay:.2f}s")

        if scenario == 'success':
            return {
                'status': 'success',
                'data': {
                    'user_id': user_id,
                    'username': f'user_{user_id}',
                    'email': f'user_{user_id}@example.com',
                    'profile': {
                        'name': f'User {user_id}',
                        'registration_date': '2024-01-15T10:30:00Z',
                        'subscription_tier': random.choice(['free', 'premium', 'enterprise']),
                        'last_login': timezone.now().isoformat(),
                        'preferences': {
                            'theme': random.choice(['light', 'dark']),
                            'notifications': random.choice([True, False]),
                            'language': random.choice(['en', 'es', 'fr', 'de'])
                        }
                    },
                    'metrics': {
                        'total_orders': random.randint(0, 100),
                        'total_spent': round(random.uniform(0, 5000), 2),
                        'loyalty_points': random.randint(0, 10000)
                    }
                },
                'meta': {
                    'api_version': '2.1',
                    'response_time_ms': int(delay * 1000),
                    'cached': random.choice([True, False])
                }
            }

        elif scenario == 'server_error':
            raise MockAPIError("Internal server error", 500, retry_after=30)

        elif scenario == 'rate_limit':
            raise MockAPIError("Rate limit exceeded", 429, retry_after=60)

        elif scenario == 'not_found':
            raise MockAPIError(f"User {user_id} not found", 404)

        elif scenario == 'timeout':
            # Simulate timeout by taking too long
            time.sleep(5)  # This would trigger a timeout in real scenarios
            raise MockAPIError("Request timeout", 408, retry_after=10)

    def sync_user_analytics(self, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mock API endpoint to sync user analytics data
        """
        # Simulate processing delay
        delay = random.uniform(0.1, 1.5)
        time.sleep(delay)

        scenario = random.choices(
            ['success', 'validation_error', 'server_error'],
            weights=[80, 15, 5]
        )[0]

        logger.info(f"Mock API sync for user {user_id}: scenario={scenario}")

        if scenario == 'success':
            return {
                'status': 'success',
                'sync_id': f'sync_{user_id}_{int(time.time())}',
                'processed_records': len(data.get('records', [])),
                'timestamp': timezone.now().isoformat()
            }

        elif scenario == 'validation_error':
            raise MockAPIError("Invalid data format", 422)

        elif scenario == 'server_error':
            raise MockAPIError("Database connection failed", 503, retry_after=45)


# Initialize mock API instance
mock_api = MockExternalAPI()


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def fetch_external_user_data(self, user_id: int, include_metrics: bool = True) -> Dict[str, Any]:
    """
    Fetch user data from external API with exponential backoff retry logic.

    Args:
        user_id: The ID of the user to fetch
        include_metrics: Whether to include user metrics in response

    Returns:
        Dict containing user data or error information

    Retry Strategy:
        - Max retries: 5
        - Base delay: 60 seconds
        - Exponential backoff: delay * (2 ** retry_count)
        - Jitter: ±25% to prevent thundering herd
    """
    try:
        logger.info(f"Fetching user data for user_id={user_id}, attempt={self.request.retries + 1}")

        # Call the mock external API
        api_response = mock_api.get_user_data(user_id)

        # Process the successful response
        result = {
            'success': True,
            'user_id': user_id,
            'data': api_response['data'],
            'meta': {
                'api_response_time_ms': api_response['meta']['response_time_ms'],
                'api_version': api_response['meta']['api_version'],
                'cached': api_response['meta']['cached'],
                'task_attempt': self.request.retries + 1,
                'fetched_at': timezone.now().isoformat()
            }
        }

        # Filter out metrics if not requested
        if not include_metrics:
            result['data'].pop('metrics', None)

        logger.info(f"Successfully fetched user data for user_id={user_id}")
        return result

    except MockAPIError as exc:
        logger.warning(f"API error for user_id={user_id}: {exc.message} (code: {exc.error_code})")

        # Don't retry on client errors (4xx)
        if 400 <= exc.error_code < 500 and exc.error_code != 429:  # Except rate limiting
            logger.error(f"Non-retryable error for user_id={user_id}: {exc.message}")
            return {
                'success': False,
                'user_id': user_id,
                'error': {
                    'message': exc.message,
                    'code': exc.error_code,
                    'retryable': False
                },
                'meta': {
                    'task_attempt': self.request.retries + 1,
                    'failed_at': timezone.now().isoformat()
                }
            }

        # Implement exponential backoff with jitter for retryable errors
        if self.request.retries < self.max_retries:
            # Calculate exponential backoff delay
            base_delay = exc.retry_after if exc.retry_after else self.default_retry_delay
            exponential_delay = base_delay * (2 ** self.request.retries)

            # Add jitter (±25% of the delay) to prevent thundering herd
            jitter = random.uniform(0.75, 1.25)
            retry_delay = int(exponential_delay * jitter)

            logger.info(
                f"Retrying user_id={user_id} in {retry_delay}s "
                f"(attempt {self.request.retries + 1}/{self.max_retries})"
            )

            raise self.retry(exc=exc, countdown=retry_delay)

        # Max retries exceeded
        logger.error(f"Max retries exceeded for user_id={user_id}: {exc.message}")
        return {
            'success': False,
            'user_id': user_id,
            'error': {
                'message': f'Max retries exceeded: {exc.message}',
                'code': exc.error_code,
                'retryable': False,
                'max_retries_exceeded': True
            },
            'meta': {
                'task_attempt': self.request.retries + 1,
                'failed_at': timezone.now().isoformat()
            }
        }

    except Exception as exc:
        logger.error(f"Unexpected error for user_id={user_id}: {exc}")

        # For unexpected errors, retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = self.default_retry_delay * (2 ** self.request.retries)
            jitter = random.uniform(0.75, 1.25)
            retry_delay = int(retry_delay * jitter)

            logger.info(f"Retrying user_id={user_id} after unexpected error in {retry_delay}s")
            raise self.retry(exc=exc, countdown=retry_delay)

        return {
            'success': False,
            'user_id': user_id,
            'error': {
                'message': f'Unexpected error: {str(exc)}',
                'code': 500,
                'retryable': False,
                'max_retries_exceeded': True
            },
            'meta': {
                'task_attempt': self.request.retries + 1,
                'failed_at': timezone.now().isoformat()
            }
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def sync_user_analytics_to_api(self, user_id: int, analytics_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sync user analytics data to external API with retry logic.

    Args:
        user_id: The ID of the user
        analytics_data: Analytics data to sync

    Returns:
        Dict containing sync results
    """
    try:
        logger.info(f"Syncing analytics for user_id={user_id}, attempt={self.request.retries + 1}")

        # Call the mock external API
        api_response = mock_api.sync_user_analytics(user_id, analytics_data)

        logger.info(f"Successfully synced analytics for user_id={user_id}")
        return {
            'success': True,
            'user_id': user_id,
            'sync_id': api_response['sync_id'],
            'processed_records': api_response['processed_records'],
            'meta': {
                'task_attempt': self.request.retries + 1,
                'synced_at': timezone.now().isoformat()
            }
        }

    except MockAPIError as exc:
        logger.warning(f"API sync error for user_id={user_id}: {exc.message}")

        # Don't retry validation errors
        if exc.error_code == 422:
            return {
                'success': False,
                'user_id': user_id,
                'error': {
                    'message': exc.message,
                    'code': exc.error_code,
                    'retryable': False
                }
            }

        # Retry server errors
        if self.request.retries < self.max_retries:
            retry_delay = (exc.retry_after or self.default_retry_delay) * (2 ** self.request.retries)
            logger.info(f"Retrying sync for user_id={user_id} in {retry_delay}s")
            raise self.retry(exc=exc, countdown=retry_delay)

        return {
            'success': False,
            'user_id': user_id,
            'error': {
                'message': f'Max retries exceeded: {exc.message}',
                'code': exc.error_code,
                'retryable': False,
                'max_retries_exceeded': True
            }
        }


@shared_task(bind=True, max_retries=3)
def batch_fetch_user_data(self, user_ids: list[int], max_concurrent: int = 5) -> Dict[str, Any]:
    """
    Fetch user data for multiple users with controlled concurrency.

    This task orchestrates the batch operation by launching individual tasks
    without waiting for results, completely avoiding synchronous calls.

    Args:
        user_ids: List of user IDs to fetch
        max_concurrent: Maximum number of concurrent API calls

    Returns:
        Dict containing batch operation metadata and task IDs
    """
    try:
        logger.info(f"Starting batch fetch for {len(user_ids)} users (max_concurrent={max_concurrent})")

        # Split user_ids into chunks for controlled concurrency
        chunks = [user_ids[i:i + max_concurrent] for i in range(0, len(user_ids), max_concurrent)]

        batch_metadata = {
            'success': True,
            'total_users': len(user_ids),
            'total_chunks': len(chunks),
            'individual_task_ids': [],
            'meta': {
                'started_at': timezone.now().isoformat(),
                'batch_id': self.request.id,
                'max_concurrent': max_concurrent
            }
        }

        # Launch all tasks individually to avoid group synchronization issues
        for chunk_idx, chunk in enumerate(chunks):
            logger.info(f"Launching chunk {chunk_idx + 1}/{len(chunks)} with {len(chunk)} users")

            chunk_tasks = []
            # Launch each task individually to avoid any group-related synchronous behavior
            for user_id in chunk:
                task_result = fetch_external_user_data.delay(user_id)
                chunk_tasks.append({
                    'user_id': user_id,
                    'task_id': task_result.id
                })

            # Store task information for this chunk
            batch_metadata['individual_task_ids'].append({
                'chunk_index': chunk_idx,
                'tasks': chunk_tasks
            })

        batch_metadata['meta']['launched_at'] = timezone.now().isoformat()

        logger.info(
            f"Batch fetch launched: {len(chunks)} chunks with {len(user_ids)} total users. "
            f"Use batch_id {self.request.id} to monitor progress."
        )

        return batch_metadata

    except Exception as exc:
        logger.error(f"Batch fetch launch error: {exc}")

        if self.request.retries < self.max_retries:
            retry_delay = 60 * (2 ** self.request.retries)
            logger.info(f"Retrying batch fetch launch in {retry_delay}s")
            raise self.retry(exc=exc, countdown=retry_delay)

        return {
            'success': False,
            'error': f'Batch fetch launch failed: {str(exc)}',
            'total_users': len(user_ids),
            'meta': {
                'failed_at': timezone.now().isoformat(),
                'max_retries_exceeded': True
            }
        }


@shared_task
def check_batch_results(batch_id: str) -> Dict[str, Any]:
    """
    Check the results of a batch operation by batch ID.

    This is a separate task that can be called to check the status
    of a batch operation without blocking.

    Args:
        batch_id: The batch task ID returned from batch_fetch_user_data

    Returns:
        Dict containing aggregated results from the batch operation
    """
    from celery.result import AsyncResult

    try:
        # Get the batch task result
        batch_task = AsyncResult(batch_id)

        if not batch_task.ready():
            return {
                'batch_complete': False,
                'status': batch_task.status,
                'message': 'Batch operation still in progress'
            }

        batch_meta = batch_task.result
        if not batch_meta.get('success', False):
            return {
                'batch_complete': True,
                'success': False,
                'error': batch_meta.get('error', 'Batch operation failed')
            }

        # Aggregate results from all chunks
        aggregated_results = {
            'batch_complete': True,
            'success': True,
            'total_users': batch_meta['total_users'],
            'successful': [],
            'failed': [],
            'in_progress': [],
            'meta': batch_meta['meta']
        }

        # Check each chunk's results
        for chunk_info in batch_meta.get('individual_task_ids', []):
            for task_info in chunk_info.get('tasks', []):
                task_id = task_info['task_id']
                user_id = task_info['user_id']
                task_result = AsyncResult(task_id)

                if task_result.ready():
                    try:
                        result = task_result.result
                        if result and result.get('success', False):
                            aggregated_results['successful'].append(result)
                        else:
                            # Add user_id to failed result if missing
                            failed_result = result or {'success': False, 'user_id': user_id}
                            if 'user_id' not in failed_result:
                                failed_result['user_id'] = user_id
                            aggregated_results['failed'].append(failed_result)
                    except Exception as e:
                        aggregated_results['failed'].append({
                            'success': False,
                            'user_id': user_id,
                            'error': {'message': f'Task error: {str(e)}', 'code': 500}
                        })
                else:
                    aggregated_results['in_progress'].append({
                        'task_id': task_id,
                        'user_id': user_id,
                        'status': task_result.status
                    })

        # Update completion status
        if aggregated_results['in_progress']:
            aggregated_results['batch_complete'] = False
            aggregated_results['message'] = f"{len(aggregated_results['in_progress'])} tasks still in progress"
        else:
            aggregated_results['meta']['completed_at'] = timezone.now().isoformat()

        logger.info(
            f"Batch {batch_id} status: {len(aggregated_results['successful'])} successful, "
            f"{len(aggregated_results['failed'])} failed, "
            f"{len(aggregated_results['in_progress'])} in progress"
        )

        return aggregated_results

    except Exception as exc:
        logger.error(f"Error checking batch results for {batch_id}: {exc}")
        return {
            'batch_complete': True,
            'success': False,
            'error': f'Failed to check batch results: {str(exc)}'
        }
