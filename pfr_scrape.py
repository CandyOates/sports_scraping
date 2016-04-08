from __future__ import print_function
import re
import numpy as np
import pandas as pd
import datetime
import bs4
import urllib2
import itertools
import functools
import argparse
import time

BASE_URL = 'http://www.pro-football-reference.com/players/%s/'
TEAM_URL = 'http://www.pro-football-reference.com/teams/%s'

def getPlayerGamelog(playerid, year):
    HEADER_ADJ = {'Sacks & Tackles': 'SacksAndTackles'}
    
    url = 'http://www.pro-football-reference.com/players/%s/%s/gamelog/%d/' % (playerid[0], playerid, year)
    page = urllib2.urlopen(url)
    text = page.read()
    soup = bs4.BeautifulSoup(text, 'lxml')
    
    def f(soup, Id):
        tabR = soup.find('table', attrs={'id': Id})
        oh, h = tabR.find('thead').findAll('tr')
        prefix = [x for y in map(lambda x: x[0]*[x[1]], map(lambda x: (int(x.get('colspan') if x.get('colspan') is not None else 1), HEADER_ADJ[x.text] if x.text in HEADER_ADJ else x.text), oh.findAll('th'))) for x in y]
        postfix = map(lambda x: x.text.replace('#','').replace('/','_'), h.findAll('th'))
        headers = map(lambda x: '%s.%s' % x if x[0] != '' else (x[1] if x[1] != '' else u'HA'), itertools.izip(prefix, postfix))
        data = []
        for tr in tabR.find('tbody').findAll('tr'):
            row = []
            for td in tr.findAll('td'):
                row.append(td.text if td.text != '' else np.nan)
            data.append(row)
        tableR = pd.DataFrame(data, columns=headers)
        tableR['PlayerID'] = playerid
        tableR['HA'] = [' vs. ' if x != '@' and x != 'N' else (' @ ' if x=='@' else x) for x in tableR.HA]
        tableR['GameType'] = u'R'
        tableR['GameID'] = ['%s %s%s%s %s %s' % x for x in itertools.izip(tableR.PlayerID, tableR.Tm, tableR.HA, tableR.Opp, tableR.Date, tableR.GameType)]
        tableR = tableR.set_index('GameID')
        return tableR
    
    try:
        tableR = f(soup, 'stats')
    except AttributeError:
        return pd.DataFrame()
    try:
        tableP = f(soup, 'stats_playoffs')
    except AttributeError:
        return tableR
    
    table = tableR.append(tableP)
    del table['Rk']
    return table

def getPlayerGamelogs(playerids, years):
    return reduce(lambda x, y: x.copy().append(y.copy()), map(lambda playerid: reduce(lambda x, y: x.copy().append(y.copy()), map(functools.partial(getPlayerGamelog, playerid), range(min(years),max(years)+1))), playerids))

def getPlayerList(START_YEAR, END_YEAR, POSITIONS=('',), verbose_level=0):
    if verbose_level >= 1:
        print('Getting Player List...')
    start = time.time()
    players = []
    for n in range(65,65+26):
        c = chr(n)
        url = BASE_URL % c
        page = urllib2.urlopen(url)
        text = page.read()
        matches = filter(lambda x: x is not None, map(lambda x: re.search(r'^(<b>){0,1}<a href="/players/./(.+)\.htm">([a-zA-Z ]+)</a> +([A-Z-]+) +(\d\d\d\d)-(\d\d\d\d)(</b>){0,1}$', x), text.split('\n')))
        rows = map(lambda x: x.groups()[1:4] + (int(x.groups()[4]),) + (int(x.groups()[5]),), matches)
        current = filter(lambda x: x[4] >= START_YEAR and any([pos in x[2] for pos in POSITIONS]), rows)
        players.extend(current)
    if 'DEF' in POSITIONS:
        url = TEAM_URL % ''
        page = urllib2.urlopen(url)
        text = page.read()
        soup = bs4.BeautifulSoup(text, 'lxml')

        text = soup.find('table', attrs={'id': 'teams_active'}).__str__()
        lines = text.split('\n')
        matches = filter(lambda x: x is not None, map(lambda x: re.search(r'^<td align="left"><a href="/teams/([a-zA-Z]+)/">(.+)</a>', x), lines))
        yrmatches = filter(lambda x: x is not None, map(lambda x: re.search(r'^<td align="right">(\d{4})-(\d{4})</td>', x), lines))

        for match, yrmatch in itertools.izip(matches, yrmatches):
            players.append(match.groups() + ('DEF',) + tuple([int(x) for x in yrmatch.groups()]))
    if verbose_level >= 1:
        print('Finished - Time Elapsed: %.2f' % (time.time() - start))
    return pd.DataFrame(players, columns=['PlayerID','Name','Pos','StartYear','LastYear']).set_index('PlayerID')

def getSeasonLogs(playerids, verbose_level=0):
    if verbose_level >= 1:
        print('Collecting Logs')
    start = time.time()
    table = pd.DataFrame()
    for playerid in playerids:
        if verbose_level == 2:
            print(playerid)
        soup = getSoup(playerid)
        tab = reduce(join_tables, map(lambda x: x(soup, playerid), 
                                      [getKicking,getKickReturns,getReceivingAndRushing,getIndividualDefense,getPassing]))
        table = table.append(tab)
    if verbose_level >= 1:
        print('Finished - Time Elapsed: %.2f' % (time.time() - start))
    return table

def getPFRURL(playerid):
    return (BASE_URL % playerid[0]) + ('%s.htm' % playerid)

#def getPFRURL(player):
#    '''Takes a row from the DataFrame "players"'''
#    if player.Pos == 'DEF':
#        return TEAM_URL % player.PlayerID
#    return (BASE_URL % player.PlayerID[0]) + ('%s.htm' % player.PlayerID)

def getSoup(playerid):
    url = getPFRURL(playerid)
    page = urllib2.urlopen(url)
    text = page.read()
    soup = bs4.BeautifulSoup(text, 'lxml')
    return soup

#def getSoup(player):
#    url = getPFRURL(player)
#    page = urllib2.urlopen(url)
#    text = page.read()
#    soup = bs4.BeautifulSoup(text, 'lxml')
#    return soup

def getKicking(Soup, playerID):
    tid = 'kicking'
    soup = Soup.find('table', attrs={'id': tid})
    if not soup:
        return pd.DataFrame()
    cols = ['Year','Age','Tm','Pos','No.','G','GS','K.FGA.0_19','K.FGM.0_19','K.FGA.20_29','K.FGM.20_29',
            'K.FGA.30_39','K.FGM.30_39','K.FGA.40_49','K.FGM.40_49','K.FGA.50p','K.FGM.50p',
            'K.FGA','K.FGM','K.Lng','K.FG%','K.XPA','K.XPM','K.XP%','P.Pnt','P.Yds','P.Lng','P.Blck',
            'P.Y_P','GameType']
    cols2 = ['Year','Age','Tm','Pos','G','GS','K.FGA.0_19','K.FGM.0_19','K.FGA.20_29','K.FGM.20_29',
            'K.FGA.30_39','K.FGM.30_39','K.FGA.40_49','K.FGM.40_49','K.FGA.50p','K.FGM.50p',
            'K.FGA','K.FGM','K.Lng','K.FG%','K.XPA','K.XPM','K.XP%','P.Pnt','P.Yds','P.Lng','P.Blck',
            'P.Y_P','GameType']
    table = pd.DataFrame(columns=cols)
    for tr in soup.find('tbody').findAll('tr'):
        row = [td.text for td in tr.findAll('td')][:len(cols)-1] + ['R']
        row = map(lambda x: np.nan if x=='' else x, row)
        table = table.append(dict(itertools.izip(cols,row)), ignore_index=True)
    try:
        for tr in Soup.find('table', attrs={'id': '%s_playoffs'%tid}).find('tbody').findAll('tr'):
            row = [td.text for td in tr.findAll('td')] + ['P']
            row = map(lambda x: np.nan if x=='' else x, row)
            table = table.append(dict(itertools.izip(cols2,row)), ignore_index=True)
    except AttributeError:
        pass
    table['Year'] = table.Year.fillna(method='ffill')
    table['Age'] = table.Age.fillna(method='ffill')
    table['ProBowl'] = [int('*' in x) for x in table.Year]
    table['FirstTeamAllPro'] = [int('+' in x) for x in table.Year]
    table['Year'] = [int(re.search(r'^(\d{4}).*$', x).group(1)) for x in table.Year]
    table['RowID'] = [('%s %s' % (playerID, ('(%d%s-%s)' % x).upper())) for x in itertools.izip(table.Year,table.GameType,table.Tm)]
    table['PlayerID'] = playerID
    table = table.set_index('RowID', drop=False)
    return table

def getKickReturns(Soup, playerID):
    tid = 'returns'
    soup = Soup.find('table', attrs={'id': tid})
    if not soup:
        return pd.DataFrame()
    cols = ['Year','Age','Tm','Pos','No.','G','GS','PR.Ret','PR.Yds','PR.TD',
            'PR.Long','PR.Y_R','KR.Rt','KR.Yds','KR.TD','KR.Long','KR.Y_R',
            'APYd','GameType']
    cols2 = ['Year','Age','Tm','Pos','G','GS','PR.Ret','PR.Yds','PR.TD',
            'PR.Long','PR.Y_R','KR.Rt','KR.Yds','KR.TD','KR.Long','KR.Y_R',
            'APYd','GameType']
    table = pd.DataFrame(columns=cols)
    for tr in soup.find('tbody').findAll('tr'):
        row = [td.text for td in tr.findAll('td')][:len(cols)-1] + ['R']
        row = map(lambda x: np.nan if x=='' else x, row)
        table = table.append(dict(itertools.izip(cols,row)), ignore_index=True)
    try:
        for tr in Soup.find('table', attrs={'id': '%s_playoffs'%tid}).find('tbody').findAll('tr'):
            row = [td.text for td in tr.findAll('td')] + ['P']
            row = map(lambda x: np.nan if x=='' else x, row)
            table = table.append(dict(itertools.izip(cols2,row)), ignore_index=True)
    except AttributeError:
        pass
    table['Year'] = table.Year.fillna(method='ffill')
    table['Age'] = table.Age.fillna(method='ffill')
    table['ProBowl'] = [int('*' in x) for x in table.Year]
    table['FirstTeamAllPro'] = [int('+' in x) for x in table.Year]
    table['Year'] = [int(re.search(r'^(\d{4}).*$', x).group(1)) for x in table.Year]
    table['RowID'] = [('%s %s' % (playerID, ('(%d%s-%s)' % x).upper())) for x in itertools.izip(table.Year,table.GameType,table.Tm)]
    table['PlayerID'] = playerID
    table = table.set_index('RowID', drop=False)
    return table

def getReceivingAndRushing(Soup, playerID):
    tid = 'receiving_and_rushing'
    soup = Soup.find('table', attrs={'id': tid})
    if not soup:
        return pd.DataFrame()
    cols = ['Year','Age','Tm','Pos','No.','G','GS','Rec.Tgt','Rec.Rec','Rec.Yds','Rec.Y_R',
            'Rec.TD','Rec.Lng','Rec.R_G','Rec.Y_G','Rush.Att','Rush.Yds','Rush.TD','Rush.Lng',
            'Rush.Y_A','Rush.Y_G','Rush.A_G','YScm','RRTD','Fmb','GameType']
    cols2 = ['Year','Age','Tm','Pos','G','GS','Rec.Tgt','Rec.Rec','Rec.Yds','Rec.Y_R',
            'Rec.TD','Rec.Lng','Rec.R_G','Rec.Y_G','Rush.Att','Rush.Yds','Rush.TD','Rush.Lng',
            'Rush.Y_A','Rush.Y_G','Rush.A_G','YScm','RRTD','Fmb','GameType']
    table = pd.DataFrame(columns=cols)
    for tr in soup.find('tbody').findAll('tr'):
        row = [td.text for td in tr.findAll('td')][:len(cols)-1] + ['R']
        row = map(lambda x: np.nan if x=='' else x, row)
        table = table.append(dict(itertools.izip(cols,row)), ignore_index=True)
    try:
        for tr in Soup.find('table', attrs={'id': '%s_playoffs'%tid}).find('tbody').findAll('tr'):
            row = [td.text for td in tr.findAll('td')] + ['P']
            row = map(lambda x: np.nan if x=='' else x, row)
            table = table.append(dict(itertools.izip(cols2,row)), ignore_index=True)
    except AttributeError:
        pass
    table['Year'] = table.Year.fillna(method='ffill')
    table['Age'] = table.Age.fillna(method='ffill')
    table['ProBowl'] = [int('*' in x) for x in table.Year]
    table['FirstTeamAllPro'] = [int('+' in x) for x in table.Year]
    table['Year'] = [int(re.search(r'(\d{4}).*', x).group(1)) for x in table.Year]
    table['RowID'] = [('%s %s' % (playerID, ('(%d%s-%s)' % x).upper())) for x in itertools.izip(table.Year,table.GameType,table.Tm)]
    table['PlayerID'] = playerID
    table = table.set_index('RowID', drop=False)
    return table

def getIndividualDefense(Soup, playerID):
    tid = 'defense'
    soup = Soup.find('table', attrs={'id': tid})
    if not soup:
        return pd.DataFrame()
    cols = ['Year','Age','Tm','Pos','No.','G','GS','DI.Int','DI.Yds','DI.TD','DI.Lng',
            'DI.PD','Fum.FF','Fum.Fmb','Fum.FR','Fum.Yds','Fum.TD','ST.Sk','ST.Tkl',
            'ST.Ast','ST.Sfty','GameType']
    cols2 = ['Year','Age','Tm','Pos','G','GS','DI.Int','DI.Yds','DI.TD','DI.Lng',
            'DI.PD','Fum.FF','Fum.Fmb','Fum.FR','Fum.Yds','Fum.TD','ST.Sk','ST.Tkl',
            'ST.Ast','ST.Sfty','GameType']
    table = pd.DataFrame(columns=cols)
    for tr in soup.find('tbody').findAll('tr'):
        row = [td.text for td in tr.findAll('td')][:len(cols)-1] + ['R']
        row = map(lambda x: np.nan if x=='' else x, row)
        table = table.append(dict(itertools.izip(cols,row)), ignore_index=True)
    try:
        for tr in Soup.find('table', attrs={'id': '%s_playoffs'%tid}).find('tbody').findAll('tr'):
            row = [td.text for td in tr.findAll('td')] + ['P']
            row = map(lambda x: np.nan if x=='' else x, row)
            table = table.append(dict(itertools.izip(cols2,row)), ignore_index=True)
    except AttributeError:
        pass
    table['Year'] = table.Year.fillna(method='ffill')
    table['Age'] = table.Age.fillna(method='ffill')
    table['ProBowl'] = [int('*' in x) for x in table.Year]
    table['FirstTeamAllPro'] = [int('+' in x) for x in table.Year]
    table['Year'] = [int(re.search(r'^(\d{4}).*$', x).group(1)) for x in table.Year]
    table['RowID'] = [('%s %s' % (playerID, ('(%d%s-%s)' % x).upper())) for x in itertools.izip(table.Year,table.GameType,table.Tm)]
    table['PlayerID'] = playerID
    table = table.set_index('RowID', drop=False)
    return table

def getPassing(Soup, playerID):
    tid = 'passing'
    soup = Soup.find('table', attrs={'id': tid})
    if not soup:
        return pd.DataFrame()
    cols = ['Year','Age','Tm','Pos','No.','G','GS','QBrec','Pass.Comp','Pass.Att','Pass.Cmp%',
            'Pass.Yds','Pass.TD','Pass.TD%','Pass.Int','Pass.Int%','Pass.Lng','Pass.Y_A',
            'Pass.AY_A','Pass.Y_C','Pass.Y_G','Pass.Rate','Pass.QBR','Pass.Sk','Pass.SkYds',
            'Pass.NY_A','Pass.ANY_A','Pass.Sk%','Pass.Q4C','Pass.GWD','GameType']
    cols2 = ['Year','Age','Tm','Pos','G','GS','QBrec','Pass.Comp','Pass.Att','Pass.Cmp%',
            'Pass.Yds','Pass.TD','Pass.TD%','Pass.Int','Pass.Int%','Pass.Lng','Pass.Y_A',
            'Pass.AY_A','Pass.Y_C','Pass.Y_G','Pass.Rate','Pass.Sk','Pass.SkYds',
            'Pass.NY_A','Pass.ANY_A','Pass.Sk%','Pass.Q4C','Pass.GWD','GameType']
    table = pd.DataFrame(columns=cols)
    for tr in soup.find('tbody').findAll('tr'):
        row = [td.text for td in tr.findAll('td')][:len(cols)-1] + ['R']
        row = map(lambda x: np.nan if x=='' else x, row)
        table = table.append(dict(itertools.izip(cols,row)), ignore_index=True)
    try:
        for tr in Soup.find('table', attrs={'id': '%s_playoffs'%tid}).find('tbody').findAll('tr'):
            row = [td.text for td in tr.findAll('td')] + ['P']
            row = map(lambda x: np.nan if x=='' else x, row)
            table = table.append(dict(itertools.izip(cols2,row)), ignore_index=True)
    except AttributeError:
        pass
    table['Year'] = table.Year.fillna(method='ffill')
    table['Age'] = table.Age.fillna(method='ffill')
    table['ProBowl'] = [int('*' in x) for x in table.Year]
    table['FirstTeamAllPro'] = [int('+' in x) for x in table.Year]
    table['Year'] = [int(re.search(r'^(\d{4}).*$', x).group(1)) for x in table.Year]
    table['RowID'] = [('%s %s' % (playerID, ('(%d%s-%s)' % x).upper())) for x in itertools.izip(table.Year,table.GameType,table.Tm)]
    table['PlayerID'] = playerID
    table = table.set_index('RowID', drop=False)
    return table

def join_tables(tab1, tab2):
    tab = tab1.copy()
    t = tab2.drop(filter(lambda x: x!='RowID', tab.keys()), axis=1, errors='ignore')
    tab[t.keys()] = t[t.keys()]
    tab.RowID = tab.index.values
    return tab

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('logtype', type=str, help='season or gamelog or playerlist', choices=['season','gamelog','playerlist'])
    parser.add_argument('outfile', type=str, help='file to save the table to')
    parser.add_argument('--playeridfile','-f', type=str, help='file listing out player ids')
    parser.add_argument('--playerid','-i', type=str, help='pro-football-reference player ID, if season or gamelog: a list separated by /, if playerlist: unused')
    parser.add_argument('--years','-y', type=int, nargs=2, help='If season: not used. If gamelog or playerlist: startyear endyear')
    parser.add_argument('--verbose','-v', type=int, help='0 - no output, 1 - some output, 2 - all output')
    parser.add_argument('--positions','-p', type=str, help='If playerlist: list of positions for players separated by /', default='')
    
    args = parser.parse_args()
    if args.logtype != 'playerlist':
		try:
			playerid = args.playerid.split('/')
		except:
			pid_table = pd.read_csv(args.playeridfile)
			playerid = pid_table.PlayerID
#			with open(args.playeridfile, 'r') as w:
#				playerid = w.read().split('\n')[:-1]
    years = args.years
    outfile = args.outfile
    
    if args.logtype == 'gamelog':
        table = getPlayerGamelogs(playerid, years)
    elif args.logtype == 'season':
        table = getSeasonLogs(playerid, verbose_level=args.verbose)
    elif args.logtype == 'playerlist':
        table = getPlayerList(min(years), max(years), args.positions.split('/'), verbose_level=args.verbose)
    table.to_csv(outfile)
