# Database Schema — Grocery Receipt Auditor

Source of truth: `backend/app/models/`. This diagram mirrors the ORM models —
update it whenever the models change. Renders as a diagram on GitHub (Mermaid).

```mermaid
erDiagram
    users ||--o{ audit_sessions : "owns"
    audit_sessions ||--o{ basket_items : "photos to truth"
    audit_sessions ||--o{ receipts : "receipts to claims"
    audit_sessions ||--o{ audit_findings : "verdicts"
    audit_sessions ||--o{ audit_events : "trail"

    receipts ||--o{ receipt_items : "lines"
    receipts ||--o{ receipt_discounts : "promo lines"
    receipt_items |o--o{ receipt_discounts : "attached to"

    retailers ||--o{ stores : "has"
    retailers ||--o{ products : "sells"
    retailers ||--o{ promotions : "offers"
    retailers ||--o{ catalogues : "publishes"
    retailers |o--o{ receipts : "identified on"
    stores |o--o{ receipts : "location of"
    stores |o--o{ catalogues : "store-specific"

    catalogues ||--o{ catalogue_sources : "proof"
    catalogues |o--o{ promotions : "contains"

    promotions ||--o{ promotion_products : "products involved"
    promotions ||--o{ promotion_eligibility : "requirements"
    products ||--o{ promotion_products : "in promos"
    products |o--o{ basket_items : "recognized as"
    products |o--o{ audit_findings : "about"

    users {
        uuid id PK
        string email UK
        string password_hash
        string display_name "nullable"
    }
    retailers {
        uuid id PK
        string name
        string slug UK
    }
    stores {
        uuid id PK
        uuid retailer_id FK
        string name
        string city
        string postcode
        string external_ref "retailer's own store id"
    }
    products {
        uuid id PK
        string ean "barcode, indexed, nullable"
        string retailer_sku
        uuid retailer_id FK "nullable"
        string brand
        string name
        string size
        string variant
        bool is_multipack
        int units_per_pack
        jsonb attributes
    }
    catalogues {
        uuid id PK
        uuid retailer_id FK
        uuid store_id FK "null = national"
        date valid_from
        date valid_to
        string version
    }
    catalogue_sources {
        uuid id PK
        uuid catalogue_id FK
        string source_url
        string source_type "pdf|html|image|fixture"
        timestamptz fetched_at
        string raw_ref "storage key"
    }
    promotions {
        uuid id PK
        uuid catalogue_id FK "nullable"
        uuid retailer_id FK
        string promo_type "9 values"
        string title
        date valid_from
        date valid_to
        jsonb store_scope
        jsonb conditions
        jsonb discount_formula
        numeric max_discount
        jsonb combination_rules
        jsonb source_evidence
    }
    promotion_products {
        uuid id PK
        uuid promotion_id FK
        uuid product_id FK
        string role "qualifying|bonus"
    }
    promotion_eligibility {
        uuid id PK
        uuid promotion_id FK
        string requirement_type "loyalty_card|coupon|min_quantity"
        jsonb params
    }
    audit_sessions {
        uuid id PK
        uuid user_id FK
        string status "DRAFT to COMPLETED"
    }
    basket_items {
        uuid id PK
        uuid session_id FK
        uuid product_id FK "nullable - unmatched"
        string label
        string ean
        numeric quantity "kg-aware"
        numeric confidence
        bool user_confirmed
        string image_ref "photo key"
        jsonb recognition_evidence
    }
    receipts {
        uuid id PK
        uuid session_id FK
        uuid retailer_id FK "nullable"
        uuid store_id FK "nullable"
        date purchase_date
        numeric total_amount
        string image_ref
        text raw_ocr_text "kept forever"
        numeric parse_confidence
        bool user_confirmed
    }
    receipt_items {
        uuid id PK
        uuid receipt_id FK
        string description "as printed"
        string ean
        numeric quantity
        numeric unit_price
        numeric total_price
        numeric line_confidence
    }
    receipt_discounts {
        uuid id PK
        uuid receipt_id FK
        uuid receipt_item_id FK "null = receipt-level"
        string description
        numeric amount
        string discount_type
    }
    audit_findings {
        uuid id PK
        uuid session_id FK
        uuid product_id FK "nullable"
        string finding_type
        string status "8 values"
        string product_name
        numeric expected_amount
        numeric actual_amount
        numeric difference
        numeric confidence
        jsonb evidence
        text explanation_fr
        bool is_deferred
    }
    audit_events {
        uuid id PK
        uuid session_id FK
        string event_type
        jsonb payload
        timestamptz created_at
    }
```

## Conventions

- All PKs: `uuid`. Timestamped tables carry `created_at`/`updated_at` (mixin);
  append-only records (`*_items`, `*_discounts`, `catalogue_sources`,
  `promotion_*`, `audit_events`) carry `created_at` only.
- All money: `numeric(10,2)` — never float.
- `||--o{` = one-to-many, `|o--o{` = optional-one to many.
- Nullable FKs mark "not yet identified" (AI extraction) — never fabricate.
- JSONB columns hold irregular domain data (promo rules, evidence); validated
  by the deterministic engines, not the schema.
