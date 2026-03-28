
from datetime import date, timedelta
from django.db.models import Count



def get_study_stats(user, study_data, set_id):
    upcoming_cards = (study_data
                      .filter(due_date__lte=date.today() + timedelta(days=7))
                      .values("due_date")
                      .annotate(count=Count("id"))
                      .order_by("due_date")) 

    reviewed_cards = (study_data
                      .filter(last_studied__gte=date.today() - timedelta(days=30))
                      .values("last_studied")
                      .annotate(count=Count("id"))
                      .order_by("last_studied"))
    
    return upcoming_cards, reviewed_cards

