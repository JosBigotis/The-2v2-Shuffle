import streamlit as st
import json
import os
import math
import datetime
import copy
import random
import string
import time

# --- Room Management Backend ---
ROOMS_DIR = "rooms"
os.makedirs(ROOMS_DIR, exist_ok=True)

def cleanup_old_rooms():
    """Deletes room files older than 24 hours."""
    now = time.time()
    for filename in os.listdir(ROOMS_DIR):
        filepath = os.path.join(ROOMS_DIR, filename)
        if now - os.path.getmtime(filepath) > 86400: 
            try:
                os.remove(filepath)
            except:
                pass

def save_room():
    """Saves the current organizer's session state to their room's JSON file."""
    if st.session_state.get('is_organizer') and st.session_state.get('room_code'):
        keys_to_save = ['game_type', 'total_players', 'players', 'round_num', 'current_matchups', 
                        'benched_players', 'history', 'completed_rounds', 'undo_scores']
        data = {k: st.session_state[k] for k in keys_to_save if k in st.session_state}
        with open(os.path.join(ROOMS_DIR, f"{st.session_state.room_code}.json"), "w") as f:
            json.dump(data, f)

def load_room(room_code):
    """Loads a room's JSON data if it exists."""
    filepath = os.path.join(ROOMS_DIR, f"{room_code.upper()}.json")
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return None

def generate_room_code():
    """Generates a random 6-letter uppercase code."""
    return "".join(random.choices(string.ascii_uppercase, k=6))

# --- Helper Function ---
def get_ranked_standings(standings_list):
    ranked_list = []
    rank, actual_position, prev_stats = 1, 1, None
    for item in standings_list:
        current_stats = (item[0], item[1], item[2])
        if prev_stats is not None and current_stats != prev_stats:
            rank = actual_position
        ranked_list.append((rank, item))
        prev_stats = current_stats
        actual_position += 1
    return ranked_list

# --- Initialize Session State & URL Routing ---
cleanup_old_rooms()

if 'stage' not in st.session_state:
    # Check if a user scanned a QR code with a room parameter in the URL
    if "room" in st.query_params:
        scanned_code = st.query_params["room"].upper()
        if load_room(scanned_code):
            st.session_state.room_code = scanned_code
            st.session_state.is_organizer = False
            st.session_state.stage = 'viewing'
        else:
            st.session_state.stage = 'landing'
            st.error("That room has expired or does not exist.")
    else:
        st.session_state.stage = 'landing'

# ==========================================
# STAGE 0: LANDING PAGE (Host or Join)
# ==========================================
if st.session_state.stage == 'landing':
    st.header("🏆 Tournament Manager")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Host a Game")
        if st.button("Create New Room", type="primary", use_container_width=True):
            st.session_state.room_code = generate_room_code()
            st.session_state.is_organizer = True
            st.session_state.stage = 'config'
            st.rerun()
            
        st.divider()
        st.write("**Accidentally closed the page?**")
        resume_code = st.text_input("Enter your Room Code to resume hosting:", max_chars=6).upper()
        if st.button("Resume as Host", use_container_width=True):
            data = load_room(resume_code)
            if data:
                st.session_state.update(data)
                st.session_state.room_code = resume_code
                st.session_state.is_organizer = True
                st.session_state.stage = 'playing'
                st.rerun()
            else:
                st.error("Room not found.")

    with col2:
        st.subheader("Join a Game")
        join_code = st.text_input("Enter 6-letter Room Code to view live standings:", max_chars=6).upper()
        if st.button("Join as Viewer", type="secondary", use_container_width=True):
            if load_room(join_code):
                st.session_state.room_code = join_code
                st.session_state.is_organizer = False
                st.session_state.stage = 'viewing'
                st.query_params["room"] = join_code # Updates their URL
                st.rerun()
            else:
                st.error("Room not found.")

# ==========================================
# STAGE 1 & 2: CONFIGURATION & SETUP (Organizer Only)
# ==========================================
elif st.session_state.stage == 'config':
    st.header(f"Setup Room: {st.session_state.room_code}")
    game_type = st.selectbox("Choose Game Type:", ["babyfoot", "padel", "padel_mixed"])
    total_players = st.number_input("Total Number of Players:", min_value=4, step=1, value=4)
    
    if st.button("Next: Enter Players"):
        st.session_state.game_type = game_type
        st.session_state.total_players = total_players
        st.session_state.players = {}
        st.session_state.round_num = 1
        st.session_state.current_matchups = []
        st.session_state.benched_players = []
        st.session_state.history = []
        st.session_state.completed_rounds = []
        st.session_state.undo_scores = []
        st.session_state.stage = 'setup_players'
        st.rerun()

elif st.session_state.stage == 'setup_players':
    st.header(f"Player Roster (Room: {st.session_state.room_code})")
    
    with st.form("player_setup_form"):
        player_inputs = []
        for i in range(st.session_state.total_players):
            col1, col2 = st.columns([2, 1])
            name = col1.text_input(f"Player {i + 1}", key=f"name_{i}")
            gender = col2.selectbox(f"Gender", ['m', 'f'], key=f"gender_{i}") if st.session_state.game_type == 'padel_mixed' else None
            player_inputs.append((name, gender))
            
        if st.form_submit_button("Start Tournament"):
            names = [p[0].strip() for p in player_inputs if p[0].strip()]
            if len(names) != st.session_state.total_players or len(names) != len(set(names)):
                st.error("Please enter unique names for all players.")
            else:
                for name, gender in player_inputs:
                    st.session_state.players[name.strip()] = {'played': 0, 'tourney_pts': 0, 'diff': 0, 'points_won': 0, 'gender': gender}
                st.session_state.stage = 'playing'
                save_room() # Initial save
                st.rerun()

# ==========================================
# STAGE 3: TOURNAMENT LOOP (Organizer Only)
# ==========================================
elif st.session_state.stage == 'playing' and st.session_state.is_organizer:
    st.header(f"Room: {st.session_state.room_code} | Round {st.session_state.round_num}")
    
    matches_per_round = st.session_state.total_players // 4
    active_players_per_round = matches_per_round * 4
    
    if not st.session_state.current_matchups:
        sortable_list = [(stats['played'], -stats['tourney_pts'], -stats['diff'], -stats['points_won'], p) 
                         for p, stats in st.session_state.players.items()]
        sortable_list.sort()
        sorted_names = [item[4] for item in sortable_list]
        
        active_players = sorted_names[:active_players_per_round]
        st.session_state.benched_players = sorted_names[active_players_per_round:]
        
        round_matches = []
        for i in range(matches_per_round):
            chunk = active_players[i * 4 : (i + 1) * 4]
            if st.session_state.game_type == 'padel_mixed':
                pairings = [((chunk[0], chunk[3]), (chunk[1], chunk[2])), ((chunk[0], chunk[2]), (chunk[1], chunk[3])), ((chunk[0], chunk[1]), (chunk[2], chunk[3]))]
                best_pairing, max_mixed = pairings[0], -1
                for t_a, t_b in pairings:
                    m_a = 1 if st.session_state.players[t_a[0]]['gender'] != st.session_state.players[t_a[1]]['gender'] else 0
                    m_b = 1 if st.session_state.players[t_b[0]]['gender'] != st.session_state.players[t_b[1]]['gender'] else 0
                    if (m_a + m_b) > max_mixed:
                        max_mixed, best_pairing = (m_a + m_b), (t_a, t_b)
                team_a, team_b = best_pairing
            else:
                team_a, team_b = (chunk[0], chunk[3]), (chunk[1], chunk[2])
            round_matches.append((team_a, team_b))
        st.session_state.current_matchups = round_matches
        save_room()

    if st.session_state.benched_players:
        st.warning(f"🪑 **Benched:** {', '.join(st.session_state.benched_players)}")
        
    with st.form("score_form", clear_on_submit=True):
        scores_input = []
        for i, (team_a, team_b) in enumerate(st.session_state.current_matchups):
            st.subheader(f"{team_a[0]} & {team_a[1]}  vs  {team_b[0]} & {team_b[1]}")
            def_a, def_b = 0, 0
            if 'undo_scores' in st.session_state and st.session_state.undo_scores and len(st.session_state.undo_scores) > i:
                _, _, def_a, def_b = st.session_state.undo_scores[i]
                
            col1, col2 = st.columns(2)
            score_a = col1.number_input(f"Score Team A", min_value=0, step=1, value=def_a, key=f"sa_{i}")
            score_b = col2.number_input(f"Score Team B", min_value=0, step=1, value=def_b, key=f"sb_{i}")
            scores_input.append((team_a, team_b, score_a, score_b))
            
        if st.form_submit_button("Submit Scores & Generate Next Round"):
            validation_passed = True
            if st.session_state.game_type == 'babyfoot':
                for _, _, sa, sb in scores_input:
                    if not (0 <= sa <= 10 and 0 <= sb <= 10) or not (sa == 10 or sb == 10) or sa == sb:
                        st.error("Invalid babyfoot score. Must end in 10 and no ties.")
                        validation_passed = False
            
            if validation_passed:
                st.session_state.history.append({
                    'round_num': st.session_state.round_num,
                    'players': copy.deepcopy(st.session_state.players),
                    'matchups': st.session_state.current_matchups,
                    'benched': st.session_state.benched_players
                })
                st.session_state.completed_rounds.append({'round_num': st.session_state.round_num, 'results': scores_input})
                st.session_state.undo_scores = []
                
                for team_a, team_b, score_a, score_b in scores_input:
                    for p in team_a:
                        st.session_state.players[p]['played'] += 1
                        st.session_state.players[p]['points_won'] += score_a
                        st.session_state.players[p]['diff'] += (score_a - score_b)
                    for p in team_b:
                        st.session_state.players[p]['played'] += 1
                        st.session_state.players[p]['points_won'] += score_b
                        st.session_state.players[p]['diff'] += (score_b - score_a)
                        
                    if st.session_state.game_type == 'babyfoot':
                        pts_a, pts_b = (2 if score_b >= 6 else 3, 1 if score_b >= 6 else 0) if score_a == 10 else (1 if score_a >= 6 else 0, 2 if score_a >= 6 else 3)
                    else:
                        pts_a, pts_b = (1, 0) if score_a > score_b else (0, 1) if score_b > score_a else (0, 0)
                            
                    for p in team_a: st.session_state.players[p]['tourney_pts'] += pts_a
                    for p in team_b: st.session_state.players[p]['tourney_pts'] += pts_b
                
                st.session_state.round_num += 1
                st.session_state.current_matchups = []
                save_room()
                st.rerun()

    if st.session_state.round_num > 1 and st.session_state.history:
        if st.button("⚠️ Undo Last Round"):
            last_state = st.session_state.history.pop()
            st.session_state.undo_scores = st.session_state.completed_rounds.pop()['results']
            st.session_state.round_num = last_state['round_num']
            st.session_state.players = last_state['players']
            st.session_state.current_matchups = last_state['matchups']
            st.session_state.benched_players = last_state['benched']
            save_room()
            st.rerun()

    st.divider()
    
    # --- Live Standings ---
    st.subheader("Current Standings")
    standings = [(-s['tourney_pts'], -s['diff'], -s['points_won'], s['played'], p) for p, s in st.session_state.players.items()]
    standings.sort()
    table_md = "| Rank | Player | Pts | Diff | Won | Matches |\n|---|---|---|---|---|---|\n"
    for rank, item in get_ranked_standings(standings):
        table_md += f"| {rank} | {item[4]} | {-item[0]} | {-item[1]} | {-item[2]} | {item[3]} |\n"
    st.markdown(table_md)
    
    # --- Match History & QR Code ---
    if st.session_state.completed_rounds:
        with st.expander("📜 Show Previous Match History"):
            for round_data in reversed(st.session_state.completed_rounds):
                st.markdown(f"**Round {round_data['round_num']}**")
                for team_a, team_b, score_a, score_b in round_data['results']:
                    st.text(f"  {team_a[0]} & {team_a[1]} ({score_a}) vs ({score_b}) {team_b[0]} & {team_b[1]}")

    st.write(f"📲 **Share live access. Code:** `{st.session_state.room_code}`")
    app_url = f"2v2-shuffle.streamlit.app/?room={st.session_state.room_code}" 
    st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={app_url}", width=150)

# ==========================================
# STAGE 4: VIEWER MODE
# ==========================================
elif st.session_state.stage == 'viewing':
    room_data = load_room(st.session_state.room_code)
    if not room_data:
        st.error("This room has expired or the organizer closed it.")
        if st.button("Return to Home"):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()
    else:
        st.header(f"Live View: Room {st.session_state.room_code}")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**Round:** {room_data['round_num']} | **Game:** {room_data['game_type'].replace('_', ' ').title()}")
        with col2:
            if st.button("🔄 Refresh Data"):
                st.rerun()
                
        if room_data['current_matchups']:
            st.subheader("Currently Playing")
            for team_a, team_b in room_data['current_matchups']:
                st.info(f"{team_a[0]} & {team_a[1]}  vs  {team_b[0]} & {team_b[1]}")
                
        st.subheader("Standings")
        standings = [(-s['tourney_pts'], -s['diff'], -s['points_won'], s['played'], p) for p, s in room_data['players'].items()]
        standings.sort()
        table_md = "| Rank | Player | Pts | Diff | Won | Matches |\n|---|---|---|---|---|---|\n"
        for rank, item in get_ranked_standings(standings):
            table_md += f"| {rank} | {item[4]} | {-item[0]} | {-item[1]} | {-item[2]} | {item[3]} |\n"
        st.markdown(table_md)
        
        if room_data['completed_rounds']:
            with st.expander("📜 Match History"):
                for round_data in reversed(room_data['completed_rounds']):
                    st.markdown(f"**Round {round_data['round_num']}**")
                    for team_a, team_b, score_a, score_b in round_data['results']:
                        st.text(f"  {team_a[0]} & {team_a[1]} ({score_a}) vs ({score_b}) {team_b[0]} & {team_b[1]}")

        st.divider()
        if st.button("Leave Room"):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()
