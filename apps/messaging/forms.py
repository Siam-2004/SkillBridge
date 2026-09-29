"""Message composition."""
from __future__ import annotations
from django import forms
class MultiFileInput(forms.ClearableFileInput):
    """Django refuses ``multiple`` on the stock widget because its ``value_from_datadict``
    returns one file. Attachments are read from ``request.FILES.getlist`` in the
    view instead, so allowing the attribute here is safe and keeps the markup
    honest about what the field accepts."""
    allow_multiple_selected = True

class MessageForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Write a message… use @name to mention someone."}),
        required=False,
        max_length=8000,
    )
    files = forms.FileField(
        required=False,
        widget=MultiFileInput(attrs={"multiple": True}),
        label="Attach files",
    )
    def clean(self):
        cleaned = super().clean()
        has_text = bool((cleaned.get("content") or "").strip())
        has_files = bool(self.files.getlist("files")) if hasattr(self.files, "getlist") else False
        if not has_text and not has_files:
            raise forms.ValidationError("Write something, or attach a file.")
        return cleaned