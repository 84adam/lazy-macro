# lazy-macro.py

import requests
from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
from decouple import config
import pandas as pd
import math
import numpy as np
import pytz
from datetime import datetime, timezone
import json
import time
import calendar
import sys
import io

# API NINJA

API_NINJA_KEY = config('API_NINJA_KEY')

def commodity_price(commodity):
    """
    API NINJA: Commodity Price
    """
    api_url = f'https://api.api-ninjas.com/v1/commodityprice?name={commodity}'
    response = requests.get(api_url, headers={'X-Api-Key': API_NINJA_KEY})
    if response.status_code == requests.codes.ok:
        p = response.json()['price']
        return p
    else:
        return f"Error: {response.status_code}, {response.text}"

def equity_price(symbol):
    api_url = f'https://api.api-ninjas.com/v1/stockprice?ticker={symbol}'
    response = requests.get(api_url, headers={'X-Api-Key': API_NINJA_KEY})
    if response.status_code == requests.codes.ok:
        p = response.json()['price']
        return p
    else:
        return f"Error: {response.status_code}, {response.text}"

# ALPHA VANTAGE

ALPHA_VANTAGE_API_KEY = config('ALPHA_VANTAGE_API_KEY')

def get_bond_yield(maturity):
    allowed_maturities = ['3month', '2year', '5year', '7year', '10year', '30year']
    if maturity not in allowed_maturities:
        raise Exception(f"maturity of '{maturity}' not in allowed list of maturities: {allowed_maturities}")
    url = f'https://www.alphavantage.co/query?function=TREASURY_YIELD&interval=daily&maturity={maturity}&apikey={ALPHA_VANTAGE_API_KEY}'
    data = None
    try:
        r = requests.get(url)
        data = r.json()
        curr_yield = float(data['data'][0]['value']) / 100
    except Exception as e:
        raise Exception(f"Error fetching bond yield data: {e} - {data}")
    return curr_yield

# COIN MARKET CAP

CMC_API_KEY = config('CMC_API_KEY')

def get_crypto_price(symbol):
    url = ' https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest'
    parameters = {
      'symbol':symbol
    }
    headers = {
      'Accepts': 'application/json',
      'X-CMC_PRO_API_KEY': CMC_API_KEY,
    }
    session = Session()
    session.headers.update(headers)
    try:
        response = session.get(url, params=parameters)
        data = json.loads(response.text)
        d = data['data'][symbol][0]['quote']['USD']['price']
        return d
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        return e

# MACRO DATA FROM FEDERAL RESERVE

def fred_ema_3d(df):
    """
    Get 3-day EMA for FRED data (yields, inflation, inflation-swaps)
    """
    per = 1
    col = 1 # column used for calculating exponential moving averages
    df['e3'] = df.iloc[:,col].ewm(span=(3*per),adjust=False, ignore_na=True).mean()
    # SEE: https://stackoverflow.com/questions/40742364/pandas-rolling-standard-deviation
    df['sd3'] = df['e3'].rolling(3).std()
    df = df.round({'e3':2, 'sd3':2})
    return df

def fred_ema_8d(df):
    """
    Get 8-day EMA for FRED data (yields, inflation, inflation-swaps)
    """
    per = 1
    col = 1 # column used for calculating exponential moving averages
    df['e8'] = df.iloc[:,col].ewm(span=(8*per),adjust=False, ignore_na=True).mean()
    # SEE: https://stackoverflow.com/questions/40742364/pandas-rolling-standard-deviation
    df['sd8'] = df['e8'].rolling(8).std()
    df = df.round({'e8':2, 'sd8':2})
    return df

def yield_two_year():
    """
    2 Year Yield
    - Market Yield on U.S. Treasury Securities at 2-Year Constant Maturity
    - Quoted on an Investment Basis
    - SEE: https://fred.stlouisfed.org/series/DGS2
    Returns: 8-day EMA of 2 year yield
    """
    url = """https://fred.stlouisfed.org/graph/fredgraph.csv?bgcolor=%23e1e9f0&chart_type=line&drp=0&fo=open%20sans&graph_bgcolor=%23ffffff&height=450&mode=fred&recession_bars=on&txtcolor=%23444444&ts=12&tts=12&width=1168&nt=0&thu=0&trc=0&show_legend=yes&show_axis_titles=yes&show_tooltip=yes&id=DGS2&scale=left&cosd=2021-10-07&line_color=%234572a7&link_values=false&line_style=solid&mark_type=none&mw=3&lw=2&ost=-99999&oet=99999&mma=0&fml=a&fq=Daily&fam=avg&fgst=lin&fgsnd=2020-02-01&line_index=1&transformation=lin&nd=1976-06-01
    """
    s = requests.get(url).content
    df = pd.read_csv(io.StringIO(s.decode('utf-8')))
    df = df[df.DGS2 != "."]
    # get 8-day EMA
    df = fred_ema_8d(df)
    # get 3-day EMA
    df3 = fred_ema_3d(df)
    full_8d = list(df3['e3'][-8::])
    last_ema_8d = list(df['e8'][-1::])[0]
    return last_ema_8d, full_8d

def breakeven_five_year():
    """
    5 Year Inflation Breakevens
    - The breakeven inflation rate represents a measure of expected inflation derived from 
    5-Year Treasury Constant Maturity Securities (BC_5YEAR) and 5-Year Treasury 
    Inflation-Indexed Constant Maturity Securities (TC_5YEAR). The latest value implies 
    what market participants expect inflation to be in the next 5 years, on average.
    - SEE: https://fred.stlouisfed.org/series/T5YIE
    Returns: 8-day EMA of 5-year Inflation Breakevens
    """
    url = """https://fred.stlouisfed.org/graph/fredgraph.csv?bgcolor=%23e1e9f0&chart_type=line&drp=0&fo=open%20sans&graph_bgcolor=%23ffffff&height=450&mode=fred&recession_bars=on&txtcolor=%23444444&ts=12&tts=12&width=1168&nt=0&thu=0&trc=0&show_legend=yes&show_axis_titles=yes&show_tooltip=yes&id=T5YIE&scale=left&cosd=2003-01-02&line_color=%234572a7&link_values=false&line_style=solid&mark_type=none&mw=3&lw=2&ost=-99999&oet=99999&mma=0&fml=a&fq=Daily&fam=avg&fgst=lin&fgsnd=2020-02-01&line_index=1&transformation=lin&nd=2003-01-02
    """
    s = requests.get(url).content
    df = pd.read_csv(io.StringIO(s.decode('utf-8')))
    df = df[df.T5YIE != "."]
    # get 8-day EMA
    df = fred_ema_8d(df)
    # get 3-day EMA
    df3 = fred_ema_3d(df)
    full_8d = list(df3['e3'][-8::])
    last_ema_8d = list(df['e8'][-1::])[0]
    return last_ema_8d, full_8d

def get_expected_inflation_rate():
    """
    Get the average of the 2Y yield and the 5Y inflation breakeven rate
    """
    expected_inflation_rate = 0.0
    try:
        be5y, be5y_8d = breakeven_five_year()
        y2y, y2y_8d = yield_two_year()
        # standard avg
        std_avg = (be5y + y2y) / 2
        # modified average counting 2Y as 2/3 of weighting
        mod_avg = (be5y + y2y + y2y) / 3
        avg = mod_avg
        expected_inflation_rate = avg / 100
        expected_inflation_rate = round(expected_inflation_rate, 4)
        
        curr_hr = f"Expected Inflation = {expected_inflation_rate*100:.3f}%"
        b5 = f"- 5YBE: {be5y}% (8d EMA)"
        b5_full = f"- 5YBE% hist: {be5y_8d}"
        y2 = f"- 2Y: {y2y}% (8d EMA)"
        y2_full = f"- 2Y% hist: {y2y_8d}"
        
        message = f"{curr_hr}\n{b5}\n{b5_full}\n{y2}\n{y2_full}"
    except Exception as e:
        raise Exception(f"ERROR: Could not derive expected inflation rate: {e}")
    return expected_inflation_rate, b5, b5_full, y2, y2_full

if __name__ == '__main__':
    
    expected_inflation, b5, b5_full, y2e, y2e_full = get_expected_inflation_rate()
    
    m3 = get_bond_yield('3month')
    y2 = get_bond_yield('2year')
    y5 = get_bond_yield('5year')
    y10 = get_bond_yield('10year')
    y30 = get_bond_yield('30year')

    risk_free_rate = y10
    hurdle_rate = expected_inflation + risk_free_rate

    gold = commodity_price('gold')
    silver = commodity_price('silver')
    bitcoin = get_crypto_price('BTC')
    
    copper = commodity_price('copper')
    lumber = commodity_price('lumber')
    aluminum = commodity_price('aluminum')
    
    corn = commodity_price('corn')
    wheat = commodity_price('wheat')
    soybean = commodity_price('soybean')
    
    brent_crude_oil = commodity_price('brent_crude_oil')
    natural_gas = commodity_price('natural_gas')
    gasoline_rbob = commodity_price('gasoline_rbob')
    
    qqq = equity_price('QQQ')
    spy = equity_price('SPY')
    dia = equity_price('DIA')
    iwm = equity_price('IWM')
    vea = equity_price('VEA')
    vwo = equity_price('VWO')
    
    print("~~~ LAZY MACRO ~~~")
    print(f"\n3-YEAR EXPECTED ANNUAL INFLATION: *** {expected_inflation*100:.3f}% ***")
    print(b5)
    print(b5_full)
    print(y2e)
    print(y2e_full)
    print("\nBOND YIELDS:")
    print(f"- 3M: {m3*100:.2f}%")
    print(f"- 2Y: {y2*100:.2f}%")
    print(f"- 5Y: {y5*100:.2f}%")
    print(f"- 10Y: {y10*100:.2f}%")
    print(f"- 30Y: {y30*100:.2f}%")
    print(f"\nINVESTMENT HURDLE RATE: *** {hurdle_rate*100:.3f}% ***")
    print("- (3-year expected inflation) + (10-year treasury bond yield)")
    print('- "Short-term is less than three years."')
    print("\nCOMMODITIES:\n")
    print(f"Gold: ${gold:.2f} / Silver: ${silver:.2f} / Bitcoin: ${bitcoin:.2f}")
    print(f"Copper: ${copper:.2f} / Lumber: ${lumber:.2f} / Aluminum: ${aluminum:.2f}")
    print(f"Corn: ${corn:.2f} / Wheat: ${wheat:.2f} / Soybeans: ${soybean:.2f}")
    print(f"Brent Crude: ${brent_crude_oil:.2f} / NatGas: ${natural_gas:.2f} / Gasoline: ${gasoline_rbob:.2f}")
    print("\nEQUITIES:\n")
    print(f"SPY: ${spy:.2f} / QQQ: ${qqq:.2f} / DIA: ${dia:.2f}")
    print(f"IWM: ${iwm:.2f} / VEA: ${vea:.2f} / VWO: ${vwo:.2f}")
    print("\n~~~\n")

    now_utc = datetime.now(timezone.utc)
    formatted_date = now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')
    utc_dt = f"Last updated: {formatted_date}"
    print(utc_dt)

    print("\nSource: https://github.com/84adam/lazy-macro")
