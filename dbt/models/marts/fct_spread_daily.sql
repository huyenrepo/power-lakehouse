with prices as (
    select bzn, delivery_date, delivery_start_utc, price
    from {{ ref('stg_day_ahead_price') }}
)

select
    a.delivery_date,
    a.bzn                                                        as zone_a,
    b.bzn                                                        as zone_b,
    round(avg(a.price - b.price), 2)                             as avg_spread,
    round(avg(abs(a.price - b.price)), 2)                        as avg_abs_spread,
    round(avg(case when abs(a.price - b.price) < 0.01 then 1.0 else 0.0 end), 3)
                                                                 as share_coupled_slots,
    count(*)                                                     as slots
from prices a
join prices b
  on  a.delivery_start_utc = b.delivery_start_utc
  and a.bzn < b.bzn              -- each pair once: (AT, DE-LU), not also (DE-LU, AT)
group by a.delivery_date, a.bzn, b.bzn