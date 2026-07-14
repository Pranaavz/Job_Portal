from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Company, JobApplication, JobPost


class JobPortalSmokeTests(TestCase):
    def test_user_profile_created_automatically(self):
        user = User.objects.create_user(username="alice", password="testpass123")
        self.assertTrue(hasattr(user, "profile"))
        self.assertEqual(user.profile.role, "candidate")

    def test_home_page_loads(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TalentBridge")

    def test_candidate_can_apply_to_job(self):
        employer = User.objects.create_user(
            username="employer",
            password="testpass123",
            email="employer@example.com",
            is_active=True,
        )
        employer.profile.role = "employer"
        employer.profile.is_verified = True
        employer.profile.save()

        company = Company.objects.create(owner=employer, name="Bright Labs")
        job = JobPost.objects.create(
            company=company,
            title="Backend Developer",
            category="Engineering",
            employment_type="full-time",
            location="Colombo",
            description="Build APIs",
        )

        candidate = User.objects.create_user(
            username="candidate",
            password="testpass123",
            email="candidate@example.com",
            is_active=True,
        )
        candidate.profile.is_verified = True
        candidate.profile.save()

        self.client.login(username="candidate", password="testpass123")
        response = self.client.post(
            reverse("apply_job", args=[job.slug]),
            {"cover_letter": "I would love to contribute."},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(JobApplication.objects.filter(job=job, applicant=candidate).exists())

    def test_user_can_login_with_email_identifier(self):
        user = User.objects.create_user(
            username="loginuser",
            password="testpass123",
            email="login@example.com",
            is_active=True,
        )
        user.profile.phone = "+94770000000"
        user.profile.is_verified = True
        user.profile.save()

        response = self.client.post(
            reverse("login"),
            {"identifier": "login@example.com", "password": "testpass123"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)

    def test_forgot_password_flow_resets_password(self):
        user = User.objects.create_user(
            username="resetuser",
            password="oldpass123",
            email="reset@example.com",
            is_active=True,
        )
        user.profile.phone = "+94771111111"
        user.profile.is_verified = True
        user.profile.save()

        response = self.client.post(
            reverse("forgot_password"),
            {"identifier": "reset@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        otp = user.otps.filter(is_used=False).first()
        self.assertIsNotNone(otp)

        response = self.client.post(
            reverse("reset_password"),
            {"code": otp.code, "new_password1": "newpass12345", "new_password2": "newpass12345"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.login(username="resetuser", password="newpass12345"))

    def test_registration_allows_phone_without_email(self):
        response = self.client.post(
            reverse("register"),
            {
                "first_name": "Phone",
                "last_name": "Only",
                "username": "phoneonly",
                "contact": "+94772223333",
                "role": "candidate",
                "password1": "testpass12345",
                "password2": "testpass12345",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="phoneonly")
        self.assertEqual(user.email, "")
        self.assertEqual(user.profile.phone, "+94772223333")

    def test_registration_allows_email_in_single_contact_field(self):
        response = self.client.post(
            reverse("register"),
            {
                "first_name": "Mail",
                "last_name": "Only",
                "username": "mailonly",
                "contact": "mailonly@example.com",
                "role": "candidate",
                "password1": "testpass12345",
                "password2": "testpass12345",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="mailonly")
        self.assertEqual(user.email, "mailonly@example.com")
        self.assertEqual(user.profile.phone, "")

    def test_home_page_stats_show_minimum_hundred(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "100")

    def test_job_search_matches_location_and_category_from_main_query(self):
        employer = User.objects.create_user(
            username="searchboss",
            password="testpass123",
            email="searchboss@example.com",
            is_active=True,
        )
        employer.profile.role = "employer"
        employer.profile.is_verified = True
        employer.profile.save()

        company = Company.objects.create(owner=employer, name="Search Labs")
        job = JobPost.objects.create(
            company=company,
            title="Frontend Engineer",
            category="Design",
            employment_type="full-time",
            location="Pune",
            description="Build polished interfaces",
        )

        response = self.client.get(reverse("jobs"), {"q": "Pune"})
        self.assertContains(response, job.title)

        response = self.client.get(reverse("jobs"), {"q": "Design"})
        self.assertContains(response, job.title)
