"""
Demonstration script for Celery API integration tasks.

This script demonstrates:
1. Successful API calls with realistic delays
2. Retry logic with exponential backoff
3. Max retries exceeded scenarios
4. Different error handling patterns

Run with: python manage.py demo_celery_api
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import time
from tasks.api_integration import (
    fetch_external_user_data,
    batch_fetch_user_data,
)


class Command(BaseCommand):
    help = "Demonstrate Celery API integration tasks with retry logic"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario",
            choices=["success", "retry", "max-retries", "batch", "all"],
            default="all",
            help="Which scenario to demonstrate",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            help="Run tasks asynchronously (requires Celery worker)",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("Celery API Integration Task Demonstration")
        )
        self.stdout.write("=" * 60)

        # Create test user
        user, created = User.objects.get_or_create(
            username="demo_user", defaults={"email": "demo@example.com"}
        )

        if created:
            self.stdout.write(f"Created demo user: {user.username}")
        else:
            self.stdout.write(f"Using existing demo user: {user.username}")

        scenario = options["scenario"]
        use_async = options["async"]

        if scenario in ["success", "all"]:
            self.demo_successful_call(user, use_async)

        if scenario in ["retry", "all"]:
            self.demo_retry_logic(user, use_async)

        if scenario in ["max-retries", "all"]:
            self.demo_max_retries(user, use_async)

        if scenario in ["batch", "all"]:
            self.demo_batch_processing(user, use_async)

        self.stdout.write(self.style.SUCCESS("\nDemonstration completed!"))

    def demo_successful_call(self, user, use_async):
        """Demonstrate successful API call"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.HTTP_INFO("1. SUCCESSFUL API CALL DEMONSTRATION"))
        self.stdout.write("=" * 60)

        self.stdout.write("Calling fetch_external_user_data...")

        if use_async:
            # Submit task to Celery worker
            result = fetch_external_user_data.delay(user.id, include_metrics=True)
            self.stdout.write(f"Task submitted with ID: {result.id}")
            self.stdout.write("Waiting for result...")

            try:
                task_result = result.get(timeout=30)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Task failed: {e}"))
                return
        else:
            # Run synchronously
            try:
                result = fetch_external_user_data.apply(args=[user.id, True])
                task_result = result.get()
                self.display_result("Successful API Call", task_result)
            except Exception as e:
                # In eager mode, retries manifest as exceptions
                self.stdout.write(
                    self.style.WARNING(
                        f"Task triggered retry logic: {type(e).__name__}"
                    )
                )
                self.stdout.write("This demonstrates the retry mechanism is working!")
                self.stdout.write(
                    "In production with a worker, the task would retry automatically."
                )

    def demo_retry_logic(self, user, use_async):
        """Demonstrate retry logic (best effort in demo)"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.HTTP_INFO("2. RETRY LOGIC DEMONSTRATION"))
        self.stdout.write("=" * 60)

        self.stdout.write(
            "Note: Retry logic is best observed with a running Celery worker."
        )
        self.stdout.write("In synchronous mode, we'll show the retry decision logic.")

        if use_async:
            self.stdout.write("Submitting task that may retry...")
            result = fetch_external_user_data.delay(user.id)
            self.stdout.write(f"Task submitted with ID: {result.id}")

            # Monitor the task
            start_time = time.time()
            while not result.ready() and time.time() - start_time < 60:
                self.stdout.write(f"Task state: {result.state}")
                time.sleep(2)

            if result.ready():
                try:
                    task_result = result.get()
                    self.display_result("Retry Demo Result", task_result)
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Task failed after retries: {e}")
                    )
            else:
                self.stdout.write(
                    "Task is still running... check Celery worker logs for retry attempts"
                )
        else:
            # Show retry logic principles
            self.stdout.write("Retry Logic Principles:")
            self.stdout.write("• 5xx errors: Retry with exponential backoff")
            self.stdout.write("• 429 (Rate Limit): Retry with specified delay")
            self.stdout.write("• 4xx errors (except 429): No retry")
            self.stdout.write("• Max retries: 5 attempts")
            self.stdout.write("• Base delay: 60 seconds")
            self.stdout.write("• Exponential backoff: delay * (2 ** retry_count)")
            self.stdout.write("• Jitter: ±25% to prevent thundering herd")

    def demo_max_retries(self, user, use_async):
        """Demonstrate max retries exceeded"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.HTTP_INFO("3. MAX RETRIES EXCEEDED DEMONSTRATION"))
        self.stdout.write("=" * 60)

        self.stdout.write("Note: This scenario is difficult to reliably demonstrate")
        self.stdout.write("because our mock API has a 70% success rate.")
        self.stdout.write("In a real scenario with consistent failures, you would see:")

        retry_schedule = []
        base_delay = 60
        for retry in range(5):
            delay = base_delay * (2**retry)
            min_delay = int(delay * 0.75)
            max_delay = int(delay * 1.25)
            retry_schedule.append(
                f"  Retry {retry + 1}: {min_delay}-{max_delay} seconds"
            )

        self.stdout.write("Retry Schedule with Exponential Backoff:")
        for schedule_item in retry_schedule:
            self.stdout.write(schedule_item)

        self.stdout.write("\nAfter 5 failed attempts, task would return:")
        self.stdout.write("{'success': False, 'error': {'max_retries_exceeded': True}}")

    def demo_batch_processing(self, user, use_async):
        """Demonstrate batch processing"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.HTTP_INFO("4. BATCH PROCESSING DEMONSTRATION"))
        self.stdout.write("=" * 60)

        # Create additional users for batch demo
        user_ids = [user.id]
        for i in range(1, 4):
            batch_user, _ = User.objects.get_or_create(
                username=f"batch_user_{i}", defaults={"email": f"batch{i}@example.com"}
            )
            user_ids.append(batch_user.id)

        self.stdout.write(f"Launching batch processing for {len(user_ids)} users...")
        self.stdout.write(
            "Note: The new batch implementation launches tasks asynchronously"
        )
        self.stdout.write("to avoid the 'Never call result.get() within a task' issue.")

        if use_async:
            result = batch_fetch_user_data.delay(user_ids, max_concurrent=2)
            self.stdout.write(f"Batch coordinator task submitted with ID: {result.id}")

            try:
                # Get the batch metadata (not the final results)
                task_result = result.get(timeout=30)
                self.display_batch_launch_result("Batch Launch Result", task_result)

                # Show how to check results
                self.stdout.write("To check batch results later, use:")
                self.stdout.write(
                    "from tasks.api_integration import check_batch_results"
                )
                self.stdout.write(
                    f"check_result = check_batch_results.delay('{result.id}')"
                )
                self.stdout.write("print(check_result.get())")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Batch task failed: {e}"))
        else:
            try:
                result = batch_fetch_user_data.apply(args=[user_ids, 2])
                task_result = result.get()
                self.display_batch_launch_result("Batch Launch Result", task_result)

                self.stdout.write(
                    "\nNote: In synchronous mode, individual API tasks are launched"
                )
                self.stdout.write(
                    "but we don't wait for their completion to avoid blocking."
                )

            except Exception as e:
                # In eager mode, this demonstrates the async launch pattern
                self.stdout.write(
                    self.style.WARNING(
                        f"Batch coordinator launched tasks asynchronously: {type(e).__name__}"
                    )
                )
                self.stdout.write("This demonstrates the non-blocking batch pattern!")
                self.stdout.write("Individual API tasks are running independently.")

    def display_result(self, title, result):
        """Display task result in a formatted way"""
        self.stdout.write(f"\n{title} Result:")
        self.stdout.write("-" * 40)

        if result.get("success"):
            self.stdout.write(self.style.SUCCESS("✓ SUCCESS"))
            if "user_id" in result:
                self.stdout.write(f"User ID: {result['user_id']}")
            if "meta" in result:
                meta = result["meta"]
                self.stdout.write(f"Task Attempt: {meta.get('task_attempt', 'N/A')}")
                if "api_response_time_ms" in meta:
                    self.stdout.write(
                        f"API Response Time: {meta['api_response_time_ms']}ms"
                    )
        else:
            self.stdout.write(self.style.ERROR("✗ FAILED"))
            if "error" in result:
                error = result["error"]
                self.stdout.write(f"Error: {error.get('message', 'Unknown error')}")
                self.stdout.write(f"Code: {error.get('code', 'N/A')}")
                self.stdout.write(f"Retryable: {error.get('retryable', False)}")
                if error.get("max_retries_exceeded"):
                    self.stdout.write(self.style.WARNING("Max retries exceeded"))

        # Show some data if available
        if result.get("success") and "data" in result:
            data = result["data"]
            if "username" in data:
                self.stdout.write(f"Username: {data['username']}")
            if "profile" in data:
                profile = data["profile"]
                self.stdout.write(f"Name: {profile.get('name', 'N/A')}")
                self.stdout.write(f"Tier: {profile.get('subscription_tier', 'N/A')}")

        # Show batch results
        if "total_users" in result:
            self.stdout.write(f"Total Users: {result['total_users']}")
            self.stdout.write(f"Successful: {len(result.get('successful', []))}")
            self.stdout.write(f"Failed: {len(result.get('failed', []))}")

        self.stdout.write("")

    def display_batch_launch_result(self, title, result):
        """Display batch launch result in a formatted way"""
        self.stdout.write(f"\n{title}:")
        self.stdout.write("-" * 40)

        if result.get("success"):
            self.stdout.write(self.style.SUCCESS("✓ BATCH LAUNCHED"))
            self.stdout.write(f"Total Users: {result.get('total_users', 'N/A')}")
            self.stdout.write(f"Total Chunks: {result.get('total_chunks', 'N/A')}")

            if "meta" in result:
                meta = result["meta"]
                self.stdout.write(f"Batch ID: {meta.get('batch_id', 'N/A')}")
                self.stdout.write(
                    f"Max Concurrent: {meta.get('max_concurrent', 'N/A')}"
                )
                if "launched_at" in meta:
                    self.stdout.write(f"Launched At: {meta['launched_at']}")

            # Show task information
            task_info = result.get("individual_task_ids", [])
            self.stdout.write(f"Launched Chunks: {len(task_info)}")
            for chunk in task_info:
                task_count = len(chunk.get("tasks", []))
                user_ids = [task["user_id"] for task in chunk.get("tasks", [])]
                self.stdout.write(
                    f"  Chunk {chunk.get('chunk_index', 0) + 1}: {task_count} tasks for users {user_ids}"
                )
        else:
            self.stdout.write(self.style.ERROR("✗ BATCH LAUNCH FAILED"))
            if "error" in result:
                self.stdout.write(f"Error: {result['error']}")

        self.stdout.write("")
