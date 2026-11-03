from django import forms
from django.contrib.auth import get_user_model
from .models import Board, Membership, Task

class BoardForm(forms.ModelForm):
    class Meta:
        model = Board
        fields = ['name', 'description']
        labels = {'name': 'Название доски', 'description': 'О чём этот проект'}
        widgets = {'name': forms.TextInput(attrs={'placeholder': 'Например, запуск нового сайта'}), 'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Цель проекта и важные детали'})}

class TaskForm(forms.ModelForm):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput, required=False)

    class Meta:
        model = Task
        fields = ['title', 'description', 'status', 'priority', 'due_date', 'assignee']
        labels = {'title': 'Название задачи', 'description': 'Описание', 'status': 'Статус', 'priority': 'Приоритет', 'due_date': 'Срок', 'assignee': 'Исполнитель'}
        widgets = {'title': forms.TextInput(attrs={'placeholder': 'Что нужно сделать?'}), 'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Что должно получиться и как это проверить'}), 'due_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})}

    def __init__(self, *args, board, user, role, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignee'].queryset = get_user_model().objects.filter(is_active=True, memberships__board=board, memberships__role__in=['manager', 'member']).order_by('username')
        self.fields['assignee'].empty_label = 'Не назначен'
        self.fields['due_date'].input_formats = ['%Y-%m-%d']
        if role != Membership.Role.MANAGER:
            self.fields.pop('assignee')
        if self.instance.pk:
            self.fields['version'].required = True
            self.initial['version'] = self.instance.version

class MoveForm(forms.Form):
    status = forms.ChoiceField(choices=Task.Status.choices)
    version = forms.IntegerField(min_value=1)

class DeleteForm(forms.Form):
    version = forms.IntegerField(min_value=1)
    confirm = forms.BooleanField(required=True)

class MemberForm(forms.Form):
    username = forms.CharField(max_length=150, label='Логин пользователя', widget=forms.TextInput(attrs={'placeholder': 'Точный логин в Потоке', 'autocomplete': 'off'}))
    role = forms.ChoiceField(choices=Membership.Role.choices, initial=Membership.Role.MEMBER, label='Роль на этой доске')

    def clean_username(self):
        username = self.cleaned_data['username']
        try:
            self.member_user = get_user_model().objects.get(username=username, is_active=True)
        except get_user_model().DoesNotExist:
            raise forms.ValidationError('Пользователь не найден. Сначала ему нужно зарегистрироваться.')
        return username
