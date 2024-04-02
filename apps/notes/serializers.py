from rest_framework import serializers

from .models import Note

class NoteSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')
    class Meta:
        model = Note
        fields = ('id', 'completed', 'title', 'text', 'date_created', 'user', 'username')

    # If you need more precise control can modify fields or add calculated fields via the to_representation method
    # def to_representation(self, instance):
    #     data = super().to_representation(instance)
    #     data['user'] = instance.user.username
    #     return data