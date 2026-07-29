from django.core.management.base import BaseCommand
from documents.crypto_utils import generate_keypair


class Command(BaseCommand):
    help = "Generate RSA signing key pair for document integrity"

    def handle(self, *args, **options):
        generate_keypair()
        self.stdout.write(self.style.SUCCESS("RSA 4096-bit key pair generated in keys/ directory"))
