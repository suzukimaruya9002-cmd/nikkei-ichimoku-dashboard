"""Archive Nikkei 225 1-minute OHLC data by JST trading day.

Runs in GitHub Actions. Historical data availability depends on Yahoo Finance.
"""
from pathlib import Path
import pandas as pd
import yfinance as yf

ROOT = Path("data/1m")
ROOT.mkdir(parents=True, exist_ok=True)
raw = yf.download("^N225", period="5d", interval="1m",
                  auto_adjust=False, progress=False, multi_level_index=False)
if raw is None or raw.empty:
    print("No intraday data returned; preserving archive.")
    raise SystemExit(0)
raw = raw[["Open", "High", "Low", "Close"]].dropna()
idx = pd.to_datetime(raw.index)
raw.index = idx.tz_localize("Asia/Tokyo") if idx.tz is None else idx.tz_convert("Asia/Tokyo")
raw.index.name = "JST"
for day, group in raw.groupby(raw.index.strftime("%Y-%m-%d")):
    path = ROOT / f"{day}.csv"
    group = group.copy()
    group.index = group.index.strftime("%Y-%m-%d %H:%M:%S%z")
    if path.exists():
        old = pd.read_csv(path, index_col="JST")
        group = pd.concat([old, group])
    group = group[~group.index.duplicated(keep="last")].sort_index()
    group.to_csv(path, float_format="%.4f")
    print(f"{path}: {len(group)} bars")
# One record per session: exact minute-bar timestamps, not exact trade timestamps.
rows = []
for path in sorted(ROOT.glob("????-??-??.csv")):
    frame = pd.read_csv(path)
    if frame.empty:
        continue
    hi = frame.loc[frame.High.idxmax()]
    lo = frame.loc[frame.Low.idxmin()]
    rows.append({"date_jst": path.stem, "high": hi.High, "high_bar_jst": hi.JST,
                 "low": lo.Low, "low_bar_jst": lo.JST, "bars": len(frame)})
pd.DataFrame(rows, columns=["date_jst","high","high_bar_jst","low","low_bar_jst","bars"]).to_csv(
    "data/daily_extrema.csv", index=False)
print(f"Indexed {len(rows)} sessions")
