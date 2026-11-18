import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

st.set_page_config(page_title="株価｜一目均衡表", page_icon="📈", layout="wide")
st.markdown("""<style>
html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"] {background-color:#050505!important;color:#f4f4f4!important}
[data-testid="stAppViewContainer"] {background: #050505!important}
[data-testid="stMetric"] {background:#0b0b0b;border:1px solid #292b35;border-radius:7px;padding:7px 9px}
[data-testid="stMetricValue"] {color:#f5f5f5!important}
[data-testid="stMetricDelta"] {color:#f5c400!important}
[data-testid="stExpander"] {background:#0b0b0b;border-color:#292b35!important}
[data-testid="stCaptionContainer"] {color:#a5a6b3!important}
button[kind="primary"] {background:#f4c400!important;color:#080808!important}

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
st.title("株価｜一目均衡表")
st.caption("日経平均・東証個別銘柄 / 日足・週足・分足 / Yahoo Finance提供（遅延あり）")
ticker_options={"日経平均":"^N225","トヨタ自動車（7203）":"7203.T","ソフトバンクグループ（9984）":"9984.T","任意の東証銘柄":"custom"}
choice=st.selectbox("分析対象",list(ticker_options),key="ticker_choice")
custom_code=st.text_input("証券コード（4桁）",value="7203",max_chars=4,key="custom_ticker") if choice=="任意の東証銘柄" else ""
if choice=="任意の東証銘柄":
    if not (custom_code.isascii() and custom_code.isdigit() and len(custom_code)==4):
        st.error("東証の4桁の証券コードを入力してください。")
        st.stop()
    ticker=f"{custom_code}.T"
    ticker_label=f"東証 {custom_code}"
else:
    ticker=ticker_options[choice]
    ticker_label=choice
st.caption(f"分析対象：{ticker_label}｜Yahoo Financeシンボル：{ticker}")

@st.cache_data(ttl=900,show_spinner=False)
def load_prices(symbol):
    d=yf.download(symbol,start="2024-01-01",auto_adjust=False,progress=False,multi_level_index=False)
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
    daily=load_prices(ticker)
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
        show_tenkan=st.checkbox("転換線（黄）",False)
        show_kijun=st.checkbox("基準線（水色）",True)
        show_cloud=st.checkbox("雲（緑・赤）",False)
        show_chikou=st.checkbox("遅行スパン（紫）",False)
        show_markers=st.checkbox("直近の高値・安値マーカー",False)
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
    fig.add_trace(go.Scatter(x=cx,y=a.loc[cx],name="先行A",line=dict(color="rgba(45,181,106,.58)",width=1.0),
        hovertemplate="%{x|%Y/%m/%d}<br>先行A %{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=cx,y=b.loc[cx],name="先行B",line=dict(color="rgba(241,108,105,.58)",width=1.0),
        fill="tonexty",fillcolor="rgba(43,170,98,.045)",
        hovertemplate="%{x|%Y/%m/%d}<br>先行B %{y:,.0f}<extra></extra>"))
if show_tenkan:
    fig.add_trace(go.Scatter(x=v.index,y=v.tenkan,name="転換線",line=dict(color="rgba(249,208,0,.82)",width=1.45)))
if show_kijun:
    fig.add_trace(go.Scatter(x=v.index,y=v.kijun,name="基準線",line=dict(color="rgba(36,198,207,.82)",width=1.45)))
if show_chikou:
    # 終値を26本前の日付にプロット（最新26本を含む）
    chikou_dates=d.index[:-26]
    chikou_values=d.Close.iloc[26:].to_numpy()
    lag=pd.Series(chikou_values,index=chikou_dates)
    lag=lag.loc[lag.index>=v.index[0]]
    fig.add_trace(go.Scatter(x=lag.index,y=lag,name="遅行スパン",line=dict(color="#ae86f5",width=1.6,dash="dot")))

high_date=v.High.idxmax()
low_date=v.Low.idxmin()
if show_markers:
    fig.add_trace(go.Scatter(x=[high_date,low_date],y=[v.High.max(),v.Low.min()],
        mode="markers",name="高値・安値",marker=dict(size=9,color=["#f9d000","#24c6cf"],symbol=["triangle-down","triangle-up"]),
        text=[f"高値 {v.High.max():,.0f}円",f"安値 {v.Low.min():,.0f}円"],
        hovertemplate="%{x|%Y/%m/%d}<br>%{text}<extra></extra>"))

fig.add_hline(y=float(last.Close),line_color="#f5c400",line_width=1.3,line_dash="dash",opacity=.9,
    annotation_text=f"{last.Close:,.0f}",annotation_position="right",annotation_font_color="#f5c400")

# ローソク足は最後に描画し、雲や線の手前に表示する。
fig.add_trace(go.Candlestick(x=v.index,open=v.Open,high=v.High,low=v.Low,close=v.Close,
    name="ローソク足",increasing_line_color="#00d34f",decreasing_line_color="#ff3b20",line=dict(width=1.3),
    increasing_fillcolor="#00d34f",decreasing_fillcolor="#ff3b20"))

fig.update_layout(
    template="plotly_dark",height=510,margin=dict(l=0,r=4,t=14,b=5),
    xaxis_rangeslider_visible=False,hovermode="x unified",
    paper_bgcolor="#050505",plot_bgcolor="#050505",font=dict(color="#e5e5e5",size=12),
    legend=dict(orientation="h",y=-.18,x=0,font=dict(size=10)),
    xaxis=dict(showgrid=True,gridcolor="rgba(145,145,160,.30)",tickformat="%m/%d",nticks=5,zeroline=False),
    yaxis=dict(title=None,side="right",tickformat=",.0f",nticks=6,showgrid=True,
               gridcolor="rgba(145,145,160,.30)",zeroline=False),
    dragmode="pan")
st.plotly_chart(fig,use_container_width=True,config={"displaylogo":False,"scrollZoom":False,
    "modeBarButtonsToRemove":["lasso2d","select2d","autoScale2d"]})
st.caption("ローソク足を最前面に表示。雲・転換線・遅行スパンは「表示する線・追加設定」で切り替えられます。黄色の破線＝最新終値。")

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
        file_name=f"{ticker.replace(chr(94),'index_').replace('.','_')}_ichimoku.csv",mime="text/csv")
st.caption("免責：投資判断の参考資料です。場中の高安値到達時刻は日足データからは特定できません。")


st.divider()
st.subheader("分単位の時間・価格分析")
st.caption("日足・週足の一目均衡表とは別に、場中の価格到達時刻を調べます。時刻は日本時間（JST）です。")
intraday_interval=st.segmented_control("分足",["1分足","5分足","15分足"],default="5分足")
period_options={"1分足":["直近1日","直近5日"],"5分足":["直近1日","直近5日","直近1か月"],"15分足":["直近1日","直近5日","直近1か月"]}
intraday_period=st.selectbox("分足の取得期間",period_options[intraday_interval],key="intraday_period")
interval_code={"1分足":"1m","5分足":"5m","15分足":"15m"}[intraday_interval]
period_code={"直近1日":"1d","直近5日":"5d","直近1か月":"1mo"}[intraday_period]

@st.cache_data(ttl=55,show_spinner=False)
def load_intraday(symbol,interval,period):
    z=yf.download(symbol,period=period,interval=interval,auto_adjust=False,progress=False,multi_level_index=False,prepost=False)
    if z is None or z.empty:
        return pd.DataFrame()
    z=z[["Open","High","Low","Close"]].dropna().sort_index()
    idx=pd.to_datetime(z.index)
    if idx.tz is None:
        idx=idx.tz_localize("Asia/Tokyo")
    else:
        idx=idx.tz_convert("Asia/Tokyo")
    z.index=idx
    return z

from datetime import datetime, time as clock_time, timedelta
from zoneinfo import ZoneInfo

st.subheader("価格・期限の自動判定")
st.caption("例：日経平均が当日11:00までに59,200円を上抜ける。判定は選択銘柄の1分足を使用します。")
rule_price=st.number_input("突破価格（円）",min_value=0.01,value=59200.0 if ticker=="^N225" else round(float(daily.Close.iloc[-1]),2),step=10.0,format="%.2f",key="rule_price")
rule_deadline=st.time_input("判定期限（日本時間）",value=clock_time(11,0),step=60,key="rule_deadline")
rule_direction=st.radio("判定条件",["上抜け（高値が指定価格を超える）","下抜け（安値が指定価格を下回る）"],horizontal=True,key="rule_direction")
st.caption("判定対象は最新の取引日。期限ちょうどに始まる足は対象外です。場中データには遅延・欠損の可能性があります。")

st.toggle("分足チャートを1分ごとに自動更新",value=True,key="intraday_autorefresh",help="画面を開いている間、60秒ごとに分足の取得・チャート表示を更新します。データ配信の遅延は解消しません。")
if st.button("分足データを今すぐ再取得",key="force_intraday_refresh"):
    load_intraday.clear()

@st.fragment(run_every="60s" if st.session_state.intraday_autorefresh else None)
def render_intraday_live():
    with st.spinner("分足を取得しています"):
        intraday=load_intraday(ticker,interval_code,period_code)
    # Use 1-minute data regardless of the selected chart interval.
    minute=intraday if interval_code=="1m" else load_intraday(ticker,"1m","5d")
    now_jst=datetime.now(ZoneInfo("Asia/Tokyo"))
    if minute.empty:
        st.warning("転換条件：1分足を取得できず判定不能です。")
    else:
        today=now_jst.strftime("%Y-%m-%d")
        minute_today=minute[minute.index.strftime("%Y-%m-%d")==today].sort_index()
        if minute_today.empty:
            st.info("転換条件：本日分の1分足がありません。休場日・寄り付き前・データ未配信の可能性があります。")
        else:
            deadline_dt=datetime.combine(now_jst.date(),rule_deadline,tzinfo=ZoneInfo("Asia/Tokyo"))
            eligible=minute_today[minute_today.index<deadline_dt]
            rising=rule_direction.startswith("上抜け")
            hits=eligible[eligible.High>rule_price] if rising else eligible[eligible.Low<rule_price]
            last_bar=minute_today.index[-1].to_pydatetime()
            if not hits.empty:
                first=hits.index[0]
                extreme=hits.iloc[0].High if rising else hits.iloc[0].Low
                st.success(f"条件成立：{first:%H:%M} JST開始の1分足で{'上抜け' if rising else '下抜け'}（足の{'高値' if rising else '安値'} {extreme:,.2f}円）。")
            elif now_jst<deadline_dt:
                st.info(f"判定待ち：{rule_deadline:%H:%M}までに{rule_price:,.2f}円を{'上抜け' if rising else '下抜け'}する条件は、取得済みの1分足では未確認です。")
            elif last_bar>=deadline_dt-timedelta(minutes=1) and (now_jst-last_bar).total_seconds()<1200:
                expected=pd.date_range(start=minute_today.index.min(),end=deadline_dt-timedelta(minutes=1),freq="min")
                # Missing bars may be exchange breaks; do not claim complete tick coverage.
                st.warning(f"期限到来・未達：{rule_deadline:%H:%M}までに条件成立を確認できませんでした（取得済み1分足に基づく暫定判定）。")
            else:
                st.warning("期限到来。ただし1分足が期限直前まで揃っていないため、未達と断定できません。")
            st.caption(f"判定データ最終足：{last_bar:%Y/%m/%d %H:%M} JST｜現在：{now_jst:%H:%M} JST。画面を閉じている間の通知は行いません。")
    if intraday.empty:
        st.warning("この期間の分足データは取得できませんでした。期間や足種を変更してお試しください。")
    else:
        last_intraday=intraday.iloc[-1]
        checked_at=datetime.now(ZoneInfo("Asia/Tokyo"))
        data_lag=(checked_at-intraday.index[-1].to_pydatetime()).total_seconds()/60
        st.caption(f"取得確認：{checked_at:%Y/%m/%d %H:%M:%S} JST｜データの最終足：{intraday.index[-1]:%H:%M} JST｜足の開始から約{max(0,data_lag):.0f}分")
        if data_lag>20:
            st.warning("取得した価格データが20分以上前のものです。リアルタイム価格として利用しないでください。")
        st.caption(f"最終取得足：{intraday.index[-1]:%Y/%m/%d %H:%M} JST（足の開始時刻）｜配信遅延の可能性あり")
        hidx=intraday.High.idxmax()
        lidx=intraday.Low.idxmin()
        cc1,cc2=st.columns(2)
        cc1.metric("期間高値",f"{intraday.High.max():,.2f} 円")
        cc1.caption(f"{hidx:%m/%d %H:%M} JST の足")
        cc2.metric("期間安値",f"{intraday.Low.min():,.2f} 円")
        cc2.caption(f"{lidx:%m/%d %H:%M} JST の足")

        target=st.number_input("追跡する重要価格（円）",min_value=0.0,value=round(float(last.Close),2),step=10.0,format="%.2f",key="intraday_target")
        touched=intraday[(intraday.Low<=target)&(intraday.High>=target)]
        above_target=intraday[intraday.High>=target]
        below_target=intraday[intraday.Low<=target]
        event_rows=[]
        for label,frame in [("指定価格を含む足（初回）",touched),("指定価格以上の高値（初回）",above_target),("指定価格以下の安値（初回）",below_target)]:
            if not frame.empty:
                ix=frame.index[0]
                event_rows.append({"条件":label,"日時（JST・足開始）":ix.strftime("%Y/%m/%d %H:%M"),"安値":f"{frame.iloc[0].Low:,.2f}","高値":f"{frame.iloc[0].High:,.2f}"})
        if event_rows:
            st.dataframe(pd.DataFrame(event_rows),hide_index=True,use_container_width=True)
        else:
            st.info("取得期間中に指定価格へ到達した足はありません。")

        # Plot only one selected trading session by default, eliminating large overnight/weekend gaps.
        available_days=sorted(intraday.index.strftime("%Y-%m-%d").unique(),reverse=True)
        selected_day=st.selectbox("チャート表示日",available_days,index=0,key="intraday_chart_day")
        chart_bars=intraday[intraday.index.strftime("%Y-%m-%d")==selected_day]
        st.caption(f"表示：{selected_day}｜{len(chart_bars)}本のローソク足。過去の高値・安値集計は選択した取得期間全体を対象とします。")
        show_intraday_ichimoku=st.checkbox("分足の一目均衡表（9・26・52）を表示",False)
        intraday_fig=go.Figure()
        if show_intraday_ichimoku:
            idata=calc(intraday).loc[chart_bars.index]
            intraday_fig.add_trace(go.Scatter(x=idata.index,y=idata.tenkan,name="分足転換線",line=dict(color="rgba(249,208,0,.75)",width=1.3)))
            intraday_fig.add_trace(go.Scatter(x=idata.index,y=idata.kijun,name="分足基準線",line=dict(color="rgba(36,198,207,.75)",width=1.3)))
        intraday_fig.add_trace(go.Candlestick(x=chart_bars.index,open=chart_bars.Open,high=chart_bars.High,low=chart_bars.Low,close=chart_bars.Close,
            name=f"{ticker_label}（分足）",increasing_line_color="#00d34f",decreasing_line_color="#ff3b20",
            increasing_fillcolor="#00d34f",decreasing_fillcolor="#ff3b20"))
        intraday_fig.add_hline(y=target,line_color="#f5c400",line_dash="dash",line_width=1.2)
        intraday_fig.update_layout(template="plotly_dark",height=510,margin=dict(l=0,r=8,t=8,b=10),
            paper_bgcolor="#050505",plot_bgcolor="#050505",font=dict(color="#eeeeee"),
            xaxis_rangeslider_visible=False,hovermode="x unified",
            xaxis=dict(type="category",showgrid=True,gridcolor="rgba(145,145,160,.22)",nticks=6,tickangle=0),
            yaxis=dict(side="right",tickformat=",.0f",gridcolor="rgba(145,145,160,.22)"),
            legend=dict(orientation="h",y=-.25,x=0))
        # String category positions remove non-trading time, preserving consistent candle spacing.
        intraday_fig.update_traces(x=chart_bars.index.strftime("%H:%M").tolist(),selector=dict(type="candlestick"))
        if show_intraday_ichimoku:
            intraday_fig.update_traces(x=chart_bars.index.strftime("%H:%M").tolist(),selector=dict(type="scatter"))
        intraday_fig.update_xaxes(tickmode="array",
            tickvals=chart_bars.index.strftime("%H:%M").tolist()[::max(1,len(chart_bars)//5)],
            ticktext=chart_bars.index.strftime("%H:%M").tolist()[::max(1,len(chart_bars)//5)])
        st.plotly_chart(intraday_fig,use_container_width=True,key="intraday_chart",config={"displaylogo":False,"scrollZoom":False,"modeBarButtonsToRemove":["lasso2d","select2d"]})
        st.caption("価格到達時刻は足の開始時刻です。足の中で実際に約定した秒・分までは特定できません。5分足なら最大5分、15分足なら最大15分の幅があります。")
        st.caption("指定価格を含む足はOHLCの範囲判定です。ギャップや気配・データ欠損などで実際の取引成立を保証しません。")
        st.download_button("分足CSV（JST）を保存",intraday.to_csv(index_label="JST").encode("utf-8-sig"),file_name=f"{ticker.replace(chr(94),'index_').replace('.','_')}_{interval_code}_jst.csv",mime="text/csv")

render_intraday_live()
st.caption("Yahoo Financeの直近分足を表示。GitHub Actionsによる継続保存は日経平均のみ対象で、個別銘柄はまだ保存していません。")

from pathlib import Path
archive_index = Path(__file__).parent / "data" / "daily_extrema.csv"
st.subheader("蓄積した日経平均の1分足データ")
if archive_index.exists():
    extrema = pd.read_csv(archive_index)
    if not extrema.empty:
        st.metric("保存済み営業日数", len(extrema))
        st.caption(f"保存期間：{extrema.date_jst.iloc[0]} ～ {extrema.date_jst.iloc[-1]}")
        st.dataframe(extrema.sort_values("date_jst", ascending=False), hide_index=True, use_container_width=True)
        dates = extrema.date_jst.astype(str).tolist()
        chosen = st.selectbox("保存済みの1分足を表示", list(reversed(dates)))
        file = Path(__file__).parent / "data" / "1m" / f"{chosen}.csv"
        if file.exists():
            archived = pd.read_csv(file)
            st.dataframe(archived.tail(500), hide_index=True, use_container_width=True)
            st.download_button("保存済み1分足CSVをダウンロード", file.read_bytes(), file_name=f"nikkei_1m_{chosen}.csv", mime="text/csv")
    else:
        st.info("保存データはまだありません。")
else:
    st.info("保存データはまだありません。GitHub Actionsの初回実行後に表示されます。")
st.caption("記録した高値・安値の時刻は1分足の開始時刻であり、約定の正確な秒数ではありません。")
