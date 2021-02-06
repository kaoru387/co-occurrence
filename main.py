# -*- coding: utf-8 -*-

import os
import configparser

import MeCab
import itertools
from collections import Counter

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
# %matplotlib inline 
import japanize_matplotlib

from googleapiclient.discovery import build
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.cloud import storage

scope = ['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']

config = configparser.ConfigParser()
config.read('../config/spreadsheet.ini')

# 久高本番
SPREADSHEET_KEY = config['BASE']['key']

range_ = config['BASE']['renge']
bucketName = config['BASE']['bucketName']

# os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '../config/client_secrets.json'
GOOGLE_APPLICATION_CREDENTIALS = '../config/kudaka-island-fbece909e515.json';
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_APPLICATION_CREDENTIALS
client = storage.Client()
bucket = client.get_bucket(bucketName)

mecab = MeCab.Tagger("-Ochasen")

def main():

    # google spreadsheet
    creds = None
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_APPLICATION_CREDENTIALS, scope)
    service = build('sheets', 'v4', credentials=creds)

    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_KEY,
                                range=range_).execute()
    values = result.get('values', [])

    text_good = ""
    text_bad = ""
    if not values:
        print('No data found.')
    else:
        print('Name, Major:')
        for row in values:
            if(len(row)==1):
                text_good+=row[0]
            if(len(row)==2):
                text_good+=row[0]
                text_bad+=row[1]
    
    # 文単位のリストに分割
    sentences = text_good.split("。")

    # 文単位の名刺リストの生成
    noun_list = [
        [v.split()[2] for v in mecab.parse(sentence).splitlines()
        if (len(v.split())>=3 and v.split()[3][:2]=='名詞')]
        for sentence in sentences
    ]

    # 文単位の名詞ペアリストを生成
    pair_list = [
        list(itertools.combinations(n, 2))
        for n in noun_list if len(noun_list) >=2
    ]

    # 名詞ペアリストの平坦化
    all_pairs = []
    for u in pair_list:
        all_pairs.extend(u)

    # 名詞ペアの頻度をカウント
    cnt_pairs = Counter(all_pairs)

    # 共起データの絞り込み
    tops = sorted(
        cnt_pairs.items(), 
        key=lambda x: x[1], reverse=True
    )[:50]

    # 重み付きデータの生成
    noun_1 = []
    noun_2 = []
    frequency = []

    # データフレームの作成
    for n,f in tops:
        noun_1.append(n[0])    
        noun_2.append(n[1])
        frequency.append(f)

    df = pd.DataFrame({'前出名詞': noun_1, '後出名詞': noun_2, '出現頻度': frequency})

    # 重み付きデータの設定
    weighted_edges = np.array(df)

    # 可視化

    # グラフオブジェクトの生成
    G = nx.Graph()

    # 重み付きデータの読み込み
    G.add_weighted_edges_from(weighted_edges)

    # # ネットワーク図の描画
    # plt.figure(figsize=(10,10))
    # nx.draw_networkx(G,
    #                  node_shape = "s",
    #                  node_color = "c", 
    #                  node_size = 500,
    #                  edge_color = "gray", 
    #                  font_family = "IPAexGothic") # フォント指定
    # plt.show()

    # nodeの配置方法の指定
    seed = 0
    np.random.seed(seed)
    pos = nx.spring_layout(G, k=0.3, seed=seed)

    # ネットワーク図の描画
    plt.figure(figsize=(10,10))
    pr = nx.pagerank(G)
    nx.draw_networkx(G,
        pos,
        node_color=list(pr.values()),
        alpha=0.7,
        node_size=[10000*v for v in pr.values()],
        cmap=plt.cm.rainbow,
        edge_color = "gray",
        fontsize=15,
        font_weight='bold',
        font_family = "IPAexGothic") # フォント指定
    plt.axis('off')
    plt.show()

    temp_local_filename = 'kyouki'
    fig_to_upload = plt.gcf()
    fig_to_upload.savefig(temp_local_filename, format='png')

    upload(temp_local_filename)
    
    # # nodeの大きさと色をページランクアルゴリズムによる重要度により変える
    # pr = nx.pagerank(G)
    # nx.draw_networkx_nodes(
    #     G,
    #     pos,
    #     node_color=list(pr.values()),
    #     cmap=plt.cm.rainbow,
    #     alpha=0.7,
    #     edge_color = "gray", 
    #     node_size=[10000*v for v in pr.values()])
 
    # # 日本語ラベルの設定
    # nx.draw_networkx_labels(G, pos, fontsize=15, font_family='IPAexGothic', font_weight='bold')
    
    # # エッジ太さをJaccard係数により変える
    # edge_width = [d['weight'] * 1 for (u, v, d) in G.edges(data=True)]
    # nx.draw_networkx_edges(G, pos, alpha=0.7, edge_color='darkgrey', width=edge_width)
    # # nx.draw_networkx_edges(G, pos=nx.spring_layout(G))

    # plt.axis('off')
    # plt.show()

    return 'success';

def upload(fname):
    blob = bucket.blob(fname+'.png')
    blob.cache_control='no-cache,max-age=0';
    blob.upload_from_filename(fname,content_type='image/png')
    os.remove(fname)
    return 'OK'


def hello_pubsub(event, context):
    print('hello-')
    main()

def hello_world(request):
    # preflight request時
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600',
        }
        return ('', 204, headers)

    param_dict=main()
    headers = {
        'Access-Control-Allow-Origin': '*'
    }
    # return (json.dumps(param_dict), 200, headers)
    return ('success', 200, headers)

if __name__ == '__main__':
    print(main())