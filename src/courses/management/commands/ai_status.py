from django.conf import settings
from django.core.management.base import BaseCommand

from courses.ai import get_ai_provider


class Command(BaseCommand):
    help = "Show which AI provider is configured without printing secrets."

    def handle(self, *args, **options):
        provider = get_ai_provider()
        self.stdout.write(f"AI_PROVIDER setting: {settings.AI_PROVIDER}")
        self.stdout.write(f"Provider class: {provider.__class__.__name__}")
        self.stdout.write(f"OPENAI_KEY configured: {bool(settings.OPENAI_KEY)}")
        self.stdout.write(f"OPENAI_MODEL: {settings.OPENAI_MODEL}")
