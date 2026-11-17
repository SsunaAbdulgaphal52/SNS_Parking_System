
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the assessment administrator account."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_ADMIN_USERNAME", "admin")
        password = os.environ.get("DJANGO_ADMIN_PASSWORD")

        if not password:
            raise CommandError("DJANGO_ADMIN_PASSWORD is required.")

        User = get_user_model()
        lookup = {User.USERNAME_FIELD: username}
        user = User.objects.filter(**lookup).first()

        if user is None:
            User.objects.create_superuser(
                **{User.USERNAME_FIELD: username},
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS("Assessment admin created.")
            )
        else:
    self.stdout.write(
        self.style.WARNING(
            "Admin account already exists. No changes made."
        )
    )