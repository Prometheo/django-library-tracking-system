from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

# Create your tests here.


from django.utils import timezone
from rest_framework.test import APITestCase

from library.models import Author, Book, Loan, Member

from unittest.mock import patch

from library.tasks import check_overdue_loans




class LoanApiTest(APITestCase):

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="vincent", password="test")
        self.member = Member.objects.create(user=self.user)
        self.author = Author.objects.create(first_name="JK")
        self.book = Book.objects.create(title="Harry Porter", author=self.author, available_copies=3)
        self.loan = Loan.objects.create(book=self.book, member=self.member, due_date=timezone.now().date() - timedelta(days=2)) # due by 2 days
        self.loan2 = Loan.objects.create(book=self.book, member=self.member)# this is a flaw, implement unique constraint on db


    @patch('library.tasks.send_loan_notification')
    def test_find_due_loan(self, loan_due_notif):

        check_overdue_loans()

        loan_due_notif.assert_called_with(self.loan.id, event="Reminder")


    def test_extend_loan_date(self):
        url = reverse('loan-extend-due-date', args=[self.loan2.id])
        res = self.client.post(url, {"additional_days": 2}, format='json')
        self.assertEqual(res.status_code, 200)


    def test_active_members(self):
        url = reverse('member-top-active')
        res = self.client.get(url)

        data = res.data

        self.assertEqual(len(data), 1)

        self.assertEqual(res.status_code, 200)
