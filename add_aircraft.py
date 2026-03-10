import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scheduler.settings')
django.setup()

from core.models import AircraftType

new_aircraft = [
    ('B735','Boeing 737-500','Boeing','narrow_body','C',False,132),
    ('B733','Boeing 737-300','Boeing','narrow_body','C',False,148),
    ('B733F','Boeing 737-300 Freighter','Boeing','narrow_body','C',False,0),
    ('B738F','Boeing 737-800 Freighter','Boeing','narrow_body','C',False,0),
    ('B39M','Boeing 737 MAX 9','Boeing','narrow_body','C',False,220),
    ('BCS3','Airbus A220-300','Airbus','narrow_body','C',False,140),
    ('A332','Airbus A330-200','Airbus','wide_body','E',True,250),
    ('B78X','Boeing 787-10 Dreamliner','Boeing','wide_body','E',True,330),
    ('A359','Airbus A350-900','Airbus','wide_body','E',True,315),
    ('A35K','Airbus A350-1000','Airbus','wide_body','E',True,366),
]

results = []
results.append(f"Total aircraft BEFORE: {AircraftType.objects.count()}")

for code,name,mfr,cat,sz,wb,pax in new_aircraft:
    try:
        obj, created = AircraftType.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'manufacturer': mfr,
                'category': cat,
                'size_code': sz,
                'is_wide_body': wb,
                'pax_capacity': pax,
            }
        )
        status = "CREATED" if created else "already exists"
        results.append(f"  {code}: {status}")
    except Exception as e:
        results.append(f"  {code}: ERROR - {str(e)}")

results.append(f"Total aircraft AFTER: {AircraftType.objects.count()}")

log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aircraft_log.txt')
with open(log_path, 'w') as f:
    f.write('\n'.join(results))
