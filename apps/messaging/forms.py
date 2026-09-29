from __future__ import annotations
from django import forms

class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MessageForm(forms.Form):
    content = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write a message… use @name to mention someone.'}), required=False, max_length=8000)
    files = forms.FileField(required=False, widget=MultiFileInput(attrs={'multiple': True}), label='Attach files')

    def clean(self):
        cleaned = super().clean()
        has_text = bool((cleaned.get('content') or '').strip())
        has_files = bool(self.files.getlist('files')) if hasattr(self.files, 'getlist') else False
        if not has_text and (not has_files):
            raise forms.ValidationError('Write something, or attach a file.')
        return cleaned
