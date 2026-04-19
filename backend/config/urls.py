"""
URL configuration for config project.

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
from django.urls import path

from api import views as api_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/transcripts/fetch', api_views.fetch_transcript, name='fetch_transcript'),
    path('api/transcripts/<uuid:pk>/summarize/', api_views.SummarizeView.as_view(), name='summarize-transcript'),
]
