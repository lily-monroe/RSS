import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus
# import json # Niepotrzebne już, jeśli nie używamy iTunes API

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

# Funkcja pobierz_obrazek_z_covers_musichoarders nie jest już potrzebna, jeśli używamy tylko YouTube
# def pobierz_obrazek_z_covers_musichoarders(artist, title):
#    ...

# Funkcja pobierz_obrazek_z_itunes nie jest już potrzebna
# def pobierz_obrazek_z_itunes(artist, title):
#    ...


def parsuj_myradioonline(html_content, stacja_nazwa, stacja_url):
    """Parsuje listę utworów ze strony myradioonline.pl/playlista."""
    soup = BeautifulSoup(html_content, 'html.parser')
    utwory_html = soup.find_all('div', itemprop='track', class_='yt-row')
    lista_parsowanych_utworow = []

    for utwor_html in utwory_html:
        youtube_id = utwor_html.find('div', class_=re.compile(r'txt1 anim'))
        youtube_id = youtube_id.get('data-youtube', '') if youtube_id else ''
        
        # POPRAWKA: Pobieramy czas z atrybutu data-original-title
        czas_emisji_span = utwor_html.find('span', class_='txt2 mcolumn')
        czas_emisji_pelny = czas_emisji_span.get('data-original-title', '').strip() if czas_emisji_span else ''

        wykonawca_span = utwor_html.find('span', itemprop='byArtist')
        wykonawca = wykonawca_span.text.strip() if wykonawca_span else ''

        tytul_span = utwor_html.find('span', itemprop='name')
        tytul = tytul_span.text.strip() if tytul_span else ''

        # Link do obrazka będzie generowany z youtube_id, więc nie pobieramy go stąd
        # image_url_big = '' 
        
        if not (wykonawca and tytul and czas_emisji_pelny):
            continue

        lista_parsowanych_utworow.append({
            'stacja': stacja_nazwa,
            'stacja_url': stacja_url,
            'wykonawca': wykonawca,
            'tytul': tytul,
            'czas_emisji_pelny': czas_emisji_pelny, 
            'youtube_id': youtube_id # Nadal potrzebujemy ID YouTube
        })
    return lista_parsowanych_utworow

def parsuj_ukradiolive(html_content, stacja_nazwa, stacja_url):
    """Parsuje listę utworów ze strony ukradiolive.com/playlist."""
    soup = BeautifulSoup(html_content, 'html.parser')
    lista_parsowanych_utworow = []

    playlist_items = soup.select('div.col-md-9 ul.list-group li.list-group-item') 

    for item in playlist_items:
        text_content = item.get_text(strip=True)
        
        czas_emisji_str = ''
        wykonawca = ''
        tytul = ''

        match = re.match(r'(\d{1,2}:\d{2}\s(?:AM|PM))\s-\s(.*)', text_content)
        if match:
            czas_emisji_str = match.group(1).strip()
            artist_title_str = match.group(2).strip()

            try:
                dt_obj = datetime.strptime(czas_emisji_str, '%I:%M %p')
                dzisiejsza_data = datetime.now().strftime('%d.%m.%Y')
                czas_emisji_pelny = f"{dzisiejsza_data} {dt_obj.strftime('%H:%M')}"
            except ValueError:
                czas_emisji_pelny = f"{datetime.now().strftime('%d.%m.%Y')} {czas_emisji_str}" 
            
            if ' - ' in artist_title_str:
                parts = artist_title_str.split(' - ', 1)
                wykonawca = parts[0].strip()
                tytul = parts[1].strip()
            else:
                tytul = artist_title_str 
        else:
            tytul = text_content
            czas_emisji_pelny = f"{datetime.now().strftime('%d.%m.%Y')} {datetime.now().strftime('%H:%M')}"

        lista_parsowanych_utworow.append({
            'stacja': stacja_nazwa,
            'stacja_url': stacja_url,
            'wykonawca': wykonawca,
            'tytul': tytul,
            'czas_emisji_pelny': czas_emisja_pelny, 
            'youtube_id': '' # Te strony nie dostarczają ID YouTube
        })
    return lista_parsowanych_utworow


def wygeneruj_rss(wszystkie_utwory, nazwa_pliku="radio_playlist.xml"):
    """Generuje plik RSS 2.0 z danych utworów ze wszystkich stacji."""
    root = ET.Element('rss', version='2.0')
    channel = ET.SubElement(root, 'channel')
    ET.SubElement(channel, 'title').text = 'ALL RADIO' 
    ET.SubElement(channel, 'link').text = 'https://github.com/lily-monroe/RSS' 
    ET.SubElement(channel, 'description').text = 'Playlista z wielu stacji radiowych'

    def get_sort_key(item):
        try:
            return datetime.strptime(item['czas_emisji_pelny'], '%d.%m.%Y %H:%M')
        except ValueError:
            return datetime.min 

    posortowane_utwory = sorted(wszystkie_utwory, key=get_sort_key, reverse=True)

    for utwor in posortowane_utwory: # Używamy posortowanych utworów
        item = ET.SubElement(channel, 'item')
        
        # Element <title>
        item_title = f"[{utwor['stacja']}] {utwor['wykonawca']} - {utwor['tytul']} | {utwor['czas_emisji_pelny']}"
        ET.SubElement(item, 'title').text = item_title
        
        # Element <description>
        item_description_parts = []
        
        # GENEROWANIE OBRAZKA Z YOUTUBE ID
        youtube_image_url = ""
        if utwor['youtube_id']:
            youtube_image_url = f"https://img.youtube.com/vi/{utwor['youtube_id']}/maxresdefault.jpg"
            item_description_parts.append(f'<img src="{youtube_image_url}"><br><br>')
        
        item_description_parts.append(f'<b>{utwor["wykonawca"]} - {utwor["tytul"]}</b><br>')
        item_description_parts.append(f'{utwor["czas_emisji_pelny"]} | ')
        
        encoded_artist = quote_plus(utwor['wykonawca'])
        encoded_album = quote_plus(utwor['tytul']) 
        cover_link = f"https://covers.musichoarders.xyz/?artist={encoded_artist}&album={encoded_album}&country=us&sources=amazonmusic"
        item_description_parts.append(f'<a href="{cover_link}">COVER</a>')

        if utwor['youtube_id']: # Upewnij się, że link YouTube jest generowany tylko jeśli mamy ID
            youtube_full_link = f'http://youtube.com/watch?v={utwor["youtube_id"]}'
            item_description_parts.append(f' | <a href="{youtube_full_link}">YOUTUBE</a>')
        
        item_description = "".join(item_description_parts)
        ET.SubElement(item, 'description').text = item_description

        ET.SubElement(item, 'link').text = utwor['stacja_url']
        
        try:
            dt_pub = datetime.strptime(utwor['czas_emisji_pelny'], '%d.%m.%Y %H:%M')
            ET.SubElement(item, 'pubDate').text = dt_pub.strftime('%a, %d %b %Y %H:%M:%S +0000') 
        except ValueError:
            ET.SubElement(item, 'pubDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')


    tree = ET.ElementTree(root)
    tree.write(nazwa_pliku, encoding='UTF-8', xml_declaration=True)
    print(f"Plik RSS został wygenerowany jako: {nazwa_pliku}")


if __name__ == "__main__":
    stacje_radiowe = {
        'Radio 357': 'https://myradioonline.pl/radio-357/playlista',
        'ChilliZET': 'https://myradioonline.pl/chillizet/playlista',
        'Radio Nowy Świat': 'https://myradioonline.pl/radio-nowy-swiat/playlista',
        'RMF FM': 'https://myradioonline.pl/rmf-fm/playlista',
        'RMF MAXXX': 'https://myradioonline.pl/rmf-maxxx/playlista',
        'Radio ZET': 'https://myradioonline.pl/radio-zet/playlista',
        'PR Czwórka': 'https://myradioonline.pl/polskie-radio-czworka/playlista',
        'PR Trójka': 'https://myradioonline.pl/polskie-radio-trojka/playlista',
        'Radio Eska': 'https://myradioonline.pl/radio-eska/playlista',
        'BBC Radio 1': 'https://ukradiolive.com/bbc-radio-1/playlist',
        'BBC Radio 2': 'https://ukradiolive.com/bbc-radio-2/playlist',
        'Virgin Radio UK': 'https://ukradiolive.com/virgin-radio-uk/playlist',
        'Heart London': 'https://ukradiolive.com/heart-london/playlist'
    }

    wszystkie_parsowane_utwory = []

    for nazwa_stacji, url_stacji in stacje_radiowe.items():
        print(f"Pobieram i parsuję playlistę dla: {nazwa_stacji} z {url_stacji}")
        html_content = pobierz_strone(url_stacji)
        if html_content:
            if "myradioonline.pl" in url_stacji:
                parsowane_utwory = parsuj_myradioonline(html_content, nazwa_stacji, url_stacji)
                wszystkie_parsowane_utwory.extend(parsowane_utwory)
            elif "ukradiolive.com" in url_stacji:
                parsowane_utwory = parsuj_ukradiolive(html_content, nazwa_stacji, url_stacji)
                wszystkie_parsowane_utwory.extend(parsowane_utwory) 
            else:
                print(f"Brak zdefiniowanej funkcji parsowania dla {url_stacji}")
        else:
            print(f"Nie udało się pobrać treści dla {url_stacji}")

    if wszystkie_parsowane_utwory:
        wygeneruj_rss(wszystkie_parsowane_utwory, nazwa_pliku="radio_playlist.xml") 
    else:
        print("Nie pobrano żadnych utworów z żadnej stacji.")
