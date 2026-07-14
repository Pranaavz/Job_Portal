from django.contrib import admin
from .models import Company, EmailOTP, JobApplication, JobPost, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "is_verified", "phone", "location")
    list_filter = ("role", "is_verified")
    search_fields = ("user__username", "user__email", "phone", "location")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "industry", "location", "website")
    search_fields = ("name", "owner__username", "industry", "location")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(JobPost)
class JobPostAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "category",
        "employment_type",
        "workplace_type",
        "city",
        "is_active",
        "created_at",
    )
    list_filter = ("employment_type", "workplace_type", "experience_level", "is_active", "category")
    search_fields = ("title", "company__name", "location", "city", "category", "key_skills")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("job", "full_name", "email", "phone", "status", "applied_at")
    list_filter = ("status",)
    search_fields = ("job__title", "applicant__username", "applicant__email", "full_name", "email", "phone")


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "is_used", "created_at", "expires_at")
    list_filter = ("is_used",)
    search_fields = ("user__username", "user__email", "code")
