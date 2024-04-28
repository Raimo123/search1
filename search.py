import requests
from bs4 import BeautifulSoup
import sqlite3
import time
from collections import deque
from urllib.parse import urlparse
import pickle
import os
import re

# 文件保存路径
SAVE_PATH = "D:/search"
# 集合文件名
DAYOO_FILE = "dayoo_links.pkl"
OTHER_FILE = "other_links.pkl"
JS_FILE = "js_links.pkl"  # 新添加的保存 script 链接的文件名
# 检索dayoo_links的上限
DAYOO_LIMIT = 3000

# 开始计时
start_time = time.time()

# 初始化 script 链接缓存集合
js_links_cache = set()

# 加载集合信息和节点顺序信息
def load_data():
    dayoo_file_path = os.path.join(SAVE_PATH, DAYOO_FILE)
    other_file_path = os.path.join(SAVE_PATH, OTHER_FILE)
    js_file_path = os.path.join(SAVE_PATH, JS_FILE)  # 新添加的 script 链接文件路径
    dayoo_links = set()
    other_links = set()
    js_links = set()  # 新添加的 script 链接集合
    url_queue = deque()

    if os.path.exists(dayoo_file_path):
        with open(dayoo_file_path, "rb") as f:
            dayoo_links, url_queue = pickle.load(f)
    if os.path.exists(other_file_path):
        with open(other_file_path, "rb") as f:
            other_links = pickle.load(f)
    if os.path.exists(js_file_path):  # 如果 script 链接文件存在，则加载内容
        with open(js_file_path, "rb") as f:
            js_links = pickle.load(f)

    return dayoo_links, other_links, js_links, url_queue  # 返回加载的数据


# 保存集合信息和节点顺序信息到文件
def save_data(dayoo_links, other_links, js_links, url_queue):
    if not os.path.exists(SAVE_PATH):
        os.makedirs(SAVE_PATH)
    with open(os.path.join(SAVE_PATH, DAYOO_FILE), "wb") as f:
        pickle.dump((dayoo_links, url_queue), f)
    with open(os.path.join(SAVE_PATH, OTHER_FILE), "wb") as f:
        pickle.dump(other_links, f)
    with open(os.path.join(SAVE_PATH, JS_FILE), "wb") as f:  # 保存 script 链接
        pickle.dump(js_links, f)


# 递归检索函数
def search_links(url_queue, dayoo_links, other_links, js_links,key):
    new_dayoo_count = 0  # 用于计数新增的 dayoo_links 的数量
    prev_link = None  # 用于记录前一个链接
    while url_queue and new_dayoo_count < DAYOO_LIMIT:
        url = url_queue.popleft()
        try:
            response = requests.get(url)
            response.raise_for_status()  # 检查响应状态，如果不是 200，则会抛出异常
            soup = BeautifulSoup(response.content, 'html.parser')

            # 获取当前页面中的所有超链接
            links = soup.find_all('a', href=True)

            for link in links:
                href = link['href']
                if key in href:
                    if href not in dayoo_links:
                        dayoo_links.add(href)
                        url_queue.append(href)  # 将新的链接加入队列
                        new_dayoo_count += 1
                        if new_dayoo_count >= DAYOO_LIMIT:
                            print("Reached DAYOO_LIMIT, stopping...")
                            return
                else:
                    if href not in other_links:
                        other_links.add(href)
                        link_text = link.get_text()  # 获取链接的标签名称
                        print("Link:", link_text, href)  # 打印链接的标签名称和链接
                        # 将不含有dayoo字段的链接和链接的标签名称传入数据库
                        if prev_link and prev_link in dayoo_links:
                            save_other_to_database(link_text, href, prev_link)

                prev_link = href  # 更新前一个链接

            # 检索每个网站的 script 标签，提取隐藏 URL
            search_script_tags(soup, url, js_links,key)

        except requests.exceptions.RequestException as e:
            print("Request Error:", e)
        except Exception as e:
            print("Error:", e)


# 检索每个网站的 script 标签，提取隐藏 URL
def search_script_tags(soup, url, js_links,key):
    script_tags = soup.find_all('script')
    for tag in script_tags:
        script_content = tag.get_text()
        # 使用正则表达式匹配隐藏 URL
        hidden_urls = re.findall(r'(http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)', script_content)
        for hidden_url in hidden_urls:
            if hidden_url.endswith(('.com', '.cn','.js')) or hidden_url.startswith(('http://', 'https://')):
                domain = urlparse(hidden_url).netloc.split(':')[0]  # 获取域名部分，忽略端口和参数
                if domain not in js_links_cache and str(key) not in hidden_url:
                    js_links_cache.add(domain)
                    if hidden_url not in js_links:  # 判断是否已经处理过
                        js_links.add(hidden_url)
                        save_js_to_database("Hidden URL", hidden_url, url)


# 将其他链接存入数据库
def save_other_to_database(name, url, before):
    save_to_database("data", name, url, before)

# 将 script 类型的链接存入数据库
def save_js_to_database(name, url, before):
    save_to_database("Jsa", name, url, before)


# 将链接存入数据库
def save_to_database(table, name, url, before):
    try:
        conn = sqlite3.connect("D:/debever/datasave/SearchLink")
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO {table} (name, URL, before) VALUES (?, ?, ?)", (name, url, before))
        conn.commit()
        conn.close()
        print("Saved to database:", name, url)
    except Exception as e:
        print("Error:", e)


# 主函数
def main():
    # 加载集合信息和节点顺序信息
    dayoo_links, other_links, js_links, url_queue = load_data()
    key = "dayoo"

    if not url_queue:  # 如果节点顺序信息为空，则从起始链接开始
        start_url = "https://news.dayoo.com/"
        url_queue.append(start_url)

    search_links(url_queue, dayoo_links, other_links, js_links,key)

    # 保存集合信息和节点顺序信息到文件
    save_data(dayoo_links, other_links, js_links, url_queue)

    # 打印集合的元素个数
    print("Number of elements in dayoo_links:", len(dayoo_links))
    print("Number of elements in other_links:", len(other_links))
    print("Number of elements in js_links:", len(js_links))

    # 结束计时
    end_time = time.time()
    elapsed_time = end_time - start_time
    print("Total time:", elapsed_time, "seconds")


if __name__ == "__main__":
    main()
