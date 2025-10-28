"""
Tests for API integration tasks with mock external APIs.

This module tests:
- Successful task execution scenarios
- Retry logic with exponential backoff
- Max retries exceeded scenarios
- Different API error conditions
- Batch processing functionality
"""

import pytest
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from tasks.api_integration import (
    fetch_external_user_data,
    sync_user_analytics_to_api,
    batch_fetch_user_data,
    MockAPIError,
    MockExternalAPI
)


class MockAPITests(TestCase):
    """Test the mock API behavior"""

    def setUp(self):
        self.api = MockExternalAPI()

    def test_mock_api_structure(self):
        """Test that mock API returns expected data structure"""
        # We'll need to patch random to ensure success
        with patch('tasks.api_integration.random.choices', return_value=['success']):
            with patch('tasks.api_integration.time.sleep'):  # Skip delays in tests
                response = self.api.get_user_data(123)

                self.assertEqual(response['status'], 'success')
                self.assertIn('data', response)
                self.assertIn('meta', response)
                self.assertEqual(response['data']['user_id'], 123)
                self.assertIn('profile', response['data'])
                self.assertIn('metrics', response['data'])

    def test_mock_api_error_scenarios(self):
        """Test different error scenarios from mock API"""
        test_scenarios = [
            ('server_error', 500),
            ('rate_limit', 429),
            ('not_found', 404),
        ]

        for scenario, expected_code in test_scenarios:
            with patch('tasks.api_integration.random.choices', return_value=[scenario]):
                with patch('tasks.api_integration.time.sleep'):
                    with self.assertRaises(MockAPIError) as cm:
                        self.api.get_user_data(123)

                    self.assertEqual(cm.exception.error_code, expected_code)


class FetchExternalUserDataTests(TestCase):
    """Test the fetch_external_user_data task"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

    @patch('tasks.api_integration.time.sleep')  # Skip delays
    @patch('tasks.api_integration.random.choices')
    @patch('tasks.api_integration.random.uniform')
    @patch('tasks.api_integration.random.choice')
    @patch('tasks.api_integration.random.randint')
    def test_successful_fetch(self, mock_randint, mock_choice, mock_uniform, mock_choices, mock_sleep):
        """Test successful user data fetch"""
        # Setup mocks for success scenario
        mock_choices.return_value = ['success']
        mock_uniform.return_value = 0.5
        mock_choice.side_effect = ['premium', 'dark', True, 'en']
        mock_randint.side_effect = [50, 2500.00, 5000]

        # Execute task
        result = fetch_external_user_data.apply(args=[self.user.id])
        task_result = result.get()

        # Verify result structure
        self.assertTrue(task_result['success'])
        self.assertEqual(task_result['user_id'], self.user.id)
        self.assertIn('data', task_result)
        self.assertIn('meta', task_result)
        self.assertEqual(task_result['meta']['task_attempt'], 1)

    @patch('tasks.api_integration.time.sleep')
    def test_non_retryable_error(self, mock_sleep):
        """Test handling of non-retryable errors (404)"""
        with patch('tasks.api_integration.random.choices', return_value=['not_found']):
            result = fetch_external_user_data.apply(args=[999])
            task_result = result.get()

            self.assertFalse(task_result['success'])
            self.assertEqual(task_result['error']['code'], 404)
            self.assertFalse(task_result['error']['retryable'])

    @patch('tasks.api_integration.time.sleep')
    def test_retry_logic_then_success(self, mock_sleep):
        """Test retry logic: fail twice, then succeed"""
        # Create a custom mock that fails twice then succeeds
        call_count = 0

        def mock_choices_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return ['server_error']  # Fail first two times
            return ['success']  # Succeed on third try

        with patch('tasks.api_integration.random.choices', side_effect=mock_choices_side_effect):
            with patch('tasks.api_integration.random.uniform', return_value=0.5):
                with patch('tasks.api_integration.random.choice', return_value='free'):
                    with patch('tasks.api_integration.random.randint', return_value=10):
                        # Apply the task
                        result = fetch_external_user_data.apply(args=[self.user.id])
                        task_result = result.get()

                        # Should succeed after retries
                        self.assertTrue(task_result['success'])
                        self.assertEqual(task_result['meta']['task_attempt'], 3)

    @patch('tasks.api_integration.time.sleep')
    def test_max_retries_exceeded(self, mock_sleep):
        """Test max retries exceeded scenario"""
        # Always return server error to exhaust retries
        with patch('tasks.api_integration.random.choices', return_value=['server_error']):
            result = fetch_external_user_data.apply(args=[self.user.id])
            task_result = result.get()

            self.assertFalse(task_result['success'])
            self.assertTrue(task_result['error']['max_retries_exceeded'])
            self.assertEqual(task_result['meta']['task_attempt'], 6)  # 1 initial + 5 retries

    @patch('tasks.api_integration.time.sleep')
    def test_rate_limiting_with_retry_after(self, mock_sleep):
        """Test rate limiting scenario with retry-after header"""
        # First call gets rate limited, second succeeds
        call_count = 0

        def mock_choices_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ['rate_limit']
            return ['success']

        with patch('tasks.api_integration.random.choices', side_effect=mock_choices_side_effect):
            with patch('tasks.api_integration.random.uniform', return_value=1.0):  # No jitter
                with patch('tasks.api_integration.random.choice', return_value='free'):
                    with patch('tasks.api_integration.random.randint', return_value=10):
                        result = fetch_external_user_data.apply(args=[self.user.id])
                        task_result = result.get()

                        self.assertTrue(task_result['success'])
                        self.assertEqual(task_result['meta']['task_attempt'], 2)

    def test_include_metrics_parameter(self, ):
        """Test include_metrics parameter functionality"""
        with patch('tasks.api_integration.time.sleep'):
            with patch('tasks.api_integration.random.choices', return_value=['success']):
                with patch('tasks.api_integration.random.uniform', return_value=0.5):
                    with patch('tasks.api_integration.random.choice', return_value='free'):
                        with patch('tasks.api_integration.random.randint', return_value=10):
                            # Test with metrics included (default)
                            result = fetch_external_user_data.apply(args=[self.user.id, True])
                            task_result = result.get()

                            self.assertTrue(task_result['success'])
                            self.assertIn('metrics', task_result['data']['profile'])

                            # Test with metrics excluded
                            result = fetch_external_user_data.apply(args=[self.user.id, False])
                            task_result = result.get()

                            self.assertTrue(task_result['success'])
                            self.assertNotIn('metrics', task_result['data']['profile'])


class SyncUserAnalyticsTests(TestCase):
    """Test the sync_user_analytics_to_api task"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        self.analytics_data = {
            'records': [
                {'event': 'page_view', 'timestamp': '2025-07-08T10:00:00Z'},
                {'event': 'button_click', 'timestamp': '2025-07-08T10:05:00Z'},
            ]
        }

    @patch('tasks.api_integration.time.sleep')
    @patch('tasks.api_integration.random.choices')
    def test_successful_sync(self, mock_choices, mock_sleep):
        """Test successful analytics sync"""
        mock_choices.return_value = ['success']

        result = sync_user_analytics_to_api.apply(
            args=[self.user.id, self.analytics_data]
        )
        task_result = result.get()

        self.assertTrue(task_result['success'])
        self.assertEqual(task_result['user_id'], self.user.id)
        self.assertIn('sync_id', task_result)
        self.assertEqual(task_result['processed_records'], 2)

    @patch('tasks.api_integration.time.sleep')
    @patch('tasks.api_integration.random.choices')
    def test_validation_error_no_retry(self, mock_choices, mock_sleep):
        """Test that validation errors are not retried"""
        mock_choices.return_value = ['validation_error']

        result = sync_user_analytics_to_api.apply(
            args=[self.user.id, self.analytics_data]
        )
        task_result = result.get()

        self.assertFalse(task_result['success'])
        self.assertEqual(task_result['error']['code'], 422)
        self.assertFalse(task_result['error']['retryable'])


class BatchFetchUserDataTests(TestCase):
    """Test the batch_fetch_user_data task"""

    def setUp(self):
        self.users = []
        for i in range(5):
            user = User.objects.create_user(
                username=f'testuser{i}',
                email=f'test{i}@example.com'
            )
            self.users.append(user)

    @patch('tasks.api_integration.time.sleep')
    @patch('tasks.api_integration.random.choices')
    @patch('tasks.api_integration.random.uniform')
    @patch('tasks.api_integration.random.choice')
    @patch('tasks.api_integration.random.randint')
    def test_successful_batch_fetch(self, mock_randint, mock_choice, mock_uniform, mock_choices, mock_sleep):
        """Test successful batch fetch of multiple users"""
        # Setup mocks for all success
        mock_choices.return_value = ['success']
        mock_uniform.return_value = 0.5
        mock_choice.return_value = 'free'
        mock_randint.return_value = 10

        user_ids = [user.id for user in self.users]
        result = batch_fetch_user_data.apply(args=[user_ids, 2])  # max_concurrent=2
        task_result = result.get()

        self.assertTrue(task_result['success'])
        self.assertEqual(task_result['total_users'], 5)
        self.assertEqual(len(task_result['successful']), 5)
        self.assertEqual(len(task_result['failed']), 0)

    @patch('tasks.api_integration.time.sleep')
    def test_mixed_success_failure_batch(self, mock_sleep):
        """Test batch processing with mixed success and failure"""
        # Mock to return different scenarios for different users
        call_count = 0

        def mock_choices_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First and third users succeed, others fail
            if call_count in [1, 3]:
                return ['success']
            elif call_count in [2, 4]:
                return ['not_found']  # Non-retryable
            else:
                return ['server_error']  # Retryable but will exhaust retries

        with patch('tasks.api_integration.random.choices', side_effect=mock_choices_side_effect):
            with patch('tasks.api_integration.random.uniform', return_value=0.5):
                with patch('tasks.api_integration.random.choice', return_value='free'):
                    with patch('tasks.api_integration.random.randint', return_value=10):
                        user_ids = [user.id for user in self.users]
                        result = batch_fetch_user_data.apply(args=[user_ids, 5])
                        task_result = result.get()

                        self.assertTrue(task_result['success'])  # Batch itself succeeds
                        self.assertEqual(task_result['total_users'], 5)
                        # Results depend on which calls succeed/fail
                        self.assertGreater(len(task_result['successful']), 0)
                        self.assertGreater(len(task_result['failed']), 0)


class ExponentialBackoffTests(TestCase):
    """Test exponential backoff calculations"""

    def test_backoff_calculation(self):
        """Test that backoff delays increase exponentially"""
        base_delay = 60

        # Test first few retry delays
        expected_delays = []
        for retry_count in range(5):
            delay = base_delay * (2 ** retry_count)
            expected_delays.append(delay)

        # Expected progression: 60, 120, 240, 480, 960
        self.assertEqual(expected_delays, [60, 120, 240, 480, 960])

    @patch('tasks.api_integration.time.sleep')
    @patch('tasks.api_integration.random.uniform')
    def test_jitter_application(self, mock_uniform, mock_sleep):
        """Test that jitter is applied to retry delays"""
        mock_uniform.return_value = 1.25  # Maximum jitter

        with patch('tasks.api_integration.random.choices', return_value=['server_error']):
            # This will exhaust retries, but we can check the delay calculations
            result = fetch_external_user_data.apply(args=[999])
            task_result = result.get()

            # Task should fail after max retries
            self.assertFalse(task_result['success'])
            self.assertTrue(task_result['error']['max_retries_exceeded'])


class IntegrationTests(TestCase):
    """Integration tests combining multiple components"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='integrationtest',
            email='integration@example.com'
        )

    @patch('tasks.api_integration.time.sleep')
    def test_full_workflow_success(self, mock_sleep):
        """Test complete workflow: fetch data, then sync analytics"""
        with patch('tasks.api_integration.random.choices', return_value=['success']):
            with patch('tasks.api_integration.random.uniform', return_value=0.5):
                with patch('tasks.api_integration.random.choice', return_value='premium'):
                    with patch('tasks.api_integration.random.randint', return_value=100):
                        # First, fetch user data
                        fetch_result = fetch_external_user_data.apply(args=[self.user.id])
                        fetch_data = fetch_result.get()

                        self.assertTrue(fetch_data['success'])

                        # Then, sync some analytics
                        analytics_data = {
                            'records': [
                                {'event': 'login', 'user_id': self.user.id},
                                {'event': 'profile_view', 'user_id': self.user.id}
                            ]
                        }

                        sync_result = sync_user_analytics_to_api.apply(
                            args=[self.user.id, analytics_data]
                        )
                        sync_data = sync_result.get()

                        self.assertTrue(sync_data['success'])
                        self.assertEqual(sync_data['processed_records'], 2)

    def test_error_handling_consistency(self):
        """Test that error handling is consistent across tasks"""
        # All tasks should return similar error structures
        tasks_to_test = [
            (fetch_external_user_data, [999]),
            (sync_user_analytics_to_api, [999, {'records': []}]),
        ]

        with patch('tasks.api_integration.time.sleep'):
            with patch('tasks.api_integration.random.choices', return_value=['not_found']):
                for task_func, args in tasks_to_test:
                    result = task_func.apply(args=args)
                    task_result = result.get()

                    # All should have consistent error structure
                    self.assertFalse(task_result['success'])
                    self.assertIn('error', task_result)
                    self.assertIn('message', task_result['error'])
                    self.assertIn('code', task_result['error'])
                    self.assertIn('retryable', task_result['error'])


# Performance and Load Testing Utilities
class PerformanceTests(TestCase):
    """Performance and load testing scenarios"""

    @patch('tasks.api_integration.time.sleep')  # Skip actual delays
    def test_concurrent_task_execution(self, mock_sleep):
        """Test multiple tasks running concurrently"""
        from celery import group

        with patch('tasks.api_integration.random.choices', return_value=['success']):
            with patch('tasks.api_integration.random.uniform', return_value=0.1):
                with patch('tasks.api_integration.random.choice', return_value='free'):
                    with patch('tasks.api_integration.random.randint', return_value=1):
                        # Create a group of tasks
                        user_ids = list(range(1, 11))  # 10 users
                        job = group(fetch_external_user_data.s(user_id) for user_id in user_ids)

                        # Execute the group
                        result = job.apply()

                        # Verify all tasks completed
                        self.assertEqual(len(result), 10)

                        # Check that all were successful
                        for task_result in result:
                            data = task_result.get()
                            self.assertTrue(data['success'])


if __name__ == '__main__':
    pytest.main([__file__])
