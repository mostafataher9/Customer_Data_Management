from django.db import models

# Create your models here.
class Customer(models.Model):
    name= models.CharField(max_length=50)
    email= models.EmailField(unique=True,max_length=100)
    #null=True, blank=True Allows existing customers to have NULL values before updating.
    phone_number= models.CharField(max_length=15,null=True,blank=True) 
    created_at= models.DateField(auto_now_add=True)

    def __str__(self):
        return self.name, self.email, self.phone_number, self.created_at
    
    
