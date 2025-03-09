from django.urls import path
from .views import CustomerListView
from .views import create_customer, customer_info, get_customer, list_customers, update_customer
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns=[
    path('customers/', list_customers , name='list_customers'),
    path('customer/', get_customer , name='get_customer'),
    path('customer/create/', create_customer , name='create_customer'),
    path('customer/<int:pk>/', customer_info , name='customer_info'),
    path('update-customer/<customer_id>/', update_customer , name='update-customer'),
    path('customers_read/', CustomerListView.as_view(), name='customer-list'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
]