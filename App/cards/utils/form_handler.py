from django import forms


def handle_form(request, form_class, instance=None, initial=None):
    kwargs = {}
    if issubclass(form_class, forms.ModelForm) and instance is not None:
        kwargs["instance"] = instance

    if request.method == "POST":
        form = form_class(request.POST, **kwargs)
        return form, form.is_valid()

    form = form_class(initial=initial, **kwargs)
    return form, False
