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

def parsuj_playliste(html_content, stacja_nazwa, stacja_base_url):
    """Parsuje listę utworów z nowej struktury HTML."""
    soup = BeautifulSoup(html_content, 'html.parser')
    utwory_html = soup.find_all('div', class_='songCont')
    lista_parsowanych_utworow = []

    for utwor_html in utwory_html:
        youtube_id = utwor_html.get('data-youtube', '')
        
        album_cover_url_base = ''
        image_cont_span = utwor_html.find('span', class_='cont anim')
        if image_cont_span:
            img_tag = image_cont_span.find('img')
            if img_tag:
                album_cover_url_base = img_tag.get('data-lazy-load', '')
                if album_cover_url_base.endswith('/50x50bb.webp'):
                    album_cover_url_base = album_cover_url_base[:-len('/50x50bb.webp')]

        artysta_tytul_alt = ''
        if image_cont_span:
            img_tag = image_cont_span.find('img')
            if img_tag:
                artysta_tytul_alt = img_tag.get('alt', '')
                
        czas_emisji_pelny = ''
        czas_emisji_span = utwor_html.find('span', class_='txt2')
        if czas_emisji_span:
            czas_emisji_pelny = czas_emisji_span.get('title', '').strip()

        if re.match(r'^\d{2}\.\d{2}\s\d{2}:\d{2}$', czas_emisji_pelny):
            current_year = datetime.now().year
            try:
                temp_dt = datetime.strptime(f"{czas_emisji_pelny} {current_year}", '%d.%m %H:%M %Y')
                czas_emisji_pelny = temp_dt.strftime('%d.%m.%Y %H:%M')
            except ValueError:
                pass 
        
        wykonawca = ''
        tytul = ''
        txt1_div = utwor_html.find('div', class_='txt1 anim')
        if txt1_div:
            text_content = txt1_div.get_text(separator=' ', strip=True) 
            # Usuwamy początkowy czas (np. "00:03" lub "23:01") z tekstu
            match = re.match(r'^\d{2}:\d{2}\s+(.*)', text_content)
            if match:
                artist_title_raw = match.group(1).strip()
                if ' - ' in artist_title_raw:
                    parts = artist_title_raw.split(' - ', 1)
                    wykonawca = parts[0].strip()
                    tytul = parts[1].strip()
            
        link_do_playlisty = stacja_base_url
        # Zapewniamy, że link do playlisty kończy się na /playlist lub /playlista
        if stacja_base_url.startswith('https://ukradiolive.com/'):
            if not link_do_playlisty.endswith('/playlist'):
                link_do_playlisty += '/playlist'
        elif stacja_base_url.startswith('https://myradioonline.pl/'):
            # Dla myradioonline.pl zawsze chcemy /playlista
            if not link_do_playlisty.endswith('/playlista'):
                # Sprawdzamy czy link nie kończy się na /playlist i wtedy zmieniamy
                if link_do_playlisty.endswith('/playlist'):
                    link_do_playlisty = link_do_playlisty.replace('/playlist', '/playlista')
                else: # Jeśli nie kończy się ani na /playlist ani /playlista
                    link_do_playlisty += '/playlista'


        if not (wykonawca and tytul and czas_emisji_pelny):
            continue

        lista_parsowanych_utworow.append({
            'stacja': stacja_nazwa,
            'stacja_base_url': stacja_base_url,
            'stacja_playlist_url': link_do_playlisty,
            'wykonawca': wykonawca,
            'tytul': tytul,
            'artysta_tytul_alt': artysta_tytul_alt,
            'czas_emisji_pelny': czas_emisji_pelny, 
            'youtube_id': youtube_id,
            'album_cover_url_base': album_cover_url_base
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
        
        item_title = f"[{utwor['stacja']}] {utwor['artysta_tytul_alt']} | {utwor['czas_emisji_pelny']}"
        ET.SubElement(item, 'title').text = item_title
        
        item_description_parts = []
        
        # Obrazek w description: warunkowe zastępowanie
        final_image_url = ''
        # Sprawdzamy, czy album_cover_url_base wygląda na "default.webp"
        if utwor['album_cover_url_base'] and 'default.webp' in utwor['album_cover_url_base'] and utwor['youtube_id']:
            # POPRAWKA: Używamy nowego wzoru dla YouTube
            final_image_url = f"https://img.youtube.com/vi/{utwor['youtube_id']}/maxresdefault.jpg"
        elif utwor['album_cover_url_base']:
            final_image_url = f"{utwor['album_cover_url_base']}/1000x1000bb.webp"
        elif utwor['youtube_id']: # Fallback, jeśli nie ma okładki ani "default.webp"
            final_image_url = f"https://img.youtube.com/vi/{utwor['youtube_id']}/maxresdefault.jpg" # Standardowa miniatura YouTube

        if final_image_url:
            item_description_parts.append(f'<img src="{final_image_url}"><br><br>')
        
        item_description_parts.append(f'<b>{utwor["artysta_tytul_alt"]}</b><br>')
        item_description_parts.append(f'{utwor["czas_emisji_pelny"]} | ')
        
        encoded_artist = quote_plus(utwor['wykonawca'])
        encoded_album = quote_plus(utwor['tytul']) 
        cover_link = f"https://covers.musichoarders.xyz/?artist={encoded_artist}&album={encoded_album}&country=us&sources=amazonmusic"
        item_description_parts.append(f'<a href="{cover_link}">COVER</a>')

        if utwor['youtube_id']:
            youtube_full_link = f'http://youtube.com/watch?v={utwor['youtube_id']}' # Wzór z Twojego poprzedniego zapytania
            item_description_parts.append(f' | <a href="{youtube_full_link}">YOUTUBE</a>')
        
        item_description = "".join(item_description_parts)
        ET.SubElement(item, 'description').text = item_description

        # Link do playlisty: myradioonline.pl kończy się na /playlista, ukradiolive.com na /playlist
        ET.SubElement(item, 'link').text = utwor['stacja_playlist_url']
        
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
        'BBC Radio 1': 'https://ukradiolive.com/bbc-radio-1',
        'BBC Radio 2': 'https://ukradiolive.com/bbc-radio-2',
        'Virgin Radio UK': 'https://ukradiolive.com/virgin-radio-uk',
        'Heart London': 'https://ukradiolive.com/heart-london',
        'Radio 357': 'https://myradioonline.pl/radio-357',
        'ChilliZET': 'https://myradioonline.pl/chillizet',
        'Radio Nowy Świat': 'https://myradioonline.pl/radio-nowy-swiat',
        'RMF FM': 'https://myradioonline.pl/rmf-fm/playlista', # Ten URL już ma /playlista
        'RMF MAXXX': 'https://myradioonline.pl/rmf-maxxx',
        'Radio ZET': 'https://myradioonline.pl/radio-zet',
        'PR Czwórka': 'https://myradioonline.pl/polskie-radio-czworka',
        'PR Trójka': 'https://myradioonline.pl/polskie-radio-trojka',
        'Radio Eska': 'https://myradioonline.pl/radio-eska'
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
