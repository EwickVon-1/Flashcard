from django.contrib import admin
from .models import User, Set, Card

# Register your models here.
admin.site.register(User)
admin.site.register(Set)
admin.site.register(Card)