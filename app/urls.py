from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("register/", views.register_view, name="register"),
    path("register/candidate/", views.candidate_register_view, name="candidate_register"),
    path("register/company/", views.company_register_view, name="company_register"),
    path("verify-otp/", views.verify_otp_view, name="verify_otp"),
    path("resend-otp/", views.resend_otp_view, name="resend_otp"),
    path("login/", views.login_view, name="login"),
    path("login/candidate/", views.candidate_login_view, name="candidate_login"),
    path("login/company/", views.company_login_view, name="company_login"),
    path("forgot-password/", views.forgot_password_view, name="forgot_password"),
    path("reset-password/", views.reset_password_view, name="reset_password"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("profile/", views.profile_view, name="profile"),
    path("company/", views.company_profile_view, name="company_profile"),
    path("jobs/", views.jobs_list_view, name="jobs"),
    path("jobs/post/", views.post_job_view, name="post_job"),
    path("jobs/mine/", views.my_jobs_view, name="my_jobs"),
    path("jobs/<slug:slug>/", views.job_detail_view, name="job_detail"),
    path("jobs/<slug:slug>/apply/", views.apply_job_view, name="apply_job"),
    path("applications/", views.applications_view, name="applications"),
    path("applications/<int:application_id>/delete/", views.delete_application_view, name="delete_application"),
    path("staff/dashboard/", views.admin_dashboard_view, name="admin_dashboard"),
    path("staff/users/", views.user_list_view, name="user_list"),
    path("staff/companies/", views.company_list_view, name="company_list"),
    path("staff/jobs/", views.admin_jobs_view, name="admin_jobs"),
    path("staff/jobs/<slug:slug>/applications/", views.admin_job_applications_view, name="admin_job_applications"),
]
