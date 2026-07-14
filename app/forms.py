from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import EmailValidator

from .models import Company, JobApplication, JobPost, UserProfile


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    contact = forms.CharField(
        label="Email or Mobile Number",
        widget=forms.TextInput(attrs={"placeholder": "Enter email or mobile number"}),
    )
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "contact", "role", "password1", "password2")

    def clean_contact(self):
        contact = (self.cleaned_data.get("contact") or "").strip()
        selected_role = self.cleaned_data.get("role") or (self.data.get("role") if hasattr(self, "data") else None)
        if not contact:
            raise forms.ValidationError("Enter your email address or mobile number.")

        validator = EmailValidator()
        is_email = True
        try:
            validator(contact)
        except forms.ValidationError:
            is_email = False

        if is_email:
            existing_email_users = User.objects.filter(email__iexact=contact).select_related("profile")
            if selected_role in ("candidate", "employer"):
                if existing_email_users.filter(profile__role=selected_role).exists():
                    role_label = "candidate" if selected_role == "candidate" else "company"
                    raise forms.ValidationError(f"This email address is already registered as a {role_label}.")
            elif existing_email_users.exists():
                raise forms.ValidationError("This email address is already registered.")
            self.cleaned_data["contact_type"] = "email"
            self.cleaned_data["normalized_contact"] = contact
            return contact

        normalized_phone = "".join(char for char in contact if char.isdigit() or char == "+")
        if len([char for char in normalized_phone if char.isdigit()]) < 10:
            raise forms.ValidationError("Enter a valid email address or mobile number.")
        existing_phone_profiles = UserProfile.objects.filter(phone=normalized_phone).exclude(phone="")
        if selected_role in ("candidate", "employer"):
            if existing_phone_profiles.filter(role=selected_role).exists():
                role_label = "candidate" if selected_role == "candidate" else "company"
                raise forms.ValidationError(f"This mobile number is already registered as a {role_label}.")
        elif existing_phone_profiles.exists():
            raise forms.ValidationError("This mobile number is already registered.")
        self.cleaned_data["contact_type"] = "phone"
        self.cleaned_data["normalized_contact"] = normalized_phone
        return contact


class OTPVerificationForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={"placeholder": "Enter 6-digit OTP"}),
    )


class LoginForm(forms.Form):
    identifier = forms.CharField(
        label="Username / Email / Mobile",
        widget=forms.TextInput(attrs={"placeholder": "Username, email or mobile number"}),
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Password"}))


class ForgotPasswordRequestForm(forms.Form):
    identifier = forms.CharField(
        label="Username / Email / Mobile",
        widget=forms.TextInput(attrs={"placeholder": "Enter username, email or mobile number"}),
    )


class ResetPasswordForm(forms.Form):
    code = forms.CharField(
        label="OTP Code",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={"placeholder": "Enter 6-digit OTP"}),
    )
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Enter new password"}),
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm new password"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")
        if password1 and password2 and password1 != password2:
            self.add_error("new_password2", "Both password fields must match.")
        return cleaned_data


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.EmailField()

    class Meta:
        model = UserProfile
        fields = ("first_name", "last_name", "email", "phone", "location", "bio", "skills", "resume_link")
        widgets = {
            "phone": forms.TextInput(attrs={"placeholder": "+91 9876543210"}),
            "location": forms.TextInput(attrs={"placeholder": "Mumbai"}),
            "bio": forms.Textarea(attrs={"rows": 4, "placeholder": "Tell employers about your profile."}),
            "skills": forms.Textarea(attrs={"rows": 3, "placeholder": "Python, React, SQL"}),
            "resume_link": forms.URLInput(attrs={"placeholder": "https://drive.google.com/..."}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["first_name"].initial = user.first_name
        self.fields["last_name"].initial = user.last_name
        self.fields["email"].initial = user.email

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.exclude(pk=self.user.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError("This email address is already in use.")
        return email

    def save(self, commit=True):
        profile = super().save(commit=False)
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]
        self.user.email = self.cleaned_data["email"]
        if commit:
            self.user.save()
            profile.save()
        return profile


class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ("name", "industry", "email", "website", "location", "description")
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "NovaStack Labs"}),
            "industry": forms.TextInput(attrs={"placeholder": "Cloud engineering"}),
            "email": forms.EmailInput(attrs={"placeholder": "hiring@novastack.com"}),
            "website": forms.URLInput(attrs={"placeholder": "https://novastack.com"}),
            "location": forms.TextInput(attrs={"placeholder": "Mumbai, Maharashtra"}),
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "Describe your company and hiring culture."}),
        }


class JobPostForm(forms.ModelForm):
    class Meta:
        model = JobPost
        fields = (
            "title",
            "category",
            "employment_type",
            "workplace_type",
            "experience_level",
            "city",
            "state",
            "location",
            "salary",
            "openings",
            "key_skills",
            "description",
            "requirements",
            "application_deadline",
            "is_active",
        )
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Senior Python Developer"}),
            "city": forms.TextInput(attrs={"placeholder": "Mumbai"}),
            "state": forms.TextInput(attrs={"placeholder": "Maharashtra"}),
            "location": forms.TextInput(attrs={"placeholder": "Auto-filled from city and state"}),
            "salary": forms.TextInput(attrs={"placeholder": "Rs 12 LPA - Rs 18 LPA"}),
            "openings": forms.NumberInput(attrs={"min": 1}),
            "key_skills": forms.Textarea(attrs={"rows": 3, "placeholder": "Python, Django, REST APIs"}),
            "description": forms.Textarea(attrs={"rows": 6, "placeholder": "Explain the role, team, and impact."}),
            "requirements": forms.Textarea(attrs={"rows": 5, "placeholder": "Experience, tools, and must-have skills."}),
            "application_deadline": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location"].required = False
        self.fields["location"].widget.attrs["readonly"] = True


class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = (
            "full_name",
            "email",
            "phone",
            "current_city",
            "skills",
            "experience_years",
            "resume_link",
            "portfolio_link",
            "cover_letter",
        )
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Your full name"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "phone": forms.TextInput(attrs={"placeholder": "+91 9876543210"}),
            "current_city": forms.TextInput(attrs={"placeholder": "Mumbai"}),
            "skills": forms.Textarea(attrs={"rows": 3, "placeholder": "Python, SQL, React"}),
            "experience_years": forms.NumberInput(attrs={"min": 0, "max": 40}),
            "resume_link": forms.URLInput(attrs={"placeholder": "https://drive.google.com/..."}),
            "portfolio_link": forms.URLInput(attrs={"placeholder": "https://github.com/yourname"}),
            "cover_letter": forms.Textarea(
                attrs={"rows": 6, "placeholder": "Tell the employer why you are a great fit."}
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            profile = getattr(user, "profile", None)
            self.fields["full_name"].initial = user.get_full_name() or user.username
            self.fields["email"].initial = user.email
            if profile:
                self.fields["phone"].initial = profile.phone
                self.fields["current_city"].initial = profile.location
                self.fields["skills"].initial = profile.skills
                self.fields["resume_link"].initial = profile.resume_link
