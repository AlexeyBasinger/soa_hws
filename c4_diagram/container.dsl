workspace "Marketplace_container" {

  model {
    buyer = person "Покупатель" "Смотрит ленту, ищет товары, оформляет заказы и оплачивает"
    seller = person "Продавец" "Управляет каталогом (товары, цены, остатки), обрабатывает заказы"
    admin = person "Администратор" "Модерация, управление пользователями, контроль за соблюдением правил площадки"

    paymentProvider = softwareSystem "Платежная система" "Платежи, их статусы и тд" {
      tags "External"
    }

    notificationProvider = softwareSystem "Рассылка уведомлений" "email/sms/push отправка сообщений" {
      tags "External"
    }

    deliveryProvider = softwareSystem "Служба доставки" "Доставка заказов покупателям, статусы доставки" {
      tags "External"
    }

    authProvider = softwareSystem "Сервис аутентфикации" "Аутетнитификация пользователей, а также безопасность их данных" {
      tags "External"
    }

    marketplace = softwareSystem "Marketplace" "Наша площадка: каталог, персонализированная лента, заказы, платежи, уведомления." {
      tags "System"

      webApp = container "Web App" "SPA" "Веб-интерфейс для покупателей и продавцов"
      mobileApp = container "Mobile App" "iOS/Android" "Мобильное приложение для покупателей"
      adminApp = container "Admin App" "Web" "Интерфейс для администрирования и модерации"

      backendApi = container "Backend API" "HTTP/JSON" "Единая точка входа для клиентских приложений (каркас). Проверка токенов, маршрутизация запросов по доменам"

      feedService = container "Feed/Recommendation Service" "HTTP/JSON" "Персонализированная выдача ленты: ранжирование, рекомендации, формирование feed (каркас)"
      feedDb = container "Feed DB" "PostgreSQL" "Сигналы/профили рекомендаций/кэш ленты (read-model)" {
        tags "Database"
      }

      catalogService = container "Catalog Service" "HTTP/JSON" "Каталог: товары, категории, цены, атрибуты (каркас)"
      catalogDb = container "Catalog DB" "PostgreSQL" "Данные каталога" {
        tags "Database"
      }

      userService = container "User Service" "HTTP/JSON" "Профили пользователей и роли (каркас)"
      userDb = container "User DB" "PostgreSQL" "Пользователи, роли, профили" {
        tags "Database"
      }

      orderService = container "Order Service" "HTTP/JSON" "Оформление заказов и статусы (каркас)"
      orderDb = container "Order DB" "PostgreSQL" "Заказы, позиции заказа, статусы" {
        tags "Database"
      }

      paymentService = container "Payment Service" "HTTP/JSON" "Инициация платежей и учет статусов (каркас)"
      paymentDb = container "Payment DB" "PostgreSQL" "Платежи и статусы" {
        tags "Database"
      }

      deliveryService = container "Delivery Service" "HTTP/JSON" "Интеграция со службой доставки, статусы доставок (каркас)"
      deliveryDb = container "Delivery DB" "PostgreSQL" "Доставки и статусы" {
        tags "Database"
      }

      notificationService = container "Notification Service" "HTTP/JSON" "Формирование и отправка уведомлений (каркас)"
      notificationDb = container "Notification DB" "PostgreSQL" "Шаблоны/журнал уведомлений" {
        tags "Database"
      }

      eventBus = container "Event Bus" "Kafka/RabbitMQ" "Асинхронные события (для статусов заказов/платежей/доставки/уведомлений/поведения)" {
        tags "Infrastructure"
      }
    }

    buyer -> webApp "Использует" "HTTPS"
    buyer -> mobileApp "Использует" "HTTPS"
    seller -> webApp "Использует" "HTTPS"
    admin -> adminApp "Использует" "HTTPS"

    webApp -> backendApi "Вызывает API" "HTTPS/JSON"
    mobileApp -> backendApi "Вызывает API" "HTTPS/JSON"
    adminApp -> backendApi "Вызывает API" "HTTPS/JSON"

    backendApi -> authProvider "Аутентификация пользователей" "OAuth2/OIDC + JWT"

    backendApi -> feedService "Получает персонализированную ленту" "HTTP/JSON"
    backendApi -> catalogService "Операции каталога" "HTTP/JSON"
    backendApi -> userService "Операции пользователей" "HTTP/JSON"
    backendApi -> orderService "Операции заказов" "HTTP/JSON"
    backendApi -> paymentService "Операции платежей" "HTTP/JSON"
    backendApi -> deliveryService "Операции доставки" "HTTP/JSON"
    backendApi -> notificationService "Операции уведомлений" "HTTP/JSON"

    feedService -> feedDb "Читает/пишет" "SQL"
    feedService -> catalogService "Запрашивает данные товаров для обогащения ленты" "HTTP/JSON"

    catalogService -> catalogDb "Читает/пишет" "SQL"
    userService -> userDb "Читает/пишет" "SQL"
    orderService -> orderDb "Читает/пишет" "SQL"
    paymentService -> paymentDb "Читает/пишет" "SQL"
    deliveryService -> deliveryDb "Читает/пишет" "SQL"
    notificationService -> notificationDb "Читает/пишет" "SQL"

    paymentService -> paymentProvider "Платежи" "API/Webhooks"
    deliveryService -> deliveryProvider "Доставка" "API/Webhooks"
    notificationService -> notificationProvider "Отправка сообщений" "API"

    orderService -> eventBus "Публикует события заказа" "Events"
    paymentService -> eventBus "Публикует события платежей" "Events"
    deliveryService -> eventBus "Публикует события доставки" "Events"
    userService -> eventBus "Публикует события профиля/предпочтений" "Events"

    backendApi -> eventBus "Публикует события поведения (просмотры/клики)" "Events"

    feedService -> eventBus "Подписывается на события поведения/заказов/платежей" "Events"
    notificationService -> eventBus "Подписывается на события заказа/платежа/доставки" "Events"
  }

  views {
    container marketplace "Container" {
      include *
      autolayout lr
      title "Marketplace — Container"
    }

    styles {
      element "Person" {
        shape person
      }
      element "System" {
        background #1168bd
        color #ffffff
      }
      element "External" {
        background #999999
        color #ffffff
      }
      element "Database" {
        shape cylinder
      }
      element "Infrastructure" {
        background #2d7f5e
        color #ffffff
      }
    }
  }
}
