<a name="readme-top"></a>

<div align="center">

  <h1>Custom Target Curve Tool</h1>

  <p>
    <strong>An anonymised Streamlit application for analysing, comparing, and adjusting marketing target curves using BigQuery data.</strong>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
    <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" />
    <img src="https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white" />
    <img src="https://img.shields.io/badge/Plotly-3F4F75?style=for-the-badge&logo=plotly&logoColor=white" />
    <img src="https://img.shields.io/badge/BigQuery-669DF6?style=for-the-badge&logo=googlecloud&logoColor=white" />
  </p>

</div>

---

## Overview

Custom Target Curve Tool is an anonymised Streamlit application designed to analyse historical marketing performance data and simulate adjusted target curves.

The tool helps users:

- compare current versus proposed target curves
- visualise cumulative RPI behaviour over time
- evaluate maturity-based target curves
- test day-0 target adjustments
- inspect performance by product, acquisition type, channel, campaign category, and device group

The application combines BigQuery querying, curve-building logic, cumulative RPI calculations, and interactive Streamlit controls into a single analytics interface.

> This is a portfolio-safe version of a workplace analytics application. It uses generic names, placeholder datasets, anonymised product names, and simplified business logic. No proprietary data, internal URLs, credentials, or confidential company logic are included.

---

## Problem

Marketing target curves are often difficult to evaluate manually because:

<ul>
  <li>Different maturity windows behave differently over time</li>
  <li>Performance curves vary by channel and acquisition type</li>
  <li>Historical data is spread across large datasets</li>
  <li>Target adjustments are difficult to visualise before deployment</li>
  <li>Comparing chained maturity curves manually is time-consuming</li>
</ul>

Analysts and stakeholders need an easier way to:

- inspect historical curve behaviour
- compare maturity windows
- simulate adjustments
- validate target assumptions

---

## Solution

This application creates an interactive workflow that:

<ol>
  <li>Pulls historical campaign performance data from BigQuery</li>
  <li>Builds cumulative RPI curves across multiple maturity windows</li>
  <li>Chains maturity curves together into a unified final percentage curve</li>
  <li>Allows users to simulate Day 0 target adjustments</li>
  <li>Displays current versus proposed curves side-by-side</li>
  <li>Provides filtering by product, channel, campaign category, acquisition type, and device group</li>
</ol>

---

## Tech Stack

<table>
  <tr>
    <th>Tool</th>
    <th>Purpose</th>
  </tr>
  <tr>
    <td>Python</td>
    <td>Main application and curve logic</td>
  </tr>
  <tr>
    <td>Streamlit</td>
    <td>Interactive analytics application interface</td>
  </tr>
  <tr>
    <td>Pandas</td>
    <td>Data manipulation and cumulative calculations</td>
  </tr>
  <tr>
    <td>Plotly</td>
    <td>Interactive visualisations</td>
  </tr>
  <tr>
    <td>BigQuery</td>
    <td>Historical campaign performance data source</td>
  </tr>
  <tr>
    <td>SQL</td>
    <td>Parameterized performance queries</td>
  </tr>
</table>

---

## Key Features

<table>
  <tr>
    <th>Feature</th>
    <th>Description</th>
  </tr>
  <tr>
    <td><strong>Maturity curve analysis</strong></td>
    <td>Builds cumulative RPI curves for 1m, 3m, 6m, 9m, 12m, 15m, and 18m maturity windows.</td>
  </tr>
  <tr>
    <td><strong>Curve chaining</strong></td>
    <td>Chains maturity windows together into a single continuous final percentage curve.</td>
  </tr>
  <tr>
    <td><strong>Target simulation</strong></td>
    <td>Allows users to test Day 0 target adjustments interactively.</td>
  </tr>
  <tr>
    <td><strong>Interactive filtering</strong></td>
    <td>Filters data by product, acquisition type, channel, campaign category, and device group.</td>
  </tr>
  <tr>
    <td><strong>Current vs proposed comparison</strong></td>
    <td>Displays current curves alongside simulated curves.</td>
  </tr>
  <tr>
    <td><strong>BigQuery integration</strong></td>
    <td>Uses parameterised queries to dynamically load performance data.</td>
  </tr>
</table>

---

## Maturity Windows

<table>
  <tr>
    <th>Maturity Window</th>
    <th>Final Day</th>
  </tr>
  <tr>
    <td>1 Month</td>
    <td>29</td>
  </tr>
  <tr>
    <td>3 Month</td>
    <td>89</td>
  </tr>
  <tr>
    <td>6 Month</td>
    <td>179</td>
  </tr>
  <tr>
    <td>9 Month</td>
    <td>271</td>
  </tr>
  <tr>
    <td>12 Month</td>
    <td>364</td>
  </tr>
  <tr>
    <td>15 Month</td>
    <td>454</td>
  </tr>
  <tr>
    <td>18 Month</td>
    <td>545</td>
  </tr>
</table>

---

## Application Workflow

```text
BigQuery campaign performance data
        ↓
Daily revenue aggregation
        ↓
Daily RPI calculation
        ↓
Cumulative RPI curve generation
        ↓
Maturity curve chaining
        ↓
Current vs proposed curve comparison
        ↓
Interactive Streamlit dashboard
