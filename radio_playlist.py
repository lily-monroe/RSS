import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import xml.etree.ElementTree as ET

def pobierz_strone(url):
    """Pobiera zawartość strony HTML."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Sprawdza, czy zapytanie zakończyło się sukcesem (kody 2xx)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Wystąpił błąd podczas pobierania strony {url}: {e}")
        return None

def parsuj_myradioonline(html_content, stacja_nazwa):
    """Parsuje listę utworów ze strony myradioonline.pl."""
    soup = BeautifulSoup(html_content, 'html.parser')
    utwory = soup.find_all('div', class_='songCont')
    lista_parsowanych_utworow = []

    for utwor in utwory:
        txt1_div = utwor.find('div', class_='txt1 anim')
        
        czas_emisji_pelny = ''
        tytul_wykonawca_raw = ''

        if txt1_div:
            span_czas = txt1_div.find('span', class_='txt2')
            if span_czas:
                czas_emisji_pelny = span_czas.get('title', '').strip()
                tytul_wykonawca_raw = txt1_div.text.replace(czas_emisji_pelny, '').strip()
            else:
                tytul_wykonawca_raw = txt1_div.text.strip()

        wykonawca = ''
        tytul = ''

        if ' - ' in tytul_wykonawca_raw:
            parts = tytul_wykonawca_raw.split(' - ', 1)
            wykonawca = re.sub(r'^\d{2}:\d{2}', '', parts[0]).strip()
            tytul = parts[1].strip()
        else:
            tytul = tytul_wykonawca_raw.strip()
            tytul = re.sub(r'^\d{2}:\d{2}', '', tytul).strip()
            wykonawca = '' 

        czas_emisji = ''
        data_emisji = ''
        if czas_emisji_pelny:
            parts_czas = czas_emisji_pelny.split(' ')
            if len(parts_czas) == 2:
                data_emisji = parts_czas[0]
                czas_emisji = parts_czas[1]

        image_span = utwor.find('span', class_='cont anim')
        image_url = image_span.find('img', class_='js-img-lload').get('data-lazy-load', '') if image_span and image_span.find('img', class_='js-img-lload') else ''
        image_url_big = image_url.replace('50x50bb.webp', '1000x1000bb.webp') if image_url else ''

        youtube_id = utwor.get('data-youtube', '')
        # Używamy http://youtube.com/watch?v=... jako linku do YouTube
        youtube_link = f'http://youtube.com/watch?v={youtube_id}' if youtube_id else ''

        lista_parsowanych_utworow.append({
            'stacja': stacja_nazwa,
            'wykonawca': wykonawca,
            'tytul': tytul,
            'data_emisji': data_emisji,
            'czas_emisji': czas_emisji,
            'image_url_big': image_url_big,
            'youtube_link': youtube_link
        })
    return lista_parsowanych_utworow

def parsuj_ukradiolive(html_content, stacja_nazwa):
    """Parsuje listę utworów ze strony ukradiolive.com."""
    soup = BeautifulSoup(html_content, 'html.parser')
    lista_parsowanych_utworow = []

    playlist_items = soup.select('div.col-md-9 ul.list-group li.list-group-item')

    for item in playlist_items:
        text_content = item.get_text(strip=True)
        
        czas_emisji = ''
        wykonawca = ''
        tytul = ''

        match = re.match(r'(\d{1,2}:\d{2}\s(?:AM|PM))\s-\s(.*)', text_content)
        if match:
            czas_emisji_str = match.group(1).strip()
            artist_title_str = match.group(2).strip()

            try:
                dt_obj = datetime.strptime(czas_emisji_str, '%I:%M %p')
                czas_emisji = dt_obj.strftime('%H:%M')
            except ValueError:
                czas_emisji = czas_emisji_str 

            if ' - ' in artist_title_str:
                parts = artist_title_str.split(' - ', 1)
                wykonawca = parts[0].strip()
                tytul = parts[1].strip()
            else:
                tytul = artist_title_str 
        else:
            tytul = text_content 

        data_emisji = datetime.now().strftime('%d.%m.%Y') # Używamy dzisiejszej daty

        lista_parsowanych_utworow.append({
            'stacja': stacja_nazwa,
            'wykonawca': wykonawca,
            'tytul': tytul,
            'data_emisji': data_emisji,
            'czas_emisji': czas_emisji,
            'image_url_big': '', 
            'youtube_link': '' 
        })
    return lista_parsowanych_utworow


def wygeneruj_rss(wszystkie_utwory, nazwa_pliku="ALL_RADIO.xml"):
    """Generuje plik RSS 2.0 z danych utworów ze wszystkich stacji."""
    root = ET.Element('rss', version='2.0')
    channel = ET.SubElement(root, 'channel')
    ET.SubElement(channel, 'title').text = 'Agregowana Playlista Radiowa'
    ET.SubElement(channel, 'link').text = 'https://github.com/lily-monroe/RSS' 
    ET.SubElement(channel, 'description').text = 'Playlista z wielu stacji radiowych'

    for utwor in wszystkie_utwory:
        item = ET.SubElement(channel, 'item')
        
        item_title = f"[{utwor['stacja']}] {utwor['wykonawca']} - {utwor['tytul']}"
        if utwor['data_emisji'] and utwor['czas_emisji']:
             item_title += f" | {utwor['data_emisji']} {utwor['czas_emisji']}"
        
        item_description_parts = []
        if utwor['image_url_big']:
            item_description_parts.append(f'<img src="{utwor["image_url_big"]}"><br><br>')
        
        item_description_parts.append(f'<b>{utwor["wykonawca"]} - {utwor["tytul"]}</b><br>')
        
        if utwor['data_emisji'] and utwor['czas_emisji']:
            item_description_parts.append(f'{utwor["data_emisji"]} {utwor["czas_emisji"]} | ')
        
        encoded_artist = requests.utils.quote(utwor['wykonawca'])
        encoded_album = requests.utils.quote(utwor['tytul'])
        cover_link = f"https://covers.musichoarders.xyz/?artist={encoded_artist}&album={encoded_album}&country=us&sources=amazonmusic"
        item_description_parts.append(f'<a href="{cover_link}">COVER</a>')

        if utwor['youtube_link']:
            item_description_parts.append(f' | <a href="{utwor["youtube_link"]}">YOUTUBE</a>')
        
        item_description = "".join(item_description_parts)

        ET.SubElement(item, 'title').text = item_title
        ET.SubElement(item, 'description').text = item_description
        ET.SubElement(item, 'pubDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
        ET.SubElement(item, 'link').text = 'https://github.com/lily-monroe/RSS' 

    tree = ET.ElementTree(root)
    tree.write(nazwa_pliku, encoding='UTF-8', xml_declaration=True)
    print(f"Plik RSS został wygenerowany jako: {nazwa_pliku}")


if __name__ == "__main__":
    stacje_radiowe = {
        'Radio 357': 'https://myradioonline.pl/radio-357/',
        'ChilliZET': 'https://myradioonline.pl/chillizet/',
        'Radio Nowy Świat': 'https://myradioonline.pl/radio-nowy-swiat/',
        'RMF FM': 'https://myradioonline.pl/rmf-fm/playlista',
        'RMF MAXXX': 'https://myradioonline.pl/rmf-maxxx/',
        'Radio ZET': 'https://myradioonline.pl/radio-zet/',
        'PR Czwórka': 'https://myradioonline.pl/polskie-radio-czworka/',
        'PR Trójka': 'https://myradioonline.pl/polskie-radio-trojka/',
        'Radio Eska': 'https://myradioonline.pl/radio-eska/',
        'BBC Radio 1': 'https://ukradiolive.com/bbc-radio-1/',
        'BBC Radio 2': 'https://ukradiolive.com/bbc-radio-2/',
        'Virgin Radio UK': 'https://ukradiolive.com/virgin-radio-uk/',
        'Heart London': 'https://ukradiolive.com/heart-london/'
    }

    wszystkie_parsowane_utwory = []

    for nazwa_stacji, url_stacji in stacje_radiowe.items():
        print(f"Pobieram i parsuję playlistę dla: {nazwa_stacji} z {url_stacji}")
        html_content = pobierz_strone(url_stacji)
        if html_content:
            if "myradioonline.pl" in url_stacji:
                parsowane_utwory = parsuj_myradioonline(html_content, nazwa_stacji)
                wszystkie_parsowane_utwory.extend(parsowane_utwory)
            elif "ukradiolive.com" in url_stacji:
                parsowane_utwory = parsuj_ukradiolive(html_content, nazwa_stacji)
                wszystkie_parsowane_utwory.extend(parsowane_utwory)
            else:
                print(f"Brak zdefiniowanej funkcji parsowania dla {url_stacji}")
        else:
            print(f"Nie udało się pobrać treści dla {url_stacji}")

    if wszystkie_parsowane_utwory:
        wygeneruj_rss(wszystkie_parsowane_utwory, nazwa_pliku="ALL_RADIO.xml") # Nazwa pliku XML
    else:
        print("Nie pobrano żadnych utworów z żadnej stacji.")
