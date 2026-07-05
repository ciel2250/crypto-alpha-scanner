import streamlit as st
import ccxt
import pandas as pd
import streamlit.components.v1 as components

# -----------------------------------------------------------------------------
# 1. 웹사이트 페이지 UI 및 메타데이터 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="ALPHA SCANNER PRO", page_icon="⚡", layout="wide")
st.title("⚡ ALPHA SCANNER PRO : 트레이딩뷰 차트 연동 유동성 공백 추적기")
st.markdown("---")

# -----------------------------------------------------------------------------
# [핵심 알파] 2. 세션 상태(Session State) 메모리 락업
# -----------------------------------------------------------------------------
if 'scanned' not in st.session_state:
    st.session_state['scanned'] = False
if 'scan_data' not in st.session_state:
    st.session_state['scan_data'] = []

# -----------------------------------------------------------------------------
# 3. 사이드바 (모든 위젯에 고유 key 부여 -> 좌표 증발 원천 차단)
# -----------------------------------------------------------------------------
st.sidebar.header("🛠️ 스캐너 설정 (Controls)")
scan_limit = st.sidebar.slider("스캔 종목 수 (거래량 상위 기준)", min_value=10, max_value=100, value=30, step=10, key="slider_limit")
timeframe = st.sidebar.selectbox("타임프레임 선택", ["15m", "30m", "1h", "4h", "1d"], index=0, key="select_tf")
min_gap_percent = st.sidebar.number_input("최소 갭 크기 필터 (%)", min_value=0.05, max_value=5.00, value=0.10, step=0.05, key="input_gap")
st.sidebar.markdown("---")
start_button = st.sidebar.button("🚀 실시간 스캔 시작", use_container_width=True, key="btn_start")

# -----------------------------------------------------------------------------
# 4. 트레이딩뷰 HTML/JS 차트 렌더러
# -----------------------------------------------------------------------------
def render_tradingview_chart(symbol):
    clean_symbol = symbol.split("/")[0] + "USDT.P"
    tv_widget_id = f"BINANCE:{clean_symbol}"
    
    tv_html = f"""
    <div class="tradingview-widget-container" style="height:550px;width:100%">
      <div id="tradingview_chart" style="height:500px;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "width": "100%",
        "height": 500,
        "symbol": "{tv_widget_id}",
        "interval": "60",
        "timezone": "Asia/Seoul",
        "theme": "dark",
        "style": "1",
        "locale": "kr",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "container_id": "tradingview_chart"
      }}
      );
      </script>
    </div>
    """
    components.html(tv_html, height=520)

# -----------------------------------------------------------------------------
# 5. 바이낸스 통신 및 퀀트 연산 엔진
# -----------------------------------------------------------------------------
@st.cache_resource
def get_exchange():
    return ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

def run_fvg_scanner(limit, tf, gap_threshold):
    binance = get_exchange()
    markets = binance.fetch_markets()
    active_symbols = [m['symbol'] for m in markets if m['active'] and m['linear'] and m['quote'] == 'USDT']
    target_symbols = active_symbols[:limit]
    
    results = []
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    for i, symbol in enumerate(target_symbols):
        progress_text.text(f"⏳ 바이낸스 실시간 연동 및 알파 연산 중... [{i+1}/{limit}] : {symbol}")
        progress_bar.progress((i + 1) / limit)
        try:
            ohlcv = binance.fetch_ohlcv(symbol, timeframe=tf, limit=10)
            df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            idx = len(df) - 2
            c1_h, c1_l = df.loc[idx-2, 'high'], df.loc[idx-2, 'low']
            c3_h, c3_l = df.loc[idx, 'high'], df.loc[idx, 'low']
            
            # 상승 FVG
            if c1_h < c3_l:
                gap_pct = ((c3_l - c1_h) / c1_h) * 100
                if gap_pct >= gap_threshold:
                    results.append({"종목명": symbol, "포지션": "🔥 상승 FVG (Long)", "진입 대기 구간 (USDT)": f"{c1_h:.4f} ~ {c3_l:.4f}", "갭 크기 (%)": f"+{gap_pct:.2f}%", "상태": "매수 불균형"})
            # 하락 FVG
            elif c1_l > c3_h:
                gap_pct = ((c1_l - c3_h) / c3_h) * 100
                if gap_pct >= gap_threshold:
                    results.append({"종목명": symbol, "포지션": "❄️ 하락 FVG (Short)", "진입 대기 구간 (USDT)": f"{c3_h:.4f} ~ {c1_l:.4f}", "갭 크기 (%)": f"-{gap_pct:.2f}%", "상태": "매도 불균형"})
        except Exception:
            continue
            
    progress_text.empty()
    progress_bar.empty()
    return results

# -----------------------------------------------------------------------------
# [핵심 통제] 6. 스캔 트리거 및 데이터 세션 락업
# -----------------------------------------------------------------------------
if start_button:
    with st.spinner("⚡ 바이낸스 선물 데이터베이스에서 알파 타점을 뜯어오는 중입니다..."):
        st.session_state['scan_data'] = run_fvg_scanner(scan_limit, timeframe, min_gap_percent)
        st.session_state['scanned'] = True

# -----------------------------------------------------------------------------
# 7. 프론트엔드 출력 (피듀셜 마크 key 바인딩)
# -----------------------------------------------------------------------------
if st.session_state['scanned']:
    scan_data = st.session_state['scan_data']
    st.subheader(f"📊 스캔 결과 리포트 (상위 {scan_limit}개 종목 | {timeframe} 봉)")
    
    if len(scan_data) > 0:
        st.success(f"총 {len(scan_data)}개의 유효한 FVG 타점을 포착했습니다!")
        st.dataframe(pd.DataFrame(scan_data), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("📈 실시간 타점 종목 차트 분석 (TradingView Integration)")
        
        found_symbols = [item["종목명"] for item in scan_data]
        
        # [최대 치트키] 고유 key="chart_ticker_selector" 각인!
        # 이제 차트를 100번 교체해도 스트림릿 엔진이 절대 좌표(세션)를 놓치지 않습니다.
        selected_symbol = st.selectbox(
            "👇 차트로 확인할 타점 종목을 선택하세요:",
            found_symbols,
            key="chart_ticker_selector"
        )
        
        if selected_symbol:
            render_tradingview_chart(selected_symbol)
            
    else:
        st.warning(f"💡 조건(상위 {scan_limit}개 종목, {timeframe} 봉, 최소 갭 {min_gap_percent}%)에 부합하는 FVG 타점이 없습니다.")
else:
    st.info("👈 좌측 사이드바에서 원하는 조건을 설정한 뒤 **'🚀 실시간 스캔 시작'** 버튼을 클릭해 주세요.")
