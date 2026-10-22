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
    path('login/', views.auth_view, name='login'),
    path('signup/', views.auth_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),

    # REST APIs
    path('api/auth/session-login/', views.api_session_login, name='api_session_login'),
    path('api/auth/session-logout/', views.api_session_logout, name='api_session_logout'),
    path('api/upload-document/', views.api_upload_document, name='api_upload_document'),
    path('api/documents/', views.api_list_documents, name='api_list_documents'),
    path('api/documents/<uuid:doc_id>/delete/', views.api_delete_document, name='api_delete_document'),
    path('api/analyze/', views.api_analyze, name='api_analyze'),
    path('api/history/', views.api_history, name='api_history'),
    path('api/load-sample-doc/', views.api_load_sample_doc, name='api_load_sample_doc'),
]
