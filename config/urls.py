from django.urls import path
from boards import views

urlpatterns = [
    path('', views.home, name='home'),
    path('accounts/signup/', views.signup, name='signup'),
    path('accounts/login/', views.TrackerLogin.as_view(), name='login'),
    path('accounts/logout/', views.TrackerLogout.as_view(), name='logout'),
    path('boards/', views.board_list, name='boards'),
    path('boards/new/', views.board_create, name='board_create'),
    path('boards/<int:board_id>/', views.board_detail, name='board'),
    path('boards/<int:board_id>/members/', views.members, name='members'),
    path('boards/<int:board_id>/tasks/new/', views.task_create, name='task_create'),
    path('boards/<int:board_id>/tasks/<int:task_id>/', views.task_detail, name='task'),
    path('boards/<int:board_id>/tasks/<int:task_id>/move/', views.task_move, name='task_move'),
    path('boards/<int:board_id>/tasks/<int:task_id>/delete/', views.task_delete, name='task_delete'),
    path('health/', views.health, name='health'),
]
handler400 = 'boards.views.error400'
handler403 = 'boards.views.error403'
handler404 = 'boards.views.error404'
handler500 = 'boards.views.error500'
