from datetime import datetime, timedelta
import time
from calendar import monthrange

#
# returns an epoch representing earliest synch date : 1514764800
#
def get_veloclicks_start_epoch():
	# year, mon, day etc month and day start at 1
	# https://docs.python.org/2/library/time.html#time.struct_time
	vc_start_tuple	= (2016, 1, 1, 0, 0, 0, 0, 1, -1)
	ve_start_epoch = time.mktime(vc_start_tuple)
	return ve_start_epoch


# returns epoch for the end of a quarter
# this returns a detailed epoch
# 1577836799.999999 = Tuesday, 31 December 2019 23:59:59.999
# 1577836800.0 = Wednesday, 1 January 2020 00:00:00
#
def get_quarter_start_epoch(year, quarter):
	if (quarter == 1):
		month_start = 1
	else:
		month_start = ((quarter -1) * 3) + 1
	dt_start = datetime(year, month_start, 1, 0, 0, 0)
	return dt_start.timestamp()

# returns the epoch for the start of a quarter
def get_quarter_end_epoch(year, quarter):
	if (quarter == 1):
		month_end = 3
	else:
		month_end = ((quarter -1) * 3) + 3
	day_end = monthrange(year, month_end)[1]
	dt_end = datetime(year, month_end, day_end, 23, 59, 59, 999999)
	return dt_end.timestamp()

# returns epochs for the start and end of the current quarter
def get_current_quarter_start_end_epoch():
	now = datetime.now()
	now_month = now.month
	now_year = now.year
	now_quarter = (now_month - 1) // 3 + 1
	print('now:', now_year, now_quarter, now_month)

	quarter_start_epoch = self.get_quarter_start_epoch(now_year, now_quarter)
	quarter_end_epoch = self.get_quarter_end_epoch(now_year, now_quarter)
	epochs = [quarter_start_epoch, quarter_end_epoch]
	return epochs


# returns epcoh time in s as a float for the start of a month, year
def get_month_start(month, year):
	print(monthrange(year, month))
	week_start = 1 # for monday
	t1 = (year, month, 1, 0, 0, 0 , week_start, 1,0)
	#get epoch
	st_epoch = time.mktime(t1)

	#convert it back to check what it is
	t2 = time.gmtime(st_epoch)
	print("requested month : ", month, year)
	print("month start time: ", time.strftime("%Y-%m-%d %H:%M:%S", t2))
	print("month start epoch : ", st_epoch)

	return st_epoch

# returns epcoh time in s as a float for the end of a month, year
def get_month_end(month, year):
	end_day = monthrange(year, month)[1]
	week_start = 0 # 0 for monday
	t1 = (year, month, end_day, 23, 59, 59 , week_start, 1, 0)
	et_epoch = time.mktime(t1)

	#convert it back to check what it is
	t2 = time.gmtime(et_epoch)
	return et_epoch

#
# returns an epoch signalling the start of the week
#
def get_week_start():
	now 		= datetime.now()
	# get tuple representing start of week
	ws		 	= now - timedelta(days=now.weekday())
	wst 		= ws.timetuple()

	# now create new tuple with same date but set the time to midnight
	new_wst = (wst[0], wst[1], wst[2], 0, 0, 0, wst[6], wst[7], wst[8])
	ws_epoch = time.mktime(new_wst)
	print("Week start tuple :", new_wst)
	print("Week start epoch :", ws_epoch)
	return ws_epoch

#
# returns an epoch representing now
#
def get_now_epoch():
	now 	= datetime.now()
	nowt 	= now.timetuple()
	now_epoch = time.mktime(nowt)
	return now_epoch

def get_now_yr_wk():
	# now is a tuple with year, week, weekday
	now = datetime.now().isocalendar()  # if date is 01/01/2018
	#year, week_num, day_of_week = my_date.isocalendar()

	print("get_now_week. week:", str(now), now[1])
	return now[0], now[1]


#
#
#
def get_now_quarter():
	now = datetime.now()
	now_quarter = (now.month - 1) // 3 + 1
	return now_quarter

#
#
#
def get_current_week_month():
	now = datetime.now()
	nowt = now.timetuple()

#
# returns an epoch representing now
#
def get_now_minus_months():
	now = datetime.now()
	nowt = now.timetuple()
	now_epoch = time.mktime(nowt)
	return now_epoch

def get_current_week_month():
	now = datetime.now()
	nowt = now.timetuple()

#
# retunrs an epoch for a year, month, day
#
def get_time( day, month, year):
	hour = 0,
	minute = 0
	second = 0
	time_tuple = (year, month, day, hour, minute, second, 0, 1, -1)

	epoch = time.mktime(time_tuple)
	return epoch

def get_week():
	print(datetime.date(2010, 6, 16).isocalendar()[1])
