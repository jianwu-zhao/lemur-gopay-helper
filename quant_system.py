# 量化ETF波段交易系统
# 融合 etf.imlam.com 评分 + swing.imlam.com 组合管理

import akshare as ak
import pandas as pd
import numpy as np
import warnings, os, json, base64
from datetime import datetime, timedelta
from pathlib import Path
warnings.filterwarnings('ignore')

# ========== 配置 ==========
INITIAL_CAPITAL = 10000.0
POSITION_PCT = 0.33        # 单只仓位比例
MAX_POSITIONS = 5           # 最大同时持仓数
STOP_ATR_MULTIPLIER = 2.2   # 止损=ATR倍数
MAX_HOLD_DAYS = 15          # 最长持仓天数
TAKE_PROFIT_T1 = 0.08       # 金字塔止盈T1
TAKE_PROFIT_T2 = 0.15       # 金字塔止盈T2
CONSECUTIVE_STOP_LIMIT = 3  # 连续止损上限
COOLDOWN_DAYS = 5           # 冷静期天数
MAX_DRAWDOWN = 0.05         # 最大回撤5%
MIN_MARKET_BREADTH = 0.25   # 最低市场宽度
MARKET_BREADTH_WINDOW = 20

# 候选ETF
ETF_WATCHLIST = [
    ('515220','国泰中证煤炭ETF'),('515880','国泰中证全指通信设备ETF'),
    ('159611','广发中证全指电力ETF'),('159259','易方达国证成长100ETF'),
    ('588170','华夏上证科创板半导体材料设备ETF'),('562950','易方达中证消费电子主题ETF'),
    ('159667','国泰中证机床ETF'),('159930','汇添富中证能源ETF'),
    ('562500','华夏中证机器人ETF'),('159326','华夏中证电网设备主题ETF'),
    ('562800','嘉实中证稀有金属主题ETF'),('516150','嘉实中证稀土产业ETF'),
    ('512690','酒ETF'),('512660','国泰中证军工ETF'),
    ('512980','广发中证传媒ETF'),('513050','易方达中证海外中国互联网50(QDII-ETF)'),
    ('512200','南方中证全指房地产ETF'),('512800','华宝中证银行ETF'),
    ('515790','华泰柏瑞中证光伏产业ETF'),('159869','华夏中证动漫游戏ETF'),
    ('518880','华安黄金ETF'),
]

# ========== 数据层 ==========
import time as _time
def get_hist(etf_code, end_date, retries=3):
    end = datetime.strptime(end_date, '%Y%m%d')
    start = end - timedelta(days=400)
    prefix = 'sh' if etf_code.startswith(('5','6')) else 'sz'
    symbol = prefix + etf_code
    for a in range(retries):
        try:
            df = ak.fund_etf_hist_sina(symbol)
            if df.empty:
                if a < retries-1: _time.sleep(2); continue
                return None, None, None
            df = df.rename(columns={'date':'日期','open':'开盘价','high':'最高价','low':'最低价','close':'收盘'})
            df['日期'] = pd.to_datetime(df['日期'])
            df = df[(df['日期'] >= start) & (df['日期'] <= end)].copy()
            if df.empty:
                if a < retries-1: _time.sleep(2); continue
                return None, None, None
            df = df.set_index('日期').sort_index()
            for x in ['收盘','最高价','最低价','开盘价']:
                if x in df.columns: df[x]=pd.to_numeric(df[x],errors='coerce')
            wk = df.resample('W-FRI').agg({'收盘':'last','最高价':'max','最低价':'min','开盘价':'first'}).dropna().reset_index()
            mo = df.resample('ME').agg({'收盘':'last','最高价':'max','最低价':'min','开盘价':'first'}).dropna().reset_index()
            return df.reset_index(), wk, mo
        except Exception as e:
            if a < retries-1: _time.sleep(2*(a+1))
            continue
    return None, None, None

def calc_indicators(df):
    close=df['收盘'].values.astype(float); high=df['最高价'].values.astype(float); low=df['最低价'].values.astype(float)
    s=pd.Series(close)
    e1=s.ewm(span=12,adjust=False).mean(); e2=s.ewm(span=26,adjust=False).mean()
    macd=e1-e2; signal=macd.ewm(span=9,adjust=False).mean(); hist=macd-signal
    sma20=s.rolling(20).mean(); std20=s.rolling(20).std(); upper=sma20+2*std20; lower=sma20-2*std20
    delta=s.diff(); gain=delta.clip(lower=0); loss=-delta.clip(upper=0)
    ag=gain.rolling(14).mean(); al=loss.rolling(14).mean(); rs=ag/al; rsi=100-(100/(1+rs))
    tr=pd.DataFrame({'hl':high-low,'hc':np.abs(high-np.roll(close,1)),'lc':np.abs(low-np.roll(close,1))}).max(axis=1)
    atr=pd.Series(tr).rolling(14).mean()
    bp=(close[-1]-lower.iloc[-1])/(upper.iloc[-1]-lower.iloc[-1])*100 if upper.iloc[-1]!=lower.iloc[-1] else 50
    return {
        'close':close[-1],'macd':macd.iloc[-1],'signal':signal.iloc[-1],'hist':hist.iloc[-1],'hist_p':hist.iloc[-2] if len(hist)>1 else 0,
        'upper':upper.iloc[-1],'lower':lower.iloc[-1],'sma20':sma20.iloc[-1],'bp':bp,'rsi':rsi.iloc[-1],
        'atr':atr.iloc[-1],'atr_pct':(atr.iloc[-1]/close[-1]*100) if close[-1]!=0 else 0
    }

def score_trend(df, period='daily'):
    min_r={'daily':20,'weekly':10,'monthly':6}
    if df is None or df.empty or len(df)<min_r.get(period,10): return 0,''
    ind=calc_indicators(df); c=ind['close']; sm=ind['sma20']; up=ind['upper']; lw=ind['lower']
    h=ind['hist']; hp=ind['hist_p']; r=ind['rsi']; bp=ind['bp']
    sc=0; tags=[]
    if c>sm: sc+=1.5; tags.append('短均多头')
    else: sc-=1.5; tags.append('盘整' if c>lw else '空头通道')
    if c>=up: sc+=1; tags.append('放量上轨' if (c-sm)/sm*100>5 else '缩量上轨')
    elif c<=lw: sc-=1.5; tags.append('放量下轨')
    if h>0:
        sc+=1; sc+=0.5 if h>hp else 0; tags.append('红柱放大' if h>hp else '红柱缩小')
    else:
        sc-=1; sc-=0.5 if h<hp else 0; tags.append('绿柱放大' if h<hp else '绿柱缩小')
    if ind['macd']>ind['signal']: sc+=0.5
    if r>70: tags.append(f'RSI{r:.0f}')
    elif r<30: tags.append(f'RSI{r:.0f}')
    if period=='monthly': sc=max(-5,min(5,sc*.9))
    elif period=='weekly': sc=max(-6,min(6,sc))
    else: sc=max(-4,min(4,sc))
    return round(sc,1),' '.join(tags[:5])

# ========== 评分引擎 ==========
def score_etf(code, name, end_date):
    d,w,m = get_hist(code,end_date)
    if d is None: return None
    ds,dt = score_trend(d,'daily')
    ws,wt = score_trend(w,'weekly')
    ms,mt = score_trend(m,'monthly')
    total = (ms+ws+ds)*1.5
    ind = calc_indicators(d)
    closes = d['收盘'].values.astype(float)
    c5=round((closes[-1]/closes[-5]-1)*100,1) if len(closes)>=5 else 0
    c20=round((closes[-1]/closes[-20]-1)*100,1) if len(closes)>=20 else 0
    return {
        'code':code,'name':name,'total':total,'monthly':ms,'weekly':ws,'daily':ds,
        'rsi':round(ind['rsi'],1),'atr_pct':round(ind['atr_pct'],1),'bp':round(ind['bp'],1),
        'close':ind['close'],'atr':ind['atr'],'chg5':c5,'chg20':c20,
        'monthly_tags':ms,'weekly_tags':ws,'daily_tags':dt,
    }

# ========== 组合管理 ==========
class Portfolio:
    def __init__(self, capital=INITIAL_CAPITAL):
        self.capital=capital
        self.positions={}  # code -> {qty,cost,entry_date,stop,hold_day}
        self.cash=capital
        self.trades=[]  # 交易记录
        self.peak=capital
        self.max_dd=0
        self.consecutive_stops=0
        self.cooldown_until=None
        self.equity_curve=[]

    def market_value(self, prices):
        mv=sum(p.get(code,0)*pos['qty'] for code,pos in self.positions.items())
        return mv

    def total_equity(self, prices):
        return self.cash+self.market_value(prices)

    def update_peak(self, prices):
        eq=self.total_equity(prices)
        if eq>self.peak: self.peak=eq
        dd=(self.peak-eq)/self.peak
        if dd>self.max_dd: self.max_dd=dd
        self.equity_curve.append({'date':prices.get('_date',''),'equity':eq,'peak':self.peak,'dd':dd})
        return eq,dd

    def can_trade(self, prices):
        if self.cooldown_until and prices.get('_date','')<self.cooldown_until:
            return False,'冷静期'
        if self.max_dd>MAX_DRAWDOWN:
            return False,f'回撤{self.max_dd:.1%}超限'
        if self.consecutive_stops>=CONSECUTIVE_STOP_LIMIT:
            return False,'连续止损超限'
        return True,''

    def buy(self, code, price, date, reason=''):
        if len(self.positions)>=MAX_POSITIONS: return False,'已达最大持仓'
        amount=self.capital*POSITION_PCT
        qty=int(amount/price/100)*100
        if qty<100: return False,'资金不足'
        cost=qty*price
        if cost>self.cash: return False,'现金不足'
        self.positions[code]={'qty':qty,'cost':price,'entry_date':date,'hold_day':0,'stop':price*(1-STOP_ATR_MULTIPLIER*0.03)}
        self.cash-=cost
        self.trades.append({'date':date,'action':'买入','code':code,'qty':qty,'price':price,'reason':reason})
        return True,''

    def sell(self, code, price, date, reason=''):
        if code not in self.positions: return False,'未持仓'
        pos=self.positions[code]
        qty=pos['qty']; proceeds=qty*price
        pl=(price-pos['cost'])*qty
        self.cash+=proceeds
        self.trades.append({'date':date,'action':'卖出','code':code,'qty':qty,'price':price,
                            'pl':round(pl,2),'pl_pct':round(pl/(pos['cost']*qty)*100,2),'reason':reason})
        del self.positions[code]
        return True,''

    def check_stops(self, prices, date):
        for code in list(self.positions.keys()):
            price=prices.get(code)
            if not price: continue
            pos=self.positions[code]
            if price<=pos['stop']:
                self.sell(code, price, date, f'止损:现{price:.3f}≤{pos["stop"]:.3f}')
                self.consecutive_stops+=1
                return True
        return False

    def check_takeprofit(self, prices, date):
        for code in list(self.positions.keys()):
            price=prices.get(code)
            if not price: continue
            pos=self.positions[code]
            pl_pct=(price-pos['cost'])/pos['cost']
            if pl_pct>=TAKE_PROFIT_T2:
                self.sell(code, price, date, f'金字塔止盈T2:浮盈{pl_pct:.1%}≥{TAKE_PROFIT_T2:.0%}')
                self.consecutive_stops=0
            elif pl_pct>=TAKE_PROFIT_T1:
                # T1止盈半仓
                half=int(pos['qty']/200)*100
                if half>=100:
                    proceeds=half*price
                    self.cash+=proceeds
                    pos['qty']-=half
                    self.trades.append({'date':date,'action':'减仓','code':code,'qty':half,'price':price,
                                        'pl':round((price-pos['cost'])*half,2),'reason':f'金字塔止盈T1:浮盈{pl_pct:.1%}≥{TAKE_PROFIT_T1:.0%}'})
                    if pos['qty']==0: del self.positions[code]
                    self.consecutive_stops=0

    def advance_day(self, prices, date):
        for pos in self.positions.values():
            pos['hold_day']+=1
        eq=self.total_equity(prices)
        if self.consecutive_stops>=CONSECUTIVE_STOP_LIMIT:
            self.cooldown_until=(datetime.strptime(date,'%Y-%m-%d')+timedelta(days=COOLDOWN_DAYS)).strftime('%Y-%m-%d')
        return eq

# ========== 市场环境 ==========
def market_assessment(results):
    if not results: return '数据不足',0,0
    scores=[r['total'] for r in results if r]
    avg=np.mean(scores) if scores else 0
    bull=sum(1 for r in results if r and r['total']>5)
    bear=sum(1 for r in results if r and r['total']<-5)
    width=bull/len(results) if results else 0
    ratio=(bull+1)/(bear+1)
    if avg>2: status='偏多'
    elif avg<-2: status='偏空'
    elif avg>0: status='偏多震荡'
    else: status='偏空震荡'
    return status,round(width*100,1),round(ratio,2)

# ========== HTML报告 ==========
def gen_html(portfolio, results, candidates, status, width, ratio, date_str):
    now=date_str
    price_dict={}
    if results:
        price_dict={c.get('code',''):c.get('close',0) for c in results if c}
    eq=portfolio.total_equity(price_dict)
    mkt_val=portfolio.market_value(price_dict)
    pl=eq-INITIAL_CAPITAL

    def price_of(code, results):
        for r in results:
            if r and r['code']==code: return r['close']
        return 0

    cand_rows=''
    for c in (candidates or [])[:8]:
        tags=[]
        if c['monthly']>2 and c['weekly']>2: tags.append('📈 三周期共振')
        if c.get('daily_tags') and '顶背离' in c['daily_tags']: tags.append('⚠️ 顶背离')
        if c.get('daily_tags') and '底背离' in c['daily_tags']: tags.append('⚡️ 底背离')
        if c['weekly']>4: tags.append('🚀 主升浪')
        if c['weekly']<-4: tags.append('❄️ 主跌浪')
        cand_rows+=f'''
<tr>
<td><b>{c['name'][:12]}</b><br><span style="font-size:10px;color:#94a3b8;">{c['code']}</span></td>
<td class="number">{c['monthly']:+.1f}</td>
<td class="number">{c['weekly']:+.1f}</td>
<td class="number">{c['daily']:+.1f}</td>
<td class="number {'' if c['total']<0 else 'is-up'}">{c['total']:+.1f}</td>
<td class="number">{c['rsi']}</td>
<td class="number">{c['chg5']:+.1f}%</td>
<td class="number">{c['chg20']:+.1f}%</td>
<td><small>{' '.join(tags)}</small></td>
</tr>'''

    pos_rows=''
    for code,pos in portfolio.positions.items():
        r=next((x for x in results if x and x['code']==code),None)
        price=r['close'] if r else price_of(code,results)
        if not price: continue
        val=price*pos['qty']; pl_pos=(price-pos['cost'])*pos['qty']; pl_pct=(price-pos['cost'])/pos['cost']
        stop_px=pos['stop']
        stop_dist=(price-stop_px)/price*100 if price else 0
        pct=int(pos['hold_day']/MAX_HOLD_DAYS*100)
        pos_rows+=f'''
<tr>
<td><b>{r['name'][:12] if r else code}</b><br><span style="font-size:10px;color:#94a3b8;">{code}</span></td>
<td class="number">{pos['qty']}</td>
<td class="number">{pos['cost']:.3f}</td>
<td class="number">{price:.3f}</td>
<td class="number">¥{val:.0f}</td>
<td class="{'is-up' if pl_pos>=0 else 'is-down'}">{pl_pct:+.2%}</td>
<td class="number">{stop_px:.3f}<br><small>距{stop_dist:.1f}%</small></td>
<td><div class="bar"><span style="width:{pct}%"><small>{pos['hold_day']}/{MAX_HOLD_DAYS}</small></span></div></td>
</tr>'''

    trade_rows=''
    for t in reversed(portfolio.trades[-30:]):
        act=t['action']
        cls='act-buy' if act=='买入' else ('act-sell' if '卖出' in act else 'act-partial')
        pl_str=f'<span class="{"is-up" if t.get("pl",0)>=0 else "is-down"}">{t.get("pl",0):+.2f}</span>' if t.get('pl',0)!=0 else '<span class="muted">-</span>'
        trade_rows+=f'''
<tr>
<td>{t['date']}</td>
<td><span class="tag {cls}">{act}</span></td>
<td><b>{t['code']}</b></td>
<td class="number">{t.get('qty',0)}</td>
<td class="number">{t.get('price',0):.3f}</td>
<td>{pl_str}</td>
<td style="font-size:11px;color:#94a3b8;">{t.get('reason','')}</td>
</tr>'''

    env=status
    env_cls='bull' if '偏多' in env else ('bear' if '偏空' in env else 'neutral')
    html=f'''<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ETF量化波段交易系统</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#0f172a;color:#e2e8f0;padding:16px}}
h1{{font-size:18px}}
h2{{font-size:15px;margin:20px 0 10px}}
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;margin:10px 0}}
.kpi{{background:#1e293b;border-radius:12px;padding:14px}}
.kpi label{{font-size:11px;color:#94a3b8;display:block}}
.kpi strong{{font-size:20px;display:block;margin:4px 0}}
table{{width:100%;border-collapse:collapse;font-size:12px;margin:8px 0}}
th{{background:#1e293b;padding:8px;text-align:left;white-space:nowrap;font-size:11px}}
td{{padding:8px;border-top:1px solid #1e293b;font-size:12px}}
.is-up{{color:#86efac}} .is-down{{color:#fca5a5}} .number{{font-variant-numeric:tabular-nums}}
.env{{display:inline-block;padding:4px 12px;border-radius:8px;font-size:13px;font-weight:700}}
.env.bull{{background:#166534;color:#86efac}}
.env.bear{{background:#7f1d1d;color:#fca5a5}}
.env.neutral{{background:#451a03;color:#fdba74}}
.tag{{display:inline-block;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:600}}
.act-buy{{background:#16653433;color:#86efac;border:1px solid:#166534}}
.act-sell{{background:#7f1d1d33;color:#fca5a5;border:1px solid:#7f1d1d}}
.act-partial{{background:#1e3a8a33;color:#93c5fd;border:1px solid:#1e3a8a}}
.bar{{background:#334155;border-radius:8px;overflow:hidden;height:20px;min-width:80px}}
.bar span{{display:block;height:100%;background:#2563eb;border-radius:8px;color:#fff;font-size:10px;text-align:center;line-height:20px}}
.footer{{font-size:11px;color:#64748b;margin:30px 0;text-align:center}}
.pos{{background:#1e293b;color:#e2e8f0}}
.neg{{background:#1e293b;color:#e2e8f0}}
</style></head><body>
<h1>📡 ETF量化波段交易系统</h1>
<p style="color:#94a3b8;">{now}</p>
<p>大盘: <span class="env {env_cls}">{env}</span> 宽度{width if width else 0}% 多空比{ratio if ratio else 0}</p>
<div class="kpi-grid">
<div class="kpi"><label>总资产</label><strong class="number">¥{eq:.0f}</strong></div>
<div class="kpi"><label>现金</label><strong class="number">¥{portfolio.cash:.0f}</strong></div>
<div class="kpi"><label>持仓市值</label><strong class="number">¥{mkt_val:.0f}</strong></div>
<div class="kpi"><label>累计盈亏</label><strong class="number {'is-up' if pl>=0 else 'is-down'}">{pl:+.0f}</strong><small>{pl/INITIAL_CAPITAL:.2%}</small></div>
<div class="kpi"><label>当前回撤</label><strong class="number {'is-down' if portfolio.max_dd>0 else 'is-up'}">-{portfolio.max_dd:.2%}</strong></div>
<div class="kpi"><label>盈利因子</label><strong class="number">{(sum(t.get('pl',0) for t in portfolio.trades if t.get('pl',0)>0)+1)/(abs(sum(t.get('pl',0) for t in portfolio.trades if t.get('pl',0)<0))+1):.2f}</strong></div>
<div class="kpi"><label>持仓数</label><strong class="number">{len(portfolio.positions)}/{MAX_POSITIONS}</strong></div>
<div class="kpi"><label>连续止损</label><strong class="number">{portfolio.consecutive_stops}/{CONSECUTIVE_STOP_LIMIT}</strong></div>
</div>

<h2>📊 持仓详情</h2>
<table><thead><tr><th>标的</th><th>数量</th><th>成本</th><th>现价</th><th>市值</th><th>盈亏</th><th>止损线</th><th>周期</th></tr></thead>
<tbody>{pos_rows or '<tr><td colspan="8" style="color:#94a3b8;text-align:center;">空仓</td></tr>'}</tbody></table>

<h2>🎯 候选评分前8</h2>
<table><thead><tr><th>标的</th><th>月</th><th>周</th><th>日</th><th>总分</th><th>RSI</th><th>5日</th><th>20日</th><th>信号</th></tr></thead>
<tbody>{cand_rows}</tbody></table>

<h2>📝 最近交易</h2>
<table><thead><tr><th>日期</th><th>操作</th><th>标的</th><th>数量</th><th>价格</th><th>盈亏</th><th>原因</th></tr></thead>
<tbody>{trade_rows or '<tr><td colspan="7" style="color:#94a3b8;text-align:center;">暂无交易</td></tr>'}</tbody></table>

<h2>🛡️ 风控</h2>
<div class="kpi-grid">
<div class="kpi"><label>冷静期</label><strong>{portfolio.cooldown_until or '无'}</strong></div>
<div class="kpi"><label>日回撤</label><strong class="{'is-down' if portfolio.max_dd>0 else 'is-up'}">-{portfolio.max_dd:.2%}</strong></div>
<div class="kpi"><label>止损限</label><strong>{portfolio.consecutive_stops}/{CONSECUTIVE_STOP_LIMIT}</strong></div>
<div class="kpi"><label>可交易</label><strong>{'✅' if portfolio.can_trade({'date':now})[0] else '❌'}</strong></div>
</div>
<div class="footer">⚠️ 仅供量化研究，不构成投资建议</div>
</body></html>'''
    return html

# ========== 主流程 ==========
def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--date', help='回测日期YYYYMMDD')
    parser.add_argument('--start', default='20260501', help='回测开始')
    parser.add_argument('--end', default='20260604', help='回测结束')
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--port', type=int, default=8895)
    args=parser.parse_args()

    if args.date:
        # 单日运行模式
        run_day(args.date, args.serve, args.port)
    else:
        # 回测模式
        backtest(args.start, args.end)

def run_day(date_str, serve=False, port=8895):
    print(f'📡 ETF量化系统 - {date_str}')
    scores=[]
    for code,name in ETF_WATCHLIST:
        print(f'  {code} {name[:12]}...',end=' ')
        r=score_etf(code,name,date_str)
        if r: scores.append(r); print(f'{r["total"]:+.1f}')
        else: print('跳过')
    status,width,ratio=market_assessment(scores)
    scores.sort(key=lambda x:x['total'],reverse=True)
    candidates=[s for s in scores if s['total']>3][:8]
    print(f'大盘: {status} 宽度{width}% 候选{len(candidates)}')

    pf=Portfolio()
    prices={r['code']:r['close'] for r in scores}
    pf.advance_day(prices,date_str[:4]+'-'+date_str[4:6]+'-'+date_str[6:])

    html=gen_html(pf,scores,candidates,status,width,ratio,date_str)
    out=Path('output'); out.mkdir(exist_ok=True)
    fp=out/'quant-report.html'; fp.write_text(html,encoding='utf-8')
    print(f'✅ {fp.resolve()}')
    if serve:
        print(f'🌐 http://0.0.0.0:{port}/')
        import http.server,socketserver
        h=html.encode(); f=__file__
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.send_header('Content-Type','text/html;charset=utf-8')
                self.send_header('Content-Length',str(len(h))); self.end_headers(); self.wfile.write(h)
            def log_message(self,*a): pass
        with socketserver.TCPServer(('0.0.0.0',port),H) as s: s.serve_forever()

def backtest(start_date, end_date):
    print(f'📡 回测 {start_date} ~ {end_date}')
    dates=pd.date_range(start=start_date,end=end_date,freq='B').strftime('%Y%m%d').tolist()
    pf=Portfolio()
    all_trades=[]
    for i,dt in enumerate(dates):
        if i%5==0: print(f'  {dt} pos:{len(pf.positions)} eq:{pf.capital:.0f}')
        scores=[]
        for code,name in ETF_WATCHLIST:
            r=score_etf(code,name,dt)
            if r: scores.append(r)
        if not scores: continue
        status,width,ratio=market_assessment(scores)
        scores.sort(key=lambda x:x['total'],reverse=True)
        candidates=[s for s in scores if s['total']>3]
        prices={r['code']:r['close'] for r in scores}
        d=dt[:4]+'-'+dt[4:6]+'-'+dt[6:]; prices['_date']=d
        eq=pf.advance_day(prices,d)
        pf.check_stops(prices,d)
        pf.check_takeprofit(prices,d)
        can_trade,reason=pf.can_trade(prices)
        if can_trade and len(pf.positions)<MAX_POSITIONS and candidates:
            for c in candidates[:3]:
                if c['code'] not in pf.positions:
                    ok,msg=pf.buy(c['code'],c['close'],d,f'优选{c["total"]:.1f}/RPS{c.get("rsi",0):.0f}')
                    if ok: break
    print(f'✅ 回测结束')
    print(f'   最终资产: ¥{pf.capital:.0f}')
    print(f'   交易次数: {len(pf.trades)}')
    print(f'   最大回撤: {pf.max_dd:.2%}')
    total_pl=sum(t.get('pl',0) for t in pf.trades)
    print(f'   总盈亏: {total_pl:+.2f}')
    # 保留交易记录到文件
    import json
    Path('output').mkdir(exist_ok=True)
    with open('output/backtest_trades.json','w') as f:
        json.dump(pf.trades,f,ensure_ascii=False,indent=2)
    print(f'   交易记录: output/backtest_trades.json')

if __name__=='__main__':
    main()
