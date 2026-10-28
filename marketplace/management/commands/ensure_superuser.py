import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Idempotently creates a superuser and configures Site + Google OAuth from environment variables."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin").strip()
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@allthings.com").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "").strip()

        # 1. Ensure Superuser Exists
        if not password:
            self.stdout.write(
                self.style.WARNING(
                    "Skipping superuser creation: DJANGO_SUPERUSER_PASSWORD is not set."
                )
            )
        else:
            user = User.objects.filter(username=username).first() or User.objects.filter(email=email).first()
            if not user:
                User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                )
                self.stdout.write(self.style.SUCCESS(f"✓ Created superuser '{username}' ({email})."))
            else:
                updated = False
                if not user.is_superuser or not user.is_staff:
                    user.is_superuser = True
                    user.is_staff = True
                    updated = True
                if os.environ.get("RESET_SUPERUSER_PASSWORD", "").lower() in ("true", "1", "yes"):
                    user.set_password(password)
                    updated = True
                if updated:
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f"✓ Updated superuser permissions for '{user.username}'."))
                else:
                    self.stdout.write(f"• Superuser '{user.username}' already exists.")

        # 2. Update Django Site Domain for allauth & absolute links
        domain = (
            os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
            or os.environ.get("SITE_URL", "").replace("https://", "").replace("http://", "").strip("/")
            or "127.0.0.1:8000"
        )
        site, _ = Site.objects.update_or_create(
            id=getattr(settings, "SITE_ID", 1),
            defaults={
                "domain": domain,
                "name": "AllThings Marketplace",
            },
        )
        self.stdout.write(self.style.SUCCESS(f"✓ Configured Site (ID={site.id}) domain -> {domain}"))

        # 3. Auto-Configure Google OAuth SocialApp if credentials are in env
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()

        if client_id and client_secret:
            try:
                from allauth.socialaccount.models import SocialApp

                social_app, _ = SocialApp.objects.update_or_create(
                    provider="google",
                    defaults={
                        "name": "Google Login",
                        "client_id": client_id,
                        "secret": client_secret,
                        "key": "",
                    },
                )
                social_app.sites.add(site)
                self.stdout.write(self.style.SUCCESS("✓ Linked Google OAuth SocialApp to Site."))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Could not configure Google SocialApp: {exc}"))