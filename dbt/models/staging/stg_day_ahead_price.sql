with source as (
    select * from {{ source('silver', 'day_ahead_price') }}
),

enriched as (
    select
        bzn,
        delivery_date,
        delivery_start_utc,
        delivery_end_utc,
        from_utc_timestamp(delivery_start_utc, 'Europe/Berlin') as delivery_start_local,
        resolution,
        price,
        is_filled,
        _silver_updated_at
    from source
)

select
    *,
    -- EEX peak definition: Mon–Fri, 08:00–20:00 local time
    dayofweek(delivery_start_local) between 2 and 6
      and hour(delivery_start_local) >= 8
      and hour(delivery_start_local) < 20      as is_peak
from enriched