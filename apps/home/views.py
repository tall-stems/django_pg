from django.shortcuts import redirect
from datetime import datetime
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView
from django.contrib.auth.views import LoginView, LogoutView

from .forms import CustomUserCreationForm

class SignupInterfaceView(CreateView):
    template_name = 'home/signup.html'
    success_url = '/'
    form_class = CustomUserCreationForm

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('home:home')
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        """Override to handle user creation."""
        response = super().form_valid(form)
        # User created successfully - could add welcome email task here if needed
        return response

class LoginInterfaceView(LoginView):
    template_name = 'home/login.html'

class LogoutInterfaceView(LogoutView):
    template_name = 'home/logout.html'

class HomeView(TemplateView):
    template_name = 'home/index.html'
    extra_context = {'today': datetime.today().strftime("%Y, %B %d - %H:%M:%S %Z")}
