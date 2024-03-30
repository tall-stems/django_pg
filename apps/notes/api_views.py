from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, CreateAPIView, DestroyAPIView, UpdateAPIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.pagination import LimitOffsetPagination
from django.contrib.auth.models import User

from notes.serializers import NoteSerializer
from notes.models import Note

class NotesPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 100

class NotesListAPIView(ListAPIView):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    filter_backends = (DjangoFilterBackend, SearchFilter)
    filterset_fields = ('id',)
    search_fields = ('title', 'text')
    pagination_class = NotesPagination

    def get_queryset(self):
        is_completed = self.request.query_params.get('completed', None)
        if is_completed is None:
            return super().get_queryset()
        queryset = Note.objects.all()
        if is_completed.lower() == 'true':
            # TODO: can handle filtering by completed here once
            # you turn notes into tasks
            # queryset = queryset.filter(completed=True)
            queryset = queryset.filter(id__lte=4)

        return queryset


class NoteCreateAPIView(CreateAPIView):
    serializer_class = NoteSerializer

    def create(self, request, *args, **kwargs):
        try:
            note = request.data
            if note['user'] is None:
                note['user'] = request.user.id
        except AttributeError as e:
            raise ValidationError("Incorrect or missing note data: " + str(e))
        return super().create(request, *args, **kwargs)


class NoteDeleteAPIView(DestroyAPIView):
    queryset = Note.objects.all()
    lookup_field = 'id'

    def delete(self, request, *args, **kwargs):

        note_id = request.data.get('id')
        response = super().delete(request, *args, **kwargs)
        # Delete related cache data if note is deleted
        if response.status_code == 204:
            from django.core.cache import cache
            cache.delete('note_data_{}'.format(note_id))
        return response


# class NoteUpdateAPIView(UpdateAPIView):
#     queryset = Note.objects.all()
#     serializer_class = NoteSerializer
#     lookup_field = 'id'
#     def update(self, request, *args, **kwargs):
#         try:
#             note = request.data
#             if note['user'] is None:
#                 note['user'] = request.user.id
#         except AttributeError as e:
#             raise ValidationError("Incorrect or missing note data: " + str(e))
#         return super().update(request, *args, **kwargs)