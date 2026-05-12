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
    "MAG7": ["AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"],
    "Memory": ["MU", "SNDK", "WDC", "STX"]
}

# 3. Sidebar Inputs
with st.sidebar:
    st.header("Settings")
    benchmark = st.selectbox("Benchmark", ["^GSPC", "^IXIC"], index=0) # ^GSPC is S&P 500
    lookback = st.slider("Lookback Period (Days)", 20, 250, 90)
    top_n = st.number_input("Top N for Group Avg", value=5)
    
    # Add Bongo Cat at the bottom of sidebar
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <div style="font-size: 80px;">🐱</div>
        <p style="font-size: 12px; color: gray;">Bongo Cat</p>
    </div>
    """, unsafe_allow_html=True)

# 4. Data Processing Function
def get_rs_data(tickers, benchmark_ticker, period):
    # Fetch data for all tickers + benchmark
    all_tickers = tickers + [benchmark_ticker]
    data = yf.download(all_tickers, period="1y", interval="1d", progress=False)['Close']
    
    # Calculate RS: (Stock / Benchmark)
    rs_series = data[tickers].div(data[benchmark_ticker], axis=0)
    
    # Get the performance over the lookback period
    rs_perf = ((rs_series.iloc[-1] / rs_series.iloc[-period]) - 1) * 100
    
    # Normalize RS to 1-99 (Mirroring your Pine Script logic)
    # We rank them against each other for this specific group
    ranks = rs_perf.rank(pct=True) * 99
    
    return rs_perf, ranks

# 5. Main Display
# Create columns for all industry groups
st.subheader("📊 All Industry Groups")

# Create a grid layout for all industry groups
cols = st.columns(len(INDUSTRIES))

for idx, (industry_name, tickers) in enumerate(INDUSTRIES.items()):
    with cols[idx]:
        with st.spinner(f"Loading {industry_name}..."):
            try:
                perf, rs_scores = get_rs_data(tickers, benchmark, lookback)
                
                # Calculate Group Average of Top N
                top_n_scores = rs_scores.nlargest(int(top_n))
                group_avg = top_n_scores.mean()
                
                # Display Industry Header
                st.markdown(f"### {industry_name}")
                
                # Display Metrics
                st.metric("Group Avg RS (Top N)", f"{group_avg:.2f}")
                
                # Build Results Table
                df_results = pd.DataFrame({
                    "Ticker": tickers,
                    "RS Score": rs_scores.values,
                    "Perf (%)": perf.values
                }).sort_values(by="RS Score", ascending=False)
                
                # Style the table
                st.dataframe(
                    df_results.style.background_gradient(subset=["RS Score"], cmap="RdYlGn"),
                    use_container_width=True,
                    height=300
                )
            except Exception as e:
                st.error(f"Error loading {industry_name}: {str(e)}")
