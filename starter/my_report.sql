-- Optimized Task 4 report.
--
-- Strategy:
--   1. Aggregate order-line metrics once.
--   2. Aggregate channel-level match-event metrics once.
--   3. Aggregate tenant-day match-event metrics once.
--   4. Compute repeat-items from distinct tenant/day/item sets.
--   5. Compute nearest-rank p95 latency with window functions.
--
-- This avoids the original per-output-row correlated scans.

WITH

-- ------------------------------------------------------------
-- Base report grain:
-- tenant + plan + channel + day
-- ------------------------------------------------------------

order_metrics AS (
    SELECT
        ol.tenant_id,
        t.plan,
        ol.channel,
        substr(ol.created_at, 1, 10) AS day,
        COUNT(DISTINCT ol.line_id) AS lines_total,
        COUNT(DISTINCT ol.customer_id) AS distinct_customers

    FROM order_line ol
    JOIN tenant t
      ON t.tenant_id = ol.tenant_id

    WHERE substr(ol.created_at, 1, 10) >= '2026-05-01'
      AND substr(ol.created_at, 1, 10) <= '2026-06-30'

    GROUP BY
        ol.tenant_id,
        t.plan,
        ol.channel,
        substr(ol.created_at, 1, 10)
),


-- ------------------------------------------------------------
-- Metrics that depend on channel.
--
-- This replaces:
--   lines_accepted
--   candidates_considered
-- ------------------------------------------------------------

channel_event_metrics AS (
    SELECT
        ol.tenant_id,
        ol.channel,
        substr(ol.created_at, 1, 10) AS day,

        COUNT(
            DISTINCT CASE
                WHEN me.accepted = 1
                THEN me.line_id
            END
        ) AS lines_accepted,

        COUNT(*) AS candidates_considered

    FROM order_line ol
    JOIN match_event me
      ON me.line_id = ol.line_id

    WHERE substr(ol.created_at, 1, 10) >= '2026-05-01'
      AND substr(ol.created_at, 1, 10) <= '2026-06-30'

    GROUP BY
        ol.tenant_id,
        ol.channel,
        substr(ol.created_at, 1, 10)
),


-- ------------------------------------------------------------
-- Metrics whose original contract is tenant + day,
-- independent of channel.
--
-- This replaces:
--   avg_accept_score
--   max_latency_ms
--   avg_latency_ms
--   accepted_disabled
-- ------------------------------------------------------------

day_event_metrics AS (
    SELECT
        me.tenant_id,
        substr(me.created_at, 1, 10) AS day,

        AVG(
            CASE
                WHEN me.accepted = 1
                THEN me.score
            END
        ) AS avg_accept_score,

        MAX(me.latency_ms) AS max_latency_ms,

        AVG(me.latency_ms) AS avg_latency_ms,

        SUM(
            CASE
                WHEN me.accepted = 1
                 AND it.disabled = 1
                THEN 1
                ELSE 0
            END
        ) AS accepted_disabled

    FROM match_event me

    LEFT JOIN item it
      ON it.tenant_id = me.tenant_id
     AND it.item_code = me.item_code

    WHERE substr(me.created_at, 1, 10) >= '2026-05-01'
      AND substr(me.created_at, 1, 10) <= '2026-06-30'

    GROUP BY
        me.tenant_id,
        substr(me.created_at, 1, 10)
),


-- ------------------------------------------------------------
-- Nearest-rank p95 latency.
--
-- rank = ceil(0.95 * N)
--
-- Integer form:
--   ceil(95*N/100) = (95*N + 99) / 100
-- ------------------------------------------------------------

latency_ranked AS (
    SELECT
        me.tenant_id,
        substr(me.created_at, 1, 10) AS day,
        me.latency_ms,

        ROW_NUMBER() OVER (
            PARTITION BY
                me.tenant_id,
                substr(me.created_at, 1, 10)
            ORDER BY me.latency_ms
        ) AS rn,

        COUNT(*) OVER (
            PARTITION BY
                me.tenant_id,
                substr(me.created_at, 1, 10)
        ) AS cnt

    FROM match_event me

    WHERE substr(me.created_at, 1, 10) >= '2026-05-01'
      AND substr(me.created_at, 1, 10) <= '2026-06-30'
),


p95_metrics AS (
    SELECT
        tenant_id,
        day,

        MAX(
            CASE
                WHEN rn = ((cnt * 95 + 99) / 100)
                THEN latency_ms
            END
        ) AS p95_latency_ms

    FROM latency_ranked

    GROUP BY
        tenant_id,
        day
),


-- ------------------------------------------------------------
-- Distinct item presence by tenant/day.
--
-- We include the day immediately before the report window
-- because May 1 needs to check April 30.
-- ------------------------------------------------------------

event_items AS (
    SELECT DISTINCT
        tenant_id,
        substr(created_at, 1, 10) AS day,
        item_code

    FROM match_event

    WHERE substr(created_at, 1, 10) >= '2026-04-30'
      AND substr(created_at, 1, 10) <= '2026-06-30'
),


-- ------------------------------------------------------------
-- Items present on both the current day and previous day.
--
-- This replaces the original nested correlated EXISTS.
-- ------------------------------------------------------------

repeat_metrics AS (
    SELECT
        current.tenant_id,
        current.day,
        COUNT(*) AS repeat_items_prev_day

    FROM event_items current

    JOIN event_items previous
      ON previous.tenant_id = current.tenant_id
     AND previous.item_code = current.item_code
     AND previous.day = date(current.day, '-1 day')

    WHERE current.day >= '2026-05-01'
      AND current.day <= '2026-06-30'

    GROUP BY
        current.tenant_id,
        current.day
)


-- ------------------------------------------------------------
-- Final report
-- ------------------------------------------------------------

SELECT
    om.tenant_id,
    om.plan,
    om.channel,
    om.day,

    om.lines_total,

    COALESCE(
        cem.lines_accepted,
        0
    ) AS lines_accepted,

    COALESCE(
        cem.candidates_considered,
        0
    ) AS candidates_considered,

    dem.avg_accept_score,
    dem.max_latency_ms,
    dem.avg_latency_ms,

    om.distinct_customers,

    COALESCE(
        rm.repeat_items_prev_day,
        0
    ) AS repeat_items_prev_day,

    COALESCE(
        dem.accepted_disabled,
        0
    ) AS accepted_disabled,

    pm.p95_latency_ms

FROM order_metrics om

LEFT JOIN channel_event_metrics cem
  ON cem.tenant_id = om.tenant_id
 AND cem.channel = om.channel
 AND cem.day = om.day

LEFT JOIN day_event_metrics dem
  ON dem.tenant_id = om.tenant_id
 AND dem.day = om.day

LEFT JOIN repeat_metrics rm
  ON rm.tenant_id = om.tenant_id
 AND rm.day = om.day

LEFT JOIN p95_metrics pm
  ON pm.tenant_id = om.tenant_id
 AND pm.day = om.day

ORDER BY
    om.tenant_id,
    om.channel,
    om.day;