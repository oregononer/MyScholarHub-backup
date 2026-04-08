from django.core.management.base import BaseCommand
from scholarships.models import Category
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Seeds initial scholarship categories'

    def handle(self, *args, **options):
        categories = [
            "STEM (Science, Technology, Engineering, Math)",
            "Humanities & Social Sciences",
            "Business & Management",
            "Healthcare & Medicine",
            "Arts & Design",
            "Law & Public Policy",
            "Education & Teaching",
            "Sports & Athletics"
        ]

        count = 0
        for name in categories:
            # Menggunakan get_or_create berdasarkan nama, jika sudah ada tidak duplicate
            cat, created = Category.objects.get_or_create(
                name=name,
                defaults={'slug': slugify(name), 'is_active': True}
            )
            if created:
                count += 1
                self.stdout.write(self.style.SUCCESS(f'Created category: {name}'))
            else:
                self.stdout.write(f'Category already exists: {name}')

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {count} new categories.'))
