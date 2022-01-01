import tweepy
from config import *
import keyboard
import sys
import datetime
from tda.orders.common import Duration, Session
from tda.orders.equities import equity_buy_limit
from tda.orders.generic import OrderBuilder
from tda.orders.options import OptionSymbol
from tda import auth, client
import json
import config
from selenium import webdriver
from tweepy.auth import OAuthHandler
from urllib3.exceptions import ProtocolError
import math
from math import ceil
import time
from fractions import Fraction
import os
import datetime

def choose(status):
    index = -1
    quant = 0
    date = -1
    command = status.text
    command = command.upper()
    if(command[:6] == '#ALERT'):
        # Cutting off unncessary parts front and back
        command = command[7:]
        command = command.split()

        # Cutting out date if given
        if command[2] in months:
            if (months.index(command[2]) < 9):
                date = '0'+str(months.index(command[2])+1) + command[3]
            else:
                date = (str(months.index(command[2])+1) + command[3])
            command[2] = command[4]
            command[3] = command[5]
        command[3] = command[3].replace("$", "")

        if len(symbol_names) != 0:
            for i in range(0, len(symbol_names)):
                if((command[1] == symbol_names[i]) and (command[2].replace('C', '')==strikes[i])):
                    index = i

        if(command[0] == "SOLD" and (len(contracts_held) != 0) and index != -1):
            # Finding index of symbols
            if('ALL' in command):
                quant = int(contracts_held[index])
            else:
                quant = math.ceil(int(contracts_held[index])*0.5)
            trades = open('trades.txt', "a", encoding="utf-8")
            time_of_message = status.created_at - datetime.timedelta(hours=5)
            trades.write(str(time_of_message) + " Sold " + str(quant) + " contracts of " + str(command[1]) +"! Comments: \n")
            order(command[1], command[0], quant, command[2], index, date)
        elif(command[0] == "BOUGHT"):
            # If we already have a contract in that stock and "rollup" is in the tweet
            if (("ROLL UP" in status.text) and (command[1] in symbol_names)):
                quant = math.ceil((1000/float(command[3]))/100)
            elif ('LOTTO' in status.text):
                quant = math.ceil((1000/float(command[3]))/100)
            elif((not("ROLL UP" in status.text)) and not('LOTTO' in status.text)):
                quant = math.ceil((2500/float(command[3]))/100)
            else:
                print('Rollup buy order not placed because contracts were not held!')
            trades = open('trades.txt', "a", encoding="utf-8")
            time_of_message = status.created_at - datetime.timedelta(hours=5)

            if (quant != 0):
                trades.write(str(time_of_message) + " Bought " + str(quant) + " contracts of " + str(command[1]) +"! Comments: \n")
                order(command[1], command[0], quant, command[2], index, date)

        else:
            print('Cannot sell because no contracts of', command[1], 'with strike', command[2],'are held!')

def closestfriday(d):
    while d.weekday() != 4:
        d += datetime.timedelta(1)
    d = d.strftime('%m/%d/%Y')
    d = d.replace("/", "")
    d = d[0:4]+d[6:8]

    return d

def closestmonthly(d):
    while d.weekday() != 4:
        d += datetime.timedelta(1)
    first_day = d.replace(day=1)
    day_of_month = d.day
    if(first_day.weekday() == 6):
        adjusted_dom = (1 + first_day.weekday()) / 7
    else:
        adjusted_dom = day_of_month + first_day.weekday()
    
    if int(ceil(adjusted_dom/7.0))>3:
        d = closestmonthly(d.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
        while d.weekday() != 4:
            d += datetime.timedelta(1)
        d += datetime.timedelta(14)
    else:
        d += datetime.timedelta((3-int(ceil(adjusted_dom/7.0)))*7)
    return d
    
def order(symbol, choice, quantity, strike, index, date):
    print((symbol, choice, quantity, strike, index, date))
    # Conversion to TDA standards
    if choice == 'BOUGHT':
        choice = 'BUY_TO_OPEN'
    else:
        choice = 'SELL_TO_CLOSE'
    strike = strike.replace('C', '')

    # Special Case SPX
    if(symbol == 'SPX'):
        symbol = 'SPXW'

    # Weekly or Monthly
    if (date != -1):
        # Specific date
        friday = date + '21'
    elif (monthly_list[0] == symbol) or (monthly_list[1]==symbol):
        # Is a Monthly
        friday = closestmonthly(datetime.datetime.today())
    else:
        # Is a weekly
        friday = closestfriday(datetime.datetime.today())
    # Formatting the symbol
    my_symbol = symbol + "_" + friday + 'C' + strike

    print(my_symbol)

    order_spec = {
        "orderType": "MARKET",
        "session": "NORMAL",
        "duration": "DAY",
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {
                "instruction": choice,
                "quantity": quantity,
                "instrument": {
                    "symbol": my_symbol,
                    "assetType": "OPTION"
                }
            }
        ]
    }

    response = c.place_order(config.acc_id, order_spec)
    print(response)

    if(symbol == 'SPXW'):
        symbol = 'SPX'

    if(choice == 'SELL_TO_CLOSE'):
        # When we remove something
        contracts_held[index] = int(contracts_held[index])-quantity
        print('Sold', quantity, 'contracts of', symbol)
    # Writing into file for bought
    elif(choice == 'BUY_TO_OPEN'):
        # Making new variable space
        if(index == -1):
            contracts_held.append(quantity)
            symbol_names.append(symbol)
            strikes.append(strike)
        else:
            contracts_held[index] = int(contracts_held[index])+quantity
        print('Bought', quantity, 'contracts of', symbol)
    else:
        print('ERROR, please contact developer :)')

    # If the quantity is 0 on a given symbol
    if(int(contracts_held[index]) == 0):
        symbol_names.pop(index)
        contracts_held.pop(index)
        strikes.pop(index)

    
    with open("positions.txt", "w") as f:
        f.write('SYMBOL QUANT STRIKE')
        for i in range(0, len(symbol_names)):
            f.write('\n' + str(symbol_names[i]) + '      ' + str(contracts_held[i]) + '      ' + str(strikes[i]))

if __name__ == '__main__':
    global symbol_names, contracts_held, strikes
    symbol_names = []
    contracts_held = []
    strikes = []

    print('--------------------BOT INITIALIZED--------------------')

    # For TDA Setup
    try:
        c = auth.client_from_token_file(config.token_path, config.tda_key)
    except FileNotFoundError:
        with webdriver.Chrome() as driver:
            c = auth.client_from_login_flow(
                driver, config.tda_key, config.redirect_url, config.token_path)

    
    # Loading in Variables
    file_read = open('positions.txt', "r")
    positions = file_read.readlines()
    with open('positions.txt','w') as f:
        for position in positions:
            if not position.isspace():
                f.write(position)
    
    header = positions[0]
    positions = positions[1:]
    if(len(positions)!=0):
        for i in range(0,len(positions)):
            temp = positions[i]
            temp = temp.split()
            symbol_names.append(temp[0])
            contracts_held.append(temp[1])
            strikes.append(temp[2])

    # Printing out what we have so far
    for i in range(0, len(symbol_names)):
        print('Holding ', contracts_held[i], symbol_names[i], 'with strike', strikes[i])
    
    print('-------------------------------------------------------')

    # Listening twitter
    auth = tweepy.OAuthHandler(apikey, apisecret)
    auth.set_access_token(accesstoken, accesstokensecret)
    api = tweepy.API(auth)
    while True:
        tweets = api.user_timeline(user_id = userid, count = 1)
        if(len(tweets)!=0):
            file_read = open('tweets.txt', "r", encoding="utf-8")
            tweets_file = file_read.read()
            if(not tweets[0].text in tweets_file):
                if((tweets[0].created_at - datetime.timedelta(hours=5)).date() == (datetime.datetime.now()).date()):
                    with open('tweets.txt','a', encoding = 'utf-8') as f:
                        f.write('\n'+tweets[0].text)
                        f.write('\n-------------------------------------------------------')
                        print(tweets[0].text)
                        choose(tweets[0])
                        print('-------------------------------------------------------')
        time.sleep(1.5)
    

