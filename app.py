import streamlit as st
import pandas as pd
from chess_analyzer import api
from chess_analyzer.engine import StockfishEngine
from chess_analyzer.analyzer import analyze_game

st.set_page_config(page_title="Chess Game Analyzer", page_icon="♟️", layout="wide")

st.title("♟️ Chess Game Analyzer")
st.markdown("Analyze your recent Chess.com games with Stockfish.")

with st.sidebar:
    st.header("Player Settings")
    username = st.text_input("Chess.com Username", value="")
    max_games = st.slider("Number of Games to Fetch", min_value=1, max_value=10, value=1)
    fetch_btn = st.button("Fetch Games", type="primary")

if "games" not in st.session_state:
    st.session_state.games = []

if fetch_btn and username:
    with st.spinner(f"Fetching {max_games} recent games for '{username}'..."):
        try:
            games = api.get_recent_games(username, max_games=max_games)
            if not games:
                st.warning(f"No games found for user '{username}'.")
            else:
                st.session_state.games = games
        except Exception as e:
            st.error(f"Failed to fetch games: {e}")

if st.session_state.games:
    st.subheader("Select a Game to Analyze")
    
    # Build options
    game_options = {}
    for i, g in enumerate(st.session_state.games):
        try:
            white = g.get('white', {}).get('username', 'Unknown')
            black = g.get('black', {}).get('username', 'Unknown')
            result = "White Won"
            
            # Try to get the result nicely
            w_res = g.get('white', {}).get('result', '')
            b_res = g.get('black', {}).get('result', '')
            if w_res == 'win':
                result = "White Won"
            elif b_res == 'win':
                result = "Black Won"
            else:
                result = "Draw / Other"
                
            label = f"{white} (W) vs {black} (B) - {result}"
        except Exception:
            label = f"Game {i+1}"
            
        game_options[label] = g

    selected_label = st.selectbox("Choose Game", options=list(game_options.keys()))
    
    if st.button("Run Analysis", type="primary"):
        selected_game = game_options[selected_label]
        pgn = selected_game.get('pgn')
        
        if not pgn:
            st.error("Selected game doesn't have PGN data.")
        else:
            with st.spinner("Stockfish is calculating your moves..."):
                try:
                    # Initialize the engine
                    stockfish_path = "stockfish_dir/stockfish/stockfish-windows-x86-64-avx2.exe"
                    with StockfishEngine(path=stockfish_path, depth=14) as engine:
                        analysis = analyze_game(pgn, engine=engine)
                        st.session_state.analysis = analysis
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

if "analysis" in st.session_state:
    analysis = st.session_state.analysis
    
    st.markdown("---")
    st.header("Analysis Results")
    
    # Summaries
    white_cpl = analysis.average_cpl_for("white")
    black_cpl = analysis.average_cpl_for("black")
    
    w_counts = analysis.classification_counts("white")
    b_counts = analysis.classification_counts("black")
    
    def styled_metric(label, value, color):
        return f"""
        <div style="border: 1px solid #ddd; border-radius: 8px; padding: 15px; text-align: center; margin-bottom: 10px;">
            <p style="margin: 0; font-size: 14px; font-weight: 600; color: #888;">{label}</p>
            <p style="margin: 0; font-size: 24px; font-weight: bold; color: {color};">{value}</p>
        </div>
        """
        
    st.subheader("White Statistics")
    w_col1, w_col2, w_col3, w_col4, w_col5 = st.columns(5)
    w_col1.markdown(styled_metric("Avg CPL", f"{white_cpl:.1f}", "#2e86c1"), unsafe_allow_html=True)
    w_col2.markdown(styled_metric("Best", w_counts.get("Best", 0), "#28b463"), unsafe_allow_html=True)
    w_col3.markdown(styled_metric("Inaccuracies", w_counts.get("Inaccuracy", 0), "#f1c40f"), unsafe_allow_html=True)
    w_col4.markdown(styled_metric("Mistakes", w_counts.get("Mistake", 0), "#e67e22"), unsafe_allow_html=True)
    w_col5.markdown(styled_metric("Blunders", w_counts.get("Blunder", 0), "#e74c3c"), unsafe_allow_html=True)
    
    st.subheader("Black Statistics")
    b_col1, b_col2, b_col3, b_col4, b_col5 = st.columns(5)
    b_col1.markdown(styled_metric("Avg CPL", f"{black_cpl:.1f}", "#2e86c1"), unsafe_allow_html=True)
    b_col2.markdown(styled_metric("Best", b_counts.get("Best", 0), "#28b463"), unsafe_allow_html=True)
    b_col3.markdown(styled_metric("Inaccuracies", b_counts.get("Inaccuracy", 0), "#f1c40f"), unsafe_allow_html=True)
    b_col4.markdown(styled_metric("Mistakes", b_counts.get("Mistake", 0), "#e67e22"), unsafe_allow_html=True)
    b_col5.markdown(styled_metric("Blunders", b_counts.get("Blunder", 0), "#e74c3c"), unsafe_allow_html=True)
    
    st.markdown("### Move History")
    
    data = []
    for m in analysis.moves:
        data.append({
            "Move #": m.move_number,
            "Side": m.side.title(),
            "Played": m.move_san,
            "Best Move": m.best_move_san if m.best_move_san else "",
            "Eval (cp)": m.score_after_cp,
            "CPL": m.cpl,
            "Classification": m.classification
        })
        
    df = pd.DataFrame(data)
    
    def color_classification(val):
        colors = {
            "Blunder": "color: #e74c3c; font-weight: bold;",
            "Mistake": "color: #e67e22; font-weight: bold;",
            "Inaccuracy": "color: #f1c40f; font-weight: bold;",
            "Good": "color: #3498db;",
            "Excellent": "color: #27ae60;",
            "Best": "color: #28b463; font-weight: bold;"
        }
        return colors.get(val, "")
        
    if hasattr(df.style, 'map'):
        styled_df = df.style.map(color_classification, subset=['Classification'])
    else:
        styled_df = df.style.applymap(color_classification, subset=['Classification'])
        
    st.dataframe(styled_df, use_container_width=True, height=500)
