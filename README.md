# 日経平均・一目均衡表 Webダッシュボード

Streamlitで動く日経平均の一目均衡表です。日足・週足、雲、遅行スパン、時間論、値幅観測、CSV出力に対応します。

## ローカル起動

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Web公開

1. https://share.streamlit.io/ にGitHubでログイン
2. Create app → Deploy a public app from GitHub
3. Repository: `suzukimaruya9002-cmd/nikkei-ichimoku-dashboard`
4. Branch: `main` / Main file path: `app.py`
5. Deployを押す

## 注意事項

株価はYahoo Finance `^N225` から取得し15分キャッシュ。開いている画面を15分ごとに再読み込みするオプションあり。株価の場中到達時刻は日足からはわかりません。雲の未来日付は祝日未考慮の概算です。既存のChatGPT朝6時通知とは自動連携していません。データ提供元の遅延・欠損・仕様変更に注意してください。
