import os
from collections import defaultdict

import pandas as pd
import plotly.express as px
import streamlit as st

from dtower.tourney_results.constants import champ, legend
from dtower.tourney_results.data import get_patches, get_tourneys
from dtower.tourney_results.models import TourneyResult
from components.util import escape_df_html

patches = sorted([patch for patch in get_patches() if patch.version_minor], key=lambda patch: patch.start_date, reverse=True)


def compute_winners():
    selected_patches_slider = st.select_slider(
        "Limit results to a patch?",
        options=sorted([patch for patch in patches if not patch.interim], reverse=True),
        value=patches[-1],
    )

    hidden_features = os.environ.get("HIDDEN_FEATURES")
    public = {"public": True} if not hidden_features else {}
    cdf = get_tourneys(TourneyResult.objects.filter(league=champ, **public), offset=0, limit=10)
    ldf = get_tourneys(TourneyResult.objects.filter(league=legend, **public), offset=0, limit=10)

    selected_patches = [patch for patch in patches if patch.version_minor >= selected_patches_slider.version_minor]

    patches_champ = [patch for patch in selected_patches if patch.version_minor <= 24]
    patches_legend = [patch for patch in selected_patches if patch.version_minor >= 25]

    cdf = cdf[cdf.patch.isin(patches_champ)]
    ldf = ldf[ldf.patch.isin(patches_legend)]

    df = pd.concat([cdf, ldf])

    # Escape HTML in name columns early in the pipeline
    df = escape_df_html(df, ['real_name', 'tourney_name'])

    how_col, hole_col = st.columns([1, 1])

    how_many = how_col.slider("How many past tournaments?", min_value=1, max_value=len(df[df.position == 1]), value=len(df[df.position == 1]))
    hole = hole_col.slider("Hole size?", min_value=0.0, max_value=1.0, value=0.3)

    dates = sorted(df.date.unique(), reverse=True)[:how_many]
    df = df[df.date.isin(dates)]

    scoring = st.selectbox("Scoring method?", ["Only winners", "5-3-2", "10-5-3-2-2-1-1-1-1-1", "bake your own"])

    skye_scoring = {1: 10, 2: 5, 3: 3, 4: 2, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1, 10: 1}

    additional_options = {"hole": hole}

    if scoring == "Only winners":
        winner_score = {1: 1, **dict(zip(range(2, 11), [0] * 9))}
    elif scoring == "5-3-2":
        winner_score = {1: 5, 2: 3, 3: 2, **dict(zip(range(4, 11), [0] * 9))}
    elif scoring == "10-5-3-2-2-1-1-1-1-1":
        winner_score = skye_scoring
    else:
        roll_columns = st.columns([1, 1, 1, 1, 1])
        winner_score = {
            place: roll_columns[(place - 1) % 5].slider(f"How many points for place {place}?", min_value=0, max_value=10, value=skye_scoring.get(place, 0))
            for place in range(1, 11)
        }
        colormap = st.selectbox(
            "Color map?",
            [item for item in dir(px.colors.sequential) if not item.startswith("__") and not item.startswith("swatches")],
        )
        additional_options = dict(color_discrete_sequence=getattr(px.colors.sequential, colormap))

    total_score = defaultdict(int)

    id_name_map = {}

    for position, score in winner_score.items():
        position_df = df[df.position == position]

        for real_name, id_ in zip(position_df.real_name, position_df.id):
            total_score[real_name] += score
            id_name_map[real_name] = id_

    total_score = {name: score for name, score in total_score.items() if score > 0}
    graph_df = pd.DataFrame(total_score.items(), columns=["name", "count"])

    fig = px.pie(graph_df, values="count", names="name", title="Winners of champ, courtesy of Jim", **additional_options)
    fig.update_traces(textinfo="value")
    st.plotly_chart(fig)


compute_winners()
