from django.http import HttpResponseRedirect
from django.views.generic import CreateView, ListView, DetailView, UpdateView
from django.views.generic.edit import DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin

from .forms import NoteForm
from .models import Note

class NoteDeleteView(DeleteView):
    model = Note
    success_url = '/notes/'
    template_name = 'notes/note_delete.html'

class NoteUpdateView(UpdateView):
    model = Note
    form_class = NoteForm
    success_url = '/notes/'

    def form_valid(self, form):
        """Override to handle note update."""
        response = super().form_valid(form)
        # Could add notification task here if needed
        return response

class NoteCreateView(CreateView):
    model = Note
    form_class = NoteForm
    success_url = '/notes/'

    def form_valid(self, form):
        """Override to set the user on note creation."""
        self.object = form.save(commit=False)
        self.object.user = self.request.user
        self.object.save()

        # Note created - could add notification task here if needed
        return HttpResponseRedirect(self.get_success_url())


class NotesListView(LoginRequiredMixin, ListView):
    model = Note
    context_object_name = 'notes'
    template_name = 'notes/note_list.html'
    login_url = '/login'

    def get_queryset(self):
        return self.request.user.notes.all()

class NoteDetailView(DetailView):
    model = Note
    template_name = 'notes/note_detail.html'
    context_object_name = 'note'
