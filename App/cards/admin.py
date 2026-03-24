from django.contrib import admin
from .models import User, Set, Card, StudyData

# Register your models here.
admin.site.register(User)
admin.site.register(Set)
admin.site.register(Card)
admin.site.register(StudyData)
