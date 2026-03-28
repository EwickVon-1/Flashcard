
def toggle_save_set(user, flashcard_set):
    if user == flashcard_set.owner:
        return False, "You cannot save your own flashcard set."
    
    if flashcard_set in user.saved_sets.all():
        user.saved_sets.remove(flashcard_set)
        return False, f"Unsaved '{flashcard_set.name}' to your saved sets."
    else:
        user.saved_sets.add(flashcard_set)
        return True, f"Saved '{flashcard_set.name}' to your saved sets."
