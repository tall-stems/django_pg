from django.db import models
from django.contrib.auth.models import User

class Note(models.Model):
    completed = models.BooleanField(default=False)
    title = models.CharField(max_length=200)
    text = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notes")