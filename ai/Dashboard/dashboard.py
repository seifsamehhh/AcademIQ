import pandas as pd
import dash
from dash import dcc, html, Input, Output
import plotly.express as px

# Load data
df = pd.read_csv("/Users/mohamedalaa/Desktop/MIU/AcademIQ/ai/Dashboard/dashboard_data_fixed.csv")


# Initialize Dash app
app = dash.Dash(__name__)
app.title = "Student Risk Dashboard"

# App layout
app.layout = html.Div(
    style={"padding": "20px", "fontFamily": "Arial"},
    children=[

        html.H1("Student Risk Analysis Dashboard"),

        html.P("Interactive visualization of student risk clusters and predictions."),

        # Risk cluster filter
        dcc.Dropdown(
            id="risk-filter",
            options=[
                {"label": "All", "value": "All"},
                {"label": "Low Risk", "value": "Low"},
                {"label": "Medium Risk", "value": "Medium"},
                {"label": "High Risk", "value": "High"},
            ],
            value="All",
            clearable=False,
            style={"width": "300px"}
        ),

        # Scatter plot
        dcc.Graph(id="risk-scatter")
    ]
)

@app.callback(
    Output("risk-scatter", "figure"),
    Input("risk-filter", "value")
)
def update_scatter(selected_risk):
    filtered_df = df.copy()

    if selected_risk != "All":
        filtered_df = filtered_df[
            filtered_df["risk_cluster"] == selected_risk
        ]

    fig = px.scatter(
        filtered_df,
        x="avg_score",
        y="engagement_level",
        color="risk_cluster",
        hover_data=[
            "student_id",
            "prediction_label",
            "recommendation_text"
        ],
        title="Student Risk Clusters"
    )

    fig.update_layout(transition_duration=300)

    return fig


if __name__ == "__main__":
    app.run(debug=True)
