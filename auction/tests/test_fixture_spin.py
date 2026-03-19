from django.test import TestCase
from auction.models import Team, TournamentPool, Match, PoolTeam
from auction.services.fixture_service import create_group_stage, generate_next_match

class TestFixtureSpinLogic(TestCase):
    def setUp(self):
        self.teams = [Team.objects.create(name=f"Team {i}") for i in range(1, 5)]
        self.pools = create_group_stage(num_pools=1, advance_n=2, teams_per_pool=4, 
                                        team_ids=[t.team_serial_number for t in self.teams])
        self.pool = self.pools[0]

    def test_generate_next_match_no_save(self):
        # Should return a match but not create it
        result = generate_next_match(save=False)
        self.assertIsNotNone(result)
        self.assertEqual(Match.objects.count(), 0)
        self.assertEqual(result['team1'], "Team 1")
        self.assertEqual(result['team2'], "Team 4") # Based on Circle Method round 1

    def test_generate_next_match_with_save(self):
        result = generate_next_match(save=True)
        self.assertIsNotNone(result)
        self.assertEqual(Match.objects.count(), 1)
        m = Match.objects.first()
        self.assertEqual(m.team1.name, result['team1'])
        self.assertEqual(m.team2.name, result['team2'])

    def test_generate_next_match_team_id_filtering(self):
        # Land on Team 2
        t2 = Team.objects.get(name="Team 2")
        result = generate_next_match(team_id=t2.team_serial_number, save=False)
        
        # Circle Method Round 1 for 4 teams: (1,4), (2,3)
        # So Team 2's next match should be vs Team 3
        self.assertEqual(result['team1'], "Team 2")
        self.assertEqual(result['team2'], "Team 3")
        
        # Confirm it didn't pick Team 1 vs Team 4
        self.assertNotEqual(result['team1'], "Team 1")

    def test_sequential_reveal_flow(self):
        # Step 1: Preview first match (save=False)
        p1 = generate_next_match(save=False)
        self.assertEqual(Match.objects.count(), 0)
        
        # Step 2: Save it (using team1_id from preview)
        s1 = generate_next_match(team_id=p1['team1_id'], save=True)
        self.assertEqual(Match.objects.count(), 1)
        self.assertEqual(s1['team1'], p1['team1'])
        
        # Step 3: Preview next match
        p2 = generate_next_match(save=False)
        self.assertEqual(Match.objects.count(), 1) # Still 1
        self.assertNotEqual(p2['team1'], p1['team1'])
