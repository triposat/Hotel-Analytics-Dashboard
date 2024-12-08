import streamlit as st
import pandas as pd
import plotly.express as px
import json
import re
from pathlib import Path

# Setup dark theme dashboard
st.set_page_config(
    page_title="Hotel Analysis Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark theme CSS styling
st.markdown(
    """
    <style>
        .main { background-color: #263238; color: white; }
        .stApp { background-color: #263238; }
        .css-1d391kg { background-color: #1e272c; }
        .stMetric {
            background-color: rgba(0,0,0,0.1);
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        .stDataFrame { background-color: rgba(0,0,0,0.1); }
        div[data-testid="stExpander"] {
            background-color: rgba(0,0,0,0.1);
            border-radius: 5px;
            padding: 10px;
            margin-bottom: 10px;
        }
        .css-1vq4p4l { background-color: #1e272c; }
        div.css-12w0qpk { background-color: transparent; }
    </style>
    """,
    unsafe_allow_html=True,
)

def format_currency(amount):
    # Convert number to INR format
    if pd.isna(amount):
        return "N/A"
    return f"₹{amount:,.2f}"

def extract_price(price_str):
    # Extract numeric value from price string
    if pd.isna(price_str) or price_str == "":
        return None
    try:
        price_str = str(price_str).replace("₹", "").replace(",", "")
        matches = re.findall(r"[\d.]+", price_str)
        return float(matches[0]) if matches else None
    except (ValueError, IndexError):
        return None

def load_data():
    try:
        with open("data/google_maps_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        df = pd.DataFrame(data)

        # Clean and transform data
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        df["reviews"] = df["reviews"].str.replace(",", "").astype(float)
        df["price_numeric"] = df["price"].apply(extract_price)
        df["amenities"] = df["amenities"].fillna("").apply(lambda x: x if isinstance(x, list) else [])

        return df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None

def get_unique_amenities(df):
    unique_amenities = set()
    for amenities_list in df["amenities"]:
        if isinstance(amenities_list, list):
            unique_amenities.update(amenities_list)
    return sorted(list(unique_amenities))

def main():
    st.title("Hotel Analysis Dashboard")

    df = load_data()
    if df is None or len(df) == 0:
        st.error("Unable to load hotel data. Please check the data file.")
        return

    # Sidebar filters
    st.sidebar.title("Filter Hotels")

    valid_prices = df["price_numeric"].dropna()
    if len(valid_prices) > 0:
        price_range = st.sidebar.slider(
            "Price Range (₹)",
            min_value=int(valid_prices.min()),
            max_value=int(valid_prices.max()),
            value=(int(valid_prices.min()), int(valid_prices.max())),
        )

    valid_ratings = df["rating"].dropna()
    rating_range = st.sidebar.slider(
        "Rating Range",
        min_value=float(valid_ratings.min()),
        max_value=float(valid_ratings.max()),
        value=(float(valid_ratings.min()), float(valid_ratings.max())),
        step=0.1,
    )

    unique_amenities = get_unique_amenities(df)
    selected_amenities = st.sidebar.multiselect(
        "Select Required Amenities", options=unique_amenities
    )

    # Apply all filters
    mask = pd.Series(True, index=df.index)
    if len(valid_prices) > 0:
        mask &= (df["price_numeric"] >= price_range[0]) & (df["price_numeric"] <= price_range[1])
    mask &= (df["rating"] >= rating_range[0]) & (df["rating"] <= rating_range[1])
    if selected_amenities:
        mask &= df["amenities"].apply(lambda x: all(amenity in x for amenity in selected_amenities))

    df_filtered = df[mask]

    # Search section
    st.markdown("### 🔍 Search Hotels")
    search_query = st.text_input("Enter hotel name")

    if search_query:
        search_results = df_filtered[df_filtered["name"].str.contains(search_query, case=False, na=False)]

        if not search_results.empty:
            st.write(f"Found {len(search_results)} hotels matching '{search_query}':")
            for _, hotel in search_results.iterrows():
                with st.expander(f"🏨 {hotel['name']} - ⭐ {hotel['rating']:.1f}"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Price:** {hotel['price']}")
                        st.write(f"**Reviews:** {int(hotel['reviews']):,}")
                        st.write("**Amenities:**")
                        st.write(", ".join(hotel["amenities"]))
                    with col2:
                        if pd.notna(hotel["link"]):
                            st.markdown(f"[🔗 View Details]({hotel['link']})")
        else:
            st.info("No hotels found matching your search.")

    # Display stats
    st.markdown("### 📊 Quick Stats")
    col1, col2, col3 = st.columns(3)

    with col1:
        avg_rating = df_filtered["rating"].mean()
        st.metric("Average Rating", f"{avg_rating:.1f} / 5.0 ⭐")
    with col2:
        total_hotels = len(df_filtered)
        st.metric("Total Hotels", f"{total_hotels:,}")
    with col3:
        median_price = df_filtered["price_numeric"].median()
        st.metric("Median Price", format_currency(median_price))

    # Top hotels table
    st.markdown("### 🏆 Top Rated Hotels")
    top_hotels = df_filtered.nlargest(5, "rating")[["name", "rating", "price"]]
    display_df = top_hotels.copy()
    display_df["rating"] = display_df["rating"].apply(lambda x: f"⭐ {x:.1f}")
    st.dataframe(
        display_df.rename(columns={"name": "Hotel Name", "rating": "Rating", "price": "Price"}),
        hide_index=True,
        use_container_width=True,
    )

    # Visualization section
    col1, col2 = st.columns(2)

    # Amenities chart
    with col1:
        st.markdown("### 🎯 Popular Amenities")
        amenity_counts = {}
        for amenities in df_filtered["amenities"]:
            for amenity in amenities:
                amenity_counts[amenity] = amenity_counts.get(amenity, 0) + 1
        if amenity_counts:
            amenity_df = (
                pd.DataFrame({"Amenity": list(amenity_counts.keys()), "Count": list(amenity_counts.values())})
                .sort_values("Count", ascending=True)
                .tail(10)
            )

            fig_amenities = px.bar(
                amenity_df,
                x="Count",
                y="Amenity",
                orientation="h",
                title="Most Common Amenities",
            )

            fig_amenities.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="white",
                margin=dict(l=10, r=10, t=30, b=10),
            )

            st.plotly_chart(fig_amenities, use_container_width=True)
        else:
            st.info("No amenity data available for the current selection.")

    # Price vs Rating scatter plot
    with col2:
        st.markdown("### 💰 Price vs Rating Analysis")
        valid_data = df_filtered.dropna(subset=["price_numeric", "rating"])

        if not valid_data.empty:
            fig_scatter = px.scatter(
                valid_data,
                x="rating",
                y="price_numeric",
                title="Price vs Rating Distribution",
                labels={"rating": "Rating", "price_numeric": "Price (₹)"},
                hover_data=["name"],
            )

            fig_scatter.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="white",
                margin=dict(l=10, r=10, t=30, b=10),
            )

            fig_scatter.update_traces(marker=dict(size=8, color="#bf360c", opacity=0.6))

            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("Insufficient data for price vs rating analysis.")

if __name__ == "__main__":
    main()
