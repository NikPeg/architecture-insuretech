from locust import HttpUser, between, task


class WebsiteUser(HttpUser):
    """
    Класс для симуляции пользовательской нагрузки на тестовое приложение.
    Отправляет запросы на главную страницу с интервалом от 1 до 5 секунд.
    """
    wait_time = between(1, 5)
    
    @task
    def index(self):
        """
        Основная задача - отправка GET-запроса на корневой эндпоинт.
        Этот запрос будет учитываться в метрике http_requests_total.
        """
        self.client.get("/")
