from django.urls import path
from . import views

urlpatterns = [
    path('api/v1/calculate-blood-loss', views.calculate_blood_loss, name='calculate_blood_loss'),
    path('api/v1/direct-update', views.direct_update, name='direct_update'),
    path('api/v1/health', views.health_check, name='health_check'),
    path('api/v1/tasks/<int:task_id>', views.task_status, name='task_status'),
]