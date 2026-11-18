import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

st.set_page_config(page_title="日経平均｜一目均衡表", page_icon="📈", layout="wide")
st.markdown("""<style>
.block-container {padding: 0.9rem 0.8rem 3rem;max-width:1200px}
h1 {font-size:1.5rem!important;margin-bottom:.25rem!important}
h2 {font-size:1.15rem!important}
[data-testid="stMetricValue"] {font-size:1.35rem}
[data-testid="stMetricLabel"] {font-size:.75rem}
div[data-testid="stHorizontalBlock"] {gap:.4rem}
@media(max-width:700px) {
.block-container {padding:.65rem .55rem 2rem}
[data-testid="stMetricValue"] {font-size:1.15rem}
[data-testid="stMetricDelta"] {font-size:.7rem}
}
</style>""",unsafe_allow_html=True)
st.title("日経平均｜一目均衡表")
st.caption("日足・週足 / 9・26・52 / 価格はYahoo Finance提供（遅延あり）")

@st.cache_data(ttl=900,show_spinner=False)
def load_prices():
    d=yf.download("^N225",start="2024-01-01",auto_adjust=False,progress=False,multi_level_index=False)
    if d is None or d.empty:
        raise RuntimeError("株価データを取得できません")
    d.index=pd.to_datetime(d.index).tz_localize(None).normalize()
    return d[["Open","High","Low","Close"]].dropna().sort_index()

def calc(d):
    d=d.copy()
    d["tenkan"]=(d.High.rolling(9).max()+d.Low.rolling(9).min())/2
    d["kijun"]=(d.High.rolling(26).max()+d.Low.rolling(26).min())/2
    d["a_raw"]=(d.tenkan+d.kijun)/2
    d["b_raw"]=(d.High.rolling(52).max()+d.Low.rolling(52).min())/2
    d["cloud_a"]=d.a_raw.shift(26)
    d["cloud_b"]=d.b_raw.shift(26)
    return d

try:
    daily=load_prices()
except Exception as exc:
    st.error(f"データ取得エラー：{exc}")
    st.stop()

with st.container():
    x1,x2=st.columns(2)
    with x1:
        timeframe=st.segmented_control("時間軸",["日足","週足"],default="日足")
    with x2:
        period=st.selectbox("表示期間",["直近1か月","直近3か月","2026/6/22以降"],index=1)
    with st.expander("表示する線・追加設定",expanded=False):
        show_tenkan=st.checkbox("転換線（橙）",True)
        show_kijun=st.checkbox("基準線（青）",True)
        show_cloud=st.checkbox("雲（緑・赤）",True)
        show_chikou=st.checkbox("遅行スパン（紫）",False)
        show_markers=st.checkbox("直近の高値・安値マーカー",True)
        if st.button("最新株価を再取得"):
            load_prices.clear()
            st.rerun()

if timeframe=="週足":
    base=daily.resample("W-FRI").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
else:
    base=daily
d=calc(base)
end=d.index[-1]
start={"直近1か月":end-pd.Timedelta(days=35),"直近3か月":end-pd.Timedelta(days=95),"2026/6/22以降":pd.Timestamp("2026-06-22")}[period]
v=d.loc[d.index>=start]
if v.empty:
    st.warning("選択期間のデータがありません")
    st.stop()
last=d.iloc[-1]
prev=d.iloc[-2]
delta=last.Close-prev.Close
m1,m2,m3=st.columns(3)
m1.metric("終値",f"{last.Close:,.0f}",f"{delta:+,.0f}円")
m2.metric("転換線",f"{last.tenkan:,.0f}")
m3.metric("基準線",f"{last.kijun:,.0f}")
st.caption(f"データ最終日：{end:%Y/%m/%d}（{timeframe}）｜取引所の休場・配信遅延に注意")

fig=go.Figure()
fig.add_trace(go.Candlestick(x=v.index,open=v.Open,high=v.High,low=v.Low,close=v.Close,
    name="日経平均",increasing_line_color="#22c55e",decreasing_line_color="#f87171",
    increasing_fillcolor="#22c55e",decreasing_fillcolor="#f87171"))
if show_cloud:
    # 26本先への雲投影。日足の未来日付は平日ベースで日本の祝日は未考慮。
    future=(pd.bdate_range(d.index[-1]+pd.offsets.BDay(1),periods=26)
            if timeframe=="日足" else
            pd.date_range(d.index[-1]+pd.Timedelta(days=7),periods=26,freq="W-FRI"))
    cloud_dates=d.index.append(future)
    a=pd.Series(float("nan"),index=cloud_dates)
    b=a.copy()
    a.loc[d.index]=d.cloud_a
    b.loc[d.index]=d.cloud_b
    a.loc[future]=d.a_raw.tail(26).to_numpy()
    b.loc[future]=d.b_raw.tail(26).to_numpy()
    cx=cloud_dates[cloud_dates>=v.index[0]]
    fig.add_trace(go.Scatter(x=cx,y=a.loc[cx],name="先行A",line=dict(color="#22c55e",width=1.2),
        hovertemplate="%{x|%Y/%m/%d}<br>先行A %{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=cx,y=b.loc[cx],name="先行B",line=dict(color="#f87171",width=1.2),
        fill="tonexty",fillcolor="rgba(34,197,94,.09)",
        hovertemplate="%{x|%Y/%m/%d}<br>先行B %{y:,.0f}<extra></extra>"))
if show_tenkan:
    fig.add_trace(go.Scatter(x=v.index,y=v.tenkan,name="転換線",line=dict(color="#fbbf24",width=2)))
if show_kijun:
    fig.add_trace(go.Scatter(x=v.index,y=v.kijun,name="基準線",line=dict(color="#60a5fa",width=2)))
if show_chikou:
    # 終値を26本前の日付にプロット（最新26本を含む）
    chikou_dates=d.index[:-26]
    chikou_values=d.Close.iloc[26:].to_numpy()
    lag=pd.Series(chikou_values,index=chikou_dates)
    lag=lag.loc[lag.index>=v.index[0]]
    fig.add_trace(go.Scatter(x=lag.index,y=lag,name="遅行スパン",line=dict(color="#c084fc",width=1.6,dash="dot")))

high_date=v.High.idxmax()
low_date=v.Low.idxmin()
if show_markers:
    fig.add_trace(go.Scatter(x=[high_date,low_date],y=[v.High.max(),v.Low.min()],
        mode="markers",name="高値・安値",marker=dict(size=9,color=["#fbbf24","#38bdf8"],symbol=["triangle-down","triangle-up"]),
        text=[f"高値 {v.High.max():,.0f}円",f"安値 {v.Low.min():,.0f}円"],
        hovertemplate="%{x|%Y/%m/%d}<br>%{text}<extra></extra>"))

fig.update_layout(
    template="plotly_dark",height=460,margin=dict(l=0,r=2,t=14,b=5),
    xaxis_rangeslider_visible=False,hovermode="x unified",
    paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",
    legend=dict(orientation="h",y=-.18,x=0,font=dict(size=10)),
    xaxis=dict(showgrid=False,tickformat="%m/%d",nticks=6),
    yaxis=dict(title=None,side="right",tickformat=",.0f",nticks=6,showgrid=True,
               gridcolor="rgba(160,170,190,.18)"),
    dragmode="pan")
st.plotly_chart(fig,use_container_width=True,config={"displaylogo":False,"scrollZoom":False,
    "modeBarButtonsToRemove":["lasso2d","select2d","autoScale2d"]})
st.caption("チャートの点をタップすると日付と価格を表示します。線の凡例をタップすると表示を切り替えられます。")

st.subheader("重要価格")
high,low=st.columns(2)
high.metric("期間高値",f"{v.High.max():,.0f} 円")
high.caption(f"到達日：{high_date:%Y/%m/%d}")
low.metric("期間安値",f"{v.Low.min():,.0f} 円")
low.caption(f"到達日：{low_date:%Y/%m/%d}")

top=max(last.cloud_a,last.cloud_b)
bottom=min(last.cloud_a,last.cloud_b)
above=last.Close>top
below=last.Close<bottom
tk=last.tenkan>last.kijun
# 遅行スパンは最新終値を26本前の日付へ描くため、比較対象は26本前の終値。
lag_bull=last.Close>d.Close.iloc[-27]
state="三役好転（簡易）" if above and tk and lag_bull else "三役逆転（簡易）" if below and not tk and not lag_bull else "混在"
st.subheader("現在の判定")
st.write(f"**{state}**｜株価：{'雲の上' if above else '雲の下' if below else '雲の中'}｜転換線：{'基準線より上' if tk else '基準線以下'}｜遅行：{'強気' if lag_bull else '弱気'}")
st.caption("遅行スパンは26本前の終値との比較による簡易判定で、ローソク足の高安との関係は含みません。")

with st.expander("時間論・転換点",expanded=False):
    turns=[]
    for i in range(5,len(d)-5):
        if d.High.iloc[i]==d.High.iloc[i-5:i+6].max():
            turns.append((d.index[i],float(d.High.iloc[i]),"高値",i))
        if d.Low.iloc[i]==d.Low.iloc[i-5:i+6].min():
            turns.append((d.index[i],float(d.Low.iloc[i]),"安値",i))
    turns.sort(key=lambda x:x[0])
    if turns:
        dt,price,kind,idx=turns[-1]
        st.write(f"直近の確定転換点：**{dt:%Y/%m/%d} {kind} {price:,.0f}円**")
        st.write(f"起点を1本目として、現在 **{len(d)-idx}本目**")
        rows=[{"基本数値":n,"到達日":d.index[idx+n-1].strftime("%Y/%m/%d") if idx+n-1<len(d) else "未到達"} for n in (9,17,26,33,42,65,76,129)]
        st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    st.caption("転換点は前後5本から機械的に抽出。直近5本は未確定です。")

with st.expander("値幅観測論（3点入力）",expanded=False):
    st.caption("下落波動A高値→B安値→C戻り高値。値は参考計算です。")
    A=st.number_input("A：高値",min_value=0.0,value=float(v.High.max()))
    B=st.number_input("B：安値",min_value=0.0,value=float(v.Low.min()))
    C=st.number_input("C：戻り高値",min_value=0.0,value=float(last.Close))
    if A<=B or C<=B:
        st.warning("下落波動では通常A>B、C>Bの3点を選択してください。")
    targets={"N":C-(A-B),"E":B-(A-B),"V":B-(C-B),"NT":C-(A-C)}
    st.dataframe(pd.DataFrame([{"観測値":k,"価格（円）":f"{value:,.0f}"} for k,value in targets.items()]),hide_index=True,use_container_width=True)

with st.expander("データのダウンロード",expanded=False):
    st.download_button("CSVを保存",d.loc[d.index>=pd.Timestamp("2026-06-22")].to_csv(index_label="Date").encode("utf-8-sig"),
        file_name="nikkei_ichimoku.csv",mime="text/csv")
st.caption("免責：投資判断の参考資料です。場中の高安値到達時刻は日足データからは特定できません。")
