from django.contrib import admin

from .models import Card, GoogleToken, Set, StudyData, User

# Register your models here.
admin.site.register(User)
admin.site.register(Set)
admin.site.register(Card)
admin.site.register(StudyData)
admin.site.register(GoogleToken)

