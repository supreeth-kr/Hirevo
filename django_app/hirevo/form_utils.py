from django import forms

def add_bootstrap_classes(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, (forms.TextInput, forms.EmailInput, forms.PasswordInput,
                               forms.NumberInput, forms.URLInput, forms.Textarea,
                               forms.Select, forms.FileInput)):
            existing = widget.attrs.get('class', '')
            widget.attrs['class'] = (existing + ' form-control').strip()
        elif isinstance(widget, forms.CheckboxInput):
            existing = widget.attrs.get('class', '')
            widget.attrs['class'] = (existing + ' form-check-input').strip()
    return form
