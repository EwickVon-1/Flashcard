from django import forms

def handle_form(request, form_class, instance=None, method="POST"):
    kwargs = {}
    if issubclass(form_class, forms.ModelForm) and instance is not None:
        kwargs["instance"] = instance

    print(f"method={method}")
    if method == "GET":
        form = form_class(request.GET, **kwargs)
        return form, form.is_valid()

    if request.method == "POST":
        form = form_class(request.POST, **kwargs)
        if form.is_valid():
            return form, True
        else:
            form = form_class(**kwargs)  # Re-render empty form on GET or invalid POST
    else:
        form = form_class(**kwargs)
    return form, False
