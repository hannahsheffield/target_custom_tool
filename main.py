import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google.cloud import bigquery
import math

# ---- CONFIG ----
PROJECT = "king-perfmarketing-sandbox"
TABLE = "king-datacommons-prod.campaign_roi.f_roi_daily"

MATURITY_OFFSETS = {
    "18m": -21,
    "15m": -18,
    "12m": -15,
    "9m": -12,
    "6m": -9,
    "3m": -6,
    "1m": -4,
}

MATURITY_FINAL_DAYS = {
    "18m": 545,
    "15m": 454,
    "12m": 364,
    "9m": 271,
    "6m": 179,
    "3m": 89,
    "1m": 29,
}

CHECKPOINTS_BY_MATURITY = {
    "18m": [4, 7, 14, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360, 390, 420, 450, 480, 510, 540],
    "15m": [4, 7, 14, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360, 390, 420, 450],
    "12m": [4, 7, 14, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360],
    "9m": [4, 7, 14, 30, 60, 90, 120, 150, 180, 210, 240, 270],
    "6m": [4, 7, 14, 30, 60, 90, 120, 150, 180],
    "3m": [4, 7, 14, 30, 60, 90],
    "1m": [4, 7, 14, 30],
}

DEVICE_GROUP_SQL = """
CASE
    WHEN f.device_class IN ('iPhone', 'iPad', 'iOS', 'iOS Unknown Type')
    THEN 'iOS'
    ELSE f.device_class
END
"""

BASE_JOINS = """
LEFT JOIN `king-datacommons-prod.campaign_roi.d_dm_kingapp` AS k
    ON f.kingappid = k.kingappid
LEFT JOIN `king-dm-roi-prod.staging_persistent.map_dm_channel360` AS m
    ON f.channel_name = m.channel_name
    AND (
        (m.android = 'croi' AND f.client_implementation_id = 2)
        OR (m.ios = 'croi' AND f.client_implementation_id = 1)
        OR (m.windows = 'croi' AND f.client_implementation_id IN (14, 15))
        OR (m.other = 'croi' AND f.client_implementation_id NOT IN (1, 2, 14, 15))
    )
    AND f.install_date BETWEEN DATE(m.valid_from_date) AND DATE(m.valid_to_date)
"""

# ---- PAGE ----
st.set_page_config(
    page_title="Custom Target Tool",
    layout="wide",
    page_icon="📊"
)

st.title("📊 Custom Target Tool")

# ---- BQ CLIENT ----
try:
    client = bigquery.Client(project=PROJECT)
    st.success("Connected to BigQuery")
except Exception as e:
    st.error(f"Connection failed: {e}")
    client = None


# ---- CACHE ----
@st.cache_data(ttl=300)
def load_filter_options(query, _job_config):
    return client.query(query, job_config=_job_config).to_dataframe()


def excel_style_pct(x):
    if pd.isna(x):
        return "-"

    pct = math.floor(float(x) * 10000) / 100
    return f"{pct:.2f}%"


def load_main_data(client, maturity, title, acquisition_type, channel, campaign_category, device_group):
    query = f"""
    SELECT
        COUNT(DISTINCT FORMAT_DATE('%Y-%m', f.install_date)) AS months,

        COALESCE(SUM(f.cost_usd), 0) AS total_cost,

        COALESCE(SUM(
            CASE
                WHEN f.activity_date = f.install_date
                THEN COALESCE(f.gross_booking_usd, 0) * COALESCE(f.net_revenue_adjustment, 1)
                ELSE 0
            END
        ), 0) AS net_revenue,

        COALESCE(SUM(
            CASE
                WHEN f.activity_date = f.install_date
                THEN COALESCE(f.ad_est_net_revenue_usd, 0)
                ELSE 0
            END
        ), 0) AS ad_net_revenue,

        COALESCE(SUM(
            CASE
                WHEN f.activity_date = f.install_date
                THEN
                    COALESCE(f.num_first_install * COALESCE(f.incrementality_factor_install, 1.2), 0)
                  + COALESCE(f.num_reinstall * COALESCE(f.incrementality_factor_install, 1.2), 0)
                  + COALESCE(f.num_reopen * COALESCE(f.incrementality_factor_install, 1.2), 0)
                ELSE 0
            END
        ), 0) AS valid_attributions

    FROM `{TABLE}` AS f
    {BASE_JOINS}

    WHERE f.install_date >= DATE_ADD(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL @maturity_offset MONTH)
      AND f.install_date < DATE_ADD(
          DATE_ADD(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL @maturity_offset MONTH),
          INTERVAL 3 MONTH
      )
      AND f.acquisition_category = 'Paid'
      AND k.title_reporting_name IN ('CCS', 'CCSS', 'FHS')
      AND m.channel_name IS NOT NULL
      AND (@title = '(All)' OR k.title_reporting_name = @title)
      AND (@acquisition_type = '(All)' OR f.campaign_acquisition_type = @acquisition_type)
      AND (@channel = '(All)' OR f.channel_name = @channel)
      AND (@campaign_category = '(All)' OR f.campaign_category = @campaign_category)
      AND (
          @device_group = '(All)'
          OR {DEVICE_GROUP_SQL} = @device_group
      )
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("maturity_offset", "INT64", MATURITY_OFFSETS[maturity]),
            bigquery.ScalarQueryParameter("title", "STRING", title),
            bigquery.ScalarQueryParameter("acquisition_type", "STRING", acquisition_type),
            bigquery.ScalarQueryParameter("channel", "STRING", channel),
            bigquery.ScalarQueryParameter("campaign_category", "STRING", campaign_category),
            bigquery.ScalarQueryParameter("device_group", "STRING", device_group),
        ]
    )

    return client.query(query, job_config=job_config).to_dataframe()


def load_daily_test_data(client, maturity, title, acquisition_type, channel, campaign_category, device_group):
    query = f"""
    SELECT
        DATE_DIFF(f.activity_date, f.install_date, DAY) AS day,

        COALESCE(SUM(f.cost_usd), 0) AS cost,

        COALESCE(SUM(
            COALESCE(f.gross_booking_usd, 0)
            * COALESCE(f.net_revenue_adjustment, 1)
        ), 0) AS net_revenue,

        COALESCE(SUM(
            COALESCE(f.ad_est_net_revenue_usd, 0)
        ), 0) AS ad_revenue,

        COALESCE(SUM(
            CASE
                WHEN f.activity_date = f.install_date
                THEN
                    COALESCE(f.num_first_install * COALESCE(f.incrementality_factor_install, 1.2), 0)
                  + COALESCE(f.num_reinstall * COALESCE(f.incrementality_factor_install, 1.2), 0)
                  + COALESCE(f.num_reopen * COALESCE(f.incrementality_factor_install, 1.2), 0)
                ELSE 0
            END
        ), 0) AS valid_attributions

    FROM `{TABLE}` AS f
    {BASE_JOINS}

    WHERE f.install_date >= DATE_ADD(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL @maturity_offset MONTH)
      AND f.install_date < DATE_ADD(
          DATE_ADD(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL @maturity_offset MONTH),
          INTERVAL 3 MONTH
      )
      AND DATE_DIFF(f.activity_date, f.install_date, DAY) BETWEEN 0 AND @final_day
      AND f.acquisition_category = 'Paid'
      AND k.title_reporting_name IN ('CCS', 'CCSS', 'FHS')
      AND m.channel_name IS NOT NULL
      AND (@title = '(All)' OR k.title_reporting_name = @title)
      AND (@acquisition_type = '(All)' OR f.campaign_acquisition_type = @acquisition_type)
      AND (@channel = '(All)' OR f.channel_name = @channel)
      AND (@campaign_category = '(All)' OR f.campaign_category = @campaign_category)
      AND (
          @device_group = '(All)'
          OR {DEVICE_GROUP_SQL} = @device_group
      )

    GROUP BY 1
    ORDER BY 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("maturity_offset", "INT64", MATURITY_OFFSETS[maturity]),
            bigquery.ScalarQueryParameter("final_day", "INT64", MATURITY_FINAL_DAYS[maturity]),
            bigquery.ScalarQueryParameter("title", "STRING", title),
            bigquery.ScalarQueryParameter("acquisition_type", "STRING", acquisition_type),
            bigquery.ScalarQueryParameter("channel", "STRING", channel),
            bigquery.ScalarQueryParameter("campaign_category", "STRING", campaign_category),
            bigquery.ScalarQueryParameter("device_group", "STRING", device_group),
        ]
    )

    return client.query(query, job_config=job_config).to_dataframe()


def load_current_curve_data(client, maturity, title, acquisition_type, channel, campaign_category, device_group):
    checkpoints = CHECKPOINTS_BY_MATURITY[maturity]

    maturity_prefix = {
        "1m": "9m",
        "3m": "9m",
        "6m": "9m",
        "9m": "9m",
        "12m": "12m",
        "15m": "15m",
        "18m": "18m",
    }[maturity]

    fields = []

    for d in checkpoints:
        age_check = d - 1

        fields.append(f"""
        SUM(
            CASE
                WHEN DATE_DIFF(DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY), f.install_date, DAY) >= {age_check}
                THEN (
                    (
                        CASE
                            WHEN DATE_DIFF(f.activity_date, f.install_date, DAY) < {d}
                            THEN COALESCE(f.gross_booking_usd, 0)
                            ELSE 0
                        END
                        * COALESCE(f.net_revenue_adjustment, 1)
                        * (
                            COALESCE(f.x_ltv_factor, 0)
                            * COALESCE(f.x_attr_factor, 0)
                            * COALESCE(f.incrementality_factor_revenue, 0)
                            + COALESCE(f.facebook_vta_factor, 0)
                        )
                    )
                    +
                    (
                        CASE
                            WHEN DATE_DIFF(f.activity_date, f.install_date, DAY) < {d}
                            THEN COALESCE(f.ad_est_net_revenue_usd, 0)
                            ELSE 0
                        END
                        * (
                            COALESCE(f.x_ltv_factor, 0)
                            * COALESCE(f.x_attr_factor, 0)
                            * COALESCE(f.incrementality_factor_revenue, 0)
                            + COALESCE(f.facebook_vta_factor, 0)
                        )
                    )
                )
                / NULLIF(f.rpi_shape_{maturity_prefix}.pct_{d}d, 0)
                ELSE 0
            END
        ) AS boosted_pred_rev_{d}d,

        SUM(
            CASE
                WHEN DATE_DIFF(DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY), f.install_date, DAY) >= {age_check}
                THEN COALESCE(f.cost_usd, 0)
                ELSE 0
            END
        ) AS cost_{d}d
        """)

    query = f"""
    SELECT
        {",".join(fields)}
    FROM `{TABLE}` AS f
    {BASE_JOINS}
    WHERE f.install_date >= DATE_ADD(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL @maturity_offset MONTH)
      AND f.install_date < DATE_ADD(
          DATE_ADD(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL @maturity_offset MONTH),
          INTERVAL 3 MONTH
      )
      AND f.acquisition_category = 'Paid'
      AND k.title_reporting_name IN ('CCS', 'CCSS', 'FHS')
      AND m.channel_name IS NOT NULL
      AND (@title = '(All)' OR k.title_reporting_name = @title)
      AND (@acquisition_type = '(All)' OR f.campaign_acquisition_type = @acquisition_type)
      AND (@channel = '(All)' OR f.channel_name = @channel)
      AND (@campaign_category = '(All)' OR f.campaign_category = @campaign_category)
      AND (
          @device_group = '(All)'
          OR {DEVICE_GROUP_SQL} = @device_group
      )
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("maturity_offset", "INT64", MATURITY_OFFSETS[maturity]),
            bigquery.ScalarQueryParameter("title", "STRING", title),
            bigquery.ScalarQueryParameter("acquisition_type", "STRING", acquisition_type),
            bigquery.ScalarQueryParameter("channel", "STRING", channel),
            bigquery.ScalarQueryParameter("campaign_category", "STRING", campaign_category),
            bigquery.ScalarQueryParameter("device_group", "STRING", device_group),
        ]
    )

    raw_df = client.query(query, job_config=job_config).to_dataframe()

    rows = []

    if not raw_df.empty:
        row = raw_df.iloc[0]

        for d in checkpoints:
            rev = row[f"boosted_pred_rev_{d}d"]
            cost = row[f"cost_{d}d"]
            current = rev / cost if pd.notna(cost) and cost != 0 else None

            rows.append({
                "day": d,
                "current_curve": current,
            })

    return pd.DataFrame(rows)


def get_curve_value(curve, day):
    if day in curve.index:
        return curve.loc[day]

    available_days = curve.index[curve.index <= day]

    if len(available_days) == 0:
        return None

    return curve.loc[available_days.max()]


def build_maturity_curve(df, final_day):
    df = df.copy()
    df["total_revenue"] = df["net_revenue"] + df["ad_revenue"]

    # Match Excel display/input precision
    df["total_revenue"] = df["total_revenue"].astype(float).round(0)

    day0_attr = df.loc[df["day"] == 0, "valid_attributions"]

    if day0_attr.empty or day0_attr.iloc[0] <= 0:
        return None

    day0_attr = float(day0_attr.iloc[0])

    df["daily_rpi"] = df["total_revenue"] / day0_attr
    df["cumulative_rpi"] = df["daily_rpi"].cumsum()

    final_row = df.loc[df["day"] == final_day, "cumulative_rpi"]

    if final_row.empty or final_row.iloc[0] <= 0:
        return None

    final_cum_rpi = final_row.iloc[0]

    df["curve"] = df["cumulative_rpi"] / final_cum_rpi

    return df.set_index("day")["curve"]


def build_final_pct_curves(maturity_curves):
    final_pct = {}

    final_pct["18m"] = maturity_curves["18m"]

    final_pct["15m"] = (
        maturity_curves["15m"]
        * get_curve_value(final_pct["18m"], 454)
    )

    final_pct["12m"] = (
        maturity_curves["12m"]
        * get_curve_value(final_pct["15m"], 364)
    )

    final_pct["9m"] = (
        maturity_curves["9m"]
        * get_curve_value(final_pct["12m"], 271)
    )

    final_pct["6m"] = (
        maturity_curves["6m"]
        * get_curve_value(final_pct["9m"], 179)
    )

    final_pct["3m"] = (
        maturity_curves["3m"]
        * get_curve_value(final_pct["6m"], 89)
    )

    three_m_day_29_chained = get_curve_value(final_pct["3m"], 29)
    one_m_day_29_raw = get_curve_value(maturity_curves["1m"], 29)

    final_pct["1m"] = (
        maturity_curves["1m"]
        * three_m_day_29_chained
        / one_m_day_29_raw
        )

    return final_pct


def calculate_new_curve(final_pct, final_pct_4d, day, day0_adj_pct):
    final_pct = float(final_pct)
    final_pct_4d = float(final_pct_4d)
    adj = float(day0_adj_pct) / 100

    if adj == 0:
        return final_pct

    adjusted_4d = final_pct_4d * (1 + adj)

    if day <= 3:
        return final_pct * (1 + adj)

    return adjusted_4d + (
        (final_pct - final_pct_4d)
        * ((1 - adjusted_4d) / (1 - final_pct_4d))
    )


def get_correct_final_pct(day, final_pct_curves):
    if day <= 29:
        return get_curve_value(final_pct_curves["1m"], day)
    elif day <= 89:
        return get_curve_value(final_pct_curves["3m"], day)
    elif day <= 179:
        return get_curve_value(final_pct_curves["6m"], day)
    elif day <= 271:
        return get_curve_value(final_pct_curves["9m"], day)
    elif day <= 364:
        return get_curve_value(final_pct_curves["12m"], day)
    elif day <= 454:
        return get_curve_value(final_pct_curves["15m"], day)
    else:
        return get_curve_value(final_pct_curves["18m"], day)


# ---- SIDEBAR ----
with st.sidebar:
    st.header("Controls")

    maturity = st.selectbox(
        "Maturity Window",
        ["1m", "3m", "6m", "9m", "12m", "15m", "18m"],
        key="maturity"
    )

    title = st.selectbox(
        "Title",
        ["(All)", "CCS", "CCSS", "FHS"],
        key="title"
    )

    try:
        options_query = f"""
        SELECT DISTINCT
            f.campaign_acquisition_type,
            f.channel_name,
            f.campaign_category,
            {DEVICE_GROUP_SQL} AS device_group
        FROM `{TABLE}` AS f
        {BASE_JOINS}
        WHERE f.install_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
          AND f.acquisition_category = 'Paid'
          AND k.title_reporting_name IN ('CCS', 'CCSS', 'FHS')
          AND (@title = '(All)' OR k.title_reporting_name = @title)
        LIMIT 1000
        """

        options_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("title", "STRING", title),
            ]
        )

        options_df = load_filter_options(options_query, options_config)

    except Exception as e:
        st.error(f"Could not load filter options: {e}")
        options_df = pd.DataFrame(
            columns=[
                "campaign_acquisition_type",
                "channel_name",
                "campaign_category",
                "device_group",
            ]
        )

    if options_df.empty:
        st.warning("No filter options loaded yet")

    acquisition_type = st.selectbox(
        "Campaign Acquisition Type",
        ["(All)"] + sorted(options_df["campaign_acquisition_type"].dropna().unique()),
        key="acquisition_type"
    )

    filtered_options = options_df.copy()

    if acquisition_type != "(All)":
        filtered_options = filtered_options[
            filtered_options["campaign_acquisition_type"] == acquisition_type
        ]

    channel = st.selectbox(
        "Channel",
        ["(All)"] + sorted(filtered_options["channel_name"].dropna().unique()),
        key="channel"
    )

    if channel != "(All)":
        filtered_options = filtered_options[
            filtered_options["channel_name"] == channel
        ]

    campaign_category = st.selectbox(
        "Campaign Category",
        ["(All)"] + sorted(filtered_options["campaign_category"].dropna().unique()),
        key="campaign_category"
    )

    if campaign_category != "(All)":
        filtered_options = filtered_options[
            filtered_options["campaign_category"] == campaign_category
        ]

    device_group = st.selectbox(
        "Device Group",
        ["(All)"] + sorted(filtered_options["device_group"].dropna().unique()),
        key="device_group"
    )

    day0_adj = st.number_input(
        "Day 0 Target Adjustment (%)",
        min_value=-100.0,
        max_value=100.0,
        value=0.0,
        step=0.1,
        key="day0_adj"
    )


# ---- TABS ----
data_tab, results_tab = st.tabs(["Data", "Results"])

with data_tab:
    st.subheader("Current Selection")
    st.write("Maturity Window:", maturity)
    st.write("Title:", title)
    st.write("Campaign Acquisition Type:", acquisition_type)
    st.write("Channel:", channel)
    st.write("Campaign Category:", campaign_category)
    st.write("Device Group:", device_group)
    st.write("Day 0 Target Adjustment:", day0_adj)

    st.subheader("Summary")

    try:
        df = load_main_data(
            client,
            maturity,
            title,
            acquisition_type,
            channel,
            campaign_category,
            device_group
        )

        if df.empty:
            st.info("No data found.")
        else:
            row = df.iloc[0]

            valid_attributions = row["valid_attributions"]
            total_cost = row["total_cost"]
            net_revenue = row["net_revenue"]
            ad_net_revenue = row["ad_net_revenue"]
            total_revenue = net_revenue + ad_net_revenue
            rpi = total_revenue / valid_attributions if valid_attributions else 0

            c1, c2, c3, c4, c5, c6 = st.columns(6)

            c1.metric("Valid Attr.", f"{valid_attributions:,.0f}")
            c2.metric("Cost", f"${total_cost:,.0f}")
            c3.metric("Net Revenue", f"${net_revenue:,.0f}")
            c4.metric("Ad Revenue", f"${ad_net_revenue:,.0f}")
            c5.metric("Total Revenue", f"${total_revenue:,.0f}")
            c6.metric("RPI", f"{rpi:.4f}")

            st.dataframe(df)

    except Exception as e:
        st.error(f"Summary failed: {e}")

    st.subheader("Daily Test Data")

    try:
        daily_df = load_daily_test_data(
            client,
            maturity,
            title,
            acquisition_type,
            channel,
            campaign_category,
            device_group
        )

        if daily_df.empty:
            st.info("No daily data.")
        else:
            st.dataframe(daily_df)

            daily_df = daily_df.copy()
            daily_df["total_revenue"] = daily_df["net_revenue"] + daily_df["ad_revenue"]

            day0_attr = daily_df.loc[daily_df["day"] == 0, "valid_attributions"]

            if not day0_attr.empty and day0_attr.iloc[0] > 0:
                day0_attr = day0_attr.iloc[0]

                daily_df["daily_rpi"] = daily_df["total_revenue"] / day0_attr
                daily_df["cumulative_rpi"] = daily_df["daily_rpi"].cumsum()

                st.subheader("Cumulative RPI Check")
                st.dataframe(daily_df[["day", "daily_rpi", "cumulative_rpi"]])
            else:
                st.warning("No valid day 0 attributions")

    except Exception as e:
        st.error(f"Daily test failed: {e}")


with results_tab:
    st.subheader("Current vs New Curve")

    try:
        maturity_windows = ["18m", "15m", "12m", "9m", "6m", "3m", "1m"]
        maturity_curves = {}

        for m in maturity_windows:
            temp_df = load_daily_test_data(
                client,
                m,
                title,
                acquisition_type,
                channel,
                campaign_category,
                device_group
            )

            curve = build_maturity_curve(
                temp_df,
                MATURITY_FINAL_DAYS[m]
            )

            if curve is not None:
                maturity_curves[m] = curve

        if len(maturity_curves) != len(maturity_windows):
            st.warning("Could not build all maturity curves.")

        else:
            final_pct_curves = build_final_pct_curves(maturity_curves)
 

            # ---- DEBUG: ALL MATURITY RPIs ----
            debug_days = list(range(0, MATURITY_FINAL_DAYS["18m"] + 1))
            debug_df = pd.DataFrame({"day": debug_days})

            debug_df["18m"] = debug_df["day"].apply(
                lambda d: get_curve_value(maturity_curves["18m"], d)
            )
            debug_df["15m"] = debug_df["day"].apply(
                lambda d: get_curve_value(maturity_curves["15m"], d)
            )
            debug_df["15m_chained"] = debug_df["day"].apply(
                lambda d: get_curve_value(final_pct_curves["15m"], d)
            )
            debug_df["12m"] = debug_df["day"].apply(
                lambda d: get_curve_value(maturity_curves["12m"], d)
            )
            debug_df["12m_chained"] = debug_df["day"].apply(
                lambda d: get_curve_value(final_pct_curves["12m"], d)
            )
            debug_df["9m"] = debug_df["day"].apply(
                lambda d: get_curve_value(maturity_curves["9m"], d)
            )
            debug_df["9m_chained"] = debug_df["day"].apply(
                lambda d: get_curve_value(final_pct_curves["9m"], d)
            )
            debug_df["6m"] = debug_df["day"].apply(
                lambda d: get_curve_value(maturity_curves["6m"], d)
            )
            debug_df["6m_chained"] = debug_df["day"].apply(
                lambda d: get_curve_value(final_pct_curves["6m"], d)
            )
            debug_df["3m"] = debug_df["day"].apply(
                lambda d: get_curve_value(maturity_curves["3m"], d)
            )
            debug_df["3m_chained"] = debug_df["day"].apply(
                lambda d: get_curve_value(final_pct_curves["3m"], d)
            )
            debug_df["1m"] = debug_df["day"].apply(
                lambda d: get_curve_value(maturity_curves["1m"], d)
            )
            debug_df["final_pct"] = debug_df["day"].apply(
                lambda d: get_correct_final_pct(d, final_pct_curves)
            )

            display_debug_df = debug_df.copy()

            st.subheader("Debug: Raw 1m / 3m handoff")

            st.write("1m raw @ day 29:", get_curve_value(maturity_curves["1m"], 29))
            st.write("3m chained @ day 29:", get_curve_value(final_pct_curves["3m"], 29))
            st.write("1m final @ day 29:", get_curve_value(final_pct_curves["1m"], 29))

            for col in display_debug_df.columns:
                if col != "day":
                    display_debug_df[col] = display_debug_df[col].apply(excel_style_pct)

            st.subheader("Debug: All Maturity RPIs")
            st.dataframe(display_debug_df, hide_index=True)

            # ---- FULL EXCEL-STYLE RESULTS TABLE ----
            full_results_df = pd.DataFrame({
                "day": list(range(0, MATURITY_FINAL_DAYS["18m"] + 1))
            })

            full_results_df["final_pct"] = full_results_df["day"].apply(
                lambda d: get_correct_final_pct(d, final_pct_curves)
            )

            base_day4 = full_results_df.loc[
                full_results_df["day"] == 3,
                "final_pct"
            ].iloc[0]

            full_results_df["New"] = full_results_df.apply(
                lambda row: calculate_new_curve(
                    row["final_pct"],
                    base_day4,
                    row["day"],
                    day0_adj
                ),
                axis=1
            )

            full_results_df["label_day"] = full_results_df["day"] + 1
            full_results_df["Day"] = full_results_df["label_day"].apply(
                lambda d: f"{int(d)}D"
            )

            st.subheader("Debug: New equals Final RPI check")

            parity_debug_df = full_results_df[
                full_results_df["label_day"].isin([4, 7, 14, 30, 60, 90])
            ][["day", "label_day", "final_pct", "New"]].copy()

            parity_debug_df["difference"] = (
                parity_debug_df["New"].astype(float)
                - parity_debug_df["final_pct"].astype(float)
            )

            st.dataframe(parity_debug_df, hide_index=True)

            results_debug_df = full_results_df.copy()

            results_debug_df["Day Label"] = results_debug_df["label_day"].apply(
                lambda d: f"{int(d)}D"
                if d in CHECKPOINTS_BY_MATURITY["18m"]
                else None
            )

            display_results_debug_df = results_debug_df[
                ["day", "final_pct", "New", "Day Label"]
            ].copy()

            display_results_debug_df["final_pct"] = display_results_debug_df["final_pct"].apply(excel_style_pct)
            display_results_debug_df["New"] = display_results_debug_df["New"].apply(excel_style_pct)

            st.subheader("Debug: Results A-C + New")
            st.dataframe(display_results_debug_df, hide_index=True)

            checkpoints = CHECKPOINTS_BY_MATURITY[maturity]

            result_df = full_results_df[
                full_results_df["label_day"].isin(checkpoints)
            ].copy()

            current_df = load_current_curve_data(
                client,
                maturity,
                title,
                acquisition_type,
                channel,
                campaign_category,
                device_group
            )

            result_df = result_df.merge(
                current_df,
                left_on="label_day",
                right_on="day",
                how="left",
                suffixes=("", "_current")
            )

            result_df["Current"] = result_df["current_curve"]

            display_df = result_df.copy()

            display_df["New"] = display_df["New"].apply(excel_style_pct)
            display_df["Current"] = display_df["Current"].apply(excel_style_pct)

            st.dataframe(
                display_df[["Day", "New", "Current"]],
                hide_index=True
            )

    except Exception as e:
        st.error(f"Target curve failed: {e}")
