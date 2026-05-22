import time

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Simple daily scheduler for self-hosted deployments."

    def add_arguments(self, parser):
        parser.add_argument("--interval-seconds", type=int, default=86400)

    def handle(self, *args, **options):
        interval = options["interval_seconds"]
        self.stdout.write(f"Starting scheduler with {interval}s interval.")
        while True:
            call_command("generate_daily_lessons")
            time.sleep(interval)
