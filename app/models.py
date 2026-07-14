from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ("candidate", "Candidate"),
        ("employer", "Employer"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="candidate")
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    skills = models.TextField(blank=True)
    resume_link = models.URLField(blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class Company(models.Model):
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name="company")
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True, blank=True)
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or slugify(self.owner.username) or "company"
            slug = base_slug
            counter = 1
            while Company.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class EmailOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps")
    code = models.CharField(max_length=6, validators=[MinLengthValidator(6)])
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP for {self.user.username}"

    def is_valid(self):
        return (not self.is_used) and timezone.now() <= self.expires_at


class JobPost(models.Model):
    CATEGORY_CHOICES = [
        ("software-development", "Software Development (Coding Jobs)"),
        ("web-design", "Web & Design"),
        ("database-backend", "Database & Backend"),
        ("data-ai", "Data & AI Jobs"),
        ("cybersecurity", "Cybersecurity"),
        ("cloud-devops", "Cloud & DevOps"),
        ("networking-systems", "Networking & System Jobs"),
        ("testing-qa", "Testing & QA"),
    ]
    EMPLOYMENT_CHOICES = [
        ("full-time", "Full Time"),
        ("part-time", "Part Time"),
        ("contract", "Contract"),
        ("internship", "Internship"),
        ("remote", "Remote"),
    ]
    WORKPLACE_CHOICES = [
        ("on-site", "On-site"),
        ("hybrid", "Hybrid"),
        ("remote", "Remote"),
    ]
    EXPERIENCE_CHOICES = [
        ("entry", "Entry Level"),
        ("mid", "Mid Level"),
        ("senior", "Senior Level"),
        ("lead", "Lead / Manager"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(max_length=150)
    slug = models.SlugField(unique=True, blank=True)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_CHOICES)
    workplace_type = models.CharField(max_length=20, choices=WORKPLACE_CHOICES, default="on-site")
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_CHOICES, default="mid")
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=120)
    salary = models.CharField(max_length=80, blank=True)
    openings = models.PositiveIntegerField(default=1)
    key_skills = models.TextField(blank=True)
    description = models.TextField()
    requirements = models.TextField(blank=True)
    application_deadline = models.DateField(null=True, blank=True)
    source_label = models.CharField(max_length=100, default="Portal")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.city:
            self.location = f"{self.city}, {self.state}".strip(", ")
        if not self.slug:
            base_slug = slugify(f"{self.title}-{self.company.name}") or "job"
            slug = base_slug
            counter = 1
            while JobPost.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class JobApplication(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("reviewed", "Reviewed"),
        ("shortlisted", "Shortlisted"),
        ("rejected", "Rejected"),
    ]

    job = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="applications")
    full_name = models.CharField(max_length=150, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=20, blank=True)
    current_city = models.CharField(max_length=120, blank=True)
    skills = models.TextField(blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    resume_link = models.URLField(blank=True)
    portfolio_link = models.URLField(blank=True)
    cover_letter = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at"]
        unique_together = ("job", "applicant")

    def __str__(self):
        return f"{self.applicant.username} -> {self.job.title}"

    def save(self, *args, **kwargs):
        if not self.full_name:
            self.full_name = self.applicant.get_full_name() or self.applicant.username
        if not self.email:
            self.email = self.applicant.email or ""
        profile = getattr(self.applicant, "profile", None)
        if profile:
            self.phone = self.phone or profile.phone
            self.current_city = self.current_city or profile.location
            self.skills = self.skills or profile.skills
            self.resume_link = self.resume_link or profile.resume_link
        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        UserProfile.objects.get_or_create(user=instance)
