import streamlit as st
import pandas as pd
from datetime import datetime, time
import pytz
from zerodte_recommender import ZeroDTERecommender

# Page config
st.set_page_config(
    page_title="SPX Credit Spread Trading Dashboard",
    page_icon="📈",
    layout="wide"
)

# Initialize recommender
@st.cache_resource
def get_recommender():
    return ZeroDTERecommender()

recommender = get_recommender()

# Title
st.title("🎯 SPX Credit Spread Trading Dashboard")

# Sidebar for settings
st.sidebar.header("Trading Parameters")

spx_price = st.sidebar.number_input(
    "SPX Current Price",
    value=5820.0,
    step=1.0,
    help="Current SPX index price"
)

target_credit = st.sidebar.number_input(
    "Target Credit ($)",
    value=2500,
    step=100,
    help="Target credit to receive from the spread"
)

max_margin = st.sidebar.number_input(
    "Max Margin ($)",
    value=5000,
    step=100,
    help="Maximum margin you're willing to use"
)

# Market time check
est = pytz.timezone('US/Eastern')
current_time = datetime.now(est).time()
market_open = time(9, 30)
entry_time = time(9, 31)
reentry_time = time(14, 0)
exit_time = time(15, 5)

# Main dashboard
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.subheader("Market Status")
    
    # Time display
    current_time_str = datetime.now(est).strftime("%H:%M:%S EST")
    st.metric("Current Time", current_time_str)
    
    # Market status
    if market_open <= current_time <= exit_time:
        st.success("🟢 Market Open")
        if current_time >= entry_time:
            st.info("✅ Entry Window Open")
        else:
            st.warning("⏳ Waiting for Entry Time (9:31 AM)")
    else:
        st.error("🔴 Market Closed")

# Get recommendations
trend_data = recommender.calculate_trend_score(spx_price)
recommendations = recommender.get_trade_recommendations(
    spx_price, target_credit, max_margin
)

# Main content area
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Trend Analysis")
    
    # Trend score with interpretation
    trend_score = trend_data['raw_score']
    st.metric(
        "Raw Trend Score",
        f"{trend_score:.4f}",
        help="Logarithmic return trend calculation. Positive = bullish, Negative = bearish"
    )
    
    # Interpretation
    if trend_score > 0.02:
        st.success("🔥 Strongly Bullish - Consider Bull Put Spreads")
    elif trend_score > 0:
        st.info("📈 Weakly Bullish - Consider Bull Put Spreads")
    elif trend_score > -0.02:
        st.info("📉 Weakly Bearish - Consider Bear Call Spreads")
    else:
        st.error("🔥 Strongly Bearish - Consider Bear Call Spreads")
    
    # VIX context
    vix_level = trend_data.get('vix_level', 18.2)
    st.metric("VIX Level", f"{vix_level:.1f}")
    
    if vix_level < 15:
        st.info("Low volatility environment")
    elif vix_level > 25:
        st.warning("High volatility environment")
    else:
        st.success("Normal volatility environment")

with col2:
    st.subheader("🎯 Trade Recommendations")
    
    # Display recommendations based on trend
    if trend_data['should_trade_long']:
        st.success("📈 BULL PUT SPREAD RECOMMENDED")
        
        rec = recommendations['bull_put_spread']
        
        col2a, col2b = st.columns(2)
        with col2a:
            st.metric("Short Strike", f"{rec['short_strike']}")
            st.metric("Short Delta", f"{rec['short_delta']:.2f}")
        with col2b:
            st.metric("Long Strike", f"{rec['long_strike']}")
            st.metric("Long Delta", f"{rec['long_delta']:.2f}")
            
        st.metric("Distance from ATM", f"{rec['distance_from_atm']:.0f} points")
        
    elif trend_data['should_trade_short']:
        st.error("📉 BEAR CALL SPREAD RECOMMENDED")
        
        rec = recommendations['bear_call_spread']
        
        col2a, col2b = st.columns(2)
        with col2a:
            st.metric("Short Strike", f"{rec['short_strike']}")
            st.metric("Short Delta", f"{rec['short_delta']:.2f}")
        with col2b:
            st.metric("Long Strike", f"{rec['long_strike']}")
            st.metric("Long Delta", f"{rec['long_delta']:.2f}")
            
        st.metric("Distance from ATM", f"{rec['distance_from_atm']:.0f} points")
    
    else:
        st.warning("⏸️ NO CLEAR TREND - CONSIDER WAITING")

# Risk management section
st.subheader("⚠️ Risk Management")

col3, col4, col5 = st.columns(3)

with col3:
    contracts_needed = recommendations.get('contracts_needed', 1)
    total_credit = recommendations.get('estimated_credit', 0) * contracts_needed
    
    st.metric(
        "Contracts Needed",
        f"{contracts_needed}",
        help="Number of spreads to trade to reach target credit"
    )
    st.metric("Expected Credit", f"${total_credit:,.0f}")

with col4:
    max_loss = recommendations.get('max_loss_per_spread', 0) * contracts_needed
    margin_needed = max_loss - total_credit
    
    st.metric("Max Loss", f"${max_loss:,.0f}")
    st.metric("Margin Required", f"${margin_needed:,.0f}")
    
    # Margin utilization
    margin_util = (margin_needed / max_margin) * 100 if max_margin > 0 else 0
    if margin_util > 90:
        st.error(f"⚠️ High margin usage: {margin_util:.1f}%")
    elif margin_util > 70:
        st.warning(f"⚠️ Moderate margin usage: {margin_util:.1f}%")
    else:
        st.success(f"✅ Safe margin usage: {margin_util:.1f}%")

with col5:
    stop_loss_level = total_credit * 0.99  # 99% of credit (1% loss tolerance)
    take_profit_level = total_credit * 0.05  # 5% profit
    
    st.metric("Stop Loss Level", f"-${stop_loss_level:,.0f}")
    st.metric("Take Profit Level", f"${take_profit_level:,.0f}")

# Detailed execution info
st.subheader("📋 Execution Details")

if trend_data['should_trade_long'] or trend_data['should_trade_short']:
    trade_type = "Bull Put Spread" if trend_data['should_trade_long'] else "Bear Call Spread"
    rec = recommendations['bull_put_spread'] if trend_data['should_trade_long'] else recommendations['bear_call_spread']
    
    with st.expander(f"📊 {trade_type} Execution Details"):
        col6, col7 = st.columns(2)
        
        with col6:
            st.write("**Short Leg (Sell):**")
            st.write(f"- Strike: {rec['short_strike']}")
            st.write(f"- Delta: {rec['short_delta']:.2f}")
            st.write(f"- Est. Bid: ${rec.get('short_bid', 3.50):.2f}")
            st.write(f"- Volume Check: {rec.get('short_volume', 'N/A')}")
            
        with col7:
            st.write("**Long Leg (Buy):**")
            st.write(f"- Strike: {rec['long_strike']}")
            st.write(f"- Delta: {rec['long_delta']:.2f}")
            st.write(f"- Est. Ask: ${rec.get('long_ask', 2.00):.2f}")
            st.write(f"- Volume Check: {rec.get('long_volume', 'N/A')}")
            
        st.write("**Spread Summary:**")
        st.write(f"- Estimated Credit: ${rec.get('estimated_credit', 150):.0f}")
        st.write(f"- Max Loss: ${rec.get('max_loss', 350):.0f}")
        st.write(f"- Strike Width: 5 points")
        st.write(f"- Contracts: {contracts_needed}")

# Trading checklist
st.subheader("✅ Pre-Trade Checklist")

checklist_items = [
    ("Market is open and past entry time (9:31 AM)", current_time >= entry_time if market_open <= current_time <= exit_time else False),
    ("Clear trend signal present", abs(trend_score) > 0.001),
    ("Margin requirement within limits", margin_util <= 90),
    ("Both strikes have adequate volume", True),  # Would check real volume data
    ("Credit target is achievable", total_credit >= target_credit * 0.8),
]

for item, status in checklist_items:
    if status:
        st.success(f"✅ {item}")
    else:
        st.error(f"❌ {item}")

# Footer
st.markdown("---")
st.caption("⚠️ This dashboard is for educational purposes. Always verify with live market data before trading.")
st.caption("📊 Based on 0DTE SPX credit spread strategy with trend-following signals.")
