from django.conf import settings
from django.urls import path
from isle import views

urlpatterns = [
    path('', views.Index.as_view(), name='index'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('update-attendance/<str:uid>', views.UpdateAttendanceView.as_view(), name='update-attendance-view'),
    path('create-team/<str:uid>/', views.CreateTeamView.as_view(), name='create-team'),
    path('confirm-team/<str:uid>/', views.ConfirmTeamView.as_view(), name='confirm-team'),
    path('load-team/<str:uid>/<int:team_id>/', views.LoadTeamMaterialsResult.as_view(), name='load-team-materials'),
    path('confirm-team-material/<str:uid>/<int:team_id>/', views.ConfirmTeamMaterial.as_view(),
         name='confirm-team-material'),
    path('load-event/<str:uid>/', views.LoadEventMaterials.as_view(), name='load-event-materials'),
    path('add-user/<str:uid>/', views.AddUserToEvent.as_view(), name='add-user'),
    path('remove-user/<str:uid>/', views.RemoveUserFromEvent.as_view(), name='remove-user'),
    path('is_public/<str:uid>/', views.IsMaterialPublic.as_view(), name='is-material-public'),
    path('autocomplete/user/', views.UserAutocomplete.as_view(), name='user-autocomplete'),
    path('autocomplete/result-type/', views.ResultTypeAutocomplete.as_view(), name='result-type-autocomplete'),
    path('autocomplete/event-user/', views.EventUserAutocomplete.as_view(), name='event-user-autocomplete'),
    path('autocomplete/event-team/', views.EventTeamAutocomplete.as_view(), name='event-team-autocomplete'),
    path('api/attendance/', views.AttendanceApi.as_view()),
    path('api/user-chart/', views.UserChartApiView.as_view()),
    path('owner/team-material/<str:uid>/<int:team_id>/<int:material_id>/', views.TeamMaterialOwnership.as_view(),
         name='team-material-owner'),
    path('owner/event-material/<str:uid>/<int:material_id>/', views.EventMaterialOwnership.as_view(),
         name='event-material-owner'),
    path('transfer-material/<str:uid>/', views.TransferView.as_view(), name='transfer'),
    path('statistics/', views.Statistics.as_view()),
    path('approve-text-edit/<str:event_entry_id>/', views.ApproveTextEdit.as_view(), name='approve-text-edit'),
    path('activities/', views.ActivitiesView.as_view(), name='activities'),
    path('add-event-block/<str:uid>/', views.AddEventBlockToMaterial.as_view(), name='add-event-block'),
    path('event-block-edit/<str:uid>/', views.EventBlockEditRenderer.as_view(), name='event-block-edit-renderer'),
    path('role-formset-render/<str:uid>/<int:team_id>/', views.RolesFormsetRender.as_view(), name='roles-formset-render'),
    path('get_event_csv/<str:uid>/', views.EventCsvData.as_view(), name='get_event_csv'),
    path('switch-context/', views.switch_context, name='switch_context'),
    path('<str:uid>/', views.EventView.as_view(), name='event-view'),
    path('<str:uid>/<int:unti_id>/', views.LoadUserMaterialsResult.as_view(), name='load-materials'),
    path('api/user-materials/', views.UserMaterialsListView.as_view()),
    path('api/user-result-info/', views.UserResultInfoView.as_view()),
    path('api/team-result-info/', views.TeamResultInfoView.as_view()),
    path('api/get-dp-data/', views.GetDpData.as_view()),
    path('<str:uid>/<int:unti_id>/<str:result_type>/<int:result_id>', views.ResultPage.as_view(), name='result-page'),
]

if settings.DEBUG:
    from django.conf.urls import url
    from django.views.static import serve
    urlpatterns += [
        url(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        })]
