import requests
import json
import os
import sqlite3
from xml.sax import parseString
from bs4 import BeautifulSoup
import requests
import re
import os
import csv
import unittest
import matplotlib
import matplotlib.pyplot as plt
import numpy as np


def getVacData():
    response_API = requests.get('https://covid-api.mmediagroup.fr/v1/vaccines')
    data = response_API.text
    info = json.loads(data)
    return info


def getGovData():
    response_API = requests.get(
        'https://covidtrackerapi.bsg.ox.ac.uk/api/v2/stringency/date-range/2022-03-01/2022-04-01')
    data = response_API.text
    info = json.loads(data)
    # print(info)
    return info


# def getCountryCodeData():
#     response_API = requests.get('https://www.iban.com/country-codes')
#     data = response_API.text
#     info = json.loads(data)
#     print(info)
#     return info


def build_gov_table(gov_json_data, cur, conn):
    cur.execute("CREATE TABLE IF NOT EXISTS Gov (country_code TEXT PRIMARY KEY, confirmed INTEGER, deaths INTEGER, stringency_actual FLOAT)")
    raw = gov_json_data['data']['2022-03-01']
    # print(raw)
    for data in raw:
        # print(data)
        country_code = raw[data]['country_code']
        confirmed = raw[data]['confirmed']
        deaths = raw[data]['deaths']
        stringency_actual = raw[data]['stringency_actual']
        cur.execute(
            """
            INSERT or IGNORE INTO Gov (country_code, confirmed, deaths, stringency_actual)
            VALUES (?, ?, ?, ?)
            """,
            (country_code, confirmed, deaths, stringency_actual)
        )
        conn.commit()


def build_code_table(cur, conn):
    cur.execute(
        "CREATE TABLE IF NOT EXISTS CountryCode (country TEXT PRIMARY KEY, code TEXT)")
    url = "https://www.iban.com/country-codes"
    # soup = BeautifulSoup(html_content, "lxml")
    html_content = requests.get(url).text
    soup = BeautifulSoup(html_content, 'html.parser')
    body = soup.find("tbody")
    container_list = body.find_all("tr")
    for container in container_list:
        # print(container)
        element_list = container.find_all("td")
        country = element_list[0].text.strip()
        code = element_list[2].text.strip()
        # print(country + " " + code + "\n")
        cur.execute(
            """
                INSERT or IGNORE INTO CountryCode (country, code)
                VALUES (?, ?)
            """,
            (country, code)
        )
        conn.commit()


def build_vac_table(vac_json_data, cur, conn):
    cur.execute(
        "CREATE TABLE IF NOT EXISTS Vac_1 (country TEXT PRIMARY KEY, people_vaccinated INTEGER, people_partially_vaccinated INTEGER, population INTEGER)")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS Vac_2 (sq_km_area INTEGER, iso INTEGER)")
    for data in vac_json_data:
        raw = vac_json_data[data]['All']
        # print(raw)
        try:
            country = raw['country']
        except:
            continue
        people_vaccinated = raw['people_vaccinated']
        people_partially_vaccinated = raw['people_partially_vaccinated']
        population = raw['population']
        try:
            sq_km_area = raw['sq_km_area']
        except:
            continue
        iso = raw['iso']
        cur.execute(
            """
                    INSERT or IGNORE INTO Vac_1 (country, people_vaccinated, people_partially_vaccinated, population)
                    VALUES (?, ?, ?, ?)
                    """,
            (country, people_vaccinated, people_partially_vaccinated, population)
        )
        cur.execute(
            """
                    INSERT INTO Vac_2 (sq_km_area, iso)
                    VALUES (?, ?)
                    """,
            (sq_km_area, iso)
        )
        conn.commit()


def setUpDb(f_name):
    path = os.path.dirname(os.path.abspath(__file__))
    conn = sqlite3.connect(path+'/'+f_name)
    cur = conn.cursor()
    return cur, conn


def calConfirmed_DeathRate(cur, conn):
    f1 = open("confirmed.txt", "w")
    f2 = open("deaths.txt", "w")
    cur.execute(
        '''
        SELECT
            Gov.confirmed,
            Gov.deaths,
            Vac_1.population,
            Vac_1.country
        FROM Gov
        JOIN CountryCode
            ON Gov.country_code = CountryCode.code
        JOIN Vac_1
            ON Vac_1.country = CountryCode.country;
        '''
    )
    lines = cur.fetchall()
    for line in lines:
        confirmed_rate = line[0] / line[2]
        deaths_rate = line[1] / line[2]
        f1.write(line[3] + " : " + str(confirmed_rate) + "\n")
        f2.write(line[3] + " : " + str(deaths_rate) + "\n")
    f1.close()
    f2.close()
    return lines


def calVacRate(cur, conn):
    f1 = open("vaccinated.txt", "w")
    f2 = open("partially_vaccinated.txt", "w")
    cur.execute(
        '''
        SELECT
            country,
            people_vaccinated,
            people_partially_vaccinated,
            population
        FROM Vac_1
        '''
    )
    lines = cur.fetchall()
    # print(lines)
    for line in lines:
        vaccinated_rate = line[1] / line[3]
        partial_vaccinated_rate = line[2] / line[3]
        f1.write(line[0] + " : " + str(vaccinated_rate) + "\n")
        f2.write(line[0] + " : " + str(partial_vaccinated_rate) + "\n")
    f1.close()
    f2.close()
    return lines


def confirmed_vs_death(data1):
    # show and contrast the confirm rate and death rate of the top 10 countries with most population
    data1 = sorted(data1, key=lambda x: x[2], reverse=True)
    dict1 = {}
    dict2 = {}
    for line in data1[:11]:
        confirmed_rate = line[0] / line[2]
        deaths_rate = line[1] / line[2]
        dict1[line[3]] = confirmed_rate
        dict2[line[3]] = deaths_rate
    x = np.arange(len(dict1))
    width = 0.25
    fig, ax = plt.subplots()
    plt.bar(x - width/2, list(dict1.values()), width, label='confirmed rate')
    plt.bar(x + width/2, list(dict2.values()), width, label='death rate')
    plt.xlabel('Country Name')
    plt.ylabel('Percentage')
    plt.title('confirmed rate vs death rate due to Covid')
    plt.xticks(x, labels=dict1.keys())
    plt.legend()
    plt.savefig("bar1.jpg")
    plt.show()


def confirmed_vs_vac(data1, data2):
    # show relationship between the confirm rate and vaccination rate of the top 10 countries with most population
    data1 = sorted(data1, key=lambda x: x[2], reverse=True)
    dict1 = {}
    dict2 = {}
    for line in data1[:11]:
        confirmed_rate = line[0] / line[2]
        dict1[line[3]] = confirmed_rate
    for line in data2[:11]:
        vaccinated_rate = (line[1] / line[3]) + (line[2] / line[3])
        dict2[line[0]] = vaccinated_rate
    x = np.arange(len(dict1))
    width = 0.25
    fig, ax = plt.subplots()
    plt.bar(x - width/2, list(dict1.values()), width, label='confirmed rate')
    plt.bar(x + width/2, list(dict2.values()), width, label='vaccination rate')
    plt.xlabel('Country Name')
    plt.ylabel('Percentage')
    plt.title('confirmed rate vs vaccination rate due to Covid')
    plt.xticks(x, labels=dict1.keys())
    plt.legend()
    plt.savefig("bar2.jpg")
    plt.show()


def vac_vs_partial_vs_no(data2):
    labels = ["vaccination rate", "non-vaccinated rate"]
    lst = []
    vac_num = 0
    no_num = 0
    population = 0
    for line in data2:
        vac_num += line[1]
        no_num += line[3] - line[1]
        population += line[3]
    vac_rate = vac_num / population
    no_rate = no_num / population
    lst.append(vac_rate)    
    lst.append(no_rate)
    fig = plt.figure()
    ax = fig.add_axes([0,0,1,1])
    ax.axis('equal')
    ax.pie(lst, labels=labels, autopct='%1.2f%%')
    plt.title("Vaccination ratio")
    plt.axis('equal')
    plt.show()
    plt.savefig("pie.jpg")
    plt.close()


def main():
    cur, conn = setUpDb('covid.db')
    gov_json_data = getGovData()
    vac_json_data = getVacData()
    build_gov_table(gov_json_data, cur, conn)
    build_vac_table(vac_json_data, cur, conn)
    build_code_table(cur, conn)
    data1 = calConfirmed_DeathRate(cur, conn)
    data2 = calVacRate(cur, conn)
    confirmed_vs_death(data1)
    confirmed_vs_vac(data1, data2)
    vac_vs_partial_vs_no(data2)


if __name__ == "__main__":
    main()
