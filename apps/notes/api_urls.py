from django.urls import path

from . import api_views

app_name = "notes"
urlpatterns = [
    path("", api_views.NotesListAPIView.as_view(), name="api_notes_list"),
    path("create", api_views.NoteCreateAPIView.as_view(), name="api_note_create"),
    path("<int:id>/delete", api_views.NoteDeleteAPIView.as_view(), name="api_note_delete"),
]
