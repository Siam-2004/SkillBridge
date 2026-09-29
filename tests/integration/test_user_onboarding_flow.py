from django.test import TestCase, Client
from unittest.mock import patch
from apps.accounts.models import User, Role, EmailVerificationToken
from apps.accounts import services as account_services


