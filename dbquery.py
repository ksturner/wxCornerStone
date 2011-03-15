#!/usr/bin/env python
import os, sys, sqlite3

def runQuerySession(conn, c):
	quit = False
	while not quit:
		print ">>",
		sql = raw_input()
		slsql = sql.strip().lower()
		if slsql == 'quit' or slsql == 'exit':
			quit = True	
		else:
			try:
				c.execute(sql)
				for row in c:
					print "-" * 80
					rowstr = ','.join([str(r) for r in row])
					print rowstr
				print "-" * 80
			except:
				print "FAIL!"


if __name__ == '__main__':
	if sys.argv[1:]:
		dbfile = sys.argv[1]
		if os.path.exists(dbfile):
			conn = sqlite3.connect(dbfile)
			c = conn.cursor()
			runQuerySession(conn, c)
			c.close()
			
