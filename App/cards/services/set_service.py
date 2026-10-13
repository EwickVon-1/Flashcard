from enum import Enum


class state(Enum):
    INVALID = 0
    UNSAVED = 1
    SAVED = 2


def toggle_save_set(user, flashcard_set):
    if user == flashcard_set.owner:
        return state.INVALID

    if saved_sets.filter(pk=flashcard_set.pk).exists():
        user.saved_sets.remove(flashcard_set)
        return state.UNSAVED
    else:
        user.saved_sets.add(flashcard_set)
        return state.SAVED
