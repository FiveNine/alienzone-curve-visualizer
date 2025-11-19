import math
from typing import List, Optional, Dict

import pandas as pd
import plotly.express as px
import streamlit as st

WAD = 10**18  # 1e18

# -------- Solidity-like integer math --------

def mul_div(n: int, num: int, den: int, round_up: bool) -> int:
    if round_up:
        return (n * num + den - 1) // den
    return (n * num) // den

def curve(x_wad: int, total_supply_wad: int, curve_factor: int, initial_price_factor_wad: int) -> int:
    # ((totalSupply * curveFactor * 1e18) / (totalSupply - x)) - (curveFactor * 1e18)
    denom = total_supply_wad - x_wad
    if denom <= 0:
        # Match contract domain: caller must ensure x < totalSupply
        raise ZeroDivisionError("totalSupply - x_wad must be > 0")
    curve_price = (total_supply_wad * curve_factor * WAD) // denom - (curve_factor * WAD)
    # (initialPriceFactor * x) / 1e18
    base_price = (initial_price_factor_wad * x_wad) // WAD
    return curve_price + base_price

def get_buy_price(
    supply_wad: int,
    amount_wad: int,
    total_supply_wad: int,
    curve_factor: int,
    initial_price_factor_wad: int
) -> Optional[int]:
    # Contract guard: require supply + amount < totalSupply
    if supply_wad + amount_wad >= total_supply_wad:
        return None
    return curve(supply_wad + amount_wad, total_supply_wad, curve_factor, initial_price_factor_wad) - curve(
        supply_wad, total_supply_wad, curve_factor, initial_price_factor_wad
    )

def get_sell_price(
    supply_wad: int,
    amount_wad: int,
    total_supply_wad: int,
    curve_factor: int,
    initial_price_factor_wad: int
) -> Optional[int]:
    # Contract logic sells from 'supply' back to 'supply - amount'
    # Guard to avoid x == totalSupply inside curve()
    if supply_wad >= total_supply_wad or amount_wad > supply_wad:
        return None
    return curve(supply_wad, total_supply_wad, curve_factor, initial_price_factor_wad) - curve(
        supply_wad - amount_wad, total_supply_wad, curve_factor, initial_price_factor_wad
    )

def get_buy_price_after_fee(price_wad: Optional[int], protocol_bps: int, creator_bps: int) -> Optional[int]:
    if price_wad is None:
        return None
    protocol_fee = mul_div(price_wad, protocol_bps, 10_000, round_up=True)
    creator_fee  = mul_div(price_wad, creator_bps,  10_000, round_up=True)
    return price_wad + protocol_fee + creator_fee

def get_sell_price_after_fee(price_wad: Optional[int], protocol_bps: int, creator_bps: int) -> Optional[int]:
    if price_wad is None:
        return None
    protocol_fee = mul_div(price_wad, protocol_bps, 10_000, round_up=False)
    creator_fee  = mul_div(price_wad, creator_bps,  10_000, round_up=False)
    return price_wad - protocol_fee - creator_fee
def to_wad_zone(x_zone: float) -> int:
    return int(round(x_zone * WAD))

def from_wad_zone(x_wad: Optional[int]) -> Optional[float]:
    if x_wad is None:
        return None
    return x_wad / WAD

# -------- UI --------

st.set_page_config(page_title="Alienzone Wearables Price Curve", layout="wide")
st.title("Alienzone Wearables Bonding Curve Visualizer")

st.header("Parameters")
col1, col2, col3 = st.columns(3)
with col1:
    initial_price_zone = st.number_input(
        "initialPriceFactor (ZONE per full wearable)",
        min_value=0.000_000_000_000_000_001,
        value=500.0,
        step=1.0,
        format="%.9f",
    )
with col2:
    supply_factor = st.number_input(
        "supplyFactor (full wearables cap)",
        min_value=1,
        max_value=10_000,
        value=1000,
        step=1,
    )
with col3:
    curve_factor = st.number_input(
        "curveFactor",
        min_value=1,
        max_value=1000,
        value=25,
        step=1,
    )

st.markdown("### Fees and trade amount")
col4, col5, col6 = st.columns(3)
with col4:
    protocol_bps = st.number_input("protocolFeeBps (bps)", min_value=0, max_value=2000, value=250, step=1)
with col5:
    creator_bps = st.number_input("creatorFeeBps (bps)", min_value=0, max_value=2000, value=300, step=1)
with col6:
    amount_full = st.number_input(
        "Trade amount (full wearables)",
        min_value=0.001,
        value=1.0,
        step=0.001,
        format="%.3f",
    )

# Enforce 0.001 granularity like the contract
amount_full = round(amount_full / 0.001) * 0.001

# Derived values
initial_price_wad = to_wad_zone(initial_price_zone)
total_supply_wad = supply_factor * WAD
amount_wad = to_wad_zone(amount_full)
max_n_available = supply_factor

st.markdown("---")
st.subheader("Point-in-time calculator")
col1, col2 = st.columns(2)
with col1:
    n_available_now = st.number_input(
        "n available now (full wearables)",
        min_value=0,
        max_value=max_n_available,
        value=int(supply_factor),
        step=1,
    )
with col2:
    amount_now = st.number_input(
        "Buy amount (full wearables)",
        min_value=0.001,
        value=float(amount_full),
        step=0.001,
        format="%.3f",
    )
    amount_now = round(amount_now / 0.001) * 0.001
supply_now = (supply_factor - n_available_now) * WAD
amount_now_wad = to_wad_zone(amount_now)
ip_now = initial_price_wad

buy_now = get_buy_price(supply_now, amount_now_wad, total_supply_wad, curve_factor, ip_now)
buy_now_net = get_buy_price_after_fee(buy_now, protocol_bps, creator_bps) if buy_now is not None else None

colA, colB = st.columns(2)
colA.metric("Buy price (before fee)", f"{from_wad_zone(buy_now):,.6f} ZONE" if buy_now is not None else "N/A")
colB.metric("Buy price (after fee)", f"{from_wad_zone(buy_now_net):,.6f} ZONE" if buy_now_net is not None else "N/A")

st.caption("Notes: Min unit = 0.001 wearable. Buys add fees. Prices are computed with the same integer math and guards as in the Solidity contract.")

st.markdown("---")
st.subheader("Sample buy prices by % available supply")
st.caption("Buy price for the selected trade amount at each percentage of remaining (not yet sold) supply.")

sample_rows: List[Dict] = []
for pct_available in range(0, 101):
    remaining_fraction = pct_available / 100.0
    sold_fraction = 1.0 - remaining_fraction

    n_sold = int(round(sold_fraction * supply_factor))
    if n_sold < 0:
        n_sold = 0
    if n_sold > supply_factor:
        n_sold = supply_factor

    supply_sample_wad = n_sold * WAD
    price_sample = get_buy_price(supply_sample_wad, amount_wad, total_supply_wad, curve_factor, initial_price_wad)
    price_sample_net = get_buy_price_after_fee(price_sample, protocol_bps, creator_bps) if price_sample is not None else None

    n_available = supply_factor - n_sold

    sample_rows.append(
        {
            "% available": pct_available,
            "n available (full wearables)": n_available,
            f"Buy price (amount={amount_full})": from_wad_zone(price_sample),
            f"Buy price after fee (amount={amount_full})": from_wad_zone(price_sample_net),
        }
    )

if sample_rows:
    sample_df = pd.DataFrame(sample_rows)

    # Graph: buy price for 1.0 full wearable (before fees) vs n available
    one_full_wad = to_wad_zone(1.0)

    def price_for_n_available(n_available: int) -> Optional[float]:
        n_sold = supply_factor - n_available
        if n_sold < 0:
            n_sold = 0
        if n_sold > supply_factor:
            n_sold = supply_factor
        supply_wad = n_sold * WAD
        price_wad = get_buy_price(supply_wad, one_full_wad, total_supply_wad, curve_factor, initial_price_wad)
        return from_wad_zone(price_wad)

    graph_df = sample_df.sort_values("n available (full wearables)")
    graph_df["Buy price (amount=1.0, before fee)"] = graph_df["n available (full wearables)"].apply(
        lambda n: price_for_n_available(int(n))
    )

    st.subheader("Buy price vs available supply (amount = 1.0, before fees)")
    fig = px.line(
        graph_df,
        x="n available (full wearables)",
        y="Buy price (amount=1.0, before fee)",
        labels={
            "n available (full wearables)": "Available supply (full wearables)",
            "Buy price (amount=1.0, before fee)": "Buy price in ZONE (amount = 1.0)",
        },
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # Table below the graph, sorted by % available descending
    sample_df = sample_df.sort_values("% available", ascending=False)
    st.table(sample_df)
