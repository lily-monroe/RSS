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

def parsuj_myradioonline(html_content, stacja_nazwa, stacja_url):
    """Parsuje listę utworów ze strony myradioonline.pl/playlista."""
    soup = BeautifulSoup(html_content, 'html.parser')
    # Szukamy divów o klasie 'yt-row' z itemprop="track"
    utwory_html = soup.find_all('div', itemprop='track', class_='yt-row')
    lista_parsowanych_utworow = []

    for utwor_html in utwory_html:
        # {%1} - data-youtube
        youtube_id = utwor_html.find('div', class_=re.compile(r'txt1 anim'))
        youtube_id = youtube_id.get('data-youtube', '') if youtube_id else ''
        
        # {%2} - data i czas odtworzenia (z span class="txt2 mcolumn" data-original-title)
        czas_emisji_span = utwor_html.find('span', class_='txt2 mcolumn')
        czas_emisji_pelny = czas_emisji_span.get('data-original-title', '').strip() if czas_emisji_span else ''

        # {%3} - nazwa artysty (span itemprop="byArtist")
        wykonawca_span = utwor_html.find('span', itemprop='byArtist')
        wykonawca = wykonawca_span.text.strip() if wykonawca_span else ''

        # {%4} - tytuł utworu (span itemprop="name")
        tytul_span = utwor_html.find('span', itemprop='name')
        tytul = tytul_span.text.strip() if tytul_span else ''

        # Adres zdjęcia (z span class="cont anim" > img data-lazy-load)
        # To jest ten sam obrazek co wcześniej, tylko teraz szukamy go w kontekście całego utworu
        image_span = utwor_html.find_previous_sibling('div', class_='songCont') # Sprawdź poprzedni sibling, jeśli struktura się zmieniła
        if not image_span: # Jeśli nie ma, szukamy w całym rodzicu
            image_span = utwor_html.find_parent('div', class_='songCont')
        
        image_url = ''
        if image_span:
            img_tag = image_span.find('img', class_='js-img-lload')
            image_url = img_tag.get('data-lazy-load', '') if img_tag else ''
        
        image_url_big = image_url.replace('50x50bb.webp', '1000x1000bb.webp') if image_url else ''

        # Jeśli brakuje kluczowych danych, pomijamy utwór
        if not (wykonawca and tytul and czas_emisji_pelny):
            continue

        lista_parsowanych_utworow.append({
            'stacja': stacja_nazwa,
            'stacja_url': stacja_url, # Dodajemy URL stacji do linku RSS
            'wykonawca': wykonawca,
            'tytul': tytul,
            'czas_emisji_pelny': czas_emisji_pelny, # Pełny czas emisji
            'image_url_big': image_url_big,
            'youtube_id': youtube_id # ID YouTube
        })
    return lista_parsowanych_utworow

def parsuj_ukradiolive(html_content, stacja_nazwa, stacja_url):
    """Parsuje listę utworów ze strony ukradiolive.com/playlist."""
    soup = BeautifulSoup(html_content, 'html.parser')
    lista_parsowanych_utworow = []

    # Struktura dla ukradiolive.com/playlist jest inna niż dla /bbc-radio-1/
    # Niestety nie ma tu tak rozbudowanych danych jak na myradioonline.pl (brak youtube_id, obrazków)
    playlist_items = soup.select('div.col-md-9 ul.list-group li.list-group-item') # Potencjalnie może być 'li.list-group-item'

    for item in playlist_items:
        text_content = item.get_text(strip=True)
        
        czas_emisji_str = ''
        wykonawca = ''
        tytul = ''

        # Próbujemy wyodrębnić czas i resztę
        # Format "1:00 AM - Artist - Title"
        match = re.match(r'(\d{1,2}:\d{2}\s(?:AM|PM))\s-\s(.*)', text_content)
        if match:
            czas_emisji_str = match.group(1).strip()
            artist_title_str = match.group(2).strip()

            # Konwertuj czas na format 24h i dodaj dzisiejszą datę
            try:
                dt_obj = datetime.strptime(czas_emisji_str, '%I:%M %p')
                # Zakładamy, że to utwory z bieżącego dnia
                dzisiejsza_data = datetime.now().strftime('%d.%m.%Y')
                czas_emisji_pelny = f"{dzisiejsza_data} {dt_obj.strftime('%H:%M')}"
            except ValueError:
                czas_emisji_pelny = f"{datetime.now().strftime('%d.%m.%Y')} {czas_emisji_str}" # Fallback
            
            if ' - ' in artist_title_str:
                parts = artist_title_str.split(' - ', 1)
                wykonawca = parts[0].strip()
                tytul = parts[1].strip()
            else:
                tytul = artist_title_str 
        else:
            # Jeśli format nie pasuje, użyj całego tekstu jako tytułu i bieżącego czasu
            tytul = text_content
            czas_emisji_pelny = f"{datetime.now().strftime('%d.%m.%Y')} {datetime.now().strftime('%H:%M')}"


        # Na tych stronach brakuje daty emisji, obrazków ani ID YouTube - zostawiamy puste
        lista_parsowanych_utworow.append({
            'stacja': stacja_nazwa,
            'stacja_url': stacja_url,
            'wykonawca': wykonawca,
            'tytul': tytul,
            'czas_emisji_pelny': czas_emisji_pelny, 
            'image_url_big': '', # Brak na tej stronie
            'youtube_id': '' # Brak na tej stronie
        })
    return lista_parsowanych_utworow


def wygeneruj_rss(wszystkie_utwory, nazwa_pliku="radio_playlist.xml"):
    """Generuje plik RSS 2.0 z danych utworów ze wszystkich stacji."""
    root = ET.Element('rss', version='2.0')
    channel = ET.SubElement(root, 'channel')
    ET.SubElement(channel, 'title').text = 'ALL RADIO' # Zgodnie z wymaganiem
    ET.SubElement(channel, 'link').text = 'https://github.com/lily-monroe/RSS' # Link do Twojego repo
    ET.SubElement(channel, 'description').text = 'Playlista z wielu stacji radiowych'

    # Opcjonalnie: sortowanie utworów przed dodaniem do RSS
    # Jeśli chcesz najnowsze na górze, upewnij się, że czas_emisji_pelny jest parsowalny
    # i użyj funkcji datetime do sortowania. 
    # np. posortowane_utwory = sorted(wszystkie_utwory, key=lambda x: datetime.strptime(x['czas_emisji_pelny'], '%d.%m.%Y %H:%M'), reverse=True)
    # Dla prostoty na razie dodajemy w kolejności zbierania

    for utwor in wszystkie_utwory:
        item = ET.SubElement(channel, 'item')
        
        # Element <title>
        item_title = f"[{utwor['stacja']}] {utwor['wykonawca']} - {utwor['tytul']} | {utwor['czas_emisji_pelny']}"
        ET.SubElement(item, 'title').text = item_title
        
        # Element <description>
        item_description_parts = []
        if utwor['image_url_big']:
            item_description_parts.append(f'<img src="{utwor["image_url_big"]}"><br><br>')
        
        item_description_parts.append(f'<b>{utwor["wykonawca"]} - {utwor["tytul"]}</b><br>')
        item_description_parts.append(f'{utwor["czas_emisji_pelny"]} | ')
        
        # Link do COVER - kodujemy wykonawcę i tytuł
        encoded_artist = quote_plus(utwor['wykonawca'])
        encoded_album = quote_plus(utwor['tytul']) # Album traktujemy jak tytuł utworu dla covers.musichoarders.xyz
        cover_link = f"https://covers.musichoarders.xyz/?artist={encoded_artist}&album={encoded_album}&country=us&sources=amazonmusic"
        item_description_parts.append(f'<a href="{cover_link}">COVER</a>')

        # Link do YOUTUBE - używamy pobranego {%1} (youtube_id)
        if utwor['youtube_id']:
            youtube_full_link = f'http://youtube.com/watch?v={utwor["youtube_id"]}'
            item_description_parts.append(f' | <a href="{youtube_full_link}">YOUTUBE</a>')
        
        item_description = "".join(item_description_parts)
        ET.SubElement(item, 'description').text = item_description

        # Element <link> - adres playlisty stacji
        ET.SubElement(item, 'link').text = utwor['stacja_url']
        
        # pubDate (opcjonalnie: konwersja czasu emisji na format RFC 822)
        # Dla prostoty, używamy aktualnej daty generowania, lub jeśli czas jest pewny, można parsować
        # try:
        #     dt_pub = datetime.strptime(utwor['czas_emisji_pelny'], '%d.%m.%Y %H:%M')
        #     ET.SubElement(item, 'pubDate').text = dt_pub.strftime('%a, %d %b %Y %H:%M:%S %z') # RFC 822 format
        # except ValueError:
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
                wszystkie_parsowane_utwory.extend(parsowane_utwory) # Poprawiona literówka
            else:
                print(f"Brak zdefiniowanej funkcji parsowania dla {url_stacji}")
        else:
            print(f"Nie udało się pobrać treści dla {url_stacji}")

    if wszystkie_parsowane_utwory:
        # Sortowanie utworów od najnowszych
        try:
            # Tworzymy słownik do przechowywania dat i czasów dla sortowania
            # Strony ukradiolive.com często nie podają roku, dlatego sortowanie może być niedokładne dla dat z różnych dni/lat
            # Jeśli utwory z ukradiolive.com mają tylko godzinę, traktujemy je jako z dzisiejszej daty.
            # Konwersja do datetime jest kluczowa dla poprawnego sortowania
            
            # Spróbuj parsować daty i godziny, a te które się nie uda, zostaw na końcu lub na początku
            def get_sort_key(item):
                try:
                    # Spróbuj parsować datę w formacie dd.mm.YYYY HH:MM
                    return datetime.strptime(item['czas_emisji_pelny'], '%d.%m.%Y %H:%M')
                except ValueError:
                    # Jeśli format się nie zgadza (np. dla ukradiolive), zwróć minimalną datę, 
                    # aby te utwory były na końcu listy po posortowaniu malejąco
                    return datetime.min 

            posortowane_utwory = sorted(wszystkie_parsowane_utwory, key=get_sort_key, reverse=True)
            wygeneruj_rss(posortowane_utwory, nazwa_pliku="radio_playlist.xml")
        except Exception as e:
            print(f"Błąd podczas sortowania utworów: {e}. Generuję RSS bez sortowania.")
            wygeneruj_rss(wszystkie_parsowane_utwory, nazwa_pliku="radio_playlist.xml")
            
    else:
        print("Nie pobrano żadnych utworów z żadnej stacji.")
