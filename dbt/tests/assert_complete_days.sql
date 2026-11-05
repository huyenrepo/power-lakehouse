select bzn, delivery_date, resolution, count(*) as slots
from {{ source('silver', 'day_ahead_price') }}
group by bzn, delivery_date, resolution
having not (
       (resolution = 'PT15M' and count(*) in (92, 96, 100))
    or (resolution = 'PT60M' and count(*) in (23, 24, 25))
)