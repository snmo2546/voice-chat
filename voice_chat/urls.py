"""
URL configuration for voice_chat project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from chat import views as chat_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Render routes (UI)
    path('', chat_views.chat_interface, name='home'),
    path('chat/', chat_views.chat_interface, name='chat_interface'),
    
    # API routes
    path('api/chat/', include('chat.urls')),
    path('api/users/', include('users.urls')),
]