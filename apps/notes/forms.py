from django import forms

from .models import Note

class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['completed', 'title', 'text']
        widgets = {
            'completed': forms.CheckboxInput(attrs={'class': 'checkbox mb-2'}),
            'title': forms.TextInput(attrs={'class': 'input mb-2'}),
            'text': forms.Textarea(attrs={'class': 'textarea mb-2'}),
        }
        labels = {
            'completed': 'Completed',
            'title': 'Title',
            'text': 'Write note here'
        }

    def clean_title(self):
        title = self.cleaned_data['title']
        # if 'Django' not in title:
        #     raise forms.ValidationError('Title must contain "Django"')
        return title