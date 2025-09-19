from datetime import timedelta
from django.db.models import Q
from django.db.models.aggregates import Count
from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, ExtendDueDateRequestSerializer, MemberSerializer, LoanSerializer
from rest_framework.decorators import action
from django.utils import timezone
from .tasks import send_loan_notification

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.select_related("author").all()
    serializer_class = BookSerializer

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer


    @action(detail=False, methods=['get'])
    def top_active(self, request, pk=None):
        top_members = Member.objects.annotate(total_loans=Count("loans", Q(is_returned=False))).select_related("user").filter(total_loans__gte=1).order_by("-total_loans")

        response_data = [
            {"id": top_member.id, "username": top_member.user.username, "email": top_member.user.email, "active_loans": top_member.total_loans} for top_member in top_members
        ]

        return Response(response_data, status=status.HTTP_200_OK)



class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer


    @action(detail=True, methods=['post'])
    def extend_due_date(self, request, pk=None):
        data = request.data
        serialized_data = ExtendDueDateRequestSerializer(data=data)
        if serialized_data.is_valid(): # serializer validates that day is positive
            loan = self.get_object()
            if loan.due_date < timezone.now().date():
                return Response({'error': 'Loan already expired, Please Return Book!'}, status=status.HTTP_400_BAD_REQUEST)
            if loan.is_returned:
                return Response({'error': 'Book already returned'}, status=status.HTTP_400_BAD_REQUEST)
            loan.due_date += timedelta(days=serialized_data.validated_data.get("additional_days"))
            loan.save()
            return Response({
                'status': 'Loan date Extended SUccessfully.',
                'new_date': loan.due_date
            }, status=status.HTTP_200_OK)
        return Response({'error': serialized_data.errors}, status=status.HTTP_400_BAD_REQUEST)
