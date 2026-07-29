from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from documents.models import Department, Category, UserProfile


class Command(BaseCommand):
    help = "Creates initial departments, categories, and test users"

    def handle(self, *args, **options):
        depts = {
            "Urban Planning": ["Building Permits", "Land Use", "Zoning"],
            "Public Works": ["Roads & Infrastructure", "Drainage", "Waste Management"],
            "Health & Sanitation": ["Public Health", "Inspection", "Environmental"],
            "Finance": ["Revenue", "Budget", "Procurement"],
            "Legal Affairs": ["Compliance", "Litigation", "Contracts"],
        }

        for dept_name, categories in depts.items():
            dept, created = Department.objects.get_or_create(name=dept_name)
            if created:
                self.stdout.write(f"Created department: {dept_name}")
            for cat_name in categories:
                cat, cat_created = Category.objects.get_or_create(name=cat_name, department=dept)
                if cat_created:
                    self.stdout.write(f"  - Category: {cat_name}")

        self.stdout.write(self.style.SUCCESS("Setup complete."))
