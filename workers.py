import concurrent.futures
import os
import random
import re
from uuid import uuid4

import requests
from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool, QThread, QRunnable
from bs4 import BeautifulSoup

from .db import Database
from .urls import urls_before_20220605
from aqt import mw


class UrlWorker(QObject):
    message_signal = pyqtSignal(str)
    complete_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.urls_to_handle = None
        self.mw = mw
        self.all_urls = None
        self.db_path = os.path.join(os.path.dirname(__file__), 'user_files', 'data.db')
        self.db = Database(self.db_path)
        self.urls_to_handle = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36'}

    def get_page_urls_in_database(self):
        # prepare news page urls, if first run (nothing in database) , set it to pre-prepared urls otherwise read
        # from database
        if not (urls_in_db := self.db.table('urls').get('url')):
            self.all_urls = urls_before_20220605
            self.db.table('urls').insertmany('url', self.all_urls)
        else:
            self.all_urls = urls_in_db

    def get_new_urls(self):
        # firstly get starting urls from albums
        self.message_signal.emit('Getting starting links from album...')
        starting_urls_in_album = []
        album_ids = ['1951342454759030784', '1517700086812704771']
        for mid in album_ids:
            album_link = f'https://mp.weixin.qq.com/mp/appmsgalbum?__biz=MzU1NDQ5NDIwNQ==&action=getalbum&album_id={mid}'
            res = requests.get(album_link, headers=self.headers)
            if res.status_code == 200:
                html = res.text
                soup = BeautifulSoup(html, 'html.parser')
                for tag in soup.find_all('li', {'data-title': re.compile('【NHK新闻听译】')}):
                    if '收藏版' not in tag['data-title']:
                        url = tag['data-link']
                        if url not in starting_urls_in_album:
                            starting_urls_in_album.append(url)
        self.message_signal.emit('Getting latest new news urls from starting urls...')
        self.get_urls_from_starting_url(starting_urls_in_album)

    def get_urls_from_starting_url(self, starting_urls: list) -> None:
        """get latest new urls from album starting urls"""
        urls_to_search = starting_urls
        new_url_count = 0
        url_existed_in_db_count = 0
        while url_existed_in_db_count < 10:
            urls_on_page = []
            url = urls_to_search.pop()
            html = requests.get(url, headers=self.headers).text
            soup = BeautifulSoup(html, 'html.parser')
            # get new urls on the page
            for tag in soup.find_all('a', text=re.compile('【NHK新闻听译】')):
                urls_on_page.append(tag['href'])

            for url_on_page in urls_on_page:
                if url_on_page not in self.all_urls:
                    self.all_urls.append(url_on_page)
                    urls_to_search.append(url_on_page)
                    new_url_count += 1
                    self.db.table('urls').insert(url=url_on_page)
                else:
                    url_existed_in_db_count += 1

            # if found 10 urls already in database, write new urls into db then stop searching
            if url_existed_in_db_count > 10:
                if new_url_count > 0:
                    self.message_signal.emit(f'Found {new_url_count} new urls and recorded into database')
                else:
                    self.message_signal.emit(f'<span style="color:salmon">No new urls found.</span>')
                break

    def check_collection(self):
        """check collection to find notes are not recorded in database"""
        nids = self.mw.col.find_notes("note:nhknews")
        for nid in nids:
            if nid not in self.db.table('notes').get('id'):
                note = self.mw.col.get_note(nid)
                page_url = note['PageUrl']
                audio_url = note['AudioUrl']
                page_id = self.db.table('urls').getone('id', url=page_url)
                self.db.table('notes').insert(id=nid, page_id=page_id, audio_url=audio_url)
            if nid not in self.db.table('log').get('note_id'):
                user_id = self.db.table('users').getone('id', name=self.mw.pm.name)
                self.db.table('log').insert(note_id=nid, user_id=user_id)

    def get_urls_in_collection(self):
        """get news page urls in anki collection"""
        nids = self.mw.col.find_notes('note:nhknews')
        urls_in_collection = []
        for nid in nids:
            note = self.mw.col.get_note(nid)
            urls_in_collection.append(note['PageUrl'])
        return urls_in_collection

    def run(self):
        """prepare urls to be handled
            1. check if urls used by notes but not recorded in database
            2. get page urls recorded in database
            3. get new urls from web
            4. the urls to be handled are stored in self.urls_to_handle
        """
        self.message_signal.emit('Preparing urls to be handled...')
        self.get_page_urls_in_database()
        self.get_new_urls()
        self.check_collection()
        urls_in_anki_collection = self.get_urls_in_collection()
        self.urls_to_handle = [url for url in self.all_urls if url not in urls_in_anki_collection]
        self.complete_signal.emit(self.urls_to_handle)


class TaskManager(QObject):
    message_signal = pyqtSignal(str)
    all_tasks_finished_signal = pyqtSignal()
    note_data_ready_signal = pyqtSignal(str, str, str, str)
    note_record_signal = pyqtSignal(int, str, str)
    task_finished_signal = pyqtSignal()

    def __init__(self, urls):
        super().__init__()
        self.tasks_finished = 0
        self.total_tasks = len(urls)
        self.urls = urls
        self.thread_pool = QThreadPool()
        self.mw = mw
        self.task_count = 0
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36'}

        self.db_path = os.path.join(os.path.dirname(__file__), 'user_files', 'data.db')
        self.db = Database(self.db_path)

        self.note_data_ready_signal.connect(self.new_note)
        self.note_record_signal.connect(self.record_data_to_database)
        self.task_finished_signal.connect(self.tasks_progress)

    def set_urls(self, urls):
        self.urls = urls

    def run(self):
        self.task_count = 0
        self.tasks_finished = 0
        self.total_tasks = len(self.urls)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5, thread_name_prefix='worker') as e:
            e.map(self.task, self.urls)

    def tasks_progress(self):
        self.tasks_finished += 1
        if self.tasks_finished == self.total_tasks:
            self.all_tasks_finished_signal.emit()
            self.message_signal.emit('<span style="color: MediumSeaGreen; font-size: 32px;">All tasks finished</span>')

    def task(self, url):
        """grab content from page
             1. get html
             2. get news text
             3. get rid of unwanted part
             4. replace brackets with word from new words list
             5. get audio links
             6. remove url from self.urls
         """
        self.task_count += 1
        self.message_signal.emit(f'{self.task_count}/{self.total_tasks} task starting....')
        thread = self.thread()
        self.message_signal.emit(
            f'Worker {thread.objectName()} is working on <a href="{url}" style="color: SlateGray">page{self.task_count}</a>')

        html = requests.get(url, headers=self.headers).text
        soup = BeautifulSoup(html, 'html.parser')
        sections = soup.find_all('section', {'data-autoskip': "1"})
        words_list = self.get_words_list(html)

        if sections:
            audio_urls = self.get_audios(html)
            for n, section in enumerate(sections):
                text = section.text
                text = self.remove_certain_text(text)
                jp, cn = self.split_text(text)
                if self.is_replaceable(jp):
                    if not words_list == [[]]:
                        try:
                            jp = self.replace_brackets_with_words(jp, words_list[n])
                        except IndexError:
                            pass

                try:
                    audio_url = audio_urls[n]
                except IndexError:
                    continue
                else:
                    # self.note_data_ready_signal.emit(jp, cn, self.url, audio_url)
                    self.new_note(jp, cn, url, audio_url)
        else:
            self.message_signal.emit('<span style="color: salmon">No news information was found.</span>')
            self.task_finished_signal.emit()

    def get_audios(self, html: str) -> list:
        """get audio links in html"""
        audio_keys = re.findall('voice_encode_fileid="(.*?)"', html)
        audio_links = []
        if audio_keys:
            for audio_key in audio_keys:
                audio_link = 'https://res.wx.qq.com/voice/getvoice?mediaid=' + audio_key
                audio_links.append(audio_link)
            return audio_links
        else:
            self.message_signal.emit('<span style="color: salmon">No audio found</span>')
            return []

    @staticmethod
    def remove_certain_text(text):
        """Get rid of some unwanted text"""
        part_list = ['生词', '背景知识', '単語', '单词']
        for part in part_list:
            if part in text:
                text = text[:text.index(part)]
        return text

    @staticmethod
    def get_words_list(html) -> list:
        """Get hidden new words list"""
        words_list = []

        # get all hidden sections
        hidden_sections = re.findall(r'<section.+?overflow: hidden.+?>(.+?)</section>', html)

        # get rid of sections without section tag
        hidden_sections = [sec for sec in hidden_sections if 'section' in sec]

        for hidden_section in hidden_sections:
            # get rid of tags
            text = re.sub('<.+?>', '', hidden_section)
            text = text.replace('&nbsp;', ' ')
            word_pattern = r'[（(]?\d+[.）)]\s*([ぁ-んァ-ンー\u4e00-\u9fff]+)[^ぁ-んァ-ンー\u4e00-\u9fff]'
            words = re.findall(word_pattern, text)
            words_list.append(words)

        return words_list

    @staticmethod
    def replace_brackets_with_words(jp, words):
        """replace brackets in text"""
        for n, word in enumerate(words):
            jp = re.sub(fr'[(（]\s*{n + 1}\s*[)）]', word, jp)
        return jp

    def get_news_title(self, url):
        """Get new title"""
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            html = res.text
            soup = BeautifulSoup(html, features='html.parser')
            title = soup.h1.text.strip()
            return title

    def split_text(self, text):
        """split text into jp and cn two segments"""
        text = re.sub(r'(。」|。”|。)', r'\g<1>\n', text)
        sentences = text.split('\n')
        jp, cn = "", ""
        p = ""
        current_lang_is_jp = True
        for sentence in sentences:
            if self.is_jp(sentence) != current_lang_is_jp:
                if current_lang_is_jp:
                    jp += f'<p>{p}</p>\n'
                else:
                    cn += f'<p>{p}</p>\n'
                current_lang_is_jp = not current_lang_is_jp
                p = ""
            if all([current_lang_is_jp, self.is_jp(sentence)]):
                p += sentence.strip()
            elif all([not current_lang_is_jp, not self.is_jp(sentence)]):
                p += sentence.strip()
        return jp, cn

    @staticmethod
    def is_jp(p: str) -> bool:
        """Check if text is japanese"""
        # if there are at least two blocks of kana return true
        if len(re.findall(r'[ぁ-んァ-ンー]+', p)) > 1:
            return True
        # if all are kana return true
        elif len(re.findall('[ぁ-んァ-ンー]', p[1:-1])) == len(p[1:-1]):
            return True
        # otherwise return false
        else:
            return False

    @staticmethod
    def is_replaceable(text) -> bool:
        """check if there are brackets and digits in the text to be replaced"""
        pattern = '[(（]\s*\d+\s*[)）]'
        if re.search(pattern, text):
            return True
        else:
            return False

    def new_note(self, jp, cn, page_url, audio_url):
        """create note with data"""
        if not self.mw.col.find_notes(f'note:nhknews Japanese:re:{jp}'):
            nhknews_model = self.mw.col.models.by_name('nhknews')
            note = self.mw.col.new_note(nhknews_model)
            note['Japanese'] = jp
            audio_filename = uuid4().hex + '.mp3'
            self.download_audio(audio_url, audio_filename)
            note['Pronunciation'] = f'[sound:{audio_filename}]'
            note['Chinese'] = cn
            note['PageUrl'] = page_url
            note['AudioUrl'] = audio_url
            langu_config = self.mw.addonManager.getConfig(__name__)
            nhknews_deck_name = langu_config.get('nhknews_deck', 'japanese')
            nhknews_deck = self.mw.col.decks.by_name(nhknews_deck_name)
            self.mw.col.add_note(note, nhknews_deck['id'])
            self.note_record_signal.emit(note.id, page_url, audio_url)
        else:
            self.message_signal.emit('<span style="color:salmon">Note already existed in collection</span>')

        self.task_finished_signal.emit()

    def download_audio(self, audio_url, audio_filename):
        """download audio into media folder"""
        res = requests.get(audio_url, headers=self.headers)
        if res.status_code == 200:
            audio_bytes = res.content
            audio_absolute_path = os.path.join(self.mw.col.media.dir(), audio_filename)
            assert type(audio_bytes) == bytes, 'audio data is NOT bytes'
            with open(audio_absolute_path, 'wb') as f:
                f.write(audio_bytes)
                self.message_signal.emit(f'Downloaded {audio_filename}')
        else:
            self.message_signal.emit(
                f'<span style="color:salmon">Downloading <a href="{audio_url}">Audio</a> failed</span>')

    def record_data_to_database(self, note_id, page_url, audio_url):
        """write note and user info into database"""
        user = self.mw.pm.name
        user_id = self.db.table('users').getone('id', name=user)
        page_id = self.db.table('urls').getone('id', url=page_url)
        self.db.table('notes').insert(id=note_id, page_id=page_id, audio_url=audio_url)
        self.db.table('log').insert(note_id=note_id, user_id=user_id)
        color = f'#{random.randint(0, 2 ** 24 - 1):06x}'
        self.message_signal.emit(
            f'Wrote Card ID <b style="color:{color}">{note_id}</b> info for User <b style="color:{color}">{user}</b> into database')
