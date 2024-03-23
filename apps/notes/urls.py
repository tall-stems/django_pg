from django.urls import path

from . import views

app_name = "notes"
urlpatterns = [
    path("", views.NotesListView.as_view(), name="list"),
    path("<int:pk>", views.NoteDetailView.as_view(), name="detail"),
    path("create", views.NoteCreateView.as_view(), name="create"),
    path("<int:pk>/edit", views.NoteUpdateView.as_view(), name="update"),
    path("<int:pk>/delete", views.NoteDeleteView.as_view(), name="delete"),
]
