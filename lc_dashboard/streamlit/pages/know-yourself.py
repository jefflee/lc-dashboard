import os

import numpy as np
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, DataReturnMode
import plotly.express as px

st.set_page_config(layout="wide")

GS_SHEET_ID = os.environ.get(
    "GS_SHEET_ID", "1wADT0jfyHTXAcu5WK3Sa3KGKWaoCwcFZ_sCQqR2XZrY"
)

df = pd.read_csv(
    f"https://docs.google.com/spreadsheets/d/{GS_SHEET_ID}/export?format=csv"
)

df["ts"] = pd.to_datetime(df["ts"], unit="s")

if_filter = st.sidebar.toggle(
    "filter df?",
    help="if this toggled, then the stat will only calculated on filtered records",
)

if if_filter:
    df = AgGrid(
        df,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        fit_columns_on_grid_load=True,
        height=300,
        width="100%",
    )["data"]
else:
    AgGrid(
        df,
        fit_columns_on_grid_load=True,
        height=300,
        width="100%",
    )

stat = df.groupby(["country", "competition"]).agg(
    ts=("ts", "min"),
    one_percent_rank=("rank", lambda x: x.quantile(0.01)),
    twenty_five_rank=("rank", lambda x: x.quantile(0.25)),
    fifty_rank=("rank", lambda x: x.quantile(0.5)),
    seventy_five_rank=("rank", lambda x: x.quantile(0.75)),
    n_candidates=("ts", "count"),
)

# user id setting
params = st.experimental_get_query_params()

user_ids = list(set(df["name"]))
if params.get("name"):
    user_id_query_idx = user_ids.index(params.get("name")[0])
else:
    user_id_query_idx = 0

user_id = st.sidebar.selectbox(
    "pick your id compare with others",
    user_ids,
    user_id_query_idx,
    help="leetcode id that wanna analysis",
)

is_calculate_competitors = st.sidebar.toggle(
    "If suggest competitors?",
    help="will pick k candidates who's percentile most close to you",
)
if is_calculate_competitors:
    n_competitors = st.sidebar.number_input(
        "number of competitors?", min_value=1, max_value=10, value=3
    )
    min_competitions = st.sidebar.number_input(
        "minimum number of competition attended?", min_value=1, max_value=10, value=3
    )

if user_id:
    person_score = df[df["name"] == user_id][
        ["name", "rank", "competition", "percentile"]
    ]

    # calculate most close competitors
    if is_calculate_competitors:
        user_median = person_score["percentile"].median()
        candidates = df.groupby("name").agg(
            {"percentile": "median", "competition": "count"}
        )
        candidates = candidates[candidates["competition"] >= min_competitions]
        candidates["diff"] = (candidates["percentile"] - user_median).abs()
        suggest_competitors = set(
            candidates.nsmallest(n_competitors + 1, "diff").index
        ) - set([user_id])

    else:
        suggest_competitors = None

    # pick competitors
    competitors = st.multiselect(
        "select competitors", set(df["name"]), suggest_competitors
    )
    # add competitor into dataframe
    for competitor in competitors:
        competitor_score = df[df["name"] == competitor][["rank", "competition"]]
        competitor_score.columns = [competitor, "competition"]
        person_score = person_score.merge(
            competitor_score, on="competition", how="outer"
        )

    merged_result = person_score.merge(stat, on=["competition"])
    available_lines = [
        "one_percent_rank",
        "twenty_five_rank",
        "fifty_rank",
        "seventy_five_rank",
    ] + competitors
    selected_lines = st.multiselect(
        "available metrics", available_lines, available_lines
    )
    merged_result.sort_values("ts", inplace=True)

    # draw lines
    fig = px.line(
        merged_result[["ts", "rank"] + selected_lines],
        x="ts",
        y=["rank"] + selected_lines,
        markers=True,
    )

    for selected_line in selected_lines:
        fig.update_traces(selector={"name": selected_line}, line={"dash": "dash"})

    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    # show metrics you compare to others
    st.write(user_id)
    for row in merged_result.iterrows():
        user_rank, score_1, score_25, score_50, score_75 = (
            row[1]["rank"],
            row[1]["one_percent_rank"],
            row[1]["twenty_five_rank"],
            row[1]["fifty_rank"],
            row[1]["seventy_five_rank"],
        )
        if np.isnan(user_rank):
            continue
        col0, col1, col2, col3, col4 = st.columns(5)
        with col0:
            st.write(row[1]["competition"])
            st.write(user_rank)
        col1.metric(f"compare with 1%:", round(score_1), f"{score_1-user_rank}")
        col2.metric(f"compare with 25%:", round(score_25), f"{score_25-user_rank}")
        col3.metric(f"compare with 50%:", round(score_50), f"{score_50-user_rank}")
        col4.metric(f"compare with 75%:", round(score_75), f"{score_75-user_rank}")