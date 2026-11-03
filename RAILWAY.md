# Подготовка к Railway · 02.11.2026

**Не опубликовано.** Публичного URL Railway нет. Ни аккаунт, ни внешняя загрузка, ни расходы в этой работе не выполнялись. Сначала подготовлен проверяемый локальный продукт. Этот runbook не является разрешением выставить сервис в интернет или собирать реальные клиентские данные.

## Что приготовлено

`Dockerfile`, `.dockerignore`, `railway.toml`, `boot.py`, `requirements.txt`, `.env.example`. Контекст Docker — только эта папка приложения, не штаб целиком. `.state`, `.venv`, секреты и тестовые данные исключены. Startup выполняет check/migrate/collectstatic уже при смонтированном volume, затем запускает Waitress. Demo seed автоматически не выполняется.

## Перед реальной публикацией

1. Подтвердить аккаунт, выбранный проект/тариф и разрешение Михаила на внешнюю загрузку/публикацию. Оплату выполняет человек. Текущие цены в этом runbook не утверждаются.
2. Проверить защиту login/signup от злоупотреблений, лимиты регистраций и нагрузку. В локальном MVP нет проверенного production throttling: **публичный запуск пока блокируется**.
3. Создать persistent volume, смонтированный в `/data`; проверить права непривилегированного пользователя контейнера, backup и реальное восстановление на платформе. Одна реплика. SQLite не размещать в эфемерной файловой системе и не запускать параллельную запись нескольких контейнеров. До проверки stop-before-start и volume semantics не обещать долговечность на Railway.
4. Выпустить новый случайный `DJANGO_SECRET_KEY` длиной от 50 символов. Задать точные `DJANGO_ALLOWED_HOSTS`, HTTPS `DJANGO_CSRF_TRUSTED_ORIGINS`, `TRACKER_STATE_DIR=/data`, `TRACKER_PUBLIC=1`. Не переносить локальный secret.key и demo-access.txt.
5. Проверить реальную proxy topology. Явно задать `TRACKER_TRUSTED_PROXY` только для доверенного прокси. Waitress принимает только `X-Forwarded-Proto`, один proxy hop; wildcard не является безопасным умолчанием. Убедиться, что напрямую к WSGI обойти границу прокси невозможно. Иначе не включать trust и не запускать публично.
6. После независимой проверки конкретного deployment и решения пользователя установить `TRACKER_PUBLIC_RELEASE_APPROVED=1` (это ручной guard, не доказательство безопасности).
7. Собрать контейнер/развернуть, выполнить `check --deploy`, health, регистрацию/вход на собственном синтетическом аккаунте, смену статуса и проверку прав всех ролей по HTTPS. Обязательно проверить отсутствие redirect loop, Secure cookies, сохранение после redeploy, backup/restore. Только после этого фиксировать публичную ссылку.

Облачная сборка и smoke на Railway в текущем результате **NOT RUN**. Не включены публичный self-service, письма восстановления пароля, файлы или реальные рабочие данные команды.

## Первичные источники

- [Railway: Deploy a Django App](https://railway.com/guides/django).
- [Railway: Volumes](https://docs.railway.com/volumes): volume не монтируется во время build/pre-deploy; операции с постоянной БД должны выполняться на правильном этапе.
- [Django 5.2 deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).
- [Waitress reverse proxy configuration](https://docs.pylonsproject.org/projects/waitress/en/stable/reverse-proxy.html).

Проверка официальных Django/Railway материалов: 02.11.2026. Реальная конфигурация аккаунта и инфраструктура Railway неизвестны.
