from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.projects.models import Project, Review
from apps.profiles.models import FreelancerProfile, ClientProfile


