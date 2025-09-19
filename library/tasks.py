from celery import shared_task
from django.utils import timezone
from .models import Loan
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_loan_notification(loan_id, event="Success"):
    try:
        loan = Loan.objects.select_related("book", "member__user").get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        if event == "Success": # use event to decide template
                _ = send_mail(
                    subject='Book Loaned Successfully',
                    message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[member_email],
                    fail_silently=False,
                )
        elif "Reminder":
                _ = send_mail(
                    subject='Search ATlas Library-- Reminder!',
                    message=f'Hello {loan.member.user.username},\n\nThe Book "{book_title}" is due for return.\nPlease return ASAP.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[member_email],
                    fail_silently=False,
                )
                logger.info(f'sent {event} notification  to {member_email}')
    except Loan.DoesNotExist:
        pass



@shared_task
def check_overdue_loans():
    due_loans = Loan.objects.filter(due_date__lt=timezone.now().date())

    for loan in due_loans:
        send_loan_notification(loan.id)

    logger.info(f'found {due_loans.count()} due loans and queued notification')
