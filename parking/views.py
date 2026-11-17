from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.utils import timezone

from .models import CarOwner, Car, ParkingLot, ParkingSpot, Ticket, Payment, LotStaff
from .forms import CarOwnerForm, CarForm, ParkingLotForm, TicketForm, PaymentForm
from .forms import ParkCarForm, CheckoutForm, StaffCreateForm, StaffLotsForm


# WHO CAN DO WHAT 
#   Manager   = a user with is_staff True. Sees and manages every lot.
#   Attendant = any other user. Works only in the lots linked to them
#               in the LotStaff table.

# Stops the request with a "not allowed" page if the user is not a manager
def check_manager(request):
    if not request.user.is_staff:
        raise PermissionDenied


# The lots this user may work in
def allowed_lots(user):
    if user.is_staff:
        return ParkingLot.objects.all()
    return ParkingLot.objects.filter(lotstaff__user=user)


# True if this user may work in this lot
def can_use_lot(user, lot):
    return allowed_lots(user).filter(pk=lot.pk).exists()


# The cars a user may see: a manager sees all, an attendant sees the cars that have had a ticket in one of his or her lots
def visible_cars(user):
    if user.is_staff:
        return Car.objects.all()
    plates = Ticket.objects.filter(spot__lot__in=allowed_lots(user)).values_list('car_plate', flat=True)
    return Car.objects.filter(car_plate__in=plates)


# The owners a user may see (the owners of the visible cars)
def visible_owners(user):
    if user.is_staff:
        return CarOwner.objects.all()
    owner_ids = visible_cars(user).values_list('owner_id', flat=True)
    return CarOwner.objects.filter(owner_id__in=owner_ids)



# For one lot: a list with every spot, its number and its open ticket (None = free)
def get_spot_rows(lot):
    rows = []
    number = 1
    for spot in ParkingSpot.objects.filter(lot=lot).order_by('spot_id'):
        rows.append({'spot': spot, 'number': number, 'ticket': spot.current_ticket()})
        number = number + 1
    return rows


# For the given lots: their spots and how many are free and occupied
def get_lot_blocks(lots):
    blocks = []
    for lot in lots:
        rows = get_spot_rows(lot)
        occupied = 0
        for row in rows:
            if row['ticket'] is not None:
                occupied = occupied + 1
        blocks.append({
            'lot': lot,
            'rows': rows,
            'occupied': occupied,
            'free': len(rows) - occupied,
        })
    return blocks


# DASHBOARD (protected: @login_required sends anyone who is not
# logged in to the login page

@login_required
def dashboard(request):
    lots = allowed_lots(request.user)
    tickets = Ticket.objects.filter(spot__lot__in=lots)
    payments = Payment.objects.filter(ticket__spot__lot__in=lots)
    total_paid = payments.filter(payment_status='Paid').aggregate(total=Sum('amount'))['total']

    lot_blocks = get_lot_blocks(lots)
    occupied_count = 0
    free_count = 0
    for block in lot_blocks:
        occupied_count = occupied_count + block['occupied']
        free_count = free_count + block['free']

    # The cars that are parked right now, with their owner, hours so far and fee so far
    parked_rows = []
    for ticket in tickets.filter(exit_time__isnull=True).order_by('entry_time'):
        car = ticket.get_car()
        parked_rows.append({
            'ticket': ticket,
            'car': car,
            'owner': car.owner if car else None,
            'hours': ticket.hours_charged(),
            'fee': ticket.fee(),
        })

    context = {
        'owner_count': CarOwner.objects.count(),
        'car_count': Car.objects.count(),
        'lot_count': lots.count(),
        'spot_count': occupied_count + free_count,
        'occupied_count': occupied_count,
        'free_count': free_count,
        'ticket_count': tickets.count(),
        'payment_count': payments.count(),
        'total_paid': total_paid or 0,
        'lot_blocks': lot_blocks,
        'parked_rows': parked_rows,
    }
    return render(request, 'parking/dashboard.html', context)


# PARK A CAR: step 1 choose the lot, step 2 click a spot and fill the form

@login_required
def park_car(request):
    blocks = get_lot_blocks(allowed_lots(request.user))
    return render(request, 'parking/park_lots.html', {'lot_blocks': blocks})

 
@login_required
def park_lot(request, lot_id):
    lot = get_object_or_404(ParkingLot, pk=lot_id)

    # An attendant can not work in a lot that is not assigned to him or her
    if not can_use_lot(request.user, lot):
        raise PermissionDenied

    if request.method == 'POST':
        form = ParkCarForm(lot, request.POST)
        if form.is_valid():
            data = form.cleaned_data

            # 1. Is this car already in our system? (same number plate)
            car = Car.objects.filter(car_plate=data['car_plate']).first()

            if car is None:
                # 2. New car: find the owner by phone number, or create the owner
                owner = CarOwner.objects.filter(phone_no=data['phone_no']).first()
                if owner is None:
                    owner = CarOwner.objects.create(
                        name=data['name'],
                        last_name=data['last_name'],
                        phone_no=data['phone_no'],
                        email=data['email'],
                        address=data['address'],
                        gender=data['gender'],
                    )
                # 3. Create the car
                car = Car.objects.create(
                    car_plate=data['car_plate'],
                    model=data['model'],
                    color=data['color'],
                    year_of_manufacture=data['year_of_manufacture'],
                    owner=owner,
                )

            # 4. Create the ticket: the car is now parked in the chosen spot
            Ticket.objects.create(
                car_plate=car.car_plate,
                spot=data['spot'],
                entry_time=timezone.now(),
            )
            return redirect('dashboard')
    else:
        form = ParkCarForm(lot)

    context = {'form': form, 'lot': lot, 'rows': get_spot_rows(lot)}
    return render(request, 'parking/park_form.html', context)


# CHECK OUT (from the dashboard): saves the exit time and goes back to the
# dashboard. The payment is made later on the Make Payment page.

@login_required
def checkout(request, pk):
    # Only tickets that are still open (no exit time) can be checked out
    ticket = get_object_or_404(Ticket, pk=pk, exit_time__isnull=True)

    if not can_use_lot(request.user, ticket.spot.lot):
        raise PermissionDenied

    if request.method == 'POST':
        # The exit time is the moment the check out is confirmed
        ticket.exit_time = timezone.now()
        ticket.save()
        return redirect('dashboard')

    now = timezone.now()
    car = ticket.get_car()
    context = {
        'ticket': ticket,
        'car': car,
        'owner': car.owner if car else None,
        'now': now,
        'hours': ticket.hours_charged(now),
        'fee': ticket.fee(now),
    }
    return render(request, 'parking/checkout.html', context)


# MAKE A PAYMENT: choose an unpaid ticket, the amount comes by itself

@login_required
def make_payment(request):
    # Unpaid tickets, only from the lots this user may work in
    unpaid_tickets = Ticket.objects.filter(spot__lot__in=allowed_lots(request.user))
    unpaid_tickets = unpaid_tickets.exclude(payment__payment_status='Paid').order_by('-ticket_id')

    # The chosen ticket number comes from the address or from the form
    ticket_id = request.GET.get('ticket') or request.POST.get('ticket')
    ticket = None
    if ticket_id and ticket_id.isdigit():
        ticket = unpaid_tickets.filter(pk=ticket_id).first()

    now = timezone.now()
    hours = None
    fee = None
    owner = None
    if ticket is not None:
        # A car that already left is charged until its exit time,we regard it as a parked car until now
        end_time = ticket.exit_time or now
        hours = ticket.hours_charged(end_time)
        fee = ticket.fee(end_time)
        car = ticket.get_car()
        owner = car.owner if car else None

    form = CheckoutForm()
    if request.method == 'POST' and ticket is not None:
        form = CheckoutForm(request.POST)
        if form.is_valid():
            # Paying for a car that is still parked also checks it out
            if ticket.exit_time is None:
                ticket.exit_time = now
                ticket.save()
            payment = Payment.objects.create(
                ticket=ticket,
                amount=fee,
                method=form.cleaned_data['method'],
                payment_status='Paid',
                payment_date=timezone.localdate(),
            )
            return redirect('receipt', pk=payment.pk)

    context = {
        'unpaid_tickets': unpaid_tickets,
        'ticket': ticket,
        'owner': owner,
        'hours': hours,
        'fee': fee,
        'form': form,
    }
    return render(request, 'parking/pay_form.html', context)


# RECEIPT

@login_required
def receipt(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    ticket = payment.ticket

    if not can_use_lot(request.user, ticket.spot.lot):
        raise PermissionDenied

    car = ticket.get_car()
    context = {
        'payment': payment,
        'ticket': ticket,
        'lot': ticket.spot.lot,
        'spot_number': ticket.spot.number(),
        'car': car,
        'owner': car.owner if car else None,
        'hours': ticket.hours_charged(),
    }
    return render(request, 'parking/receipt.html', context)



# PARKING SPOTS (list only: the spots are created by the lot)


@login_required
def spot_list(request):
    blocks = get_lot_blocks(allowed_lots(request.user))
    return render(request, 'parking/spot_list.html', {'lot_blocks': blocks})



# STAFF (managers only): create attendants and choose their lots

@login_required
def staff_list(request):
    check_manager(request)
    rows = []
    for user in User.objects.order_by('username'):
        if user.is_staff:
            role = 'Manager'
            lots_text = 'All lots'
        else:
            role = 'Attendant'
            names = []
            for lot in ParkingLot.objects.filter(lotstaff__user=user):
                names.append(lot.lot_name)
            lots_text = ', '.join(names) or 'No lot assigned yet'
        rows.append({'user': user, 'role': role, 'lots': lots_text})
    return render(request, 'parking/staff_list.html', {'rows': rows})


@login_required
def staff_add(request):
    check_manager(request)
    if request.method == 'POST':
        form = StaffCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            for lot in form.cleaned_data['lots']:
                LotStaff.objects.create(user=user, lot=lot)
            return redirect('staff_list')
    else:
        form = StaffCreateForm()
    return render(request, 'parking/form.html', {'form': form, 'title': 'Add Attendant', 'back': 'staff_list'})


@login_required
def staff_edit(request, pk):
    check_manager(request)
    user = get_object_or_404(User, pk=pk)
    if user.is_staff:
        # managers already work in every lot
        return redirect('staff_list')

    if request.method == 'POST':
        form = StaffLotsForm(request.POST)
        if form.is_valid():
            # remove the old links, then save the lots that were ticked
            LotStaff.objects.filter(user=user).delete()
            for lot in form.cleaned_data['lots']:
                LotStaff.objects.create(user=user, lot=lot)
            return redirect('staff_list')
    else:
        form = StaffLotsForm(initial={'lots': ParkingLot.objects.filter(lotstaff__user=user)})
    context = {'form': form, 'title': 'Lots for ' + user.username, 'back': 'staff_list'}
    return render(request, 'parking/form.html', context)


@login_required
def staff_delete(request, pk):
    check_manager(request)
    user = get_object_or_404(User, pk=pk)
    # a manager can not delete himself or another manager here
    if request.method == 'POST' and not user.is_staff:
        user.delete()
    return redirect('staff_list')


# Car Owners, Cars, Parking Lots, Tickets
#   Lists: everyone, but an attendant only sees the data of his or her lots.
#   Add, edit, delete: managers

@login_required
def owner_list(request):
    return render(request, 'parking/owner_list.html', {'owners': visible_owners(request.user)})


@login_required
def car_list(request):
    return render(request, 'parking/car_list.html', {'cars': visible_cars(request.user)})


@login_required
def lot_list(request):
    return render(request, 'parking/lot_list.html', {'lots': allowed_lots(request.user)})


@login_required
def ticket_list(request):
    tickets = Ticket.objects.filter(spot__lot__in=allowed_lots(request.user))
    return render(request, 'parking/ticket_list.html', {'tickets': tickets})

#CRUD
# Car Owners  (add, edit, delete: managers only)

@login_required
def owner_add(request):
    check_manager(request)
    if request.method == 'POST':
        form = CarOwnerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('owner_list')
    else:
        form = CarOwnerForm()
    return render(request, 'parking/form.html', {'form': form, 'title': 'Add Car Owner', 'back': 'owner_list'})


@login_required
def owner_edit(request, pk):
    check_manager(request)
    owner = get_object_or_404(CarOwner, pk=pk)
    if request.method == 'POST':
        form = CarOwnerForm(request.POST, instance=owner)
        if form.is_valid():
            form.save()
            return redirect('owner_list')
    else:
        form = CarOwnerForm(instance=owner)
    return render(request, 'parking/form.html', {'form': form, 'title': 'Edit Car Owner', 'back': 'owner_list'})


@login_required
def owner_delete(request, pk):
    check_manager(request)
    owner = get_object_or_404(CarOwner, pk=pk)
    if request.method == 'POST':
        owner.delete()
    return redirect('owner_list')


# Cars  (add, edit, delete: managers only)

@login_required
def car_add(request):
    check_manager(request)
    if request.method == 'POST':
        form = CarForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('car_list')
    else:
        form = CarForm()
    return render(request, 'parking/form.html', {'form': form, 'title': 'Add Car', 'back': 'car_list'})


@login_required
def car_edit(request, pk):
    check_manager(request)
    car = get_object_or_404(Car, pk=pk)
    if request.method == 'POST':
        form = CarForm(request.POST, instance=car)
        if form.is_valid():
            form.save()
            return redirect('car_list')
    else:
        form = CarForm(instance=car)
    return render(request, 'parking/form.html', {'form': form, 'title': 'Edit Car', 'back': 'car_list'})


@login_required
def car_delete(request, pk):
    check_manager(request)
    car = get_object_or_404(Car, pk=pk)
    if request.method == 'POST':
        car.delete()
    return redirect('car_list')



# Parking Lots  (add, edit, delete: managers only)

@login_required
def lot_add(request):
    check_manager(request)
    if request.method == 'POST':
        form = ParkingLotForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lot_list')
    else:
        form = ParkingLotForm()
    return render(request, 'parking/form.html', {'form': form, 'title': 'Add Parking Lot', 'back': 'lot_list'})


@login_required
def lot_edit(request, pk):
    check_manager(request)
    lot = get_object_or_404(ParkingLot, pk=pk)
    if request.method == 'POST':
        form = ParkingLotForm(request.POST, instance=lot)
        if form.is_valid():
            form.save()
            return redirect('lot_list')
    else:
        form = ParkingLotForm(instance=lot)
    return render(request, 'parking/form.html', {'form': form, 'title': 'Edit Parking Lot', 'back': 'lot_list'})


@login_required
def lot_delete(request, pk):
    check_manager(request)
    lot = get_object_or_404(ParkingLot, pk=pk)
    if request.method == 'POST':
        lot.delete()
    return redirect('lot_list')


# Tickets  (add, edit, delete: managers only)


@login_required
def ticket_add(request):
    check_manager(request)
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('ticket_list')
    else:
        form = TicketForm()
    return render(request, 'parking/form.html', {'form': form, 'title': 'Add Ticket', 'back': 'ticket_list'})


@login_required
def ticket_edit(request, pk):
    check_manager(request)
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.method == 'POST':
        form = TicketForm(request.POST, instance=ticket)
        if form.is_valid():
            form.save()
            return redirect('ticket_list')
    else:
        form = TicketForm(instance=ticket)
    return render(request, 'parking/form.html', {'form': form, 'title': 'Edit Ticket', 'back': 'ticket_list'})


@login_required
def ticket_delete(request, pk):
    check_manager(request)
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.method == 'POST':
        ticket.delete()
    return redirect('ticket_list')



# Payments  (list for everyone in their lots, edit and delete: managers only.
# New payments are made on the Make Payment page)

@login_required
def payment_list(request):
    payments = Payment.objects.filter(ticket__spot__lot__in=allowed_lots(request.user))
    return render(request, 'parking/payment_list.html', {'payments': payments})


@login_required
def payment_edit(request, pk):
    check_manager(request)
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            return redirect('payment_list')
    else:
        form = PaymentForm(instance=payment)
    return render(request, 'parking/form.html', {'form': form, 'title': 'Edit Payment', 'back': 'payment_list'})


@login_required
def payment_delete(request, pk):
    check_manager(request)
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == 'POST':
        payment.delete()
    return redirect('payment_list')
