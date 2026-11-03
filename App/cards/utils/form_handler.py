from typing import Any, TypeVar

from django import forms
from django.http import HttpRequest

FormType = TypeVar("FormType", bound=forms.ModelForm)
def handle_form(request: HttpRequest, 
                form_class: type[FormType], 
                instance: Any | None = None, 
                initial: dict[str, Any] | None = None
                ) -> tuple[FormType, bool]: 
    
    kwargs: dict[str, Any] = {}

    if instance is not None:
        kwargs["instance"] = instance

    if request.method == "POST":
        form = form_class(request.POST, **kwargs) 
    else:
        form = form_class(initial=initial, **kwargs)
    
    return form, request.method == "POST" and form.is_valid()
