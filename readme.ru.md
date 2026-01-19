# Velox Orchestrator

Платформа для быстрой оркестрации контейнеров с динамическим проксированием и непрерывным развертыванием без простоев

## Описание

Velox Orchestrator предоставляет простой и эффективный способ управления контейнерными приложениями с автоматическим роутингом трафика и обновлениями без downtime. Система интегрируется с Git-репозиториями для автоматического развертывания при каждом обновлении кода


## 1. Локальный запуск (Development)

### Предварительные требования
* Docker Engine >= 24.0
* Docker Compose

### Запуск системы
1. Перейдите в папку `docker`:
   ```bash
   cd docker
   ```
2. Запустите сервисы:
   ```bash
   docker compose up -d --build

   docker compose up --build
   ```
   *Флаг `--build` важен при первом запуске для сборки актуального образа control-plane.*

3. Проверьте статус API:
   ```bash
   curl http://localhost:8000/api/v1/health
   # Ожидаемый ответ: {"status":"ok"}
   ```

### Запуск примеров (Demo)
В папке `examples` подготовлен скрипт для деплоя тестовых приложений (API + 2 статических сайта).

1. Перейдите в папку `examples`:
   ```bash
   cd ../examples
   ```
2. Запустите скрипт деплоя:
   ```bash
   chmod +x deploy-demo.sh
   ./deploy-demo.sh
   ```
   *Скрипт соберет локальные Docker-образы и отправит конфигурацию (`demo-deploy.yaml` + `demo-compose.yml`) в API.*

3. Проверьте статус деплоя:
   ```bash
   curl http://localhost:8000/api/v1/applications/demo-api | jq
   ```
   Дождитесь статуса `healthy`.

4. Проверьте доступность сервисов (используя routing домен `127.0.0.1.nip.io`):
   ```bash
   # Demo API
   curl http://api.127.0.0.1.nip.io/health
   
   # Site 1
   curl -I http://site1.127.0.0.1.nip.io
   ```

### Работа с примерами

#### Изменение и обновление (Redeploy)
Вы можете изменить исходный код любого примера и обновить его без простоя (Zero-Downtime).

Например, для изменения `site2`:
1. Отредактируйте файл `examples/demo-site2/index.html` (или создайте его).
2. Повторно запустите скрипт деплоя:
   ```bash
   ./deploy-demo.sh
   ```
   Orchestrator автоматически:
   - Соберет новый образ Docker.
   - Запустит новый контейнер.
   - Дождется прохождения Healthcheck.
   - Переключит трафик на новую версию.
   - Остановит старую версию.

#### Остановка сервисов
Для остановки или удаления конкретного сервиса используйте API платформы.

**Остановить сервис (Stop):**
Контейнер будет остановлен, но конфигурация останется в системе.
```bash
# Остановить demo-site2
curl -X POST http://localhost:8000/api/v1/applications/demo-site2/stop
```

**Удалить сервис (Delete):**
Сервис будет полностью удален из системы, включая контейнеры и маршруты.
```bash
# Удалить demo-site2
curl -X DELETE http://localhost:8000/api/v1/applications/demo-site2
```

### Остановка системы
Чтобы остановить все сервисы и удалить контейнеры:
```bash
cd ../docker
docker compose down
```

---

## 2. Запуск на сервере (Production)

### Настройка Git Integration (GitHub/GitLab)

Система поддерживает автоматический деплой при обновлении Git-репозитория.

1. **Подготовка сервера**:
   Выполните шаги из раздела "Запуск системы" на вашем сервере. Убедитесь, что порты `80`, `443` и `8000` открыты.

2. **Подготовка репозитория**:
   В корне вашего Git-репозитория должно быть два файла:
   * `docker-compose.yml` - Описание сервисов (образы, healthchecks).
   * `deploy.yaml` - Настройка роутинга Velox Orchestrator (домены, реплики).

3. **Регистрация репозитория в Velox Orchestrator:
   Выполните запрос к API вашего сервера (например, 1.2.3.4):
   ```bash
   curl -X POST http://1.2.3.4:8000/api/v1/repos \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://github.com/your-user/your-repo.git",
       "branch": "main",
       "provider": "github",
       "config_file": "deploy.yaml"
     }'
   ```
   *В ответе вы получите `webhook_secret`. Сохраните его.*

4. **Настройка Webhook в GitHub**:
   * Перейдите в `Settings` -> `Webhooks` -> `Add webhook`.
   * **Payload URL**: `http://1.2.3.4:8000/api/v1/webhook/github`
   * **Content type**: `application/json`
   * **Secret**: (Ваш секрет из шага 3)
   * **Events**: `Push events`
   * Нажмите `Add webhook`.

Теперь при каждом `git push` в ветку `main`, Velox Orchestrator автоматически выкачает обновления и применит Zero-Downtime деплой.

---

## 3. Требования к файлам конфигурации

### `docker-compose.yml`
```yaml
version: "3.8"
services:
  app:
    image: myregistry/myapp:latest
    environment:
      PORT: "8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 5s
      retries: 5
```

### `deploy.yaml`
```yaml
name: my-project
id: my-project

services:
  app:
    domain: myapp.com
    port: 8000
    replicas: 2
    update_strategy: rolling
```

## 4. Веб-интерфейс (Frontend)

В системе предусмотрен веб-интерфейс для мониторинга и управления.

### Запуск
```bash
cd front
npm install --legacy-peer-deps
npm run dev
```
Откройте [http://localhost:5173](http://localhost:5173) в браузере.

### Доступ
- Логин: `admin`
- Пароль: `admin`

Подробнее см. в [front/README.md](front/README.md).
