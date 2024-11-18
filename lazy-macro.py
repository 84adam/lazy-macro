# lazy-macro.py

import requests
from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
from decouple import config
import pandas as pd
import math
import numpy as np
from fredapi import Fred
import pytz
from datetime import datetime, timezone
import json
import time
import calendar
import sys
import io

# HELPER FUNCTIONS

def approx_equal(x, y, tol=1e-9):
    return math.isclose(x, y, abs_tol=tol)

def check_error(value, error):
    value = 0.04 if error != None else value
    if value == None:
        value = 0.04
    return value

# API NINJA

API_NINJA_KEY = config('API_NINJA_KEY')

def commodity_price(commodity):
    """
    API NINJA: Commodity Price
    """
    error = None
    api_url = f'https://api.api-ninjas.com/v1/commodityprice?name={commodity}'
    response = requests.get(api_url, headers={'X-Api-Key': API_NINJA_KEY})
    if response.status_code == requests.codes.ok:
        p = response.json()['price']
        return p, error
    else:
        error = f"Error: {response.status_code}, {response.text}"
        return None, error

def equity_price(symbol):
    """
    API NINJA: Equity Price
    """
    error = None
    api_url = f'https://api.api-ninjas.com/v1/stockprice?ticker={symbol}'
    response = requests.get(api_url, headers={'X-Api-Key': API_NINJA_KEY})
    if response.status_code == requests.codes.ok:
        p = response.json()['price']
        return p, error
    else:
        return None, f"Error: {response.status_code}, {response.text}"

# ALPHA VANTAGE

ALPHA_VANTAGE_API_KEY = config('ALPHA_VANTAGE_API_KEY')

def get_bond_yield(maturity):
    """
    deprecated: previously rates were updated throughout the day
    """
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
    """
    get crypto price from coinmarketcap
    """
    error = None
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
        return d, error
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        return None, e

# TREASURY YIELD CURVE DATA

def get_yield_curve():
    """
    Get Yield Curve History from US Treasury
    """
    # current month only:
    current_year = datetime.now().year
    current_month = datetime.now().month
    url = f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/{current_year}{current_month}?type=daily_treasury_yield_curve&field_tdr_date_value_month={current_year}{current_month}&page&_format=csv"
    s = requests.get(url).content
    df = pd.read_csv(io.StringIO(s.decode('utf-8')))
    # convert 'Date' to datetime format
    df['Date'] = pd.to_datetime(df['Date'])
    # sort by date ascending
    df = df.sort_values(by='Date', ascending=True)
    # access the latest row (most recent date)
    latest_row = df.iloc[-1]
    # extract specific values
    m3 = latest_row['3 Mo'] / 100
    y2 = latest_row['2 Yr'] / 100
    y5 = latest_row['5 Yr'] / 100
    y10 = latest_row['10 Yr'] / 100
    y30 = latest_row['30 Yr'] / 100
    date = latest_row['Date'].strftime('%y-%m-%d')
    return m3, y2, y5, y10, y30, date

# MACRO DATA FROM FEDERAL RESERVE

def get_30y_mortgage_rates():
    """
    Get full 30-year US mortgage rate data using FRED API
    """
    fred = Fred(api_key=config('FRED_API_KEY'))
    y30mort = fred.get_series('MORTGAGE30US')
    return y30mort

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

    # RATES & INFLATION
    m3, y2, y5, y10, y30, yc_date = get_yield_curve()

    expected_inflation, b5, b5_full, y2e, y2e_full = get_expected_inflation_rate()

    risk_free_rate = y10
    hurdle_rate = expected_inflation + risk_free_rate

    mortgage_data = get_30y_mortgage_rates()
    # select most recent valid rate
    m_idx = -1
    m_rates = []
    for i in range(0,10):
        m_date = mortgage_data.iloc[m_idx:].index[m_idx].strftime('%y-%m-%d')
        m_rate = mortgage_data.iloc[m_idx]
        if m_rate is not None:
            if m_rate > 0:
                m_rates.append((m_date, m_rate))
        m_idx -= 1
    latest_30y_mortgage_rate = m_rates[0][1]
    latest_30y_mortgage_date = m_rates[0][0]

    # COMMODITIES
    gold, gold_e = commodity_price('gold')
    gold = check_error(gold, gold_e)

    silver, silver_e = commodity_price('silver')
    silver = check_error(silver, silver_e)

    bitcoin, bitcoin_e = get_crypto_price('BTC')
    bitcoin = check_error(bitcoin, bitcoin_e)
    
    platinum, platinum_e = commodity_price('platinum')
    platinum = check_error(platinum, platinum_e)

    palladium, palladium_e = commodity_price('palladium')
    palladium = check_error(palladium, palladium_e)

    copper, copper_e = commodity_price('copper')
    copper = check_error(copper, copper_e)

    aluminum, aluminum_e = commodity_price('aluminum')
    aluminum = check_error(aluminum, aluminum_e)

    lumber, lumber_e = commodity_price('lumber')
    lumber = check_error(lumber, lumber_e)

    sugar, sugar_e = commodity_price('sugar')
    sugar = check_error(sugar, sugar_e)
    
    corn, corn_e = commodity_price('corn')
    corn = check_error(corn, corn_e)

    wheat, wheat_e = commodity_price('wheat')
    wheat = check_error(wheat, wheat_e)

    soybean, soybean_e = commodity_price('soybean')
    soybean = check_error(soybean, soybean_e)

    brent_crude_oil, brent_crude_oil_e = commodity_price('brent_crude_oil')
    brent_crude_oil = check_error(brent_crude_oil, brent_crude_oil_e)

    natural_gas, natural_gas_e = commodity_price('natural_gas')
    natural_gas = check_error(natural_gas, natural_gas_e)

    gasoline_rbob, gasoline_rbob_e = commodity_price('gasoline_rbob')
    galoline_rbob = check_error(gasoline_rbob, gasoline_rbob_e)
    
    # EQUITIES
    spy, spy_e = equity_price('SPY')
    spy = check_error(spy, spy_e)

    qqq, qqq_e = equity_price('QQQ')
    qqq = check_error(qqq, qqq_e)

    dia, dia_e = equity_price('DIA')
    dia = check_error(dia, dia_e)

    iwm, iwm_e = equity_price('IWM')
    iwm = check_error(iwm, iwm_e)

    vea, vea_e = equity_price('VEA')
    vea = check_error(vea, vea_e)

    vwo, vwo_e = equity_price('VWO')
    vwo = check_error(vwo, vwo_e)

    vti, vti_e = equity_price('VTI')
    vti = check_error(vti, vti_e)

    veu, veu_e = equity_price('VEU')
    veu = check_error(veu, veu_e)

    spd, spd_e = equity_price('SPD')
    spd = check_error(spd, spd_e)

    # OUTPUT

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
    print(f"- 30Y: {y30*100:.2f}% ({yc_date})")
    print(f"- 30Y Mortgage: {latest_30y_mortgage_rate:.2f}% ({latest_30y_mortgage_date})")
    
    print(f"\nINVESTMENT HURDLE RATE: *** {hurdle_rate*100:.3f}% ***")
    print("- (3-year expected inflation) + (10-year treasury bond yield)")
    print('- "Short-term is less than three years."')
    
    print("\nCOMMODITIES:\n")

    try:
        print(f"Gold: ${gold:.2f} / Silver: ${silver:.2f} / Bitcoin: ${bitcoin:.2f}")
    except:
        print(f"Gold: ${gold} / Silver: ${silver} / Bitcoin: ${bitcoin}")
    
    try:
        print(f"Platinum: ${platinum:.2f} / Palladium: ${palladium:.2f} / Copper: ${copper:.2f}")
    except:
        print(f"Platinum: ${platinum} / Palladium: ${palladium} / Copper: ${copper}")

    try:
        print(f"Aluminum: ${aluminum:.2f} / Lumber: ${lumber:.2f} / Sugar: ${sugar:.2f}")
    except:
        print(f"Aluminum: ${aluminum} / Lumber: ${lumber} / Sugar: ${sugar}")

    try:
        print(f"Corn: ${corn:.2f} / Wheat: ${wheat:.2f} / Soybeans: ${soybean:.2f}")
    except:
        print(f"Corn: ${corn} / Wheat: ${wheat} / Soybeans: ${soybean}")

    try:
        print(f"Brent Crude: ${brent_crude_oil:.2f} / NatGas: ${natural_gas:.2f} / Gasoline: ${gasoline_rbob:.2f}")
    except:
        print(f"Brent Crude: ${brent_crude_oil} / NatGas: ${natural_gas} / Gasoline: ${gasoline_rbob}")

    print("\nEQUITIES:\n")
    try:
        print(f"SPY: ${spy:.2f} / QQQ: ${qqq:.2f} / DIA: ${dia:.2f}")
    except:
        print(f"SPY: ${spy} / QQQ: ${qqq} / DIA: ${dia}")

    try:
        print(f"IWM: ${iwm:.2f} / VEA: ${vea:.2f} / VWO: ${vwo:.2f}")
    except:
        print(f"IWM: ${iwm} / VEA: ${vea} / VWO: ${vwo}")

    try:
        print(f"VTI: ${vti:.2f} / VEU: ${veu:.2f} / SPD: ${spd:.2f}")
    except:
        print(f"VTI: ${vti} / VEU: ${veu} / SPD: ${spd}")
    print("\n~~~\n")

    now_utc = datetime.now(timezone.utc)
    formatted_date = now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')
    utc_dt = f"Last updated: {formatted_date}"
    print(utc_dt)

    print("\nSource: https://github.com/84adam/lazy-macro")

    print("\nQuestions or suggestions? Contact: info [at] xau [dot] ag")
