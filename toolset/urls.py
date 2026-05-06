from django.urls import path

from .views import activity_status, dashboard, download_file, image_editor, image_editor_process, run_tool

app_name = 'toolset'

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('run/<str:task_type>/', run_tool, name='run_tool'),
    path('downloads/<path:relative_path>/', download_file, name='download_file'),
    path('activity-status/', activity_status, name='activity_status'),
    path('image-editor/', image_editor, name='image_editor'),
    path('image-editor/process/', image_editor_process, name='image_editor_process'),
]
