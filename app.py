import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

st.set_page_config(page_title="日経平均・一目均衡表",page_icon="📈",layout="wide")
st.title("日経平均 × 一目均衡表")
st.caption("分析起点：2026/06/22｜株価：Yahoo Finance (^N225)｜15分キャッシュ")

@st.cache_data(ttl=900)
def prices():
    df=yf.download("^N225",start="2025-01-01",auto_adjust=False,progress=False,multi_level_index=False)
    if df.empty:
        raise RuntimeError("株価データを取得できませんでした")
    df.index=pd.to_datetime(df.index).tz_localize(None).normalize()
    return df[["Open","High","Low","Close"]].dropna().sort_index()

def ichimoku(df):
    d=df.copy()
    d["転換線"]=(d.High.rolling(9).max()+d.Low.rolling(9).min())/2
    d["基準線"]=(d.High.rolling(26).max()+d.Low.rolling(26).min())/2
    d["先行A原値"]=(d["転換線"]+d["基準線"])/2
    d["先行B原値"]=(d.High.rolling(52).max()+d.Low.rolling(52).min())/2
    d["雲A"]=d["先行A原値"].shift(26)
    d["雲B"]=d["先行B原値"].shift(26)
    d["遅行スパン"]=d.Close.shift(-26)
    return d

with st.sidebar:
    timeframe=st.radio("時間軸",["日足","週足"])
    period=st.selectbox("表示範囲",["2026/6/22から","直近3か月","直近1か月"])
    show_lag=st.checkbox("遅行スパン",True)
    show_points=st.checkbox("重要高値・安値",True)
    auto=st.checkbox("15分ごとに画面を再読み込み",False)
    if st.button("最新データを再取得"):
        prices.clear()
        st.rerun()
if auto:
    import streamlit.components.v1 as components
    components.html('<script>setTimeout(()=>window.parent.location.reload(),900000)</script>',height=0)

try:
    daily=prices()
except Exception as exc:
    st.error(f"取得エラー：{exc}")
    st.stop()
if timeframe=="週足":
    base=daily.resample("W-FRI").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
else:
    base=daily
d=ichimoku(base)
last=d.iloc[-1]
previous=d.iloc[-2]
end=d.index[-1]
start=pd.Timestamp("2026-06-22") if period=="2026/6/22から" else end-pd.Timedelta(days=93 if period=="直近3か月" else 32)
v=d.loc[d.index>=start]
if v.empty:
    st.warning("選択期間のデータがありません")
    st.stop()
m=st.columns(4)
m[0].metric("終値",f"{last.Close:,.2f} 円",f"{last.Close-previous.Close:+,.2f} 円")
m[1].metric("転換線",f"{last['転換線']:,.2f}")
m[2].metric("基準線",f"{last['基準線']:,.2f}")
m[3].metric("最終データ日",end.strftime("%Y/%m/%d"))

fig=go.Figure()
fig.add_trace(go.Candlestick(x=v.index,open=v.Open,high=v.High,low=v.Low,close=v.Close,name="日経平均",increasing_line_color="#22c55e",decreasing_line_color="#ef4444"))
for name,color in [("転換線","#f59e0b"),("基準線","#60a5fa")]:
    fig.add_trace(go.Scatter(x=v.index,y=v[name],name=name,line=dict(color=color,width=2)))
if timeframe=="日足":
    future=pd.bdate_range(d.index[-1]+pd.offsets.BDay(1),periods=26)
else:
    future=pd.date_range(d.index[-1]+pd.Timedelta(days=7),periods=26,freq="W-FRI")
cloud_dates=d.index.append(future)
a=pd.Series(float("nan"),index=cloud_dates)
b=a.copy()
a.loc[d.index]=d["雲A"]
b.loc[d.index]=d["雲B"]
a.loc[future]=d["先行A原値"].tail(26).to_numpy()
b.loc[future]=d["先行B原値"].tail(26).to_numpy()
mask=cloud_dates>=v.index[0]
cx=cloud_dates[mask]
fig.add_trace(go.Scatter(x=cx,y=a.loc[cx],name="先行スパンA",line=dict(color="#22c55e",width=1)))
fig.add_trace(go.Scatter(x=cx,y=b.loc[cx],name="先行スパンB",line=dict(color="#f87171",width=1),fill="tonexty",fillcolor="rgba(34,197,94,.13)"))
if show_lag:
    fig.add_trace(go.Scatter(x=v.index,y=v["遅行スパン"],name="遅行スパン",line=dict(color="#a78bfa",dash="dot")))
turns=[]
for i in range(5,len(v)-5):
    if v.High.iloc[i]==v.High.iloc[i-5:i+6].max():
        turns.append((v.index[i],float(v.High.iloc[i]),"高値"))
    if v.Low.iloc[i]==v.Low.iloc[i-5:i+6].min():
        turns.append((v.index[i],float(v.Low.iloc[i]),"安値"))
turns.sort(key=lambda p:p[0])
if show_points:
    for dt,price,kind in turns[-12:]:
        fig.add_annotation(x=dt,y=price,text=f"{dt:%m/%d} {kind}<br>{price:,.0f}",showarrow=True,ay=-36 if kind=="高値" else 36,font=dict(size=10))
fig.update_layout(template="plotly_dark",height=650,hovermode="x unified",xaxis_rangeslider_visible=False,legend=dict(orientation="h"),margin=dict(l=5,r=5,t=25,b=5),xaxis=dict(range=[v.index[0],future[-1]]),yaxis_title="円")
st.plotly_chart(fig,use_container_width=True)
st.caption("雲は26本先、遅行スパンは26本前に描画。将来の日付は日本の市場休場日を考慮していない概算です。")

st.subheader("一目均衡表の判定")
top=max(last["雲A"],last["雲B"])
bottom=min(last["雲A"],last["雲B"])
above=last.Close>top
below=last.Close<bottom
cross=last["転換線"]>last["基準線"]
lag=len(d)>26 and last.Close>d.Close.iloc[-27]
state="三役好転" if above and cross and lag else "三役逆転" if below and not cross and not lag else "混在"
st.write(f"**{state}**｜株価：{'雲上' if above else '雲下' if below else '雲内'}｜転換線：{'基準線より上' if cross else '基準線以下'}｜遅行スパン：{'強気' if lag else '弱気'}")
st.caption("遅行スパンの強弱は26本前の終値との比較による簡易判定です。")
left,right=st.columns(2)
with left:
    st.subheader("重要価格・到達日")
    q=v.tail(80)
    rows=[{"区分":"期間高値","価格":f"{q.High.max():,.2f}","日付":q.High.idxmax().strftime("%Y/%m/%d")},{"区分":"期間安値","価格":f"{q.Low.min():,.2f}","日付":q.Low.idxmin().strftime("%Y/%m/%d")},{"区分":"終値","価格":f"{last.Close:,.2f}","日付":end.strftime("%Y/%m/%d")}]
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    st.caption("日足・週足では高安値に到達した場中時刻は特定できません。")
with right:
    st.subheader("時間論")
    if turns:
        dt,price,kind=turns[-1]
        origin=d.index.get_loc(dt)
        st.write(f"起点：{dt:%Y/%m/%d} {kind} {price:,.2f}円")
        st.metric("起点からの本数（起点含む）",len(d)-origin)
        st.dataframe(pd.DataFrame([{"基本数値":n,"到達日":d.index[origin+n-1].strftime("%Y/%m/%d") if origin+n-1<len(d) else "未到達"} for n in (9,17,26,33,42,65,76,129)]),hide_index=True,use_container_width=True)
    else:
        st.info("確定転換点がまだありません")
st.subheader("値幅観測（下落波動 A→B→C）")
c1,c2,c3=st.columns(3)
A=c1.number_input("A：高値",min_value=0.0,value=float(v.High.max()))
B=c2.number_input("B：安値",min_value=0.0,value=float(v.Low.min()))
C=c3.number_input("C：戻り高値",min_value=0.0,value=float(last.Close))
if A<=B or C<=B:
    st.warning("下落波動では通常A>B、C>Bの点を指定します")
targets={"N":C-(A-B),"E":B-(A-B),"V":B-(C-B),"NT":C-(A-C)}
st.dataframe(pd.DataFrame([{"観測値":k,"価格（円）":f"{value:,.2f}"} for k,value in targets.items()]),hide_index=True,use_container_width=True)
st.download_button("CSVを保存",d.loc[d.index>=pd.Timestamp("2026-06-22")].to_csv(index_label="Date").encode("utf-8-sig"),file_name="nikkei_ichimoku.csv",mime="text/csv")
st.caption("株価データには遅延・欠損の可能性があります。投資判断はご自身で行ってください。")
