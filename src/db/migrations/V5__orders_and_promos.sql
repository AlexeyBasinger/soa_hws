-- enum для статусов заказа
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'order_status') THEN
    CREATE TYPE order_status AS ENUM ('CREATED','PAYMENT_PENDING','PAID','SHIPPED','COMPLETED','CANCELED');
  END IF;
END$$;

-- enum для типа скидки
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'discount_type') THEN
    CREATE TYPE discount_type AS ENUM ('PERCENTAGE','FIXED_AMOUNT');
  END IF;
END$$;

-- enum для операций пользователя
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'operation_type') THEN
    CREATE TYPE operation_type AS ENUM ('CREATE_ORDER','UPDATE_ORDER');
  END IF;
END$$;

-- seller_id для products (nullable, под п.10)
ALTER TABLE products
  ADD COLUMN IF NOT EXISTS seller_id UUID NULL;

-- promo_codes
CREATE TABLE IF NOT EXISTS promo_codes (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code            VARCHAR(20) NOT NULL UNIQUE,
  discount_type   discount_type NOT NULL,
  discount_value  NUMERIC(12,2) NOT NULL CHECK (discount_value >= 0),
  min_order_amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (min_order_amount >= 0),
  max_uses        INTEGER NOT NULL CHECK (max_uses >= 0),
  current_uses    INTEGER NOT NULL DEFAULT 0 CHECK (current_uses >= 0),
  valid_from      TIMESTAMPTZ NOT NULL,
  valid_until     TIMESTAMPTZ NOT NULL,
  active          BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- orders
CREATE TABLE IF NOT EXISTS orders (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL,
  status          order_status NOT NULL,
  promo_code_id   UUID NULL REFERENCES promo_codes(id),
  total_amount    NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0),
  discount_amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- order_items
CREATE TABLE IF NOT EXISTS order_items (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id       UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id     UUID NOT NULL REFERENCES products(id),
  quantity       INTEGER NOT NULL CHECK (quantity >= 1 AND quantity <= 999),
  price_at_order NUMERIC(12,2) NOT NULL CHECK (price_at_order >= 0)
);

-- user_operations
CREATE TABLE IF NOT EXISTS user_operations (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL,
  operation_type operation_type NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- индексы под проверки
CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status);
CREATE INDEX IF NOT EXISTS idx_user_ops_user_type_created ON user_operations(user_id, operation_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_promo_code_code ON promo_codes(code);
