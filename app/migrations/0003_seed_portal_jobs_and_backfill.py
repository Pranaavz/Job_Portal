from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.utils.text import slugify


def build_unique_slug(model, value):
    base_slug = slugify(value) or "item"
    slug = base_slug
    counter = 1
    while model.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def seed_jobs(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    UserProfile = apps.get_model("app", "UserProfile")
    Company = apps.get_model("app", "Company")
    JobPost = apps.get_model("app", "JobPost")
    JobApplication = apps.get_model("app", "JobApplication")

    for application in JobApplication.objects.select_related("applicant").all():
        applicant = application.applicant
        profile = getattr(applicant, "profile", None)
        application.full_name = application.full_name or applicant.get_full_name() or applicant.username
        application.email = application.email or applicant.email or ""
        if profile:
            application.phone = application.phone or profile.phone
            application.current_city = application.current_city or profile.location
            application.skills = application.skills or profile.skills
            application.resume_link = application.resume_link or profile.resume_link
        application.save()

    for job in JobPost.objects.all():
        if job.location and not job.city:
            parts = [part.strip() for part in job.location.split(",") if part.strip()]
            if parts:
                job.city = parts[0]
                if len(parts) > 1:
                    job.state = parts[1]
                job.save()

    portal_user, created = User.objects.get_or_create(
        username="portal_employer",
        defaults={
            "first_name": "Portal",
            "last_name": "Employer",
            "email": "portal@example.com",
            "is_active": True,
        },
    )
    if created:
        portal_user.password = make_password("Portal12345")
        portal_user.save(update_fields=["password"])
    UserProfile.objects.update_or_create(
        user=portal_user,
        defaults={
            "role": "employer",
            "location": "Mumbai",
            "is_verified": True,
            "phone": "+919000000001",
        },
    )
    company, _ = Company.objects.get_or_create(
        owner=portal_user,
        defaults={
            "name": "NovaStack Technologies",
            "slug": "novastack-technologies",
            "email": "careers@novastack.example",
            "website": "https://novastack.example",
            "location": "Mumbai, Maharashtra",
            "industry": "Information Technology",
            "description": "IT services and product engineering company used to showcase live technical jobs across the platform.",
        },
    )

    job_seed = [
        {
            "title": "Software Developer",
            "category": "software-development",
            "employment_type": "full-time",
            "workplace_type": "hybrid",
            "experience_level": "mid",
            "city": "Mumbai",
            "state": "Maharashtra",
            "salary": "Rs 8 LPA - Rs 14 LPA",
            "openings": 3,
            "key_skills": "Python, Django, REST API, Git",
            "description": "Build application features, improve APIs, and collaborate with product and QA teams.",
            "requirements": "2+ years in backend or full-stack development with strong coding fundamentals.",
        },
        {
            "title": "UI/UX Web Designer",
            "category": "web-design",
            "employment_type": "full-time",
            "workplace_type": "on-site",
            "experience_level": "mid",
            "city": "Pune",
            "state": "Maharashtra",
            "salary": "Rs 6 LPA - Rs 10 LPA",
            "openings": 2,
            "key_skills": "Figma, HTML, CSS, Responsive Design",
            "description": "Design modern interfaces and hand off high-quality web experiences to engineering teams.",
            "requirements": "Portfolio with landing pages, dashboards, and mobile-friendly layouts.",
        },
        {
            "title": "Database Engineer",
            "category": "database-backend",
            "employment_type": "full-time",
            "workplace_type": "hybrid",
            "experience_level": "senior",
            "city": "Bengaluru",
            "state": "Karnataka",
            "salary": "Rs 14 LPA - Rs 20 LPA",
            "openings": 2,
            "key_skills": "PostgreSQL, Query Tuning, Data Modeling, Backup Strategy",
            "description": "Own schema design, database reliability, and backend data performance for large systems.",
            "requirements": "Strong SQL optimization and production database administration experience.",
        },
        {
            "title": "Data Scientist",
            "category": "data-ai",
            "employment_type": "full-time",
            "workplace_type": "remote",
            "experience_level": "mid",
            "city": "Hyderabad",
            "state": "Telangana",
            "salary": "Rs 12 LPA - Rs 18 LPA",
            "openings": 2,
            "key_skills": "Python, Pandas, Machine Learning, NLP",
            "description": "Work on forecasting, recommendation, and AI model experiments for product teams.",
            "requirements": "Experience building production-ready ML pipelines and communicating findings clearly.",
        },
        {
            "title": "Cybersecurity Analyst",
            "category": "cybersecurity",
            "employment_type": "full-time",
            "workplace_type": "on-site",
            "experience_level": "mid",
            "city": "Chennai",
            "state": "Tamil Nadu",
            "salary": "Rs 9 LPA - Rs 15 LPA",
            "openings": 2,
            "key_skills": "SIEM, Vulnerability Assessment, Incident Response",
            "description": "Monitor threats, investigate incidents, and improve the security posture across systems.",
            "requirements": "Hands-on experience with security tooling and response playbooks.",
        },
        {
            "title": "Cloud DevOps Engineer",
            "category": "cloud-devops",
            "employment_type": "full-time",
            "workplace_type": "hybrid",
            "experience_level": "senior",
            "city": "Noida",
            "state": "Uttar Pradesh",
            "salary": "Rs 15 LPA - Rs 24 LPA",
            "openings": 2,
            "key_skills": "AWS, Docker, Kubernetes, CI/CD",
            "description": "Automate infrastructure, improve deployments, and build reliable cloud environments.",
            "requirements": "Strong infrastructure-as-code, monitoring, and production operations experience.",
        },
        {
            "title": "Network and Systems Engineer",
            "category": "networking-systems",
            "employment_type": "full-time",
            "workplace_type": "on-site",
            "experience_level": "mid",
            "city": "Delhi",
            "state": "Delhi",
            "salary": "Rs 7 LPA - Rs 12 LPA",
            "openings": 2,
            "key_skills": "LAN/WAN, Linux Servers, Firewall, Monitoring",
            "description": "Support network availability, server administration, and infrastructure troubleshooting.",
            "requirements": "Experience managing enterprise systems and day-to-day operations.",
        },
        {
            "title": "QA Automation Engineer",
            "category": "testing-qa",
            "employment_type": "full-time",
            "workplace_type": "hybrid",
            "experience_level": "entry",
            "city": "Ahmedabad",
            "state": "Gujarat",
            "salary": "Rs 5 LPA - Rs 9 LPA",
            "openings": 3,
            "key_skills": "Selenium, Test Cases, API Testing, Bug Reporting",
            "description": "Create automated test suites, validate releases, and partner with developers on quality.",
            "requirements": "Strong testing mindset with manual and automation exposure.",
        },
    ]

    for item in job_seed:
        if JobPost.objects.filter(company=company, title=item["title"]).exists():
            continue
        JobPost.objects.create(
            company=company,
            slug=build_unique_slug(JobPost, f'{item["title"]}-{company.name}'),
            location=f'{item["city"]}, {item["state"]}',
            source_label="Portal",
            is_active=True,
            **item,
        )


def remove_seed_jobs(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Company = apps.get_model("app", "Company")
    JobPost = apps.get_model("app", "JobPost")

    try:
        user = User.objects.get(username="portal_employer")
        company = Company.objects.get(owner=user)
    except (User.DoesNotExist, Company.DoesNotExist):
        return

    JobPost.objects.filter(company=company).delete()
    company.delete()
    user.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0002_jobapplication_current_city_jobapplication_email_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_jobs, remove_seed_jobs),
    ]
