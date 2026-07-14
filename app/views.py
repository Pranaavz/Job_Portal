import random
from calendar import month_abbr

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Count, Prefetch, Q, Sum
from django.db.models.functions import Coalesce, ExtractMonth
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    CompanyProfileForm,
    ForgotPasswordRequestForm,
    JobApplicationForm,
    JobPostForm,
    LoginForm,
    OTPVerificationForm,
    RegisterForm,
    ResetPasswordForm,
    UserProfileForm,
)
from .models import Company, EmailOTP, JobApplication, JobPost, UserProfile


def generate_otp():
    return f"{random.randint(100000, 999999)}"


def normalize_phone(phone):
    return "".join(char for char in (phone or "") if char.isdigit() or char == "+")


def detect_identifier_channel(identifier):
    identifier = (identifier or "").strip()
    if "@" in identifier:
        return "email"
    if len([char for char in normalize_phone(identifier) if char.isdigit()]) >= 10:
        return "phone"
    return "username"


def get_user_by_identifier(identifier, role=None):
    identifier = (identifier or "").strip()
    if not identifier:
        return None

    phone_identifier = normalize_phone(identifier)
    query = Q(username__iexact=identifier) | Q(email__iexact=identifier)

    if identifier:
        query |= Q(profile__phone=identifier)
    if phone_identifier:
        query |= Q(profile__phone=phone_identifier)

    users = User.objects.filter(query).select_related("profile")
    if role in ("candidate", "employer"):
        users = users.filter(profile__role=role)
    return users.order_by("id").first()


def is_console_email_backend():
    backend = getattr(settings, "EMAIL_BACKEND", "")
    return backend == "django.core.mail.backends.console.EmailBackend" or backend.endswith(".console.EmailBackend")


def deliver_otp(request, user, otp, context_label, preferred_channel=None):
    delivery_mode = "preview"
    delivery_channel = "email" if user.email else "phone"
    preview_target = user.email or getattr(user.profile, "phone", "") or "your account"

    if preferred_channel == "phone" and user.profile.phone:
        delivery_channel = "phone"
        preview_target = user.profile.phone
    elif preferred_channel == "email" and user.email:
        delivery_channel = "email"
        preview_target = user.email

    if delivery_channel == "email" and user.email:
        try:
            send_mail(
                subject="Your Job Portal OTP Verification Code",
                message=(
                    f"Hello {user.first_name or user.username},\n\n"
                    f"Your OTP code is {otp.code}. It is valid for 10 minutes.\n\n"
                    "If you did not request this, please ignore this email."
                ),
                from_email=None,
                recipient_list=[user.email],
                fail_silently=False,
            )
            if not is_console_email_backend():
                delivery_mode = "email"
            else:
                preview_target = user.email
        except Exception:
            messages.warning(
                request,
                "Email delivery is not configured correctly, so the portal is using preview mode for OTP.",
            )
    elif delivery_channel == "phone" and user.profile.phone:
        messages.info(
            request,
            "OTP is prepared for the mobile number you entered. Add an SMS gateway later if you want real SMS delivery.",
        )
        delivery_mode = "phone-preview"
        preview_target = user.profile.phone

    request.session["otp_preview_code"] = otp.code
    request.session["otp_preview_target"] = preview_target
    request.session["otp_context_label"] = context_label
    request.session["otp_delivery_mode"] = delivery_mode
    request.session["otp_delivery_channel"] = delivery_channel


def send_otp_to_user(request, user, context_label="verification", preferred_channel=None):
    EmailOTP.objects.filter(user=user, is_used=False).update(is_used=True)
    otp = EmailOTP.objects.create(
        user=user,
        code=generate_otp(),
        expires_at=timezone.now() + timezone.timedelta(minutes=10),
    )
    deliver_otp(request, user, otp, context_label, preferred_channel=preferred_channel)
    return otp


def is_employer(user):
    return user.is_authenticated and hasattr(user, "profile") and user.profile.role == "employer"


def is_staff_user(user):
    return user.is_authenticated and user.is_staff


def build_monthly_job_chart():
    current_year = timezone.now().year
    rows = (
        JobPost.objects.filter(created_at__year=current_year)
        .annotate(month=ExtractMonth("created_at"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )
    counts = {row["month"]: row["total"] for row in rows}
    max_total = max(counts.values(), default=1)
    return [
        {
            "label": month_abbr[month],
            "total": counts.get(month, 0),
            "height": max(10, round((counts.get(month, 0) / max_total) * 100)) if counts.get(month, 0) else 8,
        }
        for month in range(1, 13)
    ]


def get_category_summary():
    totals = {
        row["category"]: row["total"]
        for row in JobPost.objects.filter(is_active=True).values("category").annotate(total=Count("id"))
    }
    return [
        {
            "value": value,
            "label": label,
            "total": totals.get(value, 0),
        }
        for value, label in JobPost.CATEGORY_CHOICES
    ]


def index(request):
    jobs = JobPost.objects.filter(is_active=True).select_related("company")[:6]
    actual_stats = {
        "jobs": JobPost.objects.filter(is_active=True).count(),
        "companies": Company.objects.count(),
        "candidates": UserProfile.objects.filter(role="candidate", is_verified=True).count(),
        "applications": JobApplication.objects.count(),
    }
    context = {
        "jobs": jobs,
        "stats": actual_stats,
        "categories": get_category_summary(),
    }
    return render(request, "app/index.html", context)


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.first_name = form.cleaned_data["first_name"]
        user.last_name = form.cleaned_data["last_name"]
        user.email = form.cleaned_data["normalized_contact"] if form.cleaned_data["contact_type"] == "email" else ""
        user.is_active = True
        user.save()
        user.profile.role = form.cleaned_data["role"]
        user.profile.phone = form.cleaned_data["normalized_contact"] if form.cleaned_data["contact_type"] == "phone" else ""
        user.profile.is_verified = True
        user.profile.save()
        messages.success(request, "Registration successful. You can now log in with username and password.")
        return redirect("login")
    return render(request, "app/register.html", {"form": form})


def _build_role_register_form(request, forced_role):
    form_data = request.POST.copy() if request.method == "POST" else None
    if form_data is not None:
        form_data["role"] = forced_role
    form = RegisterForm(form_data or None)
    form.fields["role"].initial = forced_role
    form.fields["role"].widget = forms.HiddenInput()
    return form


def candidate_register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = _build_role_register_form(request, "candidate")
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.first_name = form.cleaned_data["first_name"]
        user.last_name = form.cleaned_data["last_name"]
        user.email = form.cleaned_data["normalized_contact"] if form.cleaned_data["contact_type"] == "email" else ""
        user.is_active = True
        user.save()
        user.profile.role = "candidate"
        user.profile.phone = form.cleaned_data["normalized_contact"] if form.cleaned_data["contact_type"] == "phone" else ""
        user.profile.is_verified = True
        user.profile.save()
        messages.success(request, "Candidate account created successfully. Please log in.")
        return redirect("candidate_login")
    return render(
        request,
        "app/register.html",
        {
            "form": form,
            "register_kind": "candidate",
        },
    )


def company_register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = _build_role_register_form(request, "employer")
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.first_name = form.cleaned_data["first_name"]
        user.last_name = form.cleaned_data["last_name"]
        user.email = form.cleaned_data["normalized_contact"] if form.cleaned_data["contact_type"] == "email" else ""
        user.is_active = True
        user.save()
        user.profile.role = "employer"
        user.profile.phone = form.cleaned_data["normalized_contact"] if form.cleaned_data["contact_type"] == "phone" else ""
        user.profile.is_verified = True
        user.profile.save()
        messages.success(request, "Company account created successfully. Please log in.")
        return redirect("company_login")
    return render(
        request,
        "app/register.html",
        {
            "form": form,
            "register_kind": "company",
        },
    )


def verify_otp_view(request):
    pending_user_id = request.session.get("pending_user_id")
    if not pending_user_id:
        messages.info(request, "Start by registering your account.")
        return redirect("register")

    user = get_object_or_404(User, pk=pending_user_id)
    form = OTPVerificationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        otp = user.otps.filter(is_used=False).first()
        if otp and otp.code == form.cleaned_data["code"] and otp.is_valid():
            otp.is_used = True
            otp.save(update_fields=["is_used"])
            user.is_active = True
            user.save(update_fields=["is_active"])
            user.profile.is_verified = True
            user.profile.save(update_fields=["is_verified"])
            login(request, user)
            request.session.pop("pending_user_id", None)
            messages.success(request, "OTP verified. Your account is now active.")
            return redirect("dashboard")
        messages.error(request, "Invalid or expired OTP. Please try again.")
    return render(
        request,
        "app/verify_otp.html",
        {
            "form": form,
            "pending_user": user,
            "pending_contact": user.email or user.profile.phone or user.username,
            "otp_preview_code": request.session.get("otp_preview_code"),
            "otp_preview_target": request.session.get("otp_preview_target"),
            "otp_context_label": request.session.get("otp_context_label", "verification"),
            "otp_delivery_mode": request.session.get("otp_delivery_mode", "preview"),
            "otp_delivery_channel": request.session.get("otp_delivery_channel", "email"),
        },
    )


def resend_otp_view(request):
    pending_user_id = request.session.get("pending_user_id")
    if not pending_user_id:
        return redirect("register")
    user = get_object_or_404(User, pk=pending_user_id)
    send_otp_to_user(
        request,
        user,
        context_label="registration",
        preferred_channel=request.session.get("otp_delivery_channel"),
    )
    messages.success(request, "A new OTP has been sent.")
    return redirect("verify_otp")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        identifier = form.cleaned_data["identifier"]
        user = get_user_by_identifier(identifier)
        if not user:
            form.add_error("identifier", "No account found with that username, email, or mobile number.")
        else:
            authenticated_user = authenticate(
                request,
                username=user.username,
                password=form.cleaned_data["password"],
            )
            if not authenticated_user:
                form.add_error("password", "Please enter a correct password.")
            else:
                user = authenticated_user
                login(request, user)
                messages.success(request, "Welcome back.")
                return redirect("dashboard")
    return render(
        request,
        "app/login.html",
        {
            "form": form,
            "console_email_mode": is_console_email_backend(),
        },
    )


def _role_login_view(request, role, wrong_role_message, login_kind):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        identifier = form.cleaned_data["identifier"]
        user = get_user_by_identifier(identifier, role=role)
        if not user:
            any_user = get_user_by_identifier(identifier)
            if any_user:
                form.add_error("identifier", wrong_role_message)
            else:
                form.add_error("identifier", "No account found with that username, email, or mobile number.")
        else:
            authenticated_user = authenticate(
                request,
                username=user.username,
                password=form.cleaned_data["password"],
            )
            if not authenticated_user:
                form.add_error("password", "Please enter a correct password.")
            else:
                login(request, authenticated_user)
                messages.success(request, "Welcome back.")
                return redirect("dashboard")
    return render(
        request,
        "app/login.html",
        {
            "form": form,
            "console_email_mode": is_console_email_backend(),
            "login_kind": login_kind,
        },
    )


def candidate_login_view(request):
    return _role_login_view(
        request,
        role="candidate",
        wrong_role_message="This account is not a candidate profile. Please use company login.",
        login_kind="candidate",
    )


def company_login_view(request):
    return _role_login_view(
        request,
        role="employer",
        wrong_role_message="This account is not a company profile. Please use candidate login.",
        login_kind="company",
    )


def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = ForgotPasswordRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        identifier = form.cleaned_data["identifier"]
        user = get_user_by_identifier(identifier)
        if not user:
            form.add_error("identifier", "No account found with that username, email, or mobile number.")
        else:
            request.session["reset_user_id"] = user.id
            send_otp_to_user(
                request,
                user,
                context_label="password reset",
                preferred_channel=detect_identifier_channel(identifier),
            )
            messages.success(request, "OTP sent. Enter the code and set your new password.")
            return redirect("reset_password")
    return render(request, "app/forgot_password.html", {"form": form})


def reset_password_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    reset_user_id = request.session.get("reset_user_id")
    if not reset_user_id:
        messages.info(request, "Start password reset by entering your username, email, or mobile number.")
        return redirect("forgot_password")

    user = get_object_or_404(User.objects.select_related("profile"), pk=reset_user_id)
    form = ResetPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        otp = user.otps.filter(is_used=False).first()
        if not otp or otp.code != form.cleaned_data["code"] or not otp.is_valid():
            form.add_error("code", "Invalid or expired OTP.")
        else:
            user.set_password(form.cleaned_data["new_password1"])
            user.save(update_fields=["password"])
            otp.is_used = True
            otp.save(update_fields=["is_used"])
            request.session.pop("reset_user_id", None)
            messages.success(request, "Password updated successfully. You can now log in.")
            return redirect("login")

    return render(
        request,
        "app/reset_password.html",
        {
            "form": form,
            "reset_user": user,
            "otp_preview_code": request.session.get("otp_preview_code"),
            "otp_preview_target": request.session.get("otp_preview_target"),
            "otp_context_label": request.session.get("otp_context_label", "password reset"),
            "otp_delivery_mode": request.session.get("otp_delivery_mode", "preview"),
            "otp_delivery_channel": request.session.get("otp_delivery_channel", "email"),
        },
    )


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("index")


@login_required
def dashboard_view(request):
    profile = request.user.profile
    area_labels = [
        "Mar 1",
        "Mar 2",
        "Mar 3",
        "Mar 4",
        "Mar 5",
        "Mar 6",
        "Mar 7",
        "Mar 8",
        "Mar 9",
        "Mar 10",
        "Mar 11",
        "Mar 12",
        "Mar 13",
    ]
    area_labels_display = [
        "Mar 1",
        "",
        "Mar 3",
        "",
        "Mar 5",
        "",
        "Mar 7",
        "",
        "Mar 9",
        "",
        "Mar 11",
        "",
        "Mar 13",
    ]
    area_values = [10000, 30162, 26263, 18394, 18287, 28682, 31274, 33259, 25849, 24159, 32651, 31984, 38451]
    area_max = 40000
    area_points = []
    area_points_plot = []
    for index, value in enumerate(area_values):
        x = 2 + round((96 / (len(area_values) - 1)) * index, 2)
        y = 58 - round((value / area_max) * 48, 2)
        area_points.append(f"{x},{y}")
        area_points_plot.append({"x": x, "y": y, "value": value})

    bar_chart = [
        {"label": "January", "value": 2500},
        {"label": "February", "value": 5000},
        {"label": "March", "value": 7800},
        {"label": "April", "value": 9000},
        {"label": "May", "value": 13000},
    ]
    bar_max = 20000
    for item in bar_chart:
        item["height"] = max(8, round((item["value"] / bar_max) * 100))
        item["bar_width"] = 82

    context = {
        "profile": profile,
        "candidate_total": UserProfile.objects.filter(role="candidate").count(),
        "area_chart_points": area_points,
        "area_chart_points_plot": area_points_plot,
        "area_chart_fill_points": f"2,58 {' '.join(area_points)} 98,58",
        "area_chart_labels": area_labels,
        "area_chart_labels_display": area_labels_display,
        "area_chart_ticks": [40000, 30000, 20000, 10000, 0],
        "bar_chart_data": bar_chart,
        "bar_chart_ticks": [20000, 15000, 10000, 5000, 0],
    }

    if request.user.is_staff:
        context["admin_stats"] = {
            "users": User.objects.count(),
            "companies": Company.objects.count(),
            "jobs": JobPost.objects.count(),
            "applications": JobApplication.objects.count(),
        }

    if profile.role == "employer":
        company = getattr(request.user, "company", None)
        jobs = (
            JobPost.objects.filter(company=company)
            .annotate(total_applications=Count("applications"))
            .order_by("-created_at")
            if company
            else []
        )
        recent_applications = (
            JobApplication.objects.filter(job__company=company)
            .select_related("job", "applicant")
            .order_by("-applied_at")[:6]
            if company
            else []
        )
        context.update(
            {
                "company": company,
                "my_jobs": jobs[:6] if company else [],
                "recent_applications": recent_applications,
                "employer_counts": {
                    "jobs": len(jobs) if isinstance(jobs, list) else jobs.count(),
                    "applicants": (
                        JobApplication.objects.filter(job__company=company).count() if company else 0
                    ),
                    "active_jobs": (
                        JobPost.objects.filter(company=company, is_active=True).count() if company else 0
                    ),
                },
            }
        )
    else:
        my_applications = JobApplication.objects.filter(applicant=request.user).select_related("job", "job__company")
        recommended_jobs = JobPost.objects.filter(is_active=True).select_related("company")[:6]
        context.update(
            {
                "my_applications": my_applications[:6],
                "recommended_jobs": recommended_jobs,
                "candidate_counts": {
                    "applications": my_applications.count(),
                    "shortlisted": my_applications.filter(status="shortlisted").count(),
                    "reviewed": my_applications.filter(status="reviewed").count(),
                },
            }
        )

    return render(request, "app/dashboard.html", context)


@login_required
def profile_view(request):
    form = UserProfileForm(request.POST or None, instance=request.user.profile, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("profile")
    return render(request, "app/profile_form.html", {"form": form})


@login_required
def company_profile_view(request):
    if request.user.profile.role != "employer" and not request.user.is_staff:
        return HttpResponseForbidden("Only employer accounts can manage company details.")

    company = getattr(request.user, "company", None)
    form = CompanyProfileForm(request.POST or None, instance=company)
    if request.method == "POST" and form.is_valid():
        company = form.save(commit=False)
        company.owner = request.user
        company.save()
        messages.success(request, "Company profile saved successfully.")
        return redirect("dashboard")
    return render(request, "app/company_form.html", {"form": form, "company": company})


@login_required
@user_passes_test(is_employer)
def post_job_view(request):
    company = getattr(request.user, "company", None)
    if not company:
        messages.warning(request, "Create your company profile before posting a job.")
        return redirect("company_profile")

    form = JobPostForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.company = company
        job.save()
        messages.success(request, "Job posted successfully.")
        return redirect("job_detail", slug=job.slug)
    return render(request, "app/job_form.html", {"form": form})


def jobs_list_view(request):
    jobs = JobPost.objects.filter(is_active=True).select_related("company")
    query = request.GET.get("q", "").strip()
    location = request.GET.get("location", "").strip()
    category = request.GET.get("category", "").strip()

    if query:
        jobs = jobs.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(company__name__icontains=query)
            | Q(key_skills__icontains=query)
        )
    if location:
        jobs = jobs.filter(Q(location__icontains=location) | Q(city__icontains=location))
    if category:
        jobs = jobs.filter(category=category)

    return render(
        request,
        "app/jobs_list.html",
        {
            "jobs": jobs,
            "filters": {"q": query, "location": location, "category": category},
            "categories": JobPost.CATEGORY_CHOICES,
            "cities": JobPost.objects.exclude(city="").values_list("city", flat=True).distinct().order_by("city"),
        },
    )


def job_detail_view(request, slug):
    job = get_object_or_404(JobPost.objects.select_related("company"), slug=slug, is_active=True)
    already_applied = False
    application_form = None
    if request.user.is_authenticated and request.user.profile.role == "candidate":
        already_applied = JobApplication.objects.filter(job=job, applicant=request.user).exists()
        application_form = JobApplicationForm(user=request.user)
    related_jobs = (
        JobPost.objects.filter(is_active=True, category=job.category)
        .exclude(pk=job.pk)
        .select_related("company")[:3]
    )
    return render(
        request,
        "app/job_detail.html",
        {
            "job": job,
            "already_applied": already_applied,
            "application_form": application_form,
            "related_jobs": related_jobs,
        },
    )


@login_required
def apply_job_view(request, slug):
    job = get_object_or_404(JobPost, slug=slug, is_active=True)
    if request.user.profile.role != "candidate":
        return HttpResponseForbidden("Only candidate accounts can apply for jobs.")
    if JobApplication.objects.filter(job=job, applicant=request.user).exists():
        messages.info(request, "You have already applied for this job.")
        return redirect("job_detail", slug=job.slug)

    form = JobApplicationForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        application = form.save(commit=False)
        application.job = job
        application.applicant = request.user
        application.save()
        messages.success(request, "Application submitted successfully.")
        return redirect("applications")
    return render(
        request,
        "app/job_detail.html",
        {"job": job, "application_form": form, "already_applied": False, "related_jobs": []},
    )


@login_required
def applications_view(request):
    if request.user.profile.role == "employer":
        applications = JobApplication.objects.filter(job__company__owner=request.user).select_related(
            "job", "applicant"
        )
        template_name = "app/employer_applications.html"
    else:
        applications = JobApplication.objects.filter(applicant=request.user).select_related(
            "job", "job__company"
        )
        template_name = "app/application_list.html"
    return render(request, template_name, {"applications": applications})


@login_required
def delete_application_view(request, application_id):
    if request.method != "POST":
        return HttpResponseForbidden("Invalid request method.")
    if request.user.profile.role != "candidate":
        return HttpResponseForbidden("Only candidate accounts can delete their applications.")

    application = get_object_or_404(JobApplication, pk=application_id, applicant=request.user)
    application.delete()
    messages.success(request, "Application deleted successfully.")
    return redirect("applications")


@login_required
@user_passes_test(is_employer)
def my_jobs_view(request):
    company = getattr(request.user, "company", None)
    jobs = (
        JobPost.objects.filter(company=company).annotate(total_applications=Count("applications")).order_by("-created_at")
        if company
        else []
    )
    return render(request, "app/my_jobs.html", {"jobs": jobs, "company": company})


@login_required
@user_passes_test(is_staff_user)
def admin_dashboard_view(request):
    query = request.GET.get("q", "").strip()
    job_results = JobPost.objects.select_related("company")
    if query:
        job_results = job_results.filter(
            Q(title__icontains=query)
            | Q(company__name__icontains=query)
            | Q(category__icontains=query)
            | Q(city__icontains=query)
        )

    admin_monthly_jobs = [
        {"label": "January", "total": 2500, "height": 17, "bar_width": 100},
        {"label": "February", "total": 5000, "height": 33, "bar_width": 100},
        {"label": "March", "total": 7800, "height": 52, "bar_width": 100},
        {"label": "April", "total": 9000, "height": 60, "bar_width": 100},
        {"label": "May", "total": 13000, "height": 87, "bar_width": 100},
    ]

    context = {
        "users_count": User.objects.count(),
        "company_count": Company.objects.count(),
        "jobs_count": JobPost.objects.count(),
        "applications_count": JobApplication.objects.count(),
        "recent_users": User.objects.select_related("profile").order_by("-date_joined")[:8],
        "top_companies": Company.objects.annotate(total_jobs=Count("jobs")).order_by("-total_jobs", "name")[:6],
        "monthly_jobs": admin_monthly_jobs,
        "job_results": job_results[:8],
        "search_query": query,
        "role_split": {
            "candidates": UserProfile.objects.filter(role="candidate").count(),
            "employers": UserProfile.objects.filter(role="employer").count(),
        },
    }
    return render(request, "app/admin_dashboard.html", context)


@login_required
@user_passes_test(is_staff_user)
def user_list_view(request):
    query = request.GET.get("q", "").strip()
    users = User.objects.select_related("profile").order_by("-date_joined")
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(profile__location__icontains=query)
        )
    return render(request, "app/admin_users.html", {"users": users, "search_query": query})


@login_required
@user_passes_test(is_staff_user)
def company_list_view(request):
    query = request.GET.get("q", "").strip()
    vacancy_queryset = (
        JobPost.objects.annotate(total_applications=Count("applications"))
        .order_by("-created_at")
    )
    companies = (
        Company.objects.select_related("owner")
        .prefetch_related(Prefetch("jobs", queryset=vacancy_queryset, to_attr="vacancy_list"))
        .annotate(
            total_jobs=Count("jobs", distinct=True),
            total_openings=Coalesce(Sum("jobs__openings"), 0),
            total_applications=Count("jobs__applications", distinct=True),
        )
        .order_by("name")
    )
    if query:
        companies = companies.filter(
            Q(name__icontains=query)
            | Q(owner__username__icontains=query)
            | Q(location__icontains=query)
            | Q(industry__icontains=query)
        )
    return render(request, "app/admin_companies.html", {"companies": companies, "search_query": query})


@login_required
@user_passes_test(is_staff_user)
def admin_jobs_view(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    jobs = JobPost.objects.select_related("company").annotate(total_applications=Count("applications"))
    if query:
        jobs = jobs.filter(
            Q(title__icontains=query)
            | Q(company__name__icontains=query)
            | Q(city__icontains=query)
            | Q(location__icontains=query)
        )
    if category:
        jobs = jobs.filter(category=category)
    return render(
        request,
        "app/admin_jobs.html",
        {
            "jobs": jobs.order_by("-created_at"),
            "search_query": query,
            "selected_category": category,
            "categories": JobPost.CATEGORY_CHOICES,
        },
    )


@login_required
@user_passes_test(is_staff_user)
def admin_job_applications_view(request, slug):
    job = get_object_or_404(JobPost.objects.select_related("company"), slug=slug)
    applications = (
        JobApplication.objects.filter(job=job)
        .select_related("applicant", "job", "job__company")
        .order_by("-applied_at")
    )
    return render(
        request,
        "app/admin_job_applications.html",
        {
            "job": job,
            "applications": applications,
        },
    )
