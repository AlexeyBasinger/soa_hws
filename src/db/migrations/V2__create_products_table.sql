CREATE TABLE IF NOT EXISTS products (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        VARCHAR(255) NOT NULL,
  description VARCHAR(4000) NULL,
  price       NUMERIC(18,2) NOT NULL CHECK (price > 0),
  stock       INTEGER NOT NULL CHECK (stock >= 0),
  category    VARCHAR(100) NOT NULL,
  status      product_status NOT NULL,
  seller_id   UUID NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
