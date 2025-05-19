import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import xml.etree.ElementTree as ET

def pobierz_i_parsuj_playliste(url):
    """Pobiera stronę i parsuje listę utworów."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        utwory = soup.find_all('div', class_='songCont')
        return utwory
    except requests.exceptions.RequestException as e:
        print(f"Wystąpił błąd podczas pobierania strony: {e}")
        return []

def wygeneruj_rss(utwory, nazwa_pliku="playlista_radio357.xml"):
    """Generuje plik RSS 2.0 z danych utworów."""
    root = ET.Element('rss', version='2.0')
    channel = ET.SubElement(root, 'channel')
    ET.SubElement(channel, 'title').text = 'RADIO 357'
    ET.SubElement(channel, 'link').text = 'https://myradioonline.pl/radio-357/'
    ET.SubElement(channel, 'description').text = 'Aktualna playlista Radio 357'

    for utwor in utwory:
        item = ET.SubElement(channel, 'item')
        txt1_div = utwor.find('div', class_='txt1 anim')
        
        czas_emisji_pelny = ''
        tytul_wykonawca = ''

        if txt1_div:
            # Znajdź span z czasem emisji
            span_czas = txt1_div.find('span', class_='txt2')
            if span_czas:
                czas_emisji_pelny = span_czas.get('title', '').strip()
                # Usuń czas emisji z tekstu, aby uzyskać czysty tytuł i wykonawcę
                tytul_wykonawca = txt1_div.text.replace(czas_emisji_pelny, '').strip()
            else:
                tytul_wykonawca = txt1_div.text.strip() # Jeśli nie ma span.txt2, użyj całego tekstu

        wykonawca = ''
        tytul = ''

        # Podziel wykonawcę i tytuł
        if ' - ' in tytul_wykonawca:
            parts = tytul_wykonawca.split(' - ', 1)
            # Użyj wyrażenia regularnego do usunięcia "HH:MM" na początku nazwy wykonawcy
            wykonawca = re.sub(r'^\d{2}:\d{2}', '', parts[0]).strip()
            tytul = parts[1].strip()
        else:
            tytul = tytul_wykonawca.strip() # Jeśli brak separatora, cały tekst to tytuł
            # Również usuń ewentualną godzinę z samego tytułu, jeśli tam się znajdzie
            tytul = re.sub(r'^\d{2}:\d{2}', '', tytul).strip()


        czas_emisji = ''
        data_emisji = ''
        if czas_emisji_pelny:
            # Zakładamy format "DD.MM.RRRR HH:MM"
            parts_czas = czas_emisji_pelny.split(' ')
            if len(parts_czas) == 2:
                data_emisji = parts_czas[0]
                czas_emisji = parts_czas[1]

        image_span = utwor.find('span', class_='cont anim')
        image_url = image_span.find('img', class_='js-img-lload').get('data-lazy-load', '') if image_span and image_span.find('img', class_='js-img-lload') else ''
        image_url_big = image_url.replace('50x50bb.webp', '1000x1000bb.webp') if image_url else ''

        youtube_id = utwor.get('data-youtube', '')
        youtube_link = f'http://youtube.com/watch?v={youtube_id}' if youtube_id else '' # Poprawiony link YouTube

        # Skonstruuj tytuł elementu
        item_title = f'{wykonawca} - {tytul} | {data_emisji} {czas_emisji}' if wykonawca and tytul else f'{tytul} | {data_emisji} {czas_emisji}'
        
        # Skonstruuj opis elementu
        # Ważne: wykonawca i tytuł w linku do coveru muszą być zakodowane do URL
        encoded_artist = requests.utils.quote(wykonawca)
        encoded_album = requests.utils.quote(tytul)
        cover_link = f'https://covers.musichoarders.xyz/?artist={encoded_artist}&album={encoded_album}&country=us&sources=amazonmusic'

        item_description = f'<img src="{image_url_big}"><br><br> <b>{wykonawca} - {tytul}</b><br> {data_emisji} {czas_emisji} | <a href="{cover_link}">COVER</a> | <a href="{youtube_link}">YOUTUBE</a>'
        
        ET.SubElement(item, 'title').text = item_title
        ET.SubElement(item, 'description').text = item_description
        ET.SubElement(item, 'pubDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
        ET.SubElement(item, 'link').text = 'https://myradioonline.pl/radio-357/'

    tree = ET.ElementTree(root)
    tree.write(nazwa_pliku, encoding='UTF-8', xml_declaration=True)
    print(f"Plik RSS został wygenerowany jako: {nazwa_pliku}")

if __name__ == "__main__":
    url_radio357 = "https://myradioonline.pl/radio-357/"
    lista_utworow = pobierz_i_parsuj_playliste(url_radio357)
    if lista_utworow:
        wygeneruj_rss(lista_utworow)