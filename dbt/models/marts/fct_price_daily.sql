{{ config(
    materialized='incremental',
    unique_key=['bzn', 'delivery_date'],
    incremental_strategy='merge'
) }}

select
    bzn,
    delivery_date,
    round(avg(price), 2)                                  as base_price,
    round(avg(case when is_peak then price end), 2)       as peak_price,
    round(avg(case when not is_peak then price end), 2)   as offpeak_price,
    min(price)                                            as min_price,
    max(price)                                            as max_price,
    count_if(price < 0)                                   as negative_slots,
    count_if(is_filled)                                   as filled_slots,
    count(*)                                              as slots,
    max(_silver_updated_at)                               as _source_updated_at
from {{ ref('stg_day_ahead_price') }}

{% if is_incremental() %}
where _silver_updated_at > (
    select coalesce(max(_source_updated_at), timestamp'1900-01-01') from {{ this }}
)
{% endif %}

group by bzn, delivery_date