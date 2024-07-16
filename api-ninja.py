# api-ninja.py

import requests
from decouple import config

API_KEY = config('API_KEY')

def commodity_price(commodity):
    api_url = f'https://api.api-ninjas.com/v1/commodityprice?name={commodity}'
    response = requests.get(api_url, headers={'X-Api-Key': API_KEY})
    if response.status_code == requests.codes.ok:
        p = response.json()['price']
        return p
    else:
        return f"Error: {response.status_code}, {response.text}"

def equity_price(symbol):
    api_url = f'https://api.api-ninjas.com/v1/stockprice?ticker={symbol}'
    response = requests.get(api_url, headers={'X-Api-Key': API_KEY})
    if response.status_code == requests.codes.ok:
        p = response.json()['price']
        return p
    else:
        return f"Error: {response.status_code}, {response.text}"

if __name__ == '__main__':
        
    gold = commodity_price('gold')
    silver = commodity_price('silver')
    copper = commodity_price('copper')
    lumber = commodity_price('lumber')
    brent_crude_oil = commodity_price('brent_crude_oil')
    natural_gas = commodity_price('natural_gas')
    
    qqq = equity_price('QQQ')
    spy = equity_price('SPY')
    dia = equity_price('DIA')
    iwm = equity_price('IWM')
    vea = equity_price('VEA')
    vwo = equity_price('VWO')
    
    print(f"gold: {gold:.2f} -- silver: {silver:.2f} -- copper: {copper:.2f}")
    print(f"lumber: {lumber:.2f} -- brent crude oil: {brent_crude_oil:.2f} -- natgas: {natural_gas:.2f}")
    print("---")
    print(f"SPY: {spy:.2f} -- QQQ: {qqq:.2f} -- DIA: {dia:.2f}")
    print(f"IWM: {iwm:.2f} -- VEA: {vea:.2f} -- VWO: {vwo:.2f}")
