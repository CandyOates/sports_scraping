Pro-Football-Reference Scraper

There are 3 usages. One which gets a list of players based on the years they were active and their position. Another which gets the season results for a list of players. And finally one which gets the gamelogs for a list of players over a range of years.

Key: 
	[] indicate a variable input
	() indicates an optional input

Note that -f [playeridfile] can replace -i [playerids separated by /] below. [playeridfile] is a csv with a column headed "PlayerID" containing the pro-football-reference player ids of each player. The output of running playerlist is valid input.

Usage:
	Get Player List:
		$python pfr_scrape.py playerlist [outfile] -y [startyear] [endyear] (-p [positions separated by /]) (-v [0 or 1 or 2])

	Get Season Logs:
		$python pfr_scrape.py season [outfile] -i [playerids separated by /] (-v [0 or 1 or 2])

	Get Gamelogs:
		$python pfr_scrape.py gamelog [outfile] -i [playerids separated by /] -y [startyear] [endyear]
