workspace "Marketplace_context" {

  model {
    buyer = person "Покупатель" "Смотрит ленту, ищет товары, оформляет заказы и оплачивает"
    seller = person "Продавец" "Управляет каталогом (товары, цены, остатки), обрабатывает заказы"
    admin = person "Администратор" "Модерация, управление пользователями, контроль за соблюдением правил площадки"

    marketplace = softwareSystem "Marketplace" "Наша площадка: каталог, персонализированная лента, заказы, платежи, уведомления." {
      tags "System"
    }

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

    buyer -> marketplace "Использует" "веб/моб приложение"
    seller -> marketplace "Использует" "веб"
    admin -> marketplace "Администрирует" "веб"

    marketplace -> paymentProvider "Инициирует платежи/получает статусы"
    marketplace -> notificationProvider "Отправляет уведомления"
    marketplace -> deliveryProvider "Создает доставки/получает статусы"
    marketplace -> authProvider "Аутентификация пользователей"
  }

  views {
    systemContext marketplace "SystemContext" {
      include *
      autolayout lr
      title "Marketplace — System Context"
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
    }
  }
}
