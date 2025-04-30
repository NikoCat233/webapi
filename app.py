from apscheduler.schedulers.asyncio import AsyncIOScheduler
from numbermanager import NumberManager
from fastapi import FastAPI, Response
import requests
from threading import Lock
import time
from datetime import datetime
from timecalc import time_since

app = FastAPI()

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'Cache-Control': 'max-age=0',
    'If-Modified-Since': 'Wed, 30 Apr 2025 09:51:46 GMT',
    'Priority': 'u=0, i',
    'Sec-Ch-Ua': '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0'
}

scheduler = AsyncIOScheduler()

banHistoryExample = {
    "time":0,
    "formated":"00:00:00",
    "watchdog":False, # if the ban is from watchdog
    "number":1,
}

banHistory = []
LockBanHistory = Lock()

watchdog = {
    "last_minute":0,
    "last_day":-1,
    "total":0,
}

staffHalfHourCalc = NumberManager()

staff = {
    "last_half_hour":0,
    "last_day":-1,
    "total":0,
}

lastUpdated = time.time()

@scheduler.scheduled_job('interval', seconds=4)
async def _():
    global staff,watchdog,staffHalfHourCalc,banHistory,LockBanHistory,lastUpdated
    punishmentStats = requests.get('https://api.plancke.io/hypixel/v1/punishmentStats',headers=headers).json()['record']
    staff['total'] = punishmentStats['staff_total']
    watchdog['total'] = punishmentStats['watchdog_total']

    if staff['last_day'] == -1 or watchdog['last_day'] == -1:
        staff['last_day'] = punishmentStats['staff_rollingDaily']
        watchdog['last_day'] = punishmentStats['watchdog_rollingDaily']
        lastUpdated = time.time()
        return

    wdiff = punishmentStats['watchdog_rollingDaily'] - watchdog['last_day']
    sdiff = punishmentStats['staff_rollingDaily'] - staff['last_day']

    if wdiff <= 0 and sdiff <= 0:
        watchdog['last_day'] = punishmentStats['watchdog_rollingDaily']
        staff['last_day'] = punishmentStats['staff_rollingDaily']
        lastUpdated = time.time()
        return

    now = time.time()
    ndatetime = datetime.fromtimestamp(now)

    with LockBanHistory:
        while len(banHistory) > 10:
            banHistory.pop()
        
        if wdiff > 0:
            data = banHistoryExample.copy()
            data['time'] = now
            data['watchdog'] = True
            data['number'] = wdiff
            data['formated'] = f'{ndatetime:%H:%M:%S}'
            banHistory.insert(0,data)

        if sdiff > 0:
            data = banHistoryExample.copy()
            data['time'] = now
            data['watchdog'] = False
            data['number'] = sdiff
            data['formated'] = f'{ndatetime:%H:%M:%S}'
            staffHalfHourCalc.add(sdiff)
            banHistory.insert(0,data)

    watchdog['last_day'] = punishmentStats['watchdog_rollingDaily']
    staff['last_day'] = punishmentStats['staff_rollingDaily']
    lastUpdated = time.time()


# remove the number that is older than 30 minutes
@scheduler.scheduled_job('interval', seconds=1)
async def _():
    staffHalfHourCalc.remove()
    staff['last_half_hour'] = staffHalfHourCalc.get_count()

@app.on_event("startup")
async def _():
    scheduler.start()

@app.on_event("shutdown")
async def _():
    scheduler.shutdown()


@app.get('/')
async def _():
    global staff,watchdog,banHistory,LockBanHistory,lastUpdated
    with LockBanHistory:
        return {'staff':staff,'watchdog':watchdog,'banHistory':banHistory,'lastUpdated':{'timestamp':lastUpdated,'formated':datetime.fromtimestamp(lastUpdated).strftime('%H:%M:%S')}}

def getAgo(gtime):
    return f'{time.strftime("%H:%M:%S", time.localtime(gtime))} {time_since(gtime)}'

@app.get('/wdr')
async def _():
    global watchdog,staff,banHistory,LockBanHistory,lastUpdated
    with LockBanHistory:
        list = f"""🐕🐕 Hypixel Ban Tracker 👮‍👮‍
[🐕] 过去一分钟有 {watchdog['last_minute']} 人被狗咬了
[🐕‍] 狗在过去二十四小时内已封禁 {watchdog['last_day']} 人,

[👮‍] 过去的半小时有 {staff['last_half_hour']} 人被逮捕了
[👮‍] 客服在过去二十四小时内已封禁 {staff['last_day']} 人,

上次更新: {getAgo(lastUpdated) }
"""
        if len(banHistory) == 0:
            list += '无最近封禁'
        else:
            list += '最近封禁记录:\n'
            for ban in banHistory:
                list += f'[{'🐕' if ban['watchdog'] else '👮'}] [{ban['formated']}] banned {ban['number']} player.\n'
            list = list[:-1]

    return {'wdr':list}

@app.get('/wdr/raw')
async def _():
    global watchdog,staff,banHistory,LockBanHistory,lastUpdated
    with LockBanHistory:
        list = f"""🐕🐕 Hypixel Ban Tracker 👮‍👮‍
[🐕] 过去一分钟有 {watchdog['last_minute']} 人被狗咬了
[🐕‍] 狗在过去二十四小时内已封禁 {watchdog['last_day']} 人,

[👮‍] 过去的半小时有 {staff['last_half_hour']} 人被逮捕了
[👮‍] 客服在过去二十四小时内已封禁 {staff['last_day']} 人,

上次更新: {getAgo(lastUpdated) }
"""
        if len(banHistory) == 0:
            list += '无最近封禁'
        else:
            list += '最近封禁记录:\n'
            for ban in banHistory:
                list += f'[{'🐕' if ban['watchdog'] else '👮'}] [{ban['formated']}] banned {ban['number']} player.\n'
            list = list[:-1]

    return Response(content=list, media_type='text/plain')