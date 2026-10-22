from django.urls import path
from debugger import views

app_name = 'debugger'

urlpatterns = [
    # Pages
    path('', views.landing_view, name='landing'),
    path('debugger/', views.debugger_view, name='debugger'),
    path('analysis/<uuid:analysis_id>/', views.results_view, name='results'),
    path('history/', views.history_view, name='history'),
    path('how-it-works/', views.how_it_works_view, name='how_it_works'),

    # REST APIs
    path('api/upload-document/', views.api_upload_document, name='api_upload_document'),
    path('api/documents/', views.api_list_documents, name='api_list_documents'),
    path('api/documents/<uuid:doc_id>/delete/', views.api_delete_document, name='api_delete_document'),
    path('api/analyze/', views.api_analyze, name='api_analyze'),
    path('api/history/', views.api_history, name='api_history'),
    path('api/load-sample-doc/', views.api_load_sample_doc, name='api_load_sample_doc'),
]
