from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CarOwner, Car, ParkingLot, ParkingSpot, Ticket, Payment


class CarOwnerForm(forms.ModelForm):
    required_css_class = 'required'

    class Meta:
        model = CarOwner
        fields = '__all__'


class CarForm(forms.ModelForm):
    required_css_class = 'required'

    class Meta:
        model = Car
        fields = '__all__'


class ParkingLotForm(forms.ModelForm):
    required_css_class = 'required'

    class Meta:
        model = ParkingLot
        fields = '__all__'

    # Runs automatically to check the capacity field
    def clean_capacity(self):
        capacity = self.cleaned_data['capacity']

        if capacity < 1 or capacity > 500:
            raise forms.ValidationError('Capacity must be between 1 and 500.')

        # When editing a lot: do not allow removing spots that have a car on them
        if self.instance.pk:
            spots = ParkingSpot.objects.filter(lot=self.instance)
            extra = spots.count() - capacity
            if extra > 0:
                last_spots = list(spots.order_by('-spot_id')[:extra])
                for spot in last_spots:
                    if spot.is_occupied():
                        raise forms.ValidationError(
                            'Cannot lower the capacity: ' + str(spot) + ' has a car parked on it.')
        return capacity


class TicketForm(forms.ModelForm):
    required_css_class = 'required'

    class Meta:
        model = Ticket
        fields = '__all__'
        # type="datetime-local" gives the browser's date and time picker
        widgets = {
            'entry_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'exit_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'ticket_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    # Runs after every field is checked: one spot can only hold one car
    def clean(self):
        cleaned = super().clean()
        spot = cleaned.get('spot')
        exit_time = cleaned.get('exit_time')
        if spot and not exit_time:
            others = Ticket.objects.filter(spot=spot, exit_time__isnull=True)
            if self.instance.pk:
                others = others.exclude(pk=self.instance.pk)
            if others.exists():
                raise forms.ValidationError('This spot already has a car parked on it.')
        return cleaned


class PaymentForm(forms.ModelForm):
    required_css_class = 'required'

    class Meta:
        model = Payment
        fields = '__all__'
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The amount is calculated by the system, so it can not be typed or changed
        self.fields['amount'].disabled = True


# A normal form (not a ModelForm) because it fills in three tables at once:
# the owner, the car and the ticket.
class ParkCarForm(forms.Form):
    required_css_class = 'required'

    name = forms.CharField(max_length=50, label='Owner first name')
    last_name = forms.CharField(max_length=50, label='Owner last name')
    phone_no = forms.CharField(max_length=15, label='Owner phone number')
    email = forms.EmailField(required=False, label='Owner email (optional)')
    address = forms.CharField(max_length=100, label='Owner address')
    gender = forms.ChoiceField(choices=CarOwner.GENDER_CHOICES, label='Owner gender')

    car_plate = forms.CharField(max_length=15, label='Car plate number')
    model = forms.CharField(max_length=50, label='Car model')
    color = forms.CharField(max_length=30, label='Car color')
    year_of_manufacture = forms.IntegerField(min_value=1950, max_value=2100, label='Year of manufacture')

    spot = forms.ModelChoiceField(
        queryset=ParkingSpot.objects.none(),
        label='Parking spot',
        error_messages={'required': 'Please click a free spot.'},
    )

    # The form is given the lot that was chosen
    def __init__(self, lot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Spots that are taken = spots that have a ticket with no exit time
        taken_ids = Ticket.objects.filter(exit_time__isnull=True).values_list('spot_id', flat=True)
        # Only offer the spots of THIS lot that are NOT taken
        free_spots = ParkingSpot.objects.filter(lot=lot).exclude(spot_id__in=taken_ids)
        self.fields['spot'].queryset = free_spots

    # Runs automatically for the field called car_plate
    def clean_car_plate(self):
        plate = self.cleaned_data['car_plate'].strip().upper()
        if Ticket.objects.filter(car_plate=plate, exit_time__isnull=True).exists():
            raise forms.ValidationError('This car is already parked.')
        return plate


# Used when a car leaves or a ticket is paid: the person chooses how it was paid
class CheckoutForm(forms.Form):
    required_css_class = 'required'

    method = forms.ChoiceField(choices=Payment.METHOD_CHOICES, label='Payment method')


# The form the manager uses to create an attendant: username, password
# (from UserCreationForm) and the lots the attendant may work in.
class StaffCreateForm(UserCreationForm):
    required_css_class = 'required'

    lots = forms.ModelMultipleChoiceField(
        queryset=ParkingLot.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Lots this attendant can work in',
    )

    class Meta(UserCreationForm.Meta):
        fields = ('username',)


# The form the manager uses to change the lots of an attendant
class StaffLotsForm(forms.Form):
    required_css_class = 'required'

    lots = forms.ModelMultipleChoiceField(
        queryset=ParkingLot.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Lots this attendant can work in',
    )
