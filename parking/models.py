import datetime
import math
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Parking fee: 1000 UGX for every hour (or part of an hour)
RATE_PER_HOUR = 1000


class CarOwner(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]

    owner_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone_no = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)

    def __str__(self):
        return self.name + " " + self.last_name


class Car(models.Model):
    car_id = models.AutoField(primary_key=True)
    car_plate = models.CharField(max_length=15)
    model = models.CharField(max_length=50)
    color = models.CharField(max_length=30)
    year_of_manufacture = models.PositiveIntegerField()
    owner = models.ForeignKey(CarOwner, on_delete=models.CASCADE)

    def __str__(self):
        return self.car_plate

    def is_parked(self):
        return Ticket.objects.filter(car_plate=self.car_plate, exit_time__isnull=True).exists()


class ParkingLot(models.Model):
    lot_id = models.AutoField(primary_key=True)
    lot_name = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField()
    location = models.CharField(max_length=100)

    def __str__(self):
        return self.lot_name

    # Runs every time a lot is saved (added or edited)
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.create_spots()

    # Makes sure the lot has exactly "capacity" spots
    def create_spots(self):
        spots = ParkingSpot.objects.filter(lot=self).order_by('spot_id')
        count = spots.count()

        # Too few spots: create the missing ones
        for i in range(self.capacity - count):
            ParkingSpot.objects.create(
                lot=self,
                lot_name=self.lot_name,
                capacity=self.capacity,
                location=self.location,
            )

        # Too many spots (capacity was lowered): remove from the end, but only free spots
        if count > self.capacity:
            extra_spots = list(spots.order_by('-spot_id')[:count - self.capacity])
            for spot in extra_spots:
                if not spot.is_occupied():
                    spot.delete()

        ParkingSpot.objects.filter(lot=self).update(
            lot_name=self.lot_name,
            capacity=self.capacity,
            location=self.location,
        )


class ParkingSpot(models.Model):
    spot_id = models.AutoField(primary_key=True)
    lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE)
    lot_name = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField()
    location = models.CharField(max_length=100)

    def number(self):
        return ParkingSpot.objects.filter(lot=self.lot, spot_id__lte=self.spot_id).count()

    # The open ticket (car without exit time) on this spot, or None if the spot is free
    def current_ticket(self):
        return Ticket.objects.filter(spot=self, exit_time__isnull=True).first()

    def is_occupied(self):
        return self.current_ticket() is not None

    def __str__(self):
        return "Spot " + str(self.number()) + " (" + self.lot_name + ")"


class Ticket(models.Model):
    ticket_id = models.AutoField(primary_key=True)
    car_plate = models.CharField(max_length=15)
    spot = models.ForeignKey(ParkingSpot, on_delete=models.CASCADE)
    entry_time = models.DateTimeField()
    exit_time = models.DateTimeField(null=True, blank=True)
    ticket_date = models.DateField(default=datetime.date.today)

    def __str__(self):
        return "Ticket " + str(self.ticket_id) + " - " + self.car_plate

    # Number of hours to pay for. Part of an hour counts as a full hour,
    # and the minimum is 1 hour.
    def hours_charged(self, end_time=None):
        if end_time is None:
            end_time = self.exit_time or timezone.now()
        seconds = (end_time - self.entry_time).total_seconds()
        hours = math.ceil(seconds / 3600)
        if hours < 1:
            hours = 1
        return hours

    # The fee = hours charged x rate per hour
    def fee(self, end_time=None):
        return self.hours_charged(end_time) * RATE_PER_HOUR

    # Find the car that has this ticket's plate (it has the owner)
    def get_car(self):
        return Car.objects.filter(car_plate=self.car_plate).first()


class Payment(models.Model):
    METHOD_CHOICES = [
        ('Cash', 'Cash'),
        ('Mobile Money', 'Mobile Money'),
        ('Card', 'Card'),
    ]
    STATUS_CHOICES = [
        ('Paid', 'Paid'),
        ('Pending', 'Pending'),
    ]

    payment_id = models.AutoField(primary_key=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    payment_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    payment_date = models.DateField(default=datetime.date.today)

    def __str__(self):
        return "Payment " + str(self.payment_id)


# Links a user (attendant) to a lot they are allowed to work in.
# One row = one user allowed in one lot.
class LotStaff(models.Model):
    staff_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE)

    def __str__(self):
        return self.user.username + " - " + self.lot.lot_name
