from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse


class ModalFormTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username='modal-manager',
            password='test-password',
            is_staff=True,
        )
        self.client.force_login(self.manager)

    def test_create_and_edit_lists_offer_modal_triggers(self):
        for page in (
            'owner_list',
            'car_list',
            'lot_list',
            'ticket_list',
            'payment_list',
            'staff_list',
        ):
            with self.subTest(page=page):
                response = self.client.get(reverse(page))
                self.assertContains(response, 'js-modal-trigger')
                self.assertContains(response, 'id="form-modal"')

    def test_form_pages_expose_content_for_modal_loading(self):
        for page in (
            'owner_add',
            'car_add',
            'lot_add',
            'ticket_add',
            'staff_add',
            'park_car',
            'make_payment',
        ):
            with self.subTest(page=page):
                response = self.client.get(reverse(page))
                self.assertContains(response, 'id="modal-page-content"')


class CheckoutAndLicenseTests(TestCase):
    def setUp(self):
        from .models import ParkingLot, Ticket
        from django.utils import timezone
        self.manager = User.objects.create_user(username='boss', password='pw', is_staff=True)
        self.client.force_login(self.manager)
        lot = ParkingLot.objects.create(lot_name='Test Lot', capacity=2, location='Here')
        spot = lot.parkingspot_set.first()
        self.ticket = Ticket.objects.create(car_plate='UAA111A', spot=spot, entry_time=timezone.now())

    def test_checkout_saves_exit_time_then_payment_page(self):
        response = self.client.post(reverse('checkout', args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.ticket.exit_time)
        self.assertEqual(self.ticket.payment_set.count(), 0)
        self.assertRedirects(response, reverse('make_payment') + '?ticket=' + str(self.ticket.pk))

    def test_payment_after_checkout_gives_receipt(self):
        self.client.post(reverse('checkout', args=[self.ticket.pk]))
        response = self.client.post(reverse('make_payment'), {'ticket': self.ticket.pk, 'method': 'Cash'})
        payment = self.ticket.payment_set.get()
        self.assertEqual(payment.payment_status, 'Paid')
        self.assertRedirects(response, reverse('receipt', args=[payment.pk]))

    def test_owner_has_no_license_field(self):
        response = self.client.get(reverse('owner_add'))
        self.assertNotContains(response, 'license')
