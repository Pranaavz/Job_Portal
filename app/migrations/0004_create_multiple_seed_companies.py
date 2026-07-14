from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations


def assign_companies(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    UserProfile = apps.get_model("app", "UserProfile")
    Company = apps.get_model("app", "Company")
    JobPost = apps.get_model("app", "JobPost")

    company_seed = [
        {
            "username": "portal_employer",
            "defaults": {
                "first_name": "NovaStack",
                "last_name": "Admin",
                "email": "careers@novastack.example",
                "is_active": True,
            },
            "profile": {
                "role": "employer",
                "location": "Mumbai",
                "is_verified": True,
                "phone": "+919000000001",
            },
            "company": {
                "name": "NovaStack Technologies",
                "slug": "novastack-technologies",
                "email": "careers@novastack.example",
                "website": "https://novastack.example",
                "location": "Mumbai, Maharashtra",
                "industry": "Information Technology",
                "description": "Product engineering and full-stack software delivery company.",
            },
        },
        {
            "username": "digiskill_employer",
            "defaults": {
                "first_name": "DigiSkill",
                "last_name": "Admin",
                "email": "careers@digiskill.example",
                "is_active": True,
            },
            "profile": {
                "role": "employer",
                "location": "Pune",
                "is_verified": True,
                "phone": "+919000000002",
            },
            "company": {
                "name": "DigiSkill Labs",
                "slug": "digiskill-labs",
                "email": "careers@digiskill.example",
                "website": "https://digiskill.example",
                "location": "Pune, Maharashtra",
                "industry": "Digital Engineering",
                "description": "Design, frontend, and applied AI engineering company.",
            },
        },
        {
            "username": "tcs_consistency_employer",
            "defaults": {
                "first_name": "TCS",
                "last_name": "Consistency",
                "email": "careers@tcsconsistency.example",
                "is_active": True,
            },
            "profile": {
                "role": "employer",
                "location": "Bengaluru",
                "is_verified": True,
                "phone": "+919000000003",
            },
            "company": {
                "name": "TCS Consistency",
                "slug": "tcs-consistency",
                "email": "careers@tcsconsistency.example",
                "website": "https://tcsconsistency.example",
                "location": "Bengaluru, Karnataka",
                "industry": "Enterprise Technology",
                "description": "Backend, cloud, and enterprise infrastructure hiring brand.",
            },
        },
        {
            "username": "wiproithub_employer",
            "defaults": {
                "first_name": "Wipro",
                "last_name": "IThub",
                "email": "careers@wiproithub.example",
                "is_active": True,
            },
            "profile": {
                "role": "employer",
                "location": "Chennai",
                "is_verified": True,
                "phone": "+919000000004",
            },
            "company": {
                "name": "WiproIThub",
                "slug": "wiproithub",
                "email": "careers@wiproithub.example",
                "website": "https://wiproithub.example",
                "location": "Chennai, Tamil Nadu",
                "industry": "IT Services",
                "description": "Cybersecurity, QA, and systems operations hiring company.",
            },
        },
    ]

    companies = {}
    for item in company_seed:
        user, created = User.objects.get_or_create(username=item["username"], defaults=item["defaults"])
        if created:
            user.password = make_password("Portal12345")
            user.save(update_fields=["password"])
        UserProfile.objects.update_or_create(user=user, defaults=item["profile"])
        company, _ = Company.objects.update_or_create(owner=user, defaults=item["company"])
        companies[company.name] = company

    assignments = {
        "Software Developer": "NovaStack Technologies",
        "Data Scientist": "NovaStack Technologies",
        "UI/UX Web Designer": "DigiSkill Labs",
        "QA Automation Engineer": "DigiSkill Labs",
        "Database Engineer": "TCS Consistency",
        "Cloud DevOps Engineer": "TCS Consistency",
        "Cybersecurity Analyst": "WiproIThub",
        "Network and Systems Engineer": "WiproIThub",
    }

    for title, company_name in assignments.items():
        JobPost.objects.filter(title=title).update(company=companies[company_name])


def unassign_companies(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Company = apps.get_model("app", "Company")
    JobPost = apps.get_model("app", "JobPost")

    try:
        primary_company = Company.objects.get(name="NovaStack Technologies")
    except Company.DoesNotExist:
        primary_company = None

    if primary_company:
        JobPost.objects.all().update(company=primary_company)

    for username in ["digiskill_employer", "tcs_consistency_employer", "wiproithub_employer"]:
        try:
            user = User.objects.get(username=username)
            user.company.delete()
            user.delete()
        except User.DoesNotExist:
            continue


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0003_seed_portal_jobs_and_backfill"),
    ]

    operations = [
        migrations.RunPython(assign_companies, unassign_companies),
    ]
