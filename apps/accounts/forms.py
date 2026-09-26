"""Auth forms.

Validation that is a *business* rule lives in ``accounts.services``; these
classes only shape and clean the input. A form never decides whether an action
is allowed — that is the service's job, and the service is what the tests
exercise.
"""

from __future__ import annotations

from django import forms

from apps.accounts.models import USERNAME_VALIDATOR, Role


class RegisterForm(forms.Form):
    role = forms.ChoiceField(
        label="Role",
        choices=[
            (Role.CLIENT, "Client"),
            (Role.FREELANCER, "Freelancer"),
        ],
        widget=forms.RadioSelect,
        initial=Role.CLIENT,
    )
    first_name = forms.CharField(max_length=80)
    last_name = forms.CharField(max_length=80, required=False)
    email = forms.EmailField()
    password = forms.CharField(min_length=8, widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput)
    accept_terms = forms.BooleanField(
        error_messages={"required": "You must accept the terms to create an account."}
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") and cleaned.get("password_confirm"):
            if cleaned["password"] != cleaned["password_confirm"]:
                self.add_error("password_confirm", "The two passwords do not match.")
        return cleaned


class LoginForm(forms.Form):
    identifier = forms.CharField(label="Email or username", max_length=254)
    password = forms.CharField(widget=forms.PasswordInput)
    remember = forms.BooleanField(required=False, initial=True)


class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput)
    new_password = forms.CharField(min_length=8, widget=forms.PasswordInput)
    new_password_confirm = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("new_password") != cleaned.get("new_password_confirm"):
            self.add_error("new_password_confirm", "The two passwords do not match.")
        return cleaned


class AccountSettingsForm(forms.Form):
    first_name = forms.CharField(max_length=80, required=False)
    last_name = forms.CharField(max_length=80, required=False)
    username = forms.CharField(max_length=50, validators=[USERNAME_VALIDATOR])
    avatar = forms.ImageField(required=False)

    def clean_username(self):
        return (self.cleaned_data["username"] or "").strip().lower()
