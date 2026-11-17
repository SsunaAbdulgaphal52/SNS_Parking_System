from django.contrib import admin
from .models import CarOwner, Car, ParkingLot, ParkingSpot, Ticket, Payment, LotStaff

admin.site.register(CarOwner)
admin.site.register(Car)
admin.site.register(ParkingLot)
admin.site.register(ParkingSpot)
admin.site.register(Ticket)
admin.site.register(Payment)
admin.site.register(LotStaff)
