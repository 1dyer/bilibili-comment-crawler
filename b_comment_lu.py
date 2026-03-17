import re
import requests
import json
from urllib.parse import quote
import pandas as pd
import hashlib
import urllib
import time
import csv

# 获取B站的Header
def get_Header():
    with open('bili_cookie.txt','r') as f:
            cookie=f.read()
    header={
            "Cookie":cookie,
            "User-Agent":'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0'
    }
    return header

# 通过bv号，获取视频的oid
def get_information(bv):
    resp = requests.get(f"https://www.bilibili.com/video/{bv}/?p=14&spm_id_from=pageDriver&vd_source=cd6ee6b033cd2da64359bad72619ca8a",headers=get_Header())
    # 提取视频oid
    obj = re.compile(f'"aid":(?P<id>.*?),"bvid":"{bv}"')
    oid = obj.search(resp.text).group('id')

    # 提取视频的标题
    obj = re.compile(r'<title data-vue-meta="true">(?P<title>.*?)</title>')
    try:
        title = obj.search(resp.text).group('title')
    except:
        title = "未识别"

    return oid,title

# MD5加密
def md5(code):
    MD5 = hashlib.md5()
    MD5.update(code.encode('utf-8'))
    w_rid = MD5.hexdigest()
    return w_rid

# 递归爬取子评论
def fetch_sub_comments(oid, rpid, csv_writer, count, target_uid, fetch_all=False):
    page = 1
    
    while True:
        try:
            second_url = f"https://api.bilibili.com/x/v2/reply/reply?oid={oid}&type=1&root={rpid}&ps=10&pn={page}&web_location=333.788"
            second_comment = requests.get(url=second_url, headers=get_Header()).content.decode('utf-8')
            second_comment = json.loads(second_comment)
            
            # 检查响应结构
            if not second_comment.get('data') or not second_comment['data'].get('replies'):
                break
            replies = second_comment['data']['replies']
            if not replies:
                break
                
            for second in replies:
                uid = second["mid"]
                
                # 判断是否应该写入
                should_write = fetch_all or str(uid) == target_uid or uid == int(target_uid)
                
                if should_write:
                    count += 1
                    parent = second["parent"]
                    second_rpid = second["rpid"]
                    name = second["member"]["uname"]
                    context = second["content"]["message"]
                    reply_time = pd.to_datetime(second["ctime"], unit='s')
                    
                    try:
                        rereply_text = second["reply_control"]["sub_reply_entry_text"]
                        rereply = int(re.findall(r'\d+', rereply_text)[0])
                    except:
                        rereply = 0
                    
                    csv_writer.writerow([count, parent, second_rpid, uid, name, context, reply_time, rereply])
                    
                    # 递归爬取该评论的子评论
                    if rereply != 0:
                        count = fetch_sub_comments(oid, second_rpid, csv_writer, count, target_uid, fetch_all)
                else:
                    # 即使不是目标用户，也要检查其子评论
                    try:
                        rereply_text = second["reply_control"]["sub_reply_entry_text"]
                        rereply = int(re.findall(r'\d+', rereply_text)[0])
                    except:
                        rereply = 0
                    
                    if rereply != 0:
                        count = fetch_sub_comments(oid, second["rpid"], csv_writer, count, target_uid, fetch_all)
            
            page += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"爬取子评论出错: {e}")
            break
    
    return count

def typeof(obj):
    return type(obj).__name__


# 轮页爬取
def start(bv, oid, pageID, count, csv_writer, is_second, target_uid):
    # fetch_all = False
    fetch_all = target_uid == "1"
    
    # 参数
    mode = 2
    plat = 1
    type = 1  
    web_location = 1315875

    # 获取当下时间戳
    wts = int(time.time())
    
    # 如果不是第一页
    if pageID != '':
        pagination_str = '{"offset":"%s"}' % pageID
        code = f"mode={mode}&oid={oid}&pagination_str={urllib.parse.quote(pagination_str)}&plat={plat}&type={type}&web_location={web_location}&wts={wts}" + 'ea1db124af3c7062474693fa704f4ff8'
        w_rid = md5(code)
        url = f"https://api.bilibili.com/x/v2/reply/wbi/main?oid={oid}&type={type}&mode={mode}&pagination_str={urllib.parse.quote(pagination_str, safe=':')}&plat=1&web_location=1315875&w_rid={w_rid}&wts={wts}"
    
    # 如果是第一页
    else:
        pagination_str = '{"offset":""}'
        code = f"mode={mode}&oid={oid}&pagination_str={urllib.parse.quote(pagination_str)}&plat={plat}&seek_rpid=&type={type}&web_location={web_location}&wts={wts}" + 'ea1db124af3c7062474693fa704f4ff8'
        w_rid = md5(code)
        url = f"https://api.bilibili.com/x/v2/reply/wbi/main?oid={oid}&type={type}&mode={mode}&pagination_str={urllib.parse.quote(pagination_str, safe=':')}&plat=1&seek_rpid=&web_location=1315875&w_rid={w_rid}&wts={wts}"
    
    comment = requests.get(url=url, headers=get_Header()).content.decode('utf-8')
    comment = json.loads(comment)

    for reply in comment['data']['replies']:
        uid = reply["mid"]
        # 判断是否应该写入
        should_write = fetch_all or str(uid) == target_uid or uid == int(target_uid)
        
        if should_write:
            count += 1

            if count % 1000 == 0:
                time.sleep(20)

            parent = reply["parent"]
            rpid = reply["rpid"]
            name = reply["member"]["uname"]
            context = reply["content"]["message"]
            reply_time = pd.to_datetime(reply["ctime"], unit='s')
            
            try:
                rereply_text = reply["reply_control"]["sub_reply_entry_text"]
                rereply = int(re.findall(r'\d+', rereply_text)[0])
            except:
                rereply = 0

            csv_writer.writerow([count, parent, rpid, uid, name, context, reply_time, rereply])

            # 爬取该评论的所有子评论
            if is_second and rereply != 0:
                count = fetch_sub_comments(oid, rpid, csv_writer, count, target_uid, fetch_all)
        else:
            # 即使不是目标用户，也要检查其子评论
            try:
                rereply_text = reply["reply_control"]["sub_reply_entry_text"]
                rereply = int(re.findall(r'\d+', rereply_text)[0])
            except:
                rereply = 0
            
            if is_second and rereply != 0:
                count = fetch_sub_comments(oid, reply["rpid"], csv_writer, count, target_uid, fetch_all)

    # 下一页的pageID
    try:
        next_pageID = comment['data']['cursor']['pagination_reply']['next_offset']
    except:
        next_pageID = 0

    # 判断是否是最后一页了
    if next_pageID == 0:
        print(f"评论爬取完成！总共爬取{count}条。")
        return bv, oid, next_pageID, count, csv_writer, is_second
    # 如果不是最后一页，则停0.5s（避免反爬机制）
    else:
        time.sleep(5)
        print(f"当前爬取{count}条。")
        return bv, oid, next_pageID, count, csv_writer, is_second


def get_bv_uid():
    print("请输入 bv 参数:")
    bv = input().strip()
    print("请输入 uid 参数（全抓输入1）:")
    uid = input().strip()
    
    if not bv or not uid:
        print("参数不能为空")
        return None, None
    
    return bv, uid
    
    
if __name__ == "__main__":
    # 获取视频bv和用户uid
    bv ,target_uid = get_bv_uid()
    # 获取视频oid和标题
    oid, title = get_information(bv)
    # 评论起始页（默认为空）
    next_pageID = ''
    # 初始化评论数量
    count = 0
    # 是否开启二级评论爬取，默认开启
    is_second = True
    ct = time.strftime("%Y-%m-%d-%H-%M")
    # 创建CSV文件并写入表头
    with open(f'{ct}评论.csv', mode='w', newline='', encoding='utf-8-sig') as file:
        csv_writer = csv.writer(file)
        csv_writer.writerow(['序号', '上级评论ID', '评论ID', '用户ID', '用户名', '评论内容', '评论时间', '回复数'])
        # 开始爬取
        while next_pageID != 0:
            bv, oid, next_pageID, count, csv_writer, is_second = start(bv, oid, next_pageID, count, csv_writer, is_second, target_uid)