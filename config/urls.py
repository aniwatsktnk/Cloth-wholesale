from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path, include
from django.http import HttpResponse
urlpatterns=[
 path("admin/",admin.site.urls),
 path("login/",auth.LoginView.as_view(template_name="login.html"),name="login"),
 path("logout/",auth.LogoutView.as_view(),name="logout"),
 path("password/",auth.PasswordChangeView.as_view(template_name="form.html",success_url="/"),name="password"),
 path("robots.txt",lambda r:HttpResponse("User-agent: *\nDisallow: /\n",content_type="text/plain")),
 path("",include("shop.urls")),
]
