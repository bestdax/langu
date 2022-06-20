import os
from concurrent.futures import ThreadPoolExecutor
import threading

import re
import requests
from bs4 import BeautifulSoup
from uuid import uuid4

try:
    from nhk.urls import urls_before_20220605
    from nhk.db import Database
except ImportError:
    from urls import urls_before_20220605
    from db import Database

from PyQt6.QtCore import QObject, pyqtSignal
from aqt import mw


class NHKNews(QObject):
    note_ready_signal = pyqtSignal(str, str, str, str)
    message_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.urls = None
        self.urls_to_handle = None
        self.db_path = os.path.join(os.path.dirname(__file__), 'user_files', 'data.db')
        self.db = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36'}
        self.mw = mw

        self.urls_to_handle = []
        self.task_count = 0
        self.total_tasks = 0
        self.data = []

        # when note data is ready, trigger new note function
        self.note_ready_signal.connect(self.new_note)

    def get_local_urls(self):
        # prepare news page urls, if first run, set it to pre-pre-paired urls otherwise read from database
        if not (urls_in_db := self.db.get('SELECT URL FROM urls')):
            self.urls = urls_before_20220605
        else:
            self.urls = urls_in_db

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
                        if url not in self.urls:
                            self.urls.append(url)
        self.message_signal.emit('Getting latest new news urls from starting urls...')
        self.get_urls_from_starting_urls(starting_urls_in_album)

        # write new urls into database
        urls_in_db = self.db.get('SELECT URL FROM urls')
        new_urls = [url for url in self.urls if url not in urls_in_db]
        self.db.executemany('INSERT INTO urls (URL) VALUES (?)', new_urls)
        self.message_signal.emit(f'Added {len(new_urls)} news page urls into database')

    def get_urls_from_starting_urls(self, starting_urls: [str]) -> None:
        """get latest new urls from album starting ten urls"""
        new_urls = []
        new_url_count = 0
        existed_url_count = 0
        for url in starting_urls:
            html = requests.get(url, headers=self.headers).text
            soup = BeautifulSoup(html, 'html.parser')

            # get new urls on the page
            for tag in soup.find_all('a', text=re.compile('【NHK新闻听译】')):
                new_urls.append(tag['href'])
            for new_url in new_urls:
                if new_url not in self.urls:
                    self.urls.append(new_url)
                    new_url_count += 1
                else:
                    existed_url_count += 1

            # if found 10 urls already in database then stop searching
            if existed_url_count > 10:
                break

        self.message_signal.emit(f'Found {new_url_count} new urls')

    def check_collection(self):
        """check collection to find notes are not recorded in database"""
        db = Database(self.db_path)
        nids = self.mw.col.find_notes("note:nhknews")
        for nid in nids:
            if not db.get('select id from notes where id=?', nid):
                note = self.mw.col.get_note(nid)
                page_url = note['PageUrl']
                audio_url = note['AudioUrl']
                page_id = db.get('select id from urls where url=?', page_url)
                db.execute(f'INSERT INTO notes (ID, PAGE_ID, AUDIO_URL) VALUES (?, ?, ?, ?)', nid, page_id, audio_url)
            if not db.get(f'SELECT NOTE_ID FROM log WHERE NOTE_ID=?', nid):
                user_id = db.get(f'SELECT NOTE_ID FROM users WHERE NAME=?', self.mw.pm.name)
                db.execute(f'INSERT INTO log (NOTE_ID, USER_ID) VALUES (?, ?)', nid, user_id)
        db.close()

    def grab_content(self, url):
        """grab content from page
            2. get html
            3. get news text
            4. get rid of unwanted part
            5. replace brackets with word from new words list
            6. get audio links
            7. remove url from self.urls
        """
        self.message_signal.emit(f'{len(self.urls_to_handle)} urls in the queue')
        self.urls_to_handle.remove(url)
        self.task_count += 1
        thread = threading.currentThread()

        self.message_signal.emit(
            f'{self.task_count}/{self.total_tasks} {thread.name} is working on page {self.get_news_title(url)}')
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
                        jp = self.replace_brackets_with_words(jp, words_list[n])
                try:
                    audio_url = audio_urls[n]
                except IndexError:
                    continue
                else:
                    self.note_ready_signal.emit(jp, cn, url, audio_url)

    @staticmethod
    def get_audios(html: str) -> list:
        """get audio links in html"""
        audio_keys = re.findall('voice_encode_fileid="(.*?)"', html)
        audio_links = []
        if audio_keys:
            for audio_key in audio_keys:
                audio_link = 'https://res.wx.qq.com/voice/getvoice?mediaid=' + audio_key
                audio_links.append(audio_link)
            return audio_links
        else:
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

        # Get all new page urls in anki collection
        db = Database(self.db_path)
        nids = self.mw.col.find_notes('note:nhknews')
        audio_urls = []
        for nid in nids:
            note = self.mw.col.get_note(nid)
            url = note['AudioUrl']
            audio_urls.append(url)

        # if audio url not in anki collection, then create new note
        if audio_url not in audio_urls:
            nhknews_model = self.mw.col.models.by_name('nhknews')
            note = self.mw.col.new_note(nhknews_model)
            note['Japanese'] = jp
            audio_filename = uuid4().hex + '.mp3'
            self.download_audio(audio_url, audio_filename)
            note['Pronunciation'] = f'[sound:{audio_filename}]'
            note['Chinese'] = cn
            note['PageUrl'] = page_url
            note['AudioUrl'] = audio_url
            nhknews_deck = self.mw.col.decks.by_name(self.mw.nhknews_deck_name)

            self.mw.col.add_note(note, nhknews_deck['id'])
            self.record_data_to_database(note.id, page_url, audio_url)
        else:
            self.message_signal.emit(f"<a href={page_url}>Page</a> already in Anki collection.")

    def record_data_to_database(self, note_id, page_url, audio_url):
        """write note and user info into database"""
        db = Database(self.db_path)
        user = self.mw.pm.name
        user_id = db.get(f'SELECT ID FROM users WHERE NAME=?', user)
        page_id = db.get(f'SELECT ID FROM urls WHERE URL=?', page_url)
        db.execute(f'INSERT INTO NOTES (ID, PAGE_ID, AUDIO_URL) VALUES (?, ?, ?)', note_id, page_id, audio_url)
        db.execute(f'INSERT INTO log (NOTE_ID, USER_ID) VALUES (?, ?)', note_id, user_id)
        self.message_signal.emit(
            f'Wrote Card ID <b>{note_id}</b> info for User <b>{user}</b> into database')
        db.close()

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
            self.message_signal.emit(f'Downloading <a href="{audio_url}">Audio</a> failed')

    def get_urls_in_collection(self):
        """get news page urls in anki collection"""
        nids = self.mw.col.find_notes('note:nhknews')
        urls_in_collection = []
        for nid in nids:
            note = self.mw.col.get_note(nid)
            urls_in_collection.append(note['PageUrl'])
        return urls_in_collection

    def scrap(self):
        self.db = Database(self.db_path)
        self.get_local_urls()
        self.get_new_urls()
        self.check_collection()
        self.message_signal.emit('Scrapping started...')

        # get all urls stored in table urls, minus urls used in notes, and get url_to_handle list
        all_urls = self.db.get("SELECT URL FROM urls")
        urls_in_collection = self.get_urls_in_collection()
        self.db.close()
        self.urls_to_handle = [url for url in all_urls if url not in urls_in_collection]

        self.total_tasks = len(self.urls_to_handle)
        max_workers = 10
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='worker') as e:
            e.map(self.grab_content, self.urls_to_handle[:20])
            e.shutdown(wait=True, cancel_futures=False)

        self.message_signal.emit('<h1>DONE</h1>')


if __name__ == '__main__':
    nhk = NHKNews()
