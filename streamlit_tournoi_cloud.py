import streamlit as st
import json
import os
import copy
import random
import string
import time
import datetime
import math

# --- Room Management Backend ---
ROOMS_DIR = "rooms"
os.makedirs(ROOMS_DIR, exist_ok=True)

def cleanup_old_rooms():
    now = time.time()
    for filename in os.listdir(ROOMS_DIR):
        filepath = os.path.join(ROOMS_DIR, filename)
        if now - os.path.getmtime(filepath) > 86400: 
            try: os.remove(filepath)
            except: pass

def save_room():
    if st.session_state.get('is_organizer') and st.session_state.get('room_code'):
        keys_to_save = ['stage', 'game_type', 'total_players', 'players', 'round_num', 'current_matchups', 
                        'benched_players', 'history', 'completed_rounds', 'fanny_alert', 'roster_alert', 'tourney_id']
        data = {k: st.session_state[k] for k in keys_to_save if k in st.session_state}
        with open(os.path.join(ROOMS_DIR, f"{st.session_state.room_code}.json"), "w") as f:
            json.dump(data, f)

def load_room(room_code):
    filepath = os.path.join(ROOMS_DIR, f"{room_code.upper()}.json")
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return None

def generate_room_code():
    """Generates a random 6-letter code with a hard cap of 5000 iterations to prevent infinite loops."""
    for _ in range(5000):
        code = "".join(random.choices(string.ascii_uppercase, k=6))
        filepath = os.path.join(ROOMS_DIR, f"{code}.json")
        if not os.path.exists(filepath):
            return code
    return "ERROR1"

# --- Analytics Backend (Privacy Preserving) ---
STATS_FILE = "global_stats.json"

def init_stats():
    """Creates the master stats file if it doesn't exist yet."""
    if not os.path.exists(STATS_FILE):
        with open(STATS_FILE, "w") as f:
            json.dump({"total_rooms": 0, "room_rounds": {}}, f)

def log_room_created():
    init_stats()
    try:
        with open(STATS_FILE, "r") as f: stats = json.load(f)
        stats["total_rooms"] += 1
        tourney_id = str(stats["total_rooms"])
        stats["room_rounds"][tourney_id] = 0
        with open(STATS_FILE, "w") as f: json.dump(stats, f)
        return tourney_id
    except Exception: return "0"

def log_round_played(tourney_id, round_num):
    if not tourney_id or tourney_id == "0": return
    init_stats()
    try:
        with open(STATS_FILE, "r") as f: stats = json.load(f)
        stats["room_rounds"][str(tourney_id)] = round_num
        with open(STATS_FILE, "w") as f: json.dump(stats, f)
    except Exception: pass

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

def calculate_cycle_info(players_dict):
    active_pool = [s['played'] for p, s in players_dict.items() if not s.get('retired', False)]
    if not active_pool: return 0, 0, 0

    N = len(active_pool)
    P = (N // 4) * 4
    if P == 0: return 0, 0, 0 

    M_max = max(active_pool)
    M_min = min(active_pool)
    
    lcm_v = (P * N) // math.gcd(P, N) if P > 0 else 0
    c_rounds = lcm_v // P if P > 0 else 0
    c_matches = c_rounds * (N // 4) if P > 0 else 0

    if M_max == M_min:
        return 0, c_rounds, c_matches

    if N == P:
        return -1, c_rounds, c_matches

    S_0 = sum(M_max - m for m in active_pool)

    k = 0
    while k < 5000:
        S = S_0 + k * N
        if S % P == 0:
            R = S // P
            T = M_max + k
            if R >= (T - M_min):
                return R, c_rounds, c_matches
        k += 1
        
    return -2, c_rounds, c_matches


def render_downloads_and_podium(players, game_type, round_num, completed_rounds):
    st.subheader("🏆 Final Standings")
    standings = [(-s['tourney_pts'], -s['diff'], -s['points_won'], s['played'], f"{p} (Retired)" if s.get('retired', False) else p) for p, s in players.items()]
    standings.sort()
    ranked_standings = get_ranked_standings(standings)
    
    table_md = "| Rank | Player | Pts | Diff | Won | Matches |\n|---|---|---|---|---|---|\n"
    for rank, item in ranked_standings:
        table_md += f"| {rank} | {item[4]} | {-item[0]} | {-item[1]} | {-item[2]} | {item[3]} |\n"
    st.markdown(table_md)

    display_game = 'padel' if game_type in ('padel', 'padel_mixed') else game_type
    timestamp = datetime.datetime.now().strftime("%d-%m-%Y_%H-%M")
    
    txt_content = "=" * 56 + "\n"
    txt_content += f"{'FINAL ' + display_game.upper() + ' STANDINGS':^56}\n"
    txt_content += f"{'Total Rounds: ' + str(round_num - 1):^56}\n"
    txt_content += "=" * 56 + "\n"
    txt_content += f"| {'Rank':<4} | {'Player':<12} | {'Pts':<3} | {'Diff':<4} | {'Won':<3} | {'Matches':<7} |\n"
    txt_content += "-" * 56 + "\n"
    for rank, item in ranked_standings: 
        txt_content += f"| {rank:<4} | {str(item[4])[:12]:<12} | {-item[0]:<3} | {-item[1]:<4} | {-item[2]:<3} | {item[3]:<7} |\n"
    txt_content += "=" * 56 + "\n"

    csv_content = "Rank,Player,Pts,Diff,Won,Matches\n"
    for rank, item in ranked_standings: 
        csv_content += f"{rank},{item[4]},{-item[0]},{-item[1]},{-item[2]},{item[3]}\n"

    st.write("**Download Results:**")
    col1, col2 = st.columns(2)
    with col1: st.download_button("📄 Download .TXT", txt_content, f"{display_game}_{timestamp}.txt", "text/plain", use_container_width=True)
    with col2: st.download_button("📊 Download .CSV", csv_content, f"{display_game}_{timestamp}.csv", "text/csv", use_container_width=True)

    # --- ADVANCED POST-GAME STATS ---
    with st.expander("📈 Detailed Statistics"):
        if completed_rounds:
            
            # --- 1. Best Duo Calculation ---
            duos = {}
            for rd in completed_rounds:
                for team_a, team_b, score_a, score_b in rd['results']:
                    for team, score, opp_score in [(team_a, score_a, score_b), (team_b, score_b, score_a)]:
                        duo = tuple(sorted(team))
                        if duo not in duos:
                            duos[duo] = {'pts': 0, 'diff': 0, 'matches': 0}
                        duos[duo]['pts'] += score
                        duos[duo]['diff'] += (score - opp_score)
                        duos[duo]['matches'] += 1
            
            if duos:
                best_duo = max(duos.items(), key=lambda x: (x[1]['diff'] / x[1]['matches'], x[1]['pts']))
                duo_names, stats = best_duo
                st.success(f"🌟 **Best Duo:** {duo_names[0]} & {duo_names[1]} (+{stats['diff']} Diff across {stats['matches']} matches)")

            # --- 2. The Nemesis Calculation ---
            h2h = {}
            for rd in completed_rounds:
                for team_a, team_b, score_a, score_b in rd['results']:
                    diff_a = score_a - score_b
                    diff_b = score_b - score_a
                    for p_a in team_a:
                        if p_a not in h2h: h2h[p_a] = {}
                        for p_b in team_b:
                            h2h[p_a][p_b] = h2h[p_a].get(p_b, 0) + diff_a
                    for p_b in team_b:
                        if p_b not in h2h: h2h[p_b] = {}
                        for p_a in team_a:
                            h2h[p_b][p_a] = h2h[p_b].get(p_a, 0) + diff_b

            lowest_diff = 0
            worst_matchup = None
            for victim, opponents in h2h.items():
                for nemesis, diff in opponents.items():
                    if diff < lowest_diff:
                        lowest_diff = diff
                        worst_matchup = (nemesis, victim, diff)

            if worst_matchup:
                nemesis, victim, diff = worst_matchup
                st.error(f"😈 **Biggest Nemesis:** {nemesis} dominated {victim} (Scored {abs(diff)} more points against them across all clashes)")

            # --- 3. Line Chart Calculations ---
            players_list = list(players.keys())
            pts_raw = {p: [0] for p in players_list}
            diff_raw = {p: [0] for p in players_list}

            for rd in completed_rounds:
                for team_a, team_b, score_a, score_b in rd['results']:
                    if game_type == 'babyfoot':
                        pts_a, pts_b = (2 if score_b >= 6 else 3, 1 if score_b >= 6 else 0) if score_a == 10 else (1 if score_a >= 6 else 0, 2 if score_a >= 6 else 3)
                    else:
                        pts_a, pts_b = (1, 0) if score_a > score_b else (0, 1) if score_b > score_a else (0, 0)

                    for p in team_a:
                        pts_raw[p].append(pts_raw[p][-1] + pts_a)
                        diff_raw[p].append(diff_raw[p][-1] + (score_a - score_b))
                    for p in team_b:
                        pts_raw[p].append(pts_raw[p][-1] + pts_b)
                        diff_raw[p].append(diff_raw[p][-1] + (score_b - score_a))

            max_matches = max([len(lst) for lst in pts_raw.values()]) if pts_raw else 1

            pts_chart = {}
            diff_chart = {}
            for i, p in enumerate(players_list):
                offset = i * 0.02 
                padded_pts = pts_raw[p] + [None] * (max_matches - len(pts_raw[p]))
                padded_diff = diff_raw[p] + [None] * (max_matches - len(diff_raw[p]))

                pts_chart[p] = [(val + offset) if val is not None else None for val in padded_pts]
                diff_chart[p] = [(val + offset) if val is not None else None for val in padded_diff]

            st.write("**Tournament Points Evolution**")
            st.line_chart(pts_chart)

            st.write("**Point Differential Evolution**")
            st.line_chart(diff_chart)
        else:
            st.info("No matches played yet to generate statistics.")


# --- Initialize Session State & URL Routing ---
cleanup_old_rooms()

# --- SECRET ADMIN DASHBOARD ---
if st.query_params.get("admin") == "true":
    st.header("🔒 Admin Dashboard")
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f: stats = json.load(f)
        st.metric("Total Tournaments Hosted", stats.get("total_rooms", 0))
        st.subheader("Rounds Played per Tournament")
        st.json(stats.get("room_rounds", {}))
    else:
        st.info("No analytics data found yet.")
        
    if st.button("Exit Admin Mode"):
        st.query_params.clear()
        st.rerun()
    st.stop()

if 'stage' not in st.session_state:
    if "host" in st.query_params:
        scanned_code = st.query_params["host"].upper()
        data = load_room(scanned_code)
        if data:
            st.session_state.update(data)
            st.session_state.room_code = scanned_code
            st.session_state.is_organizer = True
        else:
            st.query_params.clear()
            st.session_state.stage = 'landing'
            
    elif "room" in st.query_params:
        scanned_code = st.query_params["room"].upper()
        if load_room(scanned_code):
            st.session_state.room_code = scanned_code
            st.session_state.is_organizer = False
            st.session_state.stage = 'viewing'
        else:
            st.query_params.clear()
            st.session_state.stage = 'landing'
            st.error("That room has expired or does not exist.")
    else:
        st.session_state.stage = 'landing'

# ==========================================
# STAGE 0: LANDING PAGE
# ==========================================
if st.session_state.stage == 'landing':
    st.header("🏆 Tournament Manager")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Host a Game")
        if st.button("Create New Room", type="primary", use_container_width=True):
            st.session_state.room_code = generate_room_code()
            st.session_state.is_organizer = True
            st.session_state.tourney_id = log_room_created()
            st.query_params["host"] = st.session_state.room_code
            st.session_state.stage = 'config'
            save_room() 
            st.rerun()

    with col2:
        st.subheader("Join a Game")
        join_code = st.text_input("Enter 6-letter Room Code to view live standings:", max_chars=6).upper()
        if st.button("Join as Viewer", type="secondary", use_container_width=True):
            if load_room(join_code):
                st.session_state.room_code = join_code
                st.session_state.is_organizer = False
                st.session_state.stage = 'viewing'
                st.query_params["room"] = join_code
                st.rerun()
            else:
                st.error("Room not found.")
                
    st.divider()
    st.write("**Accidentally closed the page?**")
    
    col3, col4 = st.columns(2)
    with col3:
        resume_code = st.text_input("Enter your Room Code to resume hosting:", max_chars=6).upper()
        if st.button("Resume as Host", use_container_width=True):
            data = load_room(resume_code)
            if data:
                st.session_state.update(data)
                st.session_state.room_code = resume_code
                st.session_state.is_organizer = True
                st.query_params["host"] = resume_code
                st.rerun()
            else:
                st.error("Room not found.")

# ==========================================
# STAGE 1 & 2: CONFIGURATION & SETUP
# ==========================================
elif st.session_state.stage == 'config':
    st.header(f"Setup Room: {st.session_state.room_code}")
    game_type = st.selectbox("Choose Game Type:", ["padel", "padel_mixed", "babyfoot"])
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
        st.session_state.fanny_alert = False
        st.session_state.roster_alert = ""
        st.session_state.stage = 'setup_players'
        save_room()
        st.rerun()

elif st.session_state.stage == 'setup_players':
    st.header(f"Player Roster (Room: {st.session_state.room_code})")

    matches_per_round = st.session_state.total_players // 4
    active_players_per_round = matches_per_round * 4
    lcm_val = (active_players_per_round * st.session_state.total_players) // math.gcd(active_players_per_round, st.session_state.total_players)
    cycle_rounds = lcm_val // active_players_per_round
    cycle_matches = cycle_rounds * matches_per_round
    
    st.info(f"**Cycle Info:** To ensure perfectly equal play time, aim for multiples of {cycle_rounds} rounds (which equals {cycle_matches} total matches).")
    
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
                    st.session_state.players[name.strip()] = {'played': 0, 'tourney_pts': 0, 'diff': 0, 'points_won': 0, 'gender': gender, 'retired': False}
                st.session_state.stage = 'playing'
                save_room()
                st.rerun()

# ==========================================
# STAGE 3: TOURNAMENT LOOP
# ==========================================
elif st.session_state.stage == 'playing' and st.session_state.is_organizer:
    st.header(f"Room: {st.session_state.room_code} | Round {st.session_state.round_num}")
    
    if st.session_state.get('fanny_alert'):
        st.warning("👇 **Allez hop, sous la table !**")
        st.session_state.fanny_alert = False
        save_room()

    if st.session_state.get('roster_alert'):
        if "⚠️" in st.session_state.roster_alert:
            st.warning(st.session_state.roster_alert)
        else:
            st.success(st.session_state.roster_alert)
        st.session_state.roster_alert = "" 
        save_room()
    
    active_pool = [p for p, stats in st.session_state.players.items() if not stats.get('retired', False)]
    
    # --- PAUSE LOGIC FOR UNDER 4 PLAYERS ---
    if len(active_pool) < 4:
        st.warning("⏸️ **Tournament paused.** Waiting for minimum number of players (4 required for a game). Please add a player to continue.")
        st.session_state.current_matchups = []
        st.session_state.benched_players = active_pool
        save_room()
    else:
        matches_per_round = len(active_pool) // 4
        active_players_per_round = matches_per_round * 4
        
        if not st.session_state.current_matchups:
            # 1. Decide WHO plays (prioritizing those with the least matches played)
            sortable_list = [(st.session_state.players[p]['played'], -st.session_state.players[p]['tourney_pts'], 
                              -st.session_state.players[p]['diff'], -st.session_state.players[p]['points_won'], p) 
                             for p in active_pool]
            sortable_list.sort()
            sorted_names = [item[4] for item in sortable_list]
            
            selected_to_play = sorted_names[:active_players_per_round]
            st.session_state.benched_players = sorted_names[active_players_per_round:]
            
            # 2. Decide HOW they pair up (sort the selected players strictly by points/skill)
            skill_sort = [(-st.session_state.players[p]['tourney_pts'], -st.session_state.players[p]['diff'], 
                           -st.session_state.players[p]['points_won'], p) for p in selected_to_play]
            skill_sort.sort()
            active_players = [item[3] for item in skill_sort]
            
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
            st.info(f"🪑 **Benched:** {', '.join(st.session_state.benched_players)}")
            
        with st.form("score_form", clear_on_submit=True):
            scores_input = []
            for i, (team_a, team_b) in enumerate(st.session_state.current_matchups):
                st.subheader(f"{team_a[0]} & {team_a[1]}  vs  {team_b[0]} & {team_b[1]}")
                
                def_a, def_b = 0, 0
                if st.session_state.get('undo_scores') and len(st.session_state.undo_scores) > i:
                    _, _, def_a, def_b = st.session_state.undo_scores[i]
                    
                col1, col2 = st.columns(2)
                score_a = col1.number_input(f"Score Team A", min_value=0, step=1, value=def_a, key=f"sa_{i}_r{st.session_state.round_num}")
                score_b = col2.number_input(f"Score Team B", min_value=0, step=1, value=def_b, key=f"sb_{i}_r{st.session_state.round_num}")
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
                    st.session_state.fanny_alert = False  
                    
                    for team_a, team_b, score_a, score_b in scores_input:
                        if st.session_state.game_type == 'babyfoot':
                            if (score_a == 10 and score_b == 0) or (score_a == 0 and score_b == 10):
                                st.session_state.fanny_alert = True
                                
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
                    
                    if 'tourney_id' in st.session_state:
                        log_round_played(st.session_state.tourney_id, st.session_state.round_num)
                    
                    st.session_state.round_num += 1
                    st.session_state.current_matchups = []
                    save_room()
                    st.rerun()

    if st.session_state.round_num > 1 and st.session_state.history:
        if st.button("⚠️ Undo Last Round"):
            last_state = st.session_state.history.pop()
            last_scores = st.session_state.completed_rounds.pop()
            st.session_state.undo_scores = last_scores['results']  
            st.session_state.round_num = last_state['round_num']
            st.session_state.players = last_state['players']
            st.session_state.current_matchups = last_state['matchups']
            st.session_state.benched_players = last_state['benched']
            save_room()
            st.rerun()
            
    # --- DYNAMIC ROSTER (LATE ARRIVAL / EARLY EXIT) ---
    with st.expander("🛠️ Manage players"):
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Add Late Player**")
            with st.form("add_player_form", clear_on_submit=True):
                new_name = st.text_input("Name").strip()
                new_gender = st.selectbox("Gender", ['m', 'f']) if st.session_state.game_type == 'padel_mixed' else None
                submitted_add = st.form_submit_button("Add Player")
                
                if submitted_add:
                    if new_name and new_name not in st.session_state.players:
                        st.session_state.players[new_name] = {'played': 0, 'tourney_pts': 0, 'diff': 0, 'points_won': 0, 'gender': new_gender, 'retired': False}
                        st.session_state.current_matchups = [] 
                        
                        catchup_r, c_rounds, c_matches = calculate_cycle_info(st.session_state.players)
                        act_len = len([p for p, stats in st.session_state.players.items() if not stats.get('retired', False)])

                        if catchup_r == -1:
                            st.session_state.roster_alert = f"🔄 {new_name} added! ⚠️ With exactly {act_len} active players, no one sits out. The new player can never mathematically catch up."
                        elif catchup_r == -2:
                            st.session_state.roster_alert = f"🔄 {new_name} added! ⚠️ Due to players retiring unevenly, the math is permanently out of sync. Perfect equality is impossible."
                        elif catchup_r > 0:
                            st.session_state.roster_alert = f"🔄 {new_name} added! Matchups updated instantly. {catchup_r} rounds remaining for everyone to play equally, and then cycles will be {c_rounds} rounds ({c_matches} total matches)."
                        else:
                            st.session_state.roster_alert = f"🔄 {new_name} added! Matchups updated instantly. Everyone is currently perfectly equal!"
                            
                        save_room()
                        st.rerun()
                    elif new_name in st.session_state.players:
                        st.error("Player already exists.")
        with c2:
            st.write("**Retire Player (Early Exit)**")
            if active_pool:
                with st.form("retire_player_form"):
                    retire_name = st.selectbox("Select Player", active_pool)
                    submitted_retire = st.form_submit_button("Retire Player")
                    
                    if submitted_retire:
                        st.session_state.players[retire_name]['retired'] = True
                        st.session_state.current_matchups = []
                        
                        catchup_r, c_rounds, c_matches = calculate_cycle_info(st.session_state.players)
                        act_len = len([p for p, stats in st.session_state.players.items() if not stats.get('retired', False)])

                        if catchup_r == -1:
                            st.session_state.roster_alert = f"👋 {retire_name} retired. ⚠️ With exactly {act_len} active players, no one sits out. Any current gap cannot close mathematically."
                        elif catchup_r == -2:
                            st.session_state.roster_alert = f"👋 {retire_name} retired. ⚠️ The active roster's total match count is mathematically out of sync. Perfect equality is permanently impossible."
                        elif catchup_r > 0:
                            st.session_state.roster_alert = f"👋 {retire_name} retired. {catchup_r} rounds remaining for everyone to play equally, and then cycles will be {c_rounds} rounds ({c_matches} total matches)."
                        else:
                            st.session_state.roster_alert = f"👋 {retire_name} retired. Everyone is currently perfectly equal!"
                            
                        save_room()
                        st.rerun()

    # --- MANUAL MATCHMAKING OVERRIDE ---
    #with st.expander("🛠️ Manual Matchmaking Override"):
        st.write("**Swap Players in a Matchup**")
        playing_players = [p for match in st.session_state.current_matchups for team in match for p in team]
        if playing_players:
            with st.form("swap_players_form"):
                c1, c2 = st.columns(2)
                swap_a = c1.selectbox("Player 1", playing_players)
                swap_b = c2.selectbox("Player 2", playing_players)
                if st.form_submit_button("Swap Players"):
                    if swap_a != swap_b:
                        new_matchups = []
                        for team_a, team_b in st.session_state.current_matchups:
                            new_ta = tuple(swap_b if p == swap_a else swap_a if p == swap_b else p for p in team_a)
                            new_tb = tuple(swap_b if p == swap_a else swap_a if p == swap_b else p for p in team_b)
                            new_matchups.append((new_ta, new_tb))
                        st.session_state.current_matchups = new_matchups
                        save_room()
                        st.rerun()

    st.divider()
    
    st.subheader("Current Standings")
    standings = [(-s['tourney_pts'], -s['diff'], -s['points_won'], s['played'], f"{p} (Retired)" if s.get('retired', False) else p) for p, s in st.session_state.players.items()]
    standings.sort()
    table_md = "| Rank | Player | Pts | Diff | Won | Matches |\n|---|---|---|---|---|---|\n"
    for rank, item in get_ranked_standings(standings):
        table_md += f"| {rank} | {item[4]} | {-item[0]} | {-item[1]} | {-item[2]} | {item[3]} |\n"
    st.markdown(table_md)
    
    if st.session_state.completed_rounds:
        with st.expander("📜 Show Previous Match History"):
            for round_data in reversed(st.session_state.completed_rounds):
                st.markdown(f"**Round {round_data['round_num']}**")
                for team_a, team_b, score_a, score_b in round_data['results']:
                    st.text(f"  {team_a[0]} & {team_a[1]} ({score_a}) vs ({score_b}) {team_b[0]} & {team_b[1]}")

    st.write(f"📲 **Share live access. Code:** `{st.session_state.room_code}`")
    app_url = f"https://2v2-shuffle.streamlit.app/?room={st.session_state.room_code}"  
    st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={app_url}", width=150)
    
    st.divider()
    if st.button("🏁 End Tournament & Save Results", type="primary"):
        st.session_state.stage = 'finished'
        save_room()
        st.rerun()


# ==========================================
# STAGE 4: FINISHED
# ==========================================
elif st.session_state.stage == 'finished' and st.session_state.is_organizer:
    render_downloads_and_podium(st.session_state.players, st.session_state.game_type, st.session_state.round_num, st.session_state.completed_rounds)
    
    if st.session_state.completed_rounds:
        with st.expander("📜 Full Match History"):
            for round_data in reversed(st.session_state.completed_rounds):
                st.markdown(f"**Round {round_data['round_num']}**")
                for team_a, team_b, score_a, score_b in round_data['results']:
                    st.text(f"  {team_a[0]} & {team_a[1]} ({score_a}) vs ({score_b}) {team_b[0]} & {team_b[1]}")

    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Back to Tournament", use_container_width=True):
            st.session_state.stage = 'playing'
            save_room()
            st.rerun()
    with col2:
        if st.button("Close Room & Return Home", type="primary", use_container_width=True):
            st.query_params.clear()
            st.session_state.clear()
            st.rerun()

# ==========================================
# STAGE 5: VIEWER MODE
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
        
        if room_data.get('stage') == 'config':
            st.info("The organizer is currently choosing the game settings...")
            if st.button("🔄 Refresh Data"): st.rerun()
        elif room_data.get('stage') == 'setup_players':
            st.info("The organizer is currently entering player names. Stand by...")
            if st.button("🔄 Refresh Data"): st.rerun()
            
        elif room_data.get('stage') == 'finished':
            st.success("🏁 The organizer has ended the tournament.")
            render_downloads_and_podium(room_data['players'], room_data['game_type'], room_data['round_num'], room_data.get('completed_rounds', []))
        else:
            col1, col2 = st.columns([3, 1])
            with col1: st.write(f"**Round:** {room_data['round_num']} | **Game:** {room_data['game_type'].replace('_', ' ').title()}")
            with col2:
                if st.button("🔄 Refresh Data"): st.rerun()
                    
            if room_data.get('current_matchups'):
                st.subheader("Currently Playing")
                for team_a, team_b in room_data['current_matchups']:
                    st.info(f"{team_a[0]} & {team_a[1]}  vs  {team_b[0]} & {team_b[1]}")
            else:
                active_view_pool = [p for p, stats in room_data['players'].items() if not stats.get('retired', False)]
                if len(active_view_pool) < 4:
                    st.warning("⏸️ Tournament paused while waiting for minimum number of players (4 required).")
                    
            st.subheader("Standings")
            standings = [(-s['tourney_pts'], -s['diff'], -s['points_won'], s['played'], f"{p} (Retired)" if s.get('retired', False) else p) for p, s in room_data['players'].items()]
            standings.sort()
            table_md = "| Rank | Player | Pts | Diff | Won | Matches |\n|---|---|---|---|---|---|\n"
            for rank, item in get_ranked_standings(standings):
                table_md += f"| {rank} | {item[4]} | {-item[0]} | {-item[1]} | {-item[2]} | {item[3]} |\n"
            st.markdown(table_md)
            
            if room_data.get('completed_rounds'):
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
