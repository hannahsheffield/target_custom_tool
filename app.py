import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from google.cloud import bigquery


# =========================
# Config
# =========================

PROJECT = "your-gcp-project-id"
TABLE = "project.dataset.campaign_performance_daily"

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
LEFT JOIN `project.dataset.product_dimension` AS product
    ON f.product_id = product.product_id

LEFT JOIN `project.dataset.channel_mapping` AS channel_map
    ON f.channel_name = channel_map.channel_name
    AND f.install_date BETWEEN DATE(channel_map.valid_from_date)
    AND DATE(channel_map.valid_to_date)
"""


# =========================
# Page setup
# =========================

st.set_page_config(
    page_title="Custom Target Curve Tool",
    layout="wide",
    page_icon="📊"
)

st.title("📊 Custom Target Curve Tool")


# =========================
# BigQuery client
# =========================

try:
    client = bigquery.Client(project=PROJECT)
    st.success("Connected to BigQuery")
except Exception as error:
    st.error(f"Connection failed: {error}")
    client = None


# =========================
# Helpers
# =========================

@st.cache_data(ttl=300)
def load_filter_options(query, _job_config):
    return client.query(query, job_config=_job_config).to_dataframe()


def excel_style_pct(value):
    if pd.isna(value):
        return "-"

    pct = math.floor(float(value) * 10000) / 100
    return f"{pct:.2f}%"


def get_curve_value(curve, day):
    if day in curve.index:
        return curve.loc[day]

    available_days = curve.index[curve.index <= day]

    if len(available_days) == 0:
        return None

    return curve.loc[available_days.max()]


# =========================
# Data loading
# =========================

def load_main_data(
    client,
    maturity,
    product,
    acquisition_type,
    channel,
    campaign_category,
    device_group
):
    query = f"""
    SELECT
        COUNT(DISTINCT FORMAT_DATE('%Y-%m', f.install_date)) AS months,

        COALESCE(SUM(f.cost_usd), 0) AS total_cost,

        COALESCE(SUM(
            CASE
                WHEN f.activity_date = f.install_date
                THEN COALESCE(f.net_revenue_usd, 0)
                ELSE 0
            END
        ), 0) AS net_revenue,

        COALESCE(SUM(
            CASE
                WHEN f.activity_date = f.install_date
                THEN COALESCE(f.ad_revenue_usd, 0)
                ELSE 0
            END
        ), 0) AS ad_net_revenue,

        COALESCE(SUM(
            CASE
                WHEN f.activity_date = f.install_date
                THEN COALESCE(f.valid_attributions, 0)
                ELSE 0
            END
        ), 0) AS valid_attributions

    FROM `{TABLE}` AS f
    {BASE_JOINS}

    WHERE f.install_date >= DATE_ADD(
            DATE_TRUNC(CURRENT_DATE(), MONTH),
            INTERVAL @maturity_offset MONTH
          )

      AND f.install_date < DATE_ADD(
            DATE_ADD(
                DATE_TRUNC(CURRENT_DATE(), MONTH),
                INTERVAL @maturity_offset MONTH
            ),
            INTERVAL 3 MONTH
          )

      AND f.acquisition_category = 'Paid'
      AND product.product_name IN ('Game A', 'Game B', 'Game C')
      AND channel_map.channel_name IS NOT NULL

      AND (@product = '(All)' OR product.product_name = @product)
      AND (@acquisition_type = '(All)' OR f.acquisition_type = @acquisition_type)
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
            bigquery.ScalarQueryParameter("product", "STRING", product),
            bigquery.ScalarQueryParameter("acquisition_type", "STRING", acquisition_type),
            bigquery.ScalarQueryParameter("channel", "STRING", channel),
            bigquery.ScalarQueryParameter("campaign_category", "STRING", campaign_category),
            bigquery.ScalarQueryParameter("device_group", "STRING", device_group),
        ]
    )

    return client.query(query, job_config=job_config).to_dataframe()


def load_daily_test_data(
    client,
    maturity,
    product,
    acquisition_type,
    channel,
    campaign_category,
    device_group
):
    query = f"""
    SELECT
        DATE_DIFF(f.activity_date, f.install_date, DAY) AS day,

        COALESCE(SUM(f.cost_usd), 0) AS cost,

        COALESCE(SUM(f.net_revenue_usd), 0) AS net_revenue,

        COALESCE(SUM(f.ad_revenue_usd), 0) AS ad_revenue,

        COALESCE(SUM(
            CASE
                WHEN f.activity_date = f.install_date
                THEN COALESCE(f.valid_attributions, 0)
                ELSE 0
            END
        ), 0) AS valid_attributions

    FROM `{TABLE}` AS f
    {BASE_JOINS}

    WHERE f.install_date >= DATE_ADD(
            DATE_TRUNC(CURRENT_DATE(), MONTH),
            INTERVAL @maturity_offset MONTH
          )

      AND f.install_date < DATE_ADD(
            DATE_ADD(
                DATE_TRUNC(CURRENT_DATE(), MONTH),
                INTERVAL @maturity_offset MONTH
            ),
            INTERVAL 3 MONTH
          )

      AND DATE_DIFF(f.activity_date, f.install_date, DAY)
            BETWEEN 0 AND @final_day

      AND f.acquisition_category = 'Paid'
      AND product.product_name IN ('Game A', 'Game B', 'Game C')
      AND channel_map.channel_name IS NOT NULL

      AND (@product = '(All)' OR product.product_name = @product)
      AND (@acquisition_type = '(All)' OR f.acquisition_type = @acquisition_type)
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
            bigquery.ScalarQueryParameter("product", "STRING", product),
            bigquery.ScalarQueryParameter("acquisition_type", "STRING", acquisition_type),
            bigquery.ScalarQueryParameter("channel", "STRING", channel),
            bigquery.ScalarQueryParameter("campaign_category", "STRING", campaign_category),
            bigquery.ScalarQueryParameter("device_group", "STRING", device_group),
        ]
    )

    return client.query(query, job_config=job_config).to_dataframe()
