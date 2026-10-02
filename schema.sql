-- ==============================================================================
-- Flexnet Japanese Vehicles Database Schema for Supabase
-- Run this in your Supabase SQL Editor: https://supabase.com/dashboard/project/_/sql
-- ==============================================================================

-- 1. Create table for Flexnet vehicles
create table if not exists public.flexnet_vehicles (
    id bigint generated always as identity primary key,
    kanri_code text unique not null,                  -- Internal unique vehicle ID (e.g. 2414469358)
    sku text,                                        -- Stock SKU (e.g. GE1982)
    title text not null,                             -- Vehicle title (e.g. トヨタ ランドクルーザー80 4.5 VXリミテッド 4WD)
    brand text,                                      -- Manufacturer/Brand (e.g. トヨタ)
    model text,                                      -- Model name (e.g. ランドクルーザー80)
    badge_tags text[] default '{}',                  -- Tags: ['NEW', 'Renoca', 'NEW CAR', etc.]
    tagline text,                                    -- Short subtitle / promotional hook
    detail_url text not null,                        -- Direct link to vehicle page
    thumbnail_url text,                              -- Main thumbnail image URL
    
    -- Pricing in JPY (tax included)
    total_price numeric,                             -- 支払総額 (e.g. 4690000)
    vehicle_price numeric,                           -- 車両価格 (e.g. 4498000)
    expenses numeric,                                -- 諸費用 (e.g. 192000)
    
    -- Specifications
    model_year text,                                 -- 年式 (e.g. 1996年(H08年))
    mileage_raw text,                                -- Raw mileage string (e.g. 19.9万km)
    mileage_km integer,                              -- Parsed mileage in kilometers (e.g. 199000)
    displacement_raw text,                           -- Raw displacement (e.g. 4500cc)
    displacement_cc integer,                         -- Parsed displacement in CC (e.g. 4500)
    engine_type text,                                -- エンジン種別 (ガソリン / ディーゼル / etc.)
    drive_system text,                               -- 駆動方式 (4WD / 2WD)
    transmission text,                               -- シフト (4ATフロア / 6AT / etc.)
    model_code text,                                 -- 型式 (e.g. E-FZJ80G)
    body_type text,                                  -- ボディタイプ (クロカン・SUV / バン / etc.)
    color text,                                      -- 車体色 (e.g. ブラウンメタリック)
    interior_color text,                             -- 内装色
    steering text,                                   -- ハンドル (右 / 左)
    seating_capacity text,                           -- 定員 (e.g. 5名)
    doors integer,                                   -- ドア数 (e.g. 5)
    chassis_last_digits text,                        -- 車体末尾番号 (e.g. 922)
    has_supercharger text,                           -- 過給機 (あり / なし)
    sliding_doors text,                              -- スライドドア (両側電動 / 片側電動 / etc.)
    recycle_fee text,                                -- リサイクル料金 (リ済込 / etc.)
    
    -- Condition & History
    repair_history text,                             -- 修復歴 (なし / あり)
    inspection text,                                 -- 車検 (車検整備付 / etc.)
    warranty text,                                   -- 保証内容
    legal_maintenance text,                          -- 法定整備内容
    is_non_smoking boolean default false,            -- 禁煙車 flag
    is_one_owner boolean default false,              -- ワンオーナー flag
    is_unused_car boolean default false,             -- 登録済未使用車 flag
    is_campervan boolean default false,              -- キャンピングカー flag
    service_records text,                            -- 定期点検記録簿 (あり / なし)
    odometer_replaced text,                          -- メーター交換歴
    
    -- Content, Customization & Media
    sales_points text,                               -- Sales points and dealer description
    campaign_info text,                              -- Fair / event campaign perks and discounts
    equipment text[] default '{}',                   -- List of equipped features (ABS, Navi, Sunroof, etc.)
    image_urls text[] default '{}',                  -- High-resolution gallery images (15-30+ URLs)
    image_1 text,                                    -- Primary Photo 1
    image_2 text,                                    -- Photo 2
    image_3 text,                                    -- Photo 3
    image_4 text,                                    -- Photo 4
    image_5 text,                                    -- Photo 5
    
    -- Dealer Store Information
    store_name text,                                 -- Branch name (e.g. ランクルJEEP 横浜町田インター店)
    store_prefecture text,                           -- Location / prefecture (e.g. 神奈川県相模原市)
    store_tel text,                                  -- Store phone number
    store_address text,                              -- Store street address
    store_url text,                                  -- Store page link
    
    -- Inventory State & Tracking
    status text default 'available',                 -- 'available' or 'sold'
    first_seen_at timestamptz default timezone('utc'::text, now()),
    last_scraped_at timestamptz default timezone('utc'::text, now())
);

-- Optional: If table was already created, run these ALTER statements to add the new columns:
alter table public.flexnet_vehicles add column if not exists sliding_doors text;
alter table public.flexnet_vehicles add column if not exists recycle_fee text;
alter table public.flexnet_vehicles add column if not exists is_unused_car boolean default false;
alter table public.flexnet_vehicles add column if not exists is_campervan boolean default false;
alter table public.flexnet_vehicles add column if not exists service_records text;
alter table public.flexnet_vehicles add column if not exists campaign_info text;
alter table public.flexnet_vehicles add column if not exists image_1 text;
alter table public.flexnet_vehicles add column if not exists image_2 text;
alter table public.flexnet_vehicles add column if not exists image_3 text;
alter table public.flexnet_vehicles add column if not exists image_4 text;
alter table public.flexnet_vehicles add column if not exists image_5 text;


-- 2. Indexes for high performance querying
create index if not exists idx_flexnet_vehicles_kanri_code on public.flexnet_vehicles(kanri_code);
create index if not exists idx_flexnet_vehicles_status on public.flexnet_vehicles(status);
create index if not exists idx_flexnet_vehicles_brand_model on public.flexnet_vehicles(brand, model);
create index if not exists idx_flexnet_vehicles_total_price on public.flexnet_vehicles(total_price);
create index if not exists idx_flexnet_vehicles_mileage_km on public.flexnet_vehicles(mileage_km);
create index if not exists idx_flexnet_vehicles_last_scraped_at on public.flexnet_vehicles(last_scraped_at);

-- 3. Row Level Security (RLS) Configuration
-- Enables RLS on the flexnet_vehicles table
alter table public.flexnet_vehicles enable row level security;

-- Drop old policies if any exist
drop policy if exists "Allow public read access" on public.flexnet_vehicles;
drop policy if exists "Allow anon and service role insert" on public.flexnet_vehicles;
drop policy if exists "Allow anon and service role update" on public.flexnet_vehicles;

-- Allow public read access
create policy "Allow public read access"
on public.flexnet_vehicles for select
to public
using (true);

-- Allow scraper (anon key or service role) to insert new vehicles
create policy "Allow anon and service role insert"
on public.flexnet_vehicles for insert
to anon, authenticated, service_role
with check (true);

-- Allow scraper (anon key or service role) to update existing vehicles
create policy "Allow anon and service role update"
on public.flexnet_vehicles for update
to anon, authenticated, service_role
using (true)
with check (true);

-- ==============================================================================
-- 4. Users Table for Authentication & Access Control
-- ==============================================================================
create table if not exists public.users (
    id uuid default gen_random_uuid() primary key,
    username text unique not null,
    password_hash text not null,
    role text default 'admin' not null,
    created_at timestamptz default timezone('utc'::text, now()) not null
);

create index if not exists idx_users_username on public.users(username);

alter table public.users enable row level security;

drop policy if exists "Allow backend service access to users" on public.users;
create policy "Allow backend service access to users"
on public.users for all
to anon, authenticated, service_role
using (true)
with check (true);
