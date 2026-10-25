from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.projects.models import Project, Review
from apps.profiles.models import FreelancerProfile, ClientProfile
User = get_user_model()

class US25RatingReviewTest(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username='review_client',
            email='client@review.com',
            password='Password123!',
            role='CLIENT',
            is_email_verified=True
        )
        self.freelancer_user = User.objects.create_user(
            username='review_freelancer',
            email='freelancer@review.com',
            password='Password123!',
            role='FREELANCER',
            is_email_verified=True
        )
        self.other_user = User.objects.create_user(
            username='review_other',
            email='other@review.com',
            password='Password123!',
            role='FREELANCER',
            is_email_verified=True
        )
        # Ensure profiles exist
        FreelancerProfile.objects.get_or_create(user=self.freelancer_user)
        ClientProfile.objects.get_or_create(user=self.client_user)

        self.project = Project.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            title='E-Commerce Platform Redesign',
            final_price=Decimal('5000.00'),
            deadline=timezone.now() + timedelta(days=14),
            status=Project.Status.ACTIVE
        )

    def test_review_rejected_when_project_is_not_completed(self):
        """US-25: Reviews cannot be submitted before project is completed."""
        review = Review(
            project=self.project,
            reviewer=self.client_user,
            reviewee=self.freelancer_user,
            rating=5,
            feedback='Outstanding work done!'
        )
        with self.assertRaises(ValidationError) as ctx:
            review.full_clean()
        self.assertIn('Ratings and reviews can only be submitted after project completion.', str(ctx.exception))

    def test_review_allowed_after_project_completed(self):
        """US-25: Reviews can be submitted once project is completed."""
        self.project.status = Project.Status.COMPLETED
        self.project.completed_at = timezone.now()
        self.project.save()

        review = Review(
            project=self.project,
            reviewer=self.client_user,
            reviewee=self.freelancer_user,
            rating=5,
            feedback='Fantastic communication and delivered on time!'
        )
        review.full_clean()
        review.save()

        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(review.rating, 5)

    def test_review_rating_must_be_between_one_and_five(self):
        """US-25: Rating must be within 1-5."""
        self.project.status = Project.Status.COMPLETED
        self.project.save()

        invalid_review = Review(
            project=self.project,
            reviewer=self.client_user,
            reviewee=self.freelancer_user,
            rating=6,
            feedback='Exceeds scale'
        )
        with self.assertRaises(ValidationError):
            invalid_review.full_clean()

        invalid_zero = Review(
            project=self.project,
            reviewer=self.client_user,
            reviewee=self.freelancer_user,
            rating=0,
            feedback='Zero stars'
        )
        with self.assertRaises(ValidationError):
            invalid_zero.full_clean()

    def test_reviewer_cannot_review_themselves(self):
        """US-25: Reviewer cannot be the same user as reviewee."""
        self.project.status = Project.Status.COMPLETED
        self.project.save()

        self_review = Review(
            project=self.project,
            reviewer=self.freelancer_user,
            reviewee=self.freelancer_user,
            rating=5,
            feedback='I reviewed myself'
        )
        with self.assertRaises(ValidationError):
            self_review.full_clean()

    def test_single_review_per_party_per_project_uniqueness(self):
        """US-25: Users can review the counterparty only once per project."""
        self.project.status = Project.Status.COMPLETED
        self.project.save()

        Review.objects.create(
            project=self.project,
            reviewer=self.client_user,
            reviewee=self.freelancer_user,
            rating=5,
            feedback='First client review'
        )

        duplicate = Review(
            project=self.project,
            reviewer=self.client_user,
            reviewee=self.freelancer_user,
            rating=4,
            feedback='Second review attempt'
        )
        with self.assertRaises(Exception):
            duplicate.save()

    def test_profile_average_rating_and_total_reviews(self):
        """US-25: Average rating and total review counts correctly reflected in profiles."""
        self.project.status = Project.Status.COMPLETED
        self.project.save()

        Review.objects.create(
            project=self.project,
            reviewer=self.client_user,
            reviewee=self.freelancer_user,
            rating=4,
            feedback='Very solid work.'
        )

        p2 = Project.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            title='Project 2',
            final_price=Decimal('2000.00'),
            deadline=timezone.now() + timedelta(days=10),
            status=Project.Status.COMPLETED
        )
        Review.objects.create(
            project=p2,
            reviewer=self.client_user,
            reviewee=self.freelancer_user,
            rating=5,
            feedback='Even better execution.'
        )

        freelancer_profile = self.freelancer_user.freelancer_profile
        self.assertEqual(freelancer_profile.total_reviews, 2)
        self.assertEqual(freelancer_profile.average_rating, 4.5)

    def test_review_submission_view_via_http(self):
        """US-25: Submit review via Web HTTP endpoint."""
        self.project.status = Project.Status.COMPLETED
        self.project.save()

        self.client.login(email='freelancer@review.com', password='Password123!')
        url = reverse('projects:review_submit', args=[self.project.public_id])
        
        response = self.client.post(url, {
            'rating': '5',
            'feedback': 'Great client with clear requirements and prompt payment!'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Review.objects.filter(reviewer=self.freelancer_user, reviewee=self.client_user).exists())

