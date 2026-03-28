from django.contrib.auth.models import AbstractUser
from django.db import models 
from datetime import date, timedelta

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

class StudyData(models.Model):
    class Meta:
        unique_together = ("user", "card")

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="study_data")
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="studied_card")
    due_date = models.DateField(default=date.today)
    first_studied = models.DateField(null=True, blank=True)
    last_studied = models.DateField(null=True, blank=True)
    interval = models.IntegerField(default=1)
    repetitions = models.IntegerField(default=0)
    easiness = models.FloatField(default=2.5)
    
    def __str__(self):
        return f"{self.user.username} - {self.card.question}"
    
    def update_study_data(self, quality):
        if not self.first_studied:
            self.first_studied = date.today()

        self.last_studied = date.today()
        if quality < 0 or quality > 3:
            raise ValueError("Quality must be between 0 and 3")

        if quality == 0:  # Again
            self.repetitions = 0
            self.interval = 1
            self.easiness -= 0.2
        else:
            self.repetitions += 1
            
            if (self.repetitions == 1):
                self.interval = 1
            elif (self.repetitions == 2):
                self.interval = 6
            else:
                if quality == 1:  # Hard
                    self.interval = round(self.interval * 1.1)
                    self.easiness -= 0.15
                elif quality == 2:  # Good
                    self.interval = round(self.interval * self.easiness)
                elif quality == 3:  # Easy
                    self.interval = round(self.interval * self.easiness * 1.3)
                    self.easiness += 0.1

        self.easiness = max(1.3, self.easiness)
        self.interval = max(1, self.interval)

        if quality == 0:
            self.due_date = date.today()
            
        else:
            self.due_date = date.today() + timedelta(days=int(self.interval))
        self.save()
