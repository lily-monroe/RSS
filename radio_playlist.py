import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

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

def parsuj_playliste(html_content, stacja_nazwa, stacja_url):
    """Parsuje listę utworów ze stron myradioonline.pl/playlista i ukradiolive.com/playlist."""
    soup = BeautifulSoup(html_content, 'html.parser')
    utwory_html = soup.find_all('div', itemprop='track', class_='yt-row')
    lista_parsowanych_utworow = []

    for utwor_html in utwory_html:
        youtube_div = utwor_html.find('div', class_=re.compile(r'txt1 anim'))
        youtube_id = youtube_div.get('data-youtube', '') if youtube_div else ''
        
        # POPRAWKA: Pobieramy czas z tekstowej zawartości span
        czas_emisji_span = utwor_html.find('span', class_='txt2 mcolumn')
        czas_emisji_pelny = czas_emisji_span.text.strip() if czas_emisji_span else ''

        # Dodajemy bieżący rok, jeśli format to "DD.MM HH:MM"
        if re.match(r'^\d{2}\.\d{2}\s\d{2}:\d{2}$', czas_emisji_pelny):
            current_year = datetime.now().year
            # Tworzymy pełny format z rokiem, a następnie parsujemy i formatujemy ponownie
            # aby uzyskać zawsze format "DD.MM.RRRR HH:MM"
            try:
                temp_dt = datetime.strptime(f"{czas_emisji_pelny} {current_year}", '%d.%m %H:%M %Y')
                czas_emisji_pelny = temp_dt.strftime('%d.%m.%Y %H:%M')
            except ValueError:
                # Jeśli parsowanie się nie powiedzie (np. niepoprawna data), zostawiamy jak jest
                pass 
        
        wykonawca_span = utwor_html.find('span', itemprop='byArtist')
        wykonawca = wykonawca_span.text.strip() if wykonawca_span else ''

        tytul_span = utwor_html.find('span', itemprop='name')
        tytul = tytul_span.text.strip() if tytul_span else ''

        if not (wykonawca and tytul and czas_emisji_pelny):
            continue

        lista_parsowanych_utworow.append({
            'stacja': stacja_nazwa,
            'stacja_url': stacja_url,
            'wykonawca': wykonawca,
            'tytul': tytul,
            'czas_emisji_pelny': czas_emisji_pelny, 
            'youtube_id': youtube_id
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

    for utwor in posortowane_utwory:
        item = ET.SubElement(channel, 'item')
        
        item_title = f"[{utwor['stacja']}] {utwor['wykonawca']} - {utwor['tytul']} | {utwor['czas_emisji_pelny']}"
        ET.SubElement(item, 'title').text = item_title
        
        item_description_parts = []
        
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

        if utwor['youtube_id']:
            youtube_full_link = f'http://youtube.com/watch?v={utwor["youtube_id"]}'
            item_description_parts.append(f' | <a href="{youtube_full_link}">YOUTUBE</a>')
        
        item_description = "".join(item_description_parts)
        ET.SubElement(item, 'description').text = item_description

        ET.SubElement(item, 'link').text = utwor['stacja_url']
        
        try:
            dt_pub = datetime.strptime(utwor['czas_emisji_pelny'], '%d.%m.%Y %H:%M')
            ET.SubElement(item, 'pubDate').text = dt_pub.strftime('%a, %d %b %Y %H:%M:%S +0000') 
        except ValueError:
            print(f"Ostrzeżenie: Nie udało się sparsować daty '{utwor['czas_emisji_pelny']}'. Używam bieżącej daty dla pubDate.")
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
            parsowane_utwory = parsuj_playliste(html_content, nazwa_stacji, url_stacji)
            wszystkie_parsowane_utwory.extend(parsowane_utwory)
        else:
            print(f"Nie udało się pobrać treści dla {url_stacji}")

    if wszystkie_parsowane_utwory:
        wygeneruj_rss(wszystkie_parsowane_utwory, nazwa_pliku="radio_playlist.xml") 
    else:
        print("Nie pobrano żadnych utworów z żadnej stacji.")
