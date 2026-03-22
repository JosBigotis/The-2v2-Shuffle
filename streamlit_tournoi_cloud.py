import streamlit as st
import math
import datetime
import os

# --- Helper Function ---
def get_ranked_standings(standings_list):
    ranked_list = []
    rank = 1
    actual_position = 1
    prev_stats = None
    
    for item in standings_list:
        current_stats = (item[0], item[1], item[2])
        if prev_stats is not None and current_stats != prev_stats:
            rank = actual_position
            
        ranked_list.append((rank, item))
        prev_stats = current_stats
        actual_position += 1
        
    return ranked_list

# --- Initialize Session State ---
# This ensures variables survive when the page reloads after a button click
if 'stage' not in st.session_state:
    st.session_state.stage = 'config'
    st.session_state.players = {}
    st.session_state.round_num = 1
    st.session_state.current_matchups = []
    st.session_state.benched_players = []

st.title("🏆 Tournament Manager")

# ==========================================
# STAGE 1: CONFIGURATION
# ==========================================
if st.session_state.stage == 'config':
    st.header("Tournament Setup")
    
    game_type = st.selectbox("Choose Game Type:", ["babyfoot", "padel", "padel_mixed"])
    total_players = st.number_input("Total Number of Players:", min_value=4, step=1, value=4)
    
    if st.button("Next: Enter Players"):
        st.session_state.game_type = game_type
        st.session_state.total_players = total_players
        st.session_state.stage = 'setup_players'
        st.rerun()

# ==========================================
# STAGE 2: PLAYER SETUP
# ==========================================
elif st.session_state.stage == 'setup_players':
    st.header("Enter Player Names")
    
    # Calculate cycle info
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
            name = col1.text_input(f"Player {i + 1} Name", key=f"name_{i}")
            
            gender = None
            if st.session_state.game_type == 'padel_mixed':
                gender = col2.selectbox(f"Gender", ['m', 'f'], key=f"gender_{i}")
                
            player_inputs.append((name, gender))
            
        submitted = st.form_submit_button("Start Tournament")
        
        if submitted:
            names_entered = [p[0].strip() for p in player_inputs if p[0].strip()]
            
            # Validation
            if len(names_entered) != st.session_state.total_players:
                st.error("Please enter a name for all players.")
            elif len(names_entered) != len(set(names_entered)):
                st.error("All player names must be unique.")
            else:
                for name, gender in player_inputs:
                    st.session_state.players[name.strip()] = {
                        'played': 0, 'tourney_pts': 0, 'diff': 0, 'points_won': 0, 'gender': gender
                    }
                st.session_state.stage = 'playing'
                st.rerun()

# ==========================================
# STAGE 3: TOURNAMENT LOOP
# ==========================================
elif st.session_state.stage == 'playing':
    st.header(f"=== ROUND {st.session_state.round_num} ===")
    
    matches_per_round = st.session_state.total_players // 4
    active_players_per_round = matches_per_round * 4
    
    # Generate matchups exactly once per round
    if not st.session_state.current_matchups:
        sortable_list = []
        for p_name, stats in st.session_state.players.items():
            sortable_list.append((
                stats['played'], 
                -stats['tourney_pts'], 
                -stats['diff'], 
                -stats['points_won'], 
                p_name
            ))
        sortable_list.sort()
        
        sorted_names = [item[4] for item in sortable_list]
        active_players = sorted_names[:active_players_per_round]
        st.session_state.benched_players = sorted_names[active_players_per_round:]
        
        round_matches = []
        for i in range(matches_per_round):
            chunk = active_players[i * 4 : (i + 1) * 4]
            
            if st.session_state.game_type == 'padel_mixed':
                pairings = [
                    ((chunk[0], chunk[3]), (chunk[1], chunk[2])),
                    ((chunk[0], chunk[2]), (chunk[1], chunk[3])),
                    ((chunk[0], chunk[1]), (chunk[2], chunk[3]))
                ]
                
                best_pairing = pairings[0]
                max_mixed_teams = -1
                
                for t_a, t_b in pairings:
                    mixed_a = 1 if st.session_state.players[t_a[0]]['gender'] != st.session_state.players[t_a[1]]['gender'] else 0
                    mixed_b = 1 if st.session_state.players[t_b[0]]['gender'] != st.session_state.players[t_b[1]]['gender'] else 0
                    total_mixed = mixed_a + mixed_b
                    
                    if total_mixed > max_mixed_teams:
                        max_mixed_teams = total_mixed
                        best_pairing = (t_a, t_b)
                        
                team_a, team_b = best_pairing
            else:
                team_a = (chunk[0], chunk[3])
                team_b = (chunk[1], chunk[2])
                
            round_matches.append((team_a, team_b))
            
            # Increment played counter instantly so it's ready for next round's sort
            for p in chunk:
                st.session_state.players[p]['played'] += 1
                
        st.session_state.current_matchups = round_matches

    # Display Benched Players
    if st.session_state.benched_players:
        st.warning(f"🪑 **Benched this round:** {', '.join(st.session_state.benched_players)}")
        
    # Input Scores Form
    with st.form("score_form", clear_on_submit=True):
        scores_input = []
        for i, (team_a, team_b) in enumerate(st.session_state.current_matchups):
            st.subheader(f"Match {i + 1}: {team_a[0]} & {team_a[1]} vs {team_b[0]} & {team_b[1]}")
            col1, col2 = st.columns(2)
            score_a = col1.number_input(f"Score for {team_a[0]} & {team_a[1]}", min_value=0, step=1, key=f"sa_{i}")
            score_b = col2.number_input(f"Score for {team_b[0]} & {team_b[1]}", min_value=0, step=1, key=f"sb_{i}")
            scores_input.append((team_a, team_b, score_a, score_b))
            
        submit_scores = st.form_submit_button("Submit Scores & Generate Next Round")
        
        if submit_scores:
            validation_passed = True
            
            # Validate Scores
            if st.session_state.game_type == 'babyfoot':
                for _, _, sa, sb in scores_input:
                    if not (0 <= sa <= 10 and 0 <= sb <= 10):
                        st.error("Babyfoot scores must be between 0 and 10.")
                        validation_passed = False
                    elif not (sa == 10 or sb == 10):
                        st.error("Exactly one team must score 10 in babyfoot.")
                        validation_passed = False
                    elif sa == sb:
                        st.error("Scores cannot be tied.")
                        validation_passed = False
                        
            if validation_passed:
                # Process Points
                for team_a, team_b, score_a, score_b in scores_input:
                    # Raw stats
                    for p in team_a:
                        st.session_state.players[p]['points_won'] += score_a
                        st.session_state.players[p]['diff'] += (score_a - score_b)
                    for p in team_b:
                        st.session_state.players[p]['points_won'] += score_b
                        st.session_state.players[p]['diff'] += (score_b - score_a)
                        
                    # Tourney Points
                    if st.session_state.game_type == 'babyfoot':
                        if score_a == 10:
                            pts_a = 2 if score_b >= 6 else 3
                            pts_b = 1 if score_b >= 6 else 0
                        else:
                            pts_b = 2 if score_a >= 6 else 3
                            pts_a = 1 if score_a >= 6 else 0
                    else: # Padel / Padel Mixed
                        if score_a > score_b:
                            pts_a, pts_b = 1, 0
                        elif score_b > score_a:
                            pts_a, pts_b = 0, 1
                        else:
                            pts_a, pts_b = 0, 0
                            
                    for p in team_a:
                        st.session_state.players[p]['tourney_pts'] += pts_a
                    for p in team_b:
                        st.session_state.players[p]['tourney_pts'] += pts_b
                
                # Advance Round
                st.session_state.round_num += 1
                st.session_state.current_matchups = [] # Clears to trigger new matchmaking
                st.rerun()

    st.divider()
    
    # Live Standings Table Display
    st.subheader("Current Standings")
    standings = []
    for p_name, stats in st.session_state.players.items():
        standings.append((-stats['tourney_pts'], -stats['diff'], -stats['points_won'], stats['played'], p_name))
    standings.sort()
    
    ranked_standings = get_ranked_standings(standings)
    
    # Formatting for Streamlit Markdown Table
    table_md = "| Rank | Player | Pts | Diff | Won | Matches |\n|---|---|---|---|---|---|\n"
    for rank, item in ranked_standings:
        table_md += f"| {rank} | {item[4]} | {-item[0]} | {-item[1]} | {-item[2]} | {item[3]} |\n"
    st.markdown(table_md)

    # End Tournament Button
    if st.button("End Tournament", type="primary"):
        st.session_state.stage = 'finished'
        st.rerun()

# ==========================================
# STAGE 4: TOURNAMENT OVER & DOWNLOAD
# ==========================================
elif st.session_state.stage == 'finished':
    st.header("🏁 Tournament Complete")
    
    display_game = 'padel' if st.session_state.game_type in ('padel', 'padel_mixed') else st.session_state.game_type
    timestamp = datetime.datetime.now().strftime("%d-%m-%Y_%H-%M")
    filename = f"{display_game}_standings_{timestamp}.txt"
    
    # Generate the text file content in memory instead of saving to the OS
    file_content = "=" * 56 + "\n"
    file_content += f"{'FINAL ' + display_game.upper() + ' STANDINGS':^56}\n"
    file_content += f"{'Total Rounds: ' + str(st.session_state.round_num - 1):^56}\n"
    file_content += "=" * 56 + "\n"
    file_content += f"| {'Rank':<4} | {'Player':<12} | {'Pts':<3} | {'Diff':<4} | {'Won':<3} | {'Matches':<7} |\n"
    file_content += "-" * 56 + "\n"
    
    # Re-calculate final standings for the file
    standings = []
    for p_name, stats in st.session_state.players.items():
        standings.append((-stats['tourney_pts'], -stats['diff'], -stats['points_won'], stats['played'], p_name))
    standings.sort()
    
    ranked_standings = get_ranked_standings(standings)
    
    for rank, item in ranked_standings: 
        player_name = str(item[4])[:12]
        file_content += f"| {rank:<4} | {player_name:<12} | {-item[0]:<3} | {-item[1]:<4} | {-item[2]:<3} | {item[3]:<7} |\n"
        
    file_content += "=" * 56 + "\n"
    
    # Serve the file directly to the user's browser
    st.download_button(
        label="📥 Download Final Standings (.txt)",
        data=file_content,
        file_name=filename,
        mime="text/plain"
    )
    
    # Reset capability
    if st.button("Start New Tournament"):
        st.session_state.clear()
        st.rerun()
