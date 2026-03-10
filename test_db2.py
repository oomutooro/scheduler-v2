import os, json
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scheduler.settings')
django.setup()

from django.core.serializers import serialize
from core.models import FlightRequest

count = FlightRequest.objects.count()
distinct = list(FlightRequest.objects.values('season', 'year').distinct())

data = {
    'count': count,
    'seasons': distinct
}

with open('/Users/omutooro/Desktop/Projects/scheduler-v2/flight_data_dump.json', 'w') as f:
    json.dump(data, f)
