from django.conf import settings
from isle.cache import get_user_available_contexts
from isle.models import Context, ZendeskData


def context(request):
    contexts = []
    if request.user.is_authenticated:
        qs = Context.objects.filter(uuid__in=get_user_available_contexts(request.user) or [])\
            .values_list('id', 'title', 'guid', 'uuid').order_by('title', 'guid', 'uuid')
        contexts = [(i[0], i[1] or i[2] or i[3]) for i in qs]
    return {
        'AVAILABLE_CONTEXTS': contexts,
        'ZENDESK_DATA': ZendeskData.objects.first(),
        'NOW_URL': settings.NOW_URL,
        'HEADER_CABINET_URL': settings.HEADER_CABINET_URL,
        'HEADER_FULL_SCHEDULE_URL': settings.HEADER_FULL_SCHEDULE_URL,
        'HEADER_MY_SCHEDULE_URL': settings.HEADER_MY_SCHEDULE_URL,
    }
