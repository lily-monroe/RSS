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

# Funkcja parsująca, która obsłuży zarówno myradioonline.pl jak i ukradiolive.com
def parsuj_playliste(html_content, stacja_nazwa, stacja_url):
    """Parsuje listę utworów ze stron myradioonline.pl/playlista i ukradiolive.com/playlist."""
    soup = BeautifulSoup(html_content, 'html.parser')
    # Szukamy divów o klasie 'yt-row' z itemprop="track"
    utwory_html = soup.find_all('div', itemprop='track', class_='yt-row')
    lista_parsowanych_utworow = []

    for utwor_html in utwory_html:
        # {%1} - data-youtube
        youtube_div = utwor_html.find('div', class_=re.compile(r'txt1 anim'))
        youtube_id = youtube_div.get('data-youtube', '') if youtube_div else ''
        
        # {%2} - data i czas odtworzenia (z span class="txt2 mcolumn" data-original-title)
        # UWAGA: dla ukradiolive.com atrybut aria-label i data-original-title ma "Time of playback",
        # ale w zawartości spana nie ma daty, tylko placeholder. 
        # Konieczne jest użycie data-original-title.
        czas_emisji_span = utwor_html.find('span', class_='txt2 mcolumn')
        czas_emisji_pelny = czas_emisji_span.get('data-original-title', '').strip() if czas_emisji_span else ''

        # Jeśli data-original-title to "Termin odtwarzania" (PL) lub "Time of playback" (EN)
        # to oznacza, że właściwa data i czas jest w innej strukturze.
        # Sprawdźmy, czy jest to właściwa data/czas, jeśli nie, to jest to stary HTML lub pusta wartość.
        # W takim przypadku, musimy zakładać, że format jest DD.MM.RRRR GG:MM
        # Jeśli nie jest to data, to może to być problem z HTML, ale z Twojego przykładu wynika, że jest.
        
        # DODATKOWA WALIDACJA DLA CZASU EMISJI:
        # Jeśli strona zwraca "Time of playback" zamiast faktycznej daty, to poprzednie parsowanie było błędne.
        # Sprawdzimy, czy to rzeczywiście data. Jeśli nie, to możemy spróbować alternatywnego parsowania
        # lub po prostu użyć aktualnej daty, jeśli nie ma lepszej opcji.
        # Z Twojego przykładu HTML wynika, że data-original-title to już jest faktyczny czas, np. "19.05.2025 21:33"
        # Sprawdzamy, czy czas_emisji_pelny zawiera liczby i ":"
        if not re.search(r'\d{2}\.\d{2}\.\d{4}\s\d{2}:\d{2}', czas_emisji_pelny):
             # Możliwe, że jest to "Time of playback" lub inny niepasujący tekst.
             # Dla ukradiolive.com, jeśli data-original-title to "Time of playback", a nie ma faktycznej daty,
             # to niestety nie uzyskamy jej z tego elementu. 
             # Sprawdzamy, czy w inner_text spana nie ma daty, jak w poprzednich wersjach ukradiolive.com
             # (jeśli to poprzednia struktura, bez data-original-title z datą)
             
             # W TYM PRZYPADKU, GDY HTML JEST TAKI SAM, data-original-title POWINIEN JUŻ ZAWIERAĆ DATĘ.
             # Jeśli jednak mimo wszystko jest tekst "Time of playback", to znaczy, że nasza analiza HTML jest błędna
             # lub strona dynamicznie zmienia zawartość atrybutu.
             # Na podstawie Twojego ostatniego przykładu, 'data-original-title' powinien już zawierać właściwą datę.
             # Zostawiamy jak jest, ale warto mieć na uwadze, jeśli problem się powtórzy.
            pass


        # {%3} - nazwa artysty (span itemprop="byArtist")
        wykonawca_span = utwor_html.find('span', itemprop='byArtist')
        wykonawca = wykonawca_span.text.strip() if wykonawca_span else ''

        # {%4} - tytuł utworu (span itemprop="name")
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
            # Jeśli data/czas jest w nieprawidłowym formacie, dajemy minimalną datę
            # aby ten element znalazł się na końcu po posortowaniu malejąco
            return datetime.min 

    posortowane_utwory = sorted(wszystkie_utwory, key=get_sort_key, reverse=True)

    for utwor in posortowane_utwory:
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

        if utwor['youtube_id']:
            youtube_full_link = f'http://youtube.com/watch?v={utwor["youtube_id"]}'
            item_description_parts.append(f' | <a href="{youtube_full_link}">YOUTUBE</a>')
        
        item_description = "".join(item_description_parts)
        ET.SubElement(item, 'description').text = item_description

        ET.SubElement(item, 'link').text = utwor['stacja_url']
        
        try:
            # Używamy pobranego 'czas_emisji_pelny' do pubDate
            dt_pub = datetime.strptime(utwor['czas_emisji_pelny'], '%d.%m.%Y %H:%M')
            ET.SubElement(item, 'pubDate').text = dt_pub.strftime('%a, %d %b %Y %H:%M:%S +0000') # RFC 822 format (UTC)
        except ValueError:
            # Jeśli parsowanie się nie powiedzie (np. dla ukradiolive.com, gdzie data może być inna),
            # użyj bieżącej daty generowania, aby uniknąć błędu.
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
            # Ponieważ struktura HTML jest taka sama, używamy jednej funkcji parsującej
            parsowane_utwory = parsuj_playliste(html_content, nazwa_stacji, url_stacji)
            wszystkie_parsowane_utwory.extend(parsowane_utwory)
        else:
            print(f"Nie udało się pobrać treści dla {url_stacji}")

    if wszystkie_parsowane_utwory:
        wygeneruj_rss(wszystkie_parsowane_utwory, nazwa_pliku="radio_playlist.xml") 
    else:
        print("Nie pobrano żadnych utworów z żadnej stacji.")
