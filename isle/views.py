import functools
import logging
import os
from itertools import permutations, combinations
from collections import defaultdict
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import logout as base_logout
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views.generic import TemplateView, View
from dal import autocomplete
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from social_django.models import UserSocialAuth
from isle.forms import CreateTeamForm, AddUserForm
from isle.models import Event, EventEntry, EventMaterial, User, Trace, Team, EventTeamMaterial, EventOnlyMaterial, \
    Attendance
from isle.serializers import AttendanceSerializer
from isle.utils import refresh_events_data, get_allowed_event_type_ids, update_check_ins_for_event, set_check_in


def login(request):
    return render(request, 'login.html', {'next': request.GET.get('next', reverse('index'))})


def logout(request):
    return base_logout(request, next_page='index')


@method_decorator(login_required, name='dispatch')
class Index(TemplateView):
    """
    все эвенты (доступные пользователю)
    """
    template_name = 'index.html'
    DATE_FORMAT = '%Y-%m-%d'

    def get_context_data(self, **kwargs):
        date = self.get_date()
        objects = self.get_events()
        ctx = {
                'objects': objects,
                'date': date.strftime(self.DATE_FORMAT),
                'total_elements': EventMaterial.objects.count() + EventTeamMaterial.objects.count() + EventOnlyMaterial.objects.count(),
                'today_elements': EventMaterial.objects.filter(event__in=objects).count() + EventTeamMaterial.objects.filter(event__in=objects).count() + EventOnlyMaterial.objects.filter(event__in=objects).count(),
        }
        if self.request.user.is_assistant:
            enrollments = dict(EventEntry.objects.values_list('event_id').annotate(cnt=Count('user_id')))
            check_ins = dict(EventEntry.objects.filter(is_active=True).values_list('event_id')
                             .annotate(cnt=Count('user_id')))
            for obj in objects:
                obj.prop_enrollments = enrollments.get(obj.id, 0)
                obj.prop_checkins = check_ins.get(obj.id, 0)
        return ctx

    def get_date(self):
        try:
            date = timezone.datetime.strptime(self.request.GET.get('date'), self.DATE_FORMAT).date()
        except:
            date = timezone.localtime(timezone.now()).date()
        return date

    def get_events(self):
        if self.request.user.is_assistant:
            events = Event.objects.filter(is_active=True)
        else:
            events = Event.objects.filter(id__in=EventEntry.objects.filter(user=self.request.user).
                                          values_list('event_id', flat=True))
        if settings.VISIBLE_EVENT_TYPES:
            events = events.filter(event_type_id__in=get_allowed_event_type_ids())
        date = self.get_date()
        if date:
            min_dt = timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.min.time()))
            max_dt = min_dt + timezone.timedelta(days=1)
            events = events.filter(dt_start__gte=min_dt, dt_start__lt=max_dt)
        events = events.order_by('-dt_end')
        inactive_events, active_events, current_events = [], [], []
        delta = settings.CURRENT_EVENT_DELTA
        for e in events:
            if not e.is_active:
                inactive_events.append(e)
            elif e.dt_end and timezone.now() - timezone.timedelta(seconds=delta) < e.dt_end < timezone.now() \
                    + timezone.timedelta(seconds=delta):
                current_events.append(e)
            else:
                active_events.append(e)
        current_events.reverse()
        return current_events + active_events + inactive_events


class GetEventMixin:
    @cached_property
    def event(self):
        return get_object_or_404(Event, uid=self.kwargs['uid'])

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class GetEventMixinWithAccessCheck(GetEventMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect('{}?next={}'.format(reverse('login'), request.get_full_path()))
        if request.user.is_assistant or EventEntry.objects.filter(user=request.user, event=self.event).exists():
            return super().dispatch(request, *args, **kwargs)
        return render(request, 'to_xle.html', {
            'link': getattr(settings, 'XLE_URL', 'https://xle.2035.university/feedback'),
            'event': self.event,
        })


def get_event_participants(event):
    users = EventEntry.objects.filter(event=event).values_list('user_id')
    return User.objects.filter(id__in=users).order_by('last_name', 'first_name', 'second_name')


class EventView(GetEventMixinWithAccessCheck, TemplateView):
    """
    Просмотр статистики загрузок материалов по эвентам
    """
    template_name = 'event_view.html'

    def get_context_data(self, **kwargs):
        users = get_event_participants(self.event)
        check_ins = set(EventEntry.objects.filter(event=self.event, is_active=True).values_list('user_id', flat=True))
        if not self.request.user.is_assistant:
            num = dict(EventMaterial.objects.filter(event=self.event, user__in=users, is_public=True).
                       values_list('user_id').annotate(num=Count('event_id')))
        else:
            num = dict(EventMaterial.objects.filter(event=self.event, user__in=users).
                       values_list('user_id').annotate(num=Count('event_id')))
        for u in users:
            u.materials_num = num.get(u.id, 0)
            u.checked_in = u.id in check_ins
        return {
            'students': users,
            'event': self.event,
            'teams': Team.objects.filter(event=self.event).order_by('name'),
        }


class BaseLoadMaterials(GetEventMixinWithAccessCheck, TemplateView):
    template_name = 'load_materials.html'
    material_model = None

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data.update({
            'traces': self.get_traces_data(),
            'allow_file_upload': getattr(settings, 'ALLOW_FILE_UPLOAD', False),
            'max_size': settings.MAXIMUM_ALLOWED_FILE_SIZE,
            'max_uploads': settings.MAX_PARALLEL_UPLOADS,
            'event': self.event,
            'can_upload': self.can_upload(),
        })
        return data

    def can_upload(self):
        return self.request.user.is_assistant

    def get_traces_data(self):
        traces = self.event.get_traces()
        result = []
        links = defaultdict(list)
        for item in self.get_materials():
            links[item.trace_id].append(item)
        for trace in traces:
            result.append({'trace': trace, 'links': links.get(trace.id, [])})
        return result

    def post(self, request, *args, **kwargs):
        resp = self.check_post_allowed(request)
        if resp is not None:
            return resp
        try:
            trace_id = int(request.POST.get('trace_name'))
        except (ValueError, TypeError):
            return JsonResponse({}, status=400)
        if not trace_id or not trace_id in [i.id for i in self.event.get_traces()]:
            return JsonResponse({}, status=400)
        if 'add_btn' in request.POST:
            return self.add_item(request)
        return self.delete_item(request)

    def check_post_allowed(self, request):
        if not self.event.is_active or not self.can_upload():
            return JsonResponse({}, status=403)

    def delete_item(self, request):
        material_id = request.POST.get('material_id')
        if not material_id or not material_id.isdigit():
            return JsonResponse({}, status=400)
        trace = Trace.objects.filter(id=request.POST['trace_name']).first()
        if not trace:
            return JsonResponse({}, status=400)
        return self._delete_item(trace, material_id)

    def add_item(self, request):
        trace = Trace.objects.filter(id=request.POST['trace_name']).first()
        if not trace:
            return JsonResponse({}, status=400)
        data = self.get_material_fields(trace, request)
        url = request.POST.get('url_field')
        file_ = request.FILES.get('file_field')
        if bool(file_) == bool(url):
            return JsonResponse({}, status=400)
        if url:
            data['url'] = url
        material = self.material_model.objects.create(**data)
        if file_:
            material.file.save(self.make_file_path(file_.name), file_)
        return JsonResponse({'material_id': material.id, 'url': material.get_url(),
                             'name': material.get_name()})

    def get_material_fields(self, trace, request):
        return {}

    def make_file_path(self, fn):
        return fn


class LoadMaterials(BaseLoadMaterials):
    """
    Просмотр/загрузка материалов по эвенту
    """
    material_model = EventMaterial

    def can_upload(self):
        return self.request.user.is_assistant or int(self.kwargs['unti_id']) == self.request.user.unti_id

    def get_materials(self):
        if self.can_upload():
            return EventMaterial.objects.filter(event=self.event, user=self.user)
        return EventMaterial.objects.filter(event=self.event, user=self.user, is_public=True)

    @cached_property
    def user(self):
        return get_object_or_404(User, unti_id=self.kwargs['unti_id'])

    def _delete_item(self, trace, material_id):
        material = EventMaterial.objects.filter(
            event=self.event, user=self.user, trace=trace, id=material_id
        ).first()
        if not material:
            return JsonResponse({}, status=400)
        material.delete()
        return JsonResponse({})

    def add_item(self, request):
        if not EventEntry.objects.filter(event=self.event, user=self.user).exists():
            return JsonResponse({}, status=400)
        return super().add_item(request)

    def get_material_fields(self, trace, request):
        return dict(event=self.event, user=self.user, trace=trace)

    def make_file_path(self, fn):
        return os.path.join(self.event.uid, str(self.user.unti_id), fn)


class LoadTeamMaterials(BaseLoadMaterials):
    """
    Просмотр/загрузка командных материалов по эвенту
    """
    extra_context = {'with_comment_input': True, 'team_upload': True}
    material_model = EventTeamMaterial

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        users = self.team.users.order_by('last_name', 'first_name', 'second_name')
        num = dict(EventMaterial.objects.filter(event=self.event, user__in=users).
                   values_list('user_id').annotate(num=Count('event_id')))
        for u in users:
            u.materials_num = num.get(u.id, 0)
        data.update({'students': users, 'event': self.event, 'team_name': getattr(self.team, 'name', '')})
        return data

    @cached_property
    def team(self):
        return get_object_or_404(Team, id=self.kwargs['team_id'])

    def get_materials(self):
        return EventTeamMaterial.objects.filter(event=self.event, team=self.team)

    def post(self, request, *args, **kwargs):
        # загрузка и удаление файлов доступны только для эвентов, доступных для оцифровки, и по
        # командам, сформированным в данном эвенте
        if not self.event.is_active or not (self.request.user.is_assistant or
                Team.objects.filter(event=self.event, id=self.kwargs['team_id']).exists()):
            return JsonResponse({}, status=403)
        try:
            trace_id = int(request.POST.get('trace_name'))
        except (ValueError, TypeError):
            return JsonResponse({}, status=400)
        if not trace_id or not trace_id in [i.id for i in self.event.get_traces()]:
            return JsonResponse({}, status=400)
        if 'add_btn' in request.POST:
            return self.add_item(request)
        return self.delete_item(request)

    def check_post_allowed(self, request):
        # загрузка и удаление файлов доступны только для эвентов, доступных для оцифровки, и по
        # командам, сформированным в данном эвенте
        if not super().check_post_allowed(request) or not \
                Team.objects.filter(event=self.event, id=self.kwargs['team_id']).exists():
            return JsonResponse({}, status=403)

    def _delete_item(self, trace, material_id):
        material = EventTeamMaterial.objects.filter(
            event=self.event, team=self.team, trace=trace, id=material_id
        ).first()
        if not material:
            return JsonResponse({}, status=400)
        material.delete()
        return JsonResponse({})

    def make_file_path(self, fn):
        return os.path.join(self.event.uid, str(self.team.team_name), fn)

    def get_material_fields(self, trace, request):
        return dict(event=self.event, team=self.team, trace=trace, comment=request.POST.get('comment', ''))


class LoadEventMaterials(BaseLoadMaterials):
    """
    Загрузка материалов мероприятия
    """
    material_model = EventOnlyMaterial
    extra_context = {'with_comment_input': True}

    def get_materials(self):
        return EventOnlyMaterial.objects.filter(event=self.event)

    def _delete_item(self, trace, material_id):
        material = EventOnlyMaterial.objects.filter(
            event=self.event, trace=trace, id=material_id
        ).first()
        if not material:
            return JsonResponse({}, status=400)
        material.delete()
        return JsonResponse({})

    def make_file_path(self, fn):
        return os.path.join(self.event.uid, fn)

    def get_material_fields(self, trace, request):
        return dict(event=self.event, trace=trace, comment=request.POST.get('comment', ''))


class RefreshDataView(View):
    def get(self, request, uid=None):
        if not request.user.is_assistant:
            success = False
        else:
            if uid:
                if not Event.objects.filter(uid=uid).exists():
                    success = False
                else:
                    success = refresh_events_data(force=True, refresh_participants=True, refresh_for_events=[uid])
            else:
                success = refresh_events_data(force=True)
        return JsonResponse({'success': bool(success)})


@method_decorator(login_required, name='dispatch')
class CreateTeamView(GetEventMixin, TemplateView):
    template_name = 'create_team.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_assistant:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        users = self.get_available_users()
        return {'students': users, 'event': self.event}

    def get_available_users(self):
        return get_event_participants(self.event).exclude(
            id__in=Team.objects.filter(event=self.event).values_list('users', flat=True))

    def post(self, request, uid=None):
        form = CreateTeamForm(data=request.POST, event=self.event, users_qs=self.get_available_users())
        if not form.is_valid():
            return JsonResponse({}, status=400)
        form.save()
        return JsonResponse({'redirect': reverse('event-view', kwargs={'uid': self.event.uid})})


class RefreshCheckInView(GetEventMixin, View):
    """
    Обновление чекинов всех пользователей определенного мероприятия из ILE
    или обновление чекина одного пользователя в ILE
    """
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_assistant:
            return super().dispatch(request, *args, **kwargs)
        return HttpResponseForbidden()

    def get(self, request, uid=None):
        if not self.event.ext_id:
            return JsonResponse({'success': False})
        return JsonResponse({'success': bool(update_check_ins_for_event(self.event))})

    def post(self, request, uid=None):
        if not self.event.ext_id:
            return JsonResponse({'success': False})
        user_id = request.POST.get('user_id')
        if not user_id or 'status' not in request.POST:
            return JsonResponse({}, status=400)
        user = User.objects.filter(id=user_id).first()
        if not user or not EventEntry.objects.filter(event=self.event, user=user).exists():
            return JsonResponse({}, status=400)
        status = request.POST['status'] in ['true', '1', True]
        result = set_check_in(self.event, user, status)
        if result:
            EventEntry.objects.filter(event=self.event, user=user).update(is_active=True)
            Attendance.objects.update_or_create(
                event=self.event, user=user,
                defaults={
                    'confirmed_by_user': request.user,
                    'is_confirmed': True,
                    'confirmed_by_system': Attendance.SYSTEM_UPLOADS,
                }
            )
            logging.info('User %s has checked in user %s on event %s' %
                         (request.user.username, user.username, self.event.id))
        return JsonResponse({'success': result})


class AddUserToEvent(GetEventMixin, TemplateView):
    """
    Добавить пользователя на мероприятие вручную
    """
    template_name = 'add_user.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_assistant:
            return super().dispatch(request, *args, **kwargs)
        return HttpResponseForbidden()

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data.update({'event': self.event, 'form': AddUserForm(event=self.event)})
        return data

    def post(self, request, uid=None):
        form = AddUserForm(data=request.POST, event=self.event)
        if form.is_valid():
            user = form.cleaned_data['user']
            success = set_check_in(self.event, user, True)
            EventEntry.objects.update_or_create(
                user=user, event=self.event,
                defaults={'added_by_assistant': True, 'is_active': True, 'check_in_pushed': success}
            )
            Attendance.objects.update_or_create(
                event=self.event, user=user,
                defaults={
                    'confirmed_by_user': request.user,
                    'is_confirmed': True,
                    'confirmed_by_system': Attendance.SYSTEM_UPLOADS,
                }
            )
            logging.info('User %s added user %s to event %s' % (request.user.username, user.username, self.event.id))
            return redirect('event-view', uid=self.event.uid)
        else:
            return render(request, self.template_name, {'event': self.event, 'form': form})


class UserAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        event_id = self.forwarded.get('event_id')
        if not self.request.user.is_authenticated or not self.request.user.is_assistant or not event_id:
            return User.objects.none()
        qs = User.objects.filter(is_assistant=False).exclude(
            id__in=EventEntry.objects.filter(event_id=event_id).values_list('user_id', flat=True)
        ).filter(id__in=UserSocialAuth.objects.all().values_list('user__id', flat=True))
        if self.q:
            if len(self.q.split()) == 1:
                qs = qs.filter(
                    Q(email__icontains=self.q) | Q(username__icontains=self.q) |
                    Q(last_name__icontains=self.q) | Q(first_name__icontains=self.q) |
                    Q(second_name__icontains=self.q)
                )
            else:
                filters = []
                q_parts = self.q.split()
                fields = ['last_name', 'first_name', 'second_name']
                for p_len in range(1, min(len(fields), len(q_parts)) + 1):
                    indexes = filter(lambda c: c[0] == 0, combinations(range(len(q_parts)), p_len))
                    ranges = (zip(idxs, idxs[1:] + (None,)) for idxs in indexes)
                    parts_combs = [[" ".join(q_parts[i:j]) for i, j in r] for r in ranges]
                    for p in permutations(fields, p_len):
                        filters.append(functools.reduce(lambda x, y: x | y,
                                              (Q(**{k: v for k, v in zip(p, parts)}) for parts in parts_combs)))
                qs = qs.filter(functools.reduce(lambda x, y: x | y, filters))
        return qs

    def get_result_label(self, result):
        return '%s (%s)' % (result.get_full_name(), result.email)


class Paginator(PageNumberPagination):
    page_size = 20


class ApiPermission(BasePermission):
    def has_permission(self, request, view):
        if request.method == 'OPTIONS':
            return True
        api_key = getattr(settings, 'API_KEY', '')
        key = request.META.get('HTTP_X_API_KEY')
        if key and api_key and key == api_key:
            return True
        return False


class AttendanceApi(ListAPIView):
    """
    **Описание**

        Получение списка присутствовавших на мероприятии или добавление/обновление объекта присутствия.
        В запросе должен присутствовать хедер X-API-KEY

    **Пример get-запроса**

        GET /api/attendance/

    **Пример ответа**

        * {
            "count": 3, // общее количество объектов
            "next": null, // полный url следующей страницы (если есть)
            "previous": null, // полный url предыдущей страницы (если есть)
            "results": [
                {
                    "unti_id": 125, // id пользователя в UNTI SSO
                    "event_id": 2448, // id мероприятия в LABS
                    "created_on": "2018-07-15T07:14:04+10:00", // дата создания объекта
                    "updated_on": "2018-07-15T07:14:04+10:00", // дата обновления объекта
                    "is_confirmed": true, // присутствие подтверждено
                    "confirmed_by_user": 1, // id пользователя подтвердившего присутствие в UNTI SSO
                    "confirmed_by_system": "uploads", // кем подтверждено uploads или chat_bot
                    "run_id": 1405, // id прогона в LABS
                    "activity_id": 439 // id активити в LABS
                },
                ...
          }

    **Пример post-запроса**

    POST /api/attendance/{
            "is_confirmed": true,
            "user_id": 1,
            "event_id": 1,
        }

    **Параметры post-запроса**

        * is_confirmed: подтверждено или нет, boolean
        * user_id: id пользователя в UNTI SSO, integer
        * event_id: id мероприятия в LABS, integer

    **Пример ответа**

         * код 200, словарь с параметрами объекта как при get-запросе, если запрос прошел успешно
         * код 400, если не хватает параметров в запросе
         * код 403, если не указан хедер X-API-KEY или ключ неверен
         * код 404, если не найден пользователь или мероприятие из запроса

    """

    serializer_class = AttendanceSerializer
    pagination_class = Paginator
    permission_classes = (ApiPermission, )

    def get_queryset(self):
        return Attendance.objects.order_by('id')

    def post(self, request):
        is_confirmed = request.data.get('is_confirmed')
        user_id = request.data.get('user_id')
        event_id = request.data.get('event_id')
        if is_confirmed is None or not user_id or not event_id:
            return Response({'error': 'request should contain is_confirmed, user_id and event_id parameters'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(unti_id=user_id)
        except (User.DoesNotExist, TypeError):
            return Response({'error': 'user does not exist'}, status=status.HTTP_404_NOT_FOUND)
        try:
            event = Event.objects.get(ext_id=event_id)
        except (Event.DoesNotExist, TypeError):
            return Response({'error': 'event does not exist'}, status=status.HTTP_404_NOT_FOUND)
        a = Attendance.objects.update_or_create(
            user=user, event=event,
            defaults={
                'confirmed_by_user': None,
                'confirmed_by_system': Attendance.SYSTEM_CHAT_BOT,
                'is_confirmed': is_confirmed,
            }
        )[0]
        logging.info('AttendanceApi request: %s' % request.data)
        return Response(self.serializer_class(instance=a).data)
