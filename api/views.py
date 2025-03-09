 #what type of routers we have
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from Customer import settings
from api.pagination import CustomPagination
from .serializer import CustomerSerializer
from .models import Customer
import logging
from django.shortcuts import get_object_or_404, render
from rest_framework import generics
from django.db.models import Q
import csv
from django.db import transaction
from django.core.exceptions import ValidationError
from celery import shared_task
from django.core.files.storage import FileSystemStorage
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.core.mail import send_mail

#getting the list of customers
@api_view(['GET'])
def list_customers(request):
  customers=Customer.objects.all()
  serializer=CustomerSerializer( customers, many=True) #many=True means we are serializing multiple objects
  return Response(serializer.data)

"""
page_size
The paginator is an instance of CustomPagination, which controls the page size.
Example:
If the customers queryset has 100 entries and page_size = 10, this will return only the first 10 customers when page=1.
serializer = CustomerSerializer(result_page, many=True)
Converts the paginated queryset (result_page) into JSON format.
The many=True argument ensures that multiple objects are serialized.
return paginator.get_paginated_response(serializer.data)
Returns a paginated HTTP response that includes:
Total count of records.
Next page URL (if available).
Previous page URL (if available).
Paginated results (list of customer records).
"""

@api_view(['GET', 'PUT', 'DELETE'])
def customer_info(request, pk=None):
    # Initialize the queryset
    customers = Customer.objects.all()
    
    # Apply search filtering if 'search' parameter is present
    search_query = request.query_params.get('search', None)
    if search_query:
        customers = Customer.objects.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )
        if customers.exists():
                serializer = CustomerSerializer(customers, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
        return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

    #custom query parameters (e.g., sort_by and sort_order)
    # Apply sorting if 'sort_by' and 'sort_order' parameters are present
    sort_by = request.query_params.get('sort_by', 'name')  # Default sort field
    sort_order = request.query_params.get('sort_order', 'asc')  # Default sort order

    # Determine the sorting order
    if sort_order == 'desc':
        sort_by = f'-{sort_by}';

    # Apply sorting to the queryset
    #this will sort the customers queryset by the specified fields in allowed_ordering_fields
    #this will prevent security vulnerabilities such as SQL injection when we check user input against a predefined list of fields.
    if sort_by:
        allowed_ordering_fields = ['name', 'email', 'phone_number']
        ordering_fields = [field.strip() for field in sort_by.split(',')]
        sanitized_ordering = [field for field in ordering_fields if field.lstrip('-') in allowed_ordering_fields]
        if sanitized_ordering:
            customers = customers.order_by(*sanitized_ordering) # Apply sorting

    # If 'pk' is provided, filter by primary key
    if pk:
        customers = customers.filter(pk=pk)

    # Handle GET request
    if request.method == 'GET':
        if pk:
            # Retrieve a single customer
            try:
                customer = customers.get()
                serializer = CustomerSerializer(customer)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Customer.DoesNotExist:
                return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Paginate the queryset for list view
               paginator = CustomPagination()
               result_page = paginator.paginate_queryset(customers, request)
               serializer = CustomerSerializer(result_page, many=True)
               return paginator.get_paginated_response(serializer.data)

    # Handle PUT request for updating a customer
    elif request.method == 'PUT' and pk:
        try:
            customer = customers.get()
            serializer = CustomerSerializer(customer, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Customer.DoesNotExist:
            return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

    # Handle DELETE request for deleting a customer
    elif request.method == 'DELETE' and pk:
        try:
            customer = customers.get()
            customer.delete()
            return Response({"message": "Customer deleted successfully"}, status=status.HTTP_200_OK)
        except Customer.DoesNotExist:
            return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

    # If the request method is not recognized or 'pk' is missing for PUT/DELETE
    return Response({"error": "Invalid request"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_customer(request):
    return Response(CustomerSerializer({'name': 'Mostafa', 'email': 'mostafa@gmail.com', 'phone_number': '77777777',  'created_at': '2024-02-12'}).data)


@api_view(['POST'])
def create_customer(request):
   serializer=CustomerSerializer(data=request.data) 
   if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
   return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#Add a new field phone_number (text) to the existing "Customer" table.

@api_view(['PATCH'])
def update_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    phone_number = request.data.get('phone_number', None)
    
    if phone_number:
        customer.phone_number = phone_number
        customer.save()
        return Response({"message": "Customer updated successfully", "phone_number": customer.phone_number})

    return Response({"message": "No data provided"}, status=400)

class CustomerListView(generics.ListAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.query_params.get('search', None)
        
        if search_query:
            queryset = queryset.filter(
                # Search by name, email, or phone number
               # The name field contains the search query as substring (name__icontains=search_query).
               #Email: The email field contains the search query as a substring (email__icontains=search_query).
               #Phone Number: The phone_number field exactly matches the search query
                Q(name__icontains=search_query) |  
                Q(email__icontains=search_query) |  # Partial match
                Q(phone_number=search_query)  # Exact match
            )
        return queryset




# Configure logging
logging.basicConfig(filename='import_errors.log', level=logging.ERROR)

@shared_task
def import_csv(file_path,user_email):
    try:
        with open(file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            batch_size = 1000
            batch = []
            for row_number, row in enumerate(reader, start=1):
                customer = Customer(
                    name=row.get('name'),
                    email=row.get('email'),
                    phone_number=row.get('phone_number'),
                    # Add other fields as necessary
                )
                try:
                    customer.full_clean()  # Validate the customer instance
                    batch.append(customer)
                except ValidationError as e:
                    # Log validation errors with row number and error details
                    #e.message_dict contains the key as field names and the value is the list of the corresponding error messages.
                        for field, errors in e.message_dict.items():
                            for error in errors:
                                logging.error(f"Row {row_number} - Error in {field}: {error}")

                if len(batch) >= batch_size:
                    with transaction.atomic():
                        Customer.objects.bulk_create(batch)
                    batch = []

            if batch:
                with transaction.atomic():
                    Customer.objects.bulk_create(batch)
    except Exception as e:
        # Handle exceptions (e.g., log the error)
        # Optionally, send an email notification about the failure
        send_mail(
            'CSV Import Failed',
            f'There was an error importing your CSV file: {e}',
            settings.DEFAULT_FROM_EMAIL,
            [user_email],
            fail_silently=False,
        )

def upload_csv(request):
    if request.method == 'POST' and request.FILES['csv_file']:
        csv_file = request.FILES['csv_file']
        user_email = request.user.email
        fs = FileSystemStorage()
        file_path = fs.save(csv_file.name, csv_file)
        import_csv.delay(file_path,user_email) # Trigger the asynchronous task
        return render(request, 'upload_success.html')
    return render(request, 'upload.html')     

class SecureDataView(APIView):
    # Ensure that the user is authenticated
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = {
            'message': 'This is secured data.',
            'user': request.user.username,
        }
        return Response(data)