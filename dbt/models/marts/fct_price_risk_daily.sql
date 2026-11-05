with daily as (
    select bzn, delivery_date, base_price
    from {{ ref('fct_price_daily') }}
),

changes as (
    select
        *,
        base_price - lag(base_price) over (partition by bzn order by delivery_date)
            as daily_change
    from daily
)

select
    bzn,
    delivery_date,
    base_price,
    round(daily_change, 2) as daily_change,
    count(daily_change) over w30 as obs_30d,
    case when count(daily_change) over w30 >= 20
         then round(stddev_samp(daily_change) over w30, 2)
    end as volatility_30d
from changes
window w30 as (partition by bzn order by delivery_date
               rows between 29 preceding and current row)