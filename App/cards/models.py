from django.contrib.auth.models import AbstractUser
from django.db import models 

# Create your models here.
class User(AbstractUser):
    pass

class Set(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sets")
    name = models.CharField(max_length=50)
    description = models.CharField(max_length=300)
    saved_by = models.ManyToManyField(User, blank=True, related_name="saved_sets")
    
    def __str__(self):
        return self.name


class Card(models.Model):
    set = models.ForeignKey(Set, on_delete=models.CASCADE, related_name="in_set", null=True, blank=True)
    question = models.TextField()
    answer = models.TextField()

    def __str__(self):
        return self.question