from datetime import date, timedelta
from django.shortcuts import get_object_or_404
from cards.models import Card, StudyData

MAX_NEW_CARDS_TO_STUDY = 5

def get_next_card(user, set_id):
    due = StudyData.objects.filter(user=user,
                                         card__set_id=set_id,
                                         due_date__lte=date.today()
                                         ).order_by("due_date").first()

    if due:
        return due.card

    new_cards_today = StudyData.objects.filter(user=user,
                                              card__set_id=set_id,
                                              first_studied=date.today()).count()

    new = Card.objects.filter(set_id=set_id)\
    .exclude(studied_card__user=user)\
    .first() if new_cards_today < MAX_NEW_CARDS_TO_STUDY else None

    return new

def process_grade(user, card_id, set_id, grade):
    card = get_object_or_404(Card, id=card_id, set_id=set_id)
    study_data, created = StudyData.objects.get_or_create(user=user, card=card)
    study_data.update_study_data(grade)

    
def create_query(request, name, set_id):
    key = f"{name}.{set_id}"
    if key not in request.session:
        request.session[key] = 0
        request.session.modified = True
    return key

def increment_query(request, key):    
    request.session[key] += 1
    request.session.modified = True
    return request.session[key]


def destroy_query(request, key):
    if key in request.session:
        del request.session[key]

