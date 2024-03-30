from rest_framework import serializers

from .models import Note

class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ('id', 'title', 'text', 'date_created', 'user')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['user'] = instance.user.username
        return data