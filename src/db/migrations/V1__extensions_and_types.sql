-- UUID генерация
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Enum статуса (создаём только если его нет)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'product_status') THEN
    CREATE TYPE product_status AS ENUM ('ACTIVE', 'INACTIVE', 'ARCHIVED');
  END IF;
END$$;
