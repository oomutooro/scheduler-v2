import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scheduler.settings')
django.setup()

from django.apps import apps

for model in apps.get_models():
    try:
        count = model.objects.count()
        if count > 0:
            print(f"{model.__name__}: {count}")
    except Exception as e:
        pass
