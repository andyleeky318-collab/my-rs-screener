import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# 1. Setup Streamlit Page
st.set_page_config(page_title="Chrome Sector RS", layout="wide")
st.title("🚀 Chrome Sector Relative Strength")

# 2. Industry Database (Replicating your grp.txt logic)
# You can expand this dictionary with your full list from the Pine Script
INDUSTRIES = {
    "Nuclear": ["CCJ", "BWXT", "SMR", "OKLO", "NNE"],
    "Software": ["MSFT", "ORCL", "PLTR", "CRM", "SNOW"],
    "Semiconductors": ["NVDA", "AMD", "AVGO", "SMCI", "TSM"],
    "MAG7": ["AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"]
}

# 3. Sidebar Inputs
with st.sidebar:
    st.header("Settings")
    selected_industry = st.selectbox("Select Industry Group", list(INDUSTRIES.keys()))
    benchmark = st.selectbox("Benchmark", ["^GSPC", "^IXIC"], index=0) # ^GSPC is S&P 500
    lookback = st.slider("Lookback Period (Days)", 20, 250, 90)
    top_n = st.number_input("Top N for Group Avg", value=5)

# 4. Data Processing Function
def get_rs_data(tickers, benchmark_ticker, period):
    # Fetch data for all tickers + benchmark
    all_tickers = tickers + [benchmark_ticker]
    data = yf.download(all_tickers, period="1y", interval="1d")['Close']
    
    # Calculate RS: (Stock / Benchmark)
    rs_series = data[tickers].div(data[benchmark_ticker], axis=0)
    
    # Get the performance over the lookback period
    rs_perf = ((rs_series.iloc[-1] / rs_series.iloc[-lookback]) - 1) * 100
    
    # Normalize RS to 1-99 (Mirroring your Pine Script logic)
    # We rank them against each other for this specific group
    ranks = rs_perf.rank(pct=True) * 99
    
    return rs_perf, ranks

# 5. Execution and UI
if st.button("Calculate Relative Strength"):
    tickers = INDUSTRIES[selected_industry]
    
    with st.spinner(f"Fetching data for {selected_industry}..."):
        perf, rs_scores = get_rs_data(tickers, benchmark, lookback)
        
        # Calculate Group Average of Top N
        top_n_scores = rs_scores.nlargest(top_n)
        group_avg = top_n_scores.mean()
        
        # Display Metrics
        col1, col2 = st.columns(2)
        col1.metric("Group Avg RS (Top N)", f"{group_avg:.2f}")
        col2.metric("Total Tickers", len(tickers))
        
        # Build Results Table
        df_results = pd.DataFrame({
            "Ticker": tickers,
            "RS Score (1-99)": rs_scores.values,
            "Raw Performance (%)": perf.values
        }).sort_values(by="RS Score (1-99)", ascending=False)
        
        # Style the table
        st.dataframe(df_results.style.background_gradient(subset=["RS Score (1-99)"], cmap="RdYlGn"))
