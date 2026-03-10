import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scheduler.settings')
django.setup()

from core.models import FlightRequest

print('Total flights:', FlightRequest.objects.count())
print('Distinct seasons/years:', list(FlightRequest.objects.values('season', 'year').distinct()))
