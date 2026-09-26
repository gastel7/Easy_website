from django.contrib import admin
from .models import User, EasyMember

# Register your models here.
admin.site.register(User)
admin.site.register(EasyMember)